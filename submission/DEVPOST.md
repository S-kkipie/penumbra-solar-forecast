# Devpost submission: copy-paste text

**Project name:** Penumbra

**Tagline (≤ 200 chars):** Day-ahead solar forecasts that know when they're unsure: calibrated, scored against the grid operator's own forecast, and published daily with a public, append-only track record.

**Track / problem statement:** Sustainability · DN-SU-01 Solar Energy Generation Forecasting

**Links**
- Working demo: https://skkippie.me/penumbra-solar-forecast/
- Code: https://github.com/S-kkipie/penumbra-solar-forecast
- Presentation (PPT): <paste Google Drive / OneDrive link to submission/Penumbra_DataNova2026.pptx>
- Video: <paste YouTube link>

**Built with:** python, pandas, lightgbm, scikit-learn, scipy, pvlib, numpy, pyarrow, echarts, javascript, html, css, github-actions, github-pages, open-meteo, elia-open-data, pptxgenjs

---

## Project overview
Penumbra forecasts tomorrow's hourly output of Belgium's ~12 GW solar fleet. It combines eight numerical weather models, one of them ECMWF's AI model AIFS, and gives every hour an 80 % uncertainty band. The band is calibrated with Mondrian conformal prediction, so it really contains the outcome about 80 % of the time. Penumbra is benchmarked against the forecast that Belgium's grid operator, Elia, actually uses. Each day a GitHub Action issues the next day's forecast before the day-ahead market closes, commits it to an append-only log, and later scores it against measured output.

## Problem statement
Belgian PV capacity grew from 9.1 to 12.1 GW in 2.5 years. Day-ahead positions close at 12:00 CET on D-1. Every MW of solar forecast error after that has to be balanced in real time, mostly by gas plants, and paid for at imbalance prices.

The operator's forecast already averages a 335 MW error per daylight hour. A single number also hides what reserve planners and traders most need to know: how uncertain tomorrow is. A band that is too narrow under overcast skies, or too wide in clear weather, makes the operator hold the wrong amount of reserve.

## Proposed solution & methodology
- **Data (real, public).** From Elia Open Data: quarter-hourly upscaled PV output and installed capacity for 11 provinces, plus Elia's own D-1 11:00 forecast with its P10 and P90. From Open-Meteo's Previous Runs API: archived forecasts from eight weather models, taken at a fixed lead time of 24 h or 48 h. From Energy-Charts and Elia: day-ahead and imbalance prices. Together this is 2.5 years of hourly data.
- **Features.** For each weather model, irradiance is averaged over provinces, weighted by installed PV. The other features are:
  - the mean and spread across models;
  - the clear-sky index (pvlib);
  - plane-of-array irradiance for typical roof orientations;
  - spatial dispersion across provinces;
  - solar geometry and a weekend/holiday flag;
  - a trailing 14-day performance ratio;
  - yesterday's day-ahead prices. Negative prices cause PV curtailment, and they are already public before the forecast is issued.
- **Model.** LightGBM quantile regression for P10, P50 and P90 of the capacity factor, in two variants:
  - **Weather-only** uses only free public data.
  - **Hybrid** learns a residual correction on top of Elia's 11:00 forecast, which is published at the same moment.
- **Calibration.** Split-conformal quantile regression, run separately for low, mid and high sun, on the last 60 days before each forecast month.
- **Rules against look-ahead.** These are enforced and unit-tested:
  - In the strict setting, weather runs are issued 48 h before each hour.
  - Installed capacity is lagged by 2 days.
  - Price features come only from the previous delivery day.
  - The model is refitted every month and only ever trained on the past.

## Technology stack
- **Modelling:** Python, pandas, LightGBM, scikit-learn, SciPy, pvlib.
- **Dashboard:** static HTML, CSS and JS with ECharts.
- **Infrastructure:** GitHub Actions for the daily forecast and scoring, GitHub Pages for hosting (zero servers, zero cost, no API keys).
- **Datasets:** Elia Open Data ods032/ods209/ods210/ods134, Open-Meteo Previous Runs API (ICON, GFS, ARPEGE/AROME, ECMWF IFS, ECMWF AIFS, KNMI and DMI HARMONIE, GEM), Energy-Charts day-ahead prices.
- **Presentation:** pptxgenjs.

