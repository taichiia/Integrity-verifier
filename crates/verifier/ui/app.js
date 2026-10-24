const { invoke } = window.__TAURI__.core;
const targetPath = document.querySelector("#targetPath");
const recordPath = document.querySelector("#recordPath");
const publicKeyPath = document.querySelector("#publicKeyPath");
const checklistName = document.querySelector("#checklistName");
const startButton = document.querySelector("#start");
const stopButton = document.querySelector("#stop");
const exportButton = document.querySelector("#export");
const themeToggle = document.querySelector("#themeToggle");
const progressBar = document.querySelector("#progressBar");
const verifyStatus = document.querySelector("#verifyStatus");
const recoveryPath = document.querySelector("#recoveryPath");
const recoveryTargetPath = document.querySelector("#recoveryTargetPath");
const recoveryOutputPath = document.querySelector("#recoveryOutputPath");
const recoveryProgressBar = document.querySelector("#recoveryProgressBar");
const recoveryStatus = document.querySelector("#recoveryStatus");
const recoveryResultsBody = document.querySelector("#recoveryResults");
const sourceStatus = document.querySelector("#sourceStatus");
const resultsBody = document.querySelector("#results");
let currentReport = null;
let progressFrame = 0;
let recoveryProgressFrame = 0;

function renderInitialStates() {
  const verifyRow = document.createElement("tr");
  const verifyCell = document.createElement("td");
  verifyCell.colSpan = 4;
  verifyCell.className = "status-message";
  verifyCell.textContent = "尚无验证结果";
  verifyRow.append(verifyCell);
  resultsBody.replaceChildren(verifyRow);

  const recoveryRow = document.createElement("tr");
  const recoveryCell = document.createElement("td");
  recoveryCell.colSpan = 3;
  recoveryCell.className = "status-message";
  recoveryCell.textContent = "选择恢复档案后查看文件状态";
  recoveryRow.append(recoveryCell);
  recoveryResultsBody.replaceChildren(recoveryRow);
}

document.body.dataset.theme = localStorage.getItem("fit-verifier-theme") || "light";
renderInitialStates();

(async () => {
  try {
    const bundle = await invoke("discover_record_bundle");
    if (!bundle) return;
    recordPath.value = bundle.recordPath;
    publicKeyPath.value = bundle.publicKeyPath;
    targetPath.value = bundle.rootPath;
    if (bundle.recoveryPath) {
      recoveryPath.value = bundle.recoveryPath;
      recoveryTargetPath.value = bundle.rootPath;
      document.querySelector("#inspectRecovery").click();
    }
    sourceStatus.textContent = "已自动加载 .fit-support 记录；目标目录默认 Verifier 所在目录";
    document.querySelector("#inspectRecord").click();
  } catch (error) {
    sourceStatus.textContent = String(error);
  }
})();

themeToggle.addEventListener("click", () => {
  const next = document.body.dataset.theme === "dark" ? "light" : "dark";
  document.body.dataset.theme = next;
  localStorage.setItem("fit-verifier-theme", next);
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-current", item === button ? "page" : "false");
    });
    document.querySelectorAll(".page").forEach((page) => {
      page.classList.toggle("hidden", page.id !== button.dataset.panel);
      page.classList.toggle("active", page.id === button.dataset.panel);
    });
  });
});

document.querySelector("#browseTarget").addEventListener("click", async () => {
  const selected = await invoke("pick_directory");
  if (selected) targetPath.value = selected;
});

document.querySelector("#browseRecord").addEventListener("click", async () => {
  const selected = await invoke("pick_file");
  if (selected) recordPath.value = selected;
});

document.querySelector("#browsePublicKey").addEventListener("click", async () => {
  const selected = await invoke("pick_file");
  if (selected) publicKeyPath.value = selected;
});

document.querySelector("#browseRecovery").addEventListener("click", async () => {
  const selected = await invoke("pick_file");
  if (selected) recoveryPath.value = selected;
});

document.querySelector("#browseRecoveryTarget").addEventListener("click", async () => {
  const selected = await invoke("pick_directory");
  if (selected) recoveryTargetPath.value = selected;
});

document.querySelector("#browseRecoveryOutput").addEventListener("click", async () => {
  const selected = await invoke("pick_directory");
  if (selected) recoveryOutputPath.value = selected;
});

