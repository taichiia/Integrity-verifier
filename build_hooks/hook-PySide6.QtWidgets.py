from PyInstaller.utils.hooks.qt import add_qt6_dependencies


KEEP_TRANSLATIONS = {"qt_zh_cn.qm", "qtbase_zh_cn.qm"}


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
datas = [
    (source, destination)
    for source, destination in datas
    if not source.lower().endswith(".qm")
    or source.lower().replace("\\", "/").rsplit("/", 1)[-1] in KEEP_TRANSLATIONS
]
