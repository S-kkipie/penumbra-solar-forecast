// Builds submission/Penumbra_DataNova2026.pptx from reports/*.json and site/data/*.json.
// node deck/build_deck.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const R2 = J("reports/metrics_lead2.json");
const R1 = J("reports/metrics_lead1.json");
const DQ = J("reports/data_quality.json");
const IMP = J("reports/impact.json").methods;
const DAYS = J("site/data/days.json");
const SITE_URL = process.env.SITE_URL || "https://skkippie.me/penumbra-solar-forecast/";
const REPO_URL = "https://github.com/S-kkipie/penumbra-solar-forecast";
const OUT = path.join(ROOT, "submission", "Penumbra_DataNova2026.pptx");

const pt = (R) => Object.fromEntries(R.point.map((r) => [r.key, r]));
const it = (R) => Object.fromEntries(R.interval.map((r) => [r.key, r]));
const P2 = pt(R2), P1 = pt(R1), I2 = it(R2), I1 = it(R1);
const f = (x, d = 1) => Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const sgn = (x, d = 1) => (x > 0 ? "+" : x < 0 ? "−" : "") + f(Math.abs(x), d);

const THEME = {
  name: "Penumbra",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14171C", lt1: "FFFFFF", dk2: "2B313A", lt2: "F3F4F6",
    accent1: "2A78D6", accent2: "EB6834", accent3: "EDA100", accent4: "1BAF7A", accent5: "6B7280", accent6: "D03B3B",
    hlink: "2A78D6", folHlink: "4A3AA7",
  },
};
const HEX = { ink: "14171C", ink2: "2B313A", muted: "6B7280", grid: "E5E7EB", pen: "2A78D6", elia: "EB6834", sun: "EDA100", nwp: "1BAF7A", soft: "F3F4F6", white: "FFFFFF", band: "BBD3F2" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "Penumbra — DataNova 2026";
pres.author = "Adrian Issac Mamani Quispe";
pres.subject = "DN-SU-01 Solar Energy Generation Forecasting";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const W = 13.333, M = 0.6;
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: HEX.ink },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 1.3, w: 9.8, h: 2.7, fontSize: 38, bold: true, color: C.background1, fontFace: "Cambria", valign: "top" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.25, w: 10.5, h: 1.2, fontSize: 17, color: "C9CED6", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.white },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.85, fontSize: 26, bold: true, color: C.text1, fontFace: "Cambria", valign: "middle", align: "left" }, text: "" } },
    { text: { text: "Penumbra · DataNova 2026 · DN-SU-01", options: { x: M, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: HEX.muted, align: "right" },
});

let n = 0;
const slide = (section, master = "CONTENT") => { n++; return pres.addSlide({ masterName: master, sectionTitle: section }); };
const text = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, fontFace: "Calibri", color: HEX.ink2, ...o });
const card = (s, x, y, w, h, fill = HEX.soft, name) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.12, objectName: name });
const stat = (s, x, y, w, value, label, sub, color = HEX.ink) => {
  card(s, x, y, w, 1.8, HEX.soft, `stat ${label}`);
  text(s, value, { x: x + 0.25, y: y + 0.15, w: w - 0.5, h: 0.65, fontSize: 30, bold: true, color, fontFace: "Calibri", fit: "shrink" });
  text(s, label, { x: x + 0.25, y: y + 0.82, w: w - 0.5, h: 0.5, fontSize: 13, color: HEX.ink2, valign: "top" });
  if (sub) text(s, sub, { x: x + 0.25, y: y + 1.35, w: w - 0.5, h: 0.35, fontSize: 10.5, color: HEX.muted, valign: "top" });
};
const bullets = (s, items, o) => s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
  { isTextBox: true, fontFace: "Calibri", fontSize: 15, color: HEX.ink2, paraSpaceAfter: 8, valign: "top", margin: 0, ...o });
const chartBase = { catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" },
  catAxisLineShow: true, valAxisLineShow: false, legendFontFace: "+mn-lt", legendFontSize: 11, legendColor: HEX.ink2, dataLabelFontFace: "+mn-lt" };

