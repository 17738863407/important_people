"use strict";

const appState = {
  fields: [],
  records: [],
  filtered: [],
  selected: new Set(),
  sort: { fieldId: "", direction: "asc" },
  advancedRules: [],
  advancedLogic: "and",
  hiddenFieldIds: new Set(),
  fieldVisibilityLoaded: false,
  virtualWindow: { start: -1, end: -1, frameId: 0 },
  status: {},
};

const HIDDEN_FIELDS_STORAGE_KEY = "institution-workbench-hidden-fields";
const VIRTUAL_ROW_LIMIT = 100;
const TABLE_HEADER_HEIGHT = 40;
const TABLE_ROW_HEIGHT = 38;

const $ = (selector) => document.querySelector(selector);

function icon(name) {
  return `<svg class="icon" aria-hidden="true"><use href="/icons.svg#${name}"></use></svg>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function fieldById(fieldId) {
  return appState.fields.find((field) => field.field_id === fieldId);
}

function fieldIdByName(...names) {
  const field = appState.fields.find((item) => names.includes(item.export_name) || names.includes(item.source_name));
  return field?.field_id || "";
}

function recordById(recordId) {
  return appState.records.find((record) => record.record_id === recordId);
}

function visibleFields() {
  return appState.fields.filter((field) => !appState.hiddenFieldIds.has(field.field_id));
}

function loadFieldVisibility() {
  if (!appState.fieldVisibilityLoaded) {
    try {
      const stored = JSON.parse(localStorage.getItem(HIDDEN_FIELDS_STORAGE_KEY) || "[]");
      if (Array.isArray(stored)) appState.hiddenFieldIds = new Set(stored.map(String));
    } catch {
      appState.hiddenFieldIds = new Set();
    }
    appState.fieldVisibilityLoaded = true;
  }
  const fieldIds = new Set(appState.fields.map((field) => field.field_id));
  appState.hiddenFieldIds = new Set([...appState.hiddenFieldIds].filter((fieldId) => fieldIds.has(fieldId)));
  if (appState.fields.length && visibleFields().length === 0) appState.hiddenFieldIds.delete(appState.fields[0].field_id);
  saveFieldVisibility();
}

function saveFieldVisibility() {
  try {
    localStorage.setItem(HIDDEN_FIELDS_STORAGE_KEY, JSON.stringify([...appState.hiddenFieldIds]));
  } catch {
    // 浏览器禁止本地存储时，当前会话中的显示设置仍然有效。
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload;
}

function toast(message, type = "success") {
  const element = document.createElement("div");
  element.className = `toast ${type === "error" ? "error" : ""}`;
  element.textContent = message;
  $("#toastRegion").appendChild(element);
  setTimeout(() => element.remove(), 3600);
}

function showModal({ eyebrow = "数据工具", title, body, footer = "", wide = false }) {
  $("#modalEyebrow").textContent = eyebrow;
  $("#modalTitle").textContent = title;
  $("#modalBody").innerHTML = body;
  $("#modalFooter").innerHTML = footer;
  $("#modal").style.width = wide ? "min(1120px, 100%)" : "min(900px, 100%)";
  $("#modalBackdrop").classList.remove("hidden");
  $("#modalBackdrop").setAttribute("aria-hidden", "false");
}

function closeModal() {
  $("#modalBackdrop").classList.add("hidden");
  $("#modalBackdrop").setAttribute("aria-hidden", "true");
}

async function loadState() {
  const payload = await api("/api/state");
  appState.fields = payload.fields;
  appState.records = payload.records;
  appState.status = payload.status;
  loadFieldVisibility();
  appState.selected.clear();
  populateQuickFilters();
  updateStatus();
  applyFilters();
}

function getValue(record, fieldId) {
  return String(record.data[fieldId] ?? "");
}

function getNamedValue(record, ...names) {
  const fieldId = fieldIdByName(...names);
  return fieldId ? getValue(record, fieldId) : "";
}

function uniqueValuesInAppearanceOrder(fieldId, records = appState.records, limit = 1000) {
  return [...new Set(records.filter((record) => !record.deleted).map((record) => getValue(record, fieldId)).filter(Boolean))]
    .slice(0, limit);
}

function organizationSystemValues(records = appState.records) {
  return uniqueValuesInAppearanceOrder("organization_system", records);
}

function recordsInOrganizationSystemOrder(records) {
  return records;
}

function fillSelect(select, values, placeholder) {
  const current = select.value;
  select.innerHTML = "";
  const first = document.createElement("option");
  first.value = "";
  first.textContent = placeholder;
  select.appendChild(first);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  if (values.includes(current)) select.value = current;
}

function populateQuickFilters() {
  fillSelect($("#systemFilter"), organizationSystemValues(), "全部组织体系");
  populateTypeFilter();
}

function populateTypeFilter() {
  const system = $("#systemFilter").value;
  const relatedRecords = system
    ? appState.records.filter((record) => !record.deleted && getValue(record, "organization_system") === system)
    : recordsInOrganizationSystemOrder(appState.records);
  const placeholder = system ? `全部机构类型（${system}）` : "全部机构类型";
  fillSelect($("#typeFilter"), uniqueValuesInAppearanceOrder("institution_type", relatedRecords), placeholder);
  $("#typeFilterHint").textContent = system
    ? `仅列出“${system}”下的机构类型`
    : "选择组织体系后，机构类型将自动缩小范围";
}

function matchesRule(record, rule) {
  const value = getValue(record, rule.fieldId).toLocaleLowerCase("zh-CN");
  const target = String(rule.value ?? "").toLocaleLowerCase("zh-CN");
  switch (rule.operator) {
    case "contains": return value.includes(target);
    case "not_contains": return !value.includes(target);
    case "equals": return value === target;
    case "not_equals": return value !== target;
    case "starts": return value.startsWith(target);
    case "ends": return value.endsWith(target);
    case "empty": return value.trim() === "";
    case "not_empty": return value.trim() !== "";
    default: return true;
  }
}

function applyFilters(options = {}) {
  const query = $("#globalSearch").value.trim().toLocaleLowerCase("zh-CN");
  const system = $("#systemFilter").value;
  const type = $("#typeFilter").value;
  const match = $("#matchFilter").value;
  const link = $("#linkFilter").value;
  const showDeleted = $("#showDeleted").checked;

  appState.filtered = appState.records.filter((record) => {
    if (record.deleted !== showDeleted) return false;
    if (query && !appState.fields.some((field) => getValue(record, field.field_id).toLocaleLowerCase("zh-CN").includes(query))) return false;
    if (system && getValue(record, "organization_system") !== system) return false;
    if (type && getValue(record, "institution_type") !== type) return false;
    const hasScript = Boolean(getValue(record, "script_sequence"));
    if (match === "有" && !hasScript) return false;
    if (match === "无" && hasScript) return false;
    const official = getNamedValue(record, "官网链接");
    const leader = getNamedValue(record, "领导链接", "依据链接");
    if (link === "both" && !(official && leader)) return false;
    if (link === "missing-leader" && leader) return false;
    if (link === "missing-official" && official) return false;
    if (link === "none" && (official || leader)) return false;
    if (appState.advancedRules.length) {
      const results = appState.advancedRules.map((rule) => matchesRule(record, rule));
      if (appState.advancedLogic === "and" ? !results.every(Boolean) : !results.some(Boolean)) return false;
    }
    return true;
  });

  if (appState.sort.fieldId) {
    const factor = appState.sort.direction === "asc" ? 1 : -1;
    appState.filtered.sort((a, b) => getValue(a, appState.sort.fieldId).localeCompare(getValue(b, appState.sort.fieldId), "zh-CN") * factor);
  }
  if (options.resetScroll) $(".table-wrap").scrollTop = 0;
  updateMetrics();
  renderTable();
  updateSelectionState();
}

function updateStatus() {
  const external = appState.status.external_change;
  $("#externalBanner").classList.toggle("hidden", !external);
  $("#fileStatus").classList.toggle("alert", external);
  $("#fileStatus").innerHTML = `<span class="status-dot"></span>${external ? "检测到外部更新" : "文件一致"}`;
  $("#draftStatus").textContent = `${formatNumber(appState.status.pending_count || 0)} 项未发布`;
  $("#publishBtn").disabled = external;
}

function updateMetrics() {
  const active = appState.records.filter((record) => !record.deleted);
  const filtered = appState.filtered;
  const yes = filtered.filter((record) => Boolean(getValue(record, "script_sequence"))).length;
  const missing = filtered.filter((record) => !getNamedValue(record, "领导链接", "依据链接")).length;
  const deleted = appState.records.filter((record) => record.deleted).length;
  $("#metricTotal").textContent = formatNumber(active.length);
  $("#metricFiltered").textContent = formatNumber(filtered.length);
  $("#metricMatchRate").textContent = filtered.length ? `${(yes / filtered.length * 100).toFixed(1)}%` : "0.0%";
  $("#metricMatchDetail").textContent = `${formatNumber(yes)} 条已匹配`;
  $("#metricMissing").textContent = formatNumber(missing);
  $("#sidebarFiltered").textContent = formatNumber(filtered.length);
  $("#sidebarDeleted").textContent = formatNumber(deleted);
}

function renderTableHead() {
  const head = $("#tableHead");
  head.innerHTML = "";
  const row = document.createElement("tr");
  const selectTh = document.createElement("th");
  const allCheckbox = document.createElement("input");
  allCheckbox.type = "checkbox";
  allCheckbox.title = "选择当前全部结果";
  allCheckbox.addEventListener("change", () => {
    appState.filtered.forEach((record) => allCheckbox.checked ? appState.selected.add(record.record_id) : appState.selected.delete(record.record_id));
    renderTable();
    updateSelectionState();
  });
  selectTh.appendChild(allCheckbox);
  row.appendChild(selectTh);

  const numberTh = document.createElement("th");
  numberTh.className = "row-number";
  numberTh.textContent = "序号";
  row.appendChild(numberTh);

  visibleFields().forEach((field) => {
    const th = document.createElement("th");
    th.dataset.fieldId = field.field_id;
    th.title = "单击排序";
    th.textContent = field.export_name;
    if (appState.sort.fieldId === field.field_id) th.textContent += appState.sort.direction === "asc" ? " ↑" : " ↓";
    th.addEventListener("click", () => {
      if (appState.sort.fieldId === field.field_id) appState.sort.direction = appState.sort.direction === "asc" ? "desc" : "asc";
      else appState.sort = { fieldId: field.field_id, direction: "asc" };
      applyFilters({ resetScroll: true });
    });
    row.appendChild(th);
  });
  head.appendChild(row);
}

function renderCell(td, record, field) {
  const value = getValue(record, field.field_id);
  td.dataset.fieldId = field.field_id;
  td.className = "editable";
  td.title = value || "双击编辑空值";
  if (field.field_id === "script_sequence" && value) {
    const pill = document.createElement("span");
    pill.className = "match-pill yes";
    pill.textContent = value;
    td.appendChild(pill);
  } else if (field.is_link && value) {
    const wrap = document.createElement("div");
    wrap.className = "link-cell";
    const text = document.createElement("span");
    text.className = "link-text";
    text.textContent = value;
    wrap.appendChild(text);
    if (/^https?:\/\//i.test(value)) {
      const link = document.createElement("a");
      link.className = "external-link";
      link.href = value;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.title = "在新标签页打开";
      link.innerHTML = icon("external");
      link.addEventListener("dblclick", (event) => event.stopPropagation());
      wrap.appendChild(link);
    }
    td.appendChild(wrap);
  } else {
    td.textContent = value;
  }
  td.addEventListener("dblclick", () => beginCellEdit(td, record, field));
}

function calculateVirtualWindow(totalRows, firstVisibleRow, visibleRowCount, windowSize = VIRTUAL_ROW_LIMIT) {
  if (totalRows <= 0) return { start: 0, end: 0 };
  const size = Math.min(Math.max(1, windowSize), totalRows);
  const visibleCount = Math.min(Math.max(1, visibleRowCount), size);
  const maxStart = Math.max(0, totalRows - size);
  const centeredStart = firstVisibleRow - Math.floor((size - visibleCount) / 2);
  const start = Math.min(maxStart, Math.max(0, centeredStart));
  return { start, end: start + size };
}

function appendVirtualSpacer(fragment, height, columnCount) {
  if (height <= 0) return;
  const row = document.createElement("tr");
  row.className = "virtual-spacer";
  row.setAttribute("aria-hidden", "true");
  const cell = document.createElement("td");
  cell.colSpan = columnCount;
  cell.style.height = `${height}px`;
  row.appendChild(cell);
  fragment.appendChild(row);
}

function renderVirtualRows(force = false) {
  const body = $("#tableBody");
  const tableWrap = $(".table-wrap");
  const shownFields = visibleFields();
  const totalRows = appState.filtered.length;
  const visibleRowCount = Math.max(1, Math.ceil(tableWrap.clientHeight / TABLE_ROW_HEIGHT));
  const firstVisibleRow = Math.min(
    Math.max(0, totalRows - 1),
    Math.max(0, Math.floor((tableWrap.scrollTop - TABLE_HEADER_HEIGHT) / TABLE_ROW_HEIGHT)),
  );
  const lastVisibleRow = Math.min(totalRows, firstVisibleRow + visibleRowCount);
  const current = appState.virtualWindow;
  const buffer = Math.max(10, Math.floor((VIRTUAL_ROW_LIMIT - visibleRowCount) / 4));
  const viewportInsideCurrentWindow = current.start >= 0
    && (current.start === 0 || firstVisibleRow >= current.start + buffer)
    && (current.end === totalRows || lastVisibleRow <= current.end - buffer);
  if (!force && viewportInsideCurrentWindow) return;

  const next = calculateVirtualWindow(totalRows, firstVisibleRow, visibleRowCount);
  appState.virtualWindow.start = next.start;
  appState.virtualWindow.end = next.end;
  const fragment = document.createDocumentFragment();
  const columnCount = shownFields.length + 2;
  appendVirtualSpacer(fragment, next.start * TABLE_ROW_HEIGHT, columnCount);
  appState.filtered.slice(next.start, next.end).forEach((record, offset) => {
    const tr = document.createElement("tr");
    tr.dataset.recordId = record.record_id;
    tr.setAttribute("aria-rowindex", String(next.start + offset + 2));
    tr.classList.toggle("selected", appState.selected.has(record.record_id));
    tr.classList.toggle("deleted", record.deleted);
    const selectTd = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = appState.selected.has(record.record_id);
    checkbox.addEventListener("change", () => {
      checkbox.checked ? appState.selected.add(record.record_id) : appState.selected.delete(record.record_id);
      tr.classList.toggle("selected", checkbox.checked);
      updateSelectionState();
    });
    selectTd.appendChild(checkbox);
    tr.appendChild(selectTd);
    const numberTd = document.createElement("td");
    numberTd.className = "row-number";
    numberTd.textContent = String(record.sort_order + 1);
    tr.appendChild(numberTd);
    shownFields.forEach((field) => {
      const td = document.createElement("td");
      renderCell(td, record, field);
      tr.appendChild(td);
    });
    fragment.appendChild(tr);
  });
  appendVirtualSpacer(fragment, (totalRows - next.end) * TABLE_ROW_HEIGHT, columnCount);
  body.replaceChildren(fragment);

  const renderedCount = next.end - next.start;
  const renderedRange = renderedCount ? `当前加载第 ${formatNumber(next.start + 1)}–${formatNumber(next.end)} 行` : "当前无数据行";
  $("#rangeText").textContent = `共 ${formatNumber(totalRows)} 条记录 · ${renderedRange} · 显示 ${shownFields.length}/${appState.fields.length} 个字段`;
}

function renderTable() {
  renderTableHead();
  const shownFields = visibleFields();
  const minimumWidth = 96 + shownFields.reduce((total, field) => {
    if (field.field_id === "institution_name") return total + 300;
    if (field.field_id === "institution_type") return total + 230;
    if (field.is_link) return total + 230;
    if (field.field_id === "organization_system") return total + 130;
    if (field.field_id === "script_sequence") return total + 90;
    return total + 160;
  }, 0);
  $("#dataTable").style.minWidth = `max(100%, ${minimumWidth}px)`;
  $("#visibleFieldCount").textContent = `${shownFields.length}/${appState.fields.length}`;
  if (appState.virtualWindow.frameId) cancelAnimationFrame(appState.virtualWindow.frameId);
  appState.virtualWindow = { start: -1, end: -1, frameId: 0 };
  renderVirtualRows(true);
  $("#emptyState").classList.toggle("hidden", appState.filtered.length > 0);
}

function updateSelectionState() {
  const count = appState.selected.size;
  $("#sidebarSelected").textContent = formatNumber(count);
  $("#duplicateBtn").disabled = count !== 1;
  $("#deleteBtn").disabled = count === 0 || $("#showDeleted").checked;
  $("#restoreBtn").classList.toggle("hidden", !$("#showDeleted").checked);
  $("#restoreBtn").disabled = count === 0 || !$("#showDeleted").checked;
  $("#bulkBtn").disabled = count === 0 && appState.filtered.length === 0;
}

function beginCellEdit(td, record, field) {
  if (record.deleted || td.querySelector("input")) return;
  const oldValue = getValue(record, field.field_id);
  td.innerHTML = "";
  const input = document.createElement("input");
  input.className = "cell-editor";
  input.value = oldValue;
  td.appendChild(input);
  input.focus();
  input.select();
  let finished = false;
  const finish = async (save) => {
    if (finished) return;
    finished = true;
    if (save && input.value !== oldValue) {
      try {
        const result = await api(`/api/records/${record.record_id}`, { method: "PATCH", body: { field_id: field.field_id, value: input.value } });
        if (result.changed) {
          record.data[field.field_id] = result.value;
          appState.status.pending_count = (appState.status.pending_count || 0) + 1;
          updateStatus();
          toast("修改已保存到草稿");
        }
      } catch (error) {
        toast(error.message, "error");
      }
    }
    applyFilters();
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); finish(true); }
    if (event.key === "Escape") { event.preventDefault(); finish(false); }
  });
  input.addEventListener("blur", () => finish(true));
}

function clearFilters() {
  $("#globalSearch").value = "";
  $("#systemFilter").value = "";
  $("#typeFilter").value = "";
  $("#matchFilter").value = "";
  $("#linkFilter").value = "";
  appState.advancedRules = [];
  appState.advancedLogic = "and";
  $("#ruleCount").textContent = "0";
  populateTypeFilter();
  applyFilters({ resetScroll: true });
}

function fieldOptions(selected = "") {
  return appState.fields.map((field) => `<option value="${escapeHtml(field.field_id)}" ${field.field_id === selected ? "selected" : ""}>${escapeHtml(field.export_name)}</option>`).join("");
}

function openAdvancedFilters() {
  showModal({
    eyebrow: "组合查询",
    title: "高级筛选",
    body: `
      <div class="form-field" style="max-width:220px;margin-bottom:16px"><label>条件关系</label><select id="filterLogic"><option value="and" ${appState.advancedLogic === "and" ? "selected" : ""}>全部满足（并且）</option><option value="or" ${appState.advancedLogic === "or" ? "selected" : ""}>任一满足（或者）</option></select></div>
      <div id="filterRules"></div>
      <button id="addRuleBtn" class="button secondary">${icon("plus")}增加条件</button>`,
    footer: `<button id="cancelFilterBtn" class="button secondary">取消</button><button id="applyFilterBtn" class="button primary">应用筛选</button>`,
  });
  const container = $("#filterRules");
  const sourceRules = appState.advancedRules.length ? appState.advancedRules : [{ fieldId: appState.fields[0]?.field_id || "", operator: "contains", value: "" }];
  sourceRules.forEach((rule) => appendFilterRule(container, rule));
  $("#addRuleBtn").addEventListener("click", () => appendFilterRule(container, { fieldId: appState.fields[0].field_id, operator: "contains", value: "" }));
  $("#cancelFilterBtn").addEventListener("click", closeModal);
  $("#applyFilterBtn").addEventListener("click", () => {
    appState.advancedLogic = $("#filterLogic").value;
    appState.advancedRules = [...container.querySelectorAll(".filter-rule")].map((row) => ({
      fieldId: row.querySelector(".rule-field").value,
      operator: row.querySelector(".rule-operator").value,
      value: row.querySelector(".rule-value").value,
    }));
    $("#ruleCount").textContent = String(appState.advancedRules.length);
    closeModal();
    applyFilters({ resetScroll: true });
  });
}

function appendFilterRule(container, rule) {
  const row = document.createElement("div");
  row.className = "filter-rule";
  row.innerHTML = `
    <select class="rule-field">${fieldOptions(rule.fieldId)}</select>
    <select class="rule-operator">
      <option value="contains">包含</option><option value="not_contains">不包含</option><option value="equals">等于</option><option value="not_equals">不等于</option><option value="starts">开头是</option><option value="ends">结尾是</option><option value="empty">为空</option><option value="not_empty">非空</option>
    </select>
    <input class="rule-value" value="${escapeHtml(rule.value)}" placeholder="条件值">
    <button class="icon-button remove-rule" title="删除条件">${icon("x")}</button>`;
  row.querySelector(".rule-operator").value = rule.operator;
  const refreshValueState = () => row.querySelector(".rule-value").disabled = ["empty", "not_empty"].includes(row.querySelector(".rule-operator").value);
  row.querySelector(".rule-operator").addEventListener("change", refreshValueState);
  row.querySelector(".remove-rule").addEventListener("click", () => row.remove());
  refreshValueState();
  container.appendChild(row);
}

async function addRecord() {
  try {
    const record = await api("/api/records", { method: "POST", body: {} });
    await loadState();
    renderTable();
    const newRecord = recordById(record.record_id);
    if (newRecord) appState.selected.add(newRecord.record_id);
    updateSelectionState();
    toast("已新增空记录，请补充机构名称后再发布");
  } catch (error) { toast(error.message, "error"); }
}

async function duplicateRecord() {
  if (appState.selected.size !== 1) return;
  try {
    const recordId = [...appState.selected][0];
    await api(`/api/records/${recordId}/duplicate`, { method: "POST", body: {} });
    await loadState();
    toast("已复制记录");
  } catch (error) { toast(error.message, "error"); }
}

async function changeDeleted(deleted) {
  if (!appState.selected.size) return;
  const label = deleted ? "删除" : "恢复";
  if (!confirm(`确认${label}选中的 ${appState.selected.size} 条记录？`)) return;
  try {
    for (const recordId of appState.selected) await api(`/api/records/${recordId}/${deleted ? "delete" : "restore"}`, { method: "POST", body: {} });
    await loadState();
    toast(`已${label}记录`);
  } catch (error) { toast(error.message, "error"); }
}

function openBulkEdit() {
  const defaultScope = appState.selected.size ? "selected" : "filtered";
  showModal({
    eyebrow: "批量操作",
    title: "批量修改字段值",
    body: `<div class="form-grid"><div class="form-field"><label>作用范围</label><select id="bulkScope"><option value="selected" ${defaultScope === "selected" ? "selected" : ""}>已选择记录（${appState.selected.size}）</option><option value="filtered" ${defaultScope === "filtered" ? "selected" : ""}>当前筛选结果（${appState.filtered.length}）</option></select></div><div class="form-field"><label>目标字段</label><select id="bulkField">${fieldOptions()}</select></div><div class="form-field" style="grid-column:1/-1"><label>统一填写值</label><input id="bulkValue" placeholder="留空表示批量清空"></div></div>`,
    footer: `<button id="cancelBulk" class="button secondary">取消</button><button id="applyBulk" class="button primary">确认修改</button>`,
  });
  $("#cancelBulk").addEventListener("click", closeModal);
  $("#applyBulk").addEventListener("click", async () => {
    const ids = $("#bulkScope").value === "selected" ? [...appState.selected] : appState.filtered.map((record) => record.record_id);
    if (!ids.length) return toast("没有可修改的记录", "error");
    if (!confirm(`确认批量修改 ${ids.length} 条记录？`)) return;
    try {
      const result = await api("/api/bulk", { method: "POST", body: { record_ids: ids, field_id: $("#bulkField").value, value: $("#bulkValue").value } });
      closeModal();
      await loadState();
      toast(`已修改 ${result.changed_count} 条记录`);
    } catch (error) { toast(error.message, "error"); }
  });
}

function openFieldManager() {
  showModal({
    eyebrow: "结构管理",
    title: "字段显示与名称管理",
    body: `<div class="field-manager-summary"><div><strong id="fieldVisibilitySummary"></strong><span>显示设置仅保存在当前浏览器，不会修改 TXT 数据。</span></div><button id="showAllFields" class="button secondary">全部显示</button></div><div class="banner warning field-rename-warning"><div><strong>改名会同步写入 TXT 表头</strong><span>内部字段 ID 保持不变，外部重建后仍会恢复您的字段名称。</span></div></div><div class="field-list-header" aria-hidden="true"><span>显示</span><span>内部字段</span><span>来源名称</span><span>导出名称</span><span>操作</span></div><div id="fieldRows">${appState.fields.map((field) => `<div class="field-row"><label class="field-visibility-label"><input class="field-visibility" type="checkbox" data-field-id="${escapeHtml(field.field_id)}" ${appState.hiddenFieldIds.has(field.field_id) ? "" : "checked"}><span class="sr-only">显示${escapeHtml(field.export_name)}</span></label><code>${escapeHtml(field.field_id)}</code><span>${escapeHtml(field.source_name)}</span><input class="field-name-input" data-field-id="${escapeHtml(field.field_id)}" data-old="${escapeHtml(field.export_name)}" value="${escapeHtml(field.export_name)}"><button class="button secondary save-field" data-field-id="${escapeHtml(field.field_id)}">保存</button></div>`).join("")}</div>`,
    footer: `<button id="closeFields" class="button primary">完成</button>`,
  });
  const updateVisibilityControls = () => {
    const count = visibleFields().length;
    $("#fieldVisibilitySummary").textContent = `当前显示 ${count}/${appState.fields.length} 个字段`;
    document.querySelectorAll(".field-visibility").forEach((checkbox) => {
      checkbox.checked = !appState.hiddenFieldIds.has(checkbox.dataset.fieldId);
      checkbox.disabled = count === 1 && checkbox.checked;
    });
    $("#showAllFields").disabled = count === appState.fields.length;
  };
  document.querySelectorAll(".field-visibility").forEach((checkbox) => checkbox.addEventListener("change", () => {
    if (checkbox.checked) appState.hiddenFieldIds.delete(checkbox.dataset.fieldId);
    else appState.hiddenFieldIds.add(checkbox.dataset.fieldId);
    if (visibleFields().length === 0) {
      appState.hiddenFieldIds.delete(checkbox.dataset.fieldId);
      toast("至少需要显示一个字段", "error");
    } else {
      saveFieldVisibility();
      renderTable();
    }
    updateVisibilityControls();
  }));
  $("#showAllFields").addEventListener("click", () => {
    appState.hiddenFieldIds.clear();
    saveFieldVisibility();
    renderTable();
    updateVisibilityControls();
    toast("已显示全部字段");
  });
  $("#closeFields").addEventListener("click", closeModal);
  document.querySelectorAll(".save-field").forEach((button) => button.addEventListener("click", async () => {
    const input = document.querySelector(`.field-name-input[data-field-id="${button.dataset.fieldId}"]`);
    try {
      const result = await api(`/api/fields/${button.dataset.fieldId}`, { method: "PATCH", body: { export_name: input.value } });
      if (result.changed) {
        fieldById(button.dataset.fieldId).export_name = result.export_name;
        input.dataset.old = result.export_name;
        appState.status.pending_count++;
        updateStatus();
        renderTable();
        toast("字段真实名称已保存到草稿");
      }
    } catch (error) { toast(error.message, "error"); input.value = input.dataset.old; }
  }));
  updateVisibilityControls();
}

function cleanTableText(value) {
  return String(value ?? "").replace(/[\t\r\n]+/g, " ").trim();
}

function buildVisibleTableText() {
  const fields = visibleFields();
  const lines = [fields.map((field) => cleanTableText(field.export_name)).join("\t")];
  appState.filtered.forEach((record) => {
    lines.push(fields.map((field) => cleanTableText(getValue(record, field.field_id))).join("\t"));
  });
  return lines.join("\r\n");
}

async function writeClipboardText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("浏览器未允许访问剪贴板");
}

async function copyVisibleTable() {
  try {
    await writeClipboardText(buildVisibleTableText());
    toast(`已复制 ${formatNumber(appState.filtered.length)} 条记录、${visibleFields().length} 个字段（含表头）`);
  } catch (error) {
    toast(`复制失败：${error.message}`, "error");
  }
}

function aggregate(records, groupFieldId, secondFieldId, metric, targetFieldId) {
  const groups = new Map();
  records.forEach((record) => {
    const first = getValue(record, groupFieldId) || "（空值）";
    const second = secondFieldId ? (getValue(record, secondFieldId) || "（空值）") : "";
    const key = `${first}\u0000${second}`;
    if (!groups.has(key)) groups.set(key, { first, second, rows: [], values: new Set() });
    const group = groups.get(key);
    group.rows.push(record);
    group.values.add(getValue(record, targetFieldId));
  });
  return [...groups.values()].map((group) => {
    let value = group.rows.length;
    if (metric === "unique") value = [...group.values].filter(Boolean).length;
    if (metric === "empty") value = group.rows.filter((record) => !getValue(record, targetFieldId)).length;
    if (metric === "not_empty") value = group.rows.filter((record) => getValue(record, targetFieldId)).length;
    return { ...group, value };
  }).sort((a, b) => b.value - a.value || a.first.localeCompare(b.first, "zh-CN"));
}

function openStats() {
  showModal({
    eyebrow: "统计分析",
    title: "自定义分组与快速图表",
    wide: true,
    body: `<div class="chart-layout"><div class="chart-controls"><div class="form-field"><label>第一分组字段</label><select id="groupField">${fieldOptions("organization_system")}</select></div><div class="form-field"><label>第二分组字段</label><select id="secondGroup"><option value="">不使用</option>${fieldOptions()}</select></div><div class="form-field"><label>统计方式</label><select id="metricType"><option value="count">记录数</option><option value="unique">唯一值数量</option><option value="empty">空值数量</option><option value="not_empty">非空值数量</option></select></div><div class="form-field"><label>统计字段</label><select id="targetField">${fieldOptions("institution_name")}</select></div><small>统计范围：当前筛选结果 ${formatNumber(appState.filtered.length)} 条</small></div><div><div id="barChart" class="bar-chart"></div><table class="pivot-table"><thead><tr><th>第一分组</th><th id="secondHeader">第二分组</th><th>统计值</th><th>占比</th></tr></thead><tbody id="pivotBody"></tbody></table></div></div>`,
    footer: `<button id="closeStats" class="button primary">完成</button>`,
  });
  const refresh = () => {
    const rows = aggregate(appState.filtered, $("#groupField").value, $("#secondGroup").value, $("#metricType").value, $("#targetField").value);
    const max = Math.max(...rows.map((row) => row.value), 1);
    $("#barChart").innerHTML = rows.slice(0, 15).map((row) => `<div class="bar-row" title="${escapeHtml(row.first)} ${escapeHtml(row.second)}"><span class="bar-label">${escapeHtml(row.second ? `${row.first} · ${row.second}` : row.first)}</span><div class="bar-track"><div class="bar-fill" style="width:${row.value / max * 100}%"></div></div><span class="bar-value">${formatNumber(row.value)}</span></div>`).join("");
    const total = rows.reduce((sum, row) => sum + row.value, 0) || 1;
    $("#pivotBody").innerHTML = rows.slice(0, 200).map((row) => `<tr><td>${escapeHtml(row.first)}</td><td>${escapeHtml(row.second || "—")}</td><td>${formatNumber(row.value)}</td><td>${(row.value / total * 100).toFixed(1)}%</td></tr>`).join("");
  };
  ["#groupField", "#secondGroup", "#metricType", "#targetField"].forEach((selector) => $(selector).addEventListener("change", refresh));
  $("#closeStats").addEventListener("click", closeModal);
  refresh();
}

async function openHistory() {
  try {
    const payload = await api("/api/history?limit=300");
    const actionNames = { edit: "修改单元格", create: "新增记录", duplicate: "复制记录", delete: "删除记录", restore: "恢复记录", rename_field: "字段改名", undo: "撤销", publish: "发布", reconcile: "同步重放" };
    const body = payload.history.length ? `<div class="history-list">${payload.history.map((item) => {
      const field = fieldById(item.field_id);
      const oldText = item.old_value ? safeJsonDisplay(item.old_value) : "";
      const newText = item.new_value ? safeJsonDisplay(item.new_value) : "";
      const description = item.details || (field ? `${field.export_name}：${oldText} → ${newText}` : newText || oldText || "—");
      return `<article class="history-item"><header><strong>${escapeHtml(actionNames[item.action] || item.action)}${item.undone ? "（已撤销）" : ""}</strong><span>${escapeHtml(item.created_at)} · ${item.published ? "已发布" : "草稿"}</span></header><p>${escapeHtml(description)}</p></article>`;
    }).join("")}</div>` : "<p>尚无修改历史。</p>";
    showModal({ eyebrow: "审计记录", title: "最近修改历史", body, footer: `<button id="closeHistory" class="button primary">完成</button>` });
    $("#closeHistory").addEventListener("click", closeModal);
  } catch (error) { toast(error.message, "error"); }
}

function safeJsonDisplay(value) {
  try { return JSON.stringify(JSON.parse(value), null, 0); }
  catch { return String(value); }
}

async function undoLast() {
  try {
    const result = await api("/api/undo", { method: "POST", body: {} });
    if (!result.changed) return toast("没有可撤销的修改");
    await loadState();
    toast("已撤销最近修改");
  } catch (error) { toast(error.message, "error"); }
}

async function publish() {
  if (appState.status.external_change) return toast("请先同步外部更新", "error");
  if (!confirm(`确认把当前草稿发布到机构主表.txt？发布前会自动备份。`)) return;
  try {
    const result = await api("/api/publish", { method: "POST", body: {} });
    await loadState();
    toast(`发布完成：${formatNumber(result.row_count)} 条记录`);
  } catch (error) { toast(error.message, "error"); }
}

async function reconcile() {
  if (!confirm("确认同步外部生成的新文件？无冲突的人工修订会自动重新应用。")) return;
  try {
    const result = await api("/api/reconcile", { method: "POST", body: {} });
    await loadState();
    toast(`同步完成：匹配 ${formatNumber(result.matched_count)} 条，冲突 ${formatNumber(result.conflict_count)} 条`);
  } catch (error) { toast(error.message, "error"); }
}

function exportFiltered() {
  const rows = appState.filtered.filter((record) => !record.deleted);
  const lines = [appState.fields.map((field) => cleanTableText(field.export_name)).join("\t")];
  rows.forEach((record) => lines.push(appState.fields.map((field) => cleanTableText(getValue(record, field.field_id))).join("\t")));
  const blob = new Blob(["\ufeff" + lines.join("\r\n") + "\r\n"], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `机构全量表-筛选结果-${new Date().toISOString().slice(0, 10)}.txt`;
  link.click();
  URL.revokeObjectURL(url);
  toast(`已导出 ${formatNumber(rows.length)} 条筛选结果`);
}

function bindEvents() {
  let searchTimer;
  $("#globalSearch").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => applyFilters({ resetScroll: true }), 120); });
  $("#systemFilter").addEventListener("change", () => {
    populateTypeFilter();
    appState.selected.clear();
    applyFilters({ resetScroll: true });
  });
  ["#typeFilter", "#matchFilter", "#linkFilter", "#showDeleted"].forEach((selector) => $(selector).addEventListener("change", () => { appState.selected.clear(); applyFilters({ resetScroll: true }); }));
  $(".table-wrap").addEventListener("scroll", () => {
    if (appState.virtualWindow.frameId) return;
    appState.virtualWindow.frameId = requestAnimationFrame(() => {
      appState.virtualWindow.frameId = 0;
      renderVirtualRows();
    });
  }, { passive: true });
  $("#clearFiltersBtn").addEventListener("click", clearFilters);
  $("#advancedFilterBtn").addEventListener("click", openAdvancedFilters);
  $("#addBtn").addEventListener("click", addRecord);
  $("#duplicateBtn").addEventListener("click", duplicateRecord);
  $("#deleteBtn").addEventListener("click", () => changeDeleted(true));
  $("#restoreBtn").addEventListener("click", () => changeDeleted(false));
  $("#bulkBtn").addEventListener("click", openBulkEdit);
  $("#fieldBtn").addEventListener("click", openFieldManager);
  $("#copyTableBtn").addEventListener("click", copyVisibleTable);
  $("#statsBtn").addEventListener("click", openStats);
  $("#historyBtn").addEventListener("click", openHistory);
  $("#undoBtn").addEventListener("click", undoLast);
  $("#publishBtn").addEventListener("click", publish);
  $("#reconcileBtn").addEventListener("click", reconcile);
  $("#exportBtn").addEventListener("click", exportFiltered);
  $("#closeModal").addEventListener("click", closeModal);
  $("#modalBackdrop").addEventListener("click", (event) => { if (event.target === $("#modalBackdrop")) closeModal(); });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("#globalSearch").focus(); }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) { event.preventDefault(); undoLast(); }
    if (event.key === "Escape" && !$("#modalBackdrop").classList.contains("hidden")) closeModal();
  });
}

async function initialize() {
  bindEvents();
  try {
    await loadState();
    setTimeout(() => { $("#loading").classList.add("fade"); setTimeout(() => $("#loading").remove(), 260); }, 120);
  } catch (error) {
    $("#loading").innerHTML = `<strong>工作台启动失败</strong><span>${escapeHtml(error.message)}</span>`;
  }
}

initialize();
