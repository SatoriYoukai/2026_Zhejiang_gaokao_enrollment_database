const DATA = window.VOLUNTEER_DATA;
const ROWS = DATA.rows || [];

const state = {
  page: 1,
  pageSize: 100,
  filtered: ROWS,
  keywordError: "",
  keywordExpression: "",
  filterTimer: null,
};

const $ = (id) => document.getElementById(id);

const controls = {
  keyword: $("keywordInput"),
  college: $("collegeInput"),
  major: $("majorInput"),
  province: $("provinceSelect"),
  city: $("citySelect"),
  degree: $("degreeSelect"),
  subject: $("subjectSelect"),
  historyYears: $("historyYearsSelect"),
  rank2025Min: $("rank2025Min"),
  rank2025Max: $("rank2025Max"),
  latestRankMin: $("latestRankMin"),
  latestRankMax: $("latestRankMax"),
  latestScoreMin: $("latestScoreMin"),
  latestScoreMax: $("latestScoreMax"),
  planMin: $("planMin"),
  planMax: $("planMax"),
  sort: $("sortSelect"),
  pageSize: $("pageSizeSelect"),
};

function fmt(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return value.toLocaleString("zh-CN");
  return String(value);
}

function fmtTuition(value) {
  const n = asNumber(value);
  if (n === null) return "-";
  return `${n.toLocaleString("zh-CN")} 元/年`;
}

function norm(value) {
  return String(value || "").trim().toLowerCase();
}

function asNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function optionList(select, values, label = "全部") {
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "";
  all.textContent = label;
  select.appendChild(all);
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
}

function uniqueSorted(field, rows = ROWS) {
  return [...new Set(rows.map((row) => row[field]).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b), "zh-CN"),
  );
}

function initControls() {
  optionList(controls.province, DATA.facets.province || uniqueSorted("province"));
  optionList(controls.city, DATA.facets.city || uniqueSorted("city"));
  optionList(controls.degree, DATA.facets.degree_level || uniqueSorted("degree_level"));
  optionList(controls.subject, DATA.facets.subject_key || uniqueSorted("subject_key"));
  optionList(
    controls.historyYears,
    (DATA.facets.history_years_matched || [0, 1, 2, 3]).map(String),
    "全部",
  );
  controls.degree.value = "本科";
  controls.subject.value = "物理&化学";
  $("dataMeta").textContent = `2026 计划 ${fmt(DATA.row_count)} 条，历史数据 2023-2025，离线版`;
}

function rangePass(value, minInput, maxInput) {
  const n = asNumber(value);
  const min = asNumber(minInput.value);
  const max = asNumber(maxInput.value);
  if (min === null && max === null) return true;
  if (n === null) return false;
  if (min !== null && n < min) return false;
  if (max !== null && n > max) return false;
  return true;
}

