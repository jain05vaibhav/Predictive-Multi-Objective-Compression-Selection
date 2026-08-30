# Predictive Multi-Objective Compression Selection — 60% Implementation Roadmap

Source: `system_architecture.pdf` (7-stage pipeline: Acquisition → Feature Extraction → State Prediction → Decision Engine → Compression → Transmission → Cloud Feedback).

**Goal of this document:** a phase-by-phase build order that gets you to a genuinely demoable 60% milestone — a real (or realistically simulated) end-to-end pipeline, not seven disconnected scripts. Each phase lists: what to build, hardware needed (if any), files/folders, the exact algorithm (inputs → logic → outputs), and a "done" checklist.

---

## 0. What "60%" means here (read this first)

Out of the 7 architecture stages, the 60% milestone target is:

| Stage | Included at 60%? | Depth |
|---|---|---|
| 1. Data Acquisition & Windowing | ✅ Full | Real sensor + simulated fallback |
| 2. Feature Extraction | ✅ Full | Entropy, variance, data-type tag |
| 3. Resource & Network State Predictor | ✅ Full | EWMA forecasting |
| 4. Multi-Objective Decision Engine | ⚠️ Partial | Scoring + error gate fully implemented. The **online bandit weight update** (θ ← θ + η·(Actual−Predicted)·context) is stubbed with logging only — real gradient learning is a post-60% phase. |
| 5. Compression Execution | ✅ Full | Real compressors, real measured metrics |
| 6. Transmission Manager | ✅ Full | Real send/buffer, tc/netem for variability |
| 7. Cloud Receiver & Feedback Loop | ⚠️ Partial | Receiver + decompression + outcome logging done. Outcome log is *stored*, not yet fed back into a live-updating θ. |

**Why this split:** stages 1–3, 5–6 and the *scoring* half of stage 4 are deterministic, testable, and demo-friendly on their own. The *learning* half of stage 4 (bandit convergence) needs many decision cycles of real data to show anything visually meaningful in a demo — attempting it before the rest of the pipeline is stable wastes review time. Building it last, after 60%, is the safer sequencing.

**Demo at 60% = ** run the pipeline live (or on a recorded run), show a dashboard/log of: incoming sensor data → computed entropy → predicted battery/bandwidth → the chosen compressor and *why* (its score vs. rejected alternatives) → actual compression ratio/energy/latency achieved → data arriving decompressed on the "cloud" (laptop) side. That is a complete, honest, working system — it just doesn't *learn* yet.

---

## 1. Recommended repo/folder structure

Create this now, before writing any code, so every phase has a home:

```
iot-compression/
├── edge/                          # Runs on Raspberry Pi (or laptop in sim mode)
│   ├── config.py                  # window size N, alpha, epsilon, weights w1-w4, sim/real toggles
│   ├── stage1_acquisition.py
│   ├── stage2_features.py
│   ├── stage3_predictor.py
│   ├── stage4_decision.py
│   ├── stage5_compression.py
│   ├── stage6_transmission.py
│   ├── sensors/
│   │   ├── dht22_reader.py
│   │   ├── camera_reader.py
│   │   ├── ina219_power.py
│   │   └── simulated_source.py    # fallback generator when hardware isn't attached
│   └── main_loop.py                # orchestrates stages 1-6 per window
├── cloud/
│   ├── receiver.py                 # Stage 7: socket/HTTP server, decompress, log
│   └── outcome_store.py            # append-only log of outcome vectors
├── shared/
│   └── compressors.py              # registry of (compressor, param) candidates used by both edge & any offline analysis
├── dashboard/
│   └── app.py                      # simple live-updating demo view (Streamlit recommended)
├── logs/
│   ├── decisions.csv
│   └── outcomes.csv
├── network_sim/
│   └── netem_profiles.sh           # tc/netem scripts for bandwidth variability
└── tests/
    └── (one test file per stage, see each phase)
```