// 1 — Title
pres.addSection({ title: "Intro" });
let s = slide("Intro", "TITLE_DARK");
s.addText("Penumbra: day-ahead solar forecasts that know when they're unsure", { placeholder: "title" });
s.addText(`Calibrated probabilistic forecasting for Belgium's ${f(DQ.capacity_mw_last / 1000, 1)} GW PV fleet, benchmarked against the grid operator — DataNova 2026 · Sustainability · DN-SU-01`, { placeholder: "body" });
s.addShape(pres.shapes.OVAL, { x: 10.9, y: 1.0, w: 1.8, h: 1.8, fill: { color: HEX.sun }, line: { color: HEX.sun }, objectName: "sun" });
s.addShape(pres.shapes.OVAL, { x: 11.55, y: 1.0, w: 1.8, h: 1.8, fill: { color: HEX.ink }, line: { color: HEX.ink }, objectName: "shadow disc" });
text(s, "Adrian Issac Mamani Quispe · Arequipa, Peru", { x: M, y: 6.05, w: 8, h: 0.35, fontSize: 14, color: "C9CED6" });
text(s, [{ text: "Live demo: ", options: { color: "C9CED6" } }, { text: SITE_URL, options: { color: "8AB8F0", hyperlink: { url: SITE_URL } } }], { x: M, y: 6.45, w: 10, h: 0.35, fontSize: 14 });
s.addNotes("Penumbra forecasts tomorrow's Belgian solar output with calibrated uncertainty, and is scored against Elia's own operational forecast.");

// 2 — Problem
pres.addSection({ title: "Problem" });
s = slide("Problem");
s.addText("Solar is now Belgium's largest day-ahead uncertainty", { placeholder: "title" });
stat(s, M, 1.45, 3.85, `${f(DQ.capacity_mw_last / 1000, 1)} GW`, `installed PV, up from ${f(DQ.capacity_mw_first / 1000, 1)} GW`, "Elia monitored capacity, Apr 2024 → Oct 2026");
stat(s, M + 4.05, 1.45, 3.85, `${f(P2.elia_da11.MAE_MW, 0)} MW`, "average hourly error of the TSO forecast", "Elia D-1 11h, daylight hours, backtest period");
stat(s, M + 8.1, 1.45, 3.85, `${f(IMP.elia_da11.p99_overforecast_mw, 0)} MW`, "P99 shortfall to cover with reserve", "hourly over-forecast, 99th percentile");
bullets(s, [
  "Day-ahead positions close at 12:00 on D-1: every MW of forecast error is bought back in balancing, mostly from gas plants.",
  "Point forecasts hide how sure they are. Reserves and trading need honest uncertainty — wide when skies are mixed, tight when clear.",
  "Who needs it: TSOs and DSOs (reserve sizing), balance-responsible parties and aggregators (bidding), and grids in emerging solar markets that lack a TSO-grade forecaster.",
], { x: M, y: 3.55, w: W - 2 * M, h: 3.2, fontSize: 16 });
s.addNotes("The problem is DN-SU-01: forecast solar generation from weather and plant data to support grid stability and renewable planning.");

// 3 — Solution overview
pres.addSection({ title: "Solution" });
s = slide("Solution");
s.addText("Three ideas, one daily forecast", { placeholder: "title" });
const pillars = [
  ["1", "Eight weather models, not one", "ICON, GFS, ARPEGE/AROME, ECMWF IFS, HARMONIE (KNMI, DMI), GEM and ECMWF's AI model AIFS — combined per province and weighted by installed PV. Their disagreement is a feature."],
  ["2", "Bands you can trust", "LightGBM quantile regression (P10/P50/P90) + Mondrian conformal calibration per sun-elevation regime: the 80 % band covers ~80 % of hours at dawn, noon and dusk."],
  ["3", "Proven in public", "Hybrid mode also reads Elia's own 11:00 forecast (forecast combination). Every daily forecast is committed to git before market close and scored afterwards."],
];
pillars.forEach(([k, h, b], i) => {
  const x = M + i * 4.1;
  card(s, x, 1.5, 3.9, 4.9, HEX.soft, `pillar ${k}`);
  s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: 1.8, w: 0.7, h: 0.7, fill: { color: i === 1 ? HEX.pen : i === 0 ? HEX.sun : HEX.ink }, line: { color: HEX.soft }, objectName: `badge ${k}` });
  text(s, k, { x: x + 0.3, y: 1.8, w: 0.7, h: 0.7, fontSize: 22, bold: true, color: HEX.white, align: "center", valign: "middle" });
  text(s, h, { x: x + 0.3, y: 2.75, w: 3.3, h: 0.9, fontSize: 20, bold: true, color: HEX.ink, fontFace: "Cambria", valign: "top" });
  text(s, b, { x: x + 0.3, y: 3.7, w: 3.3, h: 2.5, fontSize: 15, color: HEX.ink2, valign: "top" });
});
text(s, "Everything runs on free public data and free infrastructure (GitHub Actions + GitHub Pages).", { x: M, y: 6.55, w: W - 2 * M, h: 0.35, fontSize: 13, color: HEX.muted });

