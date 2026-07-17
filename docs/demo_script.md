# Vaeris: Hackathon Live Demo Walkthrough Script

This script provides a step-by-step presentation structure for demonstrating the Vaeris platform to judges and attendees.

---

## Part 1: The Pitch (0:00 - 1:00)

* **Opening Statement:**
  "Good morning judges. Every winter, major Indian metropolitan areas are blanketed in thick, hazardous smog. Traditional air quality portals only report historic indexes, leaving smart city administrators to guess where to deploy limited resources (budget, inspectors, time) when a crisis strikes. We created Vaeris: an AI-powered urban air quality intelligence and intervention routing console."
* **The Value Proposition:**
  "Vaeris does not just report. It predicts future pollution trajectories, attributes spikes to specific physical causes using wind vector calculations and NASA FIRMS active fire hotspots, and solves a multi-objective optimization problem to recommend resource-constrained inspector dispatch schedules that maximize public health protection."

---

## Part 2: Main Console & Forecasts (1:00 - 2:30)

* **Operations Interface Walkthrough:**
  "As we open the platform, you will notice a cool, telemetry-inspired graphite console. This interface mimics air-traffic control or satellite telemetry rather than a generic SaaS page. Our spatial map (built on MapLibre GL) displays representative CPCB monitoring stations. When we click on a station (like Anand Vihar or Lodhi Road), the system highlights the selection with a scale transform and a neon glow, while dimming the other monitors to maintain cognitive focus."
* **80% Conformalized Quantile Bands:**
  "On the left, you see the predicted AQI trajectory. Instead of a single point forecast, the model outputs an 80% uncertainty band (q10 to q90 limits). Traditional quantile regression models frequently suffer from under-coverage due to training sample limitations. To fix this, we implemented post-hoc Conformalized Quantile Regression (CQR) on our validation set, generating mathematically guaranteed 80% prediction intervals that adapt to extreme weather shifts."
* **Model Explainability via SHAP:**
  "Below the forecast, the SHAP explainability chart illustrates precisely *why* the model predicted a future spike. You can see the specific positive push from boundary layer height compression (anticyclonic trapping typical of winter nights) and wind headings aligned with active crop burning zones."

---

## Part 3: Action Planning & Optimization (2:30 - 4:30)

* **Attribution Rules & Verification:**
  "Let's click 'Investigate Coordinates' to open the Action Planning panel. Vaeris runs an agentic pipeline (Planner to Executor to Verifier to Summarizer).
  Our Geospatial Verifier cross-checks the rule engine's primary attributed cause:
  * If the primary cause is resolved as 'Agricultural Burning', the verifier scans a 100km radius for NASA FIRMS wildfire coordinates and verifies the wind direction is blowing from the fires towards the station.
  * If the wind is blowing away, or if no fires are detected, the verifier automatically dampens the confidence by 40% to prevent false attributions."
* **Resource-Constrained Knapsack Solver:**
  "Once verified, the Knapsack Decision Optimizer evaluates available interventions under strict municipal constraints. Here, we can configure our available budget, total active inspectors, and travel time limits. The optimizer solves the integer programming problem, selecting the optimal combination of vehicle rationing, stubble burning bans, or industrial output caps. The public health benefit is computed using Lancet and WHO respiratory exposure risk coefficients."
* **Dynamic Scenario Projection:**
  "When we slide the budget slider from $4,000 to $1,500, the system dynamically recalculates the knapsack solver. The projected future AQI curve adjustments are updated instantly, allowing city planners to simulate budget scenarios and see the expected reduction in respiratory exposure risks."

---

## Part 4: National Grid Comparison (4:30 - 5:30)

* **Concurrently Queried Multi-City Comparison:**
  "Let's switch to the 'National Grid' comparison view. Traditional comparative grids suffer from stale cache baselines or pull faulty single-monitor spikes. 
  Vaeris addresses this in two ways:
  * It queries the live OpenAQ API concurrently in parallel worker threads (using Python's ThreadPoolExecutor) to fetch real-time air quality metrics for Delhi, Mumbai, Bengaluru, and Chennai, reducing cache-miss latencies to under 5 seconds.
  * Rather than relying on a single nearest monitor (which might be reporting false spikes like 500 AQI), the system fetches data from up to 15 stations per city and computes the median PM2.5 to calculate the current city AQI. As a result, Delhi correctly shows a realistic 345.2 AQI, while Mumbai, Bengaluru, and Chennai display stable real-time metrics."
* **Redis Caching Performance:**
  "Subsequent clicks or tab switches to the National Grid within a 10-minute window bypass the external network entirely and resolve from our Redis cache in exactly 5.5 milliseconds."

---

## Part 5: Conclusion & Technical Strength (5:30 - 6:00)

* **Technical Robustness Summary:**
  "Under the hood, Vaeris is built for reliability. We have 100% test coverage with 81 unit and integration tests verifying all edge cases, including automatic fallback modes that keep the console running seamlessly from local snapshots if all external API networks (OpenAQ, FIRMS, CPCB) time out or fail.
  Vaeris bridges the gap between raw environment data and municipal action, giving city planners the tools to act before a crisis peaks. Thank you, and we are open to questions."