document.querySelector("#makeKey").addEventListener("click", async () => {
  const privateKey = await invoke("pick_save_file", {
    name: "verifier.key",
    extensions: ["key"],
  });
  if (!privateKey) return;
  try {
    await invoke("generate_keypair_command", {
      args: {
        privateKeyPath: privateKey,
        publicKeyPath: `${privateKey}.pub`,
      },
    });
    publicKeyPath.value = `${privateKey}.pub`;
    sourceStatus.textContent = "已生成 Ed25519 密钥对";
  } catch (error) {
    sourceStatus.textContent = String(error);
  }
});

document.querySelector("#inspectRecord").addEventListener("click", async () => {
  if (!recordPath.value || !publicKeyPath.value) {
    sourceStatus.textContent = "请先选择校验记录和公钥";
    return;
  }
  try {
    const info = await invoke("inspect_fitrec", {
      recordPath: recordPath.value,
      publicKeyPath: publicKeyPath.value,
    });
    checklistName.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent =
      info.checklists.find((item) => item.active)?.name || "默认清单";
    checklistName.append(empty);
    for (const item of info.checklists) {
      const option = document.createElement("option");
      option.value = item.name;
      option.textContent = `${item.name} (${item.count})`;
      option.selected = item.active;
      checklistName.append(option);
    }
    checklistName.disabled = false;
    sourceStatus.textContent = `已读取 ${info.checklists.length} 套清单；纠错容量 ${info.parityShards}/${info.dataShards + info.parityShards} 分片`;
  } catch (error) {
    sourceStatus.textContent = String(error);
    renderError(String(error));
  }
});

document.querySelector("#inspectRecovery").addEventListener("click", async () => {
  if (!recoveryPath.value || !publicKeyPath.value) {
    recoveryStatus.textContent = "请先选择恢复档案和公钥";
    return;
  }
  try {
    const info = await invoke("inspect_file_recovery", {
      recoveryPath: recoveryPath.value,
      publicKeyPath: publicKeyPath.value,
    });
    const mode = info.mode === "dual"
      ? "单文件 + 跨文件"
      : info.mode === "singleFile"
        ? "单文件"
        : "跨文件整文件";
    recoveryStatus.textContent = `档案有效：${info.fileCount} 个文件，${formatSize(info.totalSize)}；${mode}，纠错容量 ${info.parityShards}/${info.dataShards + info.parityShards} 分片`;
  } catch (error) {
    recoveryStatus.textContent = String(error);
  }
});

const startRecoveryButton = document.querySelector("#startRecovery");
const stopRecoveryButton = document.querySelector("#stopRecovery");

startRecoveryButton.addEventListener("click", async () => {
  startRecoveryButton.disabled = true;
  stopRecoveryButton.disabled = false;
  recoveryResultsBody.replaceChildren();
  setRecoveryProgress(0, "准备恢复...");
  try {
    const report = await invoke("recover_files", {
      args: {
        recoveryPath: recoveryPath.value,
        targetPath: recoveryTargetPath.value,
        outputPath: recoveryOutputPath.value,
        publicKeyPath: publicKeyPath.value,
      },
    });
    renderRecoveryReport(report);
    setRecoveryProgress(
      100,
      report.failed || report.missing
        ? `完成；缺失文件 ${report.missing} 个，失败 ${report.failed} 个`
        : "恢复完成",
    );
  } catch (error) {
    renderRecoveryError(String(error));
    setRecoveryProgress(0, "恢复失败");
  } finally {
    startRecoveryButton.disabled = false;
    stopRecoveryButton.disabled = true;
  }
});

stopRecoveryButton.addEventListener("click", () => {
  invoke("cancel_recovery");
});

startButton.addEventListener("click", async () => {
  startButton.disabled = true;
  stopButton.disabled = false;
  exportButton.disabled = true;
  currentReport = null;
  resultsBody.replaceChildren();
  setProgress(0, "准备中...");
  ["#passed", "#failed", "#missing", "#extra"].forEach((id) => {
    document.querySelector(id).textContent = "0";
  });
  try {
    const report = await invoke("verify_record", {
      args: {
        recordPath: recordPath.value,
        targetPath: targetPath.value,
        publicKeyPath: publicKeyPath.value,
        checklistName: checklistName.value,
      },
    });
    currentReport = report;
    exportButton.disabled = false;
    setProgress(100, report.cancelled ? "已取消" : "完成");
    renderReport(report);
  } catch (error) {
    renderError(String(error));
    setProgress(0, "错误");
  } finally {
    startButton.disabled = false;
    stopButton.disabled = true;
  }
});

stopButton.addEventListener("click", () => {
  invoke("cancel_verification");
});