// 4 — Data
pres.addSection({ title: "Data & method" });
s = slide("Data & method");
s.addText("Real, public, verifiable data — 2.5 years, hourly", { placeholder: "title" });
const rows = [
  [{ text: "Source", options: { bold: true, color: HEX.muted } }, { text: "What we use", options: { bold: true, color: HEX.muted } }, { text: "Licence", options: { bold: true, color: HEX.muted } }],
  ["Elia Open Data (ods032 / ods209 / ods210)", "Measured PV output, installed capacity, 11 provinces, 15-min; Elia's D-1 11h forecast with P10/P90", "Elia Open Data Licence"],
  ["Open-Meteo Previous Runs API", "8 NWP models archived at fixed 24 h / 48 h lead; GHI, direct, cloud, temperature at 11 provincial points", "CC BY 4.0"],
  ["Energy-Charts (Fraunhofer ISE) + Elia ods134", "Day-ahead and imbalance prices — impact analysis only, never model input", "CC BY 4.0 / Elia"],
];
s.addTable(rows, { x: M, y: 1.45, w: 7.6, colW: [2.4, 3.6, 1.6], fontFace: "Calibri", fontSize: 12, color: HEX.ink2, border: { type: "solid", pt: 0.75, color: HEX.grid }, valign: "middle", rowH: 0.62 });
stat(s, 8.6, 1.45, 4.1, `${f(DQ.hours_with_target, 0)}`, "hourly targets, none imputed", `${DQ.missing_target_pct} % missing hours dropped`);
stat(s, 8.6, 3.35, 4.1, `${f(DQ.daylight_hours, 0)}`, "daylight hours used for scoring", "sun elevation > −2°");
bullets(s, [
  "Quarter-hours → hours only when all four exist; numbers stored as text with decimal commas are parsed and validated.",
  "Radiation fields re-labelled to the interval they describe (verified: correlation peaks at zero lag).",
  "Installed capacity lagged 2 days; target = capacity factor, so 33 % fleet growth does not leak.",
], { x: M, y: 4.25, w: 7.6, h: 2.6, fontSize: 14 });

// 5 — Pipeline
s = slide("Data & method");
s.addText("Pipeline and the no-look-ahead rule", { placeholder: "title" });
const steps = [
  ["Ingest", "Elia + 8 NWP models\n11 provinces, hourly"],
  ["Features", "capacity-weighted irradiance, clear-sky index (pvlib), POA, model spread, spatial dispersion, trailing performance ratio"],
  ["Model", "LightGBM quantiles P10/P50/P90 (+ Elia 11h in Hybrid)"],
  ["Calibrate", "Mondrian conformal per sun-elevation regime, last 60 days"],
  ["Deliver", "GitHub Action 10:30 UTC → append-only log → dashboard"],
];
steps.forEach(([h, b], i) => {
  const x = M + i * 2.46;
  card(s, x, 1.55, 2.25, 2.6, i === 2 || i === 3 ? "E8F1FC" : HEX.soft, `step ${h}`);
  text(s, h, { x: x + 0.2, y: 1.7, w: 1.9, h: 0.45, fontSize: 18, bold: true, color: HEX.ink, fontFace: "Cambria" });
  text(s, b, { x: x + 0.2, y: 2.2, w: 1.9, h: 1.85, fontSize: 12.5, color: HEX.ink2, valign: "top" });
  if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: x + 2.27, y: 2.75, w: 0.17, h: 0.22, rotate: 90, fill: { color: HEX.muted }, line: { color: HEX.muted }, objectName: `arrow ${i}` });
});
card(s, M, 4.45, W - 2 * M, 2.35, HEX.soft, "rules");
text(s, "Honesty rules (unit-tested)", { x: M + 0.3, y: 4.6, w: 6, h: 0.4, fontSize: 17, bold: true, color: HEX.ink, fontFace: "Cambria" });
bullets(s, [
  "Strict setting uses weather runs issued 48 h before each hour — all available before Elia's D-1 11:00 forecast.",
  `Rolling-origin backtest: refit every month, predict the next unseen month (${R2.by_month.length} months, ${R2.n_days} days).`,
  "Every method scored on the identical set of daylight hours; significance by Diebold–Mariano + block bootstrap.",
], { x: M + 0.3, y: 5.05, w: W - 2 * M - 0.6, h: 1.7, fontSize: 14 });

