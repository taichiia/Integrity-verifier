# File Integrity Tool (FIT)

**文件完整性验证工具** — 生成签名/加密的校验文件，并打包为独立的客户端验证器。

A Windows desktop application for generating signed/encrypted file checksums and packaging them into standalone verifier executables.

## Features | 功能

- **Builder (开发者端)** — 递归扫描文件夹 / 过滤文件 / 多线程计算哈希 / 数字签名与 AES 加密 / 打包为独立 EXE
- **Verifier (客户端)** — 自校验 EXE / 自动定位目标路径 / 完整性验证 / 结果导出
- **Anti-tamper** — 加密自校验 + 签名验证 + 反调试/反沙箱检测

## Quick Start | 快速开始

```bash
# Install dependencies
pip install -r requirements.txt

# Run Builder (dev mode)
python builder/main.py

# Run Verifier (dev mode)
python verifier/main.py
```

## Build | 打包

```bash
# Build standalone EXEs
python build.py --all
```

Output: `output/FileIntegrityBuilder.exe` and `output/FileIntegrityVerifier.exe`

## Project Structure | 项目结构

```
val1/
├── builder/            # Builder app (PySide6 GUI)
│   └── ui/             #   widgets / workers / theme
├── verifier/           # Verifier app (PySide6 GUI)
├── shared/             # crypto, hashing, protection, project model
├── build.py            # PyInstaller build script
└── output/             # Built EXEs
```

## License | 许可

[AGPL-3.0](LICENSE)
