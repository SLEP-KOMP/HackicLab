# -*- mode: python ; coding: utf-8 -*-

# Имя файла говорит, что это и для какой платформы:
# HackicLab_<версия>_windows_x64.exe
import os
import re
from pathlib import Path

from PySide6.QtCore import QLibraryInfo

SPEC_DIR = Path(globals().get("SPECPATH") or os.getcwd())
VERSION = re.search(
    r'__version__ = "([^"]+)"',
    (SPEC_DIR / "hackiclab" / "__init__.py").read_text(encoding="utf-8"),
).group(1)
EXE_NAME = f"HackicLab_{VERSION}_windows_x64"

QT_TRANSLATIONS = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('hackiclab/assets/acpi', 'hackiclab/assets/acpi'),
        ('hackiclab/assets/brands', 'hackiclab/assets/brands'),
        ('hackiclab/assets/support', 'hackiclab/assets/support'),
        (QT_TRANSLATIONS + '/qtbase_ru.qm', 'PySide6/translations'),
    ],
    hiddenimports=[
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
    name=EXE_NAME,
    icon=str(SPEC_DIR / "hackiclab" / "assets" / "branding" / "icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    uac_admin=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
