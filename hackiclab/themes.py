"""Темы оформления HackicLab (тёмная, светлая, системная)."""

from __future__ import annotations

DARK_QSS = """
QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background-color: #1e1e2e; }
#sidebar { background-color: #181825; border-right: 1px solid #313244; }
#sidebar QLabel#logo { color: #f5c2e7; font-size: 22px; font-weight: 800; padding: 16px 12px 4px 12px; }
#sidebar QLabel#sub { color: #7f849c; font-size: 11px; padding: 0 12px 12px 12px; }
#navList { background: transparent; border: none; outline: none; }
#navList::item { padding: 12px 16px; margin: 2px 8px; border-radius: 8px; color: #a6adc8; }
#navList::item:hover { background: #313244; color: #cdd6f4; }
#navList::item:selected { background: #8839ef; color: white; font-weight: 600; }
QPushButton { background: #8839ef; color: white; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #9d4ef0; }
QPushButton:disabled { background: #45475a; color: #7f849c; }
QPushButton#ghost { background: transparent; border: 1px solid #45475a; color: #cdd6f4; }
QPushButton#ghost:hover { background: #313244; }
#card { background: #181825; border: 1px solid #313244; border-radius: 12px; padding: 14px; }
QLabel#h1 { font-size: 20px; font-weight: 700; color: #cdd6f4; }
QLabel#h2 { font-size: 14px; font-weight: 600; color: #a6adc8; }
QLabel#val { font-size: 13px; color: #e1e3ec; }
QLabel#muted { color: #7f849c; font-size: 12px; }
QLabel#kv { color: #7f849c; font-size: 12px; }
QGroupBox { border: 1px solid #313244; border-radius: 10px; margin-top: 14px; padding: 12px 10px; color: #a6adc8; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar { background: #313244; border: none; border-radius: 6px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #8839ef; border-radius: 6px; }
QTextEdit, QPlainTextEdit { background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; font-family: 'Cascadia Code','Consolas'; font-size: 12px; }
QListWidget { background: #181825; border: 1px solid #313244; border-radius: 8px; }
QListWidget::item { padding: 8px; }
QListWidget#issueList::item { border-bottom: 1px solid #252536; padding: 6px; }
QComboBox { background: #181825; border: 1px solid #313244; border-radius: 8px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #181825; selection-background-color: #8839ef; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 2px solid #45475a; background: #181825; }
QCheckBox::indicator:checked { background: #8839ef; border-color: #8839ef; }
QSplitter::handle { background: #313244; }
QLineEdit { background: #181825; border: 1px solid #313244; border-radius: 8px; padding: 6px 10px; }
"""

LIGHT_QSS = """
QWidget { background-color: #f4f5f7; color: #1f2328; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background-color: #f4f5f7; }
#sidebar { background-color: #e8eaed; border-right: 1px solid #d0d3d8; }
#sidebar QLabel#logo { color: #8839ef; font-size: 22px; font-weight: 800; padding: 16px 12px 4px 12px; }
#sidebar QLabel#sub { color: #6c7278; font-size: 11px; padding: 0 12px 12px 12px; }
#navList { background: transparent; border: none; outline: none; }
#navList::item { padding: 12px 16px; margin: 2px 8px; border-radius: 8px; color: #444b53; }
#navList::item:hover { background: #d0d3d8; color: #1f2328; }
#navList::item:selected { background: #8839ef; color: white; font-weight: 600; }
QPushButton { background: #8839ef; color: white; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #9d4ef0; }
QPushButton:disabled { background: #c3c8ce; color: #6c7278; }
QPushButton#ghost { background: transparent; border: 1px solid #c3c8ce; color: #1f2328; }
QPushButton#ghost:hover { background: #e0e3e6; }
#card { background: #ffffff; border: 1px solid #d0d3d8; border-radius: 12px; padding: 14px; }
QLabel#h1 { font-size: 20px; font-weight: 700; color: #1f2328; }
QLabel#h2 { font-size: 14px; font-weight: 600; color: #444b53; }
QLabel#val { font-size: 13px; color: #1f2328; }
QLabel#muted { color: #6c7278; font-size: 12px; }
QLabel#kv { color: #6c7278; font-size: 12px; }
QGroupBox { border: 1px solid #d0d3d8; border-radius: 10px; margin-top: 14px; padding: 12px 10px; color: #444b53; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar { background: #d0d3d8; border: none; border-radius: 6px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #8839ef; border-radius: 6px; }
QTextEdit, QPlainTextEdit { background: #ffffff; border: 1px solid #d0d3d8; border-radius: 8px; color: #1f2328; font-family: 'Cascadia Code','Consolas'; font-size: 12px; }
QListWidget { background: #ffffff; border: 1px solid #d0d3d8; border-radius: 8px; }
QListWidget::item { padding: 8px; }
QListWidget#issueList::item { border-bottom: 1px solid #eceef0; padding: 6px; }
QComboBox { background: #ffffff; border: 1px solid #d0d3d8; border-radius: 8px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #8839ef; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 2px solid #c3c8ce; background: #ffffff; }
QCheckBox::indicator:checked { background: #8839ef; border-color: #8839ef; }
QSplitter::handle { background: #d0d3d8; }
QLineEdit { background: #ffffff; border: 1px solid #d0d3d8; border-radius: 8px; padding: 6px 10px; }
"""

