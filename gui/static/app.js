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
  contractResult: null,
  drawingsResult: null,
  baselineResult: null,
  contractDraft: { contract_no: "", title: "", owner: "", contractor: "", contract_amount: "", tax_mode: "", signed_date: "", start_date: "", end_date: "" },
  obligationsDraft: [],
  drawingsDraft: [],
  baselineDraft: [],
  planDraft: [],
  planResult: null,
  changesResult: null,
  evidenceResult: null,
  events: [],
  eventDistillation: null,
  eventDistillText: "",
  eventCrossChecks: {},
  eventDraft: {
    title: "", summary: "", source_type: "SITE_DISCOVERY", event_type: "SITE_CONDITION", severity: "MEDIUM",
    discovered_by: "", zone: "", axis: "", level: "", tags: "", source_refs: "", dimensions: {},
    baseline: { contract: false, price: false, quantity: false, cost: false },
    technical_needed: false, technical_assessment: "", technical_feasible: false,
  },
  changesDraft: [],
  evidenceDraft: [],
  reviewResult: null,
  dashboard: null,
  p09: null,
  deployment: null,
  coordination: null,
  lineContracts: null,
  linePreview: null,
  sources: [],
  connectors: [],
  recognizers: [],
  basisCatalog: { categories: [], items: [] },
  basisReferences: [],
  sourceSearchTerm: "",
  sourceListExpanded: false,
  sourceListExpandedByTarget: {},
  search: {
    mode: "search",
    query: "",
    scope: "all",
    stage: "",
    category: "",
    response: null,
  },
  intakeReports: [],
  basisIntakeReports: [],
  exportWorkspace: { kind: "report", filename: "", directoryHandle: null },
  personnel: { users: [], audit_log: [], roles: [], assignment_catalog: null, policy: null },
};

const EXPORT_OPTIONS = [
  { kind: "report", label: "Word 兼容报告", route: "report", extension: "html", description: "项目报告（HTML 格式，可用 Word 打开）", requiresCostDetail: true },
  { kind: "boq.xlsx", label: "Excel 清单", route: "boq.xlsx", extension: "xlsx", description: "标准化清单明细", requiresCostDetail: false },
  { kind: "cost-plan.xlsx", label: "Excel 成本计划", route: "cost-plan.xlsx", extension: "xlsx", description: "成本计划和组价结果", requiresCostDetail: true },
  { kind: "bundle", label: "项目交换包", route: "bundle", extension: "zip", description: "项目状态、资料和识别稿的本地交换包", requiresCostDetail: true },
];

const PROJECT_ARCHIVE_AREAS = {
  overview: "项目资料库/项目初步信息",
  boq: "项目资料库/清单与计价资料",
  drawings: "项目资料库/图纸资料",
  baseline: "项目资料库/零号台账资料",
  plan: "项目资料库/成本计划与计价资料",
  changes: "项目资料库/变更与签证资料",
  evidence: "项目资料库/证据关联资料",
  review: "项目资料库/结算与收方资料",
};

const CONTRACT_ARCHIVE_CLASSES = [
  ["招标阶段", "招标文件、清单、最高投标限价、答疑、补遗和招标图纸"],
  ["投标阶段", "投标文件、投标报价、报价清单和技术/商务承诺"],
  ["定标阶段", "中标通知书、评标报告、澄清和定标资料"],
  ["合同阶段", "合同正文、补充协议、附件、专用条款和通用条款"],
  ["执行解释", "合同交底、会议纪要、发包人指令和批准文件"],
];

const BASIS_CATEGORIES = [
  ["policy", "政策法规"],
  ["pricing_basis", "定额与计价依据"],
  ["price_info", "造价信息"],
  ["market_price", "市场价格"],
  ["interface_snapshot", "外部接口快照"],
];

const EVENT_STATUS_LABELS = {
  DISCOVERED: "已发现", ASSESSED: "已判断", PLANNING: "方案规划", COMMERCIAL_REVIEW: "造价复核",
  DECIDED: "已决策", APPROVAL: "待/已批准", EXECUTING: "执行中", VERIFIED: "已验证",
  CLAIMING: "商务申报", SETTLEMENT: "结算中", AUDITING: "审计中", COLLECTION: "回收中", CLOSED: "已关闭",
};
const EVENT_TYPE_LABELS = {
  SITE_CONDITION: "现场条件", DESIGN_CHANGE: "设计变化", CONTRACT_REVIEW: "合同审查", COST_VARIANCE: "成本偏差",
  QUANTITY_VARIANCE: "数量偏差", SCHEDULE_VARIANCE: "工期偏差", TECH_OPTIMIZATION: "技术优化", AUDIT_FEEDBACK: "审计反馈",
};
const EVENT_SOURCE_LABELS = {
  SITE_DISCOVERY: "现场发现", DRAWING_REVIEW: "图纸审查", OWNER_INSTRUCTION: "业主指令", DESIGN_CHANGE: "设计变化",
  COST_VARIANCE: "成本偏差", QUANTITY_VARIANCE: "数量偏差", SCHEDULE_VARIANCE: "工期偏差", CONTRACT_REVIEW: "合同审查",
  TECH_OPTIMIZATION: "技术优化", AUDIT_FEEDBACK: "审计反馈",
};
const EVENT_NEXT_STATUS = {
  DISCOVERED: ["ASSESSED"], ASSESSED: ["PLANNING"], PLANNING: ["COMMERCIAL_REVIEW"],
  COMMERCIAL_REVIEW: ["PLANNING", "DECIDED"], DECIDED: ["APPROVAL"], APPROVAL: ["EXECUTING"],
  EXECUTING: ["VERIFIED"], VERIFIED: ["CLAIMING"], CLAIMING: ["SETTLEMENT"], SETTLEMENT: ["AUDITING"],
  AUDITING: ["COLLECTION"], COLLECTION: ["CLOSED"], CLOSED: [],
};
const OUTCOME_STATUS_LABELS = {
  NOT_FORMED: "未形成成果", PHYSICAL_FORMED: "实体成果", EVIDENCE_READY: "证据完整", SUBMITTED: "已申报",
  CONFIRMED: "已确认", REVENUE_RECOGNIZED: "收入成立", SETTLED: "已结算", CASH_REALIZED: "已回款",
  REJECTED: "已拒绝", ABANDONED: "已放弃",
};
const OUTCOME_TYPE_LABELS = { PHYSICAL: "实体", COMMERCIAL: "经营", CONTRACTUAL: "合同权利", SCHEDULE: "工期", CASH: "现金" };
const OUTCOME_NEXT_STATUS = {
  NOT_FORMED: ["PHYSICAL_FORMED", "REJECTED", "ABANDONED"], PHYSICAL_FORMED: ["EVIDENCE_READY", "REJECTED", "ABANDONED"],
  EVIDENCE_READY: ["SUBMITTED", "REJECTED", "ABANDONED"], SUBMITTED: ["CONFIRMED", "REJECTED", "ABANDONED"],
  CONFIRMED: ["REVENUE_RECOGNIZED", "SETTLED", "REJECTED", "ABANDONED"], REVENUE_RECOGNIZED: ["SETTLED", "REJECTED", "ABANDONED"],
  SETTLED: ["CASH_REALIZED", "REJECTED", "ABANDONED"], CASH_REALIZED: [], REJECTED: [], ABANDONED: [],
};

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function outcomeStatusLabel(status) {
  return OUTCOME_STATUS_LABELS[status] || status || "未形成成果";
}

function outcomeTypeLabel(type) {
  return OUTCOME_TYPE_LABELS[type] || type || "—";
}

function prioritizedCategoryIds(items, fallbackOrder, limit = 5) {
  const counts = new Map();
  const recentRank = new Map();
  items.forEach((item, itemIndex) => {
    const category = item.archive_category || item.category;
    if (category) {
      counts.set(category, (counts.get(category) || 0) + 1);
      recentRank.set(category, itemIndex);
    }
  });
  const ranked = fallbackOrder
    .map((id, index) => ({ id, count: counts.get(id) || 0, recent: recentRank.get(id) ?? -1, index }))
    .sort((left, right) => right.count - left.count || right.recent - left.recent || left.index - right.index)
    .map((item) => item.id);
  return ranked.slice(0, Math.min(limit, fallbackOrder.length));
}

function groupedCategoryOptions(entries, priorityIds, valueFor = (entry) => entry[0], labelFor = (entry) => entry[1]) {
  const priority = new Set(priorityIds);
  const option = (entry) => `<option value="${valueFor(entry)}">${labelFor(entry)}</option>`;
  const primary = entries.filter((entry) => priority.has(valueFor(entry))).map(option).join("");
  const rest = entries.filter((entry) => !priority.has(valueFor(entry))).map(option).join("");
  return `<optgroup label="常用/近期">${primary || '<option value="">暂无常用分类</option>'}</optgroup>${rest ? `<optgroup label="其他分类">${rest}</optgroup>` : ""}`;
}

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

function currentRole() {
  return state.auth.user?.role || "";
}

// The municipal workflow is a set of independent role workbenches, not a
// universal back-office menu.  Keep this catalog in the UI as a projection of
// the server-side permissions: it controls what a role can discover, while
// every write/read API still enforces its own permission at the boundary.
const ROLE_VIEW_ACCESS = {
  project_manager: ["overview", "dashboard", "search", "events", "p09", "coordination", "personnel"],
  cost_manager: ["overview", "search", "contract", "boq", "drawings", "baseline", "plan", "changes", "events", "evidence", "review", "p09", "coordination", "basis", "dashboard", "control"],
  cost_estimator: ["overview", "search", "contract", "boq", "baseline", "plan", "changes", "events", "evidence", "coordination", "basis"],
  technical_lead: ["overview", "drawings", "changes", "events", "evidence", "coordination"],
  production_manager: ["overview", "drawings", "changes", "events", "evidence", "coordination", "dashboard"],
  site_engineer: ["overview", "drawings", "events", "evidence", "coordination"],
  surveyor: ["overview", "drawings", "events", "evidence", "coordination"],
  quality_officer: ["overview", "drawings", "events", "evidence", "coordination"],
  lab_testing_officer: ["overview", "boq", "drawings", "events", "evidence", "coordination"],
  document_controller: ["overview", "search", "contract", "drawings", "evidence", "coordination"],
  safety_officer: ["overview", "drawings", "changes", "events", "evidence", "coordination"],
  procurement_officer: ["overview", "contract", "boq", "events", "evidence", "coordination"],
  warehouse_officer: ["overview", "boq", "events", "evidence", "coordination"],
  administrative_officer: ["overview", "coordination", "personnel"],
};

const ROLE_WORKBENCH_SPECS = {
  project_manager: { title: "项目经理指标台", focus: "只处理未执行、未纠偏、未变现、未成资产四个结果池。", outputs: "决策记录、资源协调、异常处置", workflow: ["看异常", "定责任", "做决策", "验结果"], execution: "只处理升级事项，不代替岗位录入事实。" },
  cost_manager: { title: "造价经理全权限工作台", focus: "以合同、清单、基线、成本、计量和结算守住经营闸门。", outputs: "目标成本、变更测算、计量结算、经营分析", workflow: ["取基准", "算量价", "审证据", "确认价值"], execution: "所有金额必须有来源、口径和人工确认。" },
  cost_estimator: { title: "造价员成果工作台", focus: "工程量、签证、计量和成本基础只在造价线上形成，敏感金额按权限脱敏。", outputs: "工程量台账、签证、计量基础、成本事实", workflow: ["接收资料", "整理工程量", "关联证据", "提交造价审核"], execution: "只维护造价基础，不修改技术结论和现场事实。" },
  technical_lead: { title: "技术负责人工作台", focus: "图纸、方案、交底、技术核定与分包技术边界形成技术证据。", outputs: "图纸会审、分包方案审查、技术交底、技术核定", workflow: ["拆分分包工作包", "审分包方案", "做技术交底", "技术放行/移交"], execution: "分包方案未通过技术闸门，不进入现场实施。" },
  production_manager: { title: "生产经理驾驶台", focus: "把技术放行的分包工作包转成计划、资源、实物量和偏差纠偏。", outputs: "分包计划、资源组织、进度实物量、纠偏移交", workflow: ["接收技术放行", "排产配资源", "盯分包实物量", "纠偏并量验移交"], execution: "只推动分包生产落地，不代填测量、质量和造价成果。" },
  site_engineer: { title: "施工员/测量员工作台", focus: "记录现场事实、完成量和施工事件，成果交技术、质量和造价线验证。", outputs: "现场事实、日完成量、施工事件、基础实测", workflow: ["发现现场", "记录位置时间", "提交完成量", "等待复核"], execution: "事实一次录入，绑定 WBS/位置/事件后提交验证。" },
  surveyor: { title: "测量员成果工作台", focus: "放样、坐标、标高和实测工程量只由测量岗位形成。", outputs: "放样记录、坐标标高、实测工程量", workflow: ["领测量任务", "现场实测", "上传成果", "复核签认"], execution: "测量数据只追加版本，不覆盖原始实测。" },
  quality_officer: { title: "质量负责人工作台", focus: "工序检查、整改复验和实体验收形成物理验收证据。", outputs: "工序检查、检验批、整改复验、验收结论", workflow: ["接收报验", "现场检查", "退回整改", "复验通过"], execution: "不合格必须退回源岗位，不能用口头结论放行。" },
  lab_testing_officer: { title: "试验检测工作台", focus: "进场批次、取样、试验报告与材料事实相互校验。", outputs: "取样记录、试验报告、检测台账、批次校验", workflow: ["核对批次", "取样送检", "登记报告", "关联材料"], execution: "报告必须绑定材料批次和工程位置，异常立即标记。" },
  document_controller: { title: "资料员归档工作台", focus: "报验、版本、证据完整性和数字资产归档，不制造业务事实。", outputs: "报验资料、版本台账、证据包、数字资产", workflow: ["收成果", "查完整性", "归档版本", "形成资产"], execution: "只检查和归档，不代替专业岗位补造事实。" },
  safety_officer: { title: "安全员闭环工作台", focus: "检查、隐患、整改和安全验收形成可追溯证据。", outputs: "安全检查、隐患单、整改复查、安全验收", workflow: ["巡检发现", "下发隐患", "跟踪整改", "复查关闭"], execution: "隐患必须有责任人、期限和关闭证据。" },
  procurement_officer: { title: "采购员物资工作台", focus: "以造价基准为采购边界，订单、到货和价量偏差回流底座。", outputs: "采购计划、询价比价、订单、到货记录", workflow: ["引用基准", "询价比价", "下单跟货", "核对到货"], execution: "采购不改造价基准，超量超价只形成预警并提交确认。" },
  warehouse_officer: { title: "仓管员物资工作台", focus: "以采购到货为基数管理收发存、超领、节余和盘点。", outputs: "入库、出库、退库、库存、盘点台账", workflow: ["核到货", "验收入库", "按单发料", "盘点对账"], execution: "收发存绑定采购批次和施工领用，不跨岗改采购事实。" },
  administrative_officer: { title: "行政协同工作台", focus: "只管理被授权的人员与协同关系，不进入专业事实工作台。", outputs: "人员名册、授权记录、交接留痕、协同通知", workflow: ["接收授权", "维护名册", "记录交接", "回报项目经理"], execution: "没有项目经理授权，不增删人员或改变岗位权限。" },
};

const ROLE_OPERATION_MANUALS = {
  project_manager: { start: "打开经营看板，先看未执行、未纠偏、未变现、未成资产四类结果池。", save: "在工程事件、协同和 P09 中保存责任、决策、确认与结果。", handoff: "需要加人时进入当前项目的人员管理，录入姓名和岗位并把初始密码交给本人。", check: "只处理升级事项，不代替专业岗位录入合同、工程量、技术或现场事实。" },
  cost_manager: { start: "先建立当前项目，再接入合同、清单、图纸和外部依据。", save: "依次保存 P01–P08 的造价事实、证据和人工审核结果。", handoff: "金额必须带来源、口径和证据；P09 只读取已有事实，不另建金额账。", check: "确认前检查数量、单价、税口径和证据链是否完整。" },
  cost_estimator: { start: "从项目资料库接收合同、清单和现场资料，先核对编码、单位和数量。", save: "保存 P02、P04、P05、P06、P07 的造价基础和证据关联。", handoff: "把待确认项和完整依据提交造价经理审核。", check: "只维护造价基础，不修改技术结论、现场事实和责任线。" },
  technical_lead: { start: "先核对当前图纸版本、技术条件和现场问题，再拆清分包工作包边界。", save: "保存 P03 图纸、分包方案审查、P06 技术变更、交底和技术证据。", handoff: "方案、核定和交底完成专业确认后，把技术放行交生产经理组织实施。", check: "没有图纸版本、方案确认和技术交底，不进入分包现场执行。" },
  production_manager: { start: "先接收技术放行，核对分包工作包、责任人、计划和资源条件。", save: "保存分包计划、资源组织、进度实物量、工程事件、纠偏和证据。", handoff: "把生产线事实提交施工/测量、质量和造价线复核，异常通过协同任务回报。", check: "没有技术放行、责任人和资源计划不下达；完成量未复核不关闭。" },
  site_engineer: { start: "接收现场任务，先记录项目位置、WBS、时间和事件。", save: "保存现场事实、日完成量、施工事件和基础实测。", handoff: "提交技术、质量、测量和造价岗位复核。", check: "原始事实只追加版本，不覆盖历史记录。" },
  surveyor: { start: "接收测量任务，核对控制点、图纸版本和测量范围。", save: "保存放样、坐标、标高和实测工程量成果。", handoff: "关联图纸、位置和证据后提交复核签认。", check: "测量数据只追加版本，不用口头结论替代实测。" },
  quality_officer: { start: "接收报验，核对工序、检验批和现场位置。", save: "保存检查、整改、复验和验收结论。", handoff: "不合格退回源岗位，复验通过后形成质量证据。", check: "没有整改和复验依据，不得放行。" },
  lab_testing_officer: { start: "先核对进场批次、取样计划和材料来源。", save: "保存取样、试验报告、检测台账和批次校验。", handoff: "把报告绑定材料批次、位置和证据后提交关联。", check: "报告缺批次或位置时标记异常，不猜测补齐。" },
  document_controller: { start: "接收各岗位成果，先检查文件、版本和签认完整性。", save: "保存报验资料、版本台账、证据包和数字资产。", handoff: "不完整的资料退回源岗位，完整成果再归档。", check: "只检查和归档，不代替专业岗位制造事实。" },
  safety_officer: { start: "先开展现场巡检，记录隐患位置、责任人和期限。", save: "保存安全检查、隐患单、整改复查和安全验收。", handoff: "把整改任务交责任岗位，复查关闭后形成证据。", check: "隐患必须有责任人、期限和关闭证据。" },
  procurement_officer: { start: "先引用已确认的造价基准和采购需求。", save: "保存询价比价、订单、供应商和到货记录。", handoff: "超量、超价或偏差提交造价线和生产线确认。", check: "采购不改造价基准，不用采购价替代合同事实。" },
  warehouse_officer: { start: "先核对采购到货批次、验收状态和领料单。", save: "保存入库、出库、退库、库存和盘点台账。", handoff: "收发存绑定采购批次和施工领用后提交核对。", check: "只处理物资收发存，不进入 P04 零号台账。" },
  administrative_officer: { start: "先确认项目经理对当前项目的人员管理授权。", save: "在当前项目维护人员名册、授权记录和交接留痕。", handoff: "新增人员只录入姓名和岗位，把初始密码交本人并回报项目经理。", check: "没有授权不增删人员、不改变岗位权限。" },
};

// Subcontract management is deliberately a thin workflow projection over the
// existing Core Event, Evidence, Verification and Coordination surfaces.  It
// does not create a second contract or amount ledger; each line only owns its
// professional gate and hands the result to the next accountable role.
const ROLE_SUBCONTRACT_WORKFLOWS = {
  technical_lead: {
    title: "技术负责人 · 分包技术工作流",
    line: "技术线",
    focus: "先把分包范围、接口、图纸版本和技术放行锁定，再允许生产线组织实施。",
    steps: [
      ["拆分工作包", "按 WBS、图纸版本、位置和接口拆清分包范围与技术条件。"],
      ["审查方案", "审核分包施工方案、专项措施、样板/首件和风险控制。"],
      ["完成交底", "完成图纸会审、技术交底和接口确认，形成 Event + Evidence。"],
      ["技术放行", "技术核定或变更经人工确认后，交生产经理组织执行。"],
      ["验收移交", "按技术标准复核成果，交质量、资料和造价线关联。"],
    ],
    outputs: "分包技术边界、方案审查、交底记录、技术核定/验收证据",
    handoff: "技术负责人 → 生产经理 → 施工员/分包执行；争议回到 Core Event。",
    gate: "没有图纸版本、方案确认和技术交底，不得进入分包现场实施。",
  },
  production_manager: {
    title: "生产经理 · 分包生产工作流",
    line: "生产线",
    focus: "把已技术放行的分包工作包转成计划、资源、完成量和关闭证据。",
    steps: [
      ["接收技术放行", "核对工作包、图纸版本、技术交底、责任人和执行前置条件。"],
      ["排产配资源", "编制计划、接口顺序，落实分包人员、机械、材料和作业面。"],
      ["跟踪实物量", "按位置/WBS记录进度、质量安全接口和分包偏差。"],
      ["组织纠偏", "建立协同任务，推动整改/变更并记录人的确认和结果。"],
      ["量验移交", "完成量交测量、质量、造价线复核，资料归档后关闭。"],
    ],
    outputs: "分包计划、资源组织、进度实物量、偏差整改、移交记录",
    handoff: "生产经理 → 施工员/分包执行；完成量 → 测量、质量、造价线复核。",
    gate: "没有技术放行、责任人和资源计划，不下达执行；完成量未复核不关闭。",
  },
};

function currentRoles() {
  const assigned = state.auth.user?.roles;
  if (Array.isArray(assigned) && assigned.length) return assigned;
  return currentRole() ? [currentRole()] : [];
}

function visibleViewsForUser() {
  const views = new Set();
  currentRoles().forEach((role) => (ROLE_VIEW_ACCESS[role] || ["overview", "search", "events", "coordination"]).forEach((view) => views.add(view)));
  if (canManagePersonnel()) views.add("personnel");
  if (!isCostManager()) views.delete("control");
  return views;
}

function canAccessView(view) {
  return visibleViewsForUser().has(view);
}

function workbenchSpec() {
  return ROLE_WORKBENCH_SPECS[currentRole()] || ROLE_WORKBENCH_SPECS.site_engineer;
}

function renderSubcontractWorkflowPanels() {
  const workflows = currentRoles().map((role) => ROLE_SUBCONTRACT_WORKFLOWS[role]).filter(Boolean);
  if (!workflows.length) return "";
  return workflows.map((workflow) => {
    const steps = workflow.steps.map(([title, detail], index) => `<article class="subcontract-step"><span class="subcontract-step-index">${index + 1}</span><div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div></article>`).join("");
    return `<section class="overview-panel subcontract-workflow-panel">
      <div class="surface-title"><div><span class="panel-label">SUBCONTRACT WORKFLOW · ${escapeHtml(workflow.line)}</span><h3>${escapeHtml(workflow.title)}</h3></div><span class="surface-caption">只使用现有 Event → Evidence → Verification → Outcome</span></div>
      <div class="capability-intro"><strong>责任边界：</strong><span>${escapeHtml(workflow.focus)}</span></div>
      <div class="subcontract-flow-grid">${steps}</div>
      <div class="subcontract-meta-grid">
        <div><span class="card-label">应形成成果</span><strong>${escapeHtml(workflow.outputs)}</strong></div>
        <div><span class="card-label">交接路径</span><strong>${escapeHtml(workflow.handoff)}</strong></div>
        <div><span class="card-label">人工闸门</span><strong>${escapeHtml(workflow.gate)}</strong></div>
      </div>
      <div class="button-row subcontract-actions"><button class="button button-quiet" data-view="coordination" type="button">进入协同工作流</button><span class="request-status">任务、证据、确认和关闭均在现有协同界面留痕。</span></div>
    </section>`;
  }).join("");
}

