const DATA = window.AI_PATH_DATA;
const ROWS = DATA.rows || [];

const PREF_WEIGHTS = {
  favorite: 1000,
  like: 18,
  dislike: -25,
  ban: -10000,
};

const state = {
  profileId: "math_first_default",
  config: null,
  filtered: [],
  preferences: {},
  customTags: {},
  customTagCatalog: [],
};

const $ = (id) => document.getElementById(id);

const controls = {
  profile: $("profileSelect"),
  search: $("searchInput"),
  group: $("groupSelect"),
  confidence: $("confidenceSelect"),
  includeTag: $("includeTagSelect"),
  excludeTag: $("excludeTagSelect"),
  sort: $("sortSelect"),
  hideBan: $("hideBanToggle"),
  manualOnly: $("manualOnlyToggle"),
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function norm(value) {
  return String(value || "").trim().toLowerCase();
}

function asNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return value.toLocaleString("zh-CN");
  return String(value);
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function download(name, text, type = "application/json") {
  const blob = new Blob([text], { type: `${type};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function currentProfileDefaults() {
  return DATA.default_profiles[state.profileId] || DATA.default_profiles.math_first_default;
}

function scoreComponents() {
  return DATA.score_schema?.components || {};
}

function scoreFactorCatalog() {
  return DATA.score_schema?.factor_catalog || [];
}

function buildDefaultConfig(profileId) {
  const profile = DATA.default_profiles[profileId] || DATA.default_profiles.math_first_default;
  const factorWeights = {};
  for (const factor of scoreFactorCatalog()) {
    factorWeights[factor.key] = asNumber(factor.defaultWeight, 0);
  }
  Object.assign(factorWeights, profile.factorWeights || {});
  const componentWeights = {};
  for (const [key, component] of Object.entries(scoreComponents())) {
    componentWeights[key] = asNumber(component.maxScore, 0);
  }
  Object.assign(componentWeights, profile.componentWeights || {});
  const tagWeights = {};
  for (const tag of state.customTagCatalog) {
    if (!(tag.label in tagWeights)) tagWeights[tag.label] = asNumber(tag.defaultWeight, 0);
  }
  return {
    schemaVersion: "ai_path_tag_browser_config_v3",
    profileId,
    profileLabel: profile.label,
    factorWeights,
    componentWeights,
    tagWeights,
    regionWeights: profile.regionWeights || {},
    preferences: {},
    customTags: {},
    customTagCatalog: clone(state.customTagCatalog),
    qualityTierLabels: ["第一梯队", "第二梯队", "第三梯队"],
  };
}

function loadLocalState() {
  try {
    const saved = JSON.parse(localStorage.getItem("aiPathTagBrowserConfig") || "null");
    if (saved?.schemaVersion === "ai_path_tag_browser_config_v3") {
      state.profileId = saved.profileId || "math_first_default";
      state.customTagCatalog = saved.customTagCatalog || [];
      const defaults = buildDefaultConfig(state.profileId);
      state.config = { ...defaults, ...saved, schemaVersion: "ai_path_tag_browser_config_v3" };
      state.config.factorWeights = { ...defaults.factorWeights, ...(saved.factorWeights || {}) };
      state.config.componentWeights = { ...defaults.componentWeights, ...(saved.componentWeights || {}) };
      state.config.tagWeights = { ...defaults.tagWeights, ...(saved.tagWeights || {}) };
      state.config.regionWeights = { ...defaults.regionWeights, ...(saved.regionWeights || {}) };
      state.config.qualityTierLabels = state.config.qualityTierLabels || ["第一梯队", "第二梯队", "第三梯队"];
      state.preferences = saved.preferences || {};
      state.customTags = saved.customTags || {};
      return;
    }
    if (saved?.schemaVersion === "ai_path_tag_browser_config_v1" || saved?.schemaVersion === "ai_path_tag_browser_config_v2") {
      state.profileId = saved.profileId || "math_first_default";
      state.customTagCatalog = saved.customTagCatalog || [];
      state.config = buildDefaultConfig(state.profileId);
      state.preferences = saved.preferences || {};
      state.customTags = saved.customTags || {};
      return;
    }
  } catch {
    // Ignore malformed local state.
  }
  state.config = buildDefaultConfig(state.profileId);
  state.preferences = state.config.preferences;
  state.customTags = state.config.customTags;
}

function persist() {
  state.config.preferences = state.preferences;
  state.config.customTags = state.customTags;
  state.config.customTagCatalog = state.customTagCatalog;
  localStorage.setItem("aiPathTagBrowserConfig", JSON.stringify(state.config));
}

function allTagCatalog() {
  const base = new Map();
  for (const tag of DATA.tag_catalog || []) base.set(tag.label, tag);
  for (const tag of state.customTagCatalog) base.set(tag.label, tag);
  return [...base.values()].sort((a, b) => {
    const ka = `${a.kind || ""}${a.label}`;
    const kb = `${b.kind || ""}${b.label}`;
    return ka.localeCompare(kb, "zh-CN");
  });
}

function rowTags(row) {
  const base = row.tags || [];
  const custom = state.customTags[row.pool_id] || [];
  return [...base, ...custom.map((label) => ({ label, kind: "preference", confidence: "user", sources: ["user"], evidence: [] }))];
}

function rowPreference(row) {
  return state.preferences[row.pool_id] || "neutral";
}

function tagWeight(label) {
  return asNumber(state.config.tagWeights?.[label], 0);
}

function factorWeight(key) {
  return asNumber(state.config.factorWeights?.[key], 0);
}

function componentMax(key) {
  return asNumber(state.config.componentWeights?.[key], scoreComponents()[key]?.maxScore || 0);
}

function confidenceFactor(confidence) {
  if (confidence === "high") return 1;
  if (confidence === "medium") return 0.82;
  if (confidence === "low") return 0.55;
  if (confidence === "derived") return 0.65;
  if (confidence === "user") return 1;
  return 0.75;
}

function addComponentValue(components, key, label, value, evidence = "") {
  if (!components[key]) {
    components[key] = {
      key,
      label: scoreComponents()[key]?.label || key,
      maxScore: componentMax(key),
      positive: 0,
      penalty: 0,
      explain: [],
    };
  }
  if (value >= 0) components[key].positive += value;
  else components[key].penalty += value;
  components[key].explain.push({ label, value, evidence });
}

function scoreRow(row) {
  const explain = [];
  const components = {};
  const scoreV3 = row.score_v3 || {};
  const evidenceQuality = scoreV3.evidence_quality || {};
  const alignmentCap = asNumber(evidenceQuality.alignment_positive_cap, 1);
  const alignmentBase = (asNumber(row.alignment_score, 0) / 100) * componentMax("alignment") * alignmentCap;
  addComponentValue(components, "alignment", `对齐基准×证据上限 ${Math.round(alignmentCap * 100)}%`, alignmentBase, evidenceQuality.training_label || "");

  for (const factor of scoreV3.factors || []) {
    const weight = factorWeight(factor.key);
    if (!weight) continue;
    let value = weight * confidenceFactor(factor.confidence);
    if (value > 0 && factor.component === "alignment") value *= alignmentCap;
    addComponentValue(components, factor.component, factor.label, value, (factor.evidence || []).join("；"));
  }

  for (const label of state.customTags[row.pool_id] || []) {
    const value = tagWeight(label);
    if (!value) continue;
    addComponentValue(components, "freedom", `自定义：${label}`, value, "用户手动标签");
  }

  let qualityScore = 0;
  const componentList = Object.values(components).map((component) => {
    const cappedPositive = Math.min(component.positive, component.maxScore);
    const score = cappedPositive + component.penalty;
    qualityScore += score;
    return { ...component, cappedPositive, score };
  });
  qualityScore = Math.max(0, Math.min(100, qualityScore));

  for (const component of componentList) {
    explain.push({ label: component.label, value: component.score });
    for (const item of component.explain) explain.push(item);
  }

  let score = qualityScore;
  const regionWeight = asNumber(state.config.regionWeights?.[row.province], 0);
  if (regionWeight) {
    score += regionWeight;
    explain.push({ label: `${row.province}地区`, value: regionWeight });
  }

  const pref = rowPreference(row);
  const prefValue = PREF_WEIGHTS[pref] || 0;
  if (prefValue) {
    score += prefValue;
    explain.push({ label: prefLabel(pref), value: prefValue });
  }

  score = Math.max(0, Math.min(120, score));
  return { score, qualityScore, explain, components: componentList };
}

function qualityTierLabels() {
  return state.config.qualityTierLabels || ["第一梯队", "第二梯队", "第三梯队"];
}

function assignQualityTiers(entries) {
  const labels = qualityTierLabels();
  const sortedByScore = [...entries].sort((a, b) => {
    const scoreDiff = b.score - a.score;
    if (scoreDiff) return scoreDiff;
    return (a.row.rank || 999999) - (b.row.rank || 999999);
  });
  const tierSize = Math.ceil(sortedByScore.length / labels.length) || 1;
  const tierById = new Map();
  sortedByScore.forEach((entry, index) => {
    const tierOrder = Math.min(labels.length - 1, Math.floor(index / tierSize));
    tierById.set(entry.row.pool_id, {
      tier: labels[tierOrder],
      tierOrder,
      qualityRank: index + 1,
    });
  });
  return entries.map((entry) => ({ ...entry, ...tierById.get(entry.row.pool_id) }));
}

function prefLabel(pref) {
  return {
    favorite: "首选",
    like: "喜欢",
    dislike: "不喜欢",
    ban: "ban",
    neutral: "中立",
  }[pref] || "中立";
}

function groupLabel(group) {
  return {
    math_stat_info: "数学/统计/信计",
    cs: "计算机",
    ai_intelligent_science: "AI/智能",
  }[group] || group || "-";
}

function initControls() {
  controls.profile.innerHTML = Object.entries(DATA.default_profiles)
    .map(([id, profile]) => `<option value="${esc(id)}">${esc(profile.label)}</option>`)
    .join("");
  controls.profile.value = state.profileId;
  fillTagSelects();
  updateProfileDescription();
}

function fillTagSelects() {
  const options = ['<option value="">全部</option>']
    .concat(allTagCatalog().map((tag) => `<option value="${esc(tag.label)}">${esc(tag.label)} (${tag.count ?? 0})</option>`))
    .join("");
  controls.includeTag.innerHTML = options;
  controls.excludeTag.innerHTML = options;
}

function updateProfileDescription() {
  const profile = currentProfileDefaults();
  $("profileDescription").textContent = profile.description || "";
}

function renderWeightEditor() {
  const factorCatalog = scoreFactorCatalog().filter(
    (factor) => Math.abs(asNumber(factor.defaultWeight, 0)) > 0 || Math.abs(asNumber(state.config.factorWeights?.[factor.key], 0)) > 0,
  );
  const componentRows = Object.entries(scoreComponents())
    .map(([key, component]) => {
      const value = componentMax(key);
      return `
        <div class="weight-row component-weight-row" data-component="${esc(key)}">
          <span title="${esc(component.label)}">${esc(component.label)}<small>组件上限</small></span>
          <input type="number" step="1" value="${esc(value)}" aria-label="${esc(component.label)} 组件上限" />
        </div>
      `;
    })
    .join("");
  const factorRows = factorCatalog
    .map((factor) => {
      const weight = factorWeight(factor.key);
      return `
        <div class="weight-row" data-factor="${esc(factor.key)}">
          <span title="${esc(factor.label)}">${esc(factor.label)}<small>${esc(factor.component || "custom")} · ${esc(factor.kind || "")}</small></span>
          <input type="number" step="1" value="${esc(weight)}" aria-label="${esc(factor.label)} 权重" />
        </div>
      `;
    })
    .join("");
  const customRows = state.customTagCatalog
    .map((tag) => {
      const weight = tagWeight(tag.label);
      return `
        <div class="weight-row custom-weight-row" data-tag="${esc(tag.label)}">
          <span title="${esc(tag.label)}">${esc(tag.label)}<small>自定义标签</small></span>
          <input type="number" step="1" value="${esc(weight)}" aria-label="${esc(tag.label)} 权重" />
        </div>
      `;
    })
    .join("");
  $("weightEditor").innerHTML = `
    <h3>组件上限</h3>
    ${componentRows}
    <h3>评分因子</h3>
    ${factorRows}
    ${customRows ? `<h3>自定义标签</h3>${customRows}` : ""}
  `;
  for (const row of document.querySelectorAll(".weight-row[data-factor]")) {
    const input = row.querySelector("input");
    const key = row.dataset.factor;
    input.addEventListener("input", () => {
      state.config.factorWeights[key] = asNumber(input.value, 0);
      persist();
      render();
    });
  }
  for (const row of document.querySelectorAll(".weight-row[data-component]")) {
    const input = row.querySelector("input");
    const key = row.dataset.component;
    input.addEventListener("input", () => {
      state.config.componentWeights[key] = asNumber(input.value, 0);
      persist();
      render();
    });
  }
  for (const row of document.querySelectorAll(".weight-row[data-tag]")) {
    const input = row.querySelector("input");
    const label = row.dataset.tag;
    input.addEventListener("input", () => {
      state.config.tagWeights[label] = asNumber(input.value, 0);
      persist();
      render();
    });
  }
}

function matchesFilters(row, scored) {
  if (controls.hideBan.checked && rowPreference(row) === "ban") return false;
  if (controls.manualOnly.checked && row.status !== "manual_review") return false;
  if (controls.group.value && row.major_group !== controls.group.value) return false;
  if (controls.confidence.value && row.strength_confidence !== controls.confidence.value) return false;

  const tags = rowTags(row).map((tag) => tag.label);
  if (controls.includeTag.value && !tags.includes(controls.includeTag.value)) return false;
  if (controls.excludeTag.value && tags.includes(controls.excludeTag.value)) return false;

  const q = norm(controls.search.value);
  if (q) {
    const haystack = norm(
      [
        row.college,
        row.major,
        row.province,
        row.status_label,
        row.final_reason,
        row.rationale,
        row.strength_evidence_summary,
        admissionSearchText(row),
        evidenceSearchText(row),
        tags.join(" "),
        (row.score_v3?.factors || []).map((factor) => `${factor.label} ${factor.key} ${(factor.evidence || []).join(" ")}`).join(" "),
        (row.score_v3?.data_gaps || []).join(" "),
        scored.explain.map((item) => item.label).join(" "),
      ].join(" "),
    );
    if (!haystack.includes(q)) return false;
  }
  return true;
}

function sortRows(rows) {
  const sort = controls.sort.value;
  const rankAsc = (a, b) => (a.row.rank || 999999) - (b.row.rank || 999999);
  const rankDesc = (a, b) => -rankAsc(a, b);
  if (sort === "rankAsc") return rows.sort(rankAsc);
  if (sort === "rankDesc") return rows.sort(rankDesc);
  if (sort === "scoreDesc") return rows.sort((a, b) => b.score - a.score || rankAsc(a, b));
  if (sort === "collegeAsc") {
    return rows.sort((a, b) => `${a.row.college}${a.row.major}`.localeCompare(`${b.row.college}${b.row.major}`, "zh-CN"));
  }
  return rows.sort((a, b) => {
    const tierDiff = a.tierOrder - b.tierOrder;
    if (tierDiff) return tierDiff;
    return rankAsc(a, b);
  });
}

function scoredRowsWithTiers() {
  const scored = ROWS.map((row) => {
    const result = scoreRow(row);
    return { row, score: result.score, qualityScore: result.qualityScore, explain: result.explain, components: result.components };
  });
  return assignQualityTiers(scored);
}

function computeRows() {
  const scored = scoredRowsWithTiers().filter((entry) => matchesFilters(entry.row, entry));
  return sortRows(scored);
}

function renderSummary(entries) {
  $("shownCount").textContent = fmt(entries.length);
  $("autoCount").textContent = fmt(entries.filter((entry) => entry.row.status === "auto").length);
  $("manualCount").textContent = fmt(entries.filter((entry) => entry.row.status === "manual_review").length);
  $("highEvidenceCount").textContent = fmt(entries.filter((entry) => entry.row.strength_confidence === "high").length);

  const profile = currentProfileDefaults();
  const qualitySummary = DATA.data_quality_summary || {};
  const hardEvidence = qualitySummary.categories
    ?.find((category) => category.key === "curriculum_hard_evidence")
    ?.fields?.find((field) => field.key === "full_plan_or_course_grid");
  $("activeConfig").innerHTML = `
    <span class="chip platform small">${esc(profile.label)}</span>
    <span class="chip small">质量分不含位次</span>
    <span class="chip small">梯队内按位次</span>
    ${hardEvidence ? `<span class="chip evidence small">方案/课表 ${fmt(hardEvidence.coverage)}/${fmt(qualitySummary.rowCount)}</span>` : ""}
  `;
}

function factorChipClass(factor) {
  if (factor.kind === "penalty") return "red_flag";
  if (factor.component === "platform" || factor.component === "research") return "platform";
  if (factor.component === "alignment") return "fit";
  if (factor.component === "life") return "region";
  return "evidence";
}

function topScoreFactors(row, limit = 9) {
  return (row.score_v3?.factors || [])
    .map((factor) => ({ ...factor, absWeight: Math.abs(factorWeight(factor.key)) }))
    .filter((factor) => factor.absWeight > 0)
    .sort((a, b) => b.absWeight - a.absWeight || a.label.localeCompare(b.label, "zh-CN"))
    .slice(0, limit);
}

function admissionSummary(row) {
  const flat = row.admission_flat || {};
  const parts = [];
  if (flat.plan_count) parts.push(`计划 ${fmt(flat.plan_count)} 人`);
  if (flat.tuition_raw || flat.tuition) parts.push(`学费 ${fmt(flat.tuition_raw || flat.tuition)} 元/年`);
  if (flat.subject_requirement) parts.push(flat.subject_requirement);
  if (flat["2025_history_lowest_rank"]) parts.push(`2025位次 ${fmt(flat["2025_history_lowest_rank"])}`);
  if (flat["2025_history_lowest_score"]) parts.push(`2025最低分 ${fmt(flat["2025_history_lowest_score"])}`);
  return parts.join(" · ") || "主表未匹配";
}

function admissionSearchText(row) {
  const sections = row.admission_info || [];
  return sections
    .flatMap((section) => section.items || [])
    .map((item) => `${item.label} ${item.key} ${item.value}`)
    .join(" ");
}

function renderAdmissionValue(item) {
  const raw = String(item.value ?? "");
  const text = esc(fmt(raw));
  if (/^https?:\/\//i.test(raw)) {
    return `<a href="${esc(raw)}" target="_blank" rel="noreferrer">${text}</a>`;
  }
  return text;
}

function renderAdmissionDetails(row) {
  const sections = row.admission_info || [];
  const body = sections.length
    ? sections
        .map(
          (section) => `
            <section class="admission-section">
              <h4>${esc(section.title)}</h4>
              <dl class="admission-grid">
                ${(section.items || [])
                  .map(
                    (item) => `
                      <div class="admission-item">
                        <dt title="${esc(item.key)}">${esc(item.label)}</dt>
                        <dd>${renderAdmissionValue(item)}</dd>
                      </div>
                    `,
                  )
                  .join("")}
      </dl>
            </section>
          `,
        )
        .join("")
    : '<p class="admission-empty">没有在主表中匹配到这条志愿。</p>';
  return `<div class="admission-details"><div class="admission-body">${body}</div></div>`;
}

function evidenceSearchText(row) {
  return (row.evidence_panels || [])
    .map((item) =>
      [
        item.title,
        item.kind,
        item.status,
        item.confidence,
        item.training_status,
        item.summary,
        item.risks,
        item.gaps,
        item.notes,
        (item.source_urls || []).join(" "),
      ].join(" "),
    )
    .join(" ");
}

function evidenceKindLabel(kind) {
  return {
    hard: "硬证据初查",
    hard_rescue: "硬证据救援",
    weak: "弱证据初查",
    weak_rescue: "弱证据救援",
    project101: "101计划",
  }[kind] || kind || "证据";
}

function evidenceKindClass(kind) {
  return `evidence-${String(kind || "unknown").replaceAll("_", "-")}`;
}

function renderEvidencePanels(row) {
  const panels = row.evidence_panels || [];
  if (!panels.length) return '<p class="admission-empty">没有合并到调研证据。</p>';
  return `
    <div class="evidence-panel-list">
      ${panels
        .map(
          (item) => `
            <article class="evidence-panel ${esc(evidenceKindClass(item.kind))}">
              <div class="evidence-panel-head">
                <h4>${esc(evidenceKindLabel(item.kind))}</h4>
                <div class="chips">
                  <span class="chip small">${esc(item.status || "-")}</span>
                  <span class="chip small">${esc(item.confidence || "-")}</span>
                  ${item.training_status ? `<span class="chip small">${esc(item.training_status)}</span>` : ""}
                </div>
              </div>
              ${item.major_names ? `<p><strong>涉及专业：</strong>${esc(item.major_names)}</p>` : ""}
              ${item.summary ? `<p><strong>摘要：</strong>${esc(item.summary)}</p>` : ""}
              ${item.risks ? `<p class="evidence-risk"><strong>风险：</strong>${esc(item.risks)}</p>` : ""}
              ${item.gaps ? `<p class="evidence-gap"><strong>缺口：</strong>${esc(item.gaps)}</p>` : ""}
              ${item.notes ? `<p><strong>备注：</strong>${esc(item.notes)}</p>` : ""}
              <div class="url-list compact">
                ${(item.source_urls || []).map((url) => `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a>`).join("")}
              </div>
              <small>${esc(item.source_file || "")}</small>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function evidenceExportSummary(row) {
  return (row.evidence_panels || [])
    .map((item) => `${evidenceKindLabel(item.kind)}[${item.status || "-"}|${item.confidence || "-"}|${item.training_status || "-"}]: ${item.summary || item.gaps || ""}`)
    .join(" || ");
}

function evidenceSourceSummary(row) {
  return (row.evidence_panels || [])
    .flatMap((item) => item.source_urls || [])
    .filter(Boolean)
    .join(" | ");
}

function renderScoreComponents(entry) {
  const components = entry.components || [];
  if (!components.length) return '<p class="admission-empty">没有评分组件。</p>';
  const order = Object.keys(scoreComponents());
  return `
    <div class="score-component-grid">
      ${components
        .sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
        .map((component) => {
          const max = component.maxScore || 1;
          const pct = Math.max(0, Math.min(100, (component.cappedPositive / max) * 100));
          return `
            <article class="score-component">
              <div class="score-component-head">
                <strong>${esc(component.label)}</strong>
                <span>${Math.round(component.score)} / ${fmt(component.maxScore)}</span>
              </div>
              <div class="score-bar"><span style="width: ${pct}%"></span></div>
              <div class="chips">
                ${component.explain
                  .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
                  .slice(0, 8)
                  .map((item) => `<span class="chip ${item.value < 0 ? "red_flag" : "small"}" title="${esc(item.evidence || "")}">${esc(item.label)} ${item.value > 0 ? "+" : ""}${Math.round(item.value)}</span>`)
                  .join("")}
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderScoreFactors(row) {
  const factors = row.score_v3?.factors || [];
  if (!factors.length) return '<p class="admission-empty">没有规范评分因子。</p>';
  return `
    <div class="factor-list">
      ${factors
        .map(
          (factor) => `
            <article class="factor-item">
              <div>
                <strong>${esc(factor.label)}</strong>
                <small>${esc(factor.component)} · ${esc(factor.kind)} · ${esc(factor.confidence)}</small>
              </div>
              <span class="chip ${esc(factorChipClass(factor))}">${factorWeight(factor.key) > 0 ? "+" : ""}${fmt(factorWeight(factor.key))}</span>
              ${(factor.evidence || []).length ? `<p>${esc((factor.evidence || []).join("；"))}</p>` : ""}
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderCards(entries) {
  $("cards").innerHTML = entries
    .map((entry) => {
      const row = entry.row;
      const pref = rowPreference(row);
      const factors = topScoreFactors(row)
        .map((factor) => `<span class="chip ${esc(factorChipClass(factor))}" title="${esc(factor.confidence)}">${esc(factor.label)}</span>`)
        .join("");
      const dataGaps = row.score_v3?.data_gaps || [];
      return `
        <article class="card ${pref === "ban" ? "banned" : ""}" data-id="${esc(row.pool_id)}">
          <div class="card-kicker">
            <span>志愿编号 ${esc(row.volunteer_id || row.pool_id)}</span>
            <button type="button" data-action="detail" class="detail-circle-button" title="查看完整详情" aria-label="查看完整详情">?</button>
          </div>
          <div class="card-head">
            <div class="card-title">
              <h3>${esc(row.college)}<span>${esc(row.major)}</span></h3>
              <div class="chips">
                <span class="chip small">${esc(row.status_label)}</span>
                <span class="chip small">${esc(groupLabel(row.major_group))}</span>
                <span class="chip small">${esc(row.strength_confidence)}</span>
              </div>
            </div>
            <div class="score-box">
              <strong>${Math.round(entry.qualityScore)}</strong>
              <span>${esc(entry.tier)} · ${Math.round(entry.score)} 排序分</span>
            </div>
          </div>
          <div class="meta-grid">
            <div class="meta"><strong>${fmt(row.rank)}</strong><span>预测/历史位次</span></div>
            <div class="meta"><strong>${fmt(row.alignment_score)}</strong><span>原始对齐分</span></div>
            <div class="meta"><strong>${esc(row.province || "-")}</strong><span>地区</span></div>
            <div class="meta"><strong>${esc(prefLabel(pref))}</strong><span>偏好</span></div>
          </div>
          <p class="admission-line">${esc(admissionSummary(row))}</p>
          <div class="chips">${factors || '<span class="chip small">无评分因子</span>'}</div>
          ${dataGaps.length ? `<div class="chips">${dataGaps.slice(0, 3).map((gap) => `<span class="chip evidence small">${esc(gap)}</span>`).join("")}</div>` : ""}
          <p class="rationale">${esc(row.final_reason || row.rationale || row.strength_evidence_summary || "")}</p>
          <div class="card-actions">
            ${preferenceButton(row.pool_id, "favorite", pref)}
            ${preferenceButton(row.pool_id, "like", pref)}
            ${preferenceButton(row.pool_id, "dislike", pref)}
            ${preferenceButton(row.pool_id, "ban", pref)}
          </div>
        </article>
      `;
    })
    .join("");

  for (const card of document.querySelectorAll(".card")) {
    const id = card.dataset.id;
    card.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      const action = button.dataset.action;
      if (action === "detail") {
        openDetail(id);
      } else if (action) {
        setPreference(id, rowPreferenceById(id) === action ? "neutral" : action);
      }
    });
  }
}

function preferenceButton(id, action, pref) {
  return `<button type="button" data-action="${action}" class="${pref === action ? "active" : ""}">${prefLabel(action)}</button>`;
}

function rowPreferenceById(id) {
  return state.preferences[id] || "neutral";
}

function setPreference(id, pref) {
  if (pref === "neutral") delete state.preferences[id];
  else state.preferences[id] = pref;
  persist();
  render();
}

function openDetail(id) {
  const entry = scoredRowsWithTiers().find((item) => item.row.pool_id === id);
  if (!entry) return;
  const row = entry.row;
  $("detailTitle").textContent = `${row.college} · ${row.major}`;
  $("detailSubtitle").textContent = `${fmt(row.rank)} 位次 · ${groupLabel(row.major_group)} · ${row.status_label}`;
  $("detailBody").innerHTML = `
    <section class="detail-section">
      <h3>评分解释</h3>
      <div class="chips">
        <span class="chip platform">${Math.round(entry.qualityScore)} 质量分</span>
        <span class="chip">${Math.round(entry.score)} 排序分</span>
        <span class="chip">${entry.tier}</span>
        <span class="chip">质量排名 ${entry.qualityRank}</span>
        <span class="chip">质量分不含位次</span>
      </div>
      ${renderScoreComponents(entry)}
    </section>
    <section class="detail-section">
      <h3>规范评分因子</h3>
      ${renderScoreFactors(row)}
      ${(row.score_v3?.data_gaps || []).length ? `<div class="chips">${(row.score_v3?.data_gaps || []).map((gap) => `<span class="chip evidence">${esc(gap)}</span>`).join("")}</div>` : ""}
    </section>
    <section class="detail-section">
      <h3>标签</h3>
      <div class="chips">
        ${rowTags(row).map((tag) => `<span class="chip ${esc(tag.kind)}">${esc(tag.label)} · ${esc(tag.confidence)}</span>`).join("")}
      </div>
      <div class="row-tag-editor">
        <select id="rowTagSelect">${allTagCatalog().map((tag) => `<option value="${esc(tag.label)}">${esc(tag.label)}</option>`).join("")}</select>
        <button id="addRowTagBtn" type="button">给本志愿加标签</button>
      </div>
    </section>
    <section class="detail-section">
      <h3>判断理由</h3>
      <p>${esc(row.final_reason || row.rationale || "-")}</p>
      <p>${esc(row.strength_evidence_summary || "")}</p>
    </section>
    <section class="detail-section">
      <h3>调研/补证据结果</h3>
      ${renderEvidencePanels(row)}
    </section>
    <section class="detail-section">
      <h3>主表录取信息</h3>
      <p class="detail-summary">${esc(admissionSummary(row))}</p>
      ${renderAdmissionDetails(row)}
    </section>
    <section class="detail-section">
      <h3>证据链接</h3>
      <div class="url-list">
        ${(row.evidence_urls || []).map((url) => `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a>`).join("") || '<span class="chip small">无链接</span>'}
      </div>
    </section>
  `;
  $("addRowTagBtn").addEventListener("click", () => {
    const label = $("rowTagSelect").value;
    if (!label) return;
    const list = new Set(state.customTags[id] || []);
    list.add(label);
    state.customTags[id] = [...list];
    persist();
    openDetail(id);
    render();
  });
  $("detailDialog").showModal();
}

function render() {
  const entries = computeRows();
  state.filtered = entries;
  renderSummary(entries);
  renderCards(entries);
}

function resetToProfile(profileId) {
  state.profileId = profileId;
  state.config = buildDefaultConfig(profileId);
  state.preferences = {};
  state.customTags = {};
  persist();
  controls.profile.value = profileId;
  updateProfileDescription();
  renderWeightEditor();
  render();
}

function exportConfig() {
  persist();
  download("ai_path_browser_config.json", JSON.stringify(state.config, null, 2));
}

function exportCsv() {
  const admissionColumns = DATA.admission_columns || [];
  const header = [
    "pool_id",
    "volunteer_id",
    "college",
    "major",
    "rank",
    "tier",
    "quality_score",
    "sort_score",
    "preference",
    "status",
    "major_group",
    "province",
    "score_components",
    "score_factors",
    "data_gaps",
    "tags",
    "final_reason",
    "evidence_summary",
    "evidence_sources",
    ...admissionColumns.map((column) => `admission.${column}`),
  ];
  const lines = [header.join(",")];
  for (const entry of state.filtered) {
    const row = entry.row;
    const admissionFlat = row.admission_flat || {};
    const values = [
      row.pool_id,
      row.volunteer_id,
      row.college,
      row.major,
      row.rank,
      entry.tier,
      Math.round(entry.qualityScore),
      Math.round(entry.score),
      prefLabel(rowPreference(row)),
      row.status_label,
      groupLabel(row.major_group),
      row.province,
      (entry.components || []).map((component) => `${component.label}:${Math.round(component.score)}`).join(";"),
      (row.score_v3?.factors || []).map((factor) => factor.label).join(";"),
      (row.score_v3?.data_gaps || []).join(";"),
      rowTags(row).map((tag) => tag.label).join(";"),
      row.final_reason || row.rationale || "",
      evidenceExportSummary(row),
      evidenceSourceSummary(row),
      ...admissionColumns.map((column) => admissionFlat[column] || ""),
    ].map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`);
    lines.push(values.join(","));
  }
  download("ai_path_current_ranking.csv", "\ufeff" + lines.join("\n"), "text/csv");
}

function bindEvents() {
  for (const control of [controls.search, controls.group, controls.confidence, controls.includeTag, controls.excludeTag, controls.sort, controls.hideBan, controls.manualOnly]) {
    control.addEventListener("input", render);
    control.addEventListener("change", render);
  }
  controls.profile.addEventListener("change", () => resetToProfile(controls.profile.value));
  $("resetConfigBtn").addEventListener("click", () => resetToProfile(state.profileId));
  $("clearFiltersBtn").addEventListener("click", () => {
    controls.search.value = "";
    controls.group.value = "";
    controls.confidence.value = "";
    controls.includeTag.value = "";
    controls.excludeTag.value = "";
    controls.manualOnly.checked = false;
    render();
  });
  $("exportConfigBtn").addEventListener("click", exportConfig);
  $("exportCsvBtn").addEventListener("click", exportCsv);
  $("closeDialogBtn").addEventListener("click", () => $("detailDialog").close());
  $("addTagBtn").addEventListener("click", () => $("tagDialog").showModal());
  $("closeTagDialogBtn").addEventListener("click", () => $("tagDialog").close());
  $("tagForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const label = $("newTagLabel").value.trim();
    if (!label) return;
    const tag = {
      label,
      kind: $("newTagKind").value,
      defaultWeight: asNumber($("newTagWeight").value, 0),
      count: 0,
    };
    if (!state.customTagCatalog.some((item) => item.label === label)) {
      state.customTagCatalog.push(tag);
    }
    state.config.tagWeights[label] = tag.defaultWeight;
    persist();
    fillTagSelects();
    renderWeightEditor();
    render();
    $("tagForm").reset();
    $("newTagWeight").value = "-5";
    $("tagDialog").close();
  });
  $("importConfigInput").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const imported = JSON.parse(text);
    if (imported.schemaVersion !== "ai_path_tag_browser_config_v3") {
      alert("配置版本不匹配");
      return;
    }
    state.profileId = imported.profileId || "math_first_default";
    state.customTagCatalog = imported.customTagCatalog || [];
    state.config = imported;
    state.preferences = imported.preferences || {};
    state.customTags = imported.customTags || {};
    controls.profile.value = state.profileId;
    persist();
    fillTagSelects();
    updateProfileDescription();
    renderWeightEditor();
    render();
  });
}

function init() {
  loadLocalState();
  initControls();
  bindEvents();
  renderWeightEditor();
  const fullOrGrid = DATA.data_quality_summary?.categories
    ?.find((category) => category.key === "curriculum_hard_evidence")
    ?.fields?.find((field) => field.key === "full_plan_or_course_grid");
  $("dataMeta").textContent = `${DATA.row_count} 个候选；score_v3；方案/课表 ${fullOrGrid ? `${fullOrGrid.coverage}/${DATA.row_count}` : "-"}；${DATA.tagged_29k_50k_rows} 个强标签采集项`;
  render();
}

init();