function textHaystack(row) {
  return [
    row.volunteer_id,
    row.college_code,
    row.college_name,
    row.college_key,
    row.major_code,
    row.major_name,
    row.major_base_key,
    row.province,
    row.city,
    row.subject_key,
    row.remark,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function getActiveFilterLabels() {
  const labels = [];
  const pairs = [
    ["关键词", controls.keyword.value],
    ["院校", controls.college.value],
    ["专业", controls.major.value],
    ["省份", controls.province.value],
    ["城市", controls.city.value],
    ["学历", controls.degree.value],
    ["选科", controls.subject.value],
    ["匹配年数", controls.historyYears.value],
  ];
  for (const [name, value] of pairs) {
    if (value) labels.push(`${name}: ${value}`);
  }
  const ranges = [
    ["2025位次", controls.rank2025Min.value, controls.rank2025Max.value],
    ["最新位次", controls.latestRankMin.value, controls.latestRankMax.value],
    ["最新分数", controls.latestScoreMin.value, controls.latestScoreMax.value],
    ["计划数", controls.planMin.value, controls.planMax.value],
  ];
  for (const [name, min, max] of ranges) {
    if (min || max) labels.push(`${name}: ${min || "-"}-${max || "-"}`);
  }
  return labels;
}

function compileKeywordFilter() {
  const keyword = controls.keyword.value.trim();
  state.keywordError = "";
  state.keywordExpression = "";
  if (!keyword) return () => true;
  try {
    const compiled = window.VolunteerQuery.compile(keyword);
    state.keywordExpression = compiled.expression;
    return (row) => compiled.matchText(textHaystack(row));
  } catch (error) {
    state.keywordError = error.message || String(error);
    return null;
  }
}

function applyFilters() {
  const keywordMatcher = compileKeywordFilter();
  const college = norm(controls.college.value);
  const major = norm(controls.major.value);
  const province = controls.province.value;
  const city = controls.city.value;
  const degree = controls.degree.value;
  const subject = controls.subject.value;
  const historyYears = controls.historyYears.value;

  let rows = keywordMatcher
    ? ROWS.filter((row) => {
    if (!keywordMatcher(row)) return false;
    if (college && !norm(row.college_name).includes(college) && !norm(row.college_key).includes(college)) {
      return false;
    }
    if (major && !norm(row.major_name).includes(major) && !norm(row.major_base_key).includes(major)) {
      return false;
    }
    if (province && row.province !== province) return false;
    if (city && row.city !== city) return false;
    if (degree && row.degree_level !== degree) return false;
    if (subject && row.subject_key !== subject) return false;
    if (historyYears && String(row.history_years_matched ?? "") !== historyYears) return false;
    if (!rangePass(row["2025_history_lowest_rank"], controls.rank2025Min, controls.rank2025Max)) return false;
    if (!rangePass(row.history_latest_rank, controls.latestRankMin, controls.latestRankMax)) return false;
    if (!rangePass(row.history_latest_score, controls.latestScoreMin, controls.latestScoreMax)) return false;
    if (!rangePass(row.plan_count, controls.planMin, controls.planMax)) return false;
    return true;
  })
    : [];

  rows = sortRows(rows);
  state.filtered = rows;
  state.page = 1;
  render();
}

function sortRows(rows) {
  const sort = controls.sort.value;
  const copy = [...rows];
  const rankAsc = (field) => (a, b) => {
    const av = asNumber(a[field]);
    const bv = asNumber(b[field]);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return av - bv;
  };
  if (sort === "latestRankAsc") return copy.sort(rankAsc("history_latest_rank"));
  if (sort === "latestRankDesc") return copy.sort((a, b) => -rankAsc("history_latest_rank")(a, b));
  if (sort === "scoreDesc") {
    return copy.sort((a, b) => (asNumber(b.history_latest_score) ?? -1) - (asNumber(a.history_latest_score) ?? -1));
  }
  if (sort === "planDesc") {
    return copy.sort((a, b) => (asNumber(b.plan_count) ?? -1) - (asNumber(a.plan_count) ?? -1));
  }
  return copy.sort((a, b) =>
    `${a.college_key || ""}${a.major_name || ""}`.localeCompare(
      `${b.college_key || ""}${b.major_name || ""}`,
      "zh-CN",
    ),
  );
}

function renderSummary() {
  const rows = state.filtered;
  renderKeywordRuleStatus();
  $("shownCount").textContent = fmt(rows.length);
  $("undergradCount").textContent = fmt(rows.filter((r) => r.degree_level === "本科").length);
  $("matchedCount").textContent = fmt(rows.filter((r) => asNumber(r.history_latest_rank) !== null).length);
  const ranks = rows
    .map((r) => asNumber(r.history_latest_rank))
    .filter((v) => v !== null)
    .sort((a, b) => a - b);
  const mid = ranks.length ? ranks[Math.floor(ranks.length / 2)] : null;
  $("medianRank").textContent = fmt(mid);

  const active = getActiveFilterLabels();
  $("activeFilters").innerHTML = active.length
    ? active.map((label) => `<span class="filter-chip">${escapeHtml(label)}</span>`).join("")
    : '<span class="muted">无额外筛选</span>';
}

function renderKeywordRuleStatus() {
  const status = $("keywordRuleStatus");
  if (!status) return;
  if (state.keywordError) {
    status.className = "field-hint rule-error";
    status.textContent = `表达式错误：${state.keywordError}`;
    return;
  }
  if (state.keywordExpression) {
    status.className = "field-hint rule-ok";
    status.textContent = `当前逻辑：${state.keywordExpression}`;
    return;
  }
  status.className = "field-hint";
  status.textContent = "词本身表示包含；支持 AND / OR / NOT、括号、引号短语，空格等价 AND。";
}

function rankTag(row) {
  const latest = asNumber(row.history_latest_rank);
  if (latest === null) return '<span class="tag bad">无历史</span>';
  const years = asNumber(row.history_years_matched) || 0;
  if (years >= 3) return '<span class="tag good">3年</span>';
  if (years === 2) return '<span class="tag">2年</span>';
  return '<span class="tag warn">1年</span>';
}

function renderTable() {
  const start = (state.page - 1) * state.pageSize;
  const rows = state.filtered.slice(start, start + state.pageSize);
  $("resultBody").innerHTML = rows
    .map(
      (row, i) => `
        <tr>
          <td><button class="row-action" type="button" data-index="${start + i}">${escapeHtml(row.volunteer_id)}</button></td>
          <td class="college-cell">${escapeHtml(row.college_name || "")}<div class="muted">${escapeHtml(row.college_code || "")}</div></td>
          <td class="major-cell">${escapeHtml(row.major_name || "")}<div class="muted">${escapeHtml(row.remark || "")}</div></td>
          <td>${escapeHtml([row.province, row.city].filter(Boolean).join("·"))}</td>
          <td><span class="tag">${escapeHtml(row.subject_key || "-")}</span></td>
          <td class="num">${fmt(row.plan_count)}</td>
          <td class="num tuition-cell">${escapeHtml(fmtTuition(row.tuition))}</td>
          <td class="num">${fmt(row["2023_history_lowest_rank"])}</td>
          <td class="num">${fmt(row["2024_history_lowest_rank"])}</td>
          <td class="num">${fmt(row["2025_history_lowest_rank"])}</td>
          <td class="num">${fmt(row.history_latest_rank)}<div class="muted">${fmt(row.history_latest_score)} 分</div></td>
          <td>${rankTag(row)}</td>
        </tr>
      `,
    )
    .join("");

  document.querySelectorAll(".row-action").forEach((button) => {
    button.addEventListener("click", () => showDetail(state.filtered[Number(button.dataset.index)]));
  });
}

function renderPagination() {
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  if (state.page > pages) state.page = pages;
  $("pageInfo").textContent = `第 ${state.page} / ${pages} 页`;
  $("prevPageBtn").disabled = state.page <= 1;
  $("nextPageBtn").disabled = state.page >= pages;
}

function render() {
  renderSummary();
  renderPagination();
  renderTable();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showDetail(row) {
  $("detailTitle").textContent = `${row.college_key || row.college_name} - ${row.major_name}`;
  const fields = [
    ["志愿代码", row.volunteer_id],
    ["院校", row.college_name],
    ["专业", row.major_name],
    ["省市", [row.province, row.city].filter(Boolean).join("·")],
    ["学历/学制", `${fmt(row.degree_level)} / ${fmt(row.duration)} 年`],
    ["2026 计划数", row.plan_count],
    ["选科要求", row.subject_requirement],
    ["2026 学费", fmtTuition(row.tuition)],
    ["备注", row.remark],
    ["历史匹配年数", row.history_years_matched],
    ["历史位次串", row.history_ranks],
    ["2023", historyLine(row, "2023")],
    ["2024", historyLine(row, "2024")],
    ["2025", historyLine(row, "2025")],
  ];
  $("detailContent").innerHTML = `<dl class="detail-grid">${fields
    .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(fmt(v))}</dd>`)
    .join("")}</dl>`;
  $("detailDialog").showModal();
}

function historyLine(row, year) {
  const rank = row[`${year}_history_lowest_rank`];
  if (rank === null || rank === undefined || rank === "") return "无高置信匹配";
  const major = row[`${year}_history_major_name`] || row.major_name;
  const subject = row[`${year}_history_subject`] || "";
  const score = row[`${year}_history_lowest_score`];
  const avg = row[`${year}_history_avg_score`];
  const count = row[`${year}_history_admitted_count`];
  const level = row[`${year}_match_level`] || "";
  const page = row[`${year}_history_source_page`] || "";
  return `${major} | ${subject} | 最低 ${fmt(score)} / 位次 ${fmt(rank)} | 均分 ${fmt(avg)} | 录取 ${fmt(
    count,
  )} | ${level} | PDF p.${fmt(page)}`;
}

function resetFilters() {
  for (const input of [
    controls.keyword,
    controls.college,
    controls.major,
    controls.rank2025Min,
    controls.rank2025Max,
    controls.latestRankMin,
    controls.latestRankMax,
    controls.latestScoreMin,
    controls.latestScoreMax,
    controls.planMin,
    controls.planMax,
  ]) {
    input.value = "";
  }
  controls.province.value = "";
  controls.city.value = "";
  controls.degree.value = "本科";
  controls.subject.value = "物理&化学";
  controls.historyYears.value = "";
  controls.sort.value = "latestRankAsc";
  applyFilters();
}

function exportCsv() {
  const columns = [
    "volunteer_id",
    "college_name",
    "major_name",
    "province",
    "city",
    "degree_level",
    "subject_key",
    "plan_count",
    "tuition",
    "2023_history_lowest_score",
    "2023_history_lowest_rank",
    "2024_history_lowest_score",
    "2024_history_lowest_rank",
    "2025_history_lowest_score",
    "2025_history_lowest_rank",
    "history_latest_score",
    "history_latest_rank",
    "history_years_matched",
    "remark",
  ];
  const csv = [
    columns.join(","),
    ...state.filtered.map((row) =>
      columns
        .map((col) => {
          const value = row[col] ?? "";
          const text = String(value).replaceAll('"', '""');
          return /[",\n]/.test(text) ? `"${text}"` : text;
        })
        .join(","),
    ),
  ].join("\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "zhejiang_2026_filtered_volunteers.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function scheduleApplyFilters() {
  window.clearTimeout(state.filterTimer);
  state.filterTimer = window.setTimeout(applyFilters, 80);
}

function bindEvents() {
  Object.values(controls).forEach((control) => {
    control.addEventListener("input", scheduleApplyFilters);
    control.addEventListener("change", scheduleApplyFilters);
  });
  controls.pageSize.addEventListener("change", () => {
    state.pageSize = Number(controls.pageSize.value);
    state.page = 1;
    render();
  });
  $("prevPageBtn").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    render();
  });
  $("nextPageBtn").addEventListener("click", () => {
    const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
    state.page = Math.min(pages, state.page + 1);
    render();
  });
  $("resetBtn").addEventListener("click", resetFilters);
  $("exportBtn").addEventListener("click", exportCsv);
  $("closeDialogBtn").addEventListener("click", () => $("detailDialog").close());
}

initControls();
bindEvents();
applyFilters();
