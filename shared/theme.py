from shared.constants import (
    RADIUS_TINY, RADIUS_CHIP, RADIUS_BUTTON, RADIUS_CONSENT,
    RADIUS_HERO,
    FONT_FAMILY, FONT_FAMILY_MONO,
    FONT_H1_SIZE, FONT_H2_SIZE, FONT_H3_SIZE,
    FONT_BODY_SIZE, FONT_EYEBROW_SIZE, FONT_BUTTON_SIZE, FONT_MONO_SIZE,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_2XL,
)


_ACCENT_LIGHT = "#0078D4"
_ACCENT_HOVER_LIGHT = "#429CE3"
_ACCENT_PRESSED_LIGHT = "#005A9E"
_ACCENT_TEXT_LIGHT = "#FFFFFF"
_SUCCESS_LIGHT = "#0F7B0F"
_WARNING_LIGHT = "#9D5D00"
_DANGER_LIGHT = "#C42B1C"

_ACCENT_DARK = "#4CC2FF"
_ACCENT_HOVER_DARK = "#62CDFF"
_ACCENT_PRESSED_DARK = "#0093F9"
_ACCENT_TEXT_DARK = "#000000"
_SUCCESS_DARK = "#6CCB5F"
_WARNING_DARK = "#FCE100"
_DANGER_DARK = "#FF99A4"

_LIGHT = {
    "accent": _ACCENT_LIGHT,
    "accent_hover": _ACCENT_HOVER_LIGHT,
    "accent_pressed": _ACCENT_PRESSED_LIGHT,
    "accent_text": _ACCENT_TEXT_LIGHT,
    "bg": "#F3F3F3",
    "surface": "#FFFFFF",
    "surface_alt": "#F9F9F9",
    "text": "#141414",
    "secondary": "rgba(0, 0, 0, 0.60)",
    "tertiary": "rgba(0, 0, 0, 0.45)",
    "disabled_text": "rgba(0, 0, 0, 0.36)",
    "border": "rgba(0, 0, 0, 0.08)",
    "divider": "rgba(0, 0, 0, 0.06)",
    "subtle": "rgba(0, 0, 0, 0.04)",
    "secondary_fill": "rgba(0, 0, 0, 0.06)",
    "disabled_bg": "rgba(0, 0, 0, 0.04)",
    "select_bg": "rgba(0, 120, 212, 0.12)",
    "nav": "rgba(255, 255, 255, 0.72)",
    "success": _SUCCESS_LIGHT,
    "warning": _WARNING_LIGHT,
    "danger": _DANGER_LIGHT,
    "success_bg": "rgba(15, 123, 15, 0.12)",
    "warning_bg": "rgba(157, 93, 0, 0.12)",
    "danger_bg": "rgba(196, 43, 28, 0.12)",
    "info_bg": "rgba(0, 120, 212, 0.12)",
}

_DARK = {
    "accent": _ACCENT_DARK,
    "accent_hover": _ACCENT_HOVER_DARK,
    "accent_pressed": _ACCENT_PRESSED_DARK,
    "accent_text": _ACCENT_TEXT_DARK,
    "bg": "#202020",
    "surface": "#2B2B2B",
    "surface_alt": "#252525",
    "text": "#FFFFFF",
    "secondary": "rgba(255, 255, 255, 0.79)",
    "tertiary": "rgba(255, 255, 255, 0.54)",
    "disabled_text": "rgba(255, 255, 255, 0.36)",
    "border": "rgba(255, 255, 255, 0.08)",
    "divider": "rgba(255, 255, 255, 0.07)",
    "subtle": "rgba(255, 255, 255, 0.06)",
    "secondary_fill": "rgba(255, 255, 255, 0.08)",
    "disabled_bg": "rgba(255, 255, 255, 0.04)",
    "select_bg": "rgba(76, 194, 255, 0.18)",
    "nav": "rgba(255, 255, 255, 0.08)",
    "success": _SUCCESS_DARK,
    "warning": _WARNING_DARK,
    "danger": _DANGER_DARK,
    "success_bg": "rgba(108, 203, 95, 0.16)",
    "warning_bg": "rgba(252, 225, 0, 0.14)",
    "danger_bg": "rgba(255, 153, 164, 0.16)",
    "info_bg": "rgba(76, 194, 255, 0.18)",
}

_current_mode = "light"


