# FIT - 文件完整性工具

[中文](#中文) | [English](#english)

**FIT** 是一个 Windows 桌面工具集，用于证明文件没有被改动，并在有纠错数据时把损坏或缺失的文件恢复回来。它把签名清单、并行哈希、Reed-Solomon 纠错恢复整合在一个紧凑的 Rust/Tauri 应用中。

核心流程很简单：

```text
扫描 -> 哈希 -> 签名 -> 分发验证器 -> 验证或恢复
```

它适合发布目录、证据包、科研数据、备份抽查，以及任何需要回答“文件是否变过？如果变过，能否恢复？”的场景。

<a id="中文"></a>
## 中文

### 为什么选择 FIT

| 能力 | 作用 |
| --- | --- |
| 签名完整性记录 | `.fitrec` 使用 Ed25519 签名，可检测修改、删除和多余文件。 |
| 文件恢复 | `.fitrec.parity` 为原始文件内容保存 Reed-Solomon 校验分片，而不只是保护清单。 |
| 整文件重建 | `crossFile` 模式可从同组仍存活的文件中重建完全缺失的目标文件。 |
| 紧凑分发 | Rust 发布版是独立 Windows EXE，GUI 不依赖 Node.js 运行时。 |
| 安全修复 | 恢复结果先写入独立目录，通过 SHA-256 校验后才会进入最终位置。 |
| Fluent 风格界面 | Builder 和 Verifier 都提供中文界面、暗色模式、悬停说明、取消操作和实时进度。 |

FIT 不是整盘备份工具；它只保护恢复档案中显式列出的文件。

### 主要功能

#### Builder

- 递归扫描目录树，支持扩展名、目录、大小范围、黑名单和包含规则。
- 扫描期间可选开启预哈希；正式哈希会复用缓存，减少重复读取。
- 并行计算 SHA-256、SHA-512、MD5，支持暂停、停止和逐文件进度。
- 在一个项目中维护多个命名校验清单。
- 导入/导出 CSV 和 SFV 校验文件。
- 使用 Ed25519 签名校验文件。
- 使用 PBKDF2-SHA256 与 AES-256-GCM 加密/解密校验文件。
- 生成签名的 `.fitrec`、公钥 `.fitrec.pub`，以及恢复档案 `.fitrec.parity`。
- 配置变化时实时估计恢复档案体积和可恢复文件百分比。
- 一键生成发布包：自动创建 `.fit-support`，自动生成并打包 `checksums.csv`，无需手动选择清单输出位置。
- 高级配置整合清单管理、校验记录、恢复档案和 Verifier 打包。
- 分发前可对目标目录执行模拟验证。
- 保存并重新打开 `.fitbuilder` 项目。
- 首次启动时提供可跳过的高亮教程，先说明软件用途，再解释记录、公钥、恢复档案、分片和恢复模式。

#### Verifier

- 使用 `.fitrec` 和 `.fitrec.pub` 验证目标目录。
- 启动时自动发现 Verifier 同级的 `.fit-support`，自动加载记录、公钥和恢复档案。
- 支持选择校验清单；一键发布后通常无需手动选择。
- 实时显示通过/失败/缺失/多余计数和详细结果表。
- 导出 JSON 和 CSV 验证报告。
- 从 `.fitrec.parity` 恢复损坏或缺失文件。
- 作为独立验证创作工具时，可生成新的 Ed25519 密钥对。

### 分发

运行以下命令构建 Rust 发布版：

```powershell
python build.py --rust
```

脚本会先构建 Verifier，再把它嵌入 Builder 发布版，最后复制到 `output/`：

| 产物 | 用途 |
| --- | --- |
| `FileIntegrityBuilderRust.exe` | 创作应用：扫描、哈希、签名、恢复和打包。 |
| `FileIntegrityVerifierRust.exe` | 接收方应用：验证和恢复。 |
| `fit-rec.exe` | 轻量命令行桥，用于记录和密钥操作。 |

GUI EXE 是单文件 Windows 应用，需要系统 WebView2 运行时。Windows 10/11 通常已经自带。

一键发布包的推荐结构如下：

```text
release/
  FileIntegrityVerifierRust.exe
  .fit-support/
    release.fitrec
    release.fitrec.pub
    release.fitrec.parity   # 只有需要恢复时才包含
    checksums.csv           # 一键发布时自动生成
```

Verifier 启动时会检查自己所在目录和当前工作目录下的 `.fit-support`；只要目录中只有一个 `.fitrec`，就会自动加载记录、公钥和可选恢复档案，并把默认验证根目录设为发布目录。

应发送哪些文件取决于接收方是否需要修复能力：

| 场景 | 发送 | 不要发送 |
| --- | --- | --- |
| 仅验证 | Verifier EXE、`.fit-support/release.fitrec`、`.fit-support/release.fitrec.pub` | 私钥 |
| 验证加恢复 | Verifier EXE、`.fit-support` 目录 | 私钥 |
| 继续创作 | `.fitbuilder`、源文件、私钥 | 永远不要把私钥交给接收方 |

Builder 可以直接生成前两种场景：点击“一键生成并打包”即可。CSV 清单固定写入 `.fit-support/checksums.csv`；高级配置仍允许手动选择已有清单和外部 Verifier EXE。如果没有选择外部 Verifier EXE，Builder 会写入内嵌的 Verifier 载荷。

典型的 `release.fitrec` 分发包如下：

```text
FileIntegrityVerifierRust.exe
release.fitrec
release.fitrec.pub
release.fitrec.parity   # 只有需要恢复时才包含
```

请把 `fitrec.key` 或其他 Ed25519 私钥保留在作者手中；接收方验证或恢复时不需要私钥。

### 恢复模型

FIT 恢复保护的是原始文件。Reed-Solomon 档案保存文件内容分片和签名元数据。恢复出的文件必须先通过与预期 SHA-256 的比对，才会发布到输出目录。

| 模式 | 最适合 | 体积特征 | 实际边界 |
| --- | --- | --- | --- |
| `singleFile` | 修复单个文件内部损坏 | 为每个文件追加校验分片 | 默认 16 数据分片 + 4 纠错分片时，每个 RS 块最多修复 4 个损坏分片；不能恢复完全缺失的文件。 |
| `crossFile` | 重建缺失或截断的文件 | 在 16 数据 + 4 纠错时通常约为源数据 25% | 文件被分入恢复组；每组最多丢失 4 条数据/纠错通道后仍可重建。 |
| `dual` | 同时处理文件内损坏和整个文件缺失 | 同时包含两种校验布局 | 档案最大；恢复时先尝试单文件修复，再退回跨文件重建。 |

默认模式是 `crossFile`：16 数据分片、4 纠错分片、1 MiB 分片。同组文件成为并行的数据通道；每个块从各通道取相同字节范围并生成校验分片。缺失通道可由存活数据通道和校验通道重建。

无法恢复的情况：

- 未列入恢复档案的文件。
- 超过配置纠错容量的损坏。
- 整个文件缺失时的 `singleFile` 档案，且数据分片数量超过纠错分片数量。
- 跨文件组丢失的通道数量超过纠错容量。
- `.fitrec.parity` 不存在，或其签名验证失败。

Verifier 永远不会直接覆盖用户原始文件；修复内容先写入选定输出目录的临时名称，最终 SHA-256 校验通过后才改名。

### 创作流程

1. 在 Builder 中选择源目录。
2. 扫描并调整过滤条件或文件选择。
3. 执行正式哈希。
4. 生成或选择 Ed25519 私钥。
5. 配置恢复模式、分片数量和分片大小。
6. 点击“生成记录和纠错档”。
7. 点击“一键生成并打包”，准备接收方分发包。

Builder 会显示生成的记录、公钥和恢复档案路径。公钥总是写在记录旁边。

### 命令行桥

`fit-rec.exe` 支持脚本化生成密钥和记录：

```powershell
# 生成 Ed25519 密钥对
.\fit-rec.exe keygen --private fitrec.key --public fitrec.pub

# 生成签名记录和源文件恢复档案
.\fit-rec.exe generate `
  --input document.json `
  --output release.fitrec `
  --private-key fitrec.key `
  --public-key release.fitrec.pub `
  --source-directory .\source `
  --data-shards 16 `
  --parity-shards 4 `
  --shard-size 1048576 `
  --recovery-mode cross
```

命令行桥适用于无法使用 Builder UI 自动化的场景；它使用与 GUI 相同的 Rust 核心和格式。

### 架构

```text
crates/
  core/       共享 Rust 引擎：扫描、哈希、清单、加密、恢复、验证。
  builder/    Fluent 风格 Builder GUI 外壳。
  verifier/   Fluent 风格 Verifier GUI 外壳。
  cli/        fit-rec 命令行桥。
builder/      旧版 Python/PySide6 Builder。
verifier/     旧版 Python/PySide6 Verifier。
shared/       旧版 Python 共享逻辑。
build.py      Rust/Tauri 和旧版 Python 发布构建入口。
```

核心设计是一个 Rust 引擎、两个桌面外壳。Builder 和 Verifier 不重复实现扫描、哈希、清单解析、签名或恢复逻辑。GUI 层是静态 HTML/CSS/JS，没有 Node 构建链，因此供应链更简单、发布体积更小。

关键实现包括：

- 使用 `walkdir` 按排序遍历目录，并应用可配置排除规则。
- 哈希和验证使用 Rayon 并行，并复用每线程读取缓冲区。
- 验证批量发送进度和实时通过/失败/缺失/多余计数。
- 预哈希从扫描列表尾部开始，正式哈希从列表头部开始，减少两者重叠等待。
- 跨文件和单文件校验分片生成均已并行化；分片主体预分配并按偏移直接写入。
- 恢复输出先写入临时文件，SHA-256 验证通过后才改名。

### 安全模型

- `.fitrec` 头部由 Ed25519 签名保护。
- `.fitrec.parity` v2 会签名文件索引，并为源内容保存 Reed-Solomon 校验分片。
- 公钥可以随记录分发；私钥必须保留在作者手中。
- 加密校验文件使用 PBKDF2-SHA256 派生密钥，并用 AES-256-GCM 认证。
- 发布构建不会嵌入上一个项目的清单或私钥。
- 内嵌 Verifier 载荷来自同一仓库构建，而不是从任意用户选择的文件加载。

项目文件适合继续创作，但不是分发产物。

### 开发

安装 Rust 工具链和 Tauri 2 Windows WebView2 依赖。

运行 GUI 开发版：

```powershell
cargo run -p fit-builder
cargo run -p fit-verifier
```

只构建 Rust 工作区：

```powershell
cargo build --release --workspace
```

旧版 Python 套件仍保留用于兼容：

```powershell
pip install -r requirements.txt
python builder/main.py
python verifier/main.py
python build.py --all
```

### 测试

运行完整验证：

```powershell
cargo fmt --all --check
cargo check --workspace
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
node --check crates/builder/ui/app.js
node --check crates/verifier/ui/app.js
python -m pytest tests -q
python build.py --rust
```

自动化测试覆盖：

- 扫描、过滤、路径安全和缺失根目录行为。
- 扫描期预哈希和缓存复用。
- 并行哈希、多算法、取消、暂停和进度。
- 验证计数器、排除规则和可取消进度。
- CSV/SFV 往返，包括引号路径和 Unicode 路径。
- Ed25519 签名、错误密钥拒绝和校验文件加密。
- `.fitrec` 往返和畸形记录拒绝。
- 单文件、跨文件、双模式恢复，包括整个文件缺失和超容量失败。
- Builder 项目保存/加载、打包和内嵌 Verifier 提取。
- `fit-rec` 密钥生成、记录生成和恢复档案生成。

### 性能快照

以下本地快照使用 Rust 核心流水线，数据集为 64 KiB 文件，OS 文件缓存处于热缓存状态。扫描速率表示元数据遍历；哈希和验证速率表示实际 SHA-256 内容处理。这些数字适合比较版本，不能作为跨硬件保证。

| 数据集 | 扫描 | 哈希 | 验证 | 结果 |
| ---: | ---: | ---: | ---: | --- |
| 1,000 文件 / 64 MiB | 2.7 ms（约 370k 文件/s） | 28.1 ms（约 35.6k 文件/s，约 2.3 GiB/s） | 21.3 ms（约 46.9k 文件/s，约 3.0 GiB/s） | 1,000 通过 / 0 失败 |
| 5,000 文件 / 320 MiB | 15.5 ms（约 323k 文件/s） | 105.9 ms（约 47.2k 文件/s，约 3.0 GiB/s） | 125.4 ms（约 39.9k 文件/s，约 2.6 GiB/s） | 5,000 通过 / 0 失败 |

在这个热缓存测试中，5,000 个小文件的哈希约 0.1 秒完成；包含目标发现、哈希、缺失文件检测和多余文件检测的完整验证约 0.125 秒完成。冷机械盘、网络共享、杀毒拦截或很大的顺序文件通常会被存储吞吐限制，而不是被 CPU 侧速率限制。

最近的优化包括复用读取缓冲区、减少中间集合、共享十六进制编码、批量进度回调、排除目录剪枝、虚拟化表格和直接偏移写入校验档案。

### 隐私

- 用户文件列表、项目、密钥、记录、报告和测试产物只保存在用户选择的位置。
- Git 已排除常见用户数据和生成产物，例如 `.fitbuilder`、`.fitrec`、`.fitrec.parity`、`.key`、`.pub`、`.sig`、`.enc`。
- 公开文档只保留在本 README；本地进度说明和生成报告不属于仓库。
- 发布前不要添加真实业务清单、私钥、加密载荷或机器相关的测试目录。

<a id="english"></a>
## English

**FIT** is a Windows desktop toolkit for proving that files have not changed, and for putting damaged or missing files back when recovery data is available. It combines signed manifests, parallel hashing, and Reed-Solomon recovery in a compact Rust/Tauri application.

The workflow is deliberately simple:

```text
scan -> hash -> sign -> distribute verifier -> verify or repair
```

FIT is built for release folders, evidence packages, research data, backup spot checks, and any situation where a recipient needs to answer two questions: *did this change?* and, if it did, *can we put it back?*

### Why FIT

| Capability | What it gives you |
| --- | --- |
| Signed integrity records | Ed25519-signed `.fitrec` manifests detect modification, deletion, and extra files. |
| File recovery | `.fitrec.parity` contains Reed-Solomon parity for the original files, not just the manifest. |
| Whole-file reconstruction | Cross-file mode can rebuild a completely missing target file from surviving files in its recovery group. |
| Compact distribution | Rust release binaries are standalone Windows EXEs; the GUI does not require a Node.js runtime. |
| Safe repair output | Recovery writes to a separate directory and validates hashes before replacing reconstructed files. |
| Fluent-style GUI | Both Builder and Verifier provide Chinese UI, dark mode, tooltips, cancellation, and live progress. |

FIT is not a whole-disk backup tool. It protects files explicitly listed in a recovery record.

### Core Features

#### Builder

- Recursively scans directory trees with extension, folder, size-range, blacklist, and inclusion filters.
- Optionally pre-hashes during scanning; unchanged files reuse cached hashes during the formal pass.
- Computes SHA-256, SHA-512, and MD5 in parallel, with pause, stop, and per-file progress.
- Maintains multiple named checklists inside a project.
- Imports and exports CSV and SFV checksum files.
- Signs checksum files with Ed25519.
- Encrypts and decrypts checksum files with PBKDF2-SHA256 and AES-256-GCM.
- Generates signed `.fitrec`, public key `.fitrec.pub`, and recovery archive `.fitrec.parity`.
- Estimates recovery archive size and recoverable-file percentage while settings change.
- Creates a one-click release package: it automatically creates `.fit-support`, generates `checksums.csv`, and packages the manifest without asking the user to choose a manifest output path.
- Advanced settings consolidate checklist management, record generation, recovery configuration, and Verifier packaging.
- Simulates verification against a target directory before distribution.
- Saves and reopens `.fitbuilder` projects.
- Shows a skippable first-launch guided tour that explains the tool's purpose, record artifacts, recovery, and shard concepts, with a top-bar button to replay it.

#### Verifier

- Verifies a target directory against `.fitrec` and `.fitrec.pub`.
- Automatically discovers `.fit-support` beside the Verifier and loads the record, public key, and recovery archive.
- Supports checklist selection; this is usually unnecessary after a one-click release.
- Shows live passed/failed/missing/extra counters and a detailed result table.
- Exports JSON and CSV verification reports.
- Recovers damaged or missing files from `.fitrec.parity` into a separate output directory.
- Generates new Ed25519 key pairs when used as a standalone verification-authoring tool.

### Distribution

Build the Rust release with:

```powershell
python build.py --rust
```

The script builds the Verifier first, embeds it into the Builder release, then copies artifacts to `output/`:

| Artifact | Purpose |
| --- | --- |
| `FileIntegrityBuilderRust.exe` | Authoring application: scan, hash, sign, recovery, and packaging. |
| `FileIntegrityVerifierRust.exe` | Recipient application: verification and recovery. |
| `fit-rec.exe` | Lightweight command-line bridge for record/key operations. |

The GUI EXEs are single-file Windows applications and require the system WebView2 runtime. Modern Windows 10/11 installations normally include it.

The recommended one-click release layout is:

```text
release/
  FileIntegrityVerifierRust.exe
  .fit-support/
    release.fitrec
    release.fitrec.pub
    release.fitrec.parity   # included only when repair is required
    checksums.csv           # generated automatically by one-click release
```

At startup, Verifier checks `.fit-support` beside its executable and in the current working directory. When that folder contains one `.fitrec`, it loads the record, public key, and optional recovery archive automatically, and defaults its verification root to the release directory.

The exact distribution set depends on whether the recipient only verifies data or also needs repair capability:

| Scenario | Send | Do not send |
| --- | --- | --- |
| Verification only | Verifier EXE, `.fit-support/release.fitrec`, `.fit-support/release.fitrec.pub` | Private key |
| Verification plus repair | Verifier EXE, `.fit-support` directory | Private key |
| Continued authoring | `.fitbuilder`, source files, private key | Never distribute the private key |

Builder creates the first two scenarios directly. Click **Create and Package Release**; the CSV manifest is written to `.fit-support/checksums.csv`. Advanced settings still allow selecting an existing manifest and an external Verifier EXE. If no external Verifier EXE is selected, Builder writes its embedded Verifier payload into the package.

For a typical `release.fitrec`, the package looks like:

```text
FileIntegrityVerifierRust.exe
release.fitrec
release.fitrec.pub
release.fitrec.parity   # include only if repair is required
```

Keep `fitrec.key` or another Ed25519 private key with the author. A recipient never needs it to verify or recover.

### Recovery Model

FIT recovery protects the original files. The Reed-Solomon archive stores file content shards and signed metadata. Recovery always validates reconstructed content against expected SHA-256 hashes before publishing a file.

| Mode | Best for | Size profile | Practical boundary |
| --- | --- | --- | --- |
| `singleFile` | Repairing corruption inside individual files | Adds parity for each file | With default 16 data + 4 parity, it repairs up to four damaged shards per RS block, but cannot restore a completely deleted file. |
| `crossFile` | Rebuilding missing or truncated files | Usually about 25% of source data at 16 data + 4 parity | Files are grouped into lanes. A group can lose up to four data/parity lanes and still rebuild. |
| `dual` | Both random in-file damage and complete file loss | Adds both parity layouts | Largest archive; recovery tries single-file repair first, then falls back to cross-file reconstruction. |

The default is `crossFile` with 16 data shards, 4 parity shards, and 1 MiB shards. In this mode, files in the same group become parallel data lanes; a block takes the same byte range from every lane and produces parity shards. A missing lane can be rebuilt from the surviving lanes and parity.

What cannot be recovered:

- Files not listed in the recovery archive.
- Damage beyond the configured parity capacity.
- A single-file archive whose data shard count exceeds its parity shard count when the whole file is missing.
- A cross-file group that has lost more lanes than its parity capacity.
- Data when `.fitrec.parity` itself is absent or fails signature verification.

Verifier never writes repaired data over the original user files. Repairs are written to a chosen output directory, first under a temporary name and only renamed after final hash validation.

### Authoring Workflow

1. Select the source directory in Builder.
2. Scan and adjust filters or file selection.
3. Run the hash pass.
4. Generate or select an Ed25519 private key.
5. Configure recovery mode, shard count, and shard size.
6. Click **Generate Record and Recovery Archive**.
7. Use **Create and Package Release** to prepare the recipient package.

Builder displays the generated record, public key, and parity paths. The public key is always written beside the record.

### Command-Line Bridge

`fit-rec.exe` provides scriptable key and record generation:

```powershell
# Generate an Ed25519 key pair
.\fit-rec.exe keygen --private fitrec.key --public fitrec.pub

# Generate a signed record and source-file recovery archive
.\fit-rec.exe generate `
  --input document.json `
  --output release.fitrec `
  --private-key fitrec.key `
  --public-key release.fitrec.pub `
  --source-directory .\source `
  --data-shards 16 `
  --parity-shards 4 `
  --shard-size 1048576 `
  --recovery-mode cross
```

The command-line bridge is useful when Builder UI automation is not available, but it uses the same Rust core and formats.

### Architecture

```text
crates/
  core/       Shared Rust engine: scanning, hashing, manifests, crypto, recovery, verification.
  builder/    Fluent-style Builder GUI shell.
  verifier/   Fluent-style Verifier GUI shell.
  cli/        fit-rec command-line bridge.
builder/      Legacy Python/PySide6 Builder.
verifier/     Legacy Python/PySide6 Verifier.
shared/       Legacy Python shared logic.
build.py      Build entry point for Rust/Tauri and legacy Python releases.
```

The main design is one Rust engine with two desktop shells. Builder and Verifier do not duplicate scanning, hashing, manifest parsing, signing, or recovery logic. The GUI layer is static HTML/CSS/JS with no Node build chain, which keeps the supply chain and release size small.

Important implementation details:

- File walking uses `walkdir` with sorted traversal and configurable exclusion rules.
- Hashing and verification use Rayon parallelism and reusable per-thread read buffers.
- Verification emits batched progress and live pass/fail/missing/extra counters.
- Background pre-hashing starts from the tail of the scanned list so formal hashing, which starts at the head, encounters less uncached work.
- Cross-file and single-file parity generation are parallelized; parity bodies are preallocated and written at direct offsets.
- Recovery output is staged in temporary files and renamed only after SHA-256 validation.

### Security Model

- `.fitrec` record headers are protected with Ed25519 signatures.
- `.fitrec.parity` v2 signs its file index and stores Reed-Solomon parity for source content.
- Public keys may be distributed with records; private keys must remain with the author.
- Encrypted checksum files derive keys with PBKDF2-SHA256 and authenticate with AES-256-GCM.
- Release builds do not embed a previous project's manifest or private key.
- The embedded Verifier payload is built from the same repository; it is not loaded from an arbitrary user-selected file.

Project files are convenient for continued authoring, but they are not distribution artifacts.

### Development

Install the Rust toolchain and Tauri 2 Windows WebView2 prerequisites.

Run the GUI shells in development:

```powershell
cargo run -p fit-builder
cargo run -p fit-verifier
```

Build only the Rust workspace:

```powershell
cargo build --release --workspace
```

The legacy Python suite remains available for compatibility:

```powershell
pip install -r requirements.txt
python builder/main.py
python verifier/main.py
python build.py --all
```

### Tests

Run the full validation set:

```powershell
cargo fmt --all --check
cargo check --workspace
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
node --check crates/builder/ui/app.js
node --check crates/verifier/ui/app.js
python -m pytest tests -q
python build.py --rust
```

The current automated suite covers:

- Scanning, filtering, path safety, and missing-root behavior.
- Scan-time pre-hashing and cache reuse.
- Parallel hashing, multiple algorithms, cancellation, pause, and progress.
- Verification counters, exclusions, and cancelable progress.
- CSV/SFV round trips, including quoted and Unicode paths.
- Ed25519 signing, wrong-key rejection, and checksum encryption.
- `.fitrec` round trips and malformed-record rejection.
- Single-file, cross-file, and dual-mode recovery, including whole missing files and over-capacity failure.
- Builder project save/load, packaging, and embedded Verifier extraction.
- `fit-rec` key generation, record generation, and recovery generation.

### Performance Snapshot

The following local snapshot used the Rust core pipeline with 64 KiB files and a warm OS/cache working set. Scan rates measure metadata traversal; hash and verify rates measure actual SHA-256 content processing. They are useful for comparing releases, not as a hardware-independent guarantee.

| Dataset | Scan | Hash | Verify | Result |
| ---: | ---: | ---: | ---: | --- |
| 1,000 files / 64 MiB | 2.7 ms (~370k files/s) | 28.1 ms (~35.6k files/s, ~2.3 GiB/s) | 21.3 ms (~46.9k files/s, ~3.0 GiB/s) | 1,000 passed / 0 failed |
| 5,000 files / 320 MiB | 15.5 ms (~323k files/s) | 105.9 ms (~47.2k files/s, ~3.0 GiB/s) | 125.4 ms (~39.9k files/s, ~2.6 GiB/s) | 5,000 passed / 0 failed |

In this warm-cache test, hashing 5,000 small files completed in about one tenth of a second, while verification including target discovery, hashing, missing-file detection, and extra-file detection completed in about one eighth of a second. Cold HDDs, network shares, antivirus interception, and very large sequential files will usually be limited by storage rather than these CPU-side rates.

Recent optimizations include reusable read buffers, fewer intermediate result collections, shared hexadecimal encoding, batched progress callbacks, excluded-directory pruning, virtualized tables, and direct parity writing.

### Privacy

- User file lists, projects, keys, records, reports, and test artifacts stay where the user chooses.
- Git excludes common user data and generated artifacts such as `.fitbuilder`, `.fitrec`, `.fitrec.parity`, `.key`, `.pub`, `.sig`, and `.enc`.
- Public documentation is intentionally kept in this README; local progress notes and generated reports are not part of the repository.
- Before publishing, do not add real business manifests, private keys, encrypted payloads, or machine-specific test folders.

### Repository

<https://github.com/taichiia/Integrity-verifier>

### License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
