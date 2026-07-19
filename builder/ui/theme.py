from shared.constants import (
    CANVAS_CREAM, LIFTED_CREAM, INK_BLACK, WHITE,
    SIGNAL_ORANGE, LIGHT_ORANGE, SLATE_GRAY, DUST_TAUPE,
    LINK_BLUE, SOFT_BONE, CLAY_BROWN,
    SUCCESS_GREEN, ERROR_RED, WARNING_AMBER, INFO_BLUE,
    RADIUS_TINY, RADIUS_CHIP, RADIUS_BUTTON, RADIUS_CONSENT,
    RADIUS_HERO, RADIUS_PILL, RADIUS_FULL_PILL,
    FONT_FAMILY, FONT_FAMILY_MONO,
    FONT_H1_SIZE, FONT_H2_SIZE, FONT_H3_SIZE,
    FONT_BODY_SIZE, FONT_EYEBROW_SIZE, FONT_BUTTON_SIZE, FONT_MONO_SIZE,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL, SPACING_2XL,
)


def generate_builder_stylesheet() -> str:
    return f"""
/* ═══════════════════════════════════════════════════════════════
   File Integrity Tool — Builder Theme
   ═══════════════════════════════════════════════════════════════ */

/* ── Global ─────────────────────────────────────────────────── */
QWidget {{
    background-color: {CANVAS_CREAM};
    color: {INK_BLACK};
    font-family: "{FONT_FAMILY}", "Sofia Sans", "Segoe UI", Arial, sans-serif;
    font-size: {FONT_BODY_SIZE}px;
    font-weight: 450;
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
    box-shadow: 0px 24px 48px rgba(0,0,0,0.08);
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
    background-color: {INK_BLACK};
    color: {CANVAS_CREAM};
    border: 1.5px solid {INK_BLACK};
    border-radius: {RADIUS_BUTTON}px;
    padding: {SPACING_SM}px {SPACING_LG}px;
    font-size: {FONT_BUTTON_SIZE}px;
    font-weight: 500;
    letter-spacing: -0.32px;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {WHITE};
    border-color: {SLATE_GRAY};
}}

QPushButton:pressed {{
    background-color: {INK_BLACK};
    border-color: {INK_BLACK};
    padding-top: {SPACING_SM + 1}px;
    padding-bottom: {SPACING_SM - 1}px;
}}

QPushButton:disabled {{
    background-color: {DUST_TAUPE};
    color: {SLATE_GRAY};
    border-color: {DUST_TAUPE};
}}

/* Secondary (outlined) button */
QPushButton[cssClass="secondary"] {{
    background-color: {WHITE};
    color: {INK_BLACK};
    border: 1.5px solid {INK_BLACK};
}}

QPushButton[cssClass="secondary"]:hover {{
    background-color: {CANVAS_CREAM};
}}

QPushButton[cssClass="secondary"]:pressed {{
    background-color: {CANVAS_CREAM};
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
    border: 1.5px solid {INK_BLACK};
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
    border: 1.5px solid {INK_BLACK};
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
    background-color: {INK_BLACK};
    border-color: {INK_BLACK};
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1.5px solid {INK_BLACK};
    border-radius: 50%;
    background-color: {WHITE};
}}

QRadioButton::indicator:checked {{
    background-color: {INK_BLACK};
    border-color: {INK_BLACK};
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
    background-color: {CANVAS_CREAM};
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
    background-color: {INK_BLACK};
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
    color: {INK_BLACK};
    border-bottom: 2px solid {INK_BLACK};
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
"""


def generate_verifier_stylesheet() -> str:
    return generate_builder_stylesheet()

