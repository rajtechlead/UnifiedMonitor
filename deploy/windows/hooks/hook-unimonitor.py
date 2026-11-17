"""
PyInstaller hook for unimonitor package.

Collects all YAML control files and other package data
that PyInstaller's static analysis wouldn't find automatically.
"""

import os

# Importing unimonitor.db builds Settings, which refuses to initialise in
# production without a real secret key. The build machine has no runtime
# configuration, so pin a non-production environment for collection only;
# the packaged executable still reads its own .env / environment at runtime.
os.environ.setdefault("UNIMONITOR_ENV", "test")
os.environ.setdefault("UNIMONITOR_SECRET_KEY", "build-time-only-not-a-runtime-secret")  # noqa: S105

from PyInstaller.utils.hooks import collect_data_files, collect_submodules  # noqa: E402

# Collect all package data (YAML, templates, bundled frontend, etc.)
datas = collect_data_files("unimonitor")

# Collect all submodules so dynamic imports work at runtime
hiddenimports = collect_submodules("unimonitor")
