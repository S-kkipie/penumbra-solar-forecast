// Penumbra dashboard. Static: reads JSON produced by scripts/export_site.py and the daily live job.
const $ = (s) => document.querySelector(s);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (x, d = 1) => (x == null || Number.isNaN(x) ? "—" : Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const TZ = "Europe/Brussels";
const hourLabel = (iso) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: TZ }).format(new Date(iso));
const dayLabel = (iso) => new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: TZ }).format(new Date(iso + "T12:00:00Z"));

const charts = [];
const state = { lead: "2", bt: null, days: null, live: null, currentDay: null };

// ---------- theme ----------
const themeBtn = $("#themeToggle");
try { const t = localStorage.getItem("penumbra-theme"); if (t) document.documentElement.dataset.theme = t; } catch (_) {}
themeBtn.addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("penumbra-theme", document.documentElement.dataset.theme); } catch (_) {}
  renderAll();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => renderAll());

function palette() {
  return {
    pen: css("--series-1"), band: css("--series-1-band"), elia: css("--series-2"), penNwp: css("--series-3"),
    actual: css("--actual"), text: css("--text-primary"), text2: css("--text-secondary"), muted: css("--text-muted"),
    grid: css("--grid"), line: css("--line"), surface: css("--surface-1"),
  };
}

function baseOption(p) {
  return {
    animation: false,
    textStyle: { fontFamily: "IBM Plex Sans, system-ui, sans-serif", color: p.text2 },
    grid: { left: 52, right: 16, top: 16, bottom: 36, containLabel: false },
    tooltip: {
      trigger: "axis", backgroundColor: p.surface, borderColor: p.line, textStyle: { color: p.text, fontSize: 12 },
      axisPointer: { type: "line", lineStyle: { color: p.muted, width: 1 } },
    },
  };
}
const axisStyle = (p) => ({
  axisLine: { lineStyle: { color: p.line } }, axisTick: { show: false },
  axisLabel: { color: p.muted, fontSize: 11 }, splitLine: { lineStyle: { color: p.grid } },
});

function mount(id, option) {
  const el = document.getElementById(id);
  let c = echarts.getInstanceByDom(el);
  if (!c) { c = echarts.init(el, null, { renderer: "svg" }); charts.push(c); }
  c.setOption(option, true);
  return c;
}
window.addEventListener("resize", () => charts.forEach((c) => c.resize()));

function legend(el, items) {
  el.innerHTML = items.map(([label, color, kind]) =>
    `<span><i class="${kind || ""}" style="background:${color}"></i>${label}</span>`).join("");
}

// ---------- fan chart (tomorrow / explorer) ----------
function fanOption(p, { labels, q10, q50, q90, elia, actual, penNwp }) {
  const lo = q10, span = q90.map((v, i) => (v == null || lo[i] == null ? null : v - lo[i]));
  const series = [
    { name: "P10", type: "line", data: lo, stack: "band", symbol: "none", lineStyle: { opacity: 0 }, tooltip: { show: false } },
    { name: "80 % band", type: "line", data: span, stack: "band", symbol: "none", lineStyle: { opacity: 0 },
      areaStyle: { color: p.band }, tooltip: { show: false } },
    { name: "Penumbra P50", type: "line", data: q50, symbol: "none", lineStyle: { width: 2, color: p.pen }, itemStyle: { color: p.pen } },
  ];
  if (penNwp) series.push({ name: "Penumbra NWP-only", type: "line", data: penNwp, symbol: "none", lineStyle: { width: 1.5, color: p.penNwp, type: [4, 3] }, itemStyle: { color: p.penNwp } });
  if (elia) series.push({ name: "Elia D-1 11h", type: "line", data: elia, symbol: "none", lineStyle: { width: 2, color: p.elia }, itemStyle: { color: p.elia } });
  if (actual && actual.some((v) => v != null)) series.push({ name: "Measured", type: "line", data: actual, symbol: "circle", symbolSize: 5, showSymbol: true, lineStyle: { width: 2, color: p.actual }, itemStyle: { color: p.actual, borderColor: p.surface, borderWidth: 1.5 } });
  const opt = baseOption(p);
  opt.tooltip.formatter = (items) => {
    const i = items[0].dataIndex;
    let h = `<b>${labels[i]}</b> Brussels<br>`;
    h += `Penumbra P50: <b>${fmt(q50[i], 0)}</b> MW<br>80 % band: ${fmt(q10[i], 0)}–${fmt(q90[i], 0)} MW<br>`;
    if (penNwp) h += `NWP-only P50: ${fmt(penNwp[i], 0)} MW<br>`;
    if (elia) h += `Elia D-1 11h: ${fmt(elia[i], 0)} MW<br>`;
    if (actual && actual[i] != null) h += `Measured: <b>${fmt(actual[i], 0)}</b> MW`;
    return h;
  };
  opt.xAxis = { type: "category", data: labels, boundaryGap: false, ...axisStyle(p), splitLine: { show: false },
    axisLabel: { color: p.muted, fontSize: 11, interval: 2 } };
  opt.yAxis = { type: "value", ...axisStyle(p), axisLabel: { color: p.muted, fontSize: 11, formatter: (v) => v.toLocaleString("en-US") } };
  opt.series = series;
  return opt;
}