function renderRoleFlowSummary() {
  const roles = state.lineContracts?.role_flows?.roles || {};
  const active = currentRoles().map((role) => ({ role, flow: roles[role] })).filter((item) => item.flow);
  if (!active.length) return "";
  const cards = active.map(({ role, flow }) => `<article class="role-flow-card"><div class="surface-title"><div><span class="panel-label">ROLE HANDOFF</span><h3>${escapeHtml(flow.label || role)}</h3></div><span class="surface-caption">责任链 v${escapeHtml(state.lineContracts?.role_flows?.version || "1.0")}</span></div><div class="role-flow-sequence">${(flow.workflow || []).map((step, index) => `<span><b>${index + 1}</b>${escapeHtml(step)}</span>`).join('<i>→</i>')}</div><div class="role-flow-details"><div><span>接收</span><small>${escapeHtml((flow.inputs || []).join("、"))}</small></div><div><span>交付给</span><small>${escapeHtml((flow.next_roles || []).map((next) => roles[next]?.label || next).join("、") || "项目经理")}</small></div><div><span>升级到</span><small>${escapeHtml((flow.escalates_to || []).map((next) => roles[next]?.label || next).join("、") || "无")}</small></div></div><p class="business-note"><strong>闸门：</strong>${escapeHtml(flow.gate || "成果必须经责任人确认后进入下一环节。")}</p></article>`).join("");
  return `<section class="overview-panel role-flow-contract-panel"><div class="surface-title"><div><span class="panel-label">ROLE RESPONSIBILITY CHAIN</span><h3>本岗位责任链</h3></div><span class="surface-caption">造价主线 · 专业审核 · 生产兑现 · 项目经理决策</span></div><div class="role-flow-card-grid">${cards}</div><p class="business-note">工作流只推动现有 Event、Action、Evidence、Verification、Outcome；岗位不能跨线代改事实。</p></section>`;
}

function isProjectManager() {
  return currentRole() === "project_manager";
}

function isCostManager() {
  return currentRole() === "cost_manager";
}

function isEstimator() {
  return currentRole() === "cost_estimator";
}

function isAdministrativeOfficer() {
  return currentRole() === "administrative_officer";
}

function isManager() {
  return isCostManager();
}

function canManagePersonnel() {
  return Boolean(state.auth.user?.permissions?.includes("manage_personnel"));
}

function canAuthorizePersonnel() {
  return Boolean(state.auth.user?.permissions?.includes("authorize_personnel_admin"));
}

function canViewCostDetail() {
  return Boolean(state.auth.user?.can_view_cost_detail);
}

function isKpiOnly() {
  return isProjectManager();
}

function showAuth(message = "") {
  $("authShell").hidden = false;
  $("workspaceShell").hidden = true;
  $("globalSearchForm").hidden = true;
  $("userSession").hidden = true;
  setAuthMessage(message);
}

function showWorkspace(user) {
  state.auth.user = user;
  $("authShell").hidden = true;
  $("workspaceShell").hidden = false;
  $("globalSearchForm").hidden = !canAccessView("search");
  $("userSession").hidden = false;
  $("userRole").textContent = `${user.role_label} · ${user.username}`;
  $("personnelTab").hidden = !canAccessView("personnel");
  $("controlTab").hidden = !canAccessView("control");
  const spec = workbenchSpec();
  $("workspaceTitle").textContent = spec.title;
  $("workspaceTitle").title = spec.focus;
  document.querySelectorAll("#workspaceTabs .workspace-tab").forEach((tab) => {
    const view = tab.dataset.view;
    tab.hidden = !canAccessView(view);
  });
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
  if (state.events.some((event) => event.alerts?.length)) return "工程事件存在预警";
  if (state.events.length) return `工程事件 ${state.events.length} 项`;
  if (state.reviewResult) return state.reviewResult.publishable ? "初审通过" : "初审发现需处理事项";
  if (state.changesResult?.summary?.pending_count) return "存在待审批变更";
  if (state.planResult) return "成本计划已生成";
  if (state.baselineResult) return "零号台账已建立";
  if (state.boqResult) return "清单资料已接入";
  if (state.contractResult || state.drawingsResult || state.evidenceResult) return "项目资料已建立";
  return "准备开始";
}

function applyWorkspace(workspace) {
  if (!workspace) return;
  state.workspace = workspace;
  state.projectName = workspace.project?.name || state.projectName;
  state.sources = workspace.sources || [];
  state.basisReferences = workspace.basis_references || [];
  state.events = workspace.events || state.events || [];
  state.eventDistillation = workspace.event_distillation || state.eventDistillation || null;
  state.coordination = workspace.collaboration || state.coordination || null;
  if (state.sources.length && !state.fileName) state.sourceName = state.sources[state.sources.length - 1].name;
  const boq = workspace.boq?.result;
  const contract = workspace.contract?.result;
  const drawings = workspace.drawings?.result;
  const baseline = workspace.baseline?.result;
  const plan = workspace.cost_plan?.result;
  const changes = workspace.changes?.result;
  const evidence = workspace.evidence?.result;
  const review = workspace.review?.result;
  if (contract) state.contractResult = contract;
  if (boq) {
    state.boqResult = boq;
    state.boqRows = draftFromItems(boq.items);
  }
  if (drawings) state.drawingsResult = drawings;
  if (baseline) state.baselineResult = baseline;
  if (plan) {
    state.planResult = plan;
    state.planDraft = (plan.items || []).map((item) => ({
      ...item,
      contractPrice: item.unit_price ?? "",
      marketPrice: "",
    }));
  }
  if (changes) state.changesResult = changes;
  if (evidence) state.evidenceResult = evidence;
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
    await loadEventKernel();
    await refreshDashboard();
    await refreshCoordination();
  } catch (error) {
    await ensureProject();
    await loadEventKernel();
    await refreshDashboard();
    await refreshCoordination();
  }
}

async function refreshWorkspace() {
  applyWorkspace(await apiJson(`/api/workspace?project_id=${encodeURIComponent(state.projectId)}`));
  await loadEventKernel();
  await refreshDashboard();
  await refreshCoordination();
  renderDashboardIfVisible();
  await refreshP09();
}

async function loadEventKernel() {
  try {
    const response = await apiJson(`/api/event-kernel?project_id=${encodeURIComponent(state.projectId)}`);
    state.events = response.events || [];
    state.eventDistillation = response.distillation || null;
    state.eventCatalog = response.catalog || state.eventCatalog;
  } catch (_) {
    state.events = [];
    state.eventDistillation = null;
  }
}

async function refreshDashboard() {
  try {
    state.dashboard = await apiJson(`/api/dashboard?project_id=${encodeURIComponent(state.projectId)}`);
  } catch (_) {
    state.dashboard = null;
  }
}

async function refreshP09() {
  try {
    state.p09 = await apiJson("/api/p09?project_id=" + encodeURIComponent(state.projectId));
  } catch (_) {
    state.p09 = null;
  }
}

async function refreshCoordination() {
  try {
    state.coordination = await apiJson("/api/collaboration?project_id=" + encodeURIComponent(state.projectId));
    state.lineContracts = await apiJson("/api/line-contracts");
  } catch (_) {
    state.coordination = null;
  }
}

function renderP09() {
  const result = state.p09;
  if (!result) {
    renderBlockedStep("P09 全过程成果经营", "成果经营数据暂时不可用，请确认已经登录并建立项目。", "回到项目总览", "overview");
    refreshP09().then(() => { if (state.view === "p09") renderP09(); });
    return;
  }
  const summary = result.summary || {};
  const funnel = result.funnel || [];
  const leaks = result.value_leaks || [];
  const queue = result.daily_queue || [];
  const metrics = [
    ["事件", summary.event_count || 0],
    ["未闭环", summary.open_event_count || 0],
    ["成果状态", summary.outcome_count || 0],
    ["价值泄漏", dashboardMoney(summary.value_leak_total) + " · " + (summary.value_leak_count || 0) + "段"],
  ];
  $("workspaceContent").innerHTML =
    '<div class="surface-title"><div><span class="panel-label">P09 OUTCOME MANAGEMENT</span><h3>全过程成果经营台</h3></div><span class="surface-caption">只读派生：Event → Evidence → Outcome → Value Realization</span></div>' +
    '<div class="capability-intro"><strong>不新增专业金额事实。</strong><span>P09 读取 P01–P08 与工程事件内核，只把成果转化状态、价值泄漏和异常经营队列整理成可执行视图。</span></div>' +
    '<div id="p09Metrics" class="dashboard-metrics"></div>' +
    '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">OUTCOME FUNNEL</span><h3>成果转化漏斗</h3></div><span class="surface-caption">实体形成不等于事件关闭，回款状态独立推进</span></div><div id="p09Funnel" class="outcome-funnel"></div></section>' +
    '<div class="dashboard-grid"><section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">VALUE LEAK</span><h3>价值泄漏</h3></div></div><div id="p09Leaks" class="dashboard-issue-list"></div></section>' +
    '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">DAILY QUEUE</span><h3>今日经营队列</h3></div></div><div id="p09Queue" class="dashboard-issue-list"></div></section></div>' +
    '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">BOUNDARY</span><h3>能力边界</h3></div><span class="surface-caption">单一事实源 · 历史追加 · 派生结果</span></div><div id="p09Rules" class="capability-coverage"></div></section>';
  $("p09Metrics").replaceChildren(...metrics.map(([label, value]) => { const item = document.createElement("div"); item.className = "dashboard-metric"; const title = document.createElement("span"); title.className = "dashboard-metric-label"; title.textContent = label; const strong = document.createElement("strong"); strong.textContent = String(value); item.append(title, strong); return item; }));
  $("p09Funnel").replaceChildren(...funnel.map((stage, index) => { const item = document.createElement("div"); item.className = "outcome-funnel-stage"; const label = document.createElement("span"); label.textContent = stage.label || stage.stage; const amount = document.createElement("strong"); amount.textContent = dashboardMoney(stage.amount); const rate = document.createElement("small"); rate.textContent = index ? (stage.conversion_rate == null ? "—" : dashboardPercent(stage.conversion_rate)) + " 转化" : (stage.event_count || 0) + " 项事件"; item.append(label, amount, rate); return item; }));
  const leakTarget = $("p09Leaks");
  if (!leaks.length) leakTarget.textContent = "当前没有可计算的价值泄漏。";
  else leakTarget.replaceChildren(...leaks.slice(0, 8).map((leak) => { const item = document.createElement("article"); item.className = "dashboard-issue risk-yellow"; const badge = document.createElement("span"); badge.textContent = leak.code || "LEAK"; const body = document.createElement("div"); const title = document.createElement("strong"); title.textContent = (leak.title || leak.event_id) + " · " + dashboardMoney(leak.amount); const note = document.createElement("small"); note.textContent = (leak.from_stage || "") + " → " + (leak.to_stage || "") + " · " + (leak.reason || "待补充原因"); body.append(title, note); item.append(badge, body); return item; }));
  const queueTarget = $("p09Queue");
  if (!queue.length) queueTarget.textContent = "当前没有待处理异常。";
  else queueTarget.replaceChildren(...queue.slice(0, 8).map((entry) => { const item = document.createElement("article"); item.className = "dashboard-issue risk-blue"; const badge = document.createElement("span"); badge.textContent = entry.event_id || "Event"; const body = document.createElement("div"); const title = document.createElement("strong"); title.textContent = entry.title || "工程事件"; const note = document.createElement("small"); note.textContent = eventStatusLabel(entry.event_status) + " · " + outcomeStatusLabel(entry.outcome_status) + " · " + (entry.days_open == null ? "时钟待补" : "已打开 " + entry.days_open + " 天"); body.append(title, note); item.append(badge, body); return item; }));
  const ruleTarget = $("p09Rules");
  ruleTarget.replaceChildren(...Object.entries(result.rules || {}).map(([key, value]) => { const item = document.createElement("div"); item.className = "coverage-item"; const title = document.createElement("strong"); title.textContent = key; const status = document.createElement("small"); status.textContent = value ? "已启用" : "未启用"; item.append(title, status); return item; }));
}