Keep this separate from the current `veracode-agents1` content — it's an unrelated project; put it in its own directory (or its own git repo) so the two don't get tangled in commits.

---

## 2. Phase 0 — Environment & Infrastructure Setup

**Purpose:** get a working dev environment before any pipeline code, so later phases aren't blocked on tooling.

**Software infra:**
- Python 3.10+ on your laptop (primary dev target per the architecture doc: "prototype on laptop, port core logic to Pi later").
- Virtual env with: `numpy`, `scipy` (entropy/stats), `zlib`/`lzma`/`bz2` (stdlib — no install needed), `python-lz4` or `zstandard` (extra compressors), `Pillow` (image handling), `pandas` (logging/analysis), `streamlit` (dashboard), `flask` or plain `socket` (cloud receiver).
- Git repo for this project (separate from veracode-agents1).
- No cloud account is strictly required at 60% — "cloud" can be a second terminal/process on your laptop acting as the receiver (architecture doc explicitly allows "a laptop... is sufficient for prototyping").

**Hardware infra (order/acquire now, wire in Phase 1):**
- Raspberry Pi 4B (or later) + power supply + SD card (Raspberry Pi OS).
- DHT22 temperature/humidity sensor (numeric stream).
- Raspberry Pi Camera Module (image stream) — optional for 60%, see note in Phase 2.
- INA219 current/power sensor module (real energy measurement).
- USB power bank or LiPo + power management board (untethered operation).
- Jumper wires, breadboard.

**Done when:** `python -c "import numpy, scipy, PIL, streamlit"` runs clean; empty repo pushed with the folder skeleton from Section 1.

---

## 3. Phase 1 — Hardware Assembly & Wiring

**Purpose:** have real telemetry available so Stage 1/3/5 aren't measuring fictional numbers — this is what makes your energy claims credible in the demo.

**What to do:**
1. Flash Raspberry Pi OS, enable I2C (`raspi-config`) — INA219 talks over I2C.
2. Wire DHT22: data pin → a GPIO (e.g. GPIO4) with a 10kΩ pull-up resistor to 3.3V.
3. Wire INA219: VCC→3.3V, GND→GND, SDA/SCL→Pi's I2C pins. It sits **in-line with the power supply to the Pi (or a shunt load)** so it measures actual current draw during compression/transmission.
4. (Optional at 60%) Attach Camera Module via the CSI ribbon connector, enable camera in `raspi-config`.
5. Install `Adafruit_DHT` (or `adafruit-circuitpython-dht`) and `adafruit-circuitpython-ina219` libraries.
6. Write a 10-line smoke-test script per sensor that just prints one reading — confirm all three work in isolation before wiring them into the pipeline.

**If hardware isn't in hand yet:** don't block on it. Build `sensors/simulated_source.py` first (Phase 2) with a config flag `USE_REAL_HARDWARE = True/False`, and swap to real sensors the moment hardware arrives. This is the single most important decision for hitting a deadline — the whole pipeline (Stages 1–7) can be built and demoed in simulation, then hardware becomes a "bonus realism" swap-in, not a blocker.

**Done when:** each sensor smoke-test script prints a plausible live reading; INA219 shows a current draw that visibly increases when you run a CPU-heavy script.

---

## 4. Phase 2 — Stage 1: Data Acquisition & Windowing

**Purpose:** turn a continuous stream into discrete, uniformly-sized windows the rest of the pipeline can reason about.

**Algorithm:**
```
INPUT: continuous sensor stream (numeric | text/log | image), config N (window size), T_max (max wait time)
LOOP:
    buffer = []
    start_time = now()
    WHILE len(buffer) < N AND (now() - start_time) < T_max:
        sample = read_next_sample(source)
        buffer.append(sample)
    window = {
        "data": buffer,
        "data_type": tag_of(source),   # "numeric" | "text" | "image"
        "timestamp": now(),
        "window_id": incrementing counter
    }
    EMIT window to Stage 2 and hold a reference for Stage 5
```
**Data in:** raw stream from `sensors/dht22_reader.py` (numeric) or `sensors/camera_reader.py` (image), or `sensors/simulated_source.py` in sim mode.
**Data out:** a `Window` object (list of samples + type tag + id).

