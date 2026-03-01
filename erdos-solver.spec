# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Erdos Proof Mining solver.

Bundles the solver and all LLM provider dependencies into a single executable.
The resulting binary is used as a Tauri sidecar — the GUI launches it as a
subprocess and communicates via JSON Lines on stdout.
"""

import sys
from PyInstaller.utils.hooks import collect_submodules

# Collect all submodules for providers that use dynamic imports
hidden_imports = [
    # Core
    'src.solver',
    'src.config',
    'src.events',
    'src.validator',
    'src.packager',
    'src.environment',
    'src.manifest',
    'src.campaign',
    'src.sandbox',
    'src.logging_config',
    # LLM providers
    'src.llm',
    'src.llm.factory',
    'src.llm.base',
    'src.llm.openai_provider',
    'src.llm.anthropic_provider',
    'src.llm.gemini',
    'src.llm.ollama_provider',
    # Third-party with dynamic imports
    'google.generativeai',
    'google.ai.generativelanguage',
    'google.auth',
    'google.auth.transport.requests',
    'google.api_core',
    'openai',
    'anthropic',
    'httpx',
    'httpcore',
    'certifi',
    'charset_normalizer',
    'idna',
    'urllib3',
    'requests',
]

# Collect google-generativeai submodules (heavily dynamic)
try:
    hidden_imports += collect_submodules('google.generativeai')
    hidden_imports += collect_submodules('google.ai')
except Exception:
    pass

a = Analysis(
    ['src/solver.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('manifest.json', '.'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='erdos-solver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Must be console app — Tauri reads stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
