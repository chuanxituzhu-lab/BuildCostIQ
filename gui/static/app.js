const $ = (id) => document.getElementById(id);

const state = {
  auth: { token: sessionStorage.getItem("buildcostiq_token") || "", user: null },
  sample: null,
  workspace: null,
  view: "overview",
  projectId: "",
  sourceId: "",
  projectName: "",
  sourceName: "",
  fileName: "",
  boqRows: [],
  boqResult: null,
  planDraft: [],
  planResult: null,
  reviewResult: null,
  dashboard: null,
  sources: [],
  connectors: [],
  recognizers: [],
  intakeReports: [],
};

async function apiJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.auth.token) headers.set("Authorization", `Bearer ${state.auth.token}`);
  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`);
  return data;
}

function setError(message = "") {
  $("error").textContent = message;
}

function setAuthMessage(message = "") {
  $("authMessage").textContent = message;
}

function isManager() {
  return state.auth.user?.role === "project_manager";
}

function showAuth(message = "") {
  $("authShell").hidden = false;
  $("workspaceShell").hidden = true;
  $("userSession").hidden = true;
  setAuthMessage(message);
}

function showWorkspace(user) {
  state.auth.user = user;
  $("authShell").hidden = true;
  $("workspaceShell").hidden = false;
  $("userSession").hidden = false;
  $("userRole").textContent = `${user.role_label} · ${user.username}`;
  $("controlTab").hidden = !isManager();
  $("workspaceTitle").textContent = isManager() ? "项目经理工作台" : "造价人员工作台";
}

async function finishAuth(response) {
  state.auth.token = response.token;
  state.auth.user = response.user;
  sessionStorage.setItem("buildcostiq_token", response.token);
  showWorkspace(response.user);
  setAuthMessage("");
  await loadDemo();
}

async function submitLogin(event) {
  event.preventDefault();
  try {
    const response = await apiJson("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("loginUsername").value, password: $("loginPassword").value }),
    });
    await finishAuth(response);
  } catch (error) {
    setAuthMessage(error.message);
  }
}

async function submitRegister(event) {
  event.preventDefault();
  try {
    const response = await apiJson("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: $("registerUsername").value,
        password: $("registerPassword").value,
        role: $("registerRole").value,
      }),
    });
    await finishAuth(response);
  } catch (error) {
    setAuthMessage(error.message);
  }
}

async function logout() {
  try { await apiJson("/api/auth/logout", { method: "POST" }); } catch (_) { /* local session cleanup still wins */ }
  state.auth = { token: "", user: null };
  sessionStorage.removeItem("buildcostiq_token");
  showAuth("已退出登录");
}

async function restoreSession() {
  if (!state.auth.token) return false;
  try {
    const response = await apiJson("/api/auth/me");
    showWorkspace(response.user);
    await loadDemo();
    return true;
  } catch (_) {
    state.auth = { token: "", user: null };
    sessionStorage.removeItem("buildcostiq_token");
    return false;
  }
}

function draftFromSample(rows) {
  if (!Array.isArray(rows) || rows.length < 2) return [];
  const headers = rows[0].map((value) => String(value || "").trim());
  const find = (...names) => names.map((name) => headers.indexOf(name)).find((index) => index >= 0);
  const code = find("项目编码", "编码", "清单编码");
  const name = find("项目名称", "名称", "项目特征");
  const unit = find("计量单位", "单位");
  const quantity = find("工程量", "数量");
  if ([code, name, unit, quantity].some((index) => index === undefined)) return [];
  return rows.slice(1).filter((row) => row[code]).map((row) => ({
    code: String(row[code] ?? "").trim(),
    name: String(row[name] ?? "").trim(),
    unit: String(row[unit] ?? "").trim(),
    quantity: row[quantity] ?? "",
  }));
}

function draftFromItems(items) {
  return (items || []).map((item) => ({
    code: item.code || "",
    name: item.name || "",
    unit: item.unit || "",
    quantity: item.quantity ?? "",
  }));
}

function rowsForGateway() {
  return [
    ["项目编码", "项目名称", "计量单位", "工程量"],
    ...state.boqRows.map((row) => [row.code, row.name, row.unit, row.quantity]),
  ];
}

function projectContext() {
  const projectName = $("boqProjectName")?.value.trim() || state.projectName;
  const sourceName = $("boqSourceName")?.value.trim() || state.sourceName;
  state.projectName = projectName || state.projectName || "未命名项目";
  state.sourceName = sourceName || state.sourceName || "未命名资料";
  state.projectId = state.projectId || "local-project";
  state.sourceId = state.sourceId || "local-source";
  return { project_id: state.projectId, source_id: state.sourceId };
}

function setStatus(text) {
  $("projectStatus").textContent = text;
}

function restoredStatus() {
  if (state.reviewResult) return state.reviewResult.publishable ? "初审通过" : "初审发现需处理事项";
  if (state.planResult) return "成本计划已生成";
  if (state.boqResult) return "清单资料已接入";
  return "准备开始";
}

function applyWorkspace(workspace) {
  if (!workspace) return;
  state.workspace = workspace;
  state.projectName = workspace.project?.name || state.projectName;
  state.sources = workspace.sources || [];
  if (state.sources.length && !state.fileName) state.sourceName = state.sources[state.sources.length - 1].name;
  const boq = workspace.boq?.result;
  const plan = workspace.cost_plan?.result;
  const review = workspace.review?.result;
  if (boq) {
    state.boqResult = boq;
    state.boqRows = draftFromItems(boq.items);
  }
  if (plan) {
    state.planResult = plan;
    state.planDraft = (plan.items || []).map((item) => ({
      ...item,
      contractPrice: item.unit_price ?? "",
      marketPrice: "",
    }));
  }
  if (review) state.reviewResult = review;
}

async function ensureProject() {
  const context = projectContext();
  state.workspace = await apiJson("/api/project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: context.project_id, name: state.projectName }),
  });
  applyWorkspace(state.workspace);
  return context;
}

async function loadWorkspace() {
  try {
    applyWorkspace(await apiJson(`/api/workspace?project_id=${encodeURIComponent(state.projectId)}`));
    await refreshDashboard();
  } catch (error) {
    await ensureProject();
    await refreshDashboard();
  }
}

async function refreshWorkspace() {
  applyWorkspace(await apiJson(`/api/workspace?project_id=${encodeURIComponent(state.projectId)}`));
  await refreshDashboard();
  renderDashboardIfVisible();
}

async function refreshDashboard() {
  try {
    state.dashboard = await apiJson(`/api/dashboard?project_id=${encodeURIComponent(state.projectId)}`);
  } catch (_) {
    state.dashboard = null;
  }
}

async function loadConnectors() {
  const response = await apiJson("/api/connectors");
  state.connectors = response.connectors || [];
  const recognition = await apiJson("/api/recognition/catalog");
  state.recognizers = recognition.recognizers || [];
}

function updateContextBar() {
  $("projectDisplay").textContent = state.projectName || "演示项目";
  $("sourceDisplay").textContent = state.fileName || state.sourceName || "等待接入";
  $("boqCount").textContent = String(state.boqResult?.item_count ?? state.boqRows.length ?? 0);
  $("planTotal").textContent = state.planResult?.summary?.contract_subtotal ?? "—";
  $("reviewGate").textContent = state.reviewResult
    ? (state.reviewResult.publishable ? "可发布" : "需处理")
    : "未开始";
}

function renderAssist() {
  const tasks = [];
  if (state.dashboard?.alerts?.length) {
    tasks.push({ tone: state.dashboard.alerts[0].severity === "block" ? "warn" : "next", title: `经营看板有 ${state.dashboard.alerts.length} 项自动提醒`, note: "先查看红色阻断和黄色预警，再回到对应工作步骤处理。", view: "dashboard" });
  }
  if (!state.boqResult) {
    tasks.push({ tone: "next", title: "接入清单资料", note: "可多选 Excel、PDF、Word、图片等资料，或手工录入清单项。", view: "boq" });
  } else {
    tasks.push({ tone: "done", title: `已读取 ${state.boqResult.item_count} 项清单`, note: "请核对编码、单位和工程量。", view: "boq" });
  }
  if (!state.planResult) {
    tasks.push({ tone: state.boqResult ? "next" : "wait", title: "编制成本计划", note: state.boqResult ? "补充合同单价后继续。" : "完成清单接入后继续。", view: "plan" });
  } else if (state.planResult.summary?.pending_item_count) {
    tasks.push({ tone: "warn", title: `还有 ${state.planResult.summary.pending_item_count} 项待组价`, note: "系统不会替缺失合同价猜价。", view: "plan" });
  } else {
    tasks.push({ tone: "done", title: "成本计划已生成", note: "可进入结算初审。", view: "plan" });
  }
  if (!state.reviewResult) {
    tasks.push({ tone: state.planResult ? "next" : "wait", title: "运行结算初审", note: state.planResult ? "检查金额、口径和发布闸门。" : "完成成本计划后继续。", view: "review" });
  } else {
    tasks.push({ tone: state.reviewResult.publishable ? "done" : "warn", title: state.reviewResult.publishable ? "初审通过发布闸门" : "初审发现需要处理的问题", note: state.reviewResult.publishable ? "可以进入发布流程。" : "查看下方审查事项并回到资料核对。", view: "review" });
  }
  $("assistList").replaceChildren(...tasks.map((task) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `assist-item assist-${task.tone}`;
    button.dataset.view = task.view;
    const marker = document.createElement("span");
    marker.className = "assist-marker";
    const body = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = task.title;
    const note = document.createElement("small");
    note.textContent = task.note;
    body.append(title, note);
    button.append(marker, body);
    return button;
  }));
}

function dashboardMoney(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(value);
}

function dashboardPercent(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) + "%" : String(value);
}

function dashboardStatus(status) {
  return {
    comparable: "口径可比",
    undeclared: "口径未完整声明",
    conflicted: "口径冲突",
    missing: "尚未比对",
  }[status] || status || "尚未比对";
}

function renderDashboardIfVisible() {
  if (state.view === "dashboard") renderDashboard();
}

function renderDashboard() {
  const dashboard = state.dashboard;
  if (!dashboard) {
    renderBlockedStep("项目经营看板", "看板数据暂时不可用，请确认已经登录并建立项目。", "回到工作概览", "overview");
    return;
  }
  const comparison = dashboard.comparison || {};
  const periods = dashboard.periods || {};
  const week = periods.week || {};
  const month = periods.month || {};
  const roleTitle = isManager() ? "项目经理经营看板" : "造价/成本经理经营看板";
  const roleNote = isManager()
    ? "先看红色阻断、成本超限和近月重复问题，再决定项目协调和审批动作。"
    : "先看成本基线比对、待组价项目和审查问题，再回到资料和成本计划处理。";
  $("workspaceContent").innerHTML =
    '<div class="surface-title"><div><span class="panel-label">PROJECT INTELLIGENCE</span><h3>' + roleTitle + '</h3></div><span class="surface-caption">本地自动汇总 · 打开看板即刷新预警</span></div>' +
    '<div class="dashboard-intro"><strong id="dashboardProjectName"></strong><span id="dashboardRoleNote"></span><small id="dashboardGeneratedAt"></small></div>' +
    '<section class="dashboard-alert-panel"><div class="surface-title"><div><span class="panel-label">AUTOMATED ALERTS</span><h3>需要优先处理</h3></div><span class="surface-caption">红色立即处理 · 黄色安排核对 · 蓝色关注趋势</span></div><div id="dashboardAlerts" class="dashboard-alert-list"></div></section>' +
    '<div id="dashboardMetrics" class="dashboard-metrics"></div>' +
    '<div class="dashboard-grid">' +
      '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">BASELINE / COMPARISON</span><h3>成本基线与造价资料比对</h3></div><button class="button button-quiet" data-view="plan" type="button">查看成本计划</button></div><div id="dashboardComparisonSummary" class="dashboard-comparison-summary"></div><div id="dashboardComparisonTable" class="dashboard-table"></div></section>' +
      '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">WEEKLY / MONTHLY</span><h3>问题周期趋势</h3></div><button class="button button-quiet" data-view="review" type="button">查看结算初审</button></div><div id="dashboardPeriods" class="dashboard-periods"></div><div id="dashboardRecurring" class="dashboard-recurring"></div></section>' +
    '</div>' +
    '<section class="dashboard-panel dashboard-issues-panel"><div class="surface-title"><div><span class="panel-label">ISSUE QUEUE</span><h3>当前问题与处理入口</h3></div><span class="surface-caption">每次运行初审会保留本地快照，支持近7天和近30天统计</span></div><div id="dashboardIssues" class="dashboard-issue-list"></div></section>';

  $("dashboardProjectName").textContent = dashboard.project?.name || state.projectName || "当前项目";
  $("dashboardRoleNote").textContent = roleNote;
  $("dashboardGeneratedAt").textContent = "刷新时间：" + new Date(dashboard.generated_at).toLocaleString("zh-CN");
  const metrics = [
    ["成本基线", dashboard.baseline?.status === "ready" ? dashboardMoney(dashboard.baseline.contract_subtotal) : "未建立", "合同计划小计"],
    ["成本超限", comparison.over_limit_amount ? dashboardMoney(comparison.over_limit_amount) : "0.00", comparison.over_limit_rate ? "偏差 " + dashboardPercent(comparison.over_limit_rate) : "当前未发现超限"],
    ["待组价", dashboard.baseline?.pending_item_count ?? 0, "清单项目"],
    ["本周问题", week.issue_count ?? 0, (week.review_count ?? 0) + " 次审查"],
    ["本月问题", month.issue_count ?? 0, (month.review_count ?? 0) + " 次审查"],
    ["初审门禁", dashboard.review?.status === "completed" ? (dashboard.review.publishable ? "可发布" : "需处理") : "未运行", "当前审查状态"],
  ];
  $("dashboardMetrics").replaceChildren(...metrics.map(([label, value, note]) => {
    const item = document.createElement("div");
    item.className = "dashboard-metric";
    const title = document.createElement("span");
    title.className = "dashboard-metric-label";
    title.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = String(value);
    const small = document.createElement("small");
    small.textContent = note;
    item.append(title, strong, small);
    return item;
  }));

  const alerts = $("dashboardAlerts");
  if (!dashboard.alerts?.length) {
    alerts.textContent = "当前没有自动预警。建议按周运行一次结算初审，持续形成趋势数据。";
  } else {
    alerts.replaceChildren(...dashboard.alerts.map((alert) => {
      const item = document.createElement("article");
      item.className = "dashboard-alert risk-" + (alert.risk?.color || "blue");
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = alert.title || "自动提醒";
      const message = document.createElement("small");
      message.textContent = alert.message || "请查看对应工作步骤。";
      body.append(title, message);
      item.append(body);
      if (alert.view) {
        const action = document.createElement("button");
        action.type = "button";
        action.className = "icon-button";
        action.textContent = alert.view === "dashboard" ? "查看趋势" : "去处理";
        action.dataset.view = alert.view;
        item.append(action);
      }
      return item;
    }));
  }

  const comparisonSummary = $("dashboardComparisonSummary");
  comparisonSummary.replaceChildren();
  const comparisonState = document.createElement("div");
  comparisonState.className = "comparison-state";
  const comparisonTitle = document.createElement("strong");
  comparisonTitle.textContent = dashboardStatus(comparison.status);
  const comparisonReason = document.createElement("span");
  comparisonReason.textContent = comparison.reason || "合同成本基线与参考价册的单项差额会在这里显示。";
  comparisonState.append(comparisonTitle, comparisonReason);
  const comparisonTotals = document.createElement("div");
  comparisonTotals.className = "comparison-totals";
  [["合同基线", comparison.baseline_total], ["参考成本", comparison.market_total], ["基线-参考价差", comparison.total_variance], ["预警线", (comparison.limits?.warn_rate ?? "—") + "% / " + (comparison.limits?.critical_rate ?? "—") + "%"]].forEach(([label, value]) => {
    const span = document.createElement("span");
    span.textContent = label + " ";
    const strong = document.createElement("b");
    strong.textContent = typeof value === "string" && value.includes("%") ? value : dashboardMoney(value);
    span.append(strong);
    comparisonTotals.append(span);
  });
  comparisonSummary.append(comparisonState, comparisonTotals);
  renderTable($("dashboardComparisonTable"), [["code", "编码"], ["name", "项目"], ["contract_amount", "基线金额"], ["market_amount", "参考金额"], ["over_limit_amount", "超限金额"], ["over_limit_rate", "偏差率"]], (comparison.rows || []).map((row) => ({
    code: row.code,
    name: row.name,
    contract_amount: dashboardMoney(row.contract_amount),
    market_amount: dashboardMoney(row.market_amount),
    over_limit_amount: dashboardMoney(row.over_limit_amount),
    over_limit_rate: dashboardPercent(row.over_limit_rate),
  })));

  $("dashboardPeriods").replaceChildren(...[week, month].map((period) => {
    const card = document.createElement("article");
    card.className = "dashboard-period";
    const title = document.createElement("strong");
    title.textContent = period.label || "周期";
    const count = document.createElement("span");
    count.textContent = (period.review_count || 0) + " 次审查 · " + (period.issue_count || 0) + " 个问题";
    const detail = document.createElement("small");
    detail.textContent = "阻断 " + (period.block || 0) + " · 预警 " + (period.warn || 0) + " · 提示 " + (period.info || 0);
    card.append(title, count, detail);
    return card;
  }));
  const recurring = $("dashboardRecurring");
  const recurringRules = [...(month.recurring_rules || [])].filter((item) => item.count > 1);
  recurring.replaceChildren();
  const recurringLabel = document.createElement("span");
  recurringLabel.className = "panel-label";
  recurringLabel.textContent = "REPEATED RULES";
  const recurringText = document.createElement("p");
  recurringText.textContent = recurringRules.length
    ? "近30天重复出现：" + recurringRules.map((item) => item.rule_id + "（" + item.count + "次）").join("、")
    : "暂未形成重复规则统计；持续运行初审后会自动归纳。";
  recurring.append(recurringLabel, recurringText);

  const issues = $("dashboardIssues");
  if (!dashboard.recent_issues?.length) {
    issues.textContent = dashboard.review?.status === "completed" ? "最近一次初审没有发现问题。" : "尚未形成当前问题清单。";
  } else {
    issues.replaceChildren(...dashboard.recent_issues.map((finding) => {
      const item = document.createElement("article");
      item.className = "dashboard-issue risk-" + (finding.risk?.color || (finding.severity === "block" ? "red" : finding.severity === "warn" ? "yellow" : "blue"));
      const badge = document.createElement("span");
      badge.textContent = finding.risk?.label || finding.severity || "提示";
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = finding.message || "审查事项";
      const note = document.createElement("small");
      note.textContent = finding.row ? "第 " + finding.row + " 项 · " + (finding.rule_id || "规则") : (finding.rule_id || "全局规则");
      body.append(title, note);
      item.append(badge, body);
      return item;
    }));
  }
  bindViewButtons();
}

function renderOverview() {
  const items = state.boqResult?.items || [];
  const review = state.reviewResult;
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">TODAY'S WORK</span><h3>项目进度概览</h3></div><span class="surface-caption">所有资料在当前项目内流转并保存</span></div>
    <div class="project-setup">
      <div><span class="panel-label">PROJECT SETUP</span><strong>项目建档</strong><small>保存项目名称后，可一次接入照片、Word、Excel、PDF 等初步资料，系统会自动识别并归档。</small></div>
      <label>项目名称<input id="projectNameInput" /></label>
      <button id="saveProject" class="button button-primary" type="button">保存项目</button>
      <button id="addProjectInfo" class="button button-quiet" type="button">接入初步资料</button>
      <span id="projectSaveStatus" class="request-status">已连接当前项目</span>
    </div>
    <div class="overview-cards">
      <button class="overview-card" data-view="boq" type="button"><span class="card-label">清单资料</span><strong>${items.length || 0}</strong><small>${items.length ? "已读取，可核对" : "尚未接入"}</small></button>
      <button class="overview-card" data-view="plan" type="button"><span class="card-label">成本计划</span><strong>${state.planResult?.summary?.contract_subtotal ?? "—"}</strong><small>${state.planResult ? "合同计划小计" : "等待清单资料"}</small></button>
      <button class="overview-card" data-view="review" type="button"><span class="card-label">结算初审</span><strong>${review ? (review.publishable ? "通过" : "需处理") : "—"}</strong><small>${review ? `${review.summary.finding_count} 个审查事项` : "尚未运行"}</small></button>
    </div>
    <div class="overview-panel">
      <div class="surface-title"><div><span class="panel-label">RECENT DATA</span><h3>当前清单资料</h3></div><button class="button button-quiet" data-view="boq" type="button">查看清单</button></div>
      ${items.length ? "" : '<p class="empty-state">还没有清单资料。使用左侧“接入清单资料”开始。</p>'}
      <div id="overviewTable"></div>
    </div>`;
  if (items.length) renderTable($("overviewTable"), [["code", "编码"], ["name", "项目"], ["unit", "单位"], ["quantity", "工程量"]], items);
  $("projectNameInput").value = state.projectName || "";
  $("saveProject").addEventListener("click", saveProject);
  $("addProjectInfo").addEventListener("click", () => $("projectInfoInput").click());
  $("projectInfoInput").onchange = handleProjectInfoFiles;
  const sourcePanel = document.createElement("div");
  sourcePanel.className = "overview-panel source-panel";
  sourcePanel.innerHTML = `
    <div class="surface-title"><div><span class="panel-label">PROJECT FILES</span><h3>项目资料库</h3></div><button id="uploadSource" class="button button-quiet" type="button">＋接入资料</button></div>
    <p class="business-note">文件先在本地保存并自动识别归档；本地识别不外发，外部 OCR 只有在明确确认后才会发送指定文件。</p>
    <div id="sourceList" class="source-list"></div>
    <div id="sourceIntakeSummary" class="intake-report-list"></div>
    <div class="recognition-entry"><span class="panel-label">RECOGNITION</span><div id="recognizerCatalog" class="recognizer-list"></div></div>
    <div class="tool-entry"><span class="panel-label">TOOL ENTRY</span><div id="connectorCatalog" class="tool-entry-grid"></div></div>
    <div class="export-actions"><button id="exportReport" class="button button-quiet" type="button">导出 Word 兼容报告</button><button id="exportBoq" class="button button-quiet" type="button">导出 Excel 清单</button><button id="exportPlan" class="button button-quiet" type="button">导出 Excel 成本计划</button><button id="exportBundle" class="button button-primary" type="button">导出项目交换包</button><button id="importBundle" class="button button-quiet" type="button">导入项目交换包</button></div>`;
  $("workspaceContent").append(sourcePanel);
  const overviewCards = document.querySelector(".overview-cards");
  if (overviewCards) {
    overviewCards.classList.add("has-dashboard");
    const dashboardCard = document.createElement("button");
    dashboardCard.className = "overview-card";
    dashboardCard.dataset.view = "dashboard";
    dashboardCard.type = "button";
    const label = document.createElement("span");
    label.className = "card-label";
    label.textContent = "项目经营看板";
    const value = document.createElement("strong");
    value.textContent = String(state.dashboard?.alerts?.length || 0);
    const note = document.createElement("small");
    note.textContent = state.dashboard?.alerts?.length ? "项自动预警待处理" : "当前没有自动预警";
    dashboardCard.append(label, value, note);
    overviewCards.append(dashboardCard);
  }
  renderSourceList();
  renderIntakeReports("sourceIntakeSummary");
  renderRecognizerCatalog();
  renderConnectorCatalog();
  $("uploadSource").addEventListener("click", () => $("sourceInput").click());
  $("sourceInput").onchange = handleSourceFile;
  $("exportReport").addEventListener("click", () => downloadProjectFile("report"));
  $("exportBoq").addEventListener("click", () => downloadProjectFile("boq.xlsx"));
  $("exportPlan").addEventListener("click", () => downloadProjectFile("cost-plan.xlsx"));
  $("exportBundle").addEventListener("click", () => downloadProjectFile("bundle"));
  $("importBundle").addEventListener("click", () => $("bundleInput").click());
  $("bundleInput").onchange = handleBundleImport;
  bindViewButtons();
}