// ---------- tomorrow ----------
function renderTomorrow() {
  const p = palette();
  const L = state.live && state.live.latest;
  if (!L) {
    $("#tomorrowMeta").textContent = "The first live forecast is issued by the daily job at 10:30 UTC, before the 12:00 CET day-ahead gate.";
    $("#chartTomorrow").innerHTML = `<div class="empty">Waiting for the first issuance. Meanwhile, explore 19 months of out-of-sample forecasts below.</div>`;
    return;
  }
  const hrs = L.hours;
  const labels = hrs.map((h) => hourLabel(h.t));
  const get = (k) => hrs.map((h) => h[k]);
  const hasElia = hrs.some((h) => h.elia_da11 != null);
  mount("chartTomorrow", fanOption(p, { labels, q10: get("q10"), q50: get("q50"), q90: get("q90"),
    elia: hasElia ? get("elia_da11") : null, actual: get("actual") }));
  const items = [["Penumbra P50", p.pen], ["80 % band", p.band, "band"]];
  if (hasElia) items.push(["Elia D-1 11h", p.elia]);
  if (hrs.some((h) => h.actual != null)) items.push(["Measured", p.actual, "dot"]);
  legend($("#tomorrowLegend"), items);
  const issued = new Date(L.issued_at_utc);
  $("#tomorrowMeta").innerHTML = `Target day <b>${dayLabel(L.target_date)}</b> · issued ${issued.toISOString().slice(0, 16).replace("T", " ")} UTC · model <code>${L.model}</code> · installed ${fmt(L.capacity_mw / 1000, 2)} GW`;
  const e10 = hrs.reduce((a, h) => a + (h.q10 || 0), 0), e90 = hrs.reduce((a, h) => a + (h.q90 || 0), 0);
  const peak = hrs.reduce((m, h) => (h.q50 > m.q50 ? h : m), hrs[0]);
  const tiles = [
    { v: `${fmt(L.energy_mwh.q50 / 1000, 1)}<small>GWh</small>`, l: "Expected energy (P50)", s: `band-sum ${fmt(e10 / 1000, 1)}–${fmt(e90 / 1000, 1)} GWh` },
    { v: `${fmt(peak.q50 / 1000, 2)}<small>GW</small>`, l: `Peak at ${hourLabel(peak.t)}`, s: `${fmt((100 * peak.q50) / L.capacity_mw, 0)} % of installed capacity` },
  ];
  if (L.energy_mwh.elia_da11 != null) tiles.push({ v: `${fmt(L.energy_mwh.elia_da11 / 1000, 1)}<small>GWh</small>`, l: "Elia D-1 11h energy", s: "the operator's own day-ahead view" });
  $("#tomorrowTiles").innerHTML = tiles.map((t) => `<div class="tile"><div class="v">${t.v}</div><div class="l">${t.l}</div><div class="s">${t.s}</div></div>`).join("");
}

