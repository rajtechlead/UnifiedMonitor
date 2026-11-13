# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for UniMonitor Windows executable
#
# Build:   pyinstaller deploy/windows/unimonitor.spec --clean
# Output:  dist/UniMonitor/UniMonitor.exe  (folder mode)
#          dist/UniMonitor-Setup.exe       (after NSIS step)

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent.parent  # repo root

block_cipher = None

# ── Collect all data files the app needs at runtime ───────────────────────────
datas = [
    # YAML control definitions
    (str(ROOT / "controls"), "controls"),
    # Alembic migrations (directory is 'alembic/', not 'migrations/')
    (str(ROOT / "alembic.ini"), "."),
    (str(ROOT / "alembic"), "alembic"),
    # Jinja2 templates used by reporting
    (str(ROOT / "unimonitor" / "reporting" / "templates"), "unimonitor/reporting/templates"),
    # Branding assets
    (str(ROOT / "branding"), "branding"),
    # Windows-specific scripts
    (str(ROOT / "deploy" / "windows" / "scripts"), "scripts"),
]

# ── Hidden imports that PyInstaller static analysis misses ────────────────────
hiddenimports = [
    # SQLAlchemy dialects
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.postgresql",
    "aiosqlite",
    "asyncpg",
    # Alembic env
    "alembic.config",
    "alembic.command",
    # FastAPI / Starlette internals
    "fastapi.middleware.cors",
    "fastapi.staticfiles",
    "starlette.routing",
    # Pydantic
    "pydantic.networks",
    "pydantic_settings",
    # Direct bcrypt (passlib removed; bcrypt>=4.0.0 used directly)
    "bcrypt",
    # Cryptography
    "cryptography.hazmat.backends.openssl",
    # JOSE JWT
    "jose.jwt",
    # Structlog
    "structlog._frames",
    # YAML
    "yaml",
    # Celery
    "celery.app.builtins",
    "celery.backends.redis",
    # UniMonitor modules (lazy-imported)
    "unimonitor.cli",
    "unimonitor.main",
    "unimonitor.config",
    "unimonitor.db.base",
    "unimonitor.db.models",
    "unimonitor.db.session",
    "unimonitor.grc.control_loader",
    "unimonitor.grc.scoring",
    "unimonitor.grc.crosswalk",
    "unimonitor.worker.celery_app",
    "unimonitor.core.cache",
    "unimonitor.core.logging",
    "unimonitor.auth.dependencies",
    "unimonitor.graph.client",
    "unimonitor.secrets.factory",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "unimonitor" / "cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "deploy" / "windows" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "cv2",
        "torch",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Package ───────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file EXE (--onefile) is slow to start; use folder mode and wrap with NSIS
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UniMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # keeps console window (server app — not a GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "branding" / "icon.ico") if (ROOT / "branding" / "icon.ico").exists() else None,
    version=str(ROOT / "deploy" / "windows" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UniMonitor",
)