function renderConnectorCatalog() {
  const target = $("connectorCatalog");
  if (!target) return;
  const connectors = state.connectors.length ? state.connectors : [
    { name: "Excel / CSV", description: "清单、价册和成本计划的双向表格交换。", formats: [".xlsx", ".csv"], status: "ready" },
    { name: "Word", description: "合同资料归档与项目报告导出。", formats: [".docx", ".html"], status: "ready" },
    { name: "CAD / 算量", description: "图纸和算量文件进入项目资料库。", formats: [".dwg", ".dxf"], status: "exchange" },
    { name: "预算软件", description: "通过项目交换包共享清单、价册和结果。", formats: [".xlsx", ".csv", ".zip"], status: "exchange" },
  ];
  target.replaceChildren(...connectors.map((connector) => {
    const item = document.createElement("div");
    item.className = "connector-item";
    const name = document.createElement("strong");
    name.textContent = connector.name;
    const note = document.createElement("small");
    note.textContent = `${connector.description} ${connector.formats.join(" / ")}`;
    const status = document.createElement("span");
    status.className = `connector-status connector-${connector.status}`;
    status.textContent = connector.status === "ready" ? "可直接使用" : "通过交换包";
    item.append(name, note, status);
    return item;
  }));
}

function sourceViewUrl(source, derived = false) {
  return `/api/source/view?project_id=${encodeURIComponent(state.projectId)}&source_id=${encodeURIComponent(source.source_id)}${derived ? "&derived=1" : ""}`;
}

