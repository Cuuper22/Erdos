// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{State, Window};
use log::{info, warn};

// ── Event types emitted to the frontend ──

#[derive(Clone, Serialize)]
struct LogEvent {
    timestamp: String,
    level: String,
    message: String,
}

#[derive(Clone, Serialize)]
struct CostUpdateEvent {
    cost_usd: f64,
    total_spent_usd: f64,
    remaining_usd: f64,
    input_tokens: u64,
    output_tokens: u64,
}

#[derive(Clone, Serialize)]
struct SolutionFoundEvent {
    problem_id: String,
    attempts: i32,
    proof_preview: String,
    is_elegant: bool,
}

#[derive(Clone, Serialize)]
struct AttemptResultEvent {
    problem_id: String,
    attempt: i32,
    status: String,
    message: String,
}

#[derive(Clone, Serialize)]
struct MiningStatusEvent {
    status: String,  // "started", "stopped", "crashed", "completed"
    message: String,
    exit_code: Option<i32>,
}

// ── Settings from the frontend ──

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Settings {
    api_key: String,
    provider: String,  // "openai", "anthropic", "google", "ollama"
    model: String,
    max_cost: f64,
    ollama_url: String,
}

// ── Shared state ──

struct MiningState {
    is_running: AtomicBool,
    child: Mutex<Option<u32>>,  // PID of the running process
}

// ── Helper: emit a log event ──

fn emit_log(window: &Window, level: &str, message: &str) {
    let event = LogEvent {
        timestamp: chrono::Utc::now().to_rfc3339(),
        level: level.to_string(),
        message: message.to_string(),
    };
    let _ = window.emit("log-event", event);
}

fn emit_status(window: &Window, status: &str, message: &str, exit_code: Option<i32>) {
    let event = MiningStatusEvent {
        status: status.to_string(),
        message: message.to_string(),
        exit_code,
    };
    let _ = window.emit("mining-status", event);
}

// ── Parse a JSON line from the Python process ──

