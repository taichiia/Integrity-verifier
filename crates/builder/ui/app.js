const { invoke } = window.__TAURI__.core;

const state = {
  project: {
    version: 1,
    base_directory: "",
    algorithm: "sha256",
    files: [],
    entries: [],
    checklists: { default: [] },
    active_checklist: "default",
    exclude_paths: [],
    exclude_rules: {},
    fitrec_private_key_path: "",
    data_shards: 16,
    parity_shards: 4,
    shard_size: 1024 * 1024,
    recovery_mode: "crossFile",
    project_name: "Untitled",
    checksum_output_path: "",
    checksum_format: "csv",
    private_key_path: "",
    signature_algorithm: "Ed25519",
    verifier_title: "File Integrity Verifier",
    verifier_icon_path: "",
    verifier_version: "1.0.0.0",
    verifier_company: "",
    verifier_copyright: "",
    verifier_path_rule: "current_dir",
    verifier_subfolder: "",
    verifier_custom_template: "",
    verifier_embed_encrypted: true,
    verifier_enable_signature_verify: true,
    verifier_enable_antidebug: false,
    verifier_enable_antisanbox: false,
  },
  files: [],
  included: new Set(),
  excluded: new Set(),
  entries: [],
  checklists: new Map([["default", []]]),
  activeChecklist: "default",
  paused: false,
  expandAllFiles: false,
};

const $ = (id) => document.querySelector(id);
const ROW_HEIGHT = 36;
const VIRTUAL_OVERSCAN = 10;
const virtualTables = new Map();
let scanProgressFrame = 0;
let hashProgressFrame = 0;
let verifyProgressFrame = 0;
let recordProgressFrame = 0;
let recoveryEstimateTimer = 0;

function setVirtualRows(id, columns, rows, renderRow) {
  virtualTables.set(id, { columns, rows, renderRow });
  $(id).replaceChildren();
  renderVirtualWindow(id);
}

function renderVirtualWindow(id) {
  const table = virtualTables.get(id);
  const body = $(id);
  if (!table || !table.rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = table?.columns || 1;
    cell.className = "empty";
    cell.textContent = body.dataset.emptyText || "尚无结果";
    row.append(cell);
    body.replaceChildren(row);
    return;
  }

  const wrapper = body.closest(".table-wrap");
  const fragment = document.createDocumentFragment();

  if (id === "#fileRows" && state.expandAllFiles) {
    for (let index = 0; index < table.rows.length; index += 1) {
      fragment.append(table.renderRow(table.rows[index], index));
    }
  } else {
    const visibleRows = Math.ceil(wrapper.clientHeight / ROW_HEIGHT) + VIRTUAL_OVERSCAN * 2;
    const start = Math.max(0, Math.floor(wrapper.scrollTop / ROW_HEIGHT) - VIRTUAL_OVERSCAN);
    const end = Math.min(table.rows.length, start + visibleRows);

    const top = document.createElement("tr");
    const topCell = document.createElement("td");
    topCell.colSpan = table.columns;
    topCell.className = "virtual-spacer";
    topCell.style.height = `${start * ROW_HEIGHT}px`;
    top.append(topCell);

    for (let index = start; index < end; index += 1) {
      fragment.append(table.renderRow(table.rows[index], index));
    }

    const bottom = document.createElement("tr");
    const bottomCell = document.createElement("td");
    bottomCell.colSpan = table.columns;
    bottomCell.className = "virtual-spacer";
    bottomCell.style.height = `${(table.rows.length - end) * ROW_HEIGHT}px`;
    bottom.append(bottomCell);

    fragment.prepend(top);
    fragment.append(bottom);
  }
  body.replaceChildren(fragment);
}

function bindVirtualTable(id) {
  const body = $(id);
  const wrapper = body.closest(".table-wrap");
  let frame = 0;
  wrapper.addEventListener("scroll", () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      renderVirtualWindow(id);
    });
  });
}

function setStatus(id, text) {
  $(id).textContent = text;
}

function toast(message, level = "info") {
  const host = $("#toastHost");
  const item = document.createElement("div");
  item.className = `toast ${level}`;
  item.textContent = message;
  host.append(item);
  setTimeout(() => item.remove(), 3200);
}