function viewSource(source, derived = false) {
  window.open(sourceViewUrl(source, derived), "_blank", "noopener");
}

async function copySourcePaths(source) {
  const artifact = (source.recognition || {}).artifact || {};
  const paths = [source.storage_path, artifact.storage_path].filter(Boolean).join("\n");
  if (!paths) {
    setStatus("当前资料还没有记录保存路径");
    return;
  }
  try {
    await navigator.clipboard.writeText(paths);
    setStatus("资料保存路径已复制");
  } catch (_) {
    window.prompt("资料保存路径", paths);
  }
}

async function modifySource(source) {
  const nextName = window.prompt("修改资料显示名称（原始文件内容不可直接改写，修改会形成留痕）", source.name);
  if (!nextName || nextName.trim() === source.name) return;
  try {
    const response = await apiJson("/api/source/modify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, source_id: source.source_id, changes: { name: nextName.trim() } }),
    });
    applyWorkspace(response.workspace);
    renderSourceList();
    renderControlIfVisible();
    setStatus("资料名称已修改，操作已留痕");
  } catch (error) {
    setError(error.message);
  }
}

async function deleteSource(source) {
  if (!isManager() || !window.confirm("仅项目经理可执行。资料将软删除并保留原文件与操作记录，确认继续？")) return;
  try {
    const response = await apiJson("/api/source/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, source_id: source.source_id }),
    });
    applyWorkspace(response.workspace);
    renderSourceList();
    renderControlIfVisible();
    setStatus("资料已软删除，原文件和操作痕迹仍保留");
  } catch (error) {
    setError(error.message);
  }
}

