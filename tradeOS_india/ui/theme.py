"""
TradeOS India — QSS dark/light theme loader.

Provides VS Code-inspired dark and light stylesheets for the entire app.
DARK_QSS is the default. Supports runtime theme switching via apply_theme().
"""

from PySide6.QtWidgets import QApplication

from utils.logger import get_logger

log = get_logger("ui.theme")

# ═════════════════════════════════════════════════════════════════
# Color constants
# ═════════════════════════════════════════════════════════════════

COLORS_DARK = {
    "bg_primary": "#1e1e1e",
    "bg_secondary": "#252526",
    "bg_tertiary": "#2d2d30",
    "bg_input": "#3c3c3c",
    "bg_hover": "#383838",
    "bg_titlebar": "#1a1d23",
    "bg_statusbar": "#007acc",
    "bg_statusbar_warn": "#d7ba7d",
    "bg_statusbar_error": "#f44747",
    "accent": "#007acc",
    "accent_hover": "#1a8ad4",
    "text_primary": "#cccccc",
    "text_secondary": "#858585",
    "text_bright": "#e0e0e0",
    "border": "#3e3e42",
    "success": "#4ec9b0",
    "warning": "#d7ba7d",
    "error": "#f44747",
    "tab_active_border": "#007acc",
    "sidebar_active": "#37373d",
    "scrollbar": "#424242",
    "scrollbar_hover": "#4f4f4f",
    "selection": "#264f78",
}

COLORS_LIGHT = {
    "bg_primary": "#ffffff",
    "bg_secondary": "#f3f3f3",
    "bg_tertiary": "#e8e8e8",
    "bg_input": "#ffffff",
    "bg_hover": "#e8e8e8",
    "bg_titlebar": "#dddddd",
    "bg_statusbar": "#007acc",
    "bg_statusbar_warn": "#d7ba7d",
    "bg_statusbar_error": "#f44747",
    "accent": "#007acc",
    "accent_hover": "#0065a9",
    "text_primary": "#333333",
    "text_secondary": "#717171",
    "text_bright": "#1e1e1e",
    "border": "#cecece",
    "success": "#388a34",
    "warning": "#bf8803",
    "error": "#cd3131",
    "tab_active_border": "#007acc",
    "sidebar_active": "#e8e8e8",
    "scrollbar": "#c1c1c1",
    "scrollbar_hover": "#a8a8a8",
    "selection": "#add6ff",
}