// ---------- live record ----------
function renderLive() {
  const p = palette();
  const tr = (state.live && state.live.track_record) || {};
  const days = ((state.live && state.live.days) || []).filter((d) => d.mae_penumbra_mw != null);
  const tiles = [
    { v: `${tr.n_days_issued ?? 0}`, l: "Days issued", s: `${tr.n_days_scored ?? 0} fully scored` },
    { v: tr.mae_penumbra_mw != null ? `${fmt(tr.mae_penumbra_mw, 0)}<small>MW</small>` : "—", l: "Penumbra MAE (live)", s: "daylight hours" },
    { v: tr.mae_elia_da11_mw != null ? `${fmt(tr.mae_elia_da11_mw, 0)}<small>MW</small>` : "—", l: "Elia D-1 11h MAE (live)", s: tr.skill_vs_elia_pct != null ? `skill ${tr.skill_vs_elia_pct > 0 ? "+" : ""}${fmt(tr.skill_vs_elia_pct, 1)} %` : "accumulating" },
    { v: tr.coverage_80 != null ? `${fmt(100 * tr.coverage_80, 0)}<small>%</small>` : "—", l: "80 % band coverage (live)", s: tr.days_better_than_elia != null ? `better than Elia on ${tr.days_better_than_elia}/${tr.n_days_scored} days` : "target 80 %" },
  ];
  $("#liveTiles").innerHTML = tiles.map((t) => `<div class="tile"><div class="v">${t.v}</div><div class="l">${t.l}</div><div class="s">${t.s}</div></div>`).join("");
  const opt = baseOption(p);
  opt.xAxis = { type: "category", data: days.map((d) => d.date.slice(5)), ...axisStyle(p), splitLine: { show: false } };
  opt.yAxis = { type: "value", ...axisStyle(p) };
  opt.series = [
    { name: "Penumbra", type: "bar", data: days.map((d) => d.mae_penumbra_mw), itemStyle: { color: p.pen, borderRadius: [4, 4, 0, 0] }, barGap: "8%", barMaxWidth: 18 },
    { name: "Elia D-1 11h", type: "bar", data: days.map((d) => d.mae_elia_da11_mw ?? null), itemStyle: { color: p.elia, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 18 },
  ];
  opt.tooltip.axisPointer = { type: "shadow", shadowStyle: { color: "rgba(127,127,127,0.08)" } };
  mount("chartLive", opt);
  legend($("#liveLegend"), [["Penumbra", p.pen], ["Elia D-1 11h", p.elia]]);
  const all = (state.live && state.live.days) || [];
  $("#liveTable").innerHTML = `<thead><tr><th>Target day</th><th>Issued (UTC)</th><th>Penumbra</th><th>Elia</th><th>Cover.</th></tr></thead><tbody>` +
    all.slice().reverse().map((d) => `<tr><td>${d.date}</td><td>${d.issued_at_utc.slice(5, 16).replace("T", " ")}</td><td>${d.mae_penumbra_mw != null ? fmt(d.mae_penumbra_mw, 0) : "pending"}</td><td>${d.mae_elia_da11_mw != null ? fmt(d.mae_elia_da11_mw, 0) : "—"}</td><td>${d.coverage_80 != null ? fmt(100 * d.coverage_80, 0) + "%" : "—"}</td></tr>`).join("") + "</tbody>";
}

// ---------- backtest ----------
const LABEL = { persistence: "Persistence (D-2)", climatology: "Climatology", linear_nwp: "Linear NWP", elia_da11: "Elia D-1 11h", pen_q50: "Penumbra (NWP only)", hyb_q50: "Penumbra Hybrid" };

function renderBacktest() {
  const p = palette();
  const R = state.bt.leads[state.lead];
  const pt = Object.fromEntries(R.point.map((r) => [r.key, r]));
  const it = Object.fromEntries(R.interval.map((r) => [r.key, r]));
  const sig = R.significance;
  $("#btPeriod").textContent = `${R.n_days} days`;
  const hy = pt.hyb_q50, pe = pt.pen_q50, el = pt.elia_da11;
  const pv = (x) => (x < 1e-4 ? "p < 0.0001" : `p = ${x.toFixed(4)}`);
  const tiles = [
    { v: `${fmt(hy.nMAE_pct_cap, 2)}<small>%</small>`, l: "Hybrid nMAE (point error)", s: `Elia ${fmt(el.nMAE_pct_cap, 2)} % · DM ${pv(sig.hyb_q50_vs_elia_da11.p_value)}` },
    { v: `${fmt(pe.nMAE_pct_cap, 2)}<small>%</small>`, l: "Weather-only nMAE (free data only)", s: `${fmt(pe.skill_vs_persistence_pct, 0)} % better than persistence` },
    { v: `${fmt(100 * (1 - it.hyb_q50.width / it.elia_da11.width), 0)}<small>% narrower</small>`, l: "80 % band vs Elia's P10–P90", s: `coverage ${fmt(it.hyb_q50.coverage, 1)} % vs ${fmt(it.elia_da11.coverage, 1)} %` },
    { v: `${fmt(100 * (1 - it.hyb_q50.winkler / it.elia_da11.winkler), 1)}<small>% better</small>`, l: "Winkler interval score vs Elia", s: `pinball ${fmt(it.hyb_q50.mean_pinball, 3)} vs ${fmt(it.elia_da11.mean_pinball, 3)}` },
  ];
  $("#btTiles").innerHTML = tiles.map((t) => `<div class="tile"><div class="v">${t.v}</div><div class="l">${t.l}</div><div class="s">${t.s}</div></div>`).join("");

  // methods bar (single measure, sorted)
  const rows = R.point.slice().sort((a, b) => b.nMAE_pct_cap - a.nMAE_pct_cap);
  const colorFor = (k) => (k === "hyb_q50" ? p.pen : k === "pen_q50" ? p.penNwp : k === "elia_da11" ? p.elia : p.muted);
  const o1 = baseOption(p);
  o1.grid = { left: 4, right: 48, top: 8, bottom: 8, containLabel: true };
  o1.tooltip = { ...o1.tooltip, trigger: "item", formatter: (it2) => `${it2.name}<br><b>${fmt(it2.value, 2)} %</b> of capacity` };
  o1.xAxis = { type: "value", ...axisStyle(p) };
  o1.yAxis = { type: "category", data: rows.map((r) => LABEL[r.key]), ...axisStyle(p), axisLabel: { color: p.text2, fontSize: 12 } };
  o1.series = [{ type: "bar", data: rows.map((r) => ({ value: r.nMAE_pct_cap, itemStyle: { color: colorFor(r.key), borderRadius: [0, 4, 4, 0] } })), barWidth: 14,
    label: { show: true, position: "right", color: p.text2, fontSize: 11, formatter: (d) => fmt(d.value, 2) } }];
  mount("chartMethods", o1);

  // monthly lines
  const months = R.by_month.map((r) => r.month);
  const o2 = baseOption(p);
  o2.xAxis = { type: "category", data: months, ...axisStyle(p), splitLine: { show: false } };
  o2.yAxis = { type: "value", ...axisStyle(p) };
  o2.tooltip.valueFormatter = (v) => `${fmt(v, 2)} %`;
  o2.series = [
    { name: "Elia D-1 11h", type: "line", data: R.by_month.map((r) => r.elia_da11), symbol: "circle", symbolSize: 6, lineStyle: { width: 2, color: p.elia }, itemStyle: { color: p.elia } },
    { name: "Penumbra (NWP only)", type: "line", data: R.by_month.map((r) => r.pen_q50), symbol: "circle", symbolSize: 6, lineStyle: { width: 2, color: p.penNwp, type: [4, 3] }, itemStyle: { color: p.penNwp } },
    { name: "Penumbra Hybrid", type: "line", data: R.by_month.map((r) => r.hyb_q50), symbol: "circle", symbolSize: 6, lineStyle: { width: 2, color: p.pen }, itemStyle: { color: p.pen } },
  ];
  mount("chartMonthly", o2);
  legend($("#monthLegend"), [["Hybrid", p.pen], ["NWP only", p.penNwp], ["Elia", p.elia]]);

  // coverage by regime (dot plot vs 80 % target)
  const reg = R.by_regime;
  const o3 = baseOption(p);
  o3.grid = { left: 4, right: 24, top: 28, bottom: 8, containLabel: true };
  o3.tooltip = { ...o3.tooltip, trigger: "item", formatter: (d) => `${d.seriesName} · ${d.name}<br><b>${fmt(d.value, 1)} %</b> of hours inside the band` };
  o3.xAxis = { type: "value", min: 40, max: 100, ...axisStyle(p), axisLabel: { color: p.muted, formatter: "{value} %" } };
  o3.yAxis = { type: "category", data: reg.map((r) => `${r.regime}\n${r.n_hours.toLocaleString("en-US")} h`), ...axisStyle(p), axisLabel: { color: p.text2, fontSize: 12, lineHeight: 16 } };
  o3.series = [
    { name: "Elia P10–P90", type: "scatter", data: reg.map((r) => r.elia_da11_coverage), symbolSize: 12, itemStyle: { color: p.elia, borderColor: p.surface, borderWidth: 2 } },
    { name: "Penumbra Hybrid", type: "scatter", data: reg.map((r) => r.hyb_q50_coverage), symbolSize: 12, itemStyle: { color: p.pen, borderColor: p.surface, borderWidth: 2 },
      markLine: { symbol: "none", silent: true, lineStyle: { color: p.muted, type: [4, 4] }, label: { formatter: "target 80 %", position: "start", color: p.muted, fontSize: 11 }, data: [{ xAxis: 80 }] } },
  ];
  mount("chartCoverage", o3);
  legend($("#covLegend"), [["Hybrid", p.pen, "dot"], ["Elia", p.elia, "dot"]]);

  // error by hour
  const hr = R.by_hour.filter((r) => r.n_hours > 60);
  const o4 = baseOption(p);
  o4.xAxis = { type: "category", data: hr.map((r) => `${String(r.hour_utc).padStart(2, "0")}h`), ...axisStyle(p), splitLine: { show: false } };
  o4.yAxis = { type: "value", ...axisStyle(p) };
  o4.tooltip.valueFormatter = (v) => `${fmt(v, 2)} %`;
  o4.series = [
    { name: "Elia D-1 11h", type: "line", data: hr.map((r) => r.elia_da11), symbol: "none", lineStyle: { width: 2, color: p.elia }, itemStyle: { color: p.elia } },
    { name: "Penumbra Hybrid", type: "line", data: hr.map((r) => r.hyb_q50), symbol: "none", lineStyle: { width: 2, color: p.pen }, itemStyle: { color: p.pen } },
  ];
  mount("chartHour", o4);
  legend($("#hourLegend"), [["Hybrid", p.pen], ["Elia", p.elia]]);

  // tables
  const ord = ["hyb_q50", "pen_q50", "elia_da11", "linear_nwp", "climatology", "persistence"];
  $("#pointTable").innerHTML = `<thead><tr><th>Method</th><th>nMAE %</th><th>nRMSE %</th><th>MAE MW</th><th>Bias %</th><th>Skill vs Elia</th></tr></thead><tbody>` +
    ord.map((k) => pt[k]).map((r) => `<tr class="${r.key.startsWith("hyb") || r.key.startsWith("pen") ? "ours" : ""}"><td>${LABEL[r.key]}</td><td>${fmt(r.nMAE_pct_cap, 2)}</td><td>${fmt(r.nRMSE_pct_cap, 2)}</td><td>${fmt(r.MAE_MW, 0)}</td><td>${fmt(r.bias_pct_cap, 2)}</td><td>${r.key === "elia_da11" ? "—" : (r.skill_vs_elia_da11_pct > 0 ? "+" : "") + fmt(r.skill_vs_elia_da11_pct, 1) + " %"}</td></tr>`).join("") +
    `</tbody><tfoot><tr><td colspan="6" class="small">Probabilistic (80 % band): ` +
    ["hyb_q50", "pen_q50", "elia_da11"].map((k) => `${LABEL[k]} coverage ${fmt(it[k].coverage, 1)} %, width ${fmt(it[k].width, 2)} %, pinball ${fmt(it[k].mean_pinball, 3)}`).join(" · ") + `</td></tr></tfoot>`;
  const sigRows = [["hyb_q50_vs_elia_da11", "Hybrid vs Elia"], ["pen_q50_vs_elia_da11", "NWP-only vs Elia"], ["pen_q50_vs_linear_nwp", "NWP-only vs linear NWP"], ["hyb_q50_vs_persistence", "Hybrid vs persistence"]];
  $("#sigTable").innerHTML = `<thead><tr><th>Comparison</th><th>DM stat</th><th>p-value</th><th>ΔnMAE 95 % CI (pp)</th></tr></thead><tbody>` +
    sigRows.map(([k, l]) => { const s = sig[k]; return `<tr><td>${l}</td><td>${fmt(s.dm_stat, 2)}</td><td>${s.p_value < 1e-4 ? "<0.0001" : fmt(s.p_value, 4)}</td><td>[${fmt(s.mae_diff_ci95_pct_cap[0], 2)}, ${fmt(s.mae_diff_ci95_pct_cap[1], 2)}]</td></tr>`; }).join("") + "</tbody>";
  const abl = state.bt.leads["2"].ablations;
  if (abl) {
    const lab = { full_model: "Full model (8 NWP models)", abl_no_ai_model: "without ECMWF AIFS (AI model)", abl_no_market_feats: "without market features", abl_no_uncertainty_feats: "without spread / dispersion", abl_ecmwf_only: "ECMWF IFS only", abl_icon_only: "ICON only" };
    $("#ablTable").innerHTML = `<thead><tr><th>Variant (NWP only, median)</th><th>nMAE %</th><th>vs full</th></tr></thead><tbody>` +
      Object.keys(lab).filter((k) => abl[k] != null).map((k) => `<tr><td>${lab[k]}</td><td>${fmt(abl[k], 2)}</td><td>${k === "full_model" ? "—" : "+" + fmt(100 * (abl[k] / abl.full_model - 1), 1) + " %"}</td></tr>`).join("") + "</tbody>";
  }
}

function renderHero() {
  const R = state.bt.leads["2"];
  const pt = Object.fromEntries(R.point.map((r) => [r.key, r]));
  const it = Object.fromEntries(R.interval.map((r) => [r.key, r]));
  const narrower = 100 * (1 - it.hyb_q50.width / it.elia_da11.width);
  const k = [
    { v: `${fmt(narrower, 0)} %`, l: "narrower 80 % band than the grid operator's", s: `${fmt(it.hyb_q50.width, 1)} vs ${fmt(it.elia_da11.width, 1)} % of capacity` },
    { v: `${fmt(it.hyb_q50.coverage, 1)} %`, l: "of hours inside that band (target 80 %)", s: `Elia's P10–P90: ${fmt(it.elia_da11.coverage, 1)} %` },
    { v: `${fmt(pt.hyb_q50.nMAE_pct_cap, 2)} %`, l: "point error, on par with Elia", s: `Elia D-1 11h: ${fmt(pt.elia_da11.nMAE_pct_cap, 2)} % of capacity` },
    { v: `${R.n_days}`, l: "out-of-sample days, strict no-look-ahead", s: "8 weather models incl. ECMWF's AI model" },
  ];
  $("#heroKpis").innerHTML = k.map((x) => `<div class="kpi"><div class="v">${x.v}</div><div class="l">${x.l}</div><div class="s">${x.s}</div></div>`).join("");
}

// ---------- explorer ----------
function renderDay(date) {
  if (!state.days) return;
  const p = palette();
  const dates = state.days.dates;
  if (!date || !state.days.days[date]) date = dates[dates.length - 1];
  state.currentDay = date;
  $("#dayPicker").value = date;
  const d = state.days.days[date];
  const labels = d.t.map(hourLabel);
  mount("chartDay", fanOption(p, { labels, q10: d.q10, q50: d.q50, q90: d.q90, elia: d.elia, actual: d.y, penNwp: d.pen }));
  legend($("#dayLegend"), [["Hybrid P50", p.pen], ["80 % band", p.band, "band"], ["NWP-only", p.penNwp], ["Elia D-1 11h", p.elia], ["Measured", p.actual, "dot"]]);
  $("#dayTitle").textContent = `${dayLabel(date)} — hourly PV output, MW`;
  const mae = (a) => { let s = 0, n = 0; a.forEach((v, i) => { if (v != null && d.y[i] != null && d.day[i]) { s += Math.abs(v - d.y[i]); n++; } }); return n ? s / n : null; };
  const inBand = d.y.reduce((acc, v, i) => acc + (d.day[i] && v != null && v >= d.q10[i] && v <= d.q90[i] ? 1 : 0), 0);
  const nDay = d.day.filter(Boolean).length;
  const energy = (a) => a.reduce((s, v) => s + (v || 0), 0) / 1000;
  $("#dayStats").textContent = `Daylight MAE — Hybrid ${fmt(mae(d.q50), 0)} MW · NWP-only ${fmt(mae(d.pen), 0)} MW · Elia ${fmt(mae(d.elia), 0)} MW. Energy: measured ${fmt(energy(d.y), 1)} GWh, Hybrid ${fmt(energy(d.q50), 1)} GWh, Elia ${fmt(energy(d.elia), 1)} GWh. ${inBand}/${nDay} daylight hours inside the 80 % band.`;
}

function setupExplorer() {
  const dp = $("#dayPicker");
  dp.min = state.days.dates[0]; dp.max = state.days.dates[state.days.dates.length - 1];
  dp.addEventListener("change", () => renderDay(dp.value));
  $("#dayChips").innerHTML = state.days.chips.map((c) => `<button type="button" data-date="${c.date}" title="${c.date}">${c.label}</button>`).join("");
  $("#dayChips").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) renderDay(b.dataset.date); });
}