function renderSourceList() {
  const list = $("sourceList");
  if (!list) return;
  if (!state.sources.length) {
    list.className = "source-list empty-state";
    list.textContent = "当前项目还没有其他资料。可以从这里接入 Word、PDF、CAD 或 Excel 文件。";
    return;
  }
  list.className = "source-list";
  list.replaceChildren(...state.sources.slice().reverse().map((source) => {
    const item = document.createElement("div");
    item.className = "source-item";
    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = source.name;
    const meta = document.createElement("small");
    const recognition = source.recognition || {};
    const recognitionLabel = recognition.category ? ` · ${recognition.category}` : "";
    const deleted = source.status === "deleted";
    meta.textContent = `${source.kind} · ${deleted ? "已删除（保留记录）" : recognition.status === "completed" ? "已识别归档" : "已保存"}${recognitionLabel}`;
    const pathInfo = document.createElement("small");
    pathInfo.className = "source-path";
    const artifactPath = recognition.artifact?.storage_path ? `\n识别稿：${recognition.artifact.storage_path}` : "";
    pathInfo.textContent = `原件：${source.storage_path || "路径未记录"}${artifactPath}`;
    info.append(name, meta, pathInfo);
    const stateTag = document.createElement("span");
    stateTag.className = `source-state source-${recognition.status || "pending"}`;
    stateTag.textContent = deleted ? "已删除·留痕" : recognition.status === "completed" ? "本地完成" : recognition.status === "needs_ocr" ? "待 OCR" : recognition.status === "unavailable" || recognition.status === "error" ? "未转换" : "待识别";
    if (recognition.message) item.title = recognition.message;
    const actions = document.createElement("div");
    actions.className = "source-actions";
    const viewButton = document.createElement("button");
    viewButton.type = "button";
    viewButton.className = "icon-button source-view-button";
    viewButton.textContent = "查看";
    viewButton.addEventListener("click", () => viewSource(source));
    actions.append(viewButton);
    const copyPathButton = document.createElement("button");
    copyPathButton.type = "button";
    copyPathButton.className = "icon-button";
    copyPathButton.textContent = "复制路径";
    copyPathButton.addEventListener("click", () => copySourcePaths(source));
    actions.append(copyPathButton);
    if (recognition.artifact) {
      const artifactButton = document.createElement("button");
      artifactButton.type = "button";
      artifactButton.className = "icon-button";
      artifactButton.textContent = "查看识别稿";
      artifactButton.addEventListener("click", () => viewSource(source, true));
      actions.append(artifactButton);
    }
    if (!deleted) {
      const modifyButton = document.createElement("button");
      modifyButton.type = "button";
      modifyButton.className = "icon-button";
      modifyButton.textContent = "修改信息";
      modifyButton.addEventListener("click", () => modifySource(source));
      actions.append(modifyButton);
    }
    const localButton = document.createElement("button");
    localButton.type = "button";
    localButton.className = "icon-button";
    localButton.textContent = "本地识别";
    localButton.addEventListener("click", () => recognizeSource(source.source_id, "local-auto"));
    if (!deleted) actions.append(localButton);
    if (!deleted && recognition.status === "needs_ocr") {
      const externalButton = document.createElement("button");
      externalButton.type = "button";
      externalButton.className = "icon-button external-action";
      externalButton.textContent = "外部 OCR";
      externalButton.addEventListener("click", () => requestExternalOcr(source.source_id));
      actions.append(externalButton);
    }
    if (!deleted && isManager()) {
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "icon-button danger-action";
      deleteButton.textContent = "删除（留痕）";
      deleteButton.addEventListener("click", () => deleteSource(source));
      actions.append(deleteButton);
    } else if (!deleted) {
      const permission = document.createElement("small");
      permission.className = "permission-note";
      permission.textContent = "删除需项目经理";
      actions.append(permission);
    }
    item.append(info, stateTag, actions);
    return item;
  }));
}

