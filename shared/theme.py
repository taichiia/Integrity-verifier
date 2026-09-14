from shared.constants import (
    RADIUS_TINY, RADIUS_CHIP, RADIUS_BUTTON, RADIUS_CONSENT,
    RADIUS_HERO, RADIUS_PILL, RADIUS_FULL_PILL,
    FONT_FAMILY, FONT_FAMILY_MONO,
    FONT_H1_SIZE, FONT_H2_SIZE, FONT_H3_SIZE,
    FONT_BODY_SIZE, FONT_EYEBROW_SIZE, FONT_BUTTON_SIZE, FONT_MONO_SIZE,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_2XL,
)


_PRIMARY = "#1677FF"
_ACCENT_HOVER = "#4096FF"
_ACCENT_PRESSED = "#0958D9"
_SUCCESS = "#16A34A"
_WARNING = "#D97706"
_DANGER = "#DC2626"

_LIGHT = {
    "primary": _PRIMARY,
    "accent_hover": _ACCENT_HOVER,
    "accent_pressed": _ACCENT_PRESSED,
    "bg": "#F5F7FA",
    "surface": "#FFFFFF",
    "text": "#111827",
    "secondary": "#6B7280",
    "border": "#E5E7EB",
    "disabled_bg": "#F0F0F0",
    "select_bg": "#E6F4FF",
}

