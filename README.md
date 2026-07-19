# 文件校驗分發工具 File Integrity Tool
**A builder that can directly produce a self-contained verifier with sha256 files self-included that verify everything with one click.**

**文件完整性验证工具** — 生成签名/加密的校验文件，并打包为独立的客户端验证器，双击即可一键验证所有内容。

A Windows desktop application for generating signed/encrypted file checksums and packaging them into standalone verifier executables.

## Features | 功能

**Builder (开发者端)**  
— 递归扫描文件夹 / 过滤文件 / 多线程计算哈希 / 数字签名与 AES 加密 / 打包为独立 EXE  
— 生成的验证器内嵌完整校验清单，无需额外分发哈希文件
-支持多方面自定义，如校验起始目录、校验清单等

**Verifier (客户端，由开发者端生成分发)**  
— 自校验 EXE / 自动定位目标路径 / 完整性验证 / 结果导出  
— 双击即可运行，无需命令行或专业知识

**Anti-tamper** — 加密自校验 + 签名验证 + 反调试/反沙箱检测


**Builder (Developer Side)**

— Recursively scan folders / filter files / multi-threaded hashing / digital signing & AES encryption / package into a standalone EXE

— The generated verifier embeds the full checksum manifest—no need to distribute separate hash files

— Supports extensive customization, such as verification start directory, checksum list, etc.

**Verifier (Client Side, generated and distributed by the developer)**

— Self-verifying EXE / automatically locates the target path / integrity verification / export results

— Double‑click to run—no command line or technical expertise required

**Anti‑tamper** — Encrypted self‑validation + signature verification + anti‑debugging / anti‑sandbox detection
## Highlights

- **零门槛验证** – 最终用户只需双击验证器，图形化界面直接显示“通过/失败”，无需命令行。  
- **自包含分发** – 校验数据内嵌于 EXE 中，开发者无需额外托管 `.sha256` 或 `.md5` 文件。   
- **职责分离** – Builder 与 Verifier 独立设计，开发者端可定制过滤与加密策略，客户端只负责傻瓜式验证。

- **Zero-threshold verification** – End users simply double-click the verifier, and the graphical interface directly displays "Pass/Fail," eliminating the need for command lines.

- **Self-contained distribution** – Verification data is embedded within the EXE file; developers do not need to separately manage `.sha256` or `.md5` files.

- **Separation of responsibilities** – The Builder and Verifier are designed independently. Developers can customize filtering and encryption strategies, while clients only handle simple verification.
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