function renderIntakeReports(targetId = "boqIntakeSummary") {
  const target = $(targetId);
  if (!target) return;
  if (!state.intakeReports.length) {
    target.replaceChildren();
    return;
  }
  target.className = "intake-report-list";
  target.replaceChildren(...state.intakeReports.map((report) => {
    const item = document.createElement("div");
    item.className = `intake-report intake-${report.status}`;
    const title = document.createElement("strong");
    title.textContent = report.name;
    const message = document.createElement("span");
    message.textContent = report.message;
    item.append(title, message);
    if (report.storage_path) {
      const path = document.createElement("small");
      path.className = "intake-path";
      path.textContent = `保存路径：${report.storage_path}`;
      item.append(path);
    }
    return item;
  }));
}

function renderAuditLog(target, entries) {
  if (!target) return;
  if (!entries?.length) {
    target.textContent = "当前项目还没有操作记录。";
    return;
  }
  target.replaceChildren(...entries.slice().reverse().map((entry) => {
    const row = document.createElement("div");
    row.className = "audit-row";
    const action = document.createElement("strong");
    action.textContent = entry.action || "项目操作";
    const actor = document.createElement("span");
    actor.textContent = `${entry.actor?.role_label || entry.actor?.role || "本地人员"} · ${entry.actor?.username || entry.actor?.id || "未知"}`;
    const time = document.createElement("small");
    time.textContent = (entry.timestamp || "") + " · " + (entry.target || "");
    row.append(action, actor, time);
    return row;
  }));
}

function renderControlIfVisible() {
  if (state.view === "control") renderControl();
}

async function renderControl() {
  if (!isManager()) {
    setView("overview");
    return;
  }
  $("workspaceContent").innerHTML =
    '<div class="surface-title"><div><span class="panel-label">PROJECT CONTROL</span><h3>项目经理控制台</h3></div><span class="surface-caption">权限、文件状态、风险分级与全部操作留痕</span></div>' +
    '<div class="control-grid">' +
    '<section class="control-panel"><span class="panel-label">PERMISSION POLICY</span><h3>角色权限</h3>' +
    '<div class="policy-row"><strong>项目经理</strong><span>查看、录入、修改、删除（软删除）、查看审计</span></div>' +
    '<div class="policy-row"><strong>造价人员</strong><span>查看、录入、修改、识别、业务数据编辑；删除需项目经理</span></div>' +
    '<div class="policy-row"><strong>原始文件</strong><span>内容地址化保存，不直接覆盖；修改只产生元数据版本，删除保留原文件和痕迹</span></div></section>' +
    '<section class="control-panel"><span class="panel-label">RISK COLORS</span><h3>风险颜色</h3>' +
    '<div class="risk-legend"><span class="risk-chip risk-red">红色 · 紧急阻断</span><span class="risk-chip risk-yellow">黄色 · 预警</span><span class="risk-chip risk-blue">蓝色 · 一般提示</span></div>' +
    '<p class="business-note">颜色来自工作流输出的审查严重级别；不会用颜色替代证据和规则。</p></section></div>' +
    '<section class="control-panel audit-panel"><div class="surface-title"><div><span class="panel-label">AUDIT TRAIL</span><h3>项目操作记录</h3></div><span class="surface-caption">修改和删除均保留操作者、时间、对象及前后值</span></div><div id="auditLog" class="audit-list"></div></section>';
  renderAuditLog($("auditLog"), state.workspace?.audit_log || []);
  try {
    const response = await apiJson(`/api/audit?project_id=${encodeURIComponent(state.projectId)}`);
    renderAuditLog($("auditLog"), response.audit_log || []);
  } catch (error) {
    setError(error.message);
  }
}

function renderRecognizerCatalog() {
  const target = $("recognizerCatalog");
  if (!target) return;
  const recognizers = state.recognizers.length ? state.recognizers : [
    { name: "本地自动识别", status: "ready", description: "先在本机提取文字并归档分类。", requires_explicit_consent: false },
    { name: "百度 OCR", status: "requires_configuration", description: "明确确认后才发送指定图片。", requires_explicit_consent: true },
  ];
  target.replaceChildren(...recognizers.map((recognizer) => {
    const item = document.createElement("div");
    item.className = "recognizer-item";
    const title = document.createElement("strong");
    title.textContent = recognizer.name;
    const note = document.createElement("small");
    note.textContent = recognizer.description;
    const status = document.createElement("span");
    status.className = `recognizer-status recognizer-${recognizer.status}`;
    status.textContent = recognizer.requires_explicit_consent ? "需明确授权" : recognizer.status === "ready" ? "本地可用" : "可选安装";
    item.append(title, note, status);
    return item;
  }));
}

async function recognizeSource(sourceId, connectorId = "local-auto", allowExternal = false) {
  setError("");
  try {
    const response = await apiJson("/api/source/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, source_id: sourceId, connector_id: connectorId, allow_external: allowExternal }),
    });
    applyWorkspace(response.workspace);
    renderSourceList();
    updateContextBar();
    setStatus(response.recognition?.message || "资料识别完成");
  } catch (error) {
    setError(error.message);
  }
}