// 6 — Headline results
pres.addSection({ title: "Results" });
s = slide("Results");
s.addText("Ties the grid operator on accuracy, beats it on uncertainty", { placeholder: "title" });
stat(s, M, 1.45, 3.9, `${f(P2.hyb_q50.nMAE_pct_cap, 2)} %`, `Hybrid nMAE (strict) — Elia ${f(P2.elia_da11.nMAE_pct_cap, 2)} %`, `optimistic inputs: ${f(P1.hyb_q50.nMAE_pct_cap, 2)} % vs ${f(P1.elia_da11.nMAE_pct_cap, 2)} %`, HEX.pen);
stat(s, M + 4.1, 1.45, 3.9, `${f(100 * (1 - I2.hyb_q50.width / I2.elia_da11.width), 0)} %`, "narrower 80 % band than Elia's P10–P90", `coverage ${f(I2.hyb_q50.coverage, 1)} % vs ${f(I2.elia_da11.coverage, 1)} %`, HEX.pen);
stat(s, M + 8.2, 1.45, 3.93, `${f(100 * (1 - I2.hyb_q50.winkler / I2.elia_da11.winkler), 1)} %`, "better Winkler interval score than Elia", `pinball ${f(I2.hyb_q50.mean_pinball, 3)} vs ${f(I2.elia_da11.mean_pinball, 3)}`, HEX.pen);
const order = ["persistence", "climatology", "linear_nwp", "pen_q50", "hyb_q50", "elia_da11"];
const names = { persistence: "Persistence (D-2)", climatology: "Climatology", linear_nwp: "Linear NWP", pen_q50: "Penumbra weather-only", hyb_q50: "Penumbra Hybrid", elia_da11: "Elia D-1 11h" };
s.addChart(pres.charts.BAR, [{ name: "nMAE strict", labels: order.map((k) => names[k]), values: order.map((k) => +P2[k].nMAE_pct_cap.toFixed(2)) }], {
  x: M, y: 3.45, w: 7.4, h: 3.45, barDir: "bar", ...chartBase, showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.ink2,
  dataLabelFormatCode: "0.00", showLegend: false, showTitle: true, title: "nMAE, % of installed capacity (strict, lower is better)", titleFontSize: 12, titleColor: HEX.ink2, titleFontFace: "+mn-lt",
  chartColors: order.map((k) => (k === "hyb_q50" ? HEX.pen : k === "pen_q50" ? HEX.nwp : k === "elia_da11" ? HEX.elia : "9CA3AF")), valAxisMinVal: 0, barGapWidthPct: 60,
});
bullets(s, [
  `Weather-only Penumbra, from free data alone: ${f(P2.pen_q50.nMAE_pct_cap, 2)} % (strict) / ${f(P1.pen_q50.nMAE_pct_cap, 2)} % (optimistic) — ${f(-P2.pen_q50.skill_vs_persistence_pct * -1, 0)} % better than persistence.`,
  `Hybrid vs Elia on point error: ${sgn(P2.hyb_q50.skill_vs_elia_da11_pct)} % (strict, DM p = ${R2.significance.hyb_q50_vs_elia_da11.p_value.toFixed(2)}) and ${sgn(P1.hyb_q50.skill_vs_elia_da11_pct)} % (optimistic, p = ${R1.significance.hyb_q50_vs_elia_da11.p_value.toFixed(2)}).`,
  "The gain is in uncertainty: same coverage, much tighter bands → less reserve held for the same risk.",
], { x: 8.25, y: 3.55, w: 4.5, h: 3.3, fontSize: 13.5 });

