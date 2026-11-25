"""Centralized PySide6 theme tokens and QSS stylesheet."""

COLOR_PRIMARY = "#1F6AA5"
COLOR_PRIMARY_HOVER = "#267EC2"
COLOR_ACCENT_BLUE = "#4DA3E8"

COLOR_SUCCESS = "#2FA572"
COLOR_SUCCESS_HOVER = "#24875C"

COLOR_DANGER = "#A52F2F"
COLOR_DANGER_HOVER = "#852222"

COLOR_WARNING = "#FFB300"
COLOR_ERROR_TEXT = "#E54D42"

PATTERN_META: dict[str, tuple[str, str]] = {
    "DJ": ("Dense Jack", "#1F6AA5"),
    "CJ": ("Chordjack", "#8E44AD"),
    "SJ": ("Speedjack", "#D35400"),
    "ANCHOR": ("Anchor", "#27AE60"),
}

APP_QSS = """
QMainWindow, QDialog {
    background-color: #141619;
    color: #EAECEF;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QLabel {
    color: #EAECEF;
}

QFrame#PanelCard {
    background-color: #1C1F24;
    border: 1px solid #2B303A;
    border-radius: 10px;
}

QFrame#MapCard {
    background-color: #242830;
    border: 1px solid #303642;
    border-radius: 8px;
}

QFrame#MapCard:hover {
    border: 1px solid #4A5568;
}

QLineEdit, QComboBox {
    background-color: #141619;
    color: #EAECEF;
    border: 1px solid #343A46;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3B8ED0;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QListWidget {
    background-color: #141619;
    color: #EAECEF;
    border: 1px solid #343A46;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
}

QListWidget::item:hover, QListWidget::item:selected {
    background-color: #243447;
    color: #FFFFFF;
}

QPushButton {
    background-color: #2B303A;
    color: #EAECEF;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #373E4B;
}

QPushButton:disabled {
    background-color: #22252C;
    color: #6B7280;
}

QPushButton#PrimaryBtn {
    background-color: #1F6AA5;
    color: #FFFFFF;
}

QPushButton#PrimaryBtn:hover {
    background-color: #267EC2;
}

QPushButton#SuccessBtn {
    background-color: #2FA572;
    color: #FFFFFF;
}

QPushButton#SuccessBtn:hover {
    background-color: #24875C;
}

QPushButton#DangerBtn {
    background-color: #A52F2F;
    color: #FFFFFF;
}

QPushButton#DangerBtn:hover {
    background-color: #852222;
}

QPushButton#SegmentedBtn {
    background-color: #252932;
    color: #B8C0CC;
    border: 1px solid #323846;
    padding: 6px 8px;
}

QPushButton#SegmentedBtn:checked {
    background-color: #1F6AA5;
    color: #FFFFFF;
    border: 1px solid #3B8ED0;
}

QPushButton#IconBtn {
    background-color: transparent;
    color: #9CA3AF;
    padding: 2px 6px;
    border-radius: 4px;
}

QPushButton#IconBtn:hover {
    background-color: #343A46;
    color: #FFFFFF;
}

QPushButton#IconDangerBtn {
    background-color: transparent;
    color: #9CA3AF;
    padding: 2px 6px;
    border-radius: 4px;
}

QPushButton#IconDangerBtn:hover {
    background-color: #A52F2F;
    color: #FFFFFF;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #141619;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #3A414E;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QProgressBar {
    background-color: #1C1F24;
    border: 1px solid #2B303A;
    border-radius: 6px;
    text-align: center;
    color: #EAECEF;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #2FA572;
    border-radius: 5px;
}
"""