## Implementation & demonstration
The live dashboard has five sections:
- tomorrow's fan chart next to Elia's forecast;
- the live track record;
- the full backtest: method comparison, monthly error, calibration by sky regime, error by hour, significance tests and ablations;
- an explorer for every one of the 575 backtest days, with shortcuts to the hardest days;
- an impact section.

The whole pipeline reproduces from the repository with five commands.

## Results & validation
The backtest uses a rolling origin with monthly refits. It covers 19 out-of-sample months, 575 days and 7,659 daylight hours, and every method is scored on the same hours.
- **Point accuracy.** Hybrid nMAE is **2.88 %** against **2.87 %** for Elia's operational forecast (strict inputs, Diebold–Mariano p = 0.98, so a statistical tie). With fresher 24 h inputs it is **2.74 %**, **4.6 % better** than Elia (p = 0.010). The weather-only model, using free data only, reaches 3.50 % (strict) and 3.08 % (fresh). That is 55 % better than persistence and 18 % better than a linear regression on the weather forecast.
- **Uncertainty.** The 80 % band covers **81.2 %** of hours and is **29 % narrower** than Elia's P10–P90 band, which covers 80.0 %. The Winkler interval score is **10.4 % better**. Under forecast-overcast skies Elia's band covers only 62 % of hours; Penumbra's covers 89 %.
- **Ablations.** Removing the AI weather model AIFS costs 3.0 %, and removing the market features costs 1.6 %. A single-model setup is 12–23 % worse.
- **Honest limitation.** In hours with negative prices (about 10 % of daylight hours) PV is curtailed and Penumbra over-forecasts. In all other hours the Hybrid beats Elia even with strict inputs: 2.68 % vs 2.72 %.

## Potential impact
- **Reserve headroom.** At today's capacity, the band is **≈445 MW narrower** with the same coverage, so less reserve is held for the same risk.
- **Imbalance cost.** Suppose one party scheduled the whole fleet day-ahead at the forecast and settled deviations at Elia's imbalance price. Forecast error would cost **7.45 €/MWh with Penumbra versus 7.71 €/MWh** with Elia's forecast, about **3.2 M€/yr**. This is an order-of-magnitude illustration with stated assumptions, not a market simulation.
- **Users.** TSOs and DSOs for reserve sizing, aggregators and balance-responsible parties for bidding, and planners in fast-growing solar markets.
- **Scalability.** The weather-only model needs only a production history and free global weather data. Southern Peru (Arequipa, Moquegua, Tacna), with some of the highest solar irradiance in the world, is a natural next deployment, using COES data in place of Elia's.

## Team contributions
- **Adrian Issac Mamani Quispe** (Arequipa, Peru), full-stack and AI engineer, did all of it: problem framing, the data pipeline, feature engineering, modelling and calibration, the evaluation design and statistics, the live forecasting system, the dashboard, the documentation and the presentation.

## Challenges we ran into
- **Elia's dataset change.** Elia changed its open-data schema during the project. The new datasets store numbers as text with decimal commas and contain empty placeholder rows for future hours. Without care, these hide real values.
- **Inputs that existed in time.** A fair benchmark needs weather inputs that really existed before 11:00 on D-1. We used archived forecasts at a fixed lead time instead of reanalysis.
- **Curtailment at negative prices.** It turned out to be the single largest error source. It led to the market-price features, and it is the clearest next step.

## What we learned
Matching a professional operator on point accuracy is hard. The bigger, more useful gain was in honest uncertainty: a band that is narrower and still calibrated is worth hundreds of MW of reserve.

## What's next
- Per-province forecasts for DSOs.
- Intraday updates.
- Curtailment modelled from price forecasts.
- Choosing the bid quantile to minimise imbalance cost.
- A pilot on Peru's southern solar fleet.