// 7 — Calibration
s = slide("Results");
s.addText("Calibration holds in every sky regime", { placeholder: "title" });
const reg = R2.by_regime;
s.addChart(pres.charts.BAR, [
  { name: "Elia P10–P90", labels: reg.map((r) => r.regime), values: reg.map((r) => +r.elia_da11_coverage.toFixed(1)) },
  { name: "Penumbra Hybrid", labels: reg.map((r) => r.regime), values: reg.map((r) => +r.hyb_q50_coverage.toFixed(1)) },
], { x: M, y: 1.4, w: 6.6, h: 4.2, barDir: "col", ...chartBase, chartColors: [HEX.elia, HEX.pen], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.ink2, dataLabelFormatCode: "0",
  showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMaxVal: 100, showTitle: true, title: "% of hours inside the 80 % band (target 80 %)", titleFontSize: 12, titleColor: HEX.ink2, titleFontFace: "+mn-lt", barGapWidthPct: 50 });
s.addChart(pres.charts.BAR, [
  { name: "Elia D-1 11h", labels: reg.map((r) => r.regime), values: reg.map((r) => +r.elia_da11.toFixed(2)) },
  { name: "Penumbra Hybrid", labels: reg.map((r) => r.regime), values: reg.map((r) => +r.hyb_q50.toFixed(2)) },
], { x: 7.35, y: 1.4, w: 5.4, h: 4.2, barDir: "col", ...chartBase, chartColors: [HEX.elia, HEX.pen], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.ink2, dataLabelFormatCode: "0.00",
  showLegend: true, legendPos: "b", valAxisMinVal: 0, showTitle: true, title: "Point error is equal: nMAE by regime, % of capacity", titleFontSize: 12, titleColor: HEX.ink2, titleFontFace: "+mn-lt", barGapWidthPct: 50 });
text(s, `Regimes are defined from the forecast clear-sky index (known in advance). Elia's band is far too narrow when overcast and too wide when the sky is mixed; conformal calibration keeps Penumbra at or above 80 % in every regime while its average band is ${f(I2.hyb_q50.width, 1)} % of capacity vs ${f(I2.elia_da11.width, 1)} %.`, { x: M, y: 5.85, w: W - 2 * M, h: 0.9, fontSize: 14, color: HEX.ink2 });

// 8 — Over time + example day
s = slide("Results");
s.addText("Stable across 19 out-of-sample months", { placeholder: "title" });
const bm = R2.by_month;
s.addChart(pres.charts.LINE, [
  { name: "Elia D-1 11h", labels: bm.map((r) => r.month), values: bm.map((r) => +r.elia_da11.toFixed(2)) },
  { name: "Penumbra weather-only", labels: bm.map((r) => r.month), values: bm.map((r) => +r.pen_q50.toFixed(2)) },
  { name: "Penumbra Hybrid", labels: bm.map((r) => r.month), values: bm.map((r) => +r.hyb_q50.toFixed(2)) },
], { x: M, y: 1.4, w: 6.3, h: 5.3, ...chartBase, chartColors: [HEX.elia, HEX.nwp, HEX.pen], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 5, showLegend: true, legendPos: "b",
  valAxisMinVal: 0, showTitle: true, title: "Monthly nMAE, % of capacity (strict)", titleFontSize: 12, titleColor: HEX.ink2, titleFontFace: "+mn-lt", catAxisLabelRotate: -45 });