// ---------- impact ----------
function renderImpact() {
  const I = state.bt.impact;
  if (!I) return;
  $("#impactTiles").innerHTML = I.tiles.map((t) => `<div class="tile"><div class="v">${t.value}<small>${t.unit}</small></div><div class="l">${t.label}</div><div class="s">${t.sub}</div></div>`).join("");
  $("#impactNotes").textContent = I.notes;
  if (state.bt.limitations) $("#limitsLine").textContent = state.bt.limitations;
}

// ---------- boot ----------
document.querySelectorAll(".switch button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".switch button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
  state.lead = b.dataset.lead; renderBacktest();
}));

function renderAll() {
  if (state.bt) { renderHero(); renderBacktest(); renderImpact(); }
  renderTomorrow(); renderLive();
  if (state.days) renderDay(state.currentDay);
}

async function getJSON(url) { const r = await fetch(url, { cache: "no-cache" }); if (!r.ok) throw new Error(url); return r.json(); }

(async function boot() {
  const [bt, live] = await Promise.allSettled([getJSON("data/backtest.json"), getJSON("data/live/live.json")]);
  if (bt.status === "fulfilled") state.bt = bt.value;
  if (live.status === "fulfilled") state.live = live.value;
  renderAll();
  try { state.days = await getJSON("data/days.json"); setupExplorer(); renderDay(state.days.default || null); } catch (e) { console.warn(e); }
})();