function requestExternalOcr(sourceId) {
  const confirmed = window.confirm("外部 OCR 会把指定图片发送到百度 OCR。是否明确授权本次发送？");
  if (confirmed) recognizeSource(sourceId, "baidu-ocr", true);
}

async function saveProject() {
  const input = $("projectNameInput");
  const name = input?.value.trim();
  if (!name) {
    setError("请填写项目名称");
    return;
  }
  state.projectName = name;
  setError("");
  try {
    await ensureProject();
    $("projectSaveStatus").textContent = "项目已保存";
    $("projectDisplay").textContent = name;
    setStatus("项目已保存");
  } catch (error) {
    setError(error.message);
  }
}

function sourceIdFor(file, index = 0) {
  return `${file.name}-${Date.now()}-${index}`;
}

function isTableSource(file) {
  return [".xlsx", ".xlsm", ".csv"].includes(file.name.toLowerCase().slice(file.name.lastIndexOf(".")));
}

function recognitionReport(source) {
  const recognition = source?.recognition || {};
  if (recognition.status === "completed") {
    return { status: "completed", message: `已识别并归档${recognition.category ? `到“${recognition.category}”` : ""}` };
  }
  if (recognition.status === "needs_ocr") {
    return { status: "needs_ocr", message: "本地未提取到文字，文件已保存；需要 OCR 才能继续识别。" };
  }
  if (recognition.status === "unavailable") {
    return { status: "unavailable", message: recognition.message || "当前格式暂不能转换，文件已保存。" };
  }
  return { status: "pending", message: "文件已保存，等待识别。" };
}

async function uploadSourceFile(file, projectId, index = 0, parseBoq = false) {
  const sourceId = sourceIdFor(file, index);
  const form = new FormData();
  form.append("project_id", projectId);
  form.append("source_id", sourceId);
  form.append("file", file, file.name);
  if (parseBoq && isTableSource(file)) {
    const result = await apiJson("/api/boq/upload", { method: "POST", body: form });
    return { sourceId, result, source: null, report: { status: "table", message: `已读取 ${result.item_count} 项清单，进入清单核对。` } };
  }
  const response = await apiJson("/api/source/upload", { method: "POST", body: form });
  return {
    sourceId,
    result: null,
    source: response.source,
    report: {
      ...recognitionReport(response.source),
      storage_path: response.source.storage_path,
    },
  };
}

async function uploadFiles(files, { parseBoq = false } = {}) {
  const context = await ensureProject();
  const items = [];
  const reports = [];
  for (const [index, file] of files.entries()) {
    try {
      const uploaded = await uploadSourceFile(file, context.project_id, index, parseBoq);
      items.push(...(uploaded.result?.items || []));
      reports.push({ name: file.name, source_id: uploaded.sourceId, ...(uploaded.report || { status: "completed", message: "已保存。" }) });
    } catch (error) {
      reports.push({ name: file.name, status: "error", message: error.message || "文件处理失败。" });
    }
  }
  await refreshWorkspace();
  const sourceMap = new Map((state.sources || []).map((source) => [source.source_id, source]));
  for (const report of reports) {
    const source = sourceMap.get(report.source_id);
    const recognition = source?.recognition;
    if (source?.storage_path) report.storage_path = source.storage_path;
    if (report.status === "table" && recognition && recognition.status !== "completed") {
      report.status = recognition.status || "unavailable";
      report.message = `${report.message} ${recognitionReport(source).message}`;
    }
  }
  const sourceNames = files.map((file) => file.name);
  state.fileName = sourceNames.length === 1 ? sourceNames[0] : `${sourceNames.length} 个文件`;
  state.sourceName = state.fileName;
  state.intakeReports = reports;
  if (parseBoq && items.length) {
    const rows = [["项目编码", "项目名称", "计量单位", "工程量"], ...items.map((item) => [item.code, item.name, item.unit, item.quantity])];
    const combined = await apiJson("/api/boq", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...context, source_id: `multi-${Date.now()}`, rows }),
    });
    state.boqResult = combined;
    state.boqRows = draftFromItems(combined.items);
    state.planDraft = [];
    state.planResult = null;
    state.reviewResult = null;
  }
  return { files, reports, items };
}

async function handleSourceFile(event) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  setError("");
  try {
    await uploadFiles(files);
    renderSourceList();
    updateContextBar();
    renderIntakeReports("sourceIntakeSummary");
    setStatus(`${files.length} 个资料文件已保存并完成本地识别`);
    $("projectSaveStatus").textContent = `${files.length} 个资料已归档`;
  } catch (error) {
    setError(error.message);
  } finally {
    event.target.value = "";
  }
}

async function handleProjectInfoFiles(event) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  setError("");
  try {
    await uploadFiles(files);
    renderOverview();
    setStatus(`${files.length} 个初步资料已保存并自动归档`);
  } catch (error) {
    setError(error.message);
  } finally {
    event.target.value = "";
  }
}

async function handleBundleImport(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  setError("");
  try {
    const form = new FormData();
    form.append("file", file, file.name);
    const workspace = await apiJson("/api/workspace/import", { method: "POST", body: form });
    state.projectId = workspace.project?.id || state.projectId;
    state.projectName = workspace.project?.name || state.projectName;
    state.sourceId = "";
    state.sourceName = "项目交换包";
    state.fileName = file.name;
    applyWorkspace(workspace);
    setView("overview");
    setStatus("项目交换包已导入并恢复");
  } catch (error) {
    setError(error.message);
  } finally {
    event.target.value = "";
  }
}

function downloadProjectFile(kind) {
  if (!state.workspace) {
    setError("请先保存项目");
    return;
  }
  window.location.href = `/api/workspace/${encodeURIComponent(state.projectId)}/${kind}`;
}

