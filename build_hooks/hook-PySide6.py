import re

from PyInstaller.utils.hooks import check_requirement
from PyInstaller.utils.hooks.qt import pyside6_library_info, ensure_single_qt_bindings_package

ensure_single_qt_bindings_package("PySide6")

if pyside6_library_info.version is not None:
    hiddenimports = ['shiboken6', 'inspect']

    if check_requirement("PySide6 >= 6.4.0"):
        hiddenimports += ['PySide6.support.deprecated']

    excluded_qt_patterns = [
        r"qt6network\.dll$",
        r"qt6opengl\.dll$",
        r"qt6pdf\.dll$",
        r"qt6qml.*\.dll$",
        r"qt6quick.*\.dll$",
        r"qt6svg\.dll$",
        r"qt6virtualkeyboard\.dll$",
        r"opengl32sw\.dll$",
    ]

    excluded_plugin_patterns = [
        r"imageformats\\qgif\.dll$",
        r"imageformats\\qico\.dll$",
        r"imageformats\\qjpeg\.dll$",
        r"imageformats\\qwbmp\.dll$",
        r"generic\\qtuiotouchplugin\.dll$",
        r"iconengines\\qsvgicon\.dll$",
        r"imageformats\\qpdf\.dll$",
        r"imageformats\\qsvg\.dll$",
        r"imageformats\\qtga\.dll$",
        r"imageformats\\qtiff\.dll$",
        r"imageformats\\qwebp\.dll$",
        r"platforminputcontexts\\.*\.dll$",
        r"platforms\\qdirect2d\.dll$",
        r"platforms\\qminimal\.dll$",
        r"platforms\\qoffscreen\.dll$",
    ]

    excluded_patterns = excluded_qt_patterns + excluded_plugin_patterns
    excluded_regex = re.compile("|".join(f"({pattern})" for pattern in excluded_patterns), re.IGNORECASE)

    binaries = [
        binary for binary in pyside6_library_info.collect_extra_binaries()
        if not excluded_regex.search(binary[0].replace("/", "\\"))
    ]
