APP_STYLE = """
* { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QMainWindow, QWidget { background: #f1f5f9; color: #0f172a; }
QFrame#Sidebar { background: #0f172a; border: none; }
QLabel#AppTitle { color: #f8fafc; font-size: 17px; font-weight: 600; padding: 18px 16px 6px 16px; }
QLabel#SidebarHint { color: #94a3b8; font-size: 12px; padding: 0 16px 12px 16px; }
QListWidget#Nav { background: transparent; border: none; outline: none; padding: 6px; }
QListWidget#Nav::item { color: #cbd5e1; padding: 10px 12px; border-radius: 8px; margin: 2px 0; }
QListWidget#Nav::item:selected { background: #155e75; color: #ffffff; }
QListWidget#Nav::item:hover { background: #1e293b; }
QLabel#EngineState { color: #94a3b8; font-size: 12px; padding: 4px 16px; }
QFrame#Content { background: #f1f5f9; border: none; }
QWidget#Card, QFrame#Card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }
QWidget#CardPlain, QFrame#CardPlain { background: transparent; border: none; }
QLabel#PageTitle { font-size: 20px; font-weight: 600; color: #0f172a; }
QLabel#PageSub { color: #475569; }
QLabel#SectionTitle { font-weight: 600; color: #0f172a; }
QLabel#Muted { color: #64748b; }
QLabel#Warn { color: #b45309; }
QLabel#Err { color: #b91c1c; }
QLabel#Ok { color: #047857; }
QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 7px 14px; color: #0f172a; }
QPushButton:hover { background: #f8fafc; border-color: #94a3b8; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }
QPushButton#Primary { background: #0f766e; color: #ffffff; border: none; }
QPushButton#Primary:hover { background: #115e59; }
QPushButton#Primary:disabled { background: #99a6a5; color: #eef2f2; }
QPushButton#Danger { color: #b91c1c; }
QPushButton#Ghost { background: transparent; border: none; color: #0f766e; padding: 4px 8px; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 8px; selection-background-color: #99f6e4;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #0f766e; }
QComboBox::drop-down { border: none; width: 22px; }
QSlider::groove:horizontal { height: 6px; background: #e2e8f0; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #0f766e; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -5px 0; background: #ffffff; border: 2px solid #0f766e; border-radius: 9px; }
QSlider::groove:vertical { width: 6px; background: #e2e8f0; border-radius: 3px; }
QSlider::sub-page:vertical { background: #0f766e; border-radius: 3px; }
QSlider::handle:vertical { width: 16px; height: 16px; margin: 0 -5px; background: #ffffff; border: 2px solid #0f766e; border-radius: 9px; }
QProgressBar { background: #e2e8f0; border: none; border-radius: 6px; height: 12px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #0f766e; border-radius: 6px; }
QListWidget, QTableWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }
QListWidget::item { padding: 6px; border-bottom: 1px solid #f1f5f9; }
QListWidget::item:selected { background: #f0fdfa; color: #0f172a; }
QHeaderView::section { background: #f8fafc; border: none; border-bottom: 1px solid #e2e8f0; padding: 6px; font-weight: 600; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 5px; background: #ffffff; }
QCheckBox::indicator:checked { background: #0f766e; border-color: #0f766e; image: none; }
QStatusBar { background: #e2e8f0; color: #334155; }
QToolTip { background: #0f172a; color: #f8fafc; border: none; padding: 4px 8px; }
"""