fn parse_and_emit_json_line(window: &Window, line: &str) {
    let parsed: Result<serde_json::Value, _> = serde_json::from_str(line);
    match parsed {
        Ok(value) => {
            let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("unknown");
            match event_type {
                "log" => {
                    emit_log(
                        window,
                        value.get("level").and_then(|v| v.as_str()).unwrap_or("info"),
                        value.get("message").and_then(|v| v.as_str()).unwrap_or(""),
                    );
                }
                "cost_update" => {
                    let event = CostUpdateEvent {
                        cost_usd: value.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
                        total_spent_usd: value.get("total_spent_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
                        remaining_usd: value.get("remaining_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
                        input_tokens: value.get("input_tokens").and_then(|v| v.as_u64()).unwrap_or(0),
                        output_tokens: value.get("output_tokens").and_then(|v| v.as_u64()).unwrap_or(0),
                    };
                    let _ = window.emit("cost-update", event);
                }
                "solution_found" => {
                    let event = SolutionFoundEvent {
                        problem_id: value.get("problem_id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        attempts: value.get("attempts").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
                        proof_preview: value.get("proof_preview").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        is_elegant: value.get("is_elegant").and_then(|v| v.as_bool()).unwrap_or(false),
                    };
                    let _ = window.emit("solution-found", event);
                }
                "attempt_result" => {
                    let event = AttemptResultEvent {
                        problem_id: value.get("problem_id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        attempt: value.get("attempt").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
                        status: value.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        message: value.get("message").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    };
                    let _ = window.emit("attempt-result", event);
                }
                "problem_started" => {
                    emit_log(window, "info", &format!(
                        "Starting problem: {}",
                        value.get("problem_id").and_then(|v| v.as_str()).unwrap_or("?")
                    ));
                }
                "problem_failed" => {
                    emit_log(window, "warning", &format!(
                        "Problem {} failed after {} attempts",
                        value.get("problem_id").and_then(|v| v.as_str()).unwrap_or("?"),
                        value.get("attempts").and_then(|v| v.as_i64()).unwrap_or(0),
                    ));
                }
                "mining_complete" => {
                    emit_log(window, "success", &format!(
                        "Mining complete: {}/{} solved, ${:.4} spent",
                        value.get("solved").and_then(|v| v.as_i64()).unwrap_or(0),
                        value.get("total_problems").and_then(|v| v.as_i64()).unwrap_or(0),
                        value.get("total_cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
                    ));
                }
                _ => {
                    // Unknown event type — emit as raw log
                    emit_log(window, "debug", line);
                }
            }
        }
        Err(_) => {
            // Not JSON — emit as plain log
            if !line.trim().is_empty() {
                emit_log(window, "info", line);
            }
        }
    }
}

// ── Commands ──

#[tauri::command]
fn check_environment() -> bool {
    let python_check = Command::new("python3")
        .arg("--version")
        .output()
        .or_else(|_| Command::new("python").arg("--version").output());

    python_check.map(|o| o.status.success()).unwrap_or(false)
}

#[tauri::command]
async fn setup_environment(window: Window) -> Result<bool, String> {
    emit_log(&window, "info", "Checking Python installation...");

    let python_cmd = if Command::new("python3").arg("--version").output().is_ok() {
        "python3"
    } else {
        "python"
    };

    match Command::new(python_cmd).arg("--version").output() {
        Ok(output) => {
            let version = String::from_utf8_lossy(&output.stdout);
            emit_log(&window, "success", &format!("Python found: {}", version.trim()));
        }
        Err(_) => {
            emit_log(&window, "error", "Python 3 not found. Please install Python 3.11+");
            return Err("Python not found".to_string());
        }
    }

    emit_log(&window, "info", "Setting up Lean/elan environment...");

    let setup_result = Command::new(python_cmd)
        .args(["-m", "src.environment", "--install"])
        .current_dir("..")
        .output();

    match setup_result {
        Ok(output) => {
            if output.status.success() {
                emit_log(&window, "success", "Environment setup complete!");
            } else {
                let stderr = String::from_utf8_lossy(&output.stderr);
                emit_log(&window, "warning", &format!("Setup completed with warnings: {}", stderr));
            }
            Ok(true)
        }
        Err(e) => {
            emit_log(&window, "warning", &format!("Setup script error: {}. Manual setup may be required.", e));
            Ok(true)
        }
    }
}

#[tauri::command]
async fn start_mining(
    window: Window,
    settings: Settings,
    state: State<'_, Arc<MiningState>>,
) -> Result<(), String> {
    if state.is_running.load(Ordering::SeqCst) {
        return Err("Mining is already running".to_string());
    }

    state.is_running.store(true, Ordering::SeqCst);
    emit_status(&window, "started", "Mining session starting", None);

    let python_cmd = if Command::new("python3").arg("--version").output().is_ok() {
        "python3"
    } else {
        "python"
    };

    emit_log(&window, "info", &format!(
        "Starting mining with {} / {} (budget: ${:.2})",
        settings.provider, settings.model, settings.max_cost
    ));

    // Build the command
    let mut cmd = Command::new(python_cmd);
    cmd.args(["-m", "src.solver", "--manifest", "manifest.json", "--json-logs"])
        .current_dir("..")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    // Set provider-specific env vars
    cmd.env("MAX_COST_USD", settings.max_cost.to_string());
    cmd.env("LLM_MODEL", &settings.model);

    match settings.provider.as_str() {
        "openai" => { cmd.env("OPENAI_API_KEY", &settings.api_key); }
        "anthropic" => { cmd.env("ANTHROPIC_API_KEY", &settings.api_key); }
        "google" => {
            cmd.env("GEMINI_API_KEY", &settings.api_key);
            cmd.env("GOOGLE_API_KEY", &settings.api_key);
        }
        "ollama" => { cmd.env("OLLAMA_URL", &settings.ollama_url); }
        _ => {}
    }

    // Spawn the process
    let mut child: Child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            state.is_running.store(false, Ordering::SeqCst);
            emit_status(&window, "crashed", &format!("Failed to start: {}", e), None);
            return Err(format!("Failed to spawn process: {}", e));
        }
    };

    // Store PID for stop_mining
    let pid = child.id();
    {
        let mut pid_lock = state.child.lock().unwrap();
        *pid_lock = Some(pid);
    }

    info!("Mining process spawned with PID {}", pid);

    // Read stdout in a separate thread (line-by-line streaming)
    let stdout = child.stdout.take().expect("stdout was piped");
    let window_clone = window.clone();
    let stdout_handle = std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(line) => parse_and_emit_json_line(&window_clone, &line),
                Err(e) => {
                    warn!("Error reading stdout: {}", e);
                    break;
                }
            }
        }
    });

    // Read stderr in a separate thread
    let stderr = child.stderr.take().expect("stderr was piped");
    let window_clone2 = window.clone();
    let stderr_handle = std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            match line {
                Ok(line) if !line.trim().is_empty() => {
                    let level = if line.to_lowercase().contains("error") { "error" }
                        else if line.to_lowercase().contains("warning") { "warning" }
                        else { "info" };
                    emit_log(&window_clone2, level, &line);
                }
                _ => {}
            }
        }
    });

    // Wait for process to exit
    let exit_status = child.wait();

    // Wait for reader threads to finish
    let _ = stdout_handle.join();
    let _ = stderr_handle.join();

    // Clear stored PID
    {
        let mut pid_lock = state.child.lock().unwrap();
        *pid_lock = None;
    }

    state.is_running.store(false, Ordering::SeqCst);

    match exit_status {
        Ok(status) => {
            let code = status.code();
            if status.success() {
                emit_status(&window, "completed", "Mining session completed", code);
                emit_log(&window, "success", "Mining session completed successfully!");
            } else {
                emit_status(&window, "crashed", &format!("Process exited with code {:?}", code), code);
                emit_log(&window, "error", &format!("Mining process exited with code {:?}", code));
            }
        }
        Err(e) => {
            emit_status(&window, "crashed", &format!("Process error: {}", e), None);
            emit_log(&window, "error", &format!("Mining process error: {}", e));
        }
    }

    Ok(())
}