def set_theme_mode(mode: str) -> None:
    global _current_mode
    _current_mode = "dark" if mode == "dark" else "light"


def get_theme_mode() -> str:
    return _current_mode


def get_palette(mode: str | None = None) -> dict:
    return _DARK if (mode or _current_mode) == "dark" else _LIGHT


def generate_builder_stylesheet(mode: str | None = None) -> str:
    p = get_palette(mode)
    CANVAS_CREAM = p["bg"]
    WHITE = p["surface"]
    LIFTED_CREAM = p["surface"]
    INK_BLACK = p["text"]
    SLATE_GRAY = p["secondary"]
    DUST_TAUPE = p["border"]
    SOFT_BONE = p["disabled_bg"]
    SIGNAL_ORANGE = p["accent"]
    LIGHT_ORANGE = p["accent_hover"]
    CLAY_BROWN = p["accent_pressed"]
    LINK_BLUE = p["accent"]
    SUCCESS_GREEN = p["success"]
    ERROR_RED = p["danger"]
    WARNING_AMBER = p["warning"]
    INFO_BLUE = p["accent"]
    ACCENT_TEXT = p["accent_text"]

    return f"""
/* File Integrity Tool - Fluent 2 / Windows 11 */
QWidget {{
    background-color: {CANVAS_CREAM};
    color: {INK_BLACK};
    font-family: "{FONT_FAMILY}", "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 400;
}}

QMainWindow, QDialog, QFileDialog {{
    background-color: {CANVAS_CREAM};
}}

QMenuBar {{
    background-color: {CANVAS_CREAM};
    color: {INK_BLACK};
    padding: {SPACING_XS}px {SPACING_MD}px;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 500;
    border-bottom: 1px solid {DUST_TAUPE};
}}

QMenuBar::item {{
    padding: {SPACING_XS}px {SPACING_MD}px;
    border-radius: {RADIUS_CHIP}px;
}}

QMenuBar::item:selected {{
    background-color: {p["secondary_fill"]};
}}

QMenu {{
    background-color: {WHITE};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_CONSENT}px;
    padding: {SPACING_XS}px;
}}

QMenu::item {{
    padding: {SPACING_SM}px {SPACING_2XL}px;
    border-radius: {RADIUS_TINY}px;
}}

QMenu::item:selected {{
    background-color: {p["secondary_fill"]};
}}

QStatusBar {{
    background-color: {CANVAS_CREAM};
    color: {p["secondary"]};
    border-top: 1px solid {DUST_TAUPE};
    font-size: {FONT_EYEBROW_SIZE}px;
    padding: {SPACING_XS}px {SPACING_MD}px;
}}

QToolBar {{
    background-color: {CANVAS_CREAM};
    border-bottom: 1px solid {DUST_TAUPE};
    padding: {SPACING_XS}px {SPACING_MD}px;
    spacing: {SPACING_MD}px;
}}

QPushButton {{
    background-color: {SIGNAL_ORANGE};
    color: {ACCENT_TEXT};
    border: 1px solid transparent;
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_XS + 2}px {SPACING_LG}px;
    font-size: {FONT_BUTTON_SIZE}px;
    font-weight: 500;
    letter-spacing: 0;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {LIGHT_ORANGE};
}}

QPushButton:pressed {{
    background-color: {CLAY_BROWN};
}}

QPushButton:disabled {{
    background-color: {SOFT_BONE};
    color: {p["disabled_text"]};
    border-color: {p["divider"]};
}}

QPushButton:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

QPushButton[cssClass="secondary"] {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
}}

QPushButton[cssClass="secondary"]:hover {{
    background-color: {p["subtle"]};
    color: {INK_BLACK};
}}

QPushButton[cssClass="secondary"]:pressed {{
    background-color: {p["secondary_fill"]};
    color: {INK_BLACK};
}}

QPushButton[cssClass="secondary"]:disabled {{
    background-color: {SOFT_BONE};
    color: {p["disabled_text"]};
    border-color: {p["divider"]};
}}

QPushButton[cssClass="danger"] {{
    background-color: {p["danger"]};
    color: #FFFFFF;
    border: none;
}}

QPushButton[cssClass="danger"]:hover {{
    background-color: #D2463B;
}}

QPushButton[cssClass="danger"]:pressed {{
    background-color: #A52517;
}}

QPushButton[cssClass="icon-circle"] {{
    background-color: transparent;
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_BUTTON}px;
    min-width: 32px;
    min-height: 32px;
    padding: 0px;
    font-size: 14px;
}}

QPushButton[cssClass="icon-circle"]:hover {{
    background-color: {p["subtle"]};
}}

QLabel {{
    background-color: transparent;
    color: {INK_BLACK};
    font-weight: 400;
}}

QLabel[cssClass="h1"] {{
    font-size: {FONT_H1_SIZE}px;
    font-weight: 600;
    letter-spacing: 0;
    line-height: 1.2;
}}

QLabel[cssClass="h2"] {{
    font-size: {FONT_H2_SIZE}px;
    font-weight: 600;
    letter-spacing: 0;
    line-height: 1.25;
}}

QLabel[cssClass="h3"] {{
    font-size: {FONT_H3_SIZE}px;
    font-weight: 600;
    letter-spacing: 0;
    line-height: 1.25;
}}

QLabel[cssClass="eyebrow"] {{
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 500;
    letter-spacing: 0;
    text-transform: uppercase;
    color: {SLATE_GRAY};
}}

QLabel[cssClass="muted"], QLabel[cssClass="hint"] {{
    color: {SLATE_GRAY};
    font-weight: 400;
}}

QLabel[cssClass="hint"] {{
    font-size: {FONT_EYEBROW_SIZE}px;
}}

QLabel[cssClass="mono"] {{
    font-family: "{FONT_FAMILY_MONO}", Consolas, monospace;
    font-size: {FONT_MONO_SIZE}px;
    font-weight: 400;
}}

QLabel[cssClass="accent"] {{
    color: {SIGNAL_ORANGE};
    font-weight: 500;
}}

QLabel[cssClass="section-title"] {{
    color: {INK_BLACK};
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 600;
    letter-spacing: 0;
}}

QGroupBox {{
    background-color: {LIFTED_CREAM};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
    margin-top: {SPACING_2XL}px;
    padding: {SPACING_LG}px;
    padding-top: {SPACING_2XL}px;
    font-size: {FONT_H3_SIZE}px;
    font-weight: 500;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: {SPACING_XS}px {SPACING_MD}px;
    color: {INK_BLACK};
}}

QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 400;
    selection-background-color: {p["select_bg"]};
    selection-color: {INK_BLACK};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    background-color: {SOFT_BONE};
    color: {p["disabled_text"]};
}}

QComboBox {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    padding-right: {SPACING_XL}px;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 400;
    min-height: 28px;
}}

QComboBox:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

QComboBox:disabled {{
    background-color: {SOFT_BONE};
    color: {p["disabled_text"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {WHITE};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_CONSENT}px;
    padding: {SPACING_XS}px;
    selection-background-color: {p["select_bg"]};
    selection-color: {INK_BLACK};
    outline: none;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_BODY_SIZE}px;
    min-height: 28px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

QCheckBox, QRadioButton {{
    background-color: transparent;
    color: {INK_BLACK};
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 400;
    spacing: {SPACING_SM}px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {INK_BLACK};
    border-radius: {RADIUS_TINY}px;
    background-color: {WHITE};
}}

QCheckBox::indicator:checked {{
    background-color: {SIGNAL_ORANGE};
    border-color: {SIGNAL_ORANGE};
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {INK_BLACK};
    border-radius: 50%;
    background-color: {WHITE};
}}

QRadioButton::indicator:checked {{
    background-color: {SIGNAL_ORANGE};
    border-color: {SIGNAL_ORANGE};
}}

QTableView {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
    gridline-color: {p["divider"]};
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 400;
    selection-background-color: {p["select_bg"]};
    selection-color: {INK_BLACK};
    outline: none;
}}

QTableView:focus {{
    border: 2px solid {p["accent"]};
}}

QTableView::item {{
    padding: {SPACING_SM}px {SPACING_MD}px;
    border-bottom: 1px solid {p["divider"]};
}}

QTableView::item:selected {{
    background-color: {p["select_bg"]};
    color: {INK_BLACK};
}}

QTableView::item:focus {{
    border: 2px solid {p["accent"]};
}}

QHeaderView::section {{
    background-color: {p["surface_alt"]};
    color: {SLATE_GRAY};
    font-weight: 500;
    font-size: {FONT_EYEBROW_SIZE}px;
    text-transform: uppercase;
    letter-spacing: 0;
    padding: {SPACING_SM}px {SPACING_MD}px;
    border: none;
    border-bottom: 1px solid {DUST_TAUPE};
}}

QHeaderView::section:hover {{
    background-color: {p["secondary_fill"]};
}}

QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {DUST_TAUPE};
    border-radius: 4px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {SLATE_GRAY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {DUST_TAUPE};
    border-radius: 4px;
    min-width: 40px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QProgressBar {{
    background-color: {p["secondary_fill"]};
    border: none;
    border-radius: {RADIUS_BUTTON}px;
    text-align: center;
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 500;
    color: {INK_BLACK};
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {SIGNAL_ORANGE};
    border-radius: {RADIUS_BUTTON}px;
}}

QSplitter::handle {{
    background-color: {DUST_TAUPE};
    width: 1px;
}}

QSplitter::handle:hover {{
    background-color: {SLATE_GRAY};
}}

QTabWidget::pane {{
    background-color: {LIFTED_CREAM};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
    padding: {SPACING_MD}px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {SLATE_GRAY};
    padding: {SPACING_SM}px {SPACING_MD}px;
    margin-right: {SPACING_XS}px;
    font-size: {FONT_BUTTON_SIZE}px;
    font-weight: 500;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {SIGNAL_ORANGE};
    border-bottom: 2px solid {SIGNAL_ORANGE};
}}

QTabBar::tab:hover {{
    color: {INK_BLACK};
}}

QToolTip {{
    background-color: #FFFFFF;
    color: #141414;
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_CHIP}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 400;
}}

QPlainTextEdit[cssClass="log"] {{
    font-family: "{FONT_FAMILY_MONO}", Consolas, monospace;
    font-size: {FONT_MONO_SIZE}px;
    font-weight: 400;
    background-color: {WHITE};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
    padding: 8px;
}}

QFrame[cssClass="panel"] {{
    background-color: {WHITE};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
}}

QFrame[cssClass="sep"] {{
    color: {DUST_TAUPE};
    background-color: {DUST_TAUPE};
    max-height: 1px;
    border: none;
}}

QLabel[cssClass="stat-ok"], QLabel[cssClass="stat-err"],
QLabel[cssClass="stat-warn"], QLabel[cssClass="stat-info"] {{
    font-weight: 400;
    font-size: {FONT_BODY_SIZE}px;
    padding: {SPACING_XS}px {SPACING_SM}px;
    border-radius: {RADIUS_CHIP}px;
}}

QLabel[cssClass="stat-ok"] {{
    color: {SUCCESS_GREEN};
    background-color: {p["success_bg"]};
}}

QLabel[cssClass="stat-err"] {{
    color: {ERROR_RED};
    background-color: {p["danger_bg"]};
}}

QLabel[cssClass="stat-warn"] {{
    color: {WARNING_AMBER};
    background-color: {p["warning_bg"]};
}}

QLabel[cssClass="stat-info"] {{
    color: {INFO_BLUE};
    background-color: {p["info_bg"]};
}}

QFrame[cssClass="bottom-nav"] {{
    background-color: {p["nav"]};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_CONSENT}px;
}}

QPushButton[cssClass="nav-item"] {{
    background-color: transparent;
    color: {p["secondary"]};
    border: none;
    border-top: 3px solid transparent;
    border-radius: 0px;
    padding: 0px {SPACING_MD}px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0;
    min-width: 84px;
    min-height: 46px;
    max-height: 49px;
}}

QPushButton[cssClass="nav-item"]:hover {{
    background-color: {p["subtle"]};
    color: {INK_BLACK};
}}

QPushButton[cssClass="nav-item"]:focus {{
    border-top: 3px solid transparent;
    outline: 2px solid {LIGHT_ORANGE};
    outline-offset: 2px;
}}

QPushButton[cssClass="nav-item"][navState="selected"] {{
    background-color: {p["subtle"]};
    color: {SIGNAL_ORANGE};
    border-top: 3px solid {SIGNAL_ORANGE};
}}

QPushButton[cssClass="nav-item"][navState="selected"]:hover {{
    color: {SIGNAL_ORANGE};
}}

QPushButton[cssClass="nav-item"][navState="selected"]:focus {{
    border-top: 3px solid {SIGNAL_ORANGE};
}}
"""


def generate_verifier_stylesheet(mode: str | None = None) -> str:
    return generate_builder_stylesheet(mode)
