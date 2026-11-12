"""
PyInstaller hook for unimonitor package.

Collects all YAML control files and other package data
that PyInstaller's static analysis wouldn't find automatically.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all package data (YAML, templates, etc.)
datas = collect_data_files("unimonitor")

# Collect all submodules so dynamic imports work at runtime
hiddenimports = collect_submodules("unimonitor")