#[tauri::command]
fn stop_mining(
    window: Window,
    state: State<'_, Arc<MiningState>>,
) -> Result<(), String> {
    if !state.is_running.load(Ordering::SeqCst) {
        return Ok(());
    }

    let pid = {
        let pid_lock = state.child.lock().unwrap();
        *pid_lock
    };

    if let Some(pid) = pid {
        emit_log(&window, "info", &format!("Stopping mining process (PID {})", pid));

        // Platform-specific process kill
        #[cfg(target_os = "windows")]
        {
            // Windows: use taskkill /t to kill the process tree
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .output();
        }

        #[cfg(not(target_os = "windows"))]
        {
            // Unix: send SIGTERM, then SIGKILL after a delay
            unsafe {
                libc::kill(pid as i32, libc::SIGTERM);
            }
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_secs(5));
                unsafe {
                    libc::kill(pid as i32, libc::SIGKILL);
                }
            });
        }

        emit_status(&window, "stopped", "Mining stopped by user", None);
    }

    state.is_running.store(false, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
fn is_mining_running(state: State<'_, Arc<MiningState>>) -> bool {
    state.is_running.load(Ordering::SeqCst)
}

// ── Settings persistence ──

fn settings_path() -> PathBuf {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    home.join(".erdos-prover").join("settings.json")
}

#[tauri::command]
fn save_settings(settings: Settings) -> Result<(), String> {
    let path = settings_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let json = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| e.to_string())?;

    info!("Settings saved to {:?}", path);
    Ok(())
}

#[tauri::command]
fn load_settings() -> Result<Option<Settings>, String> {
    let path = settings_path();
    if !path.exists() {
        return Ok(None);
    }

    let contents = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let settings: Settings = serde_json::from_str(&contents).map_err(|e| {
        warn!("Corrupt settings file, using defaults: {}", e);
        e.to_string()
    })?;

    Ok(Some(settings))
}

fn main() {
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();

    info!("Starting Erdos Prover application");

    tauri::Builder::default()
        .manage(Arc::new(MiningState {
            is_running: AtomicBool::new(false),
            child: Mutex::new(None),
        }))
        .invoke_handler(tauri::generate_handler![
            check_environment,
            setup_environment,
            start_mining,
            stop_mining,
            is_mining_running,
            save_settings,
            load_settings
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
