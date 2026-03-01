// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{Manager, State, Window};
use log::{info, warn, error};
use chrono;

// Global state for mining control
struct MiningState {
    is_running: AtomicBool,
}

#[derive(Clone, Serialize)]
struct LogEvent {
    timestamp: String,
    level: String,
    message: String,
}

#[derive(Clone, Serialize)]
struct SolutionEvent {
    problem_id: String,
    timestamp: String,
    attempts: i32,
    status: String,
}

#[derive(Deserialize)]
struct Settings {
    api_key: String,
    provider: String,
    model: String,
    max_cost: f64,
    ollama_url: String,
}

fn emit_log(window: &Window, level: &str, message: &str) {
    let event = LogEvent {
        timestamp: chrono::Utc::now().to_rfc3339(),
        level: level.to_string(),
        message: message.to_string(),
    };
    if let Err(e) = window.emit("log-event", event) {
        error!("Failed to emit log event: {}", e);
    }
}

#[tauri::command]
fn check_environment() -> bool {
    // Check if Python is available
    let python_check = Command::new("python3")
        .arg("--version")
        .output();
    
    if python_check.is_err() {
        return false;
    }
    
    // Check if elan/lean is available (optional)
    let lean_check = Command::new("lean")
        .arg("--version")
        .output();
    
    // Return true if at least Python is available
    python_check.is_ok()
}

#[tauri::command]
async fn setup_environment(window: Window) -> Result<bool, String> {
    emit_log(&window, "info", "Checking Python installation...");
    
    // Check Python
    let python_check = Command::new("python3")
        .arg("--version")
        .output();
    
    match python_check {
        Ok(output) => {
            let version = String::from_utf8_lossy(&output.stdout);
            emit_log(&window, "success", &format!("Python found: {}", version.trim()));
        }
        Err(_) => {
            emit_log(&window, "error", "Python 3 not found. Please install Python 3.11+");
            return Err("Python not found".to_string());
        }
    }
    
    emit_log(&window, "info", "Checking Lean/elan installation...");
    
    // Try to run the environment setup script
    let setup_result = Command::new("python3")
        .args(["-m", "src.environment", "--install"])
        .current_dir("..")
        .output();
    
    match setup_result {
        Ok(output) => {
            if output.status.success() {
                emit_log(&window, "success", "Environment setup complete!");
                Ok(true)
            } else {
                let stderr = String::from_utf8_lossy(&output.stderr);
                emit_log(&window, "warning", &format!("Setup completed with warnings: {}", stderr));
                Ok(true)
            }
        }
        Err(e) => {
            emit_log(&window, "warning", &format!("Could not run setup script: {}. Manual setup may be required.", e));
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
    
    emit_log(&window, "info", &format!("Starting mining with {} / {}", settings.provider, settings.model));
    emit_log(&window, "info", &format!("Budget limit: ${:.2}", settings.max_cost));
    
    // Set environment variables for the Python script
    let mut env_vars = vec![
        ("MAX_COST_USD", settings.max_cost.to_string()),
        ("LLM_MODEL", settings.model.clone()),
    ];
    
    match settings.provider.as_str() {
        "openai" => env_vars.push(("OPENAI_API_KEY", settings.api_key.clone())),
        "anthropic" => env_vars.push(("ANTHROPIC_API_KEY", settings.api_key.clone())),
        "ollama" => env_vars.push(("OLLAMA_URL", settings.ollama_url.clone())),
        _ => {}
    }
    
    emit_log(&window, "info", "Loading problem manifest...");
    
    // Run the Python solver
    let mut cmd = Command::new("python3");
    cmd.args(["-m", "src.solver", "--manifest", "manifest.json"])
        .current_dir("..");
    
    for (key, value) in env_vars {
        cmd.env(key, value);
    }
    
    match cmd.output() {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            
            for line in stdout.lines() {
                if !line.is_empty() {
                    emit_log(&window, "info", line);
                }
            }
            
            if !stderr.is_empty() {
                for line in stderr.lines() {
                    let line_lower = line.to_lowercase();
                    if line_lower.contains("error") {
                        emit_log(&window, "error", line);
                    } else if line_lower.contains("warning") {
                        emit_log(&window, "warning", line);
                    } else {
                        emit_log(&window, "info", line);
                    }
                }
            }
            
            if output.status.success() {
                emit_log(&window, "success", "Mining session completed successfully!");
            } else {
                emit_log(&window, "warning", "Mining session ended with errors");
            }
        }
        Err(e) => {
            emit_log(&window, "error", &format!("Failed to start mining: {}", e));
        }
    }
    
    state.is_running.store(false, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
fn stop_mining(state: State<'_, Arc<MiningState>>) -> Result<(), String> {
    state.is_running.store(false, Ordering::SeqCst);
    Ok(())
}

fn main() {
    // Initialize logging
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();

    info!("Starting Erdos Prover application");

    tauri::Builder::default()
        .manage(Arc::new(MiningState {
            is_running: AtomicBool::new(false),
        }))
        .invoke_handler(tauri::generate_handler![
            check_environment,
            setup_environment,
            start_mining,
            stop_mining
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