**60% scope:** implement for **numeric** data as the primary path (this is what the demo will center on — it's the fastest to make convincing). Image-type windowing can be a secondary demo path if the camera is wired up in time; text-type is lowest priority (mention as "supported by design, numeric is what we demo").

**Files:** `edge/stage1_acquisition.py`, `edge/sensors/*.py`.

**Test:** feed 100 simulated readings, assert you get `100/N` windows each of size `N` (except possibly the last).

**Done when:** running `stage1_acquisition.py` standalone prints a stream of `Window` objects at the expected cadence.

---

## 5. Phase 3 — Stage 2: Feature Extraction

**Purpose:** compress each window down to the handful of numbers Stage 4 actually needs to make a decision.

**Algorithm:**
```
INPUT: Window (from Stage 1)
1. Discretize window.data into buckets (for numeric: histogram with ~16-32 bins over observed range;
   for text: byte/character frequency; for image: pixel intensity histogram)
2. Compute p_i = count(bucket_i) / N for each bucket
3. H = -sum(p_i * log2(p_i)) for all p_i > 0        # Shannon entropy
4. variance = statistical variance of window.data (numeric); for image, variance of pixel values;
   rate_of_change = mean(abs(x[t] - x[t-1])) across the window
5. feature_vector = { entropy: H, variance: variance, rate_of_change: rate_of_change, data_type: window.data_type }
OUTPUT: feature_vector → Stage 4
```
**Data in:** `Window` from Stage 1.
**Data out:** `feature_vector` (entropy, variance/rate-of-change, data-type tag).

**Files:** `edge/stage2_features.py`.

**Test:** feed a constant-value window → expect entropy ≈ 0. Feed uniform random noise → expect entropy near `log2(num_buckets)`. This single test is a great demo visual too ("look, our entropy calc correctly says this repetitive sensor reading is highly compressible").

**Done when:** entropy/variance outputs match hand-calculated values on a small hardcoded example.

---

## 6. Phase 4 — Stage 3: Resource & Network State Predictor

**Purpose:** forecast *next-window* battery/CPU/bandwidth instead of reacting to stale, instantaneous readings — this is literally the "Predictive" word in the project title, so make sure the demo visibly shows a forecast vs. an actual reading side by side.

**Algorithm (EWMA, applied independently to battery %, CPU load, bandwidth):**
```
INPUT: x_t (latest measurement), x_hat_t (previous forecast), alpha (0 < alpha < 1, config)
x_hat_next = alpha * x_t + (1 - alpha) * x_hat_t
STORE x_hat_next as the new x_hat_t for the next call
OUTPUT: predicted_state = { battery: ..., cpu_load: ..., bandwidth: ... }
```
- Maintain a rolling history buffer of the last 10–20 windows' raw readings per metric (as the architecture doc specifies) — used for initialization and for later swapping EWMA for AR(1) if time permits post-60%.
- `alpha` is a tunable config value; start at `0.3` and let the demo show what happens at `0.1` vs `0.7` (higher = reacts faster/noisier) — this is an easy, legitimate "we tuned this experimentally" talking point for review.

**Data in:** rolling history of battery %, CPU load, bandwidth (from `sensors/ina219_power.py` for battery/power, `psutil` for CPU, and either real network probing or the `network_sim` tc/netem profile for bandwidth).
**Data out:** `predicted_state` dict, consumed by Stage 4.

**Files:** `edge/stage3_predictor.py`.

**Test:** feed a synthetic ramp (battery draining linearly) and confirm the EWMA forecast tracks it with a small lag.

**Done when:** predictor's forecast, plotted against actual next-window readings over ~50 windows, visibly tracks the trend (a simple matplotlib/streamlit line chart of predicted-vs-actual is a strong demo asset).

---

## 7. Phase 5 — Stage 5: Compression Execution

**Purpose:** apply the chosen compressor and measure real cost, so Stage 4's scoring has ground truth to compare its own predictions against (this closes the credibility gap that makes the "measured, not estimated" language in the architecture doc meaningful).

Build this **before** Stage 4's decision logic, even though it's numbered Stage 5 — Stage 4 needs a concrete candidate set and real measured numbers to score against, so validating Stage 5 first de-risks Stage 4.

**Candidate set (define in `shared/compressors.py`):**
| Compressor | Type | Notes |
|---|---|---|
| `zlib` (levels 1, 6, 9) | lossless, numeric/text | stdlib, fast to demo |
| `lzma`/`bz2` | lossless, numeric/text | higher ratio, higher cost — good contrast for the scoring demo |
| `delta + zlib` | lossless, numeric | domain-specific: delta-encode consecutive sensor readings first |
| JPEG at quality {30, 60, 90} | lossy, image | via Pillow — gives you a real reconstruction-error tradeoff to gate |
| "none" (passthrough) | baseline | always in the candidate set as the safe fallback Stage 4 falls back to when the error gate rejects everything else |

**Algorithm:**
```
INPUT: raw window data, decision = {compressor, parameter} from Stage 4
t0 = now(); e0 = read_power_sensor()
compressed_bytes = apply(compressor, parameter, raw_data)
t1 = now(); e1 = read_power_sensor()
ratio = len(raw_data) / len(compressed_bytes)
energy = e1 - e0                      # from INA219, or a modeled proxy (see note) in sim mode
proc_time = t1 - t0
OUTPUT: { compressed_bytes, ratio, energy, proc_time } → Stage 6, and back to Stage 4's outcome log
```
**Sim-mode energy proxy (if INA219 not yet wired):** model energy as a function of `proc_time * cpu_load_during_compression` (a rough but defensible stand-in) — clearly label this as "simulated" in the demo and switch to real INA219 readings the moment hardware is ready. Don't silently fake it.

**Files:** `edge/stage5_compression.py`, `shared/compressors.py`.

**Test:** for a known input, confirm ratio/energy/time are all computed and non-degenerate for every entry in the candidate set — this doubles as the exact table Stage 4 needs.

**Done when:** you can produce a table of "for this window, here's ratio/energy/time/error for all 8-10 candidates" — this table *is* what Stage 4 scores.

---

## 8. Phase 6 — Stage 4: Multi-Objective Decision Engine (scoring half only)

**Purpose:** the heart of the system — pick the best candidate under a hard error constraint. At 60%, weights are fixed/heuristic, not yet learned.

**Algorithm:**
```
INPUT: feature_vector (Stage 2), predicted_state (Stage 3), task_criticality flag, candidate_set with
       *estimated* ratio/energy/latency/error per candidate (see note below), epsilon (error bound), weights w1..w4

1. estimate expected error per candidate:
     - lossless compressors → error = 0 always
     - lossy (JPEG) → error = calibrated function of quality parameter (precompute a small lookup table
       from a one-time offline calibration run: compress sample images at each quality level, measure
       actual reconstruction error (e.g. MSE/SSIM vs original), store as the estimate)
2. FILTER candidates: keep only those where estimated_error <= epsilon
   - epsilon is smaller (stricter) when task_criticality is "high", larger when "routine"
   - if the filtered set is empty, fall back to the "none"/lossless-only candidates
3. FOR each surviving candidate, normalize its (ratio, energy, latency, error) estimate to 0-1 scale
   against the min/max observed across the candidate set for this window
4. Score = w1*ratio_norm - w2*energy_norm - w3*latency_norm - w4*error_norm
   - w1..w4 sum to 1; shift w2 up when predicted_state.battery is low, shift w3 up when a deadline is tight
     (start with a simple rule: if predicted_battery < 20%, w2 += 0.2 and renormalize; if deadline < X ms,
     w3 += 0.2 and renormalize)
5. decision = argmax(Score) over surviving candidates
6. transmit_or_defer = "defer" if predicted_bandwidth is below a floor AND task is not urgent, else "transmit"
OUTPUT: { compressor, parameter, transmit_or_defer } → Stage 5 (to execute) and Stage 6 (transmit flag)
```

**Important 60%-scope note:** Stage 4 needs an *estimate* of ratio/energy/latency before compression actually happens (to choose *among* candidates), but Stage 5 gives you the *actual* measured value only *after* the choice is executed. Two honest ways to handle this for the demo:
- **(a) Cheap pre-estimate:** run cheap proxies (e.g. entropy-based ratio estimate, parameter-based latency estimate) to rank candidates before picking one, OR
- **(b) Exhaustive-then-pick (simplest for 60%, still defensible):** since your candidate set is small (~8-10 options) and windows aren't huge, actually run Stage 5 on *all* candidates, then Stage 4 scores using the real measured values and picks after the fact. State this explicitly in the demo/report as the 60%-stage approach, with (a) as a named future optimization — this is honest and still demonstrates the full multi-objective/gating logic correctly.

Recommend **(b)** for 60%: it removes the need for a calibration model up front, guarantees Stage 4's scores are numerically real (a strong review talking point: "our scores use real measured tradeoffs, not guesses"), and only becomes computationally wasteful at a scale you won't hit in a demo.

**Files:** `edge/stage4_decision.py`.

**What's stubbed, not built, at 60%:** the θ update rule (`θ ← θ + η·(Actual−Predicted)·context`). Instead: log every decision's context + chosen candidate + resulting Score to `logs/decisions.csv`. This log is exactly the dataset the post-60% bandit phase will train on — you're not throwing away work, you're sequencing it.

**Files:** `edge/stage4_decision.py`, appends to `logs/decisions.csv`.

**Test:** hand-craft a scenario (low battery, tight error bound) and confirm the engine picks the expected candidate (e.g. rejects JPEG-30 for exceeding epsilon, picks the lower-energy lossless option over the higher-ratio-but-costlier one).

**Done when:** for a batch of 20+ windows with varying entropy/battery levels, the printed decisions visibly shift (e.g. more aggressive compression when battery is low) — this variability *is* the demo proof that the system is "context-aware," not hardcoded.

---

## 9. Phase 7 — Stage 6: Transmission Manager

**Purpose:** actually move bytes to the cloud endpoint, respecting the transmit/defer flag, and measure real transmission cost.

**Algorithm:**
```
INPUT: compressed_payload, transmit_or_defer flag
IF transmit_or_defer == "defer":
    append payload to local buffer_queue; return
ELSE:
    flush any queued buffer_queue items first (oldest first), then:
    t0 = now()
    send(payload, cloud_endpoint)      # simple TCP socket or HTTP POST
    t1 = now()
    latency = t1 - t0
    bandwidth_used = len(payload) / latency
OUTPUT: send confirmation + { latency, bandwidth_used } → merged into Stage 5's outcome record
```
**Network variability (per architecture doc, no extra hardware needed):** use Linux `tc`/`netem` on the receiving machine (or a Pi-to-laptop link) to simulate bandwidth caps/latency/jitter/packet loss, so you can demo the predictor and defer-logic actually reacting to degraded network — e.g. `sudo tc qdisc add dev eth0 root netem delay 200ms rate 100kbit`. Script a couple of named profiles ("good", "congested", "poor") in `network_sim/netem_profiles.sh` you can flip live during the demo for a strong visual ("watch it defer/switch strategy when I throttle the network").

**Files:** `edge/stage6_transmission.py`, `network_sim/netem_profiles.sh`.

**Done when:** you can flip a netem profile mid-run and watch defer/transmit decisions and predicted-bandwidth change accordingly.

---

## 10. Phase 8 — Stage 7 (partial): Cloud Receiver & Outcome Logging

**Purpose:** receive, decompress, and log outcomes — the other half of the loop, minus the live learning feedback.

**Algorithm:**
```
LOOP (server):
    payload, metadata = receive_from_socket()
    reconstructed_data = decompress(payload, metadata.compressor_used)
    reconstruction_error = compare(reconstructed_data, original_reference)   # only computable if you also
                                                                              # send/keep a reference for
                                                                              # error measurement in the demo
    outcome = { ratio: metadata.ratio, energy: metadata.energy, latency: metadata.latency,
                error: reconstruction_error, window_id: metadata.window_id }
    append outcome to outcomes.csv
    (60%: do NOT push outcome back into a live edge-side θ update — just store it)
    forward reconstructed_data to "downstream application" (for demo: just display it)
```
**Files:** `cloud/receiver.py`, `cloud/outcome_store.py`.

**Done when:** running `receiver.py` on your laptop while the Pi (or a second local process in sim mode) sends data shows reconstructed values on screen and appends rows to `outcomes.csv`.

---

## 11. Phase 9 — Integration & Demo Dashboard

**Purpose:** wire Phases 2–8 into one continuous loop, and give the review committee something visual instead of terminal scrollback.

**`edge/main_loop.py`:** ties Stage 1 → 2 → 3 → 4 → 5 → 6 together per window, on a timer/loop, writing to `logs/decisions.csv` each cycle.

**Dashboard (`dashboard/app.py`, Streamlit recommended for speed):** live or replay view showing, per window:
- raw sensor reading (sparkline)
- entropy/variance (numbers + trend)
- predicted vs. actual battery/bandwidth (two-line chart)
- chosen compressor + its score vs. the top 2 rejected alternatives (bar chart) — this is the single most convincing "multi-objective decision-making" visual you can show
- cumulative energy saved / average compression ratio so far
- a manual "throttle network" button wired to the netem profiles from Phase 7

**Done when:** you can run one command that starts edge loop + receiver + dashboard, and narrate a live demo end-to-end without touching code.

---

## 12. Explicitly deferred beyond 60% (don't build these yet)

- The online bandit weight-update rule (θ ← θ + η·(Actual−Predicted)·context) — currently just logged, not applied.
- AR(1) upgrade to the predictor (EWMA is sufficient and specified as acceptable at this stage).
- ESP32 microconstrained-device stretch goal.
- Full text-stream and image-stream parity with the numeric path (numeric is the demoed path; image is a bonus if time allows; text is lowest priority).
- Any cloud-hosted (non-laptop) receiver — a laptop receiver is explicitly sufficient per the architecture doc.
- Rigorous statistical evaluation / baseline comparison plots for the paper-writing phase.

Keep this list visible to your reviewer — stating clearly what's *intentionally* not done yet (and why the sequencing makes sense) reads as engineering discipline, not as a gap.

---

## 13. Suggested build order (condensed checklist)

1. [ ] Phase 0: repo + env + folder skeleton
2. [ ] Phase 1: hardware wiring (or defer, start in sim mode)
3. [ ] Phase 2: Stage 1 acquisition/windowing (numeric path)
4. [ ] Phase 3: Stage 2 feature extraction + entropy unit test
5. [ ] Phase 4: Stage 3 EWMA predictor + predicted-vs-actual chart
6. [ ] Phase 5: Stage 5 compression execution + candidate table
7. [ ] Phase 6: Stage 4 scoring + error gate (using Stage 5's real measurements, approach "b")
8. [ ] Phase 7: Stage 6 transmission + netem profiles
9. [ ] Phase 8: Stage 7 receiver + outcome logging (no live learning yet)
10. [ ] Phase 9: main_loop integration + Streamlit dashboard
11. [ ] Swap in real hardware (DHT22, INA219, camera) once wired, replacing simulated_source
12. [ ] Rehearse the live demo narrative using Section 11's dashboard