function coordinationEventOptions(selected = "") {
  const events = state.coordination?.event_index || state.events || [];
  return '<option value="">请选择 Core Event</option>' + events.map((event) => {
    const id = event.event_id || "";
    const label = `${id} · ${event.title || "工程事件"}`;
    return `<option value="${escapeHtml(id)}" ${id === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
}

function renderCoordination() {
  const result = state.coordination;
  if (!result) {
    renderBlockedStep("组织协同与关系管理", "协同数据暂时不可用，请确认已经登录并建立项目。", "返回项目总览", "overview");
    refreshCoordination().then(() => { if (state.view === "coordination") renderCoordination(); });
    return;
  }
  const workflow = result.workflow || {};
  const tasks = workflow.tasks || [];
  const decisions = workflow.decisions || [];
  const relations = result.relationships || [];
  const adaptations = result.line_adaptations || [];
  const editable = !isKpiOnly();
  const contracts = state.lineContracts?.lines || [];
  const taskRows = tasks.length ? tasks.map((task) => `<article class="dashboard-issue risk-blue"><span>${escapeHtml(task.task_id || "TASK")}</span><div><strong>${escapeHtml(task.title || "协同任务")}</strong><small>${escapeHtml(task.role || "") } · ${escapeHtml(task.status || "OPEN")} · ${escapeHtml(task.event_id || "")}</small></div>${editable ? `<button class="button button-quiet" data-task-id="${escapeHtml(task.task_id)}" data-task-status="CLOSED" type="button">关闭</button>` : ""}</article>`).join("") : '<p class="empty-state">暂无协同任务。先把责任线和 Core Event 绑定起来。</p>';
  const decisionRows = decisions.length ? decisions.map((decision) => `<article class="dashboard-issue ${decision.status === "CONFIRMED" ? "risk-blue" : "risk-yellow"}"><span>${escapeHtml(decision.decision_type || "DEC")}</span><div><strong>${escapeHtml(decision.event_id || "工程事件")}</strong><small>${escapeHtml(decision.status || "PROPOSED")} · ${escapeHtml(decision.reason || "")}${decision.confirmed_by ? ` · ${escapeHtml(decision.confirmed_by)} 已确认` : " · 等待人工确认"}</small></div>${editable && decision.status !== "CONFIRMED" ? `<button class="button button-quiet" data-decision-id="${escapeHtml(decision.decision_id)}" type="button">人工确认</button>` : ""}</article>`).join("") : '<p class="empty-state">暂无 GO / OPTIMIZE / HOLD / REJECT 决策记录。</p>';
  const relationRows = relations.length ? relations.map((relation) => `<tr><td>${escapeHtml(relation.relation_type || "")}</td><td>${escapeHtml(relation.from_type || "")} · ${escapeHtml(relation.from_id || "")}</td><td>${escapeHtml(relation.to_type || "")} · ${escapeHtml(relation.to_id || "")}</td><td>${escapeHtml(relation.created_by || "")}</td></tr>`).join("") : '<tr><td colspan="4">暂无关系记录。关系只追加，不删除原 Event。</td></tr>';
  const adaptationRows = adaptations.length ? adaptations.slice().reverse().map((item) => `<article class="dashboard-issue risk-blue"><span>${escapeHtml(item.line || "line")}</span><div><strong>${escapeHtml(item.adaptation_id || "")}</strong><small>${escapeHtml(item.record_count || 0)} 条 · ${escapeHtml(item.confirmed_by || "")} · ${escapeHtml(item.mapping_targets?.join(" → ") || "")}</small></div></article>`).join("") : '<p class="empty-state">尚无已确认的三线数据接入。</p>';
  const contractCards = contracts.map((contract) => { const responsibility = contract.responsibility || {}; return `<div class="coverage-item"><strong>${escapeHtml(contract.label || contract.line)}</strong><small>v${escapeHtml(contract.version || "1.0")} · 必填 ${escapeHtml((contract.required || []).join("、"))}</small><small>系统自动归属：${escapeHtml(responsibility.head_label || "主管负责人")}（${escapeHtml(responsibility.head_role || "")})</small><small>可修改：仅对应主管负责人；${escapeHtml(contract.human_confirmation || "必须人工确认")}</small></div>`; }).join("");
  const editor = editable ? `
    <section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">COORDINATION WORKFLOW</span><h3>协同工作流</h3></div><span class="surface-caption">分派 → 复核 → 人工确认 → 关闭</span></div>
      <div class="coordination-form-grid">
        <form id="coordTaskForm" class="data-entry-card"><h4>创建协同任务</h4><label>任务标题<input id="coordTaskTitle" required placeholder="例如：技术负责人确认变更方案" /></label><label>责任线<select id="coordTaskRole"><option value="production">生产线</option><option value="technical">技术线</option><option value="cost">造价线</option><option value="project_manager">项目经理</option><option value="owner">业主</option><option value="supervision">监理</option><option value="audit">审计</option></select></label><label>Core Event<select id="coordTaskEvent" required>${coordinationEventOptions()}</select></label><label>目标路径<input id="coordTaskPath" placeholder="Core.event.technical_track" /></label><label>截止时间<input id="coordTaskDue" type="datetime-local" /></label><button class="button button-primary" type="submit">建立任务</button></form>
        <form id="coordDecisionForm" class="data-entry-card"><h4>记录人工决策</h4><label>Core Event<select id="coordDecisionEvent" required>${coordinationEventOptions()}</select></label><label>决策类型<select id="coordDecisionType"><option>GO</option><option>OPTIMIZE</option><option>HOLD</option><option>REJECT</option></select></label><label>依据/理由<textarea id="coordDecisionReason" required placeholder="数据只能提供依据，填写人的判断理由"></textarea></label><label>依据引用<input id="coordDecisionBasis" placeholder="纪要-01,图纸-A-02" /></label><label class="check-line"><input id="coordDecisionConfirm" type="checkbox" /> 我已完成人工确认并承担该决策</label><button class="button button-primary" type="submit">保存决策</button></form>
        <form id="coordRelationForm" class="data-entry-card"><h4>建立专用关系</h4><label>关系类型<select id="coordRelationType"><option value="EVENT_TO_SOURCE">Event → Source</option><option value="EVENT_TO_TASK">Event → Task</option><option value="EVENT_TO_PERSON">Event → Person</option><option value="EVENT_TO_CAPABILITY">Event → P01–P08</option><option value="EVENT_TO_OUTCOME">Event → Outcome</option><option value="EVENT_PARENT">父子事件</option><option value="EVENT_SPLIT_FROM">拆分来源</option><option value="EVENT_CANCELLED_BY">取消关系</option></select></label><label>起点标识<input id="coordRelationFrom" required placeholder="EV-2026-0001" /></label><label>终点类型<input id="coordRelationToType" value="capability" /></label><label>终点标识<input id="coordRelationTo" required placeholder="P07 / source-id / TASK-id" /></label><label>依据引用<input id="coordRelationBasis" placeholder="纪要-01" /></label><button class="button button-primary" type="submit">保存关系</button></form>
      </div>
    </section>
    <section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">LINE ADAPTERS</span><h3>生产线 / 技术线 / 造价线接入</h3></div><span class="surface-caption">预览只读；确认后才写入 Core</span></div><div class="data-entry-card"><div class="coordination-form-grid"><label>业务线<select id="lineAdapterLine"><option value="production">生产线</option><option value="technical">技术线</option><option value="cost">造价线</option></select></label><label>记录 JSON<textarea id="lineAdapterRecords" rows="9" placeholder='[{"record_id":"PR-01","event_id":"EV-2026-0001","occurred_at":"2026-08-18T09:00:00+08:00","actor":"现场负责人","status":"COMPLETED","progress":100,"quantity":12,"unit":"m3","evidence_refs":["现场照片-01"]}]'></textarea></label></div><div class="button-row"><button id="lineAdapterPreview" class="button button-quiet" type="button">只读预览</button><button id="lineAdapterConfirm" class="button button-primary" type="button" disabled>人工确认并映射</button></div><div id="lineAdapterStatus" class="request-status">所有数据接入都必须由登录人员确认；系统不会代替 GO / OPTIMIZE / HOLD / REJECT。</div></div></section>` : "";
  $("workspaceContent").innerHTML = `<div class="surface-title"><div><span class="panel-label">COLLABORATION / RELATION GRAPH</span><h3>组织协同与专用关系管理</h3></div><span class="surface-caption">数据提供依据，责任人做确认，关系只追加留痕</span></div><div class="capability-intro"><strong>负熵规则：</strong><span>三条业务线不建立新金额台账，只把已确认记录映射到现有 Core、P01–P08 和 Outcome。</span></div><div class="dashboard-grid"><section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">TASK QUEUE</span><h3>协同任务</h3></div></div><div class="dashboard-issue-list">${taskRows}</div></section><section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">DECISION LOG</span><h3>人工决策记录</h3></div></div><div class="dashboard-issue-list">${decisionRows}</div></section></div>${editor}<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">RELATION MANAGEMENT</span><h3>关系台账</h3></div><span class="surface-caption">Event / Source / Person / Capability / Outcome</span></div><div class="table-scroll"><table><thead><tr><th>关系</th><th>起点</th><th>终点</th><th>建立人</th></tr></thead><tbody>${relationRows}</tbody></table></div></section><section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">ADAPTER AUDIT</span><h3>三线接入留痕</h3></div></div><div class="dashboard-issue-list">${adaptationRows}</div></section><section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">CONTRACTS</span><h3>数据契约与人工闸门</h3></div></div><div class="capability-coverage">${contractCards}</div></section>`;
  if (!editable) return;
  const lineHeadRoles = Object.fromEntries(contracts.map((contract) => [contract.line, contract.responsibility?.head_role || ""]));
  const lineAdapterCanConfirm = () => currentRoles().includes(lineHeadRoles[$("lineAdapterLine")?.value || ""]);
  const refreshLineConfirmBoundary = () => {
    const confirmButton = $("lineAdapterConfirm");
    if (!confirmButton) return;
    confirmButton.disabled = !state.linePreview || !lineAdapterCanConfirm();
    if (!lineAdapterCanConfirm()) $("lineAdapterStatus").textContent = "当前责任线由系统自动归属；只有对应主管负责人可以确认或修改。";
  };
  $("lineAdapterLine").addEventListener("change", refreshLineConfirmBoundary);
  refreshLineConfirmBoundary();
  $("coordTaskForm").addEventListener("submit", async (event) => { event.preventDefault(); try { await apiJson("/api/collaboration/task", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, title: $("coordTaskTitle").value, role: $("coordTaskRole").value, event_id: $("coordTaskEvent").value, target_path: $("coordTaskPath").value, due_at: $("coordTaskDue").value }) }); await refreshWorkspace(); setView("coordination"); } catch (error) { setError(error.message); } });
  $("coordDecisionForm").addEventListener("submit", async (event) => { event.preventDefault(); try { await apiJson("/api/collaboration/decision", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, event_id: $("coordDecisionEvent").value, decision_type: $("coordDecisionType").value, reason: $("coordDecisionReason").value, basis_refs: $("coordDecisionBasis").value.split(",").map((item) => item.trim()).filter(Boolean), confirm: $("coordDecisionConfirm").checked }) }); await refreshWorkspace(); setView("coordination"); } catch (error) { setError(error.message); } });
  $("coordRelationForm").addEventListener("submit", async (event) => { event.preventDefault(); try { await apiJson("/api/relationships", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, relation_type: $("coordRelationType").value, from_type: "event", from_id: $("coordRelationFrom").value, to_type: $("coordRelationToType").value, to_id: $("coordRelationTo").value, basis_refs: $("coordRelationBasis").value.split(",").map((item) => item.trim()).filter(Boolean) }) }); await refreshWorkspace(); setView("coordination"); } catch (error) { setError(error.message); } });
  $("lineAdapterPreview").addEventListener("click", async () => { try { const records = JSON.parse($("lineAdapterRecords").value || "[]"); state.linePreview = await apiJson("/api/line-adapter/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, line: $("lineAdapterLine").value, records }) }); const responsibility = state.linePreview.preview.responsibility || {}; $("lineAdapterStatus").textContent = `预览通过：${state.linePreview.preview.record_count} 条；系统归属 ${responsibility.head_label || "主管负责人"}，只有对应主管负责人可以确认。`; refreshLineConfirmBoundary(); } catch (error) { $("lineAdapterStatus").textContent = error.message; state.linePreview = null; refreshLineConfirmBoundary(); } });
  $("lineAdapterConfirm").addEventListener("click", async () => { if (!state.linePreview) return; try { await apiJson("/api/line-adapter/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, preview: state.linePreview.preview }) }); state.linePreview = null; await refreshWorkspace(); setView("coordination"); } catch (error) { $("lineAdapterStatus").textContent = error.message; } });
  document.querySelectorAll("[data-decision-id]").forEach((button) => button.addEventListener("click", async () => { try { await apiJson("/api/collaboration/decision/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, decision_id: button.dataset.decisionId }) }); await refreshWorkspace(); setView("coordination"); } catch (error) { setError(error.message); } }));
  document.querySelectorAll("[data-task-id]").forEach((button) => button.addEventListener("click", async () => { try { await apiJson("/api/collaboration/task/status", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, task_id: button.dataset.taskId, status: button.dataset.taskStatus }) }); await refreshWorkspace(); setView("coordination"); } catch (error) { setError(error.message); } }));
}

async function loadConnectors() {
  const response = await apiJson("/api/connectors");
  state.connectors = response.connectors || [];
  const recognition = await apiJson("/api/recognition/catalog");
  state.recognizers = recognition.recognizers || [];
}

async function loadBasisCatalog() {
  if (isKpiOnly()) {
    state.basisCatalog = { categories: [], items: [] };
    return;
  }
  try {
    state.basisCatalog = await apiJson("/api/basis");
  } catch (_) {
    state.basisCatalog = { categories: [], items: [] };
  }
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
  if (isKpiOnly()) {
    tasks.push({ tone: "next", title: "查找资料或提问", note: "只基于本地项目资料显示可追溯依据。", view: "search" });
    tasks.push({ tone: "next", title: "查看项目经营看板", note: "项目经理仅显示重要指标、风险预警和经营趋势。", view: "dashboard" });
    if (state.events.length) tasks.push({ tone: state.events.some((event) => event.alerts?.length) ? "warn" : "done", title: `查看 ${state.events.length} 项工程事件`, note: "只显示状态向量、重要风险和三证互证结果。", view: "events" });
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
    return;
  }
  tasks.push({ tone: "next", title: "查找资料或提问", note: "本地检索优先；回答会标注命中依据和不确定性。", view: "search" });
  tasks.push({ tone: state.events.length ? (state.events.some((event) => event.alerts?.length) ? "warn" : "done") : "next", title: state.events.length ? `工程事件内核已记录 ${state.events.length} 项` : "建立工程事件", note: "先蒸馏本地资料，再融合文本事实；状态、证据和预警集中呈现。", view: "events" });
  const pendingDecisions = state.coordination?.workflow?.decision_counts?.PROPOSED || 0;
  tasks.push({ tone: pendingDecisions ? "warn" : "next", title: pendingDecisions ? `有 ${pendingDecisions} 项决策等待人工确认` : "建立组织协同关系", note: "把生产、技术、造价责任线绑定到 Core Event；数据只提供依据。", view: "coordination" });
  const structuredStages = [
    ["contract", "P01 合同与招采依据", state.contractResult, "补充合同主数据和履约义务"],
    ["drawings", "P03 图纸登记", state.drawingsResult, "登记图号、版本和审阅状态"],
    ["baseline", "P04 零号台账", state.baselineResult, "建立项目开局成本基线"],
    ["changes", "P06 变更管理", state.changesResult, "登记变更影响并等待决策"],
    ["evidence", "P07 证据关联", state.evidenceResult, "把来源与业务记录关联起来"],
  ];
  structuredStages.forEach(([view, title, result, note]) => {
    tasks.push({ tone: result ? "done" : "next", title: result ? `${title}已保存` : title, note: result ? "可继续查看、修改并保留版本痕迹" : note, view });
  });
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
  $("assistList").replaceChildren(...tasks.filter((task) => canAccessView(task.view)).map((task) => {
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
  const spec = workbenchSpec();
  const roleTitle = isProjectManager() ? "项目经理经营看板" : isCostManager() ? "造价经理经营看板" : `${spec.title} · 经营看板`;
  const roleNote = isProjectManager()
    ? "仅保留项目经理需要的关键指标、风险预警和周期趋势。"
    : isCostManager()
      ? "查看全部成本明细、基线比对、变更、证据链和审查结果。"
      : spec.focus;
  const manual = ROLE_OPERATION_MANUALS[currentRole()] || ROLE_OPERATION_MANUALS.project_manager;
  const manualPanel = '<section class="dashboard-panel role-manual-panel"><div class="surface-title"><div><span class="panel-label">ROLE OPERATION MANUAL · v0.8.0-rc5</span><h3>' + (isProjectManager() ? "项目经理操作手册" : "本岗位操作手册") + '</h3></div><span class="surface-caption">费曼四步：说清楚 → 动手做 → 交成果 → 找漏洞</span></div><div class="overview-cards role-manual-cards"><div class="overview-card"><span class="card-label">先说清楚</span><strong>输入</strong><small>' + escapeHtml(manual.start) + '</small></div><div class="overview-card"><span class="card-label">动手保存</span><strong>操作</strong><small>' + escapeHtml(manual.save) + '</small></div><div class="overview-card"><span class="card-label">交付成果</span><strong>协同</strong><small>' + escapeHtml(manual.handoff) + '</small></div><div class="overview-card"><span class="card-label">完成前复述</span><strong>检查</strong><small>' + escapeHtml(manual.check) + '</small></div></div></section>';
  const planAction = isProjectManager() || !canAccessView("plan") ? "" : '<button class="button button-quiet" data-view="plan" type="button">查看成本计划</button>';
  const reviewAction = isCostManager() ? '<button class="button button-quiet" data-view="review" type="button">查看结算初审</button>' : "";
  $("workspaceContent").innerHTML =
    '<div class="surface-title"><div><span class="panel-label">PROJECT INTELLIGENCE</span><h3>' + roleTitle + '</h3></div><span class="surface-caption">本地自动汇总 · 打开看板即刷新预警</span></div>' +
    '<div class="dashboard-intro"><strong id="dashboardProjectName"></strong><span id="dashboardRoleNote"></span><small id="dashboardGeneratedAt"></small></div>' +
    manualPanel +
    renderSubcontractWorkflowPanels() +
    renderRoleFlowSummary() +
    '<section class="dashboard-alert-panel"><div class="surface-title"><div><span class="panel-label">AUTOMATED ALERTS</span><h3>需要优先处理</h3></div><span class="surface-caption">红色立即处理 · 黄色安排核对 · 蓝色关注趋势</span></div><div id="dashboardAlerts" class="dashboard-alert-list"></div></section>' +
    '<div id="dashboardMetrics" class="dashboard-metrics"></div>' +
    '<section class="dashboard-panel outcome-management-panel"><div class="surface-title"><div><span class="panel-label">OUTCOME / VALUE LEAK</span><h3>成果转化漏斗与价值泄漏</h3></div><span class="surface-caption">实体只录一次；后续状态和差额由现有造价事实派生</span></div><div id="dashboardOutcomeFunnel" class="outcome-funnel"></div><div id="dashboardValueLeaks" class="dashboard-issue-list"></div><div id="dashboardDailyQueue" class="dashboard-issue-list"></div></section>' +
    '<div class="dashboard-grid">' +
      '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">BASELINE / COMPARISON</span><h3>成本基线与造价资料比对</h3></div>' + planAction + '</div><div id="dashboardComparisonSummary" class="dashboard-comparison-summary"></div><div id="dashboardComparisonTable" class="dashboard-table"></div></section>' +
      '<section class="dashboard-panel"><div class="surface-title"><div><span class="panel-label">WEEKLY / MONTHLY</span><h3>问题周期趋势</h3></div>' + reviewAction + '</div><div id="dashboardPeriods" class="dashboard-periods"></div><div id="dashboardRecurring" class="dashboard-recurring"></div></section>' +
    '</div>' +
    '<section class="dashboard-panel dashboard-capability-panel"><div class="surface-title"><div><span class="panel-label">P01 — P09 COVERAGE</span><h3>全能力工作面状态</h3></div><span class="surface-caption">汇总不替代业务页面，点击后进入对应能力工作台</span></div><div id="dashboardCapabilities" class="dashboard-capability-grid"></div></section>' +
    '<section class="dashboard-panel dashboard-issues-panel"><div class="surface-title"><div><span class="panel-label">ISSUE QUEUE</span><h3>当前问题与处理入口</h3></div><span class="surface-caption">每次运行初审会保留本地快照，支持近7天和近30天统计</span></div><div id="dashboardIssues" class="dashboard-issue-list"></div></section>';

  $("dashboardProjectName").textContent = dashboard.project?.name || state.projectName || "当前项目";
  $("dashboardRoleNote").textContent = roleNote;
  $("dashboardGeneratedAt").textContent = "刷新时间：" + new Date(dashboard.generated_at).toLocaleString("zh-CN");
  const capabilityViews = [["P01", "合同与招采依据", "contract"], ["P02", "清单资料", "boq"], ["P03", "图纸资料", "drawings"], ["P04", "零号台账", "baseline"], ["P05", "成本计划", "plan"], ["P06", "变更管理", "changes"], ["P07", "证据关联", "evidence"], ["P08", "结算初审", "review"], ["P09", "成果经营", "p09"]];
  $("dashboardCapabilities").replaceChildren(...capabilityViews.filter(([, , view]) => canAccessView(view)).map(([id, label, view]) => {
    const item = document.createElement(isKpiOnly() ? "div" : "button");
    if (!isKpiOnly()) item.type = "button";
    item.className = "dashboard-capability-item";
    if (!isKpiOnly()) item.dataset.view = view;
    const code = document.createElement("span"); code.className = "capability-id"; code.textContent = id;
    const title = document.createElement("strong"); title.textContent = label;
    const details = dashboard.capabilities?.[id] || {};
    const status = document.createElement("small"); status.textContent = Object.keys(details).length ? "已有本地数据" : "待建立";
    item.append(code, title, status);
    return item;
  }));
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

  const outcomeManagement = dashboard.outcome_management || {};
  const funnelTarget = $("dashboardOutcomeFunnel");
  if (funnelTarget) {
    const funnel = outcomeManagement.funnel || [];
    funnelTarget.replaceChildren(...funnel.map((stage, index) => {
      const item = document.createElement("div");
      item.className = "outcome-funnel-stage";
      const label = document.createElement("span"); label.textContent = stage.label || stage.stage;
      const amount = document.createElement("strong"); amount.textContent = dashboardMoney(stage.amount);
      const rate = document.createElement("small"); rate.textContent = index === 0 ? `${stage.event_count || 0} 项事件` : `${stage.conversion_rate == null ? "—" : dashboardPercent(stage.conversion_rate)} 转化`;
      item.append(label, amount, rate);
      return item;
    }));
  }
  const leaksTarget = $("dashboardValueLeaks");
  if (leaksTarget) {
    const leaks = outcomeManagement.value_leaks || [];
    leaksTarget.replaceChildren();
    if (!leaks.length) {
      leaksTarget.textContent = "当前没有可计算的价值泄漏；先在工程事件中记录 Outcome 快照。";
    } else {
      const heading = document.createElement("div"); heading.className = "panel-label"; heading.textContent = `价值泄漏 ${dashboardMoney(outcomeManagement.value_leak_total)} · ${outcomeManagement.value_leak_count || 0} 个阶段`;
      leaksTarget.append(heading, ...leaks.slice(0, 6).map((leak) => {
        const item = document.createElement("article"); item.className = "dashboard-issue risk-yellow";
        const badge = document.createElement("span"); badge.textContent = leak.code || "LEAK";
        const body = document.createElement("div"); const title = document.createElement("strong"); title.textContent = `${leak.title || leak.event_id} · ${dashboardMoney(leak.amount)}`; const note = document.createElement("small"); note.textContent = `${leak.from_stage || ""} → ${leak.to_stage || ""} · ${leak.reason || "待补充原因"}`; body.append(title, note); item.append(badge, body); return item;
      }));
    }
  }
  const queueTarget = $("dashboardDailyQueue");
  if (queueTarget) {
    const queue = outcomeManagement.daily_queue || [];
    queueTarget.replaceChildren();
    const heading = document.createElement("div"); heading.className = "panel-label"; heading.textContent = "今日经营队列（只看异常）";
    queueTarget.append(heading);
    if (!queue.length) queueTarget.append(Object.assign(document.createElement("small"), { textContent: "当前没有待处理异常。" }));
    else queueTarget.append(...queue.slice(0, 6).map((entry) => { const item = document.createElement("article"); item.className = "dashboard-issue risk-blue"; const badge = document.createElement("span"); badge.textContent = entry.event_id || "Event"; const body = document.createElement("div"); const title = document.createElement("strong"); title.textContent = entry.title || "工程事件"; const note = document.createElement("small"); note.textContent = `${eventStatusLabel(entry.event_status)} · ${outcomeStatusLabel(entry.outcome_status)} · ${entry.days_open == null ? "时钟待补" : `已打开 ${entry.days_open} 天`} · 预警 ${entry.alert_count || 0} · 泄漏 ${entry.value_leak_count || 0}`; body.append(title, note); item.append(badge, body); return item; }));
  }

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
  if (!canViewCostDetail()) {
    $("dashboardComparisonTable").textContent = "成本明细按角色权限隐藏，仅保留指标汇总。";
  } else {
    renderTable($("dashboardComparisonTable"), [["code", "编码"], ["name", "项目"], ["contract_amount", "基线金额"], ["market_amount", "参考金额"], ["over_limit_amount", "超限金额"], ["over_limit_rate", "偏差率"]], (comparison.rows || []).map((row) => ({
      code: row.code,
      name: row.name,
      contract_amount: dashboardMoney(row.contract_amount),
      market_amount: dashboardMoney(row.market_amount),
      over_limit_amount: dashboardMoney(row.over_limit_amount),
      over_limit_rate: dashboardPercent(row.over_limit_rate),
    })));
  }

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

function searchStatusLabel(status) {
  return status === "supported" ? "可回溯命中" : status === "related" ? "索引关联" : "依据不足";
}

function renderSearchResults() {
  const response = state.search.response;
  const resultList = $("searchResultList");
  const summary = $("searchResultSummary");
  const answerPanel = $("searchAnswerPanel");
  if (!resultList || !summary || !answerPanel) return;
  if (!response) {
    summary.textContent = state.search.query ? "正在准备本地检索…" : "输入文件名、合同条款、价格依据或你想核对的问题。";
    resultList.className = "search-result-list empty-state";
    resultList.textContent = "检索结果会显示资料来源、归档位置、识别状态和可查看入口。";
    answerPanel.hidden = true;
    return;
  }
  summary.textContent = response.total
    ? `本地检索到 ${response.total} 条相关记录；当前显示 ${response.results.length} 条`
    : "没有命中本地资料。系统不会用猜测补齐答案。";
  if (state.search.mode === "ask") {
    answerPanel.hidden = false;
    $("searchAnswerText").textContent = response.answer || "未形成回答";
    $("searchAnswerPolicy").textContent = response.answer_policy || "仅使用本地证据";
    const claimsTarget = $("searchClaims");
    const claims = response.claims || [];
    claimsTarget.replaceChildren(...claims.map((claim) => {
      const item = document.createElement("article");
      item.className = `search-claim search-claim-${claim.status || "related"}`;
      const title = document.createElement("strong");
      title.textContent = `${claim.label || "证据"} · ${claim.source || "未命名资料"}`;
      const body = document.createElement("p");
      body.textContent = claim.text || "未提供摘要";
      const source = document.createElement("small");
      source.textContent = `溯源：${claim.archive_path || "未记录归档位置"} · ${claim.is_inference ? "系统推断" : "资料原文/识别稿"}`;
      item.append(title, body, source);
      return item;
    }));
    const uncertaintyTarget = $("searchUncertainties");
    const uncertainties = response.uncertainties || [];
    uncertaintyTarget.replaceChildren(...uncertainties.map((text) => {
      const item = document.createElement("li");
      item.textContent = text;
      return item;
    }));
    $("searchUncertaintyBlock").hidden = !uncertainties.length;
  } else {
    answerPanel.hidden = true;
  }
  if (!response.results?.length) {
    resultList.className = "search-result-list empty-state";
    resultList.textContent = "未找到可引用的本地资料。可以换用文件名、合同关键词、P01–P08 阶段名称或更具体的问题。";
    return;
  }
  resultList.className = "search-result-list";
  resultList.replaceChildren(...response.results.map((result) => {
    const item = document.createElement("article");
    item.className = "search-result-item";
    const head = document.createElement("div");
    head.className = "search-result-head";
    const info = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = result.title || "未命名资料";
    const meta = document.createElement("small");
    meta.textContent = `${result.scope_label || "本地资料"} · ${result.type_label || "资料"} · ${result.category || "未分类"}`;
    info.append(title, meta);
    const status = document.createElement("span");
    status.className = `search-result-status search-status-${result.match_status || "related"}`;
    status.textContent = searchStatusLabel(result.match_status);
    head.append(info, status);
    const snippet = document.createElement("p");
    snippet.className = "search-result-snippet";
    snippet.textContent = result.snippet || "未提供可检索摘要";
    const provenance = document.createElement("small");
    provenance.className = "search-result-provenance";
    provenance.textContent = `来源：${result.provenance?.source_name || result.title || "本地资料"} · 归档：${result.archive_path || "未记录归档位置"}`;
    item.append(head, snippet, provenance);
    if (result.storage_path) {
      const path = document.createElement("small");
      path.className = "search-result-path";
      path.textContent = `本地保存：${result.storage_path}`;
      item.append(path);
    }
    const actions = document.createElement("div");
    actions.className = "search-result-actions";
    if (result.openable && result.source_id && result.result_id?.startsWith("project-source:")) {
      const view = document.createElement("button");
      view.type = "button";
      view.className = "icon-button source-view-button";
      view.textContent = result.derived ? "查看识别稿" : "查看资料";
      view.addEventListener("click", () => viewSource({ source_id: result.source_id }, Boolean(result.derived)));
      actions.append(view);
      if (result.derived) {
        const original = document.createElement("button");
        original.type = "button";
        original.className = "icon-button";
        original.textContent = "查看原件";
        original.addEventListener("click", () => viewSource({ source_id: result.source_id }, false));
        actions.append(original);
      }
    } else if (result.openable && result.source_id && result.result_id?.startsWith("external-basis:")) {
      const view = document.createElement("button");
      view.type = "button";
      view.className = "icon-button source-view-button";
      view.textContent = result.derived ? "查看识别稿" : "查看依据";
      view.addEventListener("click", () => viewBasis({ basis_id: result.source_id }, Boolean(result.derived)));
      actions.append(view);
      if (result.derived) {
        const original = document.createElement("button");
        original.type = "button";
        original.className = "icon-button";
        original.textContent = "查看原件";
        original.addEventListener("click", () => viewBasis({ basis_id: result.source_id }, false));
        actions.append(original);
      }
    } else if (!result.openable && isKpiOnly()) {
      const note = document.createElement("small");
      note.className = "permission-note";
      note.textContent = "当前角色仅显示索引和风险相关信息";
      actions.append(note);
    }
    if (actions.childNodes.length) item.append(actions);
    return item;
  }));
}

async function performSearch() {
  const queryInput = $("searchQuery");
  if (queryInput) state.search.query = queryInput.value.trim();
  if (!state.search.query) {
    state.search.response = null;
    renderSearchResults();
    return;
  }
  state.search.response = null;
  renderSearchResults();
  try {
    state.search.response = await apiJson("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.projectId,
        query: state.search.query,
        mode: state.search.mode,
        scope: state.search.scope,
        stage: state.search.stage,
        category: state.search.category,
      }),
    });
    renderSearchResults();
    setStatus(state.search.mode === "ask" ? "问题已按本地证据完成核对" : "本地资料检索完成");
  } catch (error) {
    setError(error.message);
    state.search.response = null;
    renderSearchResults();
  }
}

function renderSearch() {
  if (isKpiOnly()) state.search.scope = "project";
  const stageOptions = [
    ["", "全部 P01–P08"], ["P01", "P01 合同与招采依据"], ["P02", "P02 清单资料"], ["P03", "P03 图纸资料"],
    ["P04", "P04 零号台账"], ["P05", "P05 成本计划"], ["P06", "P06 变更管理"], ["P07", "P07 证据关联"], ["P08", "P08 结算初审"],
  ];
  const scopeOptions = isKpiOnly()
    ? [["project", "当前项目资料"]]
    : [["all", "当前项目 + 外部依据"], ["project", "仅当前项目资料"], ["basis", "仅外部依据库"]];
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">LOCAL EVIDENCE SEARCH</span><h3>资料与问题检索</h3></div><span class="surface-caption">搜索入口在顶部；这里显示完整结果、来源和溯源</span></div>
    <div class="search-policy"><strong>本地优先，认知诚实</strong><span>默认只读取当前项目、外部依据快照和已保存的 P01–P08 记录；没有依据就明确显示不足，不把系统推断写成事实。</span><span>外部 AI 未启用；未来如接入，必须逐次明确授权并显示发送范围。</span></div>
    <section class="search-workspace">
      <div class="search-mode-row"><div class="search-mode-switch"><button id="searchModeSearch" class="button ${state.search.mode === "search" ? "button-primary" : "button-quiet"}" type="button">查资料</button><button id="searchModeAsk" class="button ${state.search.mode === "ask" ? "button-primary" : "button-quiet"}" type="button">问问题</button></div><small id="searchModeNote" class="request-status">${state.search.mode === "ask" ? "回答只引用下方本地证据，不调用外部 AI。" : "按文件名、分类、路径、识别稿和业务记录查找。"}</small></div>
      <form id="searchForm" class="search-form"><label class="visually-hidden" for="searchQuery">检索内容</label><input id="searchQuery" type="search" placeholder="例如：合同金额、工程量清单、变更依据、信息价有效期" /><button class="button button-primary" type="submit">开始检索</button></form>
      <div class="search-filters"><label>检索范围<select id="searchScope">${scopeOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select></label><label>工作阶段<select id="searchStage">${stageOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select></label><label>资料分类<input id="searchCategory" placeholder="可选，如：合同与商务" /></label></div>
      <div id="searchResultSummary" class="search-result-summary"></div>
      <section id="searchAnswerPanel" class="search-answer-panel" hidden><div class="surface-title"><div><span class="panel-label">EVIDENCE-GROUNDED ANSWER</span><h3>本地证据回答</h3></div><span class="surface-caption">不是自动裁决</span></div><p id="searchAnswerText" class="search-answer-text"></p><small id="searchAnswerPolicy" class="search-answer-policy"></small><div id="searchUncertaintyBlock" class="search-uncertainty" hidden><strong>需要人工核对</strong><ul id="searchUncertainties"></ul></div><div id="searchClaims" class="search-claims"></div></section>
      <section class="search-results-panel"><div class="surface-title"><div><span class="panel-label">TRACEABLE RESULTS</span><h3>命中资料</h3></div><span class="surface-caption">每条结果都标明来源和归档位置</span></div><div id="searchResultList" class="search-result-list"></div></section>
    </section>`;
  $("searchQuery").value = state.search.query;
  $("searchScope").value = state.search.scope;
  $("searchStage").value = state.search.stage;
  $("searchCategory").value = state.search.category;
  $("searchModeSearch").addEventListener("click", () => { state.search.mode = "search"; state.search.response = null; renderSearch(); });
  $("searchModeAsk").addEventListener("click", () => { state.search.mode = "ask"; state.search.response = null; renderSearch(); });
  $("searchScope").addEventListener("change", (event) => { state.search.scope = event.target.value; state.search.response = null; });
  $("searchStage").addEventListener("change", (event) => { state.search.stage = event.target.value; state.search.response = null; });
  $("searchCategory").addEventListener("input", (event) => { state.search.category = event.target.value.trim(); state.search.response = null; });
  $("searchForm").addEventListener("submit", (event) => { event.preventDefault(); performSearch(); });
  renderSearchResults();
}

function renderRoleOverview() {
  const spec = workbenchSpec();
  const manual = ROLE_OPERATION_MANUALS[currentRole()] || {
    start: "先打开当前岗位授权的第一个工作面。",
    save: "保存本岗位事实、证据和审核状态。",
    handoff: "提交责任线和协同岗位复核。",
    check: "只做本岗位动作，不代填其他岗位事实。",
  };
  const assignedLabels = state.auth.user?.role_labels?.length
    ? state.auth.user.role_labels.join(" + ")
    : state.auth.user?.role_label || "当前岗位";
  const viewLabels = {
    search: "资料与问题检索", contract: "合同与招采依据", boq: "清单资料", drawings: "图纸资料",
    baseline: "零号台账", plan: "成本计划", changes: "变更管理", events: "工程事件", evidence: "证据关联",
    coordination: "组织协同", basis: "外部依据库", dashboard: "经营看板",
  };
  const workViews = [...visibleViewsForUser()].filter((view) => !["overview", "personnel", "control"].includes(view));
  const quickLinks = workViews.map((view) => `<button class="overview-card role-link" data-view="${view}" type="button"><span class="card-label">${viewLabels[view] || view}</span><strong>进入</strong><small>${view === "coordination" ? "责任链与人工确认" : "只处理本岗位成果"}</small></button>`).join("");
  const alertCount = state.events.filter((event) => (event.alerts || []).length).length;
  const pendingCount = state.events.filter((event) => !["CLOSED", "COST_CLOSED"].includes(event.state_vector?.event || event.status)).length;
  const assignedSpecs = currentRoles().map((role) => ROLE_WORKBENCH_SPECS[role]).filter(Boolean);
  const output = [...new Set(assignedSpecs.map((item) => item.outputs).filter(Boolean))].join(" + ") || "本岗位成果、审核状态、异常与责任链";
  const workflow = [...new Set(assignedSpecs.flatMap((item) => item.workflow || []))].slice(0, 6);
  const execution = [...new Set(assignedSpecs.map((item) => item.execution).filter(Boolean))].join(" ");
  const personnelManual = canManagePersonnel()
    ? `<div class="capability-intro"><strong>人员管理：</strong><span>当前项目可新增人员。只填姓名和岗位，保存后把一次显示的初始密码交给本人；其他项目名册不受影响。</span><button class="button button-quiet" data-view="personnel" type="button">打开人员管理</button></div>`
    : "";
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">ROLE WORKBENCH</span><h3>${spec.title}</h3></div><span class="surface-caption">${escapeHtml(assignedLabels)} · 独立工作面</span></div>
    <div class="capability-intro"><strong>本岗位核心成果：</strong><span>${escapeHtml(output)}</span><br><small>${escapeHtml(spec.focus)}</small></div>
    <section class="overview-panel role-execution-panel">
      <div class="surface-title"><div><span class="panel-label">ROLE EXECUTION LOOP</span><h3>本岗位执行流程</h3></div><span class="surface-caption">只做本岗位动作</span></div>
      <div class="role-workflow">${workflow.map((step, index) => `<span class="role-workflow-step"><b>${index + 1}</b>${escapeHtml(step)}</span>`).join('<span class="role-workflow-arrow">→</span>')}</div>
      <p class="business-note">${escapeHtml(execution)}</p>
    </section>
    ${renderSubcontractWorkflowPanels()}
    <section class="overview-panel role-manual-panel">
      <div class="surface-title"><div><span class="panel-label">ROLE OPERATION MANUAL · v0.8.0-rc5</span><h3>岗位操作手册</h3></div><span class="surface-caption">费曼四步：说清楚 → 动手做 → 交成果 → 找漏洞</span></div>
      <div class="overview-cards role-manual-cards">
        <div class="overview-card"><span class="card-label">先说清楚</span><strong>输入</strong><small>${escapeHtml(manual.start)}</small></div>
        <div class="overview-card"><span class="card-label">动手保存</span><strong>操作</strong><small>${escapeHtml(manual.save)}</small></div>
        <div class="overview-card"><span class="card-label">交付成果</span><strong>协同</strong><small>${escapeHtml(manual.handoff)}</small></div>
        <div class="overview-card"><span class="card-label">完成前复述</span><strong>检查</strong><small>${escapeHtml(manual.check)}</small></div>
      </div>
    </section>
    ${renderRoleFlowSummary()}
    ${personnelManual}
    <div class="overview-cards role-work-cards">
      <div class="overview-card"><span class="card-label">我的工作</span><strong>${workViews.length}</strong><small>个授权工作面</small></div>
      <div class="overview-card"><span class="card-label">待交成果</span><strong>${pendingCount}</strong><small>工程事件仍在流转</small></div>
      <div class="overview-card"><span class="card-label">审核状态</span><strong>人工闸门</strong><small>专业审核 → 造价总审</small></div>
      <div class="overview-card"><span class="card-label">异常 / 退回</span><strong>${alertCount}</strong><small>只显示与本岗相关的风险入口</small></div>
      <div class="overview-card"><span class="card-label">直接责任链</span><strong>Event → 成果</strong><small>Evidence → Verification → Outcome</small></div>
    </div>
    <section class="overview-panel">
      <div class="surface-title"><div><span class="panel-label">AUTHORIZED WORK SURFACES</span><h3>进入本岗位工作</h3></div><span class="surface-caption">没有授权的模块不会出现在此处</span></div>
      <div class="overview-cards role-link-grid">${quickLinks || '<p class="empty-state">当前账号没有可操作的专业工作面，请联系项目经理配置岗位。</p>'}</div>
    </section>
    <section class="overview-panel">
      <div class="surface-title"><div><span class="panel-label">SHARED FOUNDATION</span><h3>底座自动链接</h3></div><span class="surface-caption">只读共享，不跨岗代填</span></div>
      <div class="capability-intro"><span>所有成果统一绑定 Project + WBS + Location + Event + Time；本岗位只产生自己的事实，系统自动把它链接到技术、生产、造价、证据和 Outcome。</span></div>
    </section>`;
  bindViewButtons();
}

function renderOverview() {
  if (isKpiOnly()) {
    renderDashboard();
    return;
  }
  if (!isCostManager()) {
    renderRoleOverview();
    return;
  }
  const items = state.boqResult?.items || [];
  const review = state.reviewResult;
  const manual = ROLE_OPERATION_MANUALS[currentRole()] || ROLE_OPERATION_MANUALS.cost_manager;
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
    <section class="overview-panel role-manual-panel">
      <div class="surface-title"><div><span class="panel-label">ROLE OPERATION MANUAL · v0.8.0-rc5</span><h3>造价经理操作手册</h3></div><span class="surface-caption">费曼四步：说清楚 → 动手做 → 交成果 → 找漏洞</span></div>
      <div class="overview-cards role-manual-cards">
        <div class="overview-card"><span class="card-label">先说清楚</span><strong>输入</strong><small>${escapeHtml(manual.start)}</small></div>
        <div class="overview-card"><span class="card-label">动手保存</span><strong>操作</strong><small>${escapeHtml(manual.save)}</small></div>
        <div class="overview-card"><span class="card-label">交付成果</span><strong>协同</strong><small>${escapeHtml(manual.handoff)}</small></div>
        <div class="overview-card"><span class="card-label">完成前复述</span><strong>检查</strong><small>${escapeHtml(manual.check)}</small></div>
      </div>
    </section>
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
    <div class="archive-location"><span>本入口归档位置</span><strong>${PROJECT_ARCHIVE_AREAS.overview}</strong></div>
    <div class="source-search-bar"><label for="sourceSearch">搜索项目资料</label><div class="source-search-controls"><input id="sourceSearch" type="search" placeholder="文件名、资料分类或本地路径" /><button id="sourceSearchButton" class="button button-quiet" type="button">搜索资料</button><button id="sourceSearchClear" class="button button-quiet" type="button">清除</button></div><small id="sourceSearchSummary" class="source-search-summary"></small></div>
    <div id="sourceList" class="source-list"></div>
    <div id="sourceIntakeSummary" class="intake-report-list"></div>
    <div class="recognition-entry"><span class="panel-label">RECOGNITION</span><div id="recognizerCatalog" class="recognizer-list"></div></div>
    <div class="tool-entry"><span class="panel-label">TOOL ENTRY</span><div id="connectorCatalog" class="tool-entry-grid"></div></div>
    <div class="export-actions"><button id="exportReport" class="button button-quiet" type="button">导出 Word 兼容报告</button><button id="exportBoq" class="button button-quiet" type="button">导出 Excel 清单</button><button id="exportPlan" class="button button-quiet" type="button">导出 Excel 成本计划</button><button id="exportBundle" class="button button-primary" type="button">导出项目交换包</button><button id="importBundle" class="button button-quiet" type="button">导入项目交换包</button></div>`;
  $("workspaceContent").append(sourcePanel);
  if (!canViewCostDetail()) {
    ["exportReport", "exportPlan", "exportBundle"].forEach((id) => { if ($(id)) $(id).hidden = true; });
  }
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
  bindSourceLibrarySearch();
  const capabilityPanel = document.createElement("div");
  capabilityPanel.className = "overview-panel capability-coverage-panel";
  capabilityPanel.innerHTML = '<div class="surface-title"><div><span class="panel-label">P01 — P09 WORKBENCH</span><h3>九项能力入口</h3></div><span class="surface-caption">P01–P08 保存专业事实，P09 汇总成果经营派生结果</span></div><div id="capabilityCoverage" class="capability-coverage"></div>';
  $("workspaceContent").append(capabilityPanel);
  const coverage = [
    ["contract", "P01", "合同与招采依据", state.contractResult], ["boq", "P02", "清单资料", state.boqResult], ["drawings", "P03", "图纸资料", state.drawingsResult], ["baseline", "P04", "零号台账", state.baselineResult],
    ["plan", "P05", "成本计划", state.planResult], ["changes", "P06", "变更管理", state.changesResult], ["evidence", "P07", "证据关联", state.evidenceResult], ["review", "P08", "结算初审", state.reviewResult], ["p09", "P09", "成果经营", state.p09],
  ];
  $("capabilityCoverage").replaceChildren(...coverage.map(([view, id, label, result]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "coverage-item";
    button.dataset.view = view;
    const code = document.createElement("span"); code.className = "capability-id"; code.textContent = id;
    const name = document.createElement("strong"); name.textContent = label;
    const status = document.createElement("small"); status.textContent = result ? "已建立，可继续处理" : "待建立";
    button.append(code, name, status);
    button.addEventListener("click", () => setView(view));
    return button;
  }));
  renderIntakeReports("sourceIntakeSummary");
  renderRecognizerCatalog();
  renderConnectorCatalog();
  $("uploadSource").addEventListener("click", () => $("sourceInput").click());
  $("sourceInput").onchange = handleSourceFile;
  $("exportReport").addEventListener("click", () => openExportWorkspace("report"));
  $("exportBoq").addEventListener("click", () => openExportWorkspace("boq.xlsx"));
  $("exportPlan").addEventListener("click", () => openExportWorkspace("cost-plan.xlsx"));
  $("exportBundle").addEventListener("click", () => openExportWorkspace("bundle"));
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
    status.textContent = connector.status === "ready" ? "可直接使用" : connector.status === "consent" ? "明确授权后取得快照" : "通过交换包";
    item.append(name, note, status);
    return item;
  }));
}

function sourceViewUrl(source, derived = false) {
  return `/api/source/view?project_id=${encodeURIComponent(state.projectId)}&source_id=${encodeURIComponent(source.source_id)}${derived ? "&derived=1" : ""}`;
}

async function viewSource(source, derived = false) {
  const popup = window.open("about:blank", "_blank", "noopener");
  try {
    const response = await fetch(sourceViewUrl(source, derived), { headers: { Authorization: `Bearer ${state.auth.token}` } });
    if (!response.ok) throw new Error(`资料查看失败（${response.status}）`);
    const objectUrl = URL.createObjectURL(await response.blob());
    if (popup) popup.location.href = objectUrl;
    else window.open(objectUrl, "_blank", "noopener");
  } catch (error) {
    if (popup) popup.close();
    setError(error.message);
  }
}

async function copySourcePaths(source) {
  const artifact = (source.recognition || {}).artifact || {};
  const paths = [source.archive_storage_path, source.storage_path, artifact.storage_path].filter(Boolean).join("\n");
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

async function deleteSource(source, targetId = "sourceList") {
  if (!isManager() || !window.confirm("仅造价经理可执行。资料将软删除并保留原文件与操作记录，确认继续？")) return;
  try {
    const response = await apiJson("/api/source/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, source_id: source.source_id }),
    });
    applyWorkspace(response.workspace);
    renderSourceList(targetId);
    renderControlIfVisible();
    setStatus("资料已软删除，原文件和操作痕迹仍保留");
  } catch (error) {
    setError(error.message);
  }
}

function sourceSearchText(source) {
  const recognition = source.recognition || {};
  return [
    source.name,
    source.kind,
    source.archive_area,
    source.archive_category,
    source.archive_path,
    source.archive_storage_path,
    source.storage_path,
    recognition.category,
    recognition.status,
  ].filter(Boolean).join(" ").toLocaleLowerCase();
}

function bindSourceLibrarySearch() {
  const input = $("sourceSearch");
  const searchButton = $("sourceSearchButton");
  const clearButton = $("sourceSearchClear");
  if (!input || !searchButton || !clearButton) return;
  input.value = state.sourceSearchTerm;
  const runSearch = () => {
    state.sourceSearchTerm = input.value.trim();
    state.sourceListExpanded = false;
    renderSourceList("sourceList");
  };
  searchButton.addEventListener("click", runSearch);
  clearButton.addEventListener("click", () => {
    input.value = "";
    state.sourceSearchTerm = "";
    state.sourceListExpanded = false;
    renderSourceList("sourceList");
    input.focus();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runSearch();
    }
  });
}

function renderSourceList(targetId = "sourceList", filter = {}) {
  const list = $(targetId);
  if (!list) return;
  const searchTerm = (filter.searchTerm ?? (targetId === "sourceList" ? state.sourceSearchTerm : "")).trim().toLocaleLowerCase();
  const visibleSources = state.sources.filter((source) => {
    if (filter.archiveArea && source.archive_area !== filter.archiveArea) return false;
    if (searchTerm && !sourceSearchText(source).includes(searchTerm)) return false;
    return true;
  });
  const isProjectLibrary = targetId === "sourceList";
  const isCompactList = isProjectLibrary || targetId.endsWith("SourceList");
  const listExpanded = isProjectLibrary ? state.sourceListExpanded : Boolean(state.sourceListExpandedByTarget[targetId]);
  const collapsedCount = Math.max(0, visibleSources.length - 2);
  const showCollapsed = isCompactList && collapsedCount > 0 && !listExpanded;
  const displayedSources = showCollapsed ? visibleSources.slice(-2) : visibleSources;
  const searchSummary = $("sourceSearchSummary");
  if (targetId === "sourceList" && searchSummary) {
    const resultSummary = searchTerm
      ? `搜索“${searchTerm}”：${visibleSources.length} / ${state.sources.length} 项资料`
      : `${state.sources.length} 项资料，支持按名称、分类和本地路径搜索`;
    searchSummary.textContent = showCollapsed
      ? `${resultSummary}；当前显示 2 项，其余 ${collapsedCount} 项已收起`
      : resultSummary;
  }
  if (!visibleSources.length) {
    list.className = "source-list empty-state";
    list.textContent = searchTerm
      ? `没有找到与“${searchTerm}”匹配的项目资料。`
      : filter.archiveArea
      ? `当前归档位置还没有资料：${filter.archiveArea}`
      : "当前项目还没有其他资料。可以从这里接入 Word、PDF、CAD 或 Excel 文件。";
    return;
  }
  list.className = "source-list";
  list.replaceChildren(...displayedSources.slice().reverse().map((source) => {
    const item = document.createElement("div");
    item.className = "source-item";
    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = source.name;
    const meta = document.createElement("small");
    const recognition = source.recognition || {};
    const recognitionLabel = recognition.category ? ` · ${recognition.category}` : "";
    const deleted = source.status === "deleted";
    const archiveLabel = source.archive_category ? ` · ${source.archive_category}` : "";
    meta.textContent = `${source.kind} · ${deleted ? "已删除（保留记录）" : recognition.status === "completed" ? "已识别归档" : "已保存"}${archiveLabel}${recognitionLabel}`;
    const pathInfo = document.createElement("small");
    pathInfo.className = "source-path";
    const artifactPath = recognition.artifact?.storage_path ? `\n识别稿：${recognition.artifact.storage_path}` : "";
    const archiveStoragePath = source.archive_storage_path ? `\n分类文件夹：${source.archive_storage_path}` : "";
    pathInfo.textContent = `归档位置：${source.archive_path || source.archive_area || "项目资料库/待分类"}${archiveStoragePath}\n原件：${source.storage_path || "路径未记录"}${artifactPath}`;
    info.append(name, meta, pathInfo);
    const stateTag = document.createElement("span");
    stateTag.className = `source-state source-${recognition.status || "pending"}`;
    stateTag.textContent = deleted ? "已删除·留痕" : recognition.status === "completed" ? "本地完成" : recognition.status === "needs_ocr" ? "待 OCR" : recognition.status === "unavailable" || recognition.status === "error" ? "未转换" : "待识别";
    if (recognition.message) item.title = recognition.message;
    const actions = document.createElement("details");
    actions.className = "source-actions-menu";
    const actionSummary = document.createElement("summary");
    actionSummary.className = "icon-button source-menu-trigger";
    actionSummary.textContent = "⋯ 操作";
    actions.append(actionSummary);
    const actionPanel = document.createElement("div");
    actionPanel.className = "source-actions";
    actions.append(actionPanel);
    const viewButton = document.createElement("button");
    viewButton.type = "button";
    viewButton.className = "icon-button source-view-button";
    viewButton.textContent = "查看";
    viewButton.addEventListener("click", () => viewSource(source));
    actionPanel.append(viewButton);
    const copyPathButton = document.createElement("button");
    copyPathButton.type = "button";
    copyPathButton.className = "icon-button";
    copyPathButton.textContent = "复制路径";
    copyPathButton.addEventListener("click", () => copySourcePaths(source));
    actionPanel.append(copyPathButton);
    if (recognition.artifact) {
      const artifactButton = document.createElement("button");
      artifactButton.type = "button";
      artifactButton.className = "icon-button";
      artifactButton.textContent = "查看识别稿";
      artifactButton.addEventListener("click", () => viewSource(source, true));
      actionPanel.append(artifactButton);
    }
    if (!deleted) {
      const modifyButton = document.createElement("button");
      modifyButton.type = "button";
      modifyButton.className = "icon-button";
      modifyButton.textContent = "修改信息";
      modifyButton.addEventListener("click", () => modifySource(source));
      actionPanel.append(modifyButton);
    }
    const localButton = document.createElement("button");
    localButton.type = "button";
    localButton.className = "icon-button";
    localButton.textContent = "本地识别";
    localButton.addEventListener("click", () => recognizeSource(source.source_id, "local-auto"));
    if (!deleted) actionPanel.append(localButton);
    if (!deleted && recognition.status === "needs_ocr") {
      const externalButton = document.createElement("button");
      externalButton.type = "button";
      externalButton.className = "icon-button external-action";
      externalButton.textContent = "外部 OCR";
      externalButton.addEventListener("click", () => requestExternalOcr(source.source_id));
      actionPanel.append(externalButton);
    }
    if (!deleted && isManager()) {
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "icon-button danger-action";
      deleteButton.textContent = "删除（留痕）";
      deleteButton.addEventListener("click", () => deleteSource(source, targetId));
      actionPanel.append(deleteButton);
    } else if (!deleted) {
      const permission = document.createElement("small");
      permission.className = "permission-note";
      permission.textContent = "删除需造价经理";
      actionPanel.append(permission);
    }
    item.append(info, stateTag, actions);
    return item;
  }));
  if (isCompactList && collapsedCount > 0) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "button button-quiet source-list-toggle";
    toggle.setAttribute("aria-expanded", String(listExpanded));
    toggle.textContent = listExpanded
      ? "收起资料（保留最新 2 项）"
      : `⋯ 其余 ${collapsedCount} 项资料`;
    toggle.addEventListener("click", () => {
      if (isProjectLibrary) state.sourceListExpanded = !listExpanded;
      else state.sourceListExpandedByTarget[targetId] = !listExpanded;
      renderSourceList(targetId, filter);
    });
    list.append(toggle);
  }
}

function renderIntakeProgress(targetId, files, archiveArea) {
  const target = $(targetId);
  if (!target) return;
  target.className = "intake-report-list";
  target.replaceChildren(...files.map((file) => {
    const item = document.createElement("div");
    item.className = "intake-report intake-pending";
    const title = document.createElement("strong");
    title.textContent = file.name;
    const message = document.createElement("span");
    message.textContent = "正在快速保存到本地分类文件夹，识别将在保存后后台更新…";
    const path = document.createElement("small");
    path.className = "intake-path";
    path.textContent = `保存位置：${archiveArea}/${file.name}`;
    item.append(title, message, path);
    return item;
  }));
}

function intakeCompletionMessage(files, reports, label = "资料") {
  const failures = reports.filter((report) => report.status === "error").length;
  const saved = reports.length - failures;
  if (failures) return `${saved} 个${label}已保存，${failures} 个失败，请查看下方结果`;
  return `${files.length} 个${label}已保存到本地，识别结果见下方`;
}

function renderIntakeReports(targetId = "boqIntakeSummary", reports = state.intakeReports) {
  const target = $(targetId);
  if (!target) return;
  if (!reports.length) {
    target.replaceChildren();
    return;
  }
  target.className = "intake-report-list";
  target.replaceChildren(...reports.map((report) => {
    const item = document.createElement("div");
    item.className = `intake-report intake-${report.status}`;
    const title = document.createElement("strong");
    title.textContent = report.name;
    const message = document.createElement("span");
    message.textContent = report.message;
    item.append(title, message);
    if (report.archive_path || report.archive_area) {
      const archive = document.createElement("small");
      archive.className = "intake-path";
      archive.textContent = `归档位置：${report.archive_path || report.archive_area}`;
      item.append(archive);
    }
    if (report.archive_storage_path) {
      const archiveStorage = document.createElement("small");
      archiveStorage.className = "intake-path";
      archiveStorage.textContent = `分类文件夹：${report.archive_storage_path}`;
      item.append(archiveStorage);
    }
    if (report.storage_path) {
      const path = document.createElement("small");
      path.className = "intake-path";
      path.textContent = `本地原件：${report.storage_path}`;
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

function renderPersonnelTable(container) {
  if (!container) return;
  const users = state.personnel.users || [];
  if (!users.length) {
    container.textContent = "暂无人员记录";
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>姓名/登录名</th><th>主岗位</th><th>岗位组合</th><th>权限级别</th><th>成本明细</th><th>人员管理授权</th><th>录入时间</th><th>操作</th></tr></thead>";
  const body = document.createElement("tbody");
  users.forEach((user) => {
    const row = document.createElement("tr");
    const assignedRoles = user.roles || [user.role];
    const isMergedFieldRole = assignedRoles.includes("surveyor") && assignedRoles.includes("site_engineer");
    const assignmentLabel = isMergedFieldRole
      ? "施工员 + 测量员（合并）"
      : assignedRoles.map((role) => (state.personnel.roles || []).find((item) => item.role === role)?.label || role).join("、");
    [
      user.username,
      user.role_label,
      assignmentLabel,
      `L${user.role_level}`,
      user.can_view_cost_detail ? "可查看" : "按角色隐藏",
      user.role === "administrative_officer"
        ? user.personnel_admin_authorized ? "已获项目经理授权" : "待项目经理授权"
        : "—",
      user.created_at ? new Date(user.created_at).toLocaleString("zh-CN") : "—",
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "—");
      row.append(cell);
    });
    const actions = document.createElement("td");
    actions.className = "action-row";
    if (canAuthorizePersonnel() && user.role === "administrative_officer") {
      const authorization = document.createElement("button");
      authorization.className = "button button-quiet";
      authorization.type = "button";
      authorization.textContent = user.personnel_admin_authorized ? "撤销授权" : "授权管理";
      authorization.addEventListener("click", () => togglePersonnelAdmin(user.id, !user.personnel_admin_authorized));
      actions.append(authorization);
    }
    const remove = document.createElement("button");
    remove.className = "button button-danger";
    remove.type = "button";
    remove.textContent = "删除";
    remove.disabled = user.id === state.auth.user?.id;
    remove.title = remove.disabled ? "不能删除当前登录账号" : "删除后从活动人员名册移除，操作会留痕";
    remove.addEventListener("click", () => deletePersonnel(user));
    actions.append(remove);
    const rename = document.createElement("button");
    rename.className = "button button-quiet";
    rename.type = "button";
    rename.textContent = "更换姓名";
    rename.title = "保留原 user_id、密码、岗位和项目成果，仅更新姓名/登录名";
    rename.addEventListener("click", () => renamePersonnel(user));
    actions.append(rename);
    if (assignedRoles.includes("surveyor") || assignedRoles.includes("site_engineer")) {
      const roleToggle = document.createElement("button");
      roleToggle.className = "button button-quiet";
      roleToggle.type = "button";
      roleToggle.textContent = isMergedFieldRole ? "拆分岗位" : "合并测量/施工";
      roleToggle.title = isMergedFieldRole ? "恢复为单一主岗位" : "让同一账号同时承担施工员和测量员";
      roleToggle.addEventListener("click", () => toggleFieldRoleAssignment(user, !isMergedFieldRole));
      actions.append(roleToggle);
    }
    row.append(actions);
    body.append(row);
  });
  table.append(body);
  container.replaceChildren(table);
}

function renderPersonnelAudit(container) {
  if (!container) return;
  const events = [...(state.personnel.audit_log || [])].reverse();
  if (!events.length) {
    container.textContent = "暂无人员管理操作记录";
    return;
  }
  container.replaceChildren(...events.map((event) => {
    const row = document.createElement("div");
    row.className = "audit-row";
    const time = document.createElement("span");
    time.textContent = event.timestamp ? new Date(event.timestamp).toLocaleString("zh-CN") : "—";
    const actor = document.createElement("span");
    actor.textContent = `${event.actor?.username || "—"} · ${event.actor?.role_label || event.actor?.role || "—"}`;
    const detail = document.createElement("small");
    detail.textContent = `${event.action || "—"} · ${event.details?.username || event.target || "—"}`;
    row.append(time, actor, detail);
    return row;
  }));
}

function renderPersonnel() {
  if (!canManagePersonnel()) {
    setView(isKpiOnly() ? "dashboard" : "overview");
    return;
  }
  const fallbackRoles = [
    ["project_manager", "项目经理"], ["cost_manager", "造价经理"], ["cost_estimator", "造价员"],
    ["technical_lead", "技术负责人"], ["production_manager", "生产经理"], ["site_engineer", "施工员/测量员"],
    ["surveyor", "测量员"], ["quality_officer", "质量负责人"], ["lab_testing_officer", "试验检测员"],
    ["document_controller", "资料员"], ["safety_officer", "安全员"], ["procurement_officer", "采购员"],
    ["warehouse_officer", "仓管员"], ["administrative_officer", "行政人员"],
  ];
  const roles = state.personnel.roles?.length ? state.personnel.roles : fallbackRoles.map(([role, label]) => ({ role, label }));
  const roleOptions = roles.map((role) => `<option value="${escapeHtml(role.role)}">${escapeHtml(role.label)}${role.description ? ` · ${escapeHtml(role.description)}` : ""}</option>`).join("");
  const policyText = state.personnel.policy?.authorization || "项目经理可直接管理；行政人员需经项目经理明确授权后管理；其他岗位无人员管理权限。";
  const handoverText = state.personnel.policy?.handover || "更换姓名只更新登录名和显示名，保留原账号的 user_id、密码、岗位、审计和项目成果。";
  const projectScopeText = state.personnel.policy?.project_scope || "当前名册仅属于当前项目，其他项目不会共享新增、删除和岗位调整。";
  const temporaryCredentials = state.personnel.temporary_credentials;
  const credentialNotice = temporaryCredentials
    ? `<div class="notice-line credential-notice"><strong>请交给本人登录</strong><span>姓名/登录名：${escapeHtml(temporaryCredentials.username)} · 岗位：${escapeHtml(temporaryCredentials.role_label || temporaryCredentials.role)} · 初始密码：<code>${escapeHtml(temporaryCredentials.password)}</code>。${escapeHtml(temporaryCredentials.notice || "刷新后不再显示此密码。")}</span></div>`
    : "";
  $("workspaceContent").innerHTML =
    `<div class="surface-title"><div><span class="panel-label">PERSONNEL MANAGEMENT</span><h3>人员管理</h3></div><span class="surface-caption">当前项目：${escapeHtml(state.projectName || state.projectId || "未命名项目")} · 项目经理直管；行政人员授权后协同</span></div>` +
    `<div class="notice-line"><strong>人员治理规则</strong><span>${escapeHtml(policyText)} ${escapeHtml(handoverText)} ${escapeHtml(projectScopeText)}</span></div>` +
    credentialNotice +
    '<div class="control-grid personnel-grid">' +
    '<section class="control-panel"><span class="panel-label">NEW PERSONNEL</span><h3>录入人员</h3>' +
    '<form id="personnelForm" class="work-form"><div class="field-grid personnel-field-grid"><label>姓名/登录名<input id="personnelUsername" autocomplete="off" required minlength="1" maxlength="64" /></label><label>岗位角色<select id="personnelRole">' + roleOptions + '</select></label></div>' +
    '<div class="permission-note">只需录入姓名和岗位。系统自动生成初始登录密码，仅在保存成功后返回并显示一次，由项目经理或已授权行政人员安全交给本人；人员以后用“姓名/登录名 + 初始密码”登录。</div>' +
    '<div class="action-row"><button class="button button-primary" type="submit">保存人员</button><span id="personnelStatus" class="request-status"></span></div></form></section>' +
    '<section class="control-panel"><div class="surface-title"><div><span class="panel-label">LOCAL USERS</span><h3>已登记人员</h3></div><span class="surface-caption">共 <strong id="personnelCount">0</strong> 人</span></div><div id="personnelTable" class="table-wrap"></div></section></div>' +
    '<section class="control-panel audit-panel"><div class="surface-title"><div><span class="panel-label">PERSONNEL AUDIT TRAIL</span><h3>人员管理留痕</h3></div><span class="surface-caption">新增账号会记录操作人、角色、时间和目标</span></div><div id="personnelAudit" class="audit-list"></div></section>';
  $("personnelCount").textContent = String((state.personnel.users || []).length);
  renderPersonnelTable($("personnelTable"));
  renderPersonnelAudit($("personnelAudit"));
  $("personnelForm").addEventListener("submit", savePersonnel);
}

function syncCurrentPersonnelUser() {
  const current = (state.personnel.users || []).find((item) => item.id === state.auth.user?.id);
  if (current) {
    state.auth.user = current;
    $("userRole").textContent = `${current.role_label} · ${current.username}`;
  }
}

async function renamePersonnel(user) {
  const nextName = window.prompt("输入接管后的姓名/登录名。原 user_id、密码和项目成果会保留。", user.username);
  if (!nextName || nextName.trim() === user.username) return;
  setError("");
  try {
    state.personnel = await apiJson("/api/personnel/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, user_id: user.id, new_username: nextName.trim() }),
    });
    syncCurrentPersonnelUser();
    renderPersonnel();
    setStatus(`账号已由“${user.username}”交接为“${nextName.trim()}”，原有成果继续保留`);
  } catch (error) {
    setError(error.message);
  }
}

async function toggleFieldRoleAssignment(user, merged) {
  const roles = merged
    ? ["surveyor", "site_engineer"]
    : [user.role];
  if (merged && !window.confirm("确认让该账号同时承担施工员和测量员吗？原有成果不复制、不丢失。")) return;
  setError("");
  try {
    state.personnel = await apiJson("/api/personnel/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, user_id: user.id, roles }),
    });
    syncCurrentPersonnelUser();
    renderPersonnel();
    setStatus(merged ? "已合并施工员与测量员岗位" : "已拆分为单一主岗位");
  } catch (error) {
    setError(error.message);
  }
}

async function togglePersonnelAdmin(userId, authorized) {
  setError("");
  try {
    state.personnel = await apiJson("/api/personnel/authorize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, user_id: userId, authorized }),
    });
    renderPersonnel();
    setStatus(authorized ? "行政人员已获得人员管理授权" : "行政人员授权已撤销");
  } catch (error) {
    setError(error.message);
  }
}

async function deletePersonnel(user) {
  if (user.id === state.auth.user?.id) return;
  if (!window.confirm(`确定从活动名册删除“${user.username}”（${user.role_label}）吗？删除会保留审计记录。`)) return;
  setError("");
  try {
    state.personnel = await apiJson("/api/personnel/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, user_id: user.id }),
    });
    renderPersonnel();
    setStatus("人员已从活动名册移除，操作已留痕");
  } catch (error) {
    setError(error.message);
  }
}

async function savePersonnel(event) {
  event.preventDefault();
  setError("");
  const status = $("personnelStatus");
  try {
    const response = await apiJson("/api/personnel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.projectId,
        username: $("personnelUsername").value,
        role: $("personnelRole").value,
      }),
    });
    state.personnel = response;
    $("personnelForm").reset();
    status.textContent = "人员已保存，操作已留痕";
    renderPersonnel();
    setStatus("人员管理已更新");
  } catch (error) {
    status.textContent = "保存失败";
    setError(error.message);
  }
}

async function refreshPersonnel() {
  if (!canManagePersonnel()) return;
  try {
    state.personnel = await apiJson(`/api/personnel?project_id=${encodeURIComponent(state.projectId)}`);
  } catch (error) {
    setError(error.message);
  }
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
    '<div class="surface-title"><div><span class="panel-label">PROJECT CONTROL</span><h3>造价经理项目控制台</h3></div><span class="surface-caption">权限、文件状态、风险分级与全部操作留痕</span></div>' +
    '<div class="control-grid">' +
    '<section class="control-panel"><span class="panel-label">PERMISSION POLICY</span><h3>角色权限</h3>' +
    '<div class="policy-row"><strong>项目经理（一级）</strong><span>仅查看重要指标、风险预警、成本超限和周期趋势</span></div>' +
    '<div class="policy-row"><strong>造价经理（一级）</strong><span>全部 P01–P08、资料、成本、导出、删除和审计权限</span></div>' +
    '<div class="policy-row"><strong>造价员（二级）</strong><span>资料录入、识别、业务操作；敏感价格与成本明细不回显</span></div>' +
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

async function recognizeSource(sourceId, connectorId = "local-auto", allowExternal = false, { silent = false } = {}) {
  if (!silent) setError("");
  try {
    const response = await apiJson("/api/source/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, source_id: sourceId, connector_id: connectorId, allow_external: allowExternal }),
    });
    applyWorkspace(response.workspace);
    if (!silent) {
      renderSourceList();
      updateContextBar();
      setStatus(response.recognition?.message || "资料识别完成");
    }
    return response;
  } catch (error) {
    if (!silent) setError(error.message);
    throw error;
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

async function recognizeSavedSources(sourceIds, { listId = "", filter = {}, summaryId = "" } = {}) {
  if (!sourceIds.length) return;
  setStatus(`本地资料已快速保存，正在后台识别 ${sourceIds.length} 项资料…`);
  const results = [];
  for (const sourceId of sourceIds) {
    try {
      await recognizeSource(sourceId, "local-auto", false, { silent: true });
      results.push({ status: "fulfilled" });
    } catch (error) {
      results.push({ status: "rejected", reason: error });
    }
  }
  await refreshWorkspace();
  const sourceMap = new Map((state.sources || []).map((source) => [source.source_id, source]));
  state.intakeReports = state.intakeReports.map((report) => {
    const source = sourceMap.get(report.source_id);
    if (!source) return report;
    const recognition = recognitionReport(source);
    return {
      ...report,
      ...recognition,
      archive_area: source.archive_area || report.archive_area,
      archive_path: source.archive_path || report.archive_path,
      archive_storage_path: source.archive_storage_path || report.archive_storage_path,
      storage_path: source.storage_path || report.storage_path,
    };
  });
  renderIntakeReports(summaryId || "boqIntakeSummary");
  renderSourceList();
  if (listId) renderSourceList(listId, filter);
  updateContextBar();
  const failed = results.filter((result) => result.status === "rejected").length;
  setStatus(failed ? `本地资料已保存，${failed} 项识别失败，请查看资料状态` : "本地资料已保存，识别结果已更新");
}

async function uploadSourceFile(file, projectId, index = 0, parseBoq = false, metadata = {}) {
  const sourceId = sourceIdFor(file, index);
  const form = new FormData();
  form.append("project_id", projectId);
  form.append("source_id", sourceId);
  if (metadata.archiveArea) form.append("archive_area", metadata.archiveArea);
  if (metadata.archiveCategory) form.append("archive_category", metadata.archiveCategory);
  if (metadata.deferRecognition) form.append("recognize", "false");
  form.append("file", file, file.name);
  if (parseBoq && isTableSource(file)) {
    const result = await apiJson("/api/boq/upload", { method: "POST", body: form });
    const source = result.source || null;
    return {
      sourceId,
      result,
      source,
      report: {
        status: "table",
        message: `已读取 ${result.item_count} 项清单并保存到本地，进入清单核对。`,
        archive_area: source?.archive_area,
        archive_path: source?.archive_path || result.archive?.path,
        archive_storage_path: source?.archive_storage_path,
        storage_path: source?.storage_path || result.archive?.storage_path,
      },
    };
  }
  const response = await apiJson("/api/source/upload", { method: "POST", body: form });
  return {
    sourceId,
    result: null,
    source: response.source,
    report: {
      ...recognitionReport(response.source),
      archive_area: response.source.archive_area,
      archive_path: response.source.archive_path,
      archive_storage_path: response.source.archive_storage_path,
      storage_path: response.source.storage_path,
    },
  };
}

async function uploadFiles(files, { parseBoq = false, archiveArea = "", archiveCategory = "", listId = "", summaryId = "" } = {}) {
  const context = await ensureProject();
  const items = [];
  const reports = [];
  setStatus(`正在快速保存 ${files.length} 项资料到本地分类文件夹…`);
  for (const [index, file] of files.entries()) {
    setStatus(`正在快速保存到本地 ${index + 1}/${files.length}：${file.name}`);
    try {
      const uploaded = await uploadSourceFile(file, context.project_id, index, parseBoq, { archiveArea, archiveCategory, deferRecognition: true });
      items.push(...(uploaded.result?.items || []));
      reports.push({ name: file.name, source_id: uploaded.sourceId, ...(uploaded.report || { status: "completed", message: "已保存。" }) });
    } catch (error) {
      reports.push({ name: file.name, status: "error", message: error.message || "文件处理失败。" });
    }
  }
  const orderedReports = reports;
  await refreshWorkspace();
  const sourceMap = new Map((state.sources || []).map((source) => [source.source_id, source]));
  for (const report of orderedReports) {
    const source = sourceMap.get(report.source_id);
    const recognition = source?.recognition;
    if (source?.archive_area) report.archive_area = source.archive_area;
    if (source?.archive_path) report.archive_path = source.archive_path;
    if (source?.archive_storage_path) report.archive_storage_path = source.archive_storage_path;
    if (source?.storage_path) report.storage_path = source.storage_path;
    if (report.status === "table" && recognition && recognition.status !== "completed") {
      report.status = recognition.status || "unavailable";
      report.message = `${report.message} ${recognitionReport(source).message}`;
    }
  }
  const sourceNames = files.map((file) => file.name);
  state.fileName = sourceNames.length === 1 ? sourceNames[0] : `${sourceNames.length} 个文件`;
  state.sourceName = state.fileName;
  state.intakeReports = orderedReports;
  const deferredSourceIds = orderedReports
    .filter((report) => report.status !== "error" && report.source_id)
    .map((report) => report.source_id);
  if (deferredSourceIds.length) {
    void recognizeSavedSources(deferredSourceIds, { listId, filter: { archiveArea }, summaryId }).catch((error) => setError(error.message));
  }
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
  return { files, reports: orderedReports, items };
}

async function handleSourceFile(event) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  setError("");
  renderIntakeProgress("sourceIntakeSummary", files, PROJECT_ARCHIVE_AREAS.overview);
  setStatus(`已选择 ${files.length} 个资料，准备保存到 ${PROJECT_ARCHIVE_AREAS.overview}`);
  try {
    const { reports } = await uploadFiles(files, { archiveArea: PROJECT_ARCHIVE_AREAS.overview, archiveCategory: "项目初步信息", listId: "sourceList", summaryId: "sourceIntakeSummary" });
    renderSourceList();
    updateContextBar();
    renderIntakeReports("sourceIntakeSummary");
    setStatus(intakeCompletionMessage(files, reports));
    $("projectSaveStatus").textContent = intakeCompletionMessage(files, reports, "资料");
  } catch (error) {
    setError(error.message);
  } finally {
    event.target.value = "";
  }
}

async function handleContractSourceFiles(event) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  setError("");
  const archiveArea = "项目资料库/合同与招采依据";
  const archiveCategory = $("contractArchiveCategory")?.value || "合同阶段";
  const archivePath = `${archiveArea}/${archiveCategory}`;
  renderIntakeProgress("contractIntakeSummary", files, archivePath);
  setStatus(`已选择 ${files.length} 个合同资料，准备保存到 ${archivePath}`);
  try {
    const { reports } = await uploadFiles(files, {
      archiveArea,
      archiveCategory,
      listId: "contractSourceList",
      summaryId: "contractIntakeSummary",
    });
    renderSourceList("contractSourceList", { archiveArea });
    renderIntakeReports("contractIntakeSummary");
    updateContextBar();
    setStatus(intakeCompletionMessage(files, reports, "合同资料"));
    renderAssist();
  } catch (error) {
    setError(error.message);
  } finally {
    event.target.value = "";
  }
}

function stageSourcePanel(stage, title, note) {
  const archiveArea = PROJECT_ARCHIVE_AREAS[stage] || "项目资料库/待分类";
  return `
    <section class="source-panel stage-source-panel">
      <div class="surface-title"><div><span class="panel-label">${stage.toUpperCase()} FILE INTAKE</span><h3>${title}录入</h3></div><button id="upload-${stage}-source" class="button button-quiet" type="button">＋录入${title}</button></div>
      <p class="business-note">${note} 原件保存在本地资料库并自动识别，业务登记表仍需人工核对后保存。</p>
      <div class="archive-location"><span>本入口归档位置</span><strong>${archiveArea}</strong></div>
      <div id="${stage}SourceList" class="source-list"></div>
      <div id="${stage}IntakeSummary" class="intake-report-list"></div>
    </section>`;
}

function bindStageSourcePanel(stage, label) {
  const listId = `${stage}SourceList`;
  const summaryId = `${stage}IntakeSummary`;
  renderSourceList(listId, { archiveArea: PROJECT_ARCHIVE_AREAS[stage] });
  renderIntakeReports(summaryId);
  $(`upload-${stage}-source`).addEventListener("click", () => $("stageSourceInput").click());
  $("stageSourceInput").dataset.stage = stage;
  $("stageSourceInput").onchange = (event) => handleStageSourceFiles(event, { label, listId, summaryId });
}

async function handleStageSourceFiles(event, { label, listId, summaryId }) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  setError("");
  const stage = event.target.dataset.stage || "";
  const archiveArea = PROJECT_ARCHIVE_AREAS[stage] || "项目资料库/待分类";
  renderIntakeProgress(summaryId, files, archiveArea);
  setStatus(`已选择 ${files.length} 个${label}文件，准备保存到 ${archiveArea}`);
  try {
    const { reports } = await uploadFiles(files, { archiveArea, archiveCategory: label, listId, summaryId });
    renderSourceList(listId, { archiveArea });
    renderIntakeReports(summaryId);
    updateContextBar();
    setStatus(intakeCompletionMessage(files, reports, label));
    renderAssist();
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
  renderIntakeProgress("sourceIntakeSummary", files, PROJECT_ARCHIVE_AREAS.overview);
  setStatus(`已选择 ${files.length} 个初步资料，准备保存到 ${PROJECT_ARCHIVE_AREAS.overview}`);
  try {
    const { reports } = await uploadFiles(files, { archiveArea: PROJECT_ARCHIVE_AREAS.overview, archiveCategory: "项目初步信息", listId: "sourceList", summaryId: "sourceIntakeSummary" });
    renderOverview();
    renderIntakeReports("sourceIntakeSummary");
    setStatus(intakeCompletionMessage(files, reports, "初步资料"));
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

async function legacyDownloadProjectFile(kind) {
  if (!state.workspace) {
    setError("请先保存项目");
    return;
  }
  try {
    const response = await fetch(`/api/workspace/${encodeURIComponent(state.projectId)}/${kind}`, { headers: { Authorization: `Bearer ${state.auth.token}` } });
    if (!response.ok) throw new Error(`文件导出失败（${response.status}）`);
    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `${state.projectId}-${kind.replaceAll("/", "-")}`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  } catch (error) {
    setError(error.message);
  }
}

function availableExportOptions() {
  return EXPORT_OPTIONS.filter((option) => !option.requiresCostDetail || canViewCostDetail());
}

function exportOption(kind) {
  const options = availableExportOptions();
  return options.find((option) => option.kind === kind) || options[0];
}

function defaultExportFilename(kind) {
  const projectId = state.projectId || "buildcostiq-project";
  if (kind === "report") return projectId + "-report.html";
  if (kind === "boq.xlsx") return projectId + "-boq.xlsx";
  if (kind === "cost-plan.xlsx") return projectId + "-cost-plan.xlsx";
  return projectId + "-buildcostiq.zip";
}

function openExportWorkspace(kind) {
  const option = exportOption(kind);
  state.exportWorkspace = { kind: option.kind, filename: defaultExportFilename(option.kind), directoryHandle: null };
  setView("export");
}

function setExportStatus(message, tone = "") {
  const target = $("exportStatus");
  if (!target) return;
  target.className = ("export-status " + tone).trim();
  target.textContent = message;
}

function renderExportDirectory() {
  const target = $("exportDirectoryName");
  if (!target) return;
  target.textContent = state.exportWorkspace.directoryHandle?.name || "尚未选择文件夹";
}

function renderExportWorkspace() {
  const options = availableExportOptions();
  const selected = exportOption(state.exportWorkspace.kind);
  state.exportWorkspace.kind = selected.kind;
  state.exportWorkspace.filename = state.exportWorkspace.filename || defaultExportFilename(selected.kind);
  const optionHtml = options.map((option) => (
    '<option value="' + option.kind + '"' + (option.kind === selected.kind ? " selected" : "") + ">" + option.label + "</option>"
  )).join("");
  $("workspaceContent").innerHTML = [
    '<div class="surface-title"><div><span class="panel-label">LOCAL EXPORT CENTER</span><h3>导出项目资料</h3></div><span class="surface-caption">先确认导出内容和本地目标文件夹，再写入文件</span></div>',
    '<div class="capability-intro"><strong>导出文件只写入你明确选择的本地位置。</strong><span>系统不会把项目资料发送到外部服务；浏览器不支持文件夹授权时可改用默认下载。</span></div>',
    '<div class="export-workspace">',
    '<section class="export-panel"><div class="data-entry-heading"><div><span class="panel-label">EXPORT SETTINGS</span><h3>导出设置</h3></div><span class="request-status" id="exportSelectedDescription"></span></div>',
    '<div class="field-grid export-fields"><label>导出内容<select id="exportKind">' + optionHtml + '</select></label><label>文件名<input id="exportFilename" /></label></div>',
    '<div class="export-folder-card"><div><span class="panel-label">TARGET FOLDER</span><strong id="exportDirectoryName">尚未选择文件夹</strong><small>选择后将直接写入该文件夹，不经过服务器。</small></div><button id="chooseExportDirectory" class="button button-quiet" type="button">选择导出文件夹</button></div>',
    '<div class="action-row"><button id="confirmExport" class="button button-primary" type="button">确认导出到所选文件夹</button><button id="downloadExport" class="button button-quiet" type="button">下载到默认位置</button><button id="backFromExport" class="button button-quiet" type="button">返回资料库</button></div>',
    '<div id="exportStatus" class="export-status">请选择目标文件夹后确认导出。</div></section>',
    '<aside class="export-panel export-notes"><span class="panel-label">EXPORT NOTE</span><h3>本次导出内容</h3><p id="exportDescription"></p><div class="notice-line"><strong>本地优先</strong><span>导出动作会保留当前项目编号和文件名，便于归档、交接和追溯。</span></div></aside>',
    '</div>',
  ].join("");
  $("exportFilename").value = state.exportWorkspace.filename;
  $("exportSelectedDescription").textContent = selected.description;
  $("exportDescription").textContent = selected.description;
  renderExportDirectory();
  $("exportKind").addEventListener("change", (event) => {
    state.exportWorkspace.kind = event.target.value;
    state.exportWorkspace.filename = defaultExportFilename(event.target.value);
    $("exportFilename").value = state.exportWorkspace.filename;
    const option = exportOption(event.target.value);
    $("exportSelectedDescription").textContent = option.description;
    $("exportDescription").textContent = option.description;
    setExportStatus("导出内容已切换，请确认文件名和目标文件夹。", "info");
  });
  $("exportFilename").addEventListener("input", (event) => { state.exportWorkspace.filename = event.target.value; });
  $("chooseExportDirectory").addEventListener("click", chooseExportDirectory);
  $("confirmExport").addEventListener("click", confirmExportToDirectory);
  $("downloadExport").addEventListener("click", () => downloadProjectFile(state.exportWorkspace.kind));
  $("backFromExport").addEventListener("click", () => setView("overview"));
}

async function chooseExportDirectory() {
  if (!window.showDirectoryPicker) {
    setExportStatus("当前浏览器不支持直接选择文件夹，请使用“下载到默认位置”。", "warn");
    return;
  }
  try {
    state.exportWorkspace.directoryHandle = await window.showDirectoryPicker({ mode: "readwrite" });
    renderExportDirectory();
    setExportStatus("已选择文件夹：" + state.exportWorkspace.directoryHandle.name + "，可以确认导出。", "ok");
  } catch (error) {
    if (error.name !== "AbortError") setExportStatus("选择文件夹失败：" + error.message, "error");
  }
}

async function fetchProjectFile(kind) {
  if (!state.workspace) throw new Error("请先保存项目");
  const option = exportOption(kind);
  const response = await fetch(
    "/api/workspace/" + encodeURIComponent(state.projectId) + "/" + option.route,
    { headers: { Authorization: "Bearer " + state.auth.token } },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || ("文件导出失败（" + response.status + "）"));
  }
  return response.blob();
}

function triggerBrowserDownload(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

async function confirmExportToDirectory() {
  const filename = (state.exportWorkspace.filename || "").trim();
  if (!filename) {
    setExportStatus("请填写导出文件名。", "error");
    return;
  }
  if (!state.exportWorkspace.directoryHandle) {
    setExportStatus("请先选择导出文件夹；如需使用浏览器默认位置，请点击“下载到默认位置”。", "warn");
    return;
  }
  try {
    const blob = await fetchProjectFile(state.exportWorkspace.kind);
    const fileHandle = await state.exportWorkspace.directoryHandle.getFileHandle(filename, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(blob);
    await writable.close();
    setExportStatus("导出完成：" + state.exportWorkspace.directoryHandle.name + "\\" + filename, "ok");
  } catch (error) {
    setExportStatus("导出失败：" + error.message, "error");
  }
}

async function downloadProjectFile(kind) {
  try {
    const filename = (state.exportWorkspace.filename || defaultExportFilename(kind)).trim();
    const blob = await fetchProjectFile(kind);
    triggerBrowserDownload(blob, filename);
    setExportStatus("已交给浏览器下载：" + filename, "ok");
  } catch (error) {
    setExportStatus(error.message, "error");
  }
}

function basisCategoryLabel(category) {
  return (state.basisCatalog.categories || []).find((item) => item.id === category)?.label
    || BASIS_CATEGORIES.find(([id]) => id === category)?.[1]
    || category || "外部依据";
}

function gatewayBasis(item) {
  if (!item) return null;
  const priceType = {
    pricing_basis: "quota_base",
    price_info: "information_price",
    market_price: "market_quote",
  }[item.category] || "";
  const taxMode = (item.tax_mode || "").includes("不含") ? "tax_exclusive" : (item.tax_mode || "").includes("含") ? "tax_inclusive" : "";
  return {
    tax_inclusion: taxMode,
    price_type: priceType,
    source: [item.source_org, item.title, item.version].filter(Boolean).join(" · "),
    price_date: item.published_at || item.version || item.effective_from || "",
  };
}

function stageBasisContexts(stage) {
  const references = state.basisReferences.filter((item) => item.stage === stage);
  const contractReference = references.find((item) => item.category === "pricing_basis");
  const marketReference = references.find((item) => ["price_info", "market_price"].includes(item.category));
  return {
    references,
    contract_basis: gatewayBasis(contractReference) || state.sample?.contract_basis || {},
    market_basis: gatewayBasis(marketReference) || state.sample?.market_basis || {},
    subject_basis: gatewayBasis(contractReference) || state.sample?.subject_basis || {},
    reference_basis: gatewayBasis(marketReference) || state.sample?.reference_basis || {},
  };
}

function basisDisplayName(stage) {
  const latest = state.basisReferences.filter((item) => item.stage === stage).at(-1);
  return latest ? [latest.title || latest.name, latest.version].filter(Boolean).join(" · ") : "";
}

function basisReferencePanel(stage) {
  const references = state.basisReferences.filter((item) => item.stage === stage);
  const options = (state.basisCatalog.items || []).map((item) =>
    '<option value="' + (item.basis_id || "") + '">' + (item.title || item.name) + " · " + basisCategoryLabel(item.category) + (item.version ? " · " + item.version : "") + "</option>"
  ).join("");
  const referenceHtml = references.length
    ? references.map((item) =>
      '<div class="basis-reference-row"><strong>' + (item.title || item.name) + "</strong><span>" + basisCategoryLabel(item.category) + (item.version ? " · 版本 " + item.version : "") + (item.region ? " · " + item.region : "") + '</span><small>本地保存：' + (item.storage_path || "路径未记录") + "</small></div>"
    ).join("")
    : '<div class="empty-state">本阶段尚未引用外部依据。历史项目不会因依据库更新而被覆盖。</div>';
  return '<section id="basisReferencePanel-' + stage + '" class="basis-reference-panel">' +
    '<div class="data-entry-heading"><div><span class="panel-label">BASIS REFERENCE</span><h3>选择计价依据</h3></div><button class="button button-quiet" type="button" data-view="basis">进入外部依据库</button></div>' +
    '<p class="business-note">从本地外部依据库选择政策、定额、信息价或市场价；引用会保存当时的版本、有效期和本地路径快照。</p>' +
    '<div class="basis-reference-actions"><select id="basisReferenceSelect-' + stage + '"><option value="">' + (options ? "请选择本项目采用的依据" : "请先录入外部依据") + "</option>" + options + '</select><button id="saveBasisReference-' + stage + '" class="button button-quiet" type="button" ' + (options ? "" : "disabled") + '>保存本阶段引用</button></div>' +
    '<div class="basis-reference-list">' + referenceHtml + "</div></section>";
}

function bindBasisReferencePanel(stage) {
  const button = $("saveBasisReference-" + stage);
  if (button) button.addEventListener("click", () => saveBasisReference(stage));
  bindViewButtons();
}

async function saveBasisReference(stage) {
  const basisId = $("basisReferenceSelect-" + stage)?.value;
  if (!basisId) {
    setStatus("请先选择一项外部依据");
    return;
  }
  try {
    const response = await apiJson("/api/basis/reference", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, basis_id: basisId, stage }),
    });
    applyWorkspace(response.workspace);
    const panel = $("basisReferencePanel-" + stage);
    if (panel) panel.outerHTML = basisReferencePanel(stage);
    bindBasisReferencePanel(stage);
    setStatus(stage + " 已保存外部依据引用：" + (response.basis?.title || "已选择"));
  } catch (error) {
    setError(error.message);
  }
}

async function viewBasis(item, derived = false) {
  const popup = window.open("about:blank", "_blank", "noopener");
  try {
    const query = "/api/basis/view?basis_id=" + encodeURIComponent(item.basis_id) + (derived ? "&derived=1" : "");
    const response = await fetch(query, { headers: { Authorization: "Bearer " + state.auth.token } });
    if (!response.ok) throw new Error("依据查看失败（" + response.status + "）");
    const objectUrl = URL.createObjectURL(await response.blob());
    if (popup) popup.location.href = objectUrl;
    else window.open(objectUrl, "_blank", "noopener");
  } catch (error) {
    if (popup) popup.close();
    setError(error.message);
  }
}

async function copyBasisPath(item) {
  const paths = [item.archive_path, item.storage_path, item.recognition?.artifact?.storage_path].filter(Boolean).join(String.fromCharCode(10));
  try {
    await navigator.clipboard.writeText(paths);
    setStatus("依据保存位置已复制");
  } catch (_) {
    window.prompt("依据保存位置", paths);
  }
}

function renderBasisCatalog() {
  const target = $("basisCatalogList");
  if (!target) return;
  const filter = $("basisCategoryFilter")?.value || "";
  const items = (state.basisCatalog.items || []).filter((item) => !filter || item.category === filter);
  if (!items.length) {
    target.className = "basis-catalog-list empty-state";
    target.textContent = "当前分类还没有外部依据。";
    return;
  }
  target.className = "basis-catalog-list";
  target.replaceChildren(...items.slice().reverse().map((item) => {
    const card = document.createElement("article");
    card.className = "basis-item";
    const info = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.title || item.name;
    const meta = document.createElement("small");
    meta.textContent = basisCategoryLabel(item.category) + " · " + (item.source_org || "来源未填写") + (item.version ? " · 版本 " + item.version : "") + (item.source_url ? " · " + item.source_url : "");
    const scope = document.createElement("small");
    scope.textContent = "发布日期：" + (item.published_at || "未填写") + " · 适用地区：" + (item.region || "未填写") + " · 有效期：" + (item.effective_from || "未填写") + " 至 " + (item.effective_to || "未填写");
    const rule = document.createElement("small");
    rule.textContent = "税口径：" + (item.tax_mode || "未填写") + " · 计价口径：" + (item.pricing_mode || "未填写");
    const path = document.createElement("small");
    path.className = "source-path";
    path.textContent = "保存位置：" + (item.archive_path || "外部依据库") + String.fromCharCode(10) + "原件：" + (item.storage_path || "路径未记录");
    info.append(title, meta, scope, rule, path);
    const actions = document.createElement("div");
    actions.className = "source-actions";
    const view = document.createElement("button");
    view.type = "button"; view.className = "icon-button source-view-button"; view.textContent = "查看";
    view.addEventListener("click", () => viewBasis(item));
    actions.append(view);
    if (item.recognition?.artifact) {
      const derived = document.createElement("button");
      derived.type = "button"; derived.className = "icon-button"; derived.textContent = "查看识别稿";
      derived.addEventListener("click", () => viewBasis(item, true));
      actions.append(derived);
    }
    const copy = document.createElement("button");
    copy.type = "button"; copy.className = "icon-button"; copy.textContent = "复制路径";
    copy.addEventListener("click", () => copyBasisPath(item));
    actions.append(copy);
    card.append(info, actions);
    return card;
  }));
}

function renderBasis() {
  const basisCategoryPriority = prioritizedCategoryIds(
    state.basisCatalog.items || [],
    BASIS_CATEGORIES.map(([id]) => id),
    4,
  );
  const categoryOptions = groupedCategoryOptions(BASIS_CATEGORIES, basisCategoryPriority);
  $("workspaceContent").innerHTML =
    '<div class="surface-title"><div><span class="panel-label">EXTERNAL BASIS LIBRARY</span><h3>外部依据库</h3></div><span class="surface-caption">独立于项目资料库保存，按版本快照被项目引用</span></div>' +
    '<div class="capability-intro"><strong>项目资料库保存“这个项目发生了什么”；外部依据库存放“当时依据什么规则和价格判断”。</strong><span>外部接口只取得本地快照，默认不向外发送项目资料；依据被 P04、P05、P08 引用后，历史项目仍按当时版本复核。</span></div>' +
    '<div class="basis-layout">' +
      '<section class="basis-panel"><div class="data-entry-heading"><div><span class="panel-label">BASIS INTAKE</span><h3>录入外部依据</h3></div><span class="request-status">文件和元数据均保存在本地</span></div>' +
      '<div class="field-grid basis-fields">' +
        '<label>依据分类<select id="basisCategory">' + categoryOptions + '</select></label>' +
        '<label>依据名称<input id="basisTitle" placeholder="如：2026 年 7 月信息价" /></label>' +
        '<label>来源单位<input id="basisSourceOrg" placeholder="政府部门、造价站或供应商" /></label>' +
        '<label>来源地址<input id="basisSourceUrl" placeholder="可选：官网或接口地址" /></label>' +
        '<label>发布日期<input id="basisPublishedAt" type="date" /></label>' +
        '<label>版本号<input id="basisVersion" placeholder="如：2026-07" /></label>' +
        '<label>适用地区<input id="basisRegion" placeholder="如：浙江省 / 杭州市" /></label>' +
        '<label>税口径<input id="basisTaxMode" placeholder="含税/不含税" /></label>' +
        '<label>计价口径<input id="basisPricingMode" placeholder="清单计价/定额计价/市场价" /></label>' +
        '<label>有效期起<input id="basisEffectiveFrom" type="date" /></label>' +
        '<label>有效期止<input id="basisEffectiveTo" type="date" /></label>' +
      '</div>' +
      '<div class="intake-banner basis-file-picker"><div><strong id="basisFileName">尚未选择依据文件</strong><span>支持一次选择多个 PDF、Word、Excel、CSV、图片、文章和接口快照文件。</span></div><button id="chooseBasisFile" class="button button-quiet" type="button">选择依据文件</button></div>' +
      '<div class="archive-location"><span>选择后保存位置</span><strong id="basisSaveLocation">外部依据库/请选择分类/待选择文件</strong></div>' +
      '<div id="basisIntakeSummary" class="intake-report-list"></div>' +
      '<div class="action-row"><button id="saveBasis" class="button button-primary" type="button">保存到外部依据库</button><span id="basisUploadStatus" class="request-status"></span></div></section>' +
      '<aside class="basis-panel basis-boundary"><span class="panel-label">BOUNDARY</span><h3>资料边界</h3><div class="basis-boundary-row"><strong>项目资料库</strong><span>合同、清单、图纸、台账、变更、结算和证据</span></div><div class="basis-boundary-row"><strong>外部依据库</strong><span>政策、定额、信息价、市场价和接口快照</span></div><div class="basis-boundary-row"><strong>项目引用</strong><span>P04 建基线 · P05 编成本 · P08 做初审</span></div></aside>' +
    '</div>' +
    '<section class="basis-panel basis-catalog-panel"><div class="data-entry-heading"><div><span class="panel-label">LOCAL BASIS CATALOG</span><h3>本地依据目录</h3></div><label class="basis-filter">筛选分类<select id="basisCategoryFilter"><option value="">全部</option>' + categoryOptions + '</select></label></div><div id="basisCatalogList" class="basis-catalog-list"></div></section>';
  $("chooseBasisFile").addEventListener("click", () => $("basisInput").click());
  const updateBasisSelection = () => {
    const files = [...($("basisInput").files || [])];
    const category = basisCategoryLabel($("basisCategory")?.value || "policy");
    $("basisFileName").textContent = files.length === 1 ? files[0].name : files.length ? files.length + " 个依据文件已选择" : "尚未选择依据文件";
    $("basisSaveLocation").textContent = files.length === 1
      ? "外部依据库/" + category + "/" + files[0].name
      : files.length ? "外部依据库/" + category + "/（" + files.length + " 个文件，保存后逐项显示）" : "外部依据库/" + category + "/待选择文件";
    $("basisUploadStatus").textContent = files.length ? "已选择，点击“保存到外部依据库”后写入本地" : "";
  };
  $("basisInput").onchange = updateBasisSelection;
  $("basisCategory").addEventListener("change", updateBasisSelection);
  $("basisCategoryFilter").addEventListener("change", renderBasisCatalog);
  $("saveBasis").addEventListener("click", saveBasisFile);
  renderIntakeReports("basisIntakeSummary", state.basisIntakeReports);
  renderBasisCatalog();
}

async function saveBasisFile() {
  const files = [...($("basisInput").files || [])];
  if (!files.length) { $("basisUploadStatus").textContent = "请先选择依据文件"; return; }
  const fields = {
    category: "basisCategory", title: "basisTitle", source_org: "basisSourceOrg", source_url: "basisSourceUrl",
    published_at: "basisPublishedAt", version: "basisVersion", region: "basisRegion", tax_mode: "basisTaxMode",
    pricing_mode: "basisPricingMode", effective_from: "basisEffectiveFrom", effective_to: "basisEffectiveTo",
  };
  const reports = [];
  try {
    for (const [index, file] of files.entries()) {
      setStatus("正在保存第 " + (index + 1) + "/" + files.length + " 个依据文件：" + file.name);
      const form = new FormData();
      form.append("file", file, file.name);
      Object.entries(fields).forEach(([key, id]) => form.append(key, $(id).value));
      try {
        const response = await apiJson("/api/basis/upload", { method: "POST", body: form });
        const basis = response.basis || {};
        state.basisCatalog.items = response.items || state.basisCatalog.items;
        const recognition = recognitionReport(basis);
        reports.push({
          name: file.name,
          status: recognition.status,
          message: recognition.message,
          archive_area: basis.archive_area,
          archive_path: basis.archive_path,
          storage_path: basis.storage_path,
        });
      } catch (error) {
        reports.push({ name: file.name, status: "error", message: error.message || "依据文件保存失败" });
      }
    }
    state.basisIntakeReports = reports;
    renderIntakeReports("basisIntakeSummary", state.basisIntakeReports);
    $("basisUploadStatus").textContent = intakeCompletionMessage(files, reports, "依据资料");
    $("basisInput").value = "";
    $("basisFileName").textContent = "尚未选择依据文件";
    $("basisSaveLocation").textContent = "已保存到外部依据库；具体归档位置见下方";
    renderBasisCatalog();
    setStatus(intakeCompletionMessage(files, reports, "依据资料"));
    if (reports.every((report) => report.status === "error")) setError("所有依据文件保存失败，请查看下方结果");
  } catch (error) {
    $("basisUploadStatus").textContent = "保存失败";
    setError(error.message);
  }
}

function renderBoq() {
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">DOCUMENT INTAKE</span><h3>接入清单资料</h3></div><span class="surface-caption">支持多文件接入；表格进入清单，PDF/Word/图片等进入资料库并自动识别</span></div>
    <div class="intake-banner">
      <div><strong>资料接口</strong><span>可一次选择多个 Excel、CSV、PDF、Word、图片或 CAD 文件；系统会逐一显示识别和转换结果。</span></div>
      <button id="chooseFile" class="button button-primary" type="button">选择资料文件（可多选）</button>
      <span id="fileName" class="file-name">尚未选择文件</span>
    </div>
    <div class="archive-location"><span>本入口归档位置</span><strong>${PROJECT_ARCHIVE_AREAS.boq}</strong></div>
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
  renderIntakeProgress("boqIntakeSummary", files, PROJECT_ARCHIVE_AREAS.boq);
  setStatus(`已选择 ${files.length} 个清单资料，准备保存到 ${PROJECT_ARCHIVE_AREAS.boq}`);
  try {
    const { reports } = await uploadFiles(files, { parseBoq: true, archiveArea: PROJECT_ARCHIVE_AREAS.boq, archiveCategory: "清单与计价资料" });
    $("fileName").textContent = files.length === 1 ? files[0].name : `${files.length} 个文件`;
    renderBoqEditor();
    renderIntakeReports();
    if (state.boqResult) renderBoqOutput(state.boqResult);
    updateContextBar();
    renderAssist();
    setStatus(intakeCompletionMessage(files, reports, "清单资料"));
  } catch (error) {
    setError(error.message);
    setStatus("资料读取失败");
  } finally {
    event.target.value = "";
  }
}

function stageContext(sourceInputId) {
  const context = projectContext();
  const source = $(sourceInputId)?.value.trim() || state.sourceId || "local-source";
  state.sourceId = source;
  return { project_id: context.project_id, source_id: source };
}

function stageSourceField(id = "stageSourceId") {
  return `<label>关联资料编号<input id="${id}" value="${state.sourceId || "local-source"}" /></label>`;
}

function renderRowEditor(containerId, rows, columns, emptyRow) {
  const container = $(containerId);
  if (!container) return;
  if (!rows.length) rows.push(emptyRow());
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column.label;
    headRow.append(cell);
  });
  const actionHead = document.createElement("th");
  actionHead.textContent = "操作";
  headRow.append(actionHead);
  head.append(headRow);
  const body = document.createElement("tbody");
  rows.forEach((row, index) => {
    const tableRow = document.createElement("tr");
    columns.forEach((column) => {
      const cell = document.createElement("td");
      let input;
      if (column.options) {
        input = document.createElement("select");
        column.options.forEach(([value, label]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          input.append(option);
        });
      } else {
        input = document.createElement("input");
        input.type = column.type || "text";
      }
      input.value = row[column.key] ?? "";
      input.placeholder = column.placeholder || "请输入";
      input.addEventListener("input", () => { row[column.key] = input.value; });
      input.addEventListener("change", () => { row[column.key] = input.value; });
      cell.append(input);
      tableRow.append(cell);
    });
    const actionCell = document.createElement("td");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "icon-button";
    remove.textContent = "移除";
    remove.addEventListener("click", () => {
      rows.splice(index, 1);
      renderRowEditor(containerId, rows, columns, emptyRow);
    });
    actionCell.append(remove);
    tableRow.append(actionCell);
    body.append(tableRow);
  });
  table.append(head, body);
  container.replaceChildren(table);
}

function renderCapabilitySummary(targetId, result, metrics) {
  const target = $(targetId);
  if (!target || !result) return;
  target.replaceChildren();
  const row = document.createElement("div");
  row.className = "metric-row capability-metrics";
  metrics.forEach(([label, value]) => {
    const item = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = String(value ?? "—");
    const small = document.createElement("span");
    small.textContent = label;
    item.append(strong, small);
    row.append(item);
  });
  target.append(row);
}

function renderContract() {
  const result = state.contractResult;
  const contract = result?.contract || state.contractDraft;
  const obligations = result?.obligations || state.obligationsDraft;
  const contractCategoryPriority = prioritizedCategoryIds(
    state.sources,
    CONTRACT_ARCHIVE_CLASSES.map(([value]) => value),
    5,
  );
  const contractCategoryOptions = groupedCategoryOptions(CONTRACT_ARCHIVE_CLASSES, contractCategoryPriority, (entry) => entry[0], (entry) => `${entry[0]}：${entry[1]}`);
  state.contractDraft = { ...state.contractDraft, ...contract };
  state.obligationsDraft = obligations.length ? obligations.map((item) => ({ ...item })) : [{ name: "", owner: "", due_date: "", status: "pending", amount: "" }];
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">P01 CONTRACT / PROCUREMENT BASIS</span><h3>合同与招采依据台</h3></div><span class="surface-caption">重点展示影响合同范围、价格、工期、责任和履约的依据</span></div>
    <div class="capability-intro"><strong>合同资料不等同于项目所有文件。</strong><span>招标、投标、定标、合同和执行解释五类资料在本入口重点归档；清单、图纸、变更和结算资料分别进入 P02、P03、P06、P08。</span></div>
    <section class="source-panel contract-source-panel">
      <div class="surface-title"><div><span class="panel-label">CONTRACT FILE INTAKE</span><h3>合同与招采依据录入</h3></div><button id="uploadContractSource" class="button button-quiet" type="button">＋录入合同与招采依据</button></div>
      <p class="business-note">可多选招标、投标、定标、合同和执行解释资料；原件保存在本地资料库并自动识别，合同主数据仍需人工核对后保存。</p>
      <label class="archive-selector">本次资料分类<select id="contractArchiveCategory">${contractCategoryOptions}</select><small class="select-note">优先显示使用量高或近期使用的分类；其他分类仍可在下拉菜单中选择。</small></label>
      <div class="archive-location"><span>本次分类归档位置</span><strong id="contractArchiveLocation">项目资料库/合同与招采依据</strong></div>
      <div id="contractSourceList" class="source-list"></div>
      <div id="contractIntakeSummary" class="intake-report-list"></div>
    </section>
    <div class="field-grid capability-fields">
      <label>合同编号<input id="contractNo" /></label><label>合同名称<input id="contractTitle" /></label>
      <label>建设单位<input id="contractOwner" /></label><label>施工单位<input id="contractor" /></label>
      <label>合同金额<input id="contractAmount" type="number" min="0" step="0.01" /></label><label>计税口径<input id="taxMode" placeholder="含税/不含税" /></label>
      <label>签订日期<input id="signedDate" type="date" /></label><label>开工日期<input id="startDate" type="date" /></label><label>完工日期<input id="endDate" type="date" /></label>
      ${stageSourceField()}
    </div>
    <div class="data-entry-heading"><div><span class="panel-label">OBLIGATIONS</span><h3>合同义务与节点</h3></div><button id="addObligation" class="button button-quiet" type="button">＋新增义务</button></div>
    <div id="obligationEditor" class="editable-table"></div>
    <div class="action-row"><button id="saveContract" class="button button-primary" type="button">保存合同资料</button><span class="request-status">保存后会写入本地工作区并留下审计记录。</span></div>
    <div id="contractOutput" class="inline-output"></div>`;
  const fields = { contractNo: "contract_no", contractTitle: "title", contractOwner: "owner", contractor: "contractor", contractAmount: "contract_amount", taxMode: "tax_mode", signedDate: "signed_date", startDate: "start_date", endDate: "end_date" };
  Object.entries(fields).forEach(([id, key]) => { $(id).value = state.contractDraft[key] ?? ""; });
  renderRowEditor("obligationEditor", state.obligationsDraft, [
    { key: "name", label: "义务/节点" }, { key: "owner", label: "责任方" }, { key: "due_date", label: "截止日期", type: "date" },
    { key: "status", label: "状态", options: [["pending", "待办"], ["active", "进行中"], ["done", "已完成"]] }, { key: "amount", label: "金额", type: "number" },
  ], () => ({ name: "", owner: "", due_date: "", status: "pending", amount: "" }));
  renderSourceList("contractSourceList", { archiveArea: "项目资料库/合同与招采依据" });
  renderIntakeReports("contractIntakeSummary");
  $("uploadContractSource").addEventListener("click", () => $("contractSourceInput").click());
  $("contractSourceInput").onchange = handleContractSourceFiles;
  const updateContractArchiveLocation = () => {
    const category = $("contractArchiveCategory")?.value || "合同阶段";
    $("contractArchiveLocation").textContent = `项目资料库/合同与招采依据/${category}`;
  };
  $("contractArchiveCategory").addEventListener("change", updateContractArchiveLocation);
  updateContractArchiveLocation();
  $("addObligation").addEventListener("click", () => { state.obligationsDraft.push({ name: "", owner: "", due_date: "", status: "pending", amount: "" }); renderContract(); });
  $("saveContract").addEventListener("click", saveContract);
  if (result) {
    renderCapabilitySummary("contractOutput", result, [["合同义务", result.summary?.obligation_count], ["待补字段", result.summary?.missing_field_count], ["资料已整理", result.summary?.interpreted ? "是" : "否"]]);
  }
}

async function saveContract() {
  setError("");
  try {
    const context = stageContext("stageSourceId");
    const contract = { contract_no: $("contractNo").value, title: $("contractTitle").value, owner: $("contractOwner").value, contractor: $("contractor").value, contract_amount: $("contractAmount").value, tax_mode: $("taxMode").value, signed_date: $("signedDate").value, start_date: $("startDate").value, end_date: $("endDate").value };
    const result = await apiJson("/api/contract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, contract, obligations: state.obligationsDraft.filter((item) => item.name?.trim()) }) });
    state.contractResult = result;
    await refreshWorkspace();
    setStatus("合同资料已保存");
    renderContract();
    renderAssist();
  } catch (error) { setError(error.message); }
}

function renderDrawings() {
  const result = state.drawingsResult;
  state.drawingsDraft = result?.drawings?.length ? result.drawings.map((item) => ({ ...item })) : (state.drawingsDraft.length ? state.drawingsDraft : [{ drawing_no: "", name: "", discipline: "general", revision: "A", status: "received", source_id: "", review_note: "" }]);
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">P03 DRAWINGS INTAKE</span><h3>图纸登记台</h3></div><span class="surface-caption">登记图号、专业、版本和审阅状态；原始 CAD/PDF 文件保留在资料库</span></div>
    <div class="capability-intro"><strong>图纸先形成可追踪的登记册。</strong><span>几何算量或外部 CAD 工具通过适配器交换，不改变 Core。</span></div>
    ${stageSourcePanel("drawings", "图纸资料", "可多选施工图、竣工图、设计变更图、CAD、PDF 和图片资料。")}
    <div class="field-grid capability-fields">${stageSourceField()}</div>
    <div class="data-entry-heading"><div><span class="panel-label">DRAWING REGISTER</span><h3>图纸与版本</h3></div><button id="addDrawing" class="button button-quiet" type="button">＋新增图纸</button></div>
    <div id="drawingEditor" class="editable-table"></div>
    <div class="action-row"><button id="saveDrawings" class="button button-primary" type="button">保存图纸登记</button><span class="request-status">状态用于标识待审、已审和需补资料。</span></div>
    <div id="drawingsOutput" class="inline-output"></div>`;
  $("stageSourceId").value = state.sourceId || "local-source";
  renderRowEditor("drawingEditor", state.drawingsDraft, [
    { key: "drawing_no", label: "图号" }, { key: "name", label: "图纸名称" }, { key: "discipline", label: "专业" },
    { key: "revision", label: "版本" }, { key: "status", label: "状态", options: [["received", "待审"], ["reviewed", "已审"], ["approved", "已批准"], ["superseded", "已作废"]] }, { key: "source_id", label: "资料编号" }, { key: "review_note", label: "审阅备注" },
  ], () => ({ drawing_no: "", name: "", discipline: "general", revision: "A", status: "received", source_id: "", review_note: "" }));
  bindStageSourcePanel("drawings", "图纸资料");
  $("addDrawing").addEventListener("click", () => { state.drawingsDraft.push({ drawing_no: "", name: "", discipline: "general", revision: "A", status: "received", source_id: "", review_note: "" }); renderDrawings(); });
  $("saveDrawings").addEventListener("click", saveDrawings);
  if (result) renderCapabilitySummary("drawingsOutput", result, [["图纸数量", result.summary?.drawing_count], ["版本数", result.summary?.revision_count], ["待审图纸", result.summary?.unreviewed_count], ["重复登记", result.summary?.duplicate_count]]);
}

async function saveDrawings() {
  setError("");
  try {
    const context = stageContext("stageSourceId");
    const result = await apiJson("/api/drawings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, drawings: state.drawingsDraft.filter((item) => item.drawing_no?.trim() || item.name?.trim()) }) });
    state.drawingsResult = result;
    await refreshWorkspace();
    setStatus("图纸登记已保存");
    renderDrawings();
    renderAssist();
  } catch (error) { setError(error.message); }
}

function renderBaseline() {
  const result = state.baselineResult;
  state.baselineDraft = result?.entries?.length ? result.entries.map((item) => ({ ...item })) : (state.baselineDraft.length ? state.baselineDraft : [{ code: "", name: "", unit: "", quantity: "", unit_price: "", amount: "", basis: "", source_id: "" }]);
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">P04 BASELINE LEDGER</span><h3>零号台账</h3></div><span class="surface-caption">把项目开局基线单独保存，金额可由工程量×单价自动计算</span></div>
    <div class="capability-intro"><strong>零号台账是后续成本、变更和预警的比较基准。</strong><span>基线金额与 P05 成本计划分开保存，来源可回溯。</span></div>
    ${stageSourcePanel("baseline", "零号台账资料", "可多选开工资料、合同附件、目标成本表、Excel、PDF、Word 和图片资料。")}
    ${basisReferencePanel("P04")}
    <div class="field-grid capability-fields">${stageSourceField()}</div>
    <div class="data-entry-heading"><div><span class="panel-label">BASELINE ENTRIES</span><h3>基线条目</h3></div><button id="addBaseline" class="button button-quiet" type="button">＋新增台账条目</button></div>
    <div id="baselineEditor" class="editable-table"></div>
    <div class="action-row"><button id="saveBaseline" class="button button-primary" type="button">保存零号台账</button><span class="request-status">未填写金额时，系统会尝试按数量和单价计算。</span></div>
    <div id="baselineOutput" class="inline-output"></div>`;
  $("stageSourceId").value = state.sourceId || "local-source";
  renderRowEditor("baselineEditor", state.baselineDraft, [
    { key: "code", label: "编码" }, { key: "name", label: "条目名称" }, { key: "unit", label: "单位" }, { key: "quantity", label: "数量", type: "number" },
    { key: "unit_price", label: "单价", type: "number" }, { key: "amount", label: "金额", type: "number" }, { key: "basis", label: "基准口径" }, { key: "source_id", label: "资料编号" },
  ], () => ({ code: "", name: "", unit: "", quantity: "", unit_price: "", amount: "", basis: "", source_id: "" }));
  bindStageSourcePanel("baseline", "零号台账资料");
  bindBasisReferencePanel("P04");
  $("addBaseline").addEventListener("click", () => { state.baselineDraft.push({ code: "", name: "", unit: "", quantity: "", unit_price: "", amount: "", basis: "", source_id: "" }); renderBaseline(); });
  $("saveBaseline").addEventListener("click", saveBaseline);
  if (result) renderCapabilitySummary("baselineOutput", result, [["台账条目", result.summary?.entry_count], ["基线金额", dashboardMoney(result.summary?.baseline_total)], ["来源数", result.summary?.source_count], ["待定价", result.summary?.unpriced_count]]);
}

async function saveBaseline() {
  setError("");
  try {
    const context = stageContext("stageSourceId");
    const basisLabel = basisDisplayName("P04");
    const entries = state.baselineDraft.filter((item) => item.name?.trim()).map((item) => ({ ...item, basis: item.basis || basisLabel }));
    const result = await apiJson("/api/baseline", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, entries }) });
    state.baselineResult = result;
    await refreshWorkspace();
    setStatus("零号台账已保存");
    renderBaseline();
    renderAssist();
  } catch (error) { setError(error.message); }
}

function eventStatusLabel(status) {
  return EVENT_STATUS_LABELS[status] || status || "未开始";
}

function eventTypeLabel(type) {
  return EVENT_TYPE_LABELS[type] || type || "未分类";
}

function eventRiskClass(severity) {
  return severity === "block" || severity === "CRITICAL" || severity === "HIGH" ? "risk-red" : severity === "warn" || severity === "MEDIUM" ? "risk-yellow" : "risk-blue";
}

function eventSuggestionFields(suggestion) {
  if (!suggestion) return null;
  const identity = suggestion.identity || {};
  const origin = suggestion.origin || {};
  const classification = suggestion.classification || {};
  const location = origin.location || {};
  const dimensions = classification.dimensions || suggestion.dimensions || {};
  return {
    title: identity.title || suggestion.title || "",
    summary: identity.summary || suggestion.summary || "",
    source_type: origin.source_type || suggestion.source_type || "SITE_DISCOVERY",
    event_type: classification.event_type || suggestion.event_type || "SITE_CONDITION",
    severity: classification.severity || suggestion.severity || "MEDIUM",
    discovered_by: origin.discovered_by || "",
    zone: location.zone || "",
    axis: location.axis || "",
    level: location.level || "",
    tags: (classification.tags || suggestion.tags || []).join(", "),
    source_refs: (origin.source_refs || suggestion.source_refs || []).join(", "),
    dimensions,
    baseline: { contract: false, price: false, quantity: false, cost: false },
    technical_needed: false,
    technical_assessment: "",
    technical_feasible: false,
  };
}

function renderEventDistillation() {
  const target = $("eventDistillationOutput");
  if (!target) return;
  const snapshot = state.eventDistillation;
  if (!snapshot) {
    target.className = "event-distillation-output empty-state";
    target.textContent = "先点击“蒸馏本地资料”；有文本时再点击“蒸馏文本并融合”。结果会保留本地事实、文本事实、冲突和来源。";
    return;
  }
  const summary = snapshot.summary || {};
  const fused = snapshot.fused || {};
  target.className = "event-distillation-output";
  target.innerHTML = `
    <div class="event-distill-metrics">
      <div><span>本地事实</span><strong>${escapeHtml(summary.local_fact_count ?? 0)}</strong><small>来自项目资料与 P01–P08 记录</small></div>
      <div><span>文本事实</span><strong>${escapeHtml(summary.text_fact_count ?? 0)}</strong><small>仅从输入文本保守提取</small></div>
      <div><span>融合事实</span><strong>${escapeHtml(summary.fused_fact_count ?? 0)}</strong><small>保留来源与置信度</small></div>
      <div class="${summary.conflict_count ? "has-risk" : ""}"><span>待核对冲突</span><strong>${escapeHtml(summary.conflict_count ?? 0)}</strong><small>${summary.conflict_count ? "本地结构化事实优先，文本不被静默覆盖" : "暂未发现同字段冲突"}</small></div>
    </div>
    <div class="event-distill-trace"><strong>融合原则</strong><span>本地结构化记录优先；文本只补充，不替换；每条事实保留来源引用；没有依据的内容不作为结论。</span></div>
    <div id="eventConflictList" class="event-conflict-list"></div>
    <div id="eventClaimList" class="event-claim-list"></div>`;
  const conflictList = $("eventConflictList");
  const conflicts = fused.conflicts || [];
  if (!conflicts.length) conflictList.textContent = "本轮融合没有发现同字段冲突。";
  else conflictList.replaceChildren(...conflicts.slice(0, 8).map((conflict) => {
    const item = document.createElement("article");
    item.className = "event-conflict risk-yellow";
    item.innerHTML = `<strong>${escapeHtml(conflict.kind || "事实字段")}</strong><span>本地：${escapeHtml(JSON.stringify(conflict.local))}</span><span>文本：${escapeHtml(JSON.stringify(conflict.text))}</span><small>${escapeHtml(conflict.resolution || "保留来源并待核对")}</small>`;
    return item;
  }));
  const claimList = $("eventClaimList");
  const claims = fused.claims || [];
  if (claims.length) claimList.replaceChildren(...claims.slice(0, 8).map((claim) => {
    const item = document.createElement("article");
    item.className = "event-claim";
    item.innerHTML = `<strong>待证实主张</strong><span>${escapeHtml(claim.text || "")}</span><small>来源：${escapeHtml((claim.source_refs || []).join("、") || "文本输入")} · 尚未核验</small>`;
    return item;
  }));
  else claimList.textContent = "文本中未提取到需要证据确认的主张。";
}

function renderEventList() {
  const target = $("eventList");
  if (!target) return;
  if (!state.events.length) {
    target.className = "event-list empty-state";
    target.textContent = "尚未建立工程事件。可以先蒸馏本地资料，再从融合建议建立第一个永久编号事件。";
    return;
  }
  const editable = !isKpiOnly() && Boolean(state.auth.user?.permissions?.includes("edit_business_data"));
  const outcomeEditable = isCostManager();
  target.className = "event-list";
  target.replaceChildren(...state.events.map((event) => {
    const vector = event.state_vector || {};
    const outcome = event.outcome_track || {};
    const outcomeValues = outcome.values || {};
    const item = document.createElement("article");
    item.className = `event-card ${eventRiskClass(event.severity)}`;
    const next = EVENT_NEXT_STATUS[vector.event] || [];
    const transitions = next.length
      ? `<select id="eventTransition-${escapeHtml(event.event_id)}">${next.map((status) => `<option value="${status}">${eventStatusLabel(status)}</option>`).join("")}</select><button class="button button-quiet event-transition" data-event-id="${escapeHtml(event.event_id)}" type="button">推进状态</button>`
      : "";
    item.innerHTML = `
      <div class="event-card-head"><div><span class="panel-label">${escapeHtml(event.event_id || "工程事件")}</span><h4>${escapeHtml(event.title || event.identity?.title || "未命名事件")}</h4><small>${escapeHtml(eventTypeLabel(event.event_type || event.classification?.event_type))} · ${escapeHtml(eventStatusLabel(vector.event))} · ${escapeHtml(event.severity || vector.risk || "MEDIUM")}</small></div><span class="event-status-pill">${escapeHtml(eventStatusLabel(vector.event))}</span></div>
      <p class="event-card-summary">${escapeHtml(event.summary || event.identity?.summary || "未填写事件说明")}</p>
      <div class="event-vector">${[
        ["Event", eventStatusLabel(vector.event)], ["Production", `${vector.production ?? 0}%`], ["Technical", vector.technical], ["Commercial", vector.commercial],
        ["Evidence", `${vector.evidence ?? 0}%`], ["Outcome", outcomeStatusLabel(vector.outcome)], ["Leak", vector.value_leak_count ? `${vector.value_leak_count} 个` : "无"], ["Approval", vector.external_approval], ["Measurement", vector.measurement], ["Audit", `${vector.audit_readiness ?? 0}%`], ["Cash", vector.cash], ["Risk", vector.risk],
      ].map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value || "—")}</strong></div>`).join("")}</div>
      <div class="event-outcome-summary"><span>成果链</span><strong>${escapeHtml((outcome.types || vector.outcome_types || []).map(outcomeTypeLabel).join(" · ") || "待定义")}</strong><small>${escapeHtml(vector.outcome_pending_stage ? `当前卡在：${vector.outcome_pending_stage}` : "实体 → 证据 → 申报 → 确认 → 结算 → 回款")}</small></div>
      <div class="event-card-alerts">${(event.alerts || []).length ? event.alerts.slice(0, 4).map((alert) => `<div class="event-alert ${eventRiskClass(alert.severity)}"><strong>${escapeHtml(alert.title || "自动提醒")}</strong><span>${escapeHtml(alert.message || "")}</span></div>`).join("") : "<span class=\"event-no-alert\">本地规则暂未发现自动预警</span>"}</div>
      ${outcomeEditable ? `<details class="event-outcome-editor"><summary>记录 Outcome 快照（仅造价经理）</summary><div class="event-outcome-fields"><label>成果类型<input id="outcomeTypes-${escapeHtml(event.event_id)}" value="${escapeHtml((outcome.types || []).join(","))}" placeholder="PHYSICAL,COMMERCIAL" /></label><label>实体<input id="outcomePhysical-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.physical ?? ""}" /></label><label>证据完整<input id="outcomeEvidence-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.evidence_ready ?? ""}" /></label><label>已申报<input id="outcomeSubmitted-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.submitted ?? ""}" /></label><label>已确认<input id="outcomeConfirmed-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.confirmed ?? ""}" /></label><label>收入成立<input id="outcomeRevenue-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.revenue ?? ""}" /></label><label>已结算<input id="outcomeSettled-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.settled ?? ""}" /></label><label>已回款<input id="outcomePaid-${escapeHtml(event.event_id)}" type="number" step="0.01" value="${outcomeValues.paid ?? ""}" /></label></div><div class="event-card-actions"><button class="button button-primary event-outcome-save" data-event-id="${escapeHtml(event.event_id)}" type="button">保存成果快照</button>${(OUTCOME_NEXT_STATUS[vector.outcome] || []).length ? `<select id="outcomeTransition-${escapeHtml(event.event_id)}">${OUTCOME_NEXT_STATUS[vector.outcome].map((status) => `<option value="${status}">${outcomeStatusLabel(status)}</option>`).join("")}</select><button class="button button-quiet event-outcome-transition" data-event-id="${escapeHtml(event.event_id)}" type="button">推进成果状态</button>` : ""}</div></details>` : ""}
      <div class="event-card-actions"><button class="button button-quiet event-cross-check" data-event-id="${escapeHtml(event.event_id)}" type="button">三证互证 / 一致性检查</button>${editable ? transitions : ""}</div>
      <div id="eventCrossCheck-${escapeHtml(event.event_id)}" class="event-cross-check-output" hidden></div>`;
    const crossCheck = state.eventCrossChecks[event.event_id];
    if (crossCheck) renderEventCrossCheck(item.querySelector(`#eventCrossCheck-${CSS.escape(event.event_id)}`), crossCheck);
    return item;
  }));
  target.querySelectorAll(".event-transition").forEach((button) => button.addEventListener("click", () => transitionEngineeringEvent(button.dataset.eventId)));
  target.querySelectorAll(".event-outcome-save").forEach((button) => button.addEventListener("click", () => recordEventOutcome(button.dataset.eventId)));
  target.querySelectorAll(".event-outcome-transition").forEach((button) => button.addEventListener("click", () => transitionEventOutcome(button.dataset.eventId)));
  target.querySelectorAll(".event-cross-check").forEach((button) => button.addEventListener("click", () => crossCheckEngineeringEvent(button.dataset.eventId)));
}

function renderEventCrossCheck(target, result) {
  if (!target) return;
  target.hidden = false;
  target.replaceChildren(...(result.checks || []).map((check) => {
    const item = document.createElement("div");
    item.className = `event-check event-check-${String(check.status || "").toLowerCase()}`;
    item.innerHTML = `<strong>${escapeHtml(check.label || check.check_id)}</strong><span>${escapeHtml(check.status || "PENDING")}</span><small>${escapeHtml(check.reason || "")}</small>`;
    return item;
  }));
}

function renderEvents() {
  const editable = !isKpiOnly() && Boolean(state.auth.user?.permissions?.includes("edit_business_data"));
  const sourceTypes = Object.entries(EVENT_SOURCE_LABELS).map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  const eventTypes = Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  const dimensionInputs = [["cost", "成本"], ["revenue", "收入"], ["schedule", "工期"], ["quality", "质量"], ["safety", "安全"]].map(([value, label]) => `<label class="event-check-label"><input type="checkbox" data-event-dimension="${value}" />${label}</label>`).join("");
  const baselineInputs = [["contract", "合同"], ["price", "价格"], ["quantity", "数量"], ["cost", "成本"]].map(([value, label]) => `<label class="event-check-label"><input type="checkbox" data-event-baseline="${value}" />${label}基线</label>`).join("");
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">CORE / ENGINEERING EVENT KERNEL</span><h3>工程事件内核</h3></div><span class="surface-caption">跨 P01–P08 串起事实、基线、方案、证据、结算和兑现</span></div>
    <div class="capability-intro event-kernel-intro"><strong>先蒸馏本地资料，再蒸馏文本，最后融合。</strong><span>本地结构化事实优先；文本只做补充；冲突、不确定性和来源会明确标注。Core 不替人做最终决策。</span></div>
    <section class="event-distill-layout"><div class="event-distill-panel"><div class="data-entry-heading"><div><span class="panel-label">DISTILLATION PIPELINE</span><h3>资料蒸馏与事实融合</h3></div><span class="request-status">默认本地处理 · 不发送外部</span></div><textarea id="eventDistillText" class="event-text-input" placeholder="可粘贴现场记录、会议纪要、设计说明、业主指令或审计意见。系统只提取可回溯事实和待核对主张。" ${editable ? "" : "disabled"}></textarea><div class="action-row"><button id="distillLocal" class="button button-quiet" type="button" ${editable ? "" : "disabled"}>① 蒸馏本地资料</button><button id="distillText" class="button button-primary" type="button" ${editable ? "" : "disabled"}>② 蒸馏文本并融合</button><span id="eventDistillStatus" class="request-status"></span></div></div><aside class="event-pipeline-note"><span class="panel-label">EVIDENCE POLICY</span><h3>认知诚实</h3><p>事实必须有来源；推断必须标注；冲突不静默覆盖；没有足够依据就显示待核对。</p><div class="event-pipeline-step"><b>01</b><span>本地项目资料、P01–P08 记录</span></div><div class="event-pipeline-step"><b>02</b><span>输入文本中的事件、数量、时间、主张</span></div><div class="event-pipeline-step"><b>03</b><span>融合建议只填入草稿，不自动形成结论</span></div></aside></section>
    <section id="eventDistillationOutput" class="event-distillation-output"></section>
    <section class="event-create-panel" ${editable ? "" : "hidden"}><div class="data-entry-heading"><div><span class="panel-label">EVENT INTAKE</span><h3>建立永久编号工程事件</h3></div><span class="surface-caption">事件原始事实和状态历史只追加，不覆盖</span></div><div class="event-create-grid"><label>事件标题<input id="eventTitle" /></label><label>发现人<input id="eventDiscoveredBy" placeholder="姓名/岗位" /></label><label>事件来源<select id="eventSourceType">${sourceTypes}</select></label><label>事件分类<select id="eventType">${eventTypes}</select></label><label>严重程度<select id="eventSeverity"><option value="LOW">低</option><option value="MEDIUM">中</option><option value="HIGH">高</option><option value="CRITICAL">紧急</option></select></label><label>区域/部位<input id="eventZone" placeholder="如：K12+300 右幅" /></label><label>轴线/桩号<input id="eventAxis" /></label><label>楼层/标高<input id="eventLevel" /></label><label class="event-span-2">事件说明<textarea id="eventSummary"></textarea></label><label class="event-span-2">动态标签<input id="eventTags" placeholder="用逗号分隔，如：地下障碍,潜在变更" /></label><label class="event-span-2">来源资料编号<input id="eventSourceRefs" placeholder="用逗号分隔，可从项目资料库复制" /></label></div><div class="event-choice-row"><span>影响基线</span>${baselineInputs}</div><div class="event-choice-row"><span>影响维度</span>${dimensionInputs}</div><div class="event-create-grid"><label class="event-check-wide"><input id="eventTechnicalNeeded" type="checkbox" />需要技术线介入</label><label class="event-span-2">技术必要性判断<textarea id="eventTechnicalAssessment" placeholder="为什么需要技术评估，依据是什么"></textarea></label><label class="event-check-wide"><input id="eventTechnicalFeasible" type="checkbox" />已有可行技术方案（通过安全/质量/合规）</label></div><div class="action-row"><button id="saveEngineeringEvent" class="button button-primary" type="button">保存工程事件</button><button id="applyEventSuggestion" class="button button-quiet" type="button">套用上方融合建议</button><span id="eventCreateStatus" class="request-status"></span></div></section>
    <section class="event-list-panel"><div class="data-entry-heading"><div><span class="panel-label">EVENT STATE VECTOR</span><h3>工程事件状态向量与预警</h3></div><span class="surface-caption">项目经理看重要指标；造价经理看完整链路；造价员负责操作</span></div><div id="eventList" class="event-list"></div></section>`;
  const draft = state.eventDraft;
  if (editable) {
    $("eventDistillText").value = state.eventDistillText || "";
    $("eventTitle").value = draft.title || "";
    $("eventDiscoveredBy").value = draft.discovered_by || "";
    $("eventSourceType").value = draft.source_type || "SITE_DISCOVERY";
    $("eventType").value = draft.event_type || "SITE_CONDITION";
    $("eventSeverity").value = draft.severity || "MEDIUM";
    $("eventZone").value = draft.zone || "";
    $("eventAxis").value = draft.axis || "";
    $("eventLevel").value = draft.level || "";
    $("eventSummary").value = draft.summary || "";
    $("eventTags").value = draft.tags || "";
    $("eventSourceRefs").value = draft.source_refs || "";
    $("eventTechnicalNeeded").checked = Boolean(draft.technical_needed);
    $("eventTechnicalAssessment").value = draft.technical_assessment || "";
    $("eventTechnicalFeasible").checked = Boolean(draft.technical_feasible);
    document.querySelectorAll("[data-event-dimension]").forEach((input) => { input.checked = Boolean(draft.dimensions?.[input.dataset.eventDimension]); });
    document.querySelectorAll("[data-event-baseline]").forEach((input) => { input.checked = Boolean(draft.baseline?.[input.dataset.eventBaseline]); });
    $("eventDistillText").addEventListener("input", (event) => { state.eventDistillText = event.target.value; });
    $("distillLocal").addEventListener("click", () => distillEventKernel(false));
    $("distillText").addEventListener("click", () => distillEventKernel(true));
    $("saveEngineeringEvent").addEventListener("click", saveEngineeringEvent);
    $("applyEventSuggestion").addEventListener("click", applyEventSuggestion);
  }
  renderEventDistillation();
  renderEventList();
}

async function distillEventKernel(withText) {
  setError("");
  const status = $("eventDistillStatus");
  if (status) status.textContent = withText ? "正在蒸馏文本并融合…" : "正在读取本地 P01–P08 资料…";
  try {
    const result = await apiJson("/api/event-kernel/distill", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, phase: withText ? "fuse" : "local", text: withText ? state.eventDistillText : "", text_source_ref: "WebUI 文本输入" }) });
    state.eventDistillation = result.distillation;
    state.events = result.events || state.events;
    if (status) status.textContent = withText ? "文本事实已融合，冲突和来源已保留" : "本地事实蒸馏完成；可继续输入文本融合";
    renderEvents();
    renderAssist();
  } catch (error) { if (status) status.textContent = "蒸馏失败"; setError(error.message); }
}

function applyEventSuggestion() {
  const suggestion = state.eventDistillation?.fused?.suggested_event;
  const fields = eventSuggestionFields(suggestion);
  if (!fields) { setError("请先完成本地资料或文本蒸馏"); return; }
  state.eventDraft = { ...state.eventDraft, ...fields };
  renderEvents();
  setStatus("已将融合建议填入事件草稿，请核对后保存");
}

async function saveEngineeringEvent() {
  setError("");
  try {
    const dimensions = {};
    document.querySelectorAll("[data-event-dimension]").forEach((input) => { dimensions[input.dataset.eventDimension] = input.checked; });
    const baseline = {};
    document.querySelectorAll("[data-event-baseline]").forEach((input) => { baseline[input.dataset.eventBaseline] = input.checked; });
    const payload = {
      project_id: state.projectId,
      title: $("eventTitle").value.trim(), summary: $("eventSummary").value.trim(), discovered_by: $("eventDiscoveredBy").value.trim(),
      source_type: $("eventSourceType").value, event_type: $("eventType").value, severity: $("eventSeverity").value,
      location: { zone: $("eventZone").value.trim(), axis: $("eventAxis").value.trim(), level: $("eventLevel").value.trim() },
      tags: $("eventTags").value.split(",").map((value) => value.trim()).filter(Boolean), source_refs: $("eventSourceRefs").value.split(",").map((value) => value.trim()).filter(Boolean),
      dimensions,
      baseline_impact: { contract: { affected: Boolean(baseline.contract) }, price: { affected: Boolean(baseline.price) }, quantity: { affected: Boolean(baseline.quantity) }, cost: { affected: Boolean(baseline.cost) } },
      technical_track: { needed: $("eventTechnicalNeeded").checked, assessment: $("eventTechnicalAssessment").value.trim(), status: $("eventTechnicalFeasible").checked ? "FEASIBLE" : "NOT_STARTED", options: $("eventTechnicalFeasible").checked ? [{ option_id: "OPT-001", title: "已录入技术方案", feasible: true, safety_pass: true, quality_pass: true, compliance_pass: true }] : [] },
    };
    const result = await apiJson("/api/event-kernel/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.events = [...state.events, result.event];
    state.eventDraft = { ...state.eventDraft, title: "", summary: "", source_refs: "" };
    await refreshWorkspace();
    setStatus(`${result.event.event_id} 已建立，当前状态为已发现`);
    renderEvents();
  } catch (error) { setError(error.message); }
}

async function transitionEngineeringEvent(eventId) {
  const select = $("eventTransition-" + eventId);
  if (!select) return;
  try {
    const result = await apiJson("/api/event-kernel/transition", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, event_id: eventId, target_status: select.value }) });
    state.events = state.events.map((event) => event.event_id === eventId ? result.event : event);
    await refreshDashboard();
    setStatus(`${eventId} 已推进到${eventStatusLabel(select.value)}`);
    renderEvents();
  } catch (error) { setError(error.message); }
}

function outcomeNumber(id) {
  const value = $(id)?.value.trim();
  return value === "" ? null : Number(value);
}

async function recordEventOutcome(eventId) {
  try {
    const types = ($(`outcomeTypes-${eventId}`)?.value || "").split(",").map((value) => value.trim().toUpperCase()).filter(Boolean);
    const values = {
      physical: outcomeNumber(`outcomePhysical-${eventId}`), evidence_ready: outcomeNumber(`outcomeEvidence-${eventId}`),
      submitted: outcomeNumber(`outcomeSubmitted-${eventId}`), confirmed: outcomeNumber(`outcomeConfirmed-${eventId}`),
      revenue: outcomeNumber(`outcomeRevenue-${eventId}`), settled: outcomeNumber(`outcomeSettled-${eventId}`), paid: outcomeNumber(`outcomePaid-${eventId}`),
    };
    const result = await apiJson("/api/event-kernel/outcome", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, event_id: eventId, operation: "snapshot", changes: { types, values }, reason: "WebUI 成果快照" }) });
    state.events = state.events.map((event) => event.event_id === eventId ? result.event : event);
    await refreshDashboard();
    setStatus(`${eventId} 的 Outcome 快照已追加，历史版本未覆盖`);
    renderEvents();
  } catch (error) { setError(error.message); }
}

async function transitionEventOutcome(eventId) {
  const select = $(`outcomeTransition-${eventId}`);
  if (!select) return;
  const target = select.value;
  const reason = ["REJECTED", "ABANDONED"].includes(target) ? (window.prompt("请记录拒绝/放弃原因") || "") : "";
  if (["REJECTED", "ABANDONED"].includes(target) && !reason.trim()) return;
  try {
    const result = await apiJson("/api/event-kernel/outcome", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, event_id: eventId, operation: "transition", target_status: target, reason }) });
    state.events = state.events.map((event) => event.event_id === eventId ? result.event : event);
    await refreshDashboard();
    setStatus(`${eventId} 的成果状态已推进到${outcomeStatusLabel(target)}`);
    renderEvents();
  } catch (error) { setError(error.message); }
}

async function crossCheckEngineeringEvent(eventId) {
  try {
    const result = await apiJson("/api/event-kernel/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: state.projectId, event_id: eventId }) });
    state.eventCrossChecks[eventId] = result.cross_check;
    renderEventList();
    setStatus(`${eventId} 一致性检查：${result.cross_check.status === "PASS" ? "通过" : "需要核对"}`);
  } catch (error) { setError(error.message); }
}

function renderChanges() {
  const result = state.changesResult;
  state.changesDraft = result?.changes?.length ? result.changes.map((item) => ({ ...item })) : (state.changesDraft.length ? state.changesDraft : [{ change_id: "", title: "", reason: "", amount: "", status: "pending", impact_date: "", owner: "", source_id: "", risk_note: "" }]);
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">P06 CHANGE MANAGEMENT</span><h3>变更工作台</h3></div><span class="surface-caption">登记变更原因、金额影响、责任人和审批状态，形成可追踪决策队列</span></div>
    <div class="capability-intro"><strong>变更先登记、再判断、后执行。</strong><span>待审批变更会进入经营看板提醒，不会静默改变成本基线。</span></div>
    ${stageSourcePanel("changes", "变更资料", "可多选变更联系单、洽商记录、签证、现场照片、图纸和审批文件。")}
    <div class="field-grid capability-fields">${stageSourceField()}</div>
    <div class="data-entry-heading"><div><span class="panel-label">CHANGE REGISTER</span><h3>变更清单</h3></div><button id="addChange" class="button button-quiet" type="button">＋新增变更</button></div>
    <div id="changeEditor" class="editable-table"></div>
    <div class="action-row"><button id="saveChanges" class="button button-primary" type="button">保存变更清单</button><span class="request-status">批准或实施前，造价经理可在项目控制台复核。</span></div>
    <div id="changesOutput" class="inline-output"></div>`;
  $("stageSourceId").value = state.sourceId || "local-source";
  renderRowEditor("changeEditor", state.changesDraft, [
    { key: "change_id", label: "变更编号" }, { key: "title", label: "变更事项" }, { key: "reason", label: "原因" }, { key: "amount", label: "金额影响", type: "number" },
    { key: "status", label: "状态", options: [["pending", "待审批"], ["approved", "已批准"], ["implemented", "已实施"], ["rejected", "已拒绝"]] }, { key: "impact_date", label: "影响日期", type: "date" }, { key: "owner", label: "责任人" }, { key: "source_id", label: "资料编号" }, { key: "risk_note", label: "风险备注" },
  ], () => ({ change_id: "", title: "", reason: "", amount: "", status: "pending", impact_date: "", owner: "", source_id: "", risk_note: "" }));
  bindStageSourcePanel("changes", "变更资料");
  $("addChange").addEventListener("click", () => { state.changesDraft.push({ change_id: "", title: "", reason: "", amount: "", status: "pending", impact_date: "", owner: "", source_id: "", risk_note: "" }); renderChanges(); });
  $("saveChanges").addEventListener("click", saveChanges);
  if (result) renderCapabilitySummary("changesOutput", result, [["变更数量", result.summary?.change_count], ["待审批", result.summary?.pending_count], ["已批准", result.summary?.approved_count], ["净影响", dashboardMoney(result.summary?.net_amount)]]);
}

async function saveChanges() {
  setError("");
  try {
    const context = stageContext("stageSourceId");
    const result = await apiJson("/api/changes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, changes: state.changesDraft.filter((item) => item.title?.trim()) }) });
    state.changesResult = result;
    await refreshWorkspace();
    setStatus("变更清单已保存");
    renderChanges();
    renderAssist();
  } catch (error) { setError(error.message); }
}

function renderEvidence() {
  const result = state.evidenceResult;
  state.evidenceDraft = result?.links?.length ? result.links.map((item) => ({ ...item })) : (state.evidenceDraft.length ? state.evidenceDraft : [{ link_id: "", source_id: "", target_type: "", target_id: "", relation: "supports", note: "", verified: "false" }]);
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">P07 EVIDENCE LINKAGE</span><h3>证据关联台</h3></div><span class="surface-caption">把合同、图纸、清单、台账、变更和初审事项串成可回溯证据链</span></div>
    <div class="capability-intro"><strong>每个业务判断都可以回到来源。</strong><span>系统保存来源编号和关联关系，不把外部文件复制进 Core。</span></div>
    ${stageSourcePanel("evidence", "证据资料", "可多选合同、图纸、清单、台账、变更、收方单和照片等证明资料。")}
    <div class="field-grid capability-fields">${stageSourceField()}</div>
    <div class="data-entry-heading"><div><span class="panel-label">EVIDENCE LINKS</span><h3>证据链条目</h3></div><button id="addEvidence" class="button button-quiet" type="button">＋新增关联</button></div>
    <div id="evidenceEditor" class="editable-table"></div>
    <div class="action-row"><button id="saveEvidence" class="button button-primary" type="button">保存证据关联</button><span class="request-status">关联只记录来源和目标编号，原文件仍由资料库保存。</span></div>
    <div id="evidenceOutput" class="inline-output"></div>`;
  $("stageSourceId").value = state.sourceId || "local-source";
  renderRowEditor("evidenceEditor", state.evidenceDraft, [
    { key: "link_id", label: "关联编号" }, { key: "source_id", label: "来源编号" }, { key: "target_type", label: "目标类型" }, { key: "target_id", label: "目标编号" },
    { key: "relation", label: "关系" }, { key: "note", label: "说明" }, { key: "verified", label: "已核验", options: [["false", "待核验"], ["true", "已核验"]] },
  ], () => ({ link_id: "", source_id: "", target_type: "", target_id: "", relation: "supports", note: "", verified: "false" }));
  bindStageSourcePanel("evidence", "证据资料");
  $("addEvidence").addEventListener("click", () => { state.evidenceDraft.push({ link_id: "", source_id: "", target_type: "", target_id: "", relation: "supports", note: "", verified: "false" }); renderEvidence(); });
  $("saveEvidence").addEventListener("click", saveEvidence);
  if (result) renderCapabilitySummary("evidenceOutput", result, [["关联数量", result.summary?.link_count], ["已核验", result.summary?.verified_count], ["待核验", result.summary?.unverified_count], ["目标类型", (result.summary?.target_types || []).join("、") || "—"]]);
}

async function saveEvidence() {
  setError("");
  try {
    const context = stageContext("stageSourceId");
    const links = state.evidenceDraft.filter((item) => item.target_type?.trim() && item.target_id?.trim()).map((item) => ({ ...item, verified: item.verified === true || item.verified === "true" }));
    const result = await apiJson("/api/evidence", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, links }) });
    state.evidenceResult = result;
    await refreshWorkspace();
    setStatus("证据关联已保存");
    renderEvidence();
    renderAssist();
  } catch (error) { setError(error.message); }
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
  const planNote = canViewCostDetail() ? "计划金额、组价状态和成本控制结果可查看。" : "可录入价格口径；保存后价格与成本金额不回显，由造价经理负责复核。";
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">COST PLANNING</span><h3>编制成本计划</h3></div><span class="surface-caption">合同单价进入计划；市场单价仅用于内部成本参考</span></div>
    <div class="notice-line"><strong>当前资料：${state.fileName || state.sourceName}</strong><span>${state.boqResult.item_count} 项清单已带入。</span></div>
    ${stageSourcePanel("plan", "成本计划资料", "可多选组价依据、市场询价、目标成本表、合同附件和计算说明。")}
    ${basisReferencePanel("P05")}
    <div class="data-entry-heading"><div><span class="panel-label">PRICE BOOK</span><h3>补充单价</h3></div><span class="input-note">没有合同单价的项目会保留为待组价。</span></div>
    <div id="planEditor" class="editable-table"></div>
    <div class="action-row"><button id="runPlan" class="button button-primary" type="button">生成成本计划</button><span class="request-status">${planNote}</span></div>
    <div id="planOutput" class="inline-output"></div>`;
  bindStageSourcePanel("plan", "成本计划资料");
  bindBasisReferencePanel("P05");
  renderPlanEditor();
  $("runPlan").addEventListener("click", runCostPlan);
  if (state.planResult) renderPlanOutput(state.planResult);
}

function renderPlanEditor() {
  const wrap = $("planEditor");
  const table = document.createElement("table");
  const contractPriceLabel = canViewCostDetail() ? "合同单价" : "合同单价（录入后隐藏）";
  const marketPriceLabel = canViewCostDetail() ? "市场参考价" : "市场参考价（录入后隐藏）";
  table.innerHTML = `<thead><tr><th>项目</th><th>单位</th><th>工程量</th><th>${contractPriceLabel}</th><th>${marketPriceLabel}</th></tr></thead>`;
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
      input.value = canViewCostDetail() ? (state.planDraft[index][key] ?? "") : "";
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
    const basis = stageBasisContexts("P05");
    const result = await apiJson("/api/cost-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: context.project_id,
        source_id: context.source_id,
        items: state.boqResult.items,
        contract_prices: priceBook("contractPrice"),
        market_prices: priceBook("marketPrice"),
        contract_basis: basis.contract_basis,
        market_basis: basis.market_basis,
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
  const protectedMoney = canViewCostDetail() ? (summary.contract_subtotal ?? "—") : "受权限保护";
  const reviewEntry = canViewCostDetail()
    ? '<button id="toReview" class="button button-quiet" type="button">进入结算初审 →</button>'
    : '<span class="request-status">结算初审由造价经理查看和执行</span>';
  output.innerHTML = `
    <div class="metric-row"><div><strong>${protectedMoney}</strong><span>合同计划小计</span></div><div><strong>${summary.contract_item_count}</strong><span>已定价项目</span></div><div><strong>${summary.pending_item_count}</strong><span>待组价项目</span></div></div>
    <div class="result-strip ${summary.pending_item_count ? "result-warn" : "result-ok"}"><strong>${summary.pending_item_count ? `有 ${summary.pending_item_count} 项需要补充合同单价` : "成本计划已完整生成"}</strong><span>${result.cost_control ? "市场参考价已单独保留为内部成本控制信息。" : "未提供市场参考价。"}</span>${reviewEntry}</div>`;
  if ($("toReview")) $("toReview").addEventListener("click", () => setView("review"));
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
  if (!canViewCostDetail()) {
    $("workspaceContent").innerHTML = '<div class="blocked-step"><span class="panel-label">ROLE CONTROL</span><h3>结算初审</h3><p>结算初审包含单价、金额和成本判断，仅造价经理可以查看和执行。</p><button class="button button-primary" type="button" data-view="dashboard">返回操作看板</button></div>';
    bindViewButtons();
    return;
  }
  if (!state.planResult) {
    renderBlockedStep("结算初审", "请先生成成本计划。", "去做成本计划", "plan");
    return;
  }
  const rows = reviewRows();
  $("workspaceContent").innerHTML = `
    <div class="surface-title"><div><span class="panel-label">SETTLEMENT REVIEW</span><h3>结算初审</h3></div><span class="surface-caption">检查数量、金额、单位和价格口径，形成处理建议</span></div>
    <div class="notice-line"><strong>待审资料：${state.fileName || state.sourceName}</strong><span>以下数据来自已生成的成本计划。</span></div>
    ${stageSourcePanel("review", "结算资料", "可多选结算书、收方单、签证、竣工资料、对账单和其他审查依据。")}
    ${basisReferencePanel("P08")}
    <div id="reviewTable" class="editable-table readonly-table"></div>
    <div class="action-row"><button id="runReview" class="button button-primary" type="button">运行结算初审</button><span class="request-status">系统会显示可发布、阻断和需要核对的事项。</span></div>
    <div id="reviewOutput" class="inline-output"></div>`;
  bindStageSourcePanel("review", "结算资料");
  bindBasisReferencePanel("P08");
  renderTable($("reviewTable"), [["name", "项目"], ["unit", "单位"], ["quantity", "工程量"], ["unit_price", "单价"], ["amount", "金额"], ["display_status", "状态"]], (state.planResult.items || []).map((item) => ({ ...item, display_status: displayPlanStatus(item.status) })));
  $("runReview").addEventListener("click", runReview);
  if (state.reviewResult) renderReviewOutput(state.reviewResult);
}

async function runReview() {
  setError("");
  try {
    const context = await ensureProject();
    const basis = stageBasisContexts("P08");
    const result = await apiJson("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: context.project_id,
        source_id: context.source_id,
        rows: reviewRows(),
        reference_units: state.sample?.reference_units || {},
        reference_prices: state.sample?.reference_prices || {},
        subject_basis: basis.subject_basis,
        reference_basis: basis.reference_basis,
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
  if (!canAccessView(view)) {
    view = canAccessView("overview") ? "overview" : [...visibleViewsForUser()][0] || "overview";
  }
  state.view = view;
  document.querySelectorAll(".workspace-tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.view === view));
  if (view === "overview") renderOverview();
  if (view === "search") renderSearch();
  if (view === "contract") renderContract();
  if (view === "boq") renderBoq();
  if (view === "drawings") renderDrawings();
  if (view === "baseline") renderBaseline();
  if (view === "plan") renderPlan();
  if (view === "changes") renderChanges();
  if (view === "events") renderEvents();
  if (view === "evidence") renderEvidence();
  if (view === "review") renderReview();
  if (view === "export") renderExportWorkspace();
  if (view === "basis") renderBasis();
  if (view === "dashboard") renderDashboard();
  if (view === "p09") {
    renderP09();
  }
  if (view === "coordination") renderCoordination();
  if (view === "personnel") renderPersonnel();
  if (view === "control") renderControl();
  renderAssist();
  updateContextBar();
}

async function loadHealth() {
  try {
    const health = await apiJson("/api/health");
    state.deployment = health.deployment || null;
    $("runtimeVersion").textContent = `v${health.runtime.version}`;
    $("releaseHighlights").textContent = `${health.runtime.version}：${health.release_highlights || "本次迭代已完成"}`;
    $("health").className = "health health-ok";
    $("health").textContent = "资料服务就绪";
    const deployment = $("deploymentStatus");
    if (deployment && state.deployment) {
      const mode = state.deployment.mode === "central" ? "中央数据节点" : state.deployment.mode === "edge" ? "边缘节点" : "本机数据节点";
      deployment.hidden = false;
      deployment.className = `deployment-status ${state.deployment.mode}`;
      deployment.textContent = `${mode} · ${state.deployment.node_id || "local-node"}`;
    }
  } catch (error) {
    $("health").className = "health health-error";
    $("health").textContent = "资料服务不可用";
    setError(error.message);
  }
}

function submitGlobalSearch(event) {
  event.preventDefault();
  if (!canAccessView("search")) return;
  const input = $("globalSearchInput");
  const query = input?.value.trim() || "";
  if (!query) {
    setView("search");
    $("searchQuery")?.focus();
    return;
  }
  state.search.query = query;
  state.search.response = null;
  setView("search");
  performSearch();
}

async function loadDemo() {
  state.sample = await apiJson("/api/sample");
  await loadConnectors();
  await loadBasisCatalog();
  state.projectId = state.sample.project_id;
  state.sourceId = state.sample.source_id;
  state.projectName = state.sample.project_name || "演示道路项目";
  state.sourceName = state.sample.source_name || "示例清单资料";
  state.boqRows = draftFromSample(state.sample.boq_rows);
  await loadWorkspace();
  await refreshPersonnel();
  setView(isKpiOnly() ? "dashboard" : "overview");
  setStatus(restoredStatus());
}

$("workspaceTabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-view]");
  if (tab) setView(tab.dataset.view);
});

$("assistList").addEventListener("click", (event) => {
  const item = event.target.closest("[data-view]");
  if (item) setView(item.dataset.view);
});

$("loginForm").addEventListener("submit", submitLogin);
$("registerForm").addEventListener("submit", submitRegister);
$("logoutButton").addEventListener("click", logout);
$("globalSearchForm").addEventListener("submit", submitGlobalSearch);

async function boot() {
  await loadHealth();
  if (!(await restoreSession())) showAuth();
}

boot().catch((error) => setAuthMessage(error.message));
