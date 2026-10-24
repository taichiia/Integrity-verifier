import os
import sys
import subprocess
import shutil
import tempfile
from contextlib import contextmanager


ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(ROOT, "output")
SHARED_DIR = os.path.join(ROOT, "shared")
VERIFIER_DIR = os.path.join(ROOT, "verifier")
HOOKS_DIR = os.path.join(ROOT, "build_hooks")
EXCLUDED_QT_MODULES = ["PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtPdf", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtSvg", "PySide6.QtVirtualKeyboard"]
EXCLUDED_PYINSTALLER_HOOK_MODULES = [
    "PyInstaller.hooks",
]
CLI_EXCLUDED_MODULES = [
    "PySide6",
    "shiboken6",
    "PyInstaller",
    "PyInstaller.hooks",
]

EMBEDDED_DATA = os.path.join(VERIFIER_DIR, "_embedded_data.py")
FIT_REC_EXE = os.path.join(ROOT, "target", "release", "fit-rec.exe")
RUST_ARTIFACTS = {
    "Rust Builder": (
        os.path.join(ROOT, "target", "release", "fit-builder.exe"),
        "FileIntegrityBuilderRust.exe",
    ),
    "Rust Verifier": (
        os.path.join(ROOT, "target", "release", "fit-verifier.exe"),
        "FileIntegrityVerifierRust.exe",
    ),
    "Rust Record CLI": (FIT_REC_EXE, "fit-rec.exe"),
}


@contextmanager
def without_embedded_data():
    """Keep project-specific checksums out of generic release builds.

    ``verifier/_embedded_data.py`` is generated when the Builder packs a
    project verifier.  It contains the user's file list, so a release build of
    the generic verifier (or of the Builder) must never bundle it.
    """
    stash = None
    if os.path.isfile(EMBEDDED_DATA):
        stash = EMBEDDED_DATA + ".build-stash"
        shutil.move(EMBEDDED_DATA, stash)
        print("  NOTE: project-specific embedded data excluded from this build")
    try:
        yield
    finally:
        if stash and os.path.isfile(stash):
            shutil.move(stash, EMBEDDED_DATA)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def build_exe(
    entry_point: str,
    name: str,
    icon_path: str = "",
    extra_args: list[str] | None = None,
    include_shared: bool = True,
    console: bool = False,
):
    with tempfile.TemporaryDirectory(prefix="fit_build_") as build_tmp:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--console" if console else "--noconsole",
            "--clean",
            "--name", name,
            "--distpath", OUTPUT,
            "--workpath", os.path.join(build_tmp, "build"),
            "--specpath", os.path.join(build_tmp, "spec"),
            entry_point,
        ]

        if icon_path and os.path.isfile(icon_path):
            cmd.insert(4, f"--icon={icon_path}")

        if include_shared and os.path.isdir(SHARED_DIR):
            cmd.insert(4, f"--add-data={SHARED_DIR}{os.pathsep}shared")

        if extra_args:
            cmd[4:4] = extra_args

        for module in EXCLUDED_QT_MODULES:
            cmd[4:4] = [f"--exclude-module={module}"]

        for module in EXCLUDED_PYINSTALLER_HOOK_MODULES:
            cmd[4:4] = [f"--exclude-module={module}"]

        if extra_args and "--collect-all=PyInstaller" in extra_args:
            cmd[4:4] = ["--exclude-module=PyInstaller.hooks"]

        cmd[4:4] = [f"--additional-hooks-dir={HOOKS_DIR}"]

        print(f"  Building {name}...")
        print(f"  Command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, cwd=ROOT,
            capture_output=True, text=True,
        )

    if result.returncode != 0:
        print(f"  ERROR: PyInstaller failed for {name} (code {result.returncode})")
        tail = result.stderr or result.stdout or ""
        print(tail[-3000:])
        return None

    exe_path = os.path.join(OUTPUT, f"{name}.exe")
    if os.path.isfile(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"  SUCCESS: {exe_path}  ({size_mb:.1f} MB)")
        return exe_path

    print(f"  WARNING: Build completed but EXE not found at {exe_path}")
    return None


def build_builder():
    print("\n" + "=" * 60)
    print("打包: 文件完整性验证工具 — 开发者端 (Builder)")
    print("=" * 60)

    entry = os.path.join(ROOT, "builder", "main.py")
    icon = os.path.join(ROOT, "builder", "resources", "icon.ico")

    if not build_fit_cli():
        return None

    # Pack the verifier source and PyInstaller so the frozen Builder can rebuild
    # project-specific verifier executables without an installed Python runtime.
    extra_args = [
        f"--add-binary={FIT_REC_EXE}{os.pathsep}fitrec",
        f"--add-data={VERIFIER_DIR}{os.pathsep}verifier",
        f"--add-data={HOOKS_DIR}{os.pathsep}build_hooks",
        "--collect-data=PyInstaller",
        "--collect-data=_pyinstaller_hooks_contrib",
        "--copy-metadata=PyInstaller",
    ]

    with without_embedded_data():
        return build_exe(entry, "FileIntegrityBuilder", icon, extra_args)