function renderBoq() {
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">DOCUMENT INTAKE</span><h3>接入清单资料</h3></div><span class="surface-caption">支持多文件接入；表格进入清单，PDF/Word/图片等进入资料库并自动识别</span></div>
    <div class="intake-banner">
      <div><strong>资料接口</strong><span>可一次选择多个 Excel、CSV、PDF、Word、图片或 CAD 文件；系统会逐一显示识别和转换结果。</span></div>
      <button id="chooseFile" class="button button-primary" type="button">选择资料文件（可多选）</button>
      <span id="fileName" class="file-name">尚未选择文件</span>
    </div>
    <div id="boqIntakeSummary" class="intake-report-list"></div>
    <div class="field-grid workspace-fields">
      <label>项目名称<input id="boqProjectName" /></label>
      <label>资料名称<input id="boqSourceName" /></label>
    </div>
    <div class="data-entry-heading"><div><span class="panel-label">BOQ ITEMS</span><h3>清单项</h3></div><button id="addBoqRow" class="button button-quiet" type="button">＋新增一行</button></div>
    <div id="boqEditor" class="editable-table"></div>
    <div class="action-row"><button id="runBoq" class="button button-primary" type="button">接入并检查资料</button><span class="request-status">接入后会显示清单数量与核对表。</span></div>
    <div id="boqOutput" class="inline-output"></div>`;
  $("boqProjectName").value = state.projectName || "";
  $("boqSourceName").value = state.sourceName || "";
  $("fileName").textContent = state.fileName || "尚未选择文件";
  renderBoqEditor();
  $("addBoqRow").addEventListener("click", () => {
    state.boqRows.push({ code: "", name: "", unit: "", quantity: "" });
    renderBoqEditor();
  });
  $("chooseFile").addEventListener("click", () => $("fileInput").click());
  $("runBoq").addEventListener("click", runBoqManual);
  $("fileInput").onchange = handleFile;
  renderIntakeReports();
  if (state.boqResult) renderBoqOutput(state.boqResult);
}

function renderBoqEditor() {
  const rows = state.boqRows.length ? state.boqRows : [{ code: "", name: "", unit: "", quantity: "" }];
  const wrap = $("boqEditor");
  if (!wrap) return;
  wrap.replaceChildren();
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr><th>项目编码</th><th>项目名称</th><th>单位</th><th>工程量</th><th></th></tr></thead>`;
  const body = document.createElement("tbody");
  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    ["code", "name", "unit", "quantity"].forEach((key) => {
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.value = row[key] ?? "";
      input.placeholder = key === "code" ? "12位清单编码" : "请输入";
      input.addEventListener("input", () => { state.boqRows[index][key] = input.value; });
      td.append(input);
      tr.append(td);
    });
    const action = document.createElement("td");
    const remove = document.createElement("button");
    remove.className = "icon-button";
    remove.type = "button";
    remove.textContent = "删除";
    remove.addEventListener("click", () => { state.boqRows.splice(index, 1); renderBoqEditor(); });
    action.append(remove);
    tr.append(action);
    body.append(tr);
  });
  table.append(body);
  wrap.append(table);
}

function renderBoqOutput(result) {
  const output = $("boqOutput");
  if (!output) return;
  output.innerHTML = `<div class="result-strip result-ok"><strong>资料已接入</strong><span>${result.item_count} 项清单已整理，可继续核对或进入成本计划。</span><button id="toPlan" class="button button-quiet" type="button">进入成本计划 →</button></div>`;
  $("toPlan").addEventListener("click", () => setView("plan"));
}

async function runBoqManual() {
  setError("");
  try {
    const context = await ensureProject();
    const result = await apiJson("/api/boq", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...context, rows: rowsForGateway() }),
    });
    state.boqResult = result;
    state.boqRows = draftFromItems(result.items);
    state.planDraft = [];
    state.planResult = null;
    state.reviewResult = null;
    await refreshWorkspace();
    setStatus("清单资料已接入");
    updateContextBar();
    renderBoqOutput(result);
    renderAssist();
  } catch (error) {
    setError(error.message);
    setStatus("清单资料未接入");
  }
}

async function handleFile(event) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  setError("");
  try {
    await uploadFiles(files, { parseBoq: true });
    $("fileName").textContent = files.length === 1 ? files[0].name : `${files.length} 个文件`;
    renderBoqEditor();
    renderIntakeReports();
    if (state.boqResult) renderBoqOutput(state.boqResult);
    updateContextBar();
    renderAssist();
    setStatus(`${files.length} 个资料文件已处理`);
  } catch (error) {
    setError(error.message);
    setStatus("资料读取失败");
  } finally {
    event.target.value = "";
  }
}

function syncPlanDraft() {
  const items = state.boqResult?.items || [];
  if (state.planDraft.length !== items.length) {
    state.planDraft = items.map((item) => ({ ...item, contractPrice: "", marketPrice: "" }));
  }
}

function renderPlan() {
  if (!state.boqResult) {
    renderBlockedStep("成本计划", "请先接入清单资料。", "去接入清单", "boq");
    return;
  }
  syncPlanDraft();
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">COST PLANNING</span><h3>编制成本计划</h3></div><span class="surface-caption">合同单价进入计划；市场单价仅用于内部成本参考</span></div>
    <div class="notice-line"><strong>当前资料：${state.fileName || state.sourceName}</strong><span>${state.boqResult.item_count} 项清单已带入。</span></div>
    <div class="data-entry-heading"><div><span class="panel-label">PRICE BOOK</span><h3>补充单价</h3></div><span class="input-note">没有合同单价的项目会保留为待组价。</span></div>
    <div id="planEditor" class="editable-table"></div>
    <div class="action-row"><button id="runPlan" class="button button-primary" type="button">生成成本计划</button><span class="request-status">计划金额和待组价项目会显示在下方。</span></div>
    <div id="planOutput" class="inline-output"></div>`;
  renderPlanEditor();
  $("runPlan").addEventListener("click", runCostPlan);
  if (state.planResult) renderPlanOutput(state.planResult);
}

function renderPlanEditor() {
  const wrap = $("planEditor");
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr><th>项目</th><th>单位</th><th>工程量</th><th>合同单价</th><th>市场参考价</th></tr></thead>`;
  const body = document.createElement("tbody");
  state.planDraft.forEach((row, index) => {
    const tr = document.createElement("tr");
    [row.name, row.unit, row.quantity].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = String(value ?? "—");
      tr.append(td);
    });
    ["contractPrice", "marketPrice"].forEach((key) => {
      const td = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.step = "0.01";
      input.placeholder = "未填写";
      input.value = state.planDraft[index][key] ?? "";
      input.addEventListener("input", () => { state.planDraft[index][key] = input.value; });
      td.append(input);
      tr.append(td);
    });
    body.append(tr);
  });
  table.append(body);
  wrap.append(table);
}

function priceBook(key) {
  return Object.fromEntries(state.planDraft.filter((item) => item[key] !== "" && item[key] !== null).map((item) => [item.code, item[key]]));
}

async function runCostPlan() {
  setError("");
  try {
    const context = await ensureProject();
    const result = await apiJson("/api/cost-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: context.project_id,
        source_id: context.source_id,
        items: state.boqResult.items,
        contract_prices: priceBook("contractPrice"),
        market_prices: priceBook("marketPrice"),
        contract_basis: state.sample?.contract_basis || {},
        market_basis: state.sample?.market_basis || {},
      }),
    });
    state.planResult = result;
    state.reviewResult = null;
    await refreshWorkspace();
    setStatus("成本计划已生成");
    updateContextBar();
    renderPlanOutput(result);
    renderAssist();
  } catch (error) {
    setError(error.message);
    setStatus("成本计划生成失败");
  }
}

function renderPlanOutput(result) {
  const summary = result.summary || {};
  const output = $("planOutput");
  if (!output) return;
  output.innerHTML = `
    <div class="metric-row"><div><strong>${summary.contract_subtotal}</strong><span>合同计划小计</span></div><div><strong>${summary.contract_item_count}</strong><span>已定价项目</span></div><div><strong>${summary.pending_item_count}</strong><span>待组价项目</span></div></div>
    <div class="result-strip ${summary.pending_item_count ? "result-warn" : "result-ok"}"><strong>${summary.pending_item_count ? `有 ${summary.pending_item_count} 项需要补充合同单价` : "成本计划已完整生成"}</strong><span>${result.cost_control ? "市场参考价已单独保留为内部成本控制信息。" : "未提供市场参考价。"}</span><button id="toReview" class="button button-quiet" type="button">进入结算初审 →</button></div>`;
  $("toReview").addEventListener("click", () => setView("review"));
}

function displayPlanStatus(status) {
  return {
    contract: "合同价",
    "re-priced-pending": "待组价",
    unpriced: "未定价",
  }[status] || status || "—";
}