# Собственная "фирменная" тема HackicLab — тёмная с бирюзово-фиолетовыми акцентами
CUSTOM_QSS = """
QWidget { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background-color: #0f172a; }
#sidebar { background-color: #0b1120; border-right: 1px solid #1e293b; }
#sidebar QLabel#logo { color: #22d3ee; font-size: 22px; font-weight: 800; padding: 16px 12px 4px 12px; }
#sidebar QLabel#sub { color: #64748b; font-size: 11px; padding: 0 12px 12px 12px; }
#navList { background: transparent; border: none; outline: none; }
#navList::item { padding: 12px 16px; margin: 2px 8px; border-radius: 8px; color: #94a3b8; }
#navList::item:hover { background: #1e293b; color: #e2e8f0; }
#navList::item:selected { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #8b5cf6); color: white; font-weight: 600; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #8b5cf6); color: white; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #22d3ee, stop:1 #a78bfa); }
QPushButton:disabled { background: #334155; color: #64748b; }
QPushButton#ghost { background: transparent; border: 1px solid #334155; color: #e2e8f0; }
QPushButton#ghost:hover { background: #1e293b; }
#card { background: #0b1120; border: 1px solid #1e293b; border-radius: 12px; padding: 14px; }
QLabel#h1 { font-size: 20px; font-weight: 700; color: #e2e8f0; }
QLabel#h2 { font-size: 14px; font-weight: 600; color: #94a3b8; }
QLabel#val { font-size: 13px; color: #f1f5f9; }
QLabel#muted { color: #64748b; font-size: 12px; }
QLabel#kv { color: #64748b; font-size: 12px; }
QGroupBox { border: 1px solid #1e293b; border-radius: 10px; margin-top: 14px; padding: 12px 10px; color: #94a3b8; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar { background: #1e293b; border: none; border-radius: 6px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #8b5cf6); border-radius: 6px; }
QTextEdit, QPlainTextEdit { background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; color: #e2e8f0; font-family: 'Cascadia Code','Consolas'; font-size: 12px; }
QListWidget { background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; }
QListWidget::item { padding: 8px; }
QListWidget#issueList::item { border-bottom: 1px solid #1a2537; padding: 6px; }
QComboBox { background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #0b1120; selection-background-color: #8b5cf6; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 2px solid #334155; background: #0b1120; }
QCheckBox::indicator:checked { background: #06b6d4; border-color: #06b6d4; }
QSplitter::handle { background: #1e293b; }
QLineEdit { background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 6px 10px; }
"""

THEMES = {
    "dark": DARK_QSS,
    "light": LIGHT_QSS,
    "system": DARK_QSS,      # временно: системная = тёмная, пока не подключим Qt system palette
    "custom": CUSTOM_QSS,
}


def get_qss(theme: str) -> str:
    return THEMES.get(theme, DARK_QSS)