document.querySelector("#openGitHub").addEventListener("click", async () => {
  const url = "https://github.com/taichiia/Integrity-verifier";
  try {
    await window.__TAURI__.opener.openUrl(url);
  } catch {
    window.open(url, "_blank", "noopener");
  }
});

exportButton.addEventListener("click", async () => {
  if (!currentReport) return;
  try {
    await invoke("save_report", { report: currentReport });
  } catch (error) {
    verifyStatus.textContent = String(error);
  }
});

window.__TAURI__.event.listen("verification-progress", (event) => {
  const payload = event.payload;
  if (progressFrame) return;
  progressFrame = requestAnimationFrame(() => {
    progressFrame = 0;
    setProgress(payload.total ? Math.round((payload.completed / payload.total) * 100) : 0,
      `已检查 ${payload.completed} / ${payload.total}`);
    document.querySelector("#passed").textContent = payload.passed || 0;
    document.querySelector("#failed").textContent = payload.failed || 0;
    document.querySelector("#missing").textContent = payload.missing || 0;
    document.querySelector("#extra").textContent = payload.extra || 0;
  });
});

window.__TAURI__.event.listen("recovery-progress", (event) => {
  const { completed, total, path } = event.payload;
  if (recoveryProgressFrame) return;
  recoveryProgressFrame = requestAnimationFrame(() => {
    recoveryProgressFrame = 0;
    setRecoveryProgress(total ? Math.round((completed / total) * 100) : 0, path);
  });
});

function setProgress(percent, text) {
  progressBar.style.width = `${percent}%`;
  verifyStatus.textContent = text;
}

function setRecoveryProgress(percent, text) {
  recoveryProgressBar.style.width = `${percent}%`;
  recoveryStatus.textContent = text;
}

function renderReport(report) {
  document.querySelector("#passed").textContent = report.passed;
  document.querySelector("#failed").textContent = report.failed;
  document.querySelector("#missing").textContent = report.missing;
  document.querySelector("#extra").textContent = report.extra_count;

  if (!report.details.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.className = "status-message";
    cell.textContent = "尚无验证结果";
    row.append(cell);
    resultsBody.replaceChildren(row);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const detail of report.details) {
    const row = document.createElement("tr");
    const status = document.createElement("td");
    status.className = `status-${detail.status}`;
    status.textContent = statusLabel(detail.status);
    const path = document.createElement("td");
    path.textContent = detail.path;
    const expected = document.createElement("td");
    expected.textContent = detail.expected;
    const actual = document.createElement("td");
    actual.textContent = detail.actual;
    row.append(status, path, expected, actual);
    fragment.append(row);
  }
  resultsBody.replaceChildren(fragment);
}

function renderError(message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 4;
  cell.className = "status-message";
  cell.textContent = message;
  resultsBody.append(row);
}

function renderRecoveryReport(report) {
  document.querySelector("#repaired").textContent = report.repaired;
  document.querySelector("#healthy").textContent = report.healthy;
  document.querySelector("#unrecoverable").textContent = report.missing;
  document.querySelector("#recoveryFailed").textContent = report.failed;
  document.querySelector("#recoveryTotal").textContent = report.total;

  if (!report.details.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.className = "status-message";
    cell.textContent = "档案中没有文件";
    row.append(cell);
    recoveryResultsBody.replaceChildren(row);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const detail of report.details) {
    const row = document.createElement("tr");
    const status = document.createElement("td");
    status.className = `status-${detail.status}`;
    status.textContent = recoveryStatusLabel(detail.status);
    const path = document.createElement("td");
    path.textContent = detail.path;
    const message = document.createElement("td");
    message.textContent = detail.message;
    row.append(status, path, message);
    fragment.append(row);
  }
  recoveryResultsBody.replaceChildren(fragment);
}

function renderRecoveryError(message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 3;
  cell.className = "status-message";
  cell.textContent = message;
  recoveryResultsBody.replaceChildren(row);
}

function statusLabel(status) {
  const labels = {
    pass: "通过",
    fail: "失败",
    missing: "缺失",
    extra: "多余",
    error: "错误",
  };
  return labels[status] ?? status;
}

function recoveryStatusLabel(status) {
  const labels = {
    healthy: "健康",
    repaired: "已修复",
    missing: "无法恢复",
    failed: "失败",
  };
  return labels[status] ?? status;
}

function formatSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`;
  return `${(size / 1024 ** 3).toFixed(2)} GB`;
}