def build_fit_cli() -> bool:
    print("  Building fit-rec bridge...")
    result = subprocess.run(
        ["cargo", "build", "--release", "-p", "fit-cli"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("  ERROR: cargo build failed for fit-rec")
        print((result.stderr or result.stdout)[-3000:])
        return False
    if not os.path.isfile(FIT_REC_EXE):
        print(f"  ERROR: fit-rec output not found: {FIT_REC_EXE}")
        return False
    return True


def build_rust():
    print("\n" + "=" * 60)
    print("打包: Rust Builder / Verifier / fit-rec")
    print("=" * 60)

    verifier_result = subprocess.run(
        ["cargo", "build", "--release", "-p", "fit-verifier", "-p", "fit-cli"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if verifier_result.returncode != 0:
        print("  ERROR: cargo build failed")
        print((verifier_result.stderr or verifier_result.stdout)[-3000:])
        return {}

    builder_result = subprocess.run(
        ["cargo", "build", "--release", "-p", "fit-builder"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if builder_result.returncode != 0:
        print("  ERROR: builder build failed")
        print((builder_result.stderr or builder_result.stdout)[-3000:])
        return {}

    ensure_dir(OUTPUT)
    results = {}
    for label, (source, output_name) in RUST_ARTIFACTS.items():
        if not os.path.isfile(source):
            print(f"  ERROR: Rust output not found: {source}")
            continue
        destination = os.path.join(OUTPUT, output_name)
        shutil.copy2(source, destination)
        size_mb = os.path.getsize(destination) / (1024 * 1024)
        print(f"  SUCCESS: {destination}  ({size_mb:.1f} MB)")
        results[label] = destination
    return results


def build_verifier():
    print("\n" + "=" * 60)
    print("打包: 文件完整性验证器 — 客户端 (Verifier)")
    print("=" * 60)

    entry = os.path.join(ROOT, "verifier", "main.py")
    icon = os.path.join(ROOT, "verifier", "resources", "icon.ico")

    with without_embedded_data():
        return build_exe(entry, "FileIntegrityVerifier", icon, include_shared=False)


def build_cli_verifier():
    print("\n" + "=" * 60)
    print("打包: 文件完整性验证器 — CLI-only 客户端")
    print("=" * 60)

    entry = os.path.join(ROOT, "verifier", "cli.py")
    extra_args = [
        f"--exclude-module={module}"
        for module in CLI_EXCLUDED_MODULES
    ]

    with without_embedded_data():
        return build_exe(
            entry,
            "FileIntegrityVerifierCLI",
            extra_args=extra_args,
            include_shared=False,
            console=True,
        )


def main():
    print("文件完整性验证工具 — 构建系统")
    print(f"根目录: {ROOT}")
    print(f"输出目录: {OUTPUT}")
    ensure_dir(OUTPUT)

    import argparse
    parser = argparse.ArgumentParser(description="打包文件完整性验证工具")
    parser.add_argument("--builder", action="store_true", help="仅打包 Builder（开发者端）")
    parser.add_argument("--verifier", action="store_true", help="仅打包 Verifier（客户端）")
    parser.add_argument("--verifier-cli", action="store_true", help="仅打包 CLI-only Verifier")
    parser.add_argument("--all", action="store_true", help="打包全部（默认）")
    parser.add_argument("--rust", action="store_true", help="仅打包 Rust Builder/Verifier/fit-rec")
    parser.add_argument("--rust-all", action="store_true", help="打包 Python 桌面应用和 Rust 套件")
    args = parser.parse_args()

    build_all = args.all or args.rust_all or (
        not args.builder
        and not args.verifier
        and not args.verifier_cli
        and not args.rust
    )
    build_rust_suite = args.rust or args.rust_all or args.all

    results = {}
    if build_all or args.builder:
        results["Builder"] = build_builder()
    if build_all or args.verifier:
        results["Verifier"] = build_verifier()
    if build_all or args.verifier_cli:
        results["Verifier CLI"] = build_cli_verifier()
    if build_rust_suite:
        results.update(build_rust())

    print("\n" + "=" * 60)
    print("构建汇总")
    print("=" * 60)
    for name, path in results.items():
        if path and os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  {name}: 成功 — {path} ({size_mb:.1f} MB)")
        else:
            print(f"  {name}: 失败")


if __name__ == "__main__":
    main()

