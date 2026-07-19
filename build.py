import os
import sys
import subprocess
import shutil


ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(ROOT, "output")
SHARED_DIR = os.path.join(ROOT, "shared")


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def build_exe(entry_point: str, name: str, icon_path: str = ""):
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--clean",
        "--name", name,
        "--distpath", OUTPUT,
        "--workpath", os.path.join(OUTPUT, ".build_temp"),
        "--specpath", os.path.join(OUTPUT, ".specs"),
        entry_point,
    ]

    if icon_path and os.path.isfile(icon_path):
        cmd.insert(4, f"--icon={icon_path}")

    if os.path.isdir(SHARED_DIR):
        cmd.insert(4, f"--add-data={SHARED_DIR}{os.pathsep}shared")

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

    return build_exe(entry, "FileIntegrityBuilder", icon)


def build_verifier():
    print("\n" + "=" * 60)
    print("打包: 文件完整性验证器 — 客户端 (Verifier)")
    print("=" * 60)

    entry = os.path.join(ROOT, "verifier", "main.py")
    icon = os.path.join(ROOT, "verifier", "resources", "icon.ico")

    return build_exe(entry, "FileIntegrityVerifier", icon)


def main():
    print("文件完整性验证工具 — 构建系统")
    print(f"根目录: {ROOT}")
    print(f"输出目录: {OUTPUT}")
    ensure_dir(OUTPUT)

    import argparse
    parser = argparse.ArgumentParser(description="打包文件完整性验证工具")
    parser.add_argument("--builder", action="store_true", help="仅打包 Builder（开发者端）")
    parser.add_argument("--verifier", action="store_true", help="仅打包 Verifier（客户端）")
    parser.add_argument("--all", action="store_true", help="打包全部（默认）")
    args = parser.parse_args()

    build_all = args.all or (not args.builder and not args.verifier)

    results = {}
    if build_all or args.builder:
        results["Builder"] = build_builder()
    if build_all or args.verifier:
        results["Verifier"] = build_verifier()

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

