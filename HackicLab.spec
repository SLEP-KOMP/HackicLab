# -*- mode: python ; coding: utf-8 -*-

# Переводы Qt (qtbase_*.qm): без них стандартные кнопки остаются на английском
from PySide6.QtCore import QLibraryInfo

QT_TRANSLATIONS = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('hackiclab/assets/acpi', 'hackiclab/assets/acpi'),
        ('hackiclab/assets/brands', 'hackiclab/assets/brands'),
        ('hackiclab/assets/hwdb', 'hackiclab/assets/hwdb'),
        ('hackiclab/assets/support', 'hackiclab/assets/support'),
        ('hackiclab/assets/hero', 'hackiclab/assets/hero'),
        (QT_TRANSLATIONS + '/qtbase_ru.qm', 'PySide6/translations'),
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
        'hackiclab.builder.amd_patches',
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    uac_admin=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
