# Build with:  pyinstaller --clean vidx.spec
#
# Do NOT build with `pyinstaller --onefile vidx_entry.py` -- that ignores this
# file, so none of the hiddenimports or datas below are bundled. The v0.4.0-v0.4.3
# releases were built that way and shipped an exe whose --align crashed on the
# missing uroman data tables.
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

try:
    import uroman
except ImportError:  # fail loudly rather than silently omitting the aligner
    raise SystemExit(
        "vidx.spec requires the optional extras at build time.\n"
        '    pip install -e ".[align,youtube]"\n'
        "Without them PyInstaller produces an exe that fails at runtime."
    )

hidden_imports = (
    collect_submodules('charset_normalizer')
    + collect_submodules('requests')
    + collect_submodules('urllib3')
    + collect_submodules('googleapiclient')
    + collect_submodules('google.auth')
    + collect_submodules('google.oauth2')
    + collect_submodules('google_auth_oauthlib')
    + collect_submodules('google_auth_httplib2')
    + collect_submodules('oauthlib')
    + collect_submodules('requests_oauthlib')
    + collect_submodules('uritemplate')
    + collect_submodules('httplib2')
    + collect_submodules('pyasn1')
    + collect_submodules('pyasn1_modules')
    + collect_submodules('rsa')
    + collect_submodules('cachetools')
    + collect_submodules('uroman')
    + ['chardet']
)

uroman_data_dir = os.path.join(os.path.dirname(uroman.__file__), 'data')
datas_list = (
    collect_data_files('charset_normalizer')
    + collect_data_files('certifi')
    + collect_data_files('requests')
    + collect_data_files('googleapiclient')
    + collect_data_files('google_auth_oauthlib')
    + collect_data_files('google.auth')
    + [(uroman_data_dir, 'uroman/data')]
)

a = Analysis(
    ['vidx_entry.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='vidx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
