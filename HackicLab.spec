# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('hackiclab/assets/acpi', 'hackiclab/assets/acpi'),
    ],
    hiddenimports=[
        'psutil',
        'hackiclab.scanner',
        'hackiclab.knowledge',
        'hackiclab.builder',
        'hackiclab.analyzer',
        'hackiclab.ui',
        'hackiclab.scanner.diskmap',
        'hackiclab.builder.usb_map',
        'hackiclab.builder.config_editor',
        'hackiclab.builder.history',
        'hackiclab.analyzer.oc_log',
        'hackiclab.analyzer.efi_health',
        'hackiclab.knowledge.rationale',
    ],
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
    name='HackicLab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