function reviewRows() {
  return (state.planResult?.items || []).map((item, index) => ({
    row: index + 1,
    code: item.code,
    name: item.name,
    unit: item.unit,
    quantity: item.quantity,
    price: item.unit_price,
    total: item.amount,
  }));
}

function renderReview() {
  if (!state.planResult) {
    renderBlockedStep("结算初审", "请先生成成本计划。", "去做成本计划", "plan");
    return;
  }
  const rows = reviewRows();
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">SETTLEMENT REVIEW</span><h3>结算初审</h3></div><span class="surface-caption">检查数量、金额、单位和价格口径，形成处理建议</span></div>
    <div class="notice-line"><strong>待审资料：${state.fileName || state.sourceName}</strong><span>以下数据来自已生成的成本计划。</span></div>
    <div id="reviewTable" class="editable-table readonly-table"></div>
    <div class="action-row"><button id="runReview" class="button button-primary" type="button">运行结算初审</button><span class="request-status">系统会显示可发布、阻断和需要核对的事项。</span></div>
    <div id="reviewOutput" class="inline-output"></div>`;
  renderTable($("reviewTable"), [["name", "项目"], ["unit", "单位"], ["quantity", "工程量"], ["unit_price", "单价"], ["amount", "金额"], ["display_status", "状态"]], (state.planResult.items || []).map((item) => ({ ...item, display_status: displayPlanStatus(item.status) })));
  $("runReview").addEventListener("click", runReview);
  if (state.reviewResult) renderReviewOutput(state.reviewResult);
}

async function runReview() {
  setError("");
  try {
    const context = await ensureProject();
    const result = await apiJson("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: context.project_id,
        source_id: context.source_id,
        rows: reviewRows(),
        reference_units: state.sample?.reference_units || {},
        reference_prices: state.sample?.reference_prices || {},
        subject_basis: state.sample?.subject_basis || {},
        reference_basis: state.sample?.reference_basis || {},
      }),
    });
    state.reviewResult = result;
    await refreshWorkspace();
    setStatus(result.publishable ? "初审通过" : "初审发现需处理事项");
    updateContextBar();
    renderReviewOutput(result);
    renderAssist();
  } catch (error) {
    setError(error.message);
    setStatus("初审运行失败");
  }
}

function renderReviewOutput(result) {
  const summary = result.summary || {};
  const output = $("reviewOutput");
  if (!output) return;
  output.innerHTML = `<div class="metric-row"><div><strong>${summary.row_count}</strong><span>待审项目</span></div><div><strong>${summary.finding_count}</strong><span>审查事项</span></div><div><strong>${summary.block}</strong><span>阻断</span></div><div><strong>${summary.warn}</strong><span>提醒</span></div></div>`;
  const risk = result.risk || { label: result.publishable ? "无风险事项" : "需要处理", color: result.publishable ? "blue" : "red" };
  const riskStrip = document.createElement("div");
  riskStrip.className = `risk-strip risk-${risk.color || "blue"}`;
  riskStrip.textContent = `当前最高风险：${risk.label}`;
  output.append(riskStrip);
  const legend = document.createElement("div");
  legend.className = "risk-legend review-risk-legend";
  legend.innerHTML = '<span class="risk-chip risk-red">红色 · 紧急阻断</span><span class="risk-chip risk-yellow">黄色 · 预警</span><span class="risk-chip risk-blue">蓝色 · 一般提示</span>';
  output.append(legend);
  const gate = document.createElement("div");
  gate.className = `result-strip ${result.publishable ? "result-ok" : "result-warn"}`;
  const title = document.createElement("strong");
  title.textContent = result.publishable ? "可以进入发布流程" : "暂不能发布，请先处理下列事项";
  gate.append(title);
  output.append(gate);
  const list = document.createElement("div");
  list.className = "finding-list";
  (result.findings || []).forEach((finding) => {
    const item = document.createElement("article");
    item.className = `finding finding-${finding.severity} finding-risk-${finding.risk?.color || (finding.severity === "block" ? "red" : finding.severity === "warn" ? "yellow" : "blue")}`;
    const badge = document.createElement("span");
    badge.className = "finding-badge";
    badge.textContent = finding.risk?.label || (finding.severity === "block" ? "紧急阻断" : finding.severity === "warn" ? "预警" : "提示");
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = String(finding.message || "").replaceAll("tax_exclusive", "未含税").replaceAll("tax_inclusive", "含税");
    const note = document.createElement("small");
    note.textContent = finding.row ? `第 ${finding.row} 项 · 请核对相关资料` : "全局口径 · 请统一相关资料口径";
    body.append(title, note);
    item.append(badge, body);
    list.append(item);
  });
  if (!result.findings?.length) list.textContent = "未发现需要处理的事项。";
  output.append(list);
}

function renderTable(container, columns, rows) {
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach(([, label]) => { const cell = document.createElement("th"); cell.textContent = label; headRow.append(cell); });
  head.append(headRow);
  const body = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach(([key]) => { const cell = document.createElement("td"); cell.textContent = row[key] === null || row[key] === undefined ? "—" : String(row[key]); tr.append(cell); });
    body.append(tr);
  });
  table.append(head, body);
  container.replaceChildren(table);
}

function renderBlockedStep(title, message, actionLabel, view) {
  $("workspaceContent").innerHTML = `<div class="blocked-step"><span class="panel-label">WORK ASSIST</span><h3>${title}</h3><p>${message}</p><button id="blockedAction" class="button button-primary" type="button">${actionLabel}</button></div>`;
  $("blockedAction").addEventListener("click", () => setView(view));
}

function bindViewButtons() {
  document.querySelectorAll("#workspaceContent [data-view], #assistList [data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".workspace-tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.view === view));
  if (view === "overview") renderOverview();
  if (view === "boq") renderBoq();
  if (view === "plan") renderPlan();
  if (view === "review") renderReview();
  if (view === "dashboard") renderDashboard();
  if (view === "control") renderControl();
  renderAssist();
  updateContextBar();
}

async function loadHealth() {
  try {
    const health = await apiJson("/api/health");
    $("runtimeVersion").textContent = `v${health.runtime.version}`;
    $("releaseHighlights").textContent = `${health.runtime.version}：${health.release_highlights || "本次迭代已完成"}`;
    $("health").className = "health health-ok";
    $("health").textContent = "资料服务就绪";
  } catch (error) {
    $("health").className = "health health-error";
    $("health").textContent = "资料服务不可用";
    setError(error.message);
  }
}

async function loadDemo() {
  state.sample = await apiJson("/api/sample");
  await loadConnectors();
  state.projectId = state.sample.project_id;
  state.sourceId = state.sample.source_id;
  state.projectName = state.sample.project_name || "演示道路项目";
  state.sourceName = state.sample.source_name || "示例清单资料";
  state.boqRows = draftFromSample(state.sample.boq_rows);
  await loadWorkspace();
  setView("overview");
  setStatus(restoredStatus());
}

$("workspaceTabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-view]");
  if (tab) setView(tab.dataset.view);
});

$("loginForm").addEventListener("submit", submitLogin);
$("registerForm").addEventListener("submit", submitRegister);
$("logoutButton").addEventListener("click", logout);

async function boot() {
  await loadHealth();
  if (!(await restoreSession())) showAuth();
}

boot().catch((error) => setAuthMessage(error.message));
