# Video script, about 3:00 (English narration)

Recording setup:
- Record the screen at 1080p with your voice over it (OBS or Loom).
- Use the live dashboard (https://s-kkipie.github.io/penumbra-solar-forecast/) in a desktop browser at 100 % zoom.
- Keep the deck `submission/Penumbra_DataNova2026.pptx` open in another window.
- Speak slowly, at about 140 words per minute. Each segment below fits its time slot.

| Time | On screen | Narration |
|---|---|---|
| 0:00–0:15 | Deck slide 1 (title) | "Hi, I'm Adrian Mamani from Arequipa, Peru. This is Penumbra, my project for DataNova's Sustainability track, problem DN-SU-01. It produces day-ahead solar forecasts that know when they're unsure." |
| 0:15–0:40 | Deck slide 2 (problem) | "Belgium's solar fleet grew from 9 to 12 gigawatts in two and a half years. The day-ahead market closes at noon the day before. Every megawatt of forecast error after that is balanced in real time, mostly by gas plants. The grid operator's own forecast still misses by about 335 megawatts on an average daylight hour, and a single number doesn't tell planners how much to trust it." |
| 0:40–1:05 | Deck slide 5 (pipeline) | "Penumbra uses only public data. It takes Elia's measured output for 11 provinces and archived forecasts from eight weather models, including ECMWF's new AI model. A LightGBM quantile model predicts P10, P50 and P90. Conformal calibration then makes sure the 80 % band really contains the outcome 80 % of the time: at dawn, at noon and at dusk. One rule matters most: no input from the future. We use weather runs issued 48 hours ahead, capacity lagged two days, and a monthly refit. The rules are unit-tested." |
| 1:05–1:40 | Dashboard → Backtest section; toggle Strict / Optimistic | "Here are 575 out-of-sample days. The Hybrid model ties the grid operator on point error: 2.88 versus 2.87 percent of capacity, a statistical tie. With fresher weather runs it is 4.6 percent better, and that difference is significant. The real win is uncertainty. Our band is 29 percent narrower than Elia's, with the same coverage. On overcast days Elia's band catches only 62 percent of hours, and ours catches 89 percent." |
| 1:40–2:05 | Dashboard → Explorer: click "Biggest gain vs Elia", then "Our worst day" | "You can open any backtest day. This one shows the band tracking a cloudy afternoon. This one is our worst day, a negative-price weekend when solar plants curtail output. It is our main limitation, and we report it next to the results instead of hiding it." |
| 2:05–2:30 | Dashboard → Tomorrow + Live track record; then GitHub commit history of `site/data/live/forecast_log.json` | "Every morning a GitHub Action issues tomorrow's forecast before the market closes. It commits the forecast to an append-only log and scores it once Elia publishes the actuals. The git history is the proof: no forecast is ever edited." |
| 2:30–2:50 | Dashboard → Impact | "What is it worth? The band is about 445 megawatts narrower for the same risk, so the operator can hold less reserve. In a simple imbalance-settlement model, error costs 7.45 euros per megawatt-hour instead of 7.71, about 3 million euros a year." |
| 2:50–3:00 | Deck slide 10 (portable) | "The weather-only version needs only free data, so it can serve grids without a professional forecaster, like Peru's southern solar region. Thanks for watching. The code and the full evaluation are on GitHub." |

## Likely judge questions (Round 2)
- **Why Belgium and not Peru?**
  - Belgium publishes the measured output and the operator's own forecast with its uncertainty band. That allows an honest benchmark against a professional system.
  - The method only needs a production history, so porting it to Peru (COES data) is the next step.
- **Isn't Hybrid just copying Elia?**
  - It learns a residual correction plus a calibrated band on top of Elia's 11:00 forecast. That forecast is public at the same moment, so the comparison is fair.
  - Its point error ties Elia's in the strict setting and beats it in the optimistic setting. Its band is 29 % narrower at the same coverage.
  - The weather-only model needs no Elia input at all.
- **How do you know there's no leakage?**
  - Weather runs are issued 48 h earlier, capacity is lagged 2 days, and prices come from the previous delivery day.
  - The backtest refits monthly, and unit tests assert that training never touches the test month.
  - The live log is append-only.
- **Why conformal prediction?**
  - It gives a finite-sample coverage guarantee.
  - Doing it per sun-elevation regime ("Mondrian") keeps coverage honest at low sun, where errors behave differently.
- **Biggest weakness?** Curtailment at negative prices, about 10 % of daylight hours. Day-ahead prices for D are published after the 11:00 cut-off, so we proxy them with yesterday's prices. A price forecast is the next step.
- **Cost to run?** Zero: GitHub Actions and GitHub Pages, with free open data.