function csv(value) {
  return value
    .split(/[,\n;]/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function filterConfig() {
  return {
    enabled: $("#filterEnabled").checked,
    blacklist: $("#filterBlacklist").checked,
    extensions: csv($("#extensions").value),
    folders: csv($("#folders").value),
    min_size: Number($("#minSize").value || 0) * 1024,
    max_size: Number($("#maxSize").value || 0) * 1024,
  };
}

function formatSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`;
  return `${(size / 1024 ** 3).toFixed(2)} GB`;
}

function renderFiles() {
  const query = $("#fileSearch").value.trim().toLowerCase();
  const visibleFiles = state.files
    .map((file, index) => ({ file, index }))
    .filter(({ file }) => matchesFileSearch(file, query));
  const fileRow = ({ file, index }) => {
    const row = document.createElement("tr");
    const checkCell = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.index = index;
    checkbox.checked = state.included.has(file.path);
    checkbox.setAttribute("aria-label", `包含 ${file.path}`);
    checkCell.append(checkbox);
    const path = document.createElement("td");
    path.textContent = file.path;
  path.title = file.absolute_path || file.path;
    const size = document.createElement("td");
    size.textContent = formatSize(file.size);
    const action = document.createElement("td");
    const remove = document.createElement("button");
    remove.className = "ghost";
    remove.dataset.action = "remove";
    remove.dataset.index = index;
    remove.textContent = "移除";
    remove.setAttribute("aria-label", `移除 ${file.path}`);
    action.append(remove);
    row.append(checkCell, path, size, action);
    return row;
  };
  $("#fileCount").textContent = `${visibleFiles.length} / ${state.files.length} 个文件`;
  setVirtualRows("#fileRows", 4, visibleFiles, fileRow);
}

function matchesFileSearch(file, query) {
  if (!query) return true;
  return [file.path, file.absolute_path].some((value) => value?.toLowerCase().includes(query));
}

function applyScanResult(report) {
  state.files = report.files;
  state.included = new Set(report.files.map((file) => file.path));
  state.excluded = new Set();
  const prehashText = $("#prehashEnabled").checked ? "；预哈希后台进行中" : "";
  setStatus(
    "#scanStatus",
    report.cancelled
      ? `扫描已取消${prehashText}`
      : report.errors.length
        ? `扫描完成，${report.errors.length} 个错误${prehashText}`
        : `扫描完成${prehashText}`
  );
}

function applyFilters(files) {
  return invoke("filter_files", { args: { files, rules: filterConfig() } });
}

function selectedFiles() {
  return state.files.filter((file) => state.included.has(file.path));
}

function renderHashResults(rows, bodyId) {
  const hashRow = (row) => {
    const tr = document.createElement("tr");
    const status = document.createElement("td");
    status.textContent = row.error ? "ERR" : "OK";
    status.className = row.error ? "error" : "pass";
    const path = document.createElement("td");
    path.textContent = row.path;
    const hash = document.createElement("td");
    hash.textContent = row.error || row.hash;
    hash.className = "hash-text";
    tr.append(status, path, hash);
    return tr;
  };
  setVirtualRows(bodyId, 3, rows, hashRow);
}

function hashRows() {
  return state.entries.map((entry) => ({
    path: entry.path,
    hash: entry.hash,
    error: entry.status === "error" ? "error" : "",
  }));
}

function checklistsFromState() {
  const checklists = {};
  for (const [name, entries] of state.checklists) {
    checklists[name] = entries.filter((entry) => entry.hash && !entry.error);
  }
  return checklists;
}

function documentFromState() {
  const checklists = checklistsFromState();
  return {
    format_version: 1,
    algorithm: $("#algorithm").value,
    active_checklist: state.activeChecklist,
    checklists,
    exclude_paths: [...state.excluded],
    exclude_rules: filterConfig(),
    metadata: {},
  };
}

function projectFromState() {
  const checklists = checklistsFromState();
  const checklist = checklists[state.activeChecklist] || [];
  return {
    ...state.project,
    version: 1,
    base_directory: $("#rootPath").value,
    algorithm: $("#algorithm").value,
    files: state.files,
    entries: checklist,
    checklists,
    active_checklist: state.activeChecklist,
    exclude_paths: [...state.excluded],
    exclude_rules: filterConfig(),
    fitrec_private_key_path: $("#privateKeyPath").value,
    data_shards: Number($("#dataShards").value),
    parity_shards: Number($("#parityShards").value),
    shard_size: Math.max(1, Math.round(Number($("#shardSize").value || 1) * 1024 * 1024)),
    recovery_mode: $("#recoveryMode").value,
    checksum_output_path: $("#checksumPath").value,
    checksum_format: document.querySelector("input[name='checksumFormat']:checked").value,
    verifier_title: state.project.verifier_title || "File Integrity Verifier",
    verifier_version: state.project.verifier_version || "1.0.0.0",
    verifier_company: state.project.verifier_company || "",
    verifier_copyright: state.project.verifier_copyright || "",
  };
}

function loadProjectState(project) {
  state.project = project;
  $("#rootPath").value = project.base_directory || "";
  $("#algorithm").value = project.algorithm || "sha256";
  $("#privateKeyPath").value = project.fitrec_private_key_path || "";
  $("#dataShards").value = project.data_shards || 16;
  $("#parityShards").value = project.parity_shards || 4;
  $("#recoveryMode").value = project.recovery_mode || "crossFile";
  $("#shardSize").value = (project.shard_size || 1024 * 1024) / (1024 * 1024);
  $("#checksumPath").value = project.checksum_output_path || "";
  state.files = project.files || [];
  state.entries = project.entries || [];
  state.activeChecklist = project.active_checklist || "default";
  state.included = new Set(state.files.map((file) => file.path));
  state.excluded = new Set(project.exclude_paths || []);
  state.checklists = new Map(Object.entries(project.checklists || { default: [] }));
  $("#projectName").textContent = project.project_name || "Untitled";
  $("#password").value = "";
  refreshRecoveryEstimate();
  renderFiles();
  renderChecklistSelect();
  renderHashResults(hashRows(), "#hashRows");
  renderChecklistRows();
  toast("项目已加载", "success");
}

async function refreshRecoveryEstimate(immediate = false) {
  window.clearTimeout(recoveryEstimateTimer);
  const update = async () => {
    if (!$("#rootPath").value) {
      $("#recoveryEstimate").textContent = "--";
      $("#recoveryTotalEstimate").textContent = "--";
      $("#recoveryEstimateDetail").textContent = "请先选择源目录";
      return;
    }
    try {
      const estimate = await invoke("estimate_file_recovery_command", {
        args: {
          document: documentFromState(),
          sourceDirectory: $("#rootPath").value,
          dataShards: Number($("#dataShards").value),
          parityShards: Number($("#parityShards").value),
          shardSize: Math.max(1, Math.round(Number($("#shardSize").value || 1) * 1024 * 1024)),
          mode: $("#recoveryMode").value,
        },
      });
      $("#recoveryEstimate").textContent = formatSize(estimate.paritySize);
      $("#recoveryTotalEstimate").textContent = formatSize(estimate.totalSize);
      const percent = Math.round((estimate.recoverableRatio || 0) * 100);
      $("#recoveryRecoverable").textContent = `${percent}%（${estimate.recoverableFiles} / ${estimate.fileCount}）`;
      $("#recoveryEstimateDetail").textContent =
        `${estimate.fileCount} 个文件，${estimate.groupCount} 组；含签名头部`;
    } catch (error) {
      $("#recoveryEstimate").textContent = "--";
      $("#recoveryTotalEstimate").textContent = "--";
      $("#recoveryRecoverable").textContent = "--";
      $("#recoveryEstimateDetail").textContent = String(error);
    }
  };
  if (immediate) {
    await update();
    return;
  }
  recoveryEstimateTimer = window.setTimeout(update, 220);
}

function renderChecklistRows() {
  renderHashResults(
    state.entries.map((entry) => ({ path: entry.path, hash: entry.hash, error: entry.status === "error" ? "error" : "" })),
    "#checklistRows"
  );
}

function renderChecklistSelect() {
  const select = $("#checklistName");
  select.innerHTML = "";
  for (const name of [...state.checklists.keys()].sort()) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    option.selected = name === state.activeChecklist;
    select.append(option);
  }
}

function setProgress(barId, completed, total) {
  $(barId).style.width = total ? `${Math.round((completed / total) * 100)}%` : "0%";
}

function statusLabel(status) {
  return { pass: "通过", fail: "失败", missing: "缺失", extra: "多余", error: "错误" }[status] || status;
}

function renderVerifyReport(report) {
  $("#passed").textContent = report.passed;
  $("#failed").textContent = report.failed;
  $("#missing").textContent = report.missing;
  $("#extra").textContent = report.extra_count;
  const detailRow = (detail) => {
    const row = document.createElement("tr");
    const status = document.createElement("td");
    status.textContent = statusLabel(detail.status);
    status.className = `status-${detail.status}`;
    const path = document.createElement("td");
    path.textContent = detail.path;
    const expected = document.createElement("td");
    expected.textContent = detail.expected;
    const actual = document.createElement("td");
    actual.textContent = detail.actual;
    row.append(status, path, expected, actual);
    return row;
  };
  setVirtualRows("#verifyRows", 4, report.details, detailRow);
}

function activatePanel(panelId) {
  document.querySelectorAll(".nav-item").forEach((item) => {
    const active = item.dataset.panel === panelId;
    item.classList.toggle("active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.toggle("hidden", page.id !== panelId);
  });
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => activatePanel(button.dataset.panel));
});

$("#fileRows").addEventListener("change", (event) => {
  const checkbox = event.target;
  if (checkbox.type !== "checkbox" || checkbox.dataset.index === undefined) return;
  const file = state.files[Number(checkbox.dataset.index)];
  if (!file) return;
  if (checkbox.checked) {
    state.included.add(file.path);
    state.excluded.delete(file.path);
  } else {
    state.included.delete(file.path);
    state.excluded.add(file.path);
  }
});

$("#fileRows").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action='remove']");
  if (!button) return;
  const index = Number(button.dataset.index);
  const file = state.files[index];
  if (!file) return;
  state.files.splice(index, 1);
  state.included.delete(file.path);
  state.excluded.delete(file.path);
  renderFiles();
});

["#fileRows", "#hashRows", "#checklistRows", "#verifyRows"].forEach(bindVirtualTable);

$("#browseRoot").addEventListener("click", async () => {
  const path = await invoke("pick_directory");
  if (path) $("#rootPath").value = path;
  refreshRecoveryEstimate();
});

$("#rootPath").addEventListener("input", () => refreshRecoveryEstimate());

["#recoveryMode", "#dataShards", "#parityShards", "#shardSize"].forEach((id) => {
  $(id).addEventListener("change", () => refreshRecoveryEstimate());
  $(id).addEventListener("input", () => refreshRecoveryEstimate());
});

$("#scan").addEventListener("click", async () => {
  setStatus("#scanStatus", "扫描中...");
  try {
    applyScanResult(
      await invoke("scan_directory", {
        args: {
          rootPath: $("#rootPath").value,
          prehash: $("#prehashEnabled").checked,
          algorithm: $("#algorithm").value,
        },
      })
    );
    state.files = await applyFilters(state.files);
    state.included = new Set(state.files.map((file) => file.path));
    renderFiles();
  } catch (error) {
    renderFiles();
    setStatus("#scanStatus", String(error));
    toast(String(error), "error");
  }
});

$("#stopScan").addEventListener("click", () => invoke("cancel_scan"));

$("#addFiles").addEventListener("click", async () => {
  const paths = await invoke("pick_files");
  if (!paths?.length) return;
  const existing = new Set(state.files.map((file) => file.absolute_path));
  for (const absolutePath of paths) {
    if (existing.has(absolutePath)) continue;
    const name = absolutePath.split(/[\\/]/).pop();
    state.files.push({ path: name, absolute_path: absolutePath, size: 0, modified: null });
  }
  renderFiles();
});

$("#applyFilters").addEventListener("click", async () => {
  try {
    state.files = await applyFilters(state.files);
    state.included = new Set(state.files.map((file) => file.path));
    renderFiles();
  } catch (error) {
    setStatus("#scanStatus", String(error));
  }
});

$("#selectAll").addEventListener("click", () => {
  state.included = new Set(state.files.map((file) => file.path));
  state.excluded.clear();
  renderFiles();
});

$("#selectAllMatches").addEventListener("click", () => {
  const query = $("#fileSearch").value.trim().toLowerCase();
  const matches = state.files.filter((file) => matchesFileSearch(file, query));
  for (const file of matches) {
    state.included.add(file.path);
    state.excluded.delete(file.path);
  }
  renderFiles();
});

$("#fileSearch").addEventListener("input", () => renderFiles());

$("#expandAllFiles").addEventListener("click", () => {
  state.expandAllFiles = !state.expandAllFiles;
  const button = $("#expandAllFiles");
  button.setAttribute("aria-pressed", String(state.expandAllFiles));
  button.classList.toggle("active", state.expandAllFiles);
  button.textContent = state.expandAllFiles ? "恢复虚拟列表" : "展开全部";
  renderFiles();
});

$("#invertSelection").addEventListener("click", () => {
  const next = new Set();
  for (const file of state.files) {
    if (!state.included.has(file.path)) next.add(file.path);
  }
  state.included = next;
  renderFiles();
});

$("#clearFiles").addEventListener("click", () => {
  state.files = [];
  state.included.clear();
  state.excluded.clear();
  renderFiles();
  setStatus("#scanStatus", "已清空");
});

$("#startHash").addEventListener("click", async () => {
  const files = selectedFiles();
  if (!files.length) {
    setStatus("#hashStatus", "请先选择文件");
    return;
  }
  $("#startHash").disabled = true;
  $("#stopHash").disabled = false;
  try {
    const report = await invoke("calculate_hashes", {
      args: {
        basePath: $("#rootPath").value,
        paths: files.map((file) => file.absolute_path),
        algorithm: $("#algorithm").value,
      },
    });
    state.entries = report.results.map((result, index) => ({
      path: files[index].path,
      hash: result.hash,
      size: files[index].size,
      status: result.error ? "error" : "ok",
    }));
    state.checklists.set(state.activeChecklist, state.entries);
    renderHashResults(hashRows(), "#hashRows");
    renderChecklistRows();
    await refreshRecoveryEstimate(true);
    setStatus("#hashStatus", `哈希完成，复用预哈希 ${report.reused} / ${report.total}`);
    toast(`哈希计算完成，复用预哈希 ${report.reused} / ${report.total}`, "success");
  } catch (error) {
    setStatus("#hashStatus", String(error));
    toast(String(error), "error");
  } finally {
    $("#startHash").disabled = false;
    $("#stopHash").disabled = true;
  }
});

$("#pauseHash").addEventListener("click", async () => {
  state.paused = await invoke("toggle_hash_pause");
  $("#pauseHash").textContent = state.paused ? "继续" : "暂停";
});

$("#stopHash").addEventListener("click", () => invoke("cancel_hashing"));

$("#newChecklist").addEventListener("click", () => {
  const name = window.prompt("清单名称", "checklist");
  if (!name || state.checklists.has(name)) return;
  state.checklists.set(name, []);
  state.activeChecklist = name;
  state.entries = [];
  renderChecklistSelect();
  renderChecklistRows();
});

$("#deleteChecklist").addEventListener("click", () => {
  if (state.checklists.size <= 1) return;
  state.checklists.delete(state.activeChecklist);
  state.activeChecklist = [...state.checklists.keys()][0];
  state.entries = state.checklists.get(state.activeChecklist) || [];
  renderChecklistSelect();
  renderChecklistRows();
});

$("#checklistName").addEventListener("change", (event) => {
  state.activeChecklist = event.target.value;
  state.entries = state.checklists.get(state.activeChecklist) || [];
  renderChecklistRows();
  refreshRecoveryEstimate();
});

$("#browseChecksum").addEventListener("click", async () => {
  const format = document.querySelector("input[name='checksumFormat']:checked").value;
  const path = await invoke("pick_save_file", { name: `integrity.${format}`, extensions: [format] });
  if (path) $("#checksumPath").value = path;
});

$("#exportChecksum").addEventListener("click", async () => {
  const format = document.querySelector("input[name='checksumFormat']:checked").value;
  let path = $("#checksumPath").value;
  if (!path) {
    path = await invoke("pick_save_file", { name: `integrity.${format}`, extensions: [format] });
    if (!path) return;
    $("#checksumPath").value = path;
  }
  try {
    const entries = state.entries
      .filter((entry) => entry.hash && !entry.error)
      .map((entry) => ({ path: entry.path, hash: entry.hash }));
    await invoke("write_checksum_file", {
      args: { path, format, algorithm: $("#algorithm").value, entries },
    });
    setStatus("#checksumStatus", `已导出 ${path}`);
    toast("校验文件已导出", "success");
  } catch (error) {
    setStatus("#checksumStatus", String(error));
    toast(String(error), "error");
  }
});

$("#importChecksum").addEventListener("click", async () => {
  const path = await invoke("pick_file");
  if (!path) return;
  await loadChecksumFile(path);
});

async function loadChecksumFile(path) {
  try {
    const loaded = await invoke("read_checksum_file", { path });
    $("#checksumPath").value = path;
    $("#algorithm").value = loaded.algorithm || "sha256";
    state.entries = loaded.entries.map((entry) => ({
      path: entry.path,
      hash: entry.hash,
      status: "ok",
    }));
    state.checklists.set(state.activeChecklist, state.entries);
    renderChecklistRows();
    renderHashResults(hashRows(), "#hashRows");
    setStatus("#checksumStatus", `已导入 ${path}`);
  } catch (error) {
    setStatus("#checksumStatus", String(error));
  }
}

$("#encryptChecksum").addEventListener("click", async () => {
  const path = $("#checksumPath").value;
  const password = $("#password").value;
  if (!path || !password) {
    setStatus("#checksumStatus", "需要校验文件和密码");
    return;
  }
  const suggested = `${path}.enc`;
  const output = await invoke("pick_save_file", { name: suggested.split(/[\\/]/).pop(), extensions: ["enc"] });
  if (!output) return;
  try {
    const encrypted = await invoke("encrypt_checksum_file", {
      args: { path, outputPath: output, password },
    });
    setStatus("#checksumStatus", `已加密 ${encrypted}`);
    toast("校验文件已加密", "success");
  } catch (error) {
    setStatus("#checksumStatus", String(error));
    toast(String(error), "error");
  }
});

$("#decryptChecksum").addEventListener("click", async () => {
  const path = $("#checksumPath").value;
  const password = $("#password").value;
  if (!path || !password) {
    setStatus("#checksumStatus", "需要加密文件和密码");
    return;
  }
  const name = path.split(/[\\/]/).pop();
  const encodedName = name.replace(/\.[^./\\]+$/, "");
  const output = await invoke("pick_save_file", {
    name: `${encodedName}.decoded.csv`,
    extensions: ["csv", "sfv"],
  });
  if (!output) return;
  try {
    const decrypted = await invoke("decrypt_checksum_file", {
      args: { path, outputPath: output, password },
    });
    await loadChecksumFile(decrypted);
    toast("校验文件已解密导入", "success");
  } catch (error) {
    setStatus("#checksumStatus", String(error));
    toast(String(error), "error");
  }
});

$("#signChecksum").addEventListener("click", async () => {
  const path = $("#checksumPath").value;
  const privateKey = $("#privateKeyPath").value;
  if (!path || !privateKey) {
    setStatus("#checksumStatus", "需要校验文件和私钥");
    return;
  }
  try {
    const signature = await invoke("sign_checksum_file", { path, privateKeyPath: privateKey });
    setStatus("#checksumStatus", `已签名 ${signature}`);
  } catch (error) {
    setStatus("#checksumStatus", String(error));
  }
});

$("#verifyChecksum").addEventListener("click", async () => {
  const path = $("#checksumPath").value;
  const publicKey = $("#privateKeyPath").value;
  if (!path || !publicKey) {
    setStatus("#checksumStatus", "需要校验文件和公钥");
    return;
  }
  try {
    await invoke("verify_checksum_file", { path, publicKeyPath: `${publicKey}.pub` });
    setStatus("#checksumStatus", "签名有效");
  } catch (error) {
    setStatus("#checksumStatus", String(error));
  }
});

$("#browseRecord").addEventListener("click", async () => {
  const path = await invoke("pick_save_file", { name: "release.fitrec", extensions: ["fitrec"] });
  if (path) $("#recordPath").value = path;
});

$("#browseKey").addEventListener("click", async () => {
  const path = await invoke("pick_file");
  if (path) $("#privateKeyPath").value = path;
});

$("#makeKey").addEventListener("click", async () => {
  const privateKey = await invoke("pick_save_file", { name: "fitrec.key", extensions: ["key"] });
  if (!privateKey) return;
  await invoke("generate_keypair_command", {
    args: { privateKeyPath: privateKey, publicKeyPath: `${privateKey}.pub` },
  });
  $("#privateKeyPath").value = privateKey;
  setStatus("#recordStatus", "密钥已生成");
});

async function locateVerifier() {
  try {
    const path = await invoke("locate_verifier");
    const field = $("#verifierPath");
    field.value = path === "builtin-verifier" ? "内置 Verifier" : path || "";
    field.dataset.value = path || "";
    $("#packVerifier").disabled = !path;
    setStatus(
      "#recordStatus",
      path
        ? path === "builtin-verifier"
          ? "已启用内置于 Builder 的验证器"
          : `验证器 EXE 已定位：${path}`
        : "未找到验证器 EXE；请先运行 python build.py --rust"
    );
  } catch (error) {
    const field = $("#verifierPath");
    field.value = "";
    field.dataset.value = "";
    $("#packVerifier").disabled = true;
    setStatus("#recordStatus", String(error));
  }
}

$("#locateVerifier").addEventListener("click", locateVerifier);
locateVerifier();

$("#browsePack").addEventListener("click", async () => {
  const path = await invoke("pick_directory");
  if (path) $("#packPath").value = path;
});

$("#generate").addEventListener("click", async () => {
  if (!state.entries.some((entry) => entry.status === "ok")) {
    setStatus("#recordStatus", "请先生成有效哈希");
    return;
  }
  try {
    const output = await invoke("generate_fitrec_command", {
      args: {
        document: documentFromState(),
        sourceDirectory: $("#rootPath").value,
        outputPath: $("#recordPath").value,
        privateKeyPath: $("#privateKeyPath").value,
        dataShards: Number($("#dataShards").value),
        parityShards: Number($("#parityShards").value),
        shardSize: Math.max(1, Math.round(Number($("#shardSize").value || 1) * 1024 * 1024)),
        mode: $("#recoveryMode").value,
      },
    });
    setStatus("#recordStatus", `已生成 ${output}、${output}.pub 和 ${output}.parity`);
    toast("恢复记录和文件纠错档案已生成", "success");
  } catch (error) {
    setStatus("#recordStatus", String(error));
    toast(String(error), "error");
  }
});

$("#packVerifier").addEventListener("click", async () => {
  if (!$("#recordPath").value || !$("#packPath").value) {
    setStatus("#recordStatus", "需要恢复记录和输出目录");
    return;
  }
  try {
    const output = await invoke("pack_native_verifier", {
      args: {
        outputDirectory: $("#packPath").value,
        recordPath: $("#recordPath").value,
        verifierPath: $("#verifierPath").dataset.value || "",
      },
    });
    setStatus("#recordStatus", `已打包到 ${output}`);
    toast("原生验证器已打包", "success");
  } catch (error) {
    setStatus("#recordStatus", String(error));
    toast(String(error), "error");
  }
});

$("#browseVerify").addEventListener("click", async () => {
  const path = await invoke("pick_directory");
  if (path) $("#verifyPath").value = path;
});

$("#simulate").addEventListener("click", async () => {
  $("#simulate").disabled = true;
  $("#stopVerify").disabled = false;
  try {
    const report = await invoke("verify_document", {
      args: { document: documentFromState(), targetPath: $("#verifyPath").value },
    });
    renderVerifyReport(report);
    setStatus("#recordStatus", report.cancelled ? "验证已取消" : "验证完成");
  } catch (error) {
    setStatus("#recordStatus", String(error));
    toast(String(error), "error");
  } finally {
    $("#simulate").disabled = false;
    $("#stopVerify").disabled = true;
  }
});

$("#stopVerify").addEventListener("click", () => invoke("cancel_verification"));

$("#saveProject").addEventListener("click", async () => {
  const path = await invoke("pick_save_file", { name: "project.fitbuilder", extensions: ["fitbuilder"] });
  if (!path) return;
  await invoke("save_project", { path, project: projectFromState() });
  state.project.project_name = path.split(/[\\/]/).pop();
  $("#projectName").textContent = state.project.project_name;
  toast("项目已保存", "success");
});

$("#openProject").addEventListener("click", async () => {
  const path = await invoke("pick_file");
  if (!path) return;
  loadProjectState(await invoke("load_project", { path }));
});

$("#newProject").addEventListener("click", () => {
  location.reload();
});

$("#openGitHub").addEventListener("click", async () => {
  const url = "https://github.com/taichiia/Integrity-verifier";
  try {
    await window.__TAURI__.opener.openUrl(url);
  } catch {
    window.open(url, "_blank", "noopener");
  }
});

const TOUR_STORAGE_KEY = "fit-builder-onboarding-v2";
const TOUR_STEPS = [
  {
    target: null,
    panel: null,
    title: "FIT 是做什么的？",
    body: "FIT 帮你回答两个问题：文件有没有被改过？如果坏掉或丢了，能不能修回来？Builder 负责制作校验记录和恢复档案，Verifier 给接收方用来验证或修复。",
    points: [
      "校验：发现文件被修改、删除或多出。",
      "恢复：利用纠错档案修复损坏或缺失的文件。",
    ],
  },
  {
    target: null,
    panel: null,
    title: "三个关键产物",
    body: "后面会反复看到几个文件。先分清它们，后面的配置就容易理解了。",
    points: [
      ".fitrec：签名后的校验记录，用来判断文件是否变化。",
      ".fitrec.pub：公钥，用来验证记录签名，可以随记录分发。",
      ".fitrec.parity：恢复档案，保存纠错分片；只有需要恢复时才分发。",
      "fitrec.key：私钥，只留在作者手里，不要放进分发包。",
    ],
  },
  {
    target: ".topbar-actions",
    panel: null,
    title: "项目与外观",
    body: "这里用于新建、打开、保存项目，也能切换暗色模式或打开 GitHub 仓库。",
  },
  {
    target: "#panel-files .field-row",
    panel: "panel-files",
    title: "选择并扫描目录",
    body: "先选择源目录，然后点击“扫描”。Builder 会递归读取文件列表。",
    points: [
      "扫描只是收集文件列表，还没有正式计算哈希。",
      "如果开启预哈希，扫描过程中会先算一部分哈希，后面正式哈希可以复用缓存。",
    ],
  },
  {
    target: "#panel-files .filters",
    panel: "panel-files",
    title: "控制扫描范围",
    body: "扩展名、目录、大小范围和黑名单会决定哪些文件进入清单。确认后点击“应用过滤”。",
    points: [
      "清单只保护你选中的文件，未选中的文件不会参与校验或恢复。",
      "文件列表支持搜索、全选、反选和展开全部。",
    ],
  },
  {
    target: "#panel-hashes .toolbar",
    panel: "panel-hashes",
    title: "计算校验值",
    body: "选择 SHA-256、SHA-512 或 MD5 后开始计算。长时间任务可以暂停或停止。",
    points: [
      "SHA-256 是推荐的默认算法，兼顾安全性和速度。",
      "MD5 通常只用于兼容旧系统，不建议用于安全校验。",
    ],
  },
  {
    target: "#panel-checklists .toolbar",
    panel: "panel-checklists",
    title: "管理校验清单",
    body: "这里可以导出或导入 CSV / SFV，也可以签名、验证签名或加密校验文件。",
    points: [
      "CSV 和 SFV 适合与外部工具交换校验结果。",
      "签名能防止清单被篡改；加密用于保护清单内容。",
    ],
  },
  {
    target: "#panel-package section.card:nth-of-type(1)",
    panel: "panel-package",
    title: "生成签名记录",
    body: "设置 .fitrec 输出路径，并生成或选择 Ed25519 私钥。公钥会自动写在记录旁边。",
    points: [
      "私钥负责签名；公钥负责验证签名。",
      "私钥丢失后无法用同一身份继续签名，所以请单独备份。",
    ],
  },
  {
    target: "#recoveryMode",
    panel: "panel-package",
    title: "选择恢复模式",
    body: "恢复模式决定纠错档案保护什么类型的损坏。选错模式，档案可能无法修复你最担心的问题。",
    points: [
      "singleFile：修复单个文件内部的损坏，不擅长整个文件完全丢失。",
      "crossFile：把同组文件当作通道；整个文件缺失时有机会重建。",
      "dual：同时支持文件内修复和跨文件重建，档案体积更大。",
    ],
  },
  {
    target: "#panel-package section.card:nth-of-type(2) .form-grid",
    panel: "panel-package",
    title: "分片：体积与容错的平衡",
    body: "分片是恢复档案的基本单位。数据分片来自原始文件，纠错分片是从数据分片计算出来的冗余。",
    points: [
      "可以把它理解为：把文件切成小块，再用冗余块补齐缺失或损坏的块。",
      "数据分片越多，分块粒度越细。",
      "纠错分片越多，可容忍的损坏越多，但档案也越大。",
      "默认 16 + 4 表示每个组最多能容忍 4 个分片损坏或丢失。",
      "分片大小影响块粒度：较小分片更细，较大分片开销更低。",
    ],
  },
  {
    target: "#panel-package section.card:nth-of-type(2) .estimate-row",
    panel: "panel-package",
    title: "看懂预估结果",
    body: "配置变化时，下方会实时估算体积和可恢复比例。它适合在生成前比较方案。",
    points: [
      "预计恢复档案：.fitrec.parity 大约多大。",
      "预计总输出：记录、公钥和恢复档案等总大小。",
      "预计可恢复：当前配置下大概能恢复多少文件。",
      "这是估算值；实际结果仍取决于哪些文件损坏或缺失。",
    ],
  },
  {
    target: "#panel-package section.card:nth-of-type(3)",
    panel: "panel-package",
    title: "分发验证器",
    body: "选择输出目录后打包验证器。没有选择外部 EXE 时，Builder 会使用内嵌 Verifier。",
    points: [
      "只验证：发 Verifier、.fitrec 和 .fitrec.pub。",
      "需要恢复：再加上 .fitrec.parity。",
      "私钥永远不要发给接收方。",
    ],
  },
  {
    target: null,
    panel: "panel-package",
    title: "准备完成",
    body: "完整流程是：扫描 -> 哈希 -> 生成记录和纠错档 -> 打包验证器 -> 接收方验证或恢复。",
    points: [
      "Verifier 先判断文件是否变化；必要时再用恢复档案修复。",
      "恢复会写到单独目录，不会直接覆盖原文件。",
      "之后可以从顶栏问号按钮重新打开这个教程。",
    ],
  },
];

let tutorialStep = 0;
let tutorialPositionFrame = 0;

function currentTutorialTarget() {
  const step = TOUR_STEPS[tutorialStep];
  if (!step || !step.target) return null;
  const target = document.querySelector(step.target);
  return target && target.getClientRects().length ? target : null;
}

function placeShade(edge, left, top, width, height) {
  const shade = document.querySelector(`.tour-shade[data-edge="${edge}"]`);
  if (!shade) return;
  shade.hidden = width <= 0 || height <= 0;
  shade.style.left = `${left}px`;
  shade.style.top = `${top}px`;
  shade.style.width = `${Math.max(0, width)}px`;
  shade.style.height = `${Math.max(0, height)}px`;
}

function positionTutorial() {
  const overlay = $("#tutorialOverlay");
  if (overlay.hidden) return;

  const target = currentTutorialTarget();
  const highlight = overlay.querySelector(".tour-highlight");
  const card = overlay.querySelector(".tour-card");
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  if (!target) {
    document.querySelector('.tour-shade[data-edge="all"]').hidden = false;
    ["top", "bottom", "left", "right"].forEach((edge) => {
      document.querySelector(`.tour-shade[data-edge="${edge}"]`).hidden = true;
    });
    highlight.hidden = true;
    card.style.left = `${Math.max(16, (viewportWidth - card.offsetWidth) / 2)}px`;
    card.style.top = `${Math.max(16, (viewportHeight - card.offsetHeight) / 2)}px`;
    return;
  }

  const padding = 12;
  const rect = target.getBoundingClientRect();
  const left = Math.max(0, rect.left - padding);
  const top = Math.max(0, rect.top - padding);
  const right = Math.min(viewportWidth, rect.right + padding);
  const bottom = Math.min(viewportHeight, rect.bottom + padding);
  const width = Math.max(0, right - left);
  const height = Math.max(0, bottom - top);

  document.querySelector('.tour-shade[data-edge="all"]').hidden = true;
  placeShade("top", 0, 0, viewportWidth, top);
  placeShade("bottom", 0, bottom, viewportWidth, viewportHeight - bottom);
  placeShade("left", 0, top, left, height);
  placeShade("right", right, top, viewportWidth - right, height);

  highlight.hidden = false;
  highlight.style.left = `${left}px`;
  highlight.style.top = `${top}px`;
  highlight.style.width = `${width}px`;
  highlight.style.height = `${height}px`;

  const cardWidth = card.offsetWidth;
  const cardHeight = card.offsetHeight;
  const gap = 18;
  const spaceBelow = viewportHeight - bottom - 16;
  const spaceAbove = top - 16;
  const spaceRight = viewportWidth - right - 16;
  const spaceLeft = left - 16;

  let cardLeft;
  let cardTop;
  if (spaceBelow >= cardHeight + gap) {
    cardTop = bottom + gap;
    cardLeft = left + width / 2 - cardWidth / 2;
  } else if (spaceAbove >= cardHeight + gap) {
    cardTop = top - cardHeight - gap;
    cardLeft = left + width / 2 - cardWidth / 2;
  } else if (spaceRight >= cardWidth + gap) {
    cardLeft = right + gap;
    cardTop = top + height / 2 - cardHeight / 2;
  } else if (spaceLeft >= cardWidth + gap) {
    cardLeft = left - cardWidth - gap;
    cardTop = top + height / 2 - cardHeight / 2;
  } else {
    cardLeft = (viewportWidth - cardWidth) / 2;
    cardTop = (viewportHeight - cardHeight) / 2;
  }

  card.style.left = `${Math.max(16, Math.min(viewportWidth - cardWidth - 16, cardLeft))}px`;
  card.style.top = `${Math.max(16, Math.min(viewportHeight - cardHeight - 16, cardTop))}px`;
}

function scheduleTutorialPosition() {
  if (tutorialPositionFrame) cancelAnimationFrame(tutorialPositionFrame);
  tutorialPositionFrame = requestAnimationFrame(() => {
    tutorialPositionFrame = 0;
    positionTutorial();
  });
}

function setTutorialStep(index) {
  tutorialStep = Math.max(0, Math.min(TOUR_STEPS.length - 1, index));
  const step = TOUR_STEPS[tutorialStep];
  const overlay = $("#tutorialOverlay");
  overlay.hidden = false;
  document.body.classList.add("tutorial-open");

  if (step.panel) activatePanel(step.panel);
  $("#tutorialTitle").textContent = step.title;
  $("#tutorialBody").textContent = step.body;
  const points = step.points || [];
  const pointsHost = $("#tutorialPoints");
  pointsHost.replaceChildren(
    ...points.map((point) => {
      const item = document.createElement("li");
      const separator = point.indexOf("：");
      if (separator > 0) {
        const label = document.createElement("strong");
        label.textContent = point.slice(0, separator + 1);
        item.append(label, document.createTextNode(point.slice(separator + 1)));
      } else {
        item.textContent = point;
      }
      return item;
    }),
  );
  pointsHost.hidden = points.length === 0;
  $("#tutorialProgress").textContent = `${tutorialStep + 1} / ${TOUR_STEPS.length}`;
  $("#tutorialPrev").disabled = tutorialStep === 0;
  $("#tutorialNext").textContent = tutorialStep === TOUR_STEPS.length - 1 ? "完成" : "下一步";

  const target = currentTutorialTarget();
  if (target) target.scrollIntoView({ block: "center", inline: "nearest" });
  requestAnimationFrame(positionTutorial);
  setTimeout(positionTutorial, 220);
  $("#tutorialNext").focus({ preventScroll: true });
}

function closeTutorial(markComplete = false) {
  if (markComplete || !$("#tutorialOverlay").hidden) {
    localStorage.setItem(TOUR_STORAGE_KEY, "completed");
  }
  $("#tutorialOverlay").hidden = true;
  document.body.classList.remove("tutorial-open");
}

function startTutorial() {
  setTutorialStep(0);
}

$("#tutorialButton").addEventListener("click", startTutorial);
$("#tutorialSkip").addEventListener("click", () => closeTutorial(false));
$("#tutorialPrev").addEventListener("click", () => setTutorialStep(tutorialStep - 1));
$("#tutorialNext").addEventListener("click", () => {
  if (tutorialStep === TOUR_STEPS.length - 1) {
    closeTutorial(true);
  } else {
    setTutorialStep(tutorialStep + 1);
  }
});

window.addEventListener("keydown", (event) => {
  if ($("#tutorialOverlay").hidden) return;
  if (event.key === "Escape") {
    closeTutorial(false);
  } else if (event.key === "ArrowLeft" && tutorialStep > 0) {
    setTutorialStep(tutorialStep - 1);
  } else if (event.key === "ArrowRight") {
    $("#tutorialNext").click();
  }
});

window.addEventListener("resize", scheduleTutorialPosition);
window.addEventListener("scroll", scheduleTutorialPosition, true);

$("#themeToggle").addEventListener("click", () => {
  const next = document.body.dataset.theme === "dark" ? "light" : "dark";
  document.body.dataset.theme = next;
  localStorage.setItem("fit-builder-theme", next);
});

window.__TAURI__.event.listen("builder-scan-progress", ({ payload }) => {
  if (scanProgressFrame) return;
  scanProgressFrame = requestAnimationFrame(() => {
    scanProgressFrame = 0;
    setStatus(
      "#scanStatus",
      payload.stage === "prehash"
        ? `预哈希中 ${payload.completed} / ${payload.total}：${payload.path}`
        : `扫描中 ${payload.count}：${payload.path}`
    );
  });
});

window.__TAURI__.event.listen("builder-hash-progress", ({ payload }) => {
  if (hashProgressFrame) return;
  hashProgressFrame = requestAnimationFrame(() => {
    hashProgressFrame = 0;
    setProgress("#hashBar", payload.completed, payload.total);
    $("#hashStats").textContent = `${payload.completed} / ${payload.total}`;
    setStatus("#hashStatus", payload.path);
  });
});

window.__TAURI__.event.listen("builder-verify-progress", ({ payload }) => {
  if (verifyProgressFrame) return;
  verifyProgressFrame = requestAnimationFrame(() => {
    verifyProgressFrame = 0;
    setProgress("#verifyBar", payload.completed, payload.total);
    $("#passed").textContent = payload.passed || 0;
    $("#failed").textContent = payload.failed || 0;
    $("#missing").textContent = payload.missing || 0;
    $("#extra").textContent = payload.extra || 0;
    setStatus("#recordStatus", `已检查 ${payload.completed} / ${payload.total}；通过 ${payload.passed || 0}，失败 ${payload.failed || 0}`);
  });
});

window.__TAURI__.event.listen("builder-file-recovery-progress", ({ payload }) => {
  if (recordProgressFrame) return;
  recordProgressFrame = requestAnimationFrame(() => {
    recordProgressFrame = 0;
    setProgress("#recordBar", payload.completed, payload.total);
    setStatus("#recordStatus", `正在生成文件纠错档案：${payload.path}`);
  });
});

document.body.dataset.theme = localStorage.getItem("fit-builder-theme") || "light";
renderChecklistSelect();
renderChecklistRows();

if (!localStorage.getItem(TOUR_STORAGE_KEY)) {
  setTimeout(startTutorial, 240);
}