const day = DAYS.days[DAYS.default];
const hrs = day.t.map((t) => new Date(t).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Brussels" }));
const keep = day.day.map((d, i) => d || (day.day[i - 1] || day.day[i + 1]));
const sel = (a) => a.filter((_, i) => keep[i]).map((v) => (v == null ? 0 : v));
s.addChart(pres.charts.LINE, [
  { name: "P10", labels: hrs.filter((_, i) => keep[i]), values: sel(day.q10) },
  { name: "P90", labels: hrs.filter((_, i) => keep[i]), values: sel(day.q90) },
  { name: "Hybrid P50", labels: hrs.filter((_, i) => keep[i]), values: sel(day.q50) },
  { name: "Elia D-1 11h", labels: hrs.filter((_, i) => keep[i]), values: sel(day.elia) },
  { name: "Measured", labels: hrs.filter((_, i) => keep[i]), values: sel(day.y) },
], { x: 7.1, y: 1.4, w: 5.65, h: 5.3, ...chartBase, chartColors: [HEX.band, HEX.band, HEX.pen, HEX.elia, HEX.ink], lineSize: 2, lineDataSymbol: "none", showLegend: true, legendPos: "b",
  valAxisMinVal: 0, showTitle: true, title: `Example: ${DAYS.default} (largest gain vs Elia), MW`, titleFontSize: 12, titleColor: HEX.ink2, titleFontFace: "+mn-lt" });

// 9 — Impact
pres.addSection({ title: "Impact" });
s = slide("Impact");
s.addText("What the improvement is worth", { placeholder: "title" });
const dEnergy = IMP.elia_da11.abs_error_gwh_per_year - IMP.hyb_q50.abs_error_gwh_per_year;
const dRes = IMP.elia_da11.p99_overforecast_mw - IMP.hyb_q50.p99_overforecast_mw;
const bandMW = ((I2.elia_da11.width - I2.hyb_q50.width) / 100) * DQ.capacity_mw_last;
stat(s, M, 1.45, 3.9, `${f(bandMW, 0)} MW`, "narrower average 80 % band", "at today's 12.1 GW, same coverage", HEX.pen);
stat(s, M + 4.1, 1.45, 3.9, `${f(IMP.hyb_q50.imbalance_cost_eur_per_mwh, 2)} €/MWh`, "imbalance cost of forecast error", `Elia's forecast: ${f(IMP.elia_da11.imbalance_cost_eur_per_mwh, 2)} €/MWh`, HEX.pen);
stat(s, M + 8.2, 1.45, 3.93, `${f(IMP.elia_da11.imbalance_cost_meur_per_year - IMP.hyb_q50.imbalance_cost_meur_per_year, 1)} M€/yr`, "lower imbalance settlement", "whole fleet, price-taker illustration", HEX.pen);
bullets(s, [
  "Reserve sizing: a TSO dimensions upward/downward reserve from forecast uncertainty — a band that is narrower at equal coverage is directly less capacity held idle (mostly gas).",
  "Trading: a balance-responsible party can bid the quantile that minimises its expected imbalance cost instead of a single number.",
  `Honest caveat: the P99 hourly over-forecast is ${f(dRes < 0 ? -dRes : dRes, 0)} MW ${dRes < 0 ? "worse" : "better"} than Elia's — concentrated in negative-price hours when PV is curtailed.`,
  "Assumptions are explicit (price-taker, hourly settlement); figures are orders of magnitude, not a market simulation.",
], { x: M, y: 3.55, w: W - 2 * M, h: 3.3, fontSize: 15 });

// 10 — Scale & feasibility
s = slide("Impact");
s.addText("Feasible today, portable tomorrow", { placeholder: "title" });
card(s, M, 1.45, 5.9, 4.4, HEX.soft, "feasibility");
text(s, "Runs in production now", { x: M + 0.3, y: 1.65, w: 5.3, h: 0.45, fontSize: 19, bold: true, color: HEX.ink, fontFace: "Cambria" });
bullets(s, [
  "Daily GitHub Action issues tomorrow's forecast at 10:30 UTC, before the 12:00 CET gate.",
  "Append-only forecast log, scored automatically when Elia publishes actuals.",
  "Static dashboard on GitHub Pages: no server, no cost, no API keys.",
  "Full backtest reproduces in ~10 minutes on a laptop (download ~15 min).",
], { x: M + 0.3, y: 2.2, w: 5.3, h: 4.3, fontSize: 14.5 });
card(s, 6.85, 1.45, 5.9, 4.4, "E8F1FC", "portability");
text(s, "Portable to data-scarce grids", { x: 7.15, y: 1.65, w: 5.3, h: 0.45, fontSize: 19, bold: true, color: HEX.ink, fontFace: "Cambria" });
bullets(s, [
  "Weather-only mode needs just a production history and free global NWP — no TSO forecast.",
  "Peru's southern solar hub (Arequipa, Moquegua, Tacna) sits under the world's highest irradiance; COES dispatch data can replace Elia's.",
  "Capacity-factor target and per-region weighting carry over to any fleet size.",
  "Next: per-province forecasts for DSOs, intraday updates, curtailment-aware features from price forecasts.",
], { x: 7.15, y: 2.2, w: 5.3, h: 4.3, fontSize: 14.5 });

// 11 — Live demo
pres.addSection({ title: "Demo" });
s = slide("Demo");
s.addText("Live dashboard and verifiable track record", { placeholder: "title" });
const shot = path.join(ROOT, "docs", "figures", "dashboard.png");
if (fs.existsSync(shot)) s.addImage({ path: shot, x: M, y: 1.4, w: 7.4, h: 5.3, sizing: { type: "contain", w: 7.4, h: 5.3 }, altText: "Penumbra dashboard screenshot" });
else card(s, M, 1.4, 7.4, 5.3, HEX.soft, "screenshot placeholder");
bullets(s, [
  "Tomorrow: fan chart with P10–P90 band next to Elia's forecast.",
  "Live record: daily error vs Elia, coverage, issue timestamps.",
  "Backtest: method comparison, monthly skill, calibration, significance tests.",
  "Explorer: any of the backtest days, with shortcuts to the hardest ones.",
], { x: 8.3, y: 1.5, w: 4.45, h: 3.6, fontSize: 14.5 });
text(s, "Demo", { x: 8.3, y: 5.2, w: 4.6, h: 0.3, fontSize: 12, bold: true, color: HEX.ink });
text(s, [{ text: SITE_URL, options: { color: HEX.pen, hyperlink: { url: SITE_URL } } }], { x: 8.3, y: 5.5, w: 4.6, h: 0.3, fontSize: 11 });
text(s, "Code", { x: 8.3, y: 5.95, w: 4.6, h: 0.3, fontSize: 12, bold: true, color: HEX.ink });
text(s, [{ text: REPO_URL, options: { color: HEX.pen, hyperlink: { url: REPO_URL } } }], { x: 8.3, y: 6.25, w: 4.6, h: 0.3, fontSize: 11 });

// 12 — Limits, responsible AI, team
pres.addSection({ title: "Close" });
s = slide("Close");
s.addText("Limits, responsible use and team", { placeholder: "title" });
card(s, M, 1.45, 5.9, 5.3, HEX.soft, "limits");
text(s, "Known limits", { x: M + 0.3, y: 1.65, w: 5.3, h: 0.45, fontSize: 19, bold: true, color: HEX.ink, fontFace: "Cambria" });
bullets(s, [
  "Target is Elia's upscaled estimate of the fleet, not metered totals.",
  "Market-driven curtailment at negative prices is only proxied (weekend/holiday flag, trailing ratio).",
  `Accuracy depends on weather-run freshness: 48 h- vs 24 h-old runs cost ${f(P2.pen_q50.nMAE_pct_cap - P1.pen_q50.nMAE_pct_cap, 1)} pp nMAE (weather-only).`,
  "National aggregate only; per-province models are future work.",
], { x: M + 0.3, y: 2.2, w: 5.3, h: 4.3, fontSize: 14.5 });
card(s, 6.85, 1.45, 5.9, 2.5, "E8F1FC", "responsible");
text(s, "Responsible data use", { x: 7.15, y: 1.65, w: 5.3, h: 0.45, fontSize: 19, bold: true, color: HEX.ink, fontFace: "Cambria" });
text(s, "Aggregate, non-personal public data under open licences; all sources credited; claims reproducible from the repo; no result is reported without its benchmark and confidence interval.", { x: 7.15, y: 2.15, w: 5.3, h: 1.7, fontSize: 14, valign: "top" });
card(s, 6.85, 4.15, 5.9, 2.6, HEX.soft, "team");
text(s, "Team", { x: 7.15, y: 4.35, w: 5.3, h: 0.45, fontSize: 19, bold: true, color: HEX.ink, fontFace: "Cambria" });
text(s, "Adrian Issac Mamani Quispe (Arequipa, Peru) — full-stack / AI engineer: problem framing, data pipeline, modelling, evaluation, live system, dashboard and documentation.", { x: 7.15, y: 4.85, w: 5.3, h: 1.7, fontSize: 14, valign: "top" });

(async () => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT, n, "slides");
})();