_DARK = {
    "primary": _PRIMARY,
    "accent_hover": _ACCENT_HOVER,
    "accent_pressed": _ACCENT_PRESSED,
    "bg": "#141414",
    "surface": "#1F1F1F",
    "text": "#E8E8E8",
    "secondary": "#A6A6A6",
    "border": "#333333",
    "disabled_bg": "#2A2A2A",
    "select_bg": "#15325B",
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
    SIGNAL_ORANGE = _PRIMARY
    LIGHT_ORANGE = _ACCENT_HOVER
    CLAY_BROWN = _ACCENT_PRESSED
    LINK_BLUE = _PRIMARY
    SUCCESS_GREEN = _SUCCESS
    ERROR_RED = _DANGER
    WARNING_AMBER = _WARNING
    INFO_BLUE = _PRIMARY

    return f"""
/* File Integrity Tool — Ant-inspired enterprise theme */

/* ── Global ─────────────────────────────────────────────────── */
QWidget {{
    background-color: {CANVAS_CREAM};
    color: {INK_BLACK};
    font-family: "{FONT_FAMILY}", "Segoe UI", Arial, sans-serif;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 400;
}}

QMainWindow {{
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

QMenuBar::item:selected {{
    background-color: {LIFTED_CREAM};
    border-radius: {RADIUS_CHIP}px;
}}

QMenu {{
    background-color: {WHITE};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_CHIP}px;
    padding: {SPACING_XS}px;
}}

QMenu::item {{
    padding: {SPACING_SM}px {SPACING_2XL}px;
    border-radius: {RADIUS_TINY}px;
}}

QMenu::item:selected {{
    background-color: {CANVAS_CREAM};
    color: {INK_BLACK};
}}

/* ── Status Bar ─────────────────────────────────────────────── */
QStatusBar {{
    background-color: {CANVAS_CREAM};
    color: {SLATE_GRAY};
    border-top: 1px solid {DUST_TAUPE};
    font-size: {FONT_EYEBROW_SIZE}px;
    padding: {SPACING_XS}px {SPACING_MD}px;
}}

/* ── Toolbar ────────────────────────────────────────────────── */
QToolBar {{
    background-color: {CANVAS_CREAM};
    border-bottom: 1px solid {DUST_TAUPE};
    padding: {SPACING_XS}px {SPACING_MD}px;
    spacing: {SPACING_MD}px;
}}

/* ── Push Buttons ───────────────────────────────────────────── */
QPushButton {{
    background-color: {SIGNAL_ORANGE};
    color: {WHITE};
    border: 1px solid {SIGNAL_ORANGE};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_XS + 2}px {SPACING_LG}px;
    font-size: {FONT_BUTTON_SIZE}px;
    font-weight: 500;
    letter-spacing: 0;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {LIGHT_ORANGE};
    border-color: {LIGHT_ORANGE};
}}

QPushButton:pressed {{
    background-color: {CLAY_BROWN};
    border-color: {CLAY_BROWN};
}}

QPushButton:disabled {{
    background-color: {SOFT_BONE};
    color: {SLATE_GRAY};
    border-color: {DUST_TAUPE};
}}

QPushButton:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

/* Secondary (outlined) button */
QPushButton[cssClass="secondary"] {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
}}

QPushButton[cssClass="secondary"]:hover {{
    color: {SIGNAL_ORANGE};
    border-color: {SIGNAL_ORANGE};
}}

QPushButton[cssClass="secondary"]:pressed {{
    color: {CLAY_BROWN};
    border-color: {CLAY_BROWN};
}}

QPushButton[cssClass="secondary"]:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

/* Signal/danger button (sparing use) */
QPushButton[cssClass="danger"] {{
    background-color: {SIGNAL_ORANGE};
    color: {WHITE};
    border: none;
}}

/* Small icon button (circular) */
QPushButton[cssClass="icon-circle"] {{
    background-color: transparent;
    color: {INK_BLACK};
    border: 1px solid {INK_BLACK};
    border-radius: 50%;
    min-width: 40px;
    min-height: 40px;
    max-width: 40px;
    max-height: 40px;
    padding: 0px;
    font-size: 18px;
}}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {{
    background-color: transparent;
    color: {INK_BLACK};
    font-weight: 450;
}}

QLabel[cssClass="h1"] {{
    font-size: {FONT_H1_SIZE}px;
    font-weight: 500;
    letter-spacing: -0.56px;
    line-height: 1.0;
}}

QLabel[cssClass="h2"] {{
    font-size: {FONT_H2_SIZE}px;
    font-weight: 500;
    letter-spacing: -0.44px;
    line-height: 1.2;
}}

QLabel[cssClass="h3"] {{
    font-size: {FONT_H3_SIZE}px;
    font-weight: 500;
    letter-spacing: -0.32px;
    line-height: 1.2;
}}

QLabel[cssClass="eyebrow"] {{
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 700;
    letter-spacing: 0.44px;
    text-transform: uppercase;
    color: {SLATE_GRAY};
}}

QLabel[cssClass="muted"] {{
    color: {SLATE_GRAY};
}}

QLabel[cssClass="mono"] {{
    font-family: "{FONT_FAMILY_MONO}", "JetBrains Mono", monospace;
    font-size: {FONT_MONO_SIZE}px;
    font-weight: 450;
}}

/* ── Group Box / Card ───────────────────────────────────────── */
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

/* ── Line Edit / Text Input ─────────────────────────────────── */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 450;
    selection-background-color: {LIGHT_ORANGE};
    selection-color: {WHITE};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {LIGHT_ORANGE};
}}

QLineEdit:disabled {{
    background-color: {SOFT_BONE};
    color: {DUST_TAUPE};
}}

QLineEdit[cssClass="pill"] {{
    border-radius: {RADIUS_FULL_PILL}px;
    padding: {SPACING_SM}px {SPACING_LG}px;
}}

/* ── Combo Box ──────────────────────────────────────────────── */
QComboBox {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    padding-right: {SPACING_XL}px;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 450;
    min-height: 28px;
}}

QComboBox:focus {{
    border: 2px solid {LIGHT_ORANGE};
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
    border-radius: {RADIUS_CHIP}px;
    padding: {SPACING_XS}px;
    selection-background-color: {CANVAS_CREAM};
    selection-color: {INK_BLACK};
    outline: none;
}}

/* ── Spin Box ───────────────────────────────────────────────── */
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
    border: 1.5px solid {INK_BLACK};
}}

/* ── Check Box & Radio Button ───────────────────────────────── */
QCheckBox, QRadioButton {{
    background-color: transparent;
    color: {INK_BLACK};
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 450;
    spacing: {SPACING_SM}px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1.5px solid {INK_BLACK};
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
    border: 1.5px solid {INK_BLACK};
    border-radius: 50%;
    background-color: {WHITE};
}}

QRadioButton::indicator:checked {{
    background-color: {SIGNAL_ORANGE};
    border-color: {SIGNAL_ORANGE};
}}

/* ── Table View ─────────────────────────────────────────────── */
QTableView {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
    gridline-color: {CANVAS_CREAM};
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 450;
    selection-background-color: {CANVAS_CREAM};
    selection-color: {INK_BLACK};
    outline: none;
}}

QTableView::item {{
    padding: {SPACING_SM}px {SPACING_MD}px;
    border-bottom: 1px solid {CANVAS_CREAM};
}}

QTableView::item:selected {{
    background-color: {LIGHT_ORANGE};
    color: {INK_BLACK};
}}

QHeaderView::section {{
    background-color: {CANVAS_CREAM};
    color: {INK_BLACK};
    font-weight: 500;
    font-size: {FONT_EYEBROW_SIZE}px;
    text-transform: uppercase;
    letter-spacing: 0.44px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    border: none;
    border-bottom: 1px solid {DUST_TAUPE};
}}

QHeaderView::section:hover {{
    background-color: {DUST_TAUPE};
}}

/* ── Scroll Bar ─────────────────────────────────────────────── */
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

/* ── Progress Bar ───────────────────────────────────────────── */
QProgressBar {{
    background-color: {CANVAS_CREAM};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_PILL}px;
    text-align: center;
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 500;
    color: {INK_BLACK};
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {SIGNAL_ORANGE};
    border-radius: {RADIUS_PILL}px;
}}

/* ── Splitter ───────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {DUST_TAUPE};
    width: 1px;
}}

QSplitter::handle:hover {{
    background-color: {SLATE_GRAY};
}}

/* ── Tab Widget ─────────────────────────────────────────────── */
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

/* ── Tool Tip ───────────────────────────────────────────────── */
QToolTip {{
    background-color: {INK_BLACK};
    color: {CANVAS_CREAM};
    border: none;
    border-radius: {RADIUS_CHIP}px;
    padding: {SPACING_SM}px {SPACING_MD}px;
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 450;
}}

/* ── Dialog ─────────────────────────────────────────────────── */
QDialog {{
    background-color: {CANVAS_CREAM};
}}

/* ── File Dialog ────────────────────────────────────────────── */
QFileDialog {{
    background-color: {CANVAS_CREAM};
}}

/* ── Reusable component classes ─────────────────────────────── */
QPlainTextEdit[cssClass="log"] {{
    font-family: "{FONT_FAMILY_MONO}", "JetBrains Mono", monospace;
    font-size: {FONT_MONO_SIZE}px;
    font-weight: 450;
    background-color: {WHITE};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
    padding: 8px;
}}

QFrame[cssClass="panel"] {{
    background-color: {LIFTED_CREAM};
    border: 1px solid {DUST_TAUPE};
    border-radius: {RADIUS_HERO}px;
}}

QLabel[cssClass="hint"] {{
    color: {SLATE_GRAY};
    font-size: {FONT_EYEBROW_SIZE}px;
    font-weight: 400;
}}

QLabel[cssClass="accent"] {{
    color: {SIGNAL_ORANGE};
    font-weight: 500;
}}

QLabel[cssClass="section-title"] {{
    color: {INK_BLACK};
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 700;
    letter-spacing: 0;
}}

QLabel[cssClass="stat-ok"] {{ color: {SUCCESS_GREEN}; font-weight: 700; font-size: {FONT_BODY_SIZE}px; }}
QLabel[cssClass="stat-err"] {{ color: {ERROR_RED}; font-weight: 700; font-size: {FONT_BODY_SIZE}px; }}
QLabel[cssClass="stat-warn"] {{ color: {WARNING_AMBER}; font-weight: 700; font-size: {FONT_BODY_SIZE}px; }}
QLabel[cssClass="stat-info"] {{ color: {INFO_BLUE}; font-weight: 700; font-size: {FONT_BODY_SIZE}px; }}

QFrame[cssClass="sep"] {{
    color: {DUST_TAUPE};
    background-color: {DUST_TAUPE};
    max-height: 1px;
    border: none;
}}
"""


def generate_verifier_stylesheet(mode: str | None = None) -> str:
    return generate_builder_stylesheet(mode)

