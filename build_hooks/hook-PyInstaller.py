from PyInstaller.utils.hooks import collect_data_files


KEEP_SUFFIXES = (
    "rthooks.dat",
    "run.exe",
    "runw.exe",
    "README.rst",
)

datas = [
    data for data in collect_data_files("PyInstaller")
    if data[0].endswith(KEEP_SUFFIXES)
]
