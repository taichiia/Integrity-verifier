import re

from PyInstaller.utils.hooks.qt import add_qt6_dependencies


KEEP_TRANSLATIONS = {"qt_zh_cn.qm", "qtbase_zh_cn.qm"}
EXCLUDED_PLUGIN_PATTERNS = [
    r"plugins\\imageformats\\qgif\.dll$",
    r"plugins\\imageformats\\qico\.dll$",
    r"plugins\\imageformats\\qjpeg\.dll$",
    r"plugins\\imageformats\\qwbmp\.dll$",
    r"plugins\\generic\\qtuiotouchplugin\.dll$",
    r"plugins\\iconengines\\qsvgicon\.dll$",
    r"plugins\\imageformats\\qicns\.dll$",
    r"plugins\\imageformats\\qpdf\.dll$",
    r"plugins\\imageformats\\qsvg\.dll$",
    r"plugins\\imageformats\\qtga\.dll$",
    r"plugins\\imageformats\\qtiff\.dll$",
    r"plugins\\imageformats\\qwebp\.dll$",
    r"plugins\\platforminputcontexts\\.*\.dll$",
    r"plugins\\platforms\\qdirect2d\.dll$",
    r"plugins\\platforms\\qminimal\.dll$",
    r"plugins\\platforms\\qoffscreen\.dll$",
]

EXCLUDED_PLUGIN_REGEX = re.compile(
    "|".join(f"({pattern})" for pattern in EXCLUDED_PLUGIN_PATTERNS),
    re.IGNORECASE,
)


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [
    binary for binary in binaries
    if not EXCLUDED_PLUGIN_REGEX.search(binary[0].replace("/", "\\"))
]
datas = [
    (source, destination)
    for source, destination in datas
    if not source.lower().endswith(".qm")
    or source.lower().replace("\\", "/").rsplit("/", 1)[-1] in KEEP_TRANSLATIONS
]