def _build_qss(c: dict[str, str]) -> str:
    """Build the full QSS string from a color dict.

    Args:
        c: Color dictionary.

    Returns:
        Complete QSS stylesheet string.
    """
    return f"""
/* ═══════════════════════════════════════════════════════════════
   TradeOS India — VS Code Theme
   ═══════════════════════════════════════════════════════════════ */

/* ─── Global ──────────────────────────────────────────────── */
QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
}}

QMainWindow {{
    background-color: {c['bg_primary']};
}}

/* ─── Title Bar ───────────────────────────────────────────── */
#TitleBar {{
    background-color: {c['bg_titlebar']};
    min-height: 32px;
    max-height: 32px;
}}

#TitleBar QLabel {{
    color: {c['text_primary']};
    font-size: 12px;
    background: transparent;
}}

#TitleBar QPushButton {{
    background: transparent;
    border: none;
    color: {c['text_primary']};
    min-width: 46px;
    max-width: 46px;
    min-height: 32px;
    max-height: 32px;
    font-size: 10px;
}}

#TitleBar QPushButton:hover {{
    background-color: {c['bg_hover']};
}}

#TitleBar QPushButton#btn_close:hover {{
    background-color: {c['error']};
    color: #ffffff;
}}

/* ─── Menu Buttons (Title Bar) ────────────────────────────── */
#TitleBar .menu-btn {{
    background: transparent;
    border: none;
    color: {c['text_secondary']};
    padding: 0 10px;
    min-width: 0;
    max-width: 9999px;
    font-size: 12px;
}}

#TitleBar .menu-btn:hover {{
    color: {c['text_bright']};
    background-color: {c['bg_hover']};
}}

/* ─── Menus ───────────────────────────────────────────────── */
QMenu {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    padding: 4px 0;
    font-size: 12px;
}}

QMenu::item {{
    padding: 6px 30px 6px 20px;
    color: {c['text_primary']};
}}

QMenu::item:selected {{
    background-color: {c['accent']};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 4px 10px;
}}

QMenu::item:disabled {{
    color: {c['text_secondary']};
}}

/* ─── Activity Bar ────────────────────────────────────────── */
#ActivityBar {{
    background-color: {c['bg_secondary']};
    min-width: 48px;
    max-width: 48px;
    border-right: 1px solid {c['border']};
}}

#ActivityBar QPushButton {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    min-height: 48px;
    max-height: 48px;
    min-width: 48px;
    max-width: 48px;
    color: {c['text_secondary']};
    font-size: 18px;
}}

#ActivityBar QPushButton:hover {{
    color: {c['text_bright']};
}}

#ActivityBar QPushButton:checked,
#ActivityBar QPushButton[active="true"] {{
    border-left: 2px solid {c['accent']};
    background-color: {c['sidebar_active']};
    color: {c['text_bright']};
}}

/* ─── Sidebar ─────────────────────────────────────────────── */
#Sidebar {{
    background-color: {c['bg_secondary']};
    border-right: 1px solid {c['border']};
}}

#Sidebar QLabel#SidebarHeader {{
    color: {c['text_secondary']};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 10px 14px 6px;
    letter-spacing: 0.5px;
    background: transparent;
}}

/* ─── Tab Bar ─────────────────────────────────────────────── */
#TabBar {{
    background-color: {c['bg_tertiary']};
    min-height: 35px;
    max-height: 35px;
}}

#TabBar QPushButton {{
    background: transparent;
    border: none;
    border-top: 2px solid transparent;
    color: {c['text_secondary']};
    padding: 0 16px;
    min-height: 35px;
    max-height: 35px;
    font-size: 12px;
}}

#TabBar QPushButton:hover {{
    color: {c['text_primary']};
}}

#TabBar QPushButton:checked,
#TabBar QPushButton[active="true"] {{
    color: {c['text_bright']};
    border-top: 2px solid {c['tab_active_border']};
    background-color: {c['bg_primary']};
}}

/* ─── Editor / Content Area ───────────────────────────────── */
#EditorArea {{
    background-color: {c['bg_primary']};
}}

/* ─── Bottom Panel ────────────────────────────────────────── */
#BottomPanel {{
    background-color: {c['bg_primary']};
    border-top: 1px solid {c['border']};
}}

#BottomPanel QTabWidget::pane {{
    border: none;
    background-color: {c['bg_primary']};
}}

#BottomPanel QTabBar::tab {{
    background: transparent;
    color: {c['text_secondary']};
    padding: 6px 14px;
    border: none;
    font-size: 11px;
    text-transform: uppercase;
}}

#BottomPanel QTabBar::tab:selected {{
    color: {c['text_bright']};
    border-bottom: 1px solid {c['accent']};
}}

/* ─── Status Bar ──────────────────────────────────────────── */
#StatusBar {{
    background-color: {c['bg_statusbar']};
    min-height: 22px;
    max-height: 22px;
    border: none;
}}

#StatusBar QLabel {{
    color: #ffffff;
    font-size: 11px;
    padding: 0 8px;
    background: transparent;
}}

#StatusBar[status="warning"] {{
    background-color: {c['bg_statusbar_warn']};
}}

#StatusBar[status="error"] {{
    background-color: {c['bg_statusbar_error']};
}}

/* ─── Scrollbars ──────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {c['scrollbar']};
    min-height: 30px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: {c['scrollbar_hover']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background: {c['scrollbar']};
    min-width: 30px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {c['scrollbar_hover']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ─── QPlainTextEdit ──────────────────────────────────────── */
QPlainTextEdit {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    border: none;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    selection-background-color: {c['selection']};
}}

/* ─── QLineEdit ───────────────────────────────────────────── */
QLineEdit {{
    background-color: {c['bg_input']};
    color: {c['text_bright']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 12px;
    selection-background-color: {c['selection']};
}}

QLineEdit:focus {{
    border-color: {c['accent']};
}}

/* ─── QPushButton (generic) ───────────────────────────────── */
QPushButton {{
    background-color: {c['accent']};
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {c['accent_hover']};
}}

QPushButton:pressed {{
    background-color: {c['accent']};
}}

QPushButton:disabled {{
    background-color: {c['bg_tertiary']};
    color: {c['text_secondary']};
}}

/* ─── QComboBox ───────────────────────────────────────────── */
QComboBox {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    selection-background-color: {c['accent']};
    selection-color: #ffffff;
}}

/* ─── QTableWidget ────────────────────────────────────────── */
QTableWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    border: none;
    gridline-color: {c['border']};
    font-size: 11px;
}}

QTableWidget::item {{
    padding: 4px 8px;
}}

QTableWidget::item:selected {{
    background-color: {c['selection']};
}}

QHeaderView::section {{
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 6px 8px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
}}

/* ─── QSplitter ───────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {c['border']};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ─── QTabWidget ──────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
}}

QTabBar::tab {{
    background: transparent;
    color: {c['text_secondary']};
    padding: 8px 16px;
    border: none;
    font-size: 12px;
}}

QTabBar::tab:selected {{
    color: {c['text_bright']};
    border-bottom: 2px solid {c['accent']};
}}

QTabBar::tab:hover {{
    color: {c['text_primary']};
}}

/* ─── QToolTip ────────────────────────────────────────────── */
QToolTip {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    padding: 4px 8px;
    font-size: 11px;
}}

/* ─── Settings Panel ──────────────────────────────────────── */
#SettingsPanel {{
    background-color: {c['bg_primary']};
}}

#SettingsPanel QLabel.section-header {{
    color: {c['text_secondary']};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 14px 0 6px;
    background: transparent;
}}

#SettingsPanel QLabel.setting-label {{
    color: {c['text_bright']};
    font-size: 12px;
    background: transparent;
}}

#SettingsPanel QLabel.setting-desc {{
    color: {c['text_secondary']};
    font-size: 11px;
    background: transparent;
}}

#SettingsPanel QFrame.setting-row {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 10px 14px;
}}

#SettingsPanel QFrame.setting-row:hover {{
    border-color: {c['accent']};
}}

/* ─── QCheckBox ───────────────────────────────────────────── */
QCheckBox {{
    color: {c['text_primary']};
    spacing: 8px;
    font-size: 12px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {c['text_secondary']};
    border-radius: 3px;
    background: transparent;
}}

QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}

/* ─── QSpinBox / QDoubleSpinBox ───────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_input']};
    color: {c['text_bright']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['accent']};
}}

/* ─── QGroupBox ───────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
    font-size: 11px;
    font-weight: 600;
    color: {c['text_secondary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    padding: 0 8px;
}}
"""


# ═════════════════════════════════════════════════════════════════
# Compiled stylesheets
# ═════════════════════════════════════════════════════════════════

DARK_QSS: str = _build_qss(COLORS_DARK)
LIGHT_QSS: str = _build_qss(COLORS_LIGHT)


def apply_theme(theme: str = "dark") -> None:
    """Apply a theme to the running QApplication.

    Args:
        theme: 'dark' or 'light'.
    """
    app = QApplication.instance()
    if not app:
        log.warning("No QApplication to apply theme")
        return

    qss = DARK_QSS if theme == "dark" else LIGHT_QSS
    app.setStyleSheet(qss)
    log.info(f"Theme applied: {theme}")


def get_color(name: str, theme: str = "dark") -> str:
    """Get a named color from the current theme palette.

    Args:
        name: Color key name.
        theme: 'dark' or 'light'.

    Returns:
        Hex color string.
    """
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT
    return colors.get(name, "#ffffff")


__all__ = [
    "DARK_QSS",
    "LIGHT_QSS",
    "COLORS_DARK",
    "COLORS_LIGHT",
    "apply_theme",
    "get_color",
]
