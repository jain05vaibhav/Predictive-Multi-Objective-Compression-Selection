# Predictive Multi-Objective Compression Selection — 100% Implementation Roadmap & Status

**Target Architecture:** 7-Stage Adaptive Edge Pipeline with Closed-Loop Telemetry  
(Acquisition → Feature Extraction → State Prediction → Decision Engine → Compression → Transmission → Cloud Feedback).

---

## 1. What "100%" Means: Closing the Gap from 60% to Full Pipeline

At 60%, the system demonstrates an end-to-end deterministic pipeline using heuristic weights, offline logging, EWMA forecasting, numeric-only priority, and exhaustive post-execution scoring. 

The 100% milestone transforms this baseline into a **fully adaptive, closed-loop, multi-modal, learning-driven system**. It activates the online contextual bandit, closes the cloud-to-edge feedback loop, implements pre-execution cost estimation, upgrades time-series forecasting to autoregressive AR(1), expands to full image and text parity, and provides rigorous benchmarking.

### The 60% vs. 100% Stage Matrix

| Stage | 60% Milestone | 100% Complete Implementation |
|---|---|---|
| **1. Data Acquisition & Windowing** | Numeric stream only; static window size $N$. | **Multi-Modal Parity & Dynamic Windowing:** Full concurrent support for Numeric (DHT22), Image (Pi Camera), and Text/Logs. Adaptive window sizing ($N$ scales dynamically based on signal volatility and rate-of-change). |
| **2. Feature Extraction** | 1D Shannon entropy, numeric variance, data-type tag. | **Multi-Modal Feature Suite:** 2D spatial entropy & gradient variance for images; character/byte n-gram frequency & token repetition for text; cross-sensor correlation metrics for multi-channel numeric data. |
| **3. State Predictor** | 1-step EWMA forecasting for battery, CPU, and bandwidth. | **AR(1) Autoregressive + Multi-Step Horizon:** AR(1) parameter estimation tracking trends and cyclical network behavior; multi-step forecast horizons; dynamic prediction error tracking with adaptive smoothing parameters. |
| **4. Decision Engine** | Static/heuristic weights ($w_1..w_4$); approach (b) exhaustive execution of all candidates; bandit update stubbed with passive logging. | **Live Contextual Bandit & Pre-Execution Scoring:** Active online weight update ($\theta \leftarrow \theta + \eta \cdot (\text{Actual} - \text{Predicted}) \cdot \text{context}$); transition from exhaustive execution to approach (a) lightweight pre-execution cost estimators; exploration vs. exploitation policy ($\epsilon$-decay / LinUCB). |
| **5. Compression Execution** | Basic suite: zlib (1, 6, 9), lzma, bz2, delta+zlib, basic JPEG. | **Expanded High-Performance Registry & Constrained Footprints:** Addition of LZ4, Zstandard (multiple levels), Snappy; fine-grained JPEG quality spectrum; zero-copy in-memory buffer pooling; ESP32 micro-constrained memory profiling. |
| **6. Transmission Manager** | Basic TCP/HTTP send or single local buffer queue; manual netem switching. | **QoS-Aware Resilient Transmission & Priority Backlog:** Multi-tier priority queue with deadline-aware eviction; opportunistic flushing triggered by predicted network peaks; backlog coalescing and re-compression during sustained outages. |
| **7. Cloud Receiver & Feedback Loop** | Receiver decompresses and logs outcomes to static CSV; no return path to edge. | **Closed-Loop Real-Time Feedback Channel:** Bidirectional backchannel (Cloud $\rightarrow$ Edge); server computes exact reconstruction error (MSE/SSIM/bit-exact) and transmits compact feedback packets to drive edge-side online bandit weight updates. |

---

## 2. Extended Repo Structure (100% Target)

Building on the foundation repository skeleton, the following files and modules complete the 100% implementation:

```
iot-compression/
├── edge/
│   ├── config.py                      # Extended: bandit learning rate eta, epsilon schedule, AR(1) history length, memory bounds
│   ├── stage1_acquisition.py          # Dynamic windowing & multi-source support
│   ├── stage2_features.py             # Multi-modal extraction (numeric, image, text)
│   ├── stage3_predictor.py            # EWMA + AR(1) autoregressive forecasting
│   ├── stage4_decision.py             # Contextual bandit, online learner, candidate pre-estimator
│   ├── stage4_pre_estimator.py        # NEW: Approach (a) lightweight surrogate cost model for candidates
│   ├── stage4_bandit_learner.py       # NEW: Gradient update step, exploration strategy, parameter persistence
│   ├── stage5_compression.py          # Zero-copy pooling, expanded candidate set
│   ├── stage6_transmission.py         # Priority buffer, opportunistic flush, re-compression
│   ├── feedback_listener.py           # NEW: Background thread receiving feedback packets from Cloud Stage 7
│   ├── sensors/
│   │   ├── dht22_reader.py
│   │   ├── camera_reader.py           # Real camera capture with PiCamera2/V4L2
│   │   ├── rpi_system_reader.py       # Native BCM2837 SoC telemetry (temp, core volt, cpu load proxy)
│   │   ├── text_log_reader.py         # NEW: System/application log stream generator
│   │   └── simulated_source.py
│   └── main_loop.py                   # Orchestrates closed-loop live execution
├── cloud/
│   ├── receiver.py                    # Multi-threaded server with decompression and error calculation
│   ├── feedback_sender.py             # NEW: Emits telemetry feedback packets back to edge
│   ├── outcome_store.py               # SQLite/PostgreSQL storage for longitudinal analysis
│   └── error_evaluator.py             # NEW: Computes ground-truth error metrics (bit-exact, MSE, PSNR, SSIM)
├── shared/
│   ├── compressors.py                 # Full registry: zlib, lzma, bz2, lz4, zstd, delta+zlib, jpeg
│   └── protocol.py                    # NEW: Packet schema for edge-to-cloud data & cloud-to-edge feedback
├── dashboard/
│   └── app.py                         # Extended: Bandit weight convergence, live feedback latency, multi-modal views
├── benchmarks/
│   ├── run_benchmarks.py              # NEW: Automated evaluation harness against static baselines
│   ├── datasets/                      # NEW: Standard sensor, text, and image evaluation traces
│   └── plot_tradeoffs.py              # NEW: Generates Pareto frontiers, energy savings, latency distributions
├── logs/
│   ├── decisions.csv
│   ├── outcomes.csv
│   ├── feedback.csv                   # NEW: Received cloud feedback logs
│   └── bandit_weights.csv             # NEW: Evolution of theta parameters over time
├── network_sim/
│   └── netem_profiles.sh
└── tests/
    ├── test_stage1_multimodal.py
    ├── test_stage2_multimodal.py
    ├── test_stage3_ar1.py
    ├── test_stage4_bandit.py
    ├── test_stage4_pre_estimator.py
    ├── test_stage5_all_compressors.py
    ├── test_stage6_priority_queue.py
    └── test_closed_loop_feedback.py
```

---

## 3. Phase 10 — Closed-Loop Cloud-to-Edge Feedback Protocol (Stage 7 Full)

**Purpose:** Connect the cloud receiver back to the edge decision engine. At 60%, the outcome was merely logged on the receiver. At 100%, the receiver computes true ground-truth metrics and dispatches feedback packets back to the edge device, providing the necessary signal for online gradient learning.

### Feedback Architecture & Packet Protocol (`shared/protocol.py`)
1. **Edge-to-Cloud Data Packet:**
   - Header: `window_id`, `timestamp`, `data_type`, `compressor_id`, `param`, `compressed_size`, `edge_energy_uj`, `edge_latency_ms`.
   - Payload: raw compressed bytes.
   - Ground-truth reference (optional/evaluation mode): small hash or downsampled reference if verification requires it; for demo/test mode, the original uncompressed payload can be validated directly.
2. **Cloud-to-Edge Feedback Packet:**
   - Payload:
     ```json
     {
       "window_id": 1042,
       "status": "SUCCESS",
       "decompression_latency_ms": 1.45,
       "reconstruction_error": 0.0182,
       "cloud_verified_ratio": 3.84,
       "timestamp": 1729000000.12
     }
     ```

### Algorithm:
```
CLOUD RECEIVER (cloud/receiver.py + cloud/error_evaluator.py + cloud/feedback_sender.py):
1. Upon receiving packet from Edge:
     t_decomp_start = now()
     decompressed_data = decompress(packet.payload, packet.compressor_id, packet.param)
     t_decomp_end = now()
     
2. Compute Reconstruction Error:
     IF packet.data_type == "numeric" OR packet.data_type == "text":
         error = 0.0 if (decompressed_data == expected_reference) else calculate_numeric_rmse(decompressed_data, expected_reference)
     ELSE IF packet.data_type == "image":
         error = 1.0 - compute_ssim(decompressed_data, original_image_reference)   # or normalized MSE
         
3. Store outcome record into cloud database (cloud/outcome_store.py).
4. Construct feedback_packet containing { window_id, reconstruction_error, decomp_latency, ratio }.
5. Send feedback_packet back to Edge via asynchronous return socket/HTTP POST.

EDGE FEEDBACK LISTENER (edge/feedback_listener.py):
1. Runs as a background daemon thread alongside edge/main_loop.py.
2. Receives feedback_packet from Cloud.
3. Matches window_id against local pending decision record in logs/decisions.csv.
4. Emits resolved (Context, Action, Actual Outcome) tuple to Stage 4 Bandit Learner (Phase 11).
```

- **Data in:** Compressed stream from Stage 6; reference data for validation.
- **Data out:** Structured feedback packet transmitted across network to Edge `feedback_listener.py`.
- **Files:** `cloud/receiver.py`, `cloud/feedback_sender.py`, `cloud/error_evaluator.py`, `edge/feedback_listener.py`, `shared/protocol.py`.
- **Test:** Run `tests/test_closed_loop_feedback.py`: Edge emits compressed packet; cloud decompresses, evaluates error, returns feedback within <50ms; Edge listener catches and parses packet without dropped IDs.
- **Done when:** The edge process prints: `[Feedback Received] Window 42: Cloud confirmed error=0.000, ratio=3.41, round-trip=18ms`.

---

## 4. Phase 11 — Stage 4 Full: Online Contextual Bandit & Dynamic Learning Engine

**Purpose:** Move from static heuristic scoring and exhaustive candidate execution (approach b) to an intelligent, self-updating online decision engine with lightweight pre-execution estimation (approach a).

### Sub-Phase 11A: Transitioning from Exhaustive Execution (b) to Pre-Execution Estimation (a)
At 60%, Stage 5 compressed using all 8–10 candidates per window to find real numbers. At 100%, this is computationally prohibitive on constrained edge devices.
We introduce `edge/stage4_pre_estimator.py`:
- Uses feature vector (entropy $H$, variance $\sigma^2$, data length $L$) to predict expected $(Ratio, Energy, Latency, Error)$ for each candidate *before* compression:
  $$\widehat{Ratio}_c = f_c(H, \text{data\_type})$$
  $$\widehat{Latency}_c = g_c(H, L, \text{CPU\_load})$$
  $$\widehat{Energy}_c = h_c(\widehat{Latency}_c, \text{CPU\_load})$$
  $$\widehat{Error}_c = 0 \text{ (for lossless)}, \quad \widehat{Error}_c = \text{LUT}_{\text{calibrated}}(q) \text{ (for lossy)}$$
- The estimators $f_c, g_c, h_c$ are lightweight linear/polynomial surrogate models calibrated during initial bootstrap and continuously refined via online feedback.

### Sub-Phase 11B: The Online Contextual Bandit Algorithm
The decision engine maintains a parameter vector $\boldsymbol{\theta}_c$ for each compressor candidate $c$ (or a shared multi-objective weight matrix):

```
CONTEXT VECTOR x_t:
x_t = [ 1.0, 
        normalized(entropy), 
        normalized(variance), 
        normalized(predicted_battery), 
        normalized(predicted_cpu), 
        normalized(predicted_bandwidth), 
        task_criticality_flag ]

PRE-EXECUTION SCORING & GATING:
1. Candidate Filtering (Hard Error Gate):
     Keep candidates where Estimated_Error_c <= epsilon(task_criticality)
     If empty, fallback to candidate "none" or "zlib-level-6".

2. Multi-Objective Score Formulation:
     Predicted_Score_c = (theta_ratio · Ratio_c) - (theta_energy · Energy_c) - (theta_latency · Latency_c) - (theta_error · Error_c)
     
3. Exploration vs. Exploitation Strategy:
     With probability epsilon_t:
         Pick randomly from valid candidates (Exploration)
     Else:
         Pick candidate c* = argmax_c (Predicted_Score_c) (Exploitation)
     *Optionally use LinUCB: Score_c = x_t^T theta_c + alpha * sqrt(x_t^T A_c^-1 x_t)
     Decay exploration: epsilon_t = max(epsilon_min, epsilon_0 * (decay_factor)^t)

4. Execute candidate c* ONLY via Stage 5.

ONLINE PARAMETER UPDATE (Upon receiving Cloud Feedback):
When actual outcome arrives from Phase 10:
Actual_Reward = w1*Actual_Ratio - w2*Actual_Energy - w3*Actual_Latency - w4*Actual_Error
Prediction_Error = Actual_Reward - Predicted_Score_c*

Gradient Update:
theta_c* <-- theta_c* + eta · Prediction_Error · x_t

Guardrails:
- Clip theta parameters to positive domain [theta_min, theta_max] to prevent runaway divergence.
- If Prediction_Error exceeds safety threshold for 3 consecutive windows, fallback to robust conservative defaults.
```

- **Data in:** `feature_vector` (Stage 2), `predicted_state` (Stage 3), incoming cloud feedback (Phase 10).
- **Data out:** Single chosen `{compressor, parameter, transmit_or_defer}`; continuously updated weight parameters saved to `logs/bandit_weights.csv`.
- **Files:** `edge/stage4_decision.py`, `edge/stage4_pre_estimator.py`, `edge/stage4_bandit_learner.py`.
- **Test:** Run `tests/test_stage4_bandit.py`: Feed 200 synthetic windows where bandwidth drops suddenly. Verify that:
  1. The bandit shifts candidate selection from bandwidth-heavy to ratio-maximizing algorithms.
  2. Weights $\boldsymbol{\theta}$ converge smoothly without oscillating or exploding.
  3. Pre-execution estimate error drops below 10% relative error after 50 warm-up windows.
- **Done when:** The dashboard exhibits live convergence plots of $\boldsymbol{\theta}$ adapting in real time to fluctuating battery and network conditions.

---

## 5. Phase 12 — Stage 3 Full: Autoregressive AR(1) & Multi-Step Horizon State Predictor

**Purpose:** Replace pure EWMA smoothing with an Autoregressive AR(1) model with trend estimation, enabling the pipeline to anticipate impending resource exhaustion or network drops rather than lagging behind them.

### Algorithm (AR(1) with Rolling Parameter Estimation):
```
INPUT: Rolling historical buffer of length M (e.g., M = 20) for metric x in {battery_level, cpu_load, bandwidth}

1. Parameter Estimation via Rolling Least Squares:
     Given history [x_{t-M+1}, ..., x_t]:
     Compute empirical mean mu = mean(x)
     Compute lag-1 autocorrelation:
         phi = sum((x_i - mu) * (x_{i-1} - mu)) / sum((x_{i-1} - mu)^2)
     Clamp phi to (-0.95, 0.95) to ensure stationarity.
     c = mu * (1 - phi)

2. 1-Step-Ahead Forecast:
     x_hat_{t+1} = c + phi * x_t

3. Multi-Step-Ahead Horizon (k-step forecast, k in {1, 2, 3}):
     x_hat_{t+k} = mu + (phi^k) * (x_t - mu)

4. Hybrid Fallback Rule:
     If sample variance of history is below noise threshold:
         Use EWMA forecast: x_hat = alpha * x_t + (1 - alpha) * x_hat_{t-1}
     Else:
         Use AR(1) forecast.

OUTPUT: predicted_state = { 
    battery: { step_1: ..., step_2: ... },
    cpu_load: { step_1: ..., step_2: ... },
    bandwidth: { step_1: ..., step_2: ... },
    volatility: empirical_variance 
}
```

- **Data in:** Real-time system readings from `sensors/rpi_system_reader.py` (BCM2837 SoC voltage/frequency/temp), `psutil`, and network transmission speeds.
- **Data out:** Multi-step `predicted_state` dictionary with trend indicators.
- **Files:** `edge/stage3_predictor.py`, `tests/test_stage3_ar1.py`.
- **Test:** Synthetic sinusoidal bandwidth trace and linear battery depletion ramp. Verify that AR(1) predicts turns and drops with lower Mean Absolute Error (MAE) than EWMA.
- **Done when:** Plotted side-by-side on the dashboard, AR(1) shows a 25%+ reduction in one-step prediction lag compared to EWMA during network phase changes.

---

## 6. Phase 13 — Multi-Modal Stream Parity (Stages 1 & 2 Full for Image and Text)

**Purpose:** Expand Stages 1 and 2 from numeric-only into full multi-modal pipelines running concurrently or interchangeably.

### Sub-Phase 13A: Real Image Stream Pipeline
1. **Acquisition (`sensors/camera_reader.py`):**
   - Connects to Raspberry Pi Camera Module (via `libcamera` / `picamera2` / OpenCV V4L2) or synthetic frame generator.
   - Captures raw image frames (RGB / Grayscale / YUV).
   - Windowing: Single-frame window or multi-frame burst window.
2. **Feature Extraction (`stage2_features.py`):**
   - **2D Shannon Entropy:** Calculated over 256-bin intensity histogram:
     $$H_{\text{img}} = -\sum_{k=0}^{255} p_k \log_2(p_k)$$
   - **Spatial Gradient Variance:** Compute Laplacian or Sobel gradient variance:
     $$\sigma_{\text{spatial}}^2 = \text{Var}(\nabla^2 I)$$
     (High variance indicates high detail/edges, predicting poor compression ratio for aggressive lossless algorithms).
   - **Reconstruction Sensitivity Tag:** High for mission-critical object/edge detection; normal for routine background telemetry.

### Sub-Phase 13B: Text and Log Stream Pipeline
1. **Acquisition (`sensors/text_log_reader.py`):**
   - Streams syslog, application logs, or text buffer strings.
   - Windowing: Accumulates $N$ lines or byte blocks up to $T_{\max}$.
2. **Feature Extraction (`stage2_features.py`):**
   - **Byte-Level Entropy:** Shannon entropy across 256 byte values.
   - **Lexical Repetition Index:** Ratio of unique 4-gram tokens to total tokens (indicates applicability of dictionary-based compressors like zlib/lz4 vs. entropy coders).
   - **ASCII/Binary Ratio:** Fraction of printable characters.

### Sub-Phase 13C: Dynamic Window Sizing ($N_{\text{adaptive}}$)
Instead of a fixed window size $N$, Stage 1 dynamically modulates $N$ based on previous window entropy and rate of change:
- When rate of change is low (steady state), increase $N \rightarrow 2N$ to maximize compression ratio.
- When rate of change is high (transient event or anomaly), decrease $N \rightarrow N / 2$ to reduce decision latency and preserve responsiveness.

- **Data in:** Live camera frames, syslog stream, DHT22 readings.
- **Data out:** Polymorphic `Window` objects and rich `feature_vector` dictionaries with modal-specific metrics.
- **Files:** `edge/stage1_acquisition.py`, `edge/stage2_features.py`, `edge/sensors/camera_reader.py`, `edge/sensors/text_log_reader.py`.
- **Test:** Run `tests/test_stage1_multimodal.py` and `tests/test_stage2_multimodal.py`: verify that text, image, and numeric windows produce valid feature vectors and that dynamic windowing shrinks on sudden entropy spikes.
- **Done when:** The system seamlessly switches between processing a DHT22 burst, a log snippet, and a camera snapshot in the same execution loop without crashing or type errors.

---

## 7. Phase 14 — Expanded Candidate Compressor Registry & Hardware Optimization (Stage 5 Full)

**Purpose:** Equip Stage 5 with a comprehensive suite of modern edge-viable compression algorithms and optimize execution for memory-constrained platforms.

### Candidate Matrix (`shared/compressors.py`):

| Algorithm | Category | Config Options | Target Modality | Key Trade-off Character |
|---|---|---|---|---|
| `passthrough` ("none") | Raw | None | All | Zero CPU/energy, max bandwidth |
| `zlib` | Lossless | Levels: 1, 6, 9 | Numeric, Text | Balanced baseline, widely compatible |
| `lz4` | Lossless | Fast / High Compression | Numeric, Text | Ultra-fast execution, modest ratio |
| `zstandard` (`zstd`) | Lossless | Levels: 1, 3, 15 | Numeric, Text | Superior Pareto frontier of ratio vs. speed |
| `bz2` | Lossless | Level 9 | Text | High ratio, high CPU/energy penalty |
| `lzma` | Lossless | Preset 6 | Numeric, Text | Maximum ratio, extreme latency/energy cost |
| `delta + zlib` | Lossless | 1st-order delta | Numeric | High ratio on autocorrelated sensor telemetry |
| `delta + zstd` | Lossless | 1st-order delta | Numeric | Optimal ratio & energy on numeric streams |
| `jpeg` | Lossy | Quality: 20, 50, 75, 90 | Image | Wide range of tunable error vs. size |
| `lossy_numeric_quant` | Lossy | Precision: 0.1, 0.01 | Numeric | Quantizes sensor floats before entropy coding |

### Edge Hardware Optimization:
1. **Zero-Copy In-Memory Buffer Pooling:**
   - Pre-allocate reusable memory buffers for compression staging, preventing heap fragmentation and garbage collection pauses on the Pi.
2. **ESP32 & Micro-Constrained Device Feasibility Profile:**
   - Profile memory ceiling: ensure working RAM stays under 64 KB for numeric compression pipelines.
   - Replace floating-point Shannon entropy calculations with integer/fixed-point bitwise approximations when running under constrained emulation modes.

- **Files:** `shared/compressors.py`, `edge/stage5_compression.py`, `tests/test_stage5_all_compressors.py`.
- **Test:** Verify every compressor entry against corner-case inputs: empty buffer, constant array, random uniform noise, 4K byte log string, 640x480 test image.
- **Done when:** A fully populated benchmark table displays measured ratio, throughput (MB/s), energy ($\mu\text{J}/\text{byte}$), and error for all 10+ candidates.

---

## 8. Phase 15 — Stage 6 Full: QoS-Aware Resilient Transmission & Priority Backlog

**Purpose:** Upgrade the basic transmission manager into an intelligent, QoS-aware network dispatcher that can queue, prioritize, coalesce, and opportunistically flush data under severe network volatility.

### Algorithm & Queue Architecture:
```
QUEUE SYSTEM:
- Priority Queue with 3 tiers:
    Tier 0: Urgent / Critical (error-intolerant, anomaly detections)
    Tier 1: Routine Telemetry (normal operational windows)
    Tier 2: Background / Bulk (historical archives, low-priority logs)

LOGIC PER CYCLE (edge/stage6_transmission.py):
1. Ingest { compressed_payload, metadata, task_criticality }:
     Assign priority tier based on task_criticality.
     Enforce buffer memory ceiling (e.g., max 50 MB):
         If queue full: evict lowest priority, oldest non-critical item.

2. Transmission Decision Logic:
     predicted_bw = Stage3.predict_bandwidth()
     
     IF transmit_or_defer == "defer":
         Enqueue payload into corresponding Priority Queue tier.
     ELSE:
         # Opportunistic flush condition:
         # If network condition is "good" or predicted to deteriorate soon:
         # Drain queued items in priority order.
         WHILE Queue.has_items() AND estimated_send_time < window_deadline:
             item = Queue.pop_highest_priority()
             send_result = socket_send(item)
             IF send_result.failed:
                 Queue.re_insert_front(item)
                 BREAK (enter backoff)
                 
3. Backlog Coalescing (During Sustained Outages):
     If Tier 1 backlog exceeds K windows of identical sensor type:
         Merge consecutive windows and re-compress with high-ratio algorithm (zstd-15 / lzma)
         to reclaim buffer memory while waiting for connectivity restoration.
```

- **Files:** `edge/stage6_transmission.py`, `tests/test_stage6_priority_queue.py`.
- **Test:** Simulate a 30-second network blackout via `tc/netem`, followed by a 10-second high-bandwidth window.
- **Done when:** The system queues routine data during the blackout without packet dropping, protects Tier 0 urgent packets, and opportunistically drains the backlog once network recovers.

---

## 9. Phase 16 — Production Deployment & Scalable Storage

**Purpose:** Move the cloud receiver from a prototype laptop script into a persistent, production-ready server capable of handling sustained streams, logging metrics to an ACID database, and hosting an executive live dashboard.

### Implementation:
1. **Persistent Database (`cloud/outcome_store.py`):**
   - SQLite (local/embedded) or PostgreSQL (remote server) schema:
     - `windows`: `(window_id, timestamp, data_type, raw_size, compressed_size, ratio)`
     - `decisions`: `(window_id, chosen_compressor, param, predicted_score, score_alternatives)`
     - `telemetry`: `(window_id, energy_microjoules, edge_latency_ms, cloud_latency_ms, reconstruction_error)`
     - `bandit_history`: `(iteration, theta_vector, prediction_error, reward)`
2. **Decoupled Asynchronous Receiver Service (`cloud/receiver.py`):**
   - Implemented via non-blocking asynchronous socket server (`asyncio`) or HTTP API (`FastAPI` / `Uvicorn`).
   - Thread pool for decompression workers to isolate network reception from compute-intensive decompression.
3. **Daemonization:**
   - Systemd unit files or Docker container setup for persistent 24/7 background operation.

- **Files:** `cloud/receiver.py`, `cloud/outcome_store.py`, `cloud/db.py`, `cloud/Dockerfile`.
- **Test:** Stress-test receiver with 10,000 back-to-back synthetic windows across multiple concurrent client sessions; verify zero dropped records and database integrity.
- **Done when:** The receiver operates continuously as a headless service, appending to the database and serving real-time queries to the dashboard.

---

## 10. Phase 17 — Comprehensive Benchmark Suite & Statistical Evaluation

**Purpose:** Provide the empirical proof required to defend the system. Implement automated benchmarking against static and heuristic baselines across diverse realistic workloads.

### Benchmark Harness (`benchmarks/run_benchmarks.py`):
Compare the **Adaptive Multi-Objective Bandit Pipeline** against 4 competitor baselines under identical simulated network/battery conditions:
1. **Baseline 1: Static Passthrough** (No compression, raw transmission).
2. **Baseline 2: Static Fast Lossless** (Always LZ4 / zlib-1).
3. **Baseline 3: Static High-Ratio Lossless** (Always zstd-15 / lzma).
4. **Baseline 4: Fixed Heuristic / Rule-Based** (Hand-crafted if-else logic without learning).

### Automated Evaluation Metrics (`benchmarks/plot_tradeoffs.py`):
- **Pareto Optimality Curve:** Plot Compression Ratio vs. Energy Consumed per Byte.
- **Deadline Adherence Rate:** Percentage of windows transmitted before latency deadline.
- **Reconstruction Error vs. Budget Trade-off:** PSNR/SSIM across image quality levels.
- **Battery Life Extension:** Cumulative energy savings translated into estimated device runtime hours.
- **Online Learning Convergence Curve:** Evolution of regret and prediction error over 1,000 continuous windows.

- **Files:** `benchmarks/run_benchmarks.py`, `benchmarks/plot_tradeoffs.py`, `benchmarks/datasets/*.csv`.
- **Test:** Run full benchmark suite on recorded traces; generate publication-quality evaluation plots in `logs/benchmark_results/`.
- **Done when:** The script outputs final comparative summary tables and Pareto plots verifying that the adaptive bandit achieves superior multi-objective trade-offs compared to all four static baselines.

---

## 11. Full 100% Comprehensive Build Checklist & Execution Order

This checklist covers the complete path from Phase 0 to Phase 17:

### Foundation & 60% Milestone (Phases 0–9)
- [ ] **Phase 0:** Dev environment, virtualenv, repo skeleton (`edge/`, `cloud/`, `shared/`, `dashboard/`).
- [ ] **Phase 1:** Hardware wiring (Pi board, DHT22, Camera) and native BCM2837 SoC telemetry (`rpi_system_reader.py`), or fallback to `sensors/simulated_source.py`.
- [ ] **Phase 2:** Stage 1 Acquisition & Windowing (numeric path, fixed $N$).
- [ ] **Phase 3:** Stage 2 Feature Extraction (Shannon entropy, numeric variance).
- [ ] **Phase 4:** Stage 3 State Predictor (1-step EWMA forecasting).
- [ ] **Phase 5:** Stage 5 Compression Execution (basic candidates: zlib, lzma, bz2, delta+zlib, jpeg).
- [ ] **Phase 6:** Stage 4 Decision Engine (heuristic scoring + error gate, exhaustive approach "b", logging only).
- [ ] **Phase 7:** Stage 6 Transmission Manager (socket transmission + `tc/netem` network variability).
- [ ] **Phase 8:** Stage 7 Cloud Receiver (decompression + append-only CSV outcome logging).
- [ ] **Phase 9:** Integration & Demo Dashboard (`edge/main_loop.py` + Streamlit dashboard).

### Advanced 100% Production Milestone (Phases 10–17)
- [ ] **Phase 10:** Closed-Loop Cloud-to-Edge Feedback Protocol (Stage 7 Full)
  - [ ] Implement `shared/protocol.py` for structured data and feedback packets.
  - [ ] Add `cloud/error_evaluator.py` for ground-truth MSE/SSIM/bit-exact error calculations.
  - [ ] Implement `cloud/feedback_sender.py` to transmit feedback back to edge.
  - [ ] Add `edge/feedback_listener.py` background thread to receive feedback.
- [ ] **Phase 11:** Stage 4 Full: Online Contextual Bandit & Dynamic Learning Engine
  - [ ] Build `edge/stage4_pre_estimator.py` (approach "a" surrogate cost model to replace exhaustive execution).
  - [ ] Implement `edge/stage4_bandit_learner.py` with online gradient update: $\boldsymbol{\theta} \leftarrow \boldsymbol{\theta} + \eta \cdot (R_{\text{actual}} - R_{\text{predicted}}) \cdot \mathbf{x}$.
  - [ ] Implement exploration-exploitation policy ($\epsilon$-greedy decay / LinUCB).
  - [ ] Add parameter guardrails and persist weights to `logs/bandit_weights.csv`.
- [ ] **Phase 12:** Stage 3 Full: Autoregressive AR(1) & Multi-Step Predictor
  - [ ] Implement AR(1) parameter estimation with rolling least squares in `edge/stage3_predictor.py`.
  - [ ] Add multi-step ahead forecast horizons for battery and bandwidth.
  - [ ] Implement hybrid EWMA-AR(1) fallback based on signal volatility.
- [ ] **Phase 13:** Multi-Modal Stream Parity (Stages 1 & 2 Full)
  - [ ] Implement `edge/sensors/camera_reader.py` and 2D spatial entropy / gradient variance in `edge/stage2_features.py`.
  - [ ] Implement `edge/sensors/text_log_reader.py` with byte entropy and lexical repetition metrics.
  - [ ] Implement dynamic window sizing ($N_{\text{adaptive}}$) driven by rate-of-change and entropy.
- [ ] **Phase 14:** Expanded Candidate Registry & Hardware Optimization (Stage 5 Full)
  - [ ] Integrate LZ4, Zstandard (levels 1, 3, 15), Snappy, and lossy numeric quantization in `shared/compressors.py`.
  - [ ] Implement zero-copy buffer pooling in `edge/stage5_compression.py`.
  - [ ] Profile memory footprint under ESP32 / micro-constrained hardware budgets.
- [ ] **Phase 15:** Stage 6 Full: QoS-Aware Resilient Transmission & Priority Backlog
  - [ ] Implement multi-tier priority queue (Tier 0 Urgent, Tier 1 Routine, Tier 2 Bulk) in `edge/stage6_transmission.py`.
  - [ ] Implement opportunistic backlog flushing triggered by predicted network surges.
  - [ ] Add backlog coalescing and re-compression during prolonged outages.
- [ ] **Phase 16:** Production Cloud Deployment & Scalable Storage
  - [ ] Implement ACID database storage (SQLite / PostgreSQL) in `cloud/outcome_store.py`.
  - [ ] Deploy asynchronous worker-pooled receiver in `cloud/receiver.py`.
  - [ ] Containerize cloud receiver with Docker and systemd unit configuration.
- [ ] **Phase 17:** Comprehensive Benchmark Suite & Statistical Evaluation
  - [ ] Create automated benchmark harness `benchmarks/run_benchmarks.py` comparing against 4 baselines.
  - [ ] Generate Pareto curves, cumulative energy savings, and learning convergence plots with `benchmarks/plot_tradeoffs.py`.
  - [ ] Verify full closed-loop convergence over 1,000+ continuous multi-modal cycles.

---

## 12. Current Implementation Status & Actionable Work Checklist

### Summary of Current Project Health
- **Total Automated Tests Passing:** 71 / 71 tests passing (`pytest` verified).
- **Core Pipeline Status:** End-to-end closed-loop execution is functional from sensor acquisition through cloud decompression and TCP feedback return.
- **Power Modeling:** Hardware-grounded BCM2837 SoC energy model (`vcgencmd` voltage/temp + `psutil` load) active without external INA219.

---

### Phase A: Work Completed Till Now (`[x]` Done)

#### 1. Hardware Ingestion & Sensors
- [x] **DHT22 Ingestion:** Real GPIO4 temperature and humidity polling with software retry and simulated fallback (`edge/sensors/dht22_reader.py`).
- [x] **RPi Camera Module:** CSI camera still frame capture via PiCamera2 / V4L2 with disk and memory buffers (`edge/sensors/camera_reader.py`).
- [x] **BCM2837 SoC Telemetry:** Real-time hardware register polling via `vcgencmd` for core temp, core voltage, clock frequency, and throttling bits (`edge/sensors/rpi_system_reader.py`).
- [x] **Simulated Telemetry Fallback:** Realistic synthetic generator for zero-hardware headless environments (`edge/sensors/simulated_source.py`).

#### 2. Pipeline Stages 1 & 2 (Acquisition & Feature Extraction)
- [x] **Stage 1 Dynamic Windowing:** Window object packaging, sample buffering, window ID tracking, and byte serialization `window.to_bytes()` (`edge/stage1_acquisition.py`).
- [x] **Stage 2 Shannon Entropy:** 1D Shannon entropy ($H$) calculation over discretized histogram buckets (`edge/stage2_features.py`).
- [x] **Stage 2 Statistical Profiling:** Variance ($\sigma^2$), Rate of Change (RoC), min, max, and mean extraction (`edge/stage2_features.py`).

#### 3. Pipeline Stage 3 (Resource & State Forecasting)
- [x] **EWMA State Predictor:** Exponentially weighted moving average ($\alpha = 0.3$) for CPU load, CPU temperature, and network bandwidth (`edge/stage3_predictor.py`).
- [x] **Holt's Linear Trend Extrapolation:** Two-parameter trend forecasting ($\beta = 0.2$) predicting thermal ramp and network drops (`edge/stage3_predictor.py`).
- [x] **Thermal Headroom & Throttling Risk:** Active headroom calculation before BCM2837 thermal throttling thresholds (`edge/stage3_predictor.py`).

#### 4. Pipeline Stages 4 & 5 (Profiling, Gating & Decision Engine)
- [x] **Hardware Profiler Stage:** Empirical calibration tables mapping data characteristics to codec performance (`edge/stage4_profiler.py`).
- [x] **Rule-Based Safety Gate:** Hard error bound filtering ($\epsilon = 0.0$ for critical data, $\epsilon = 0.05$ for routine telemetry) eliminating invalid candidates (`edge/stage5_decision.py`).
- [x] **Multi-Objective Pareto Scoring:** Composite utility formulation ($w_1 \cdot \text{Ratio} - w_2 \cdot \text{Energy} - w_3 \cdot \text{Latency}$) with dynamic thermal/bandwidth weight adaptation (`edge/stage5_decision.py`).
- [x] **Online Contextual Bandit:** Real gradient weight update step $\theta_c \leftarrow \theta_c + \eta \cdot (R_{\text{actual}} - R_{\text{predicted}}) \cdot \mathbf{x}$ updating decision policy from cloud feedback (`edge/stage5_decision.py`).

#### 5. Pipeline Stage 6 (Compression Execution)
- [x] **Multi-Codec Lossless Execution:** Real compression execution using LZ4, Zstandard (zstd), Gzip/zlib, Bzip2, Delta+Zlib, and Passthrough (`edge/stage6_compression.py`).
- [x] **SoC Physics-Grounded Energy Model:** High-precision execution timing calculating energy consumption via $\text{Energy } (\mu\text{J}) = \text{Power } (\text{mW}) \times \text{Execution Time } (\text{ms})$ (`edge/stage6_compression.py`).
- [x] **Local Error Self-Verification:** Edge-side verification measuring reconstruction distortion before dispatch (`edge/stage6_compression.py`).

#### 6. Pipeline Stages 7 & 8 (Network Transmission & Cloud Receiver)
- [x] **Transmission Manager & Deferral Queue:** 4-byte framed TCP streaming with RAM deferral queue during simulated network degradation (`edge/stage7_radio.py`, `edge/stage6_transmission.py`).
- [x] **Cloud Ingestion Server:** Multi-client TCP socket server on port 8765/8799 (`cloud/receiver.py`).
- [x] **Lossless Cloud Verification:** Ingestion decompression, payload hash/integrity verification, and outcome logging to `logs/outcomes.csv` (`cloud/receiver.py`, `cloud/outcome_store.py`).
- [x] **Bidirectional Closed-Loop Feedback:** TCP ACK packet returning verified ratio, decompression latency, and error back to edge node (`cloud/receiver.py`, `tests/test_closed_loop_feedback.py`).

#### 7. System Orchestration & Testing
- [x] **Main Loop Orchestrator:** Seamless execution loop connecting Stages 1 through 8 (`edge/main_loop.py`).
- [x] **Live Demo Dashboard:** Interactive Streamlit dashboard showing real-time telemetry, compressor selection, and override controls (`dashboard/app.py`).
- [x] **Unit & Integration Test Suite:** 71 automated tests passing covering every stage and edge-cloud closed-loop integration (`tests/`).

---

### Phase B: Remaining Work To Complete 100% Milestone (`[ ]` To Do)

#### 1. Advanced Forecasting Upgrade (Phase 12)
- [ ] **Rolling Autoregressive AR(1) Model:** Implement least-squares lag-1 autocorrelation estimation $\phi$ in `edge/stage3_predictor.py` to complement EWMA.
- [ ] **Multi-Step Ahead Forecasting:** Generate 2-step and 3-step forecast horizons to preemptively adapt before sudden battery drops or network cliffs.
- [ ] **Empirical Volatility Tracking:** Compute residual variance to dynamically adjust prediction confidence intervals.

#### 2. Decoupled Pre-Execution Candidate Estimator (Phase 11A)
- [ ] **Surrogate Regression Cost Models:** Implement `edge/stage4_pre_estimator.py` to predict ratio, energy, and latency directly from feature vectors before compression runs.
- [ ] **Exploration Policy Refinement:** Formulate explicit LinUCB / $\epsilon$-greedy exploration decay schedule for the contextual bandit.

#### 3. Multi-Modal Parity for Image and Text (Phase 13)
- [ ] **Text/Log Stream Ingestion:** Implement `edge/sensors/text_log_reader.py` for continuous system/application log streams.
- [ ] **Text Feature Extraction:** Add byte-frequency entropy and 4-gram lexical repetition index to `edge/stage2_features.py`.
- [ ] **2D Image Feature Extraction:** Implement 2D spatial entropy and Laplacian edge variance in `edge/stage2_features.py` for captured camera frames.
- [ ] **Dynamic Window Modulation:** Dynamically adapt window size $N$ (halving during entropy spikes, doubling during steady state).

#### 4. Expanded Candidate Registry & Edge Portability (Phase 14)
- [ ] **Extended Codec Matrix:** Add Snappy and fine-grained Zstandard levels (levels 1, 3, 15) to `shared/compressors.py`.
- [ ] **Zero-Copy Buffer Pooling:** Pre-allocate static in-memory buffers in `edge/stage5_compression.py` to prevent garbage collection jitter on the Raspberry Pi.

#### 5. QoS-Aware Priority Backlog (Phase 15)
- [ ] **3-Tier Priority Queue:** Implement Urgent (Tier 0), Routine (Tier 1), and Bulk (Tier 2) buffer queues in `edge/stage6_transmission.py`.
- [ ] **Opportunistic Transmission Flushing:** Automatically trigger backlog drains when Stage 3 forecasts network bandwidth recovery.
- [ ] **Backlog Coalescing:** Re-compress stalled backlog windows into single high-ratio archives during sustained network outages.

#### 6. Scalable Production Storage & Infrastructure (Phase 16)
- [ ] **ACID Database Engine:** Migrate outcome logging from flat CSVs to SQLite/PostgreSQL in `cloud/outcome_store.py`.
- [ ] **Worker-Pooled Receiver:** Decouple socket reception from decompression using asynchronous worker pools.
- [ ] **Containerization & Daemons:** Create Dockerfile and systemd service units for 24/7 background operation.

#### 7. Automated Benchmark Suite & Empirical Evaluation (Phase 17)
- [ ] **Automated Benchmark Runner:** Create `benchmarks/run_benchmarks.py` evaluating the pipeline against 4 baselines (Static Raw, Static Fast LZ4, Static High-Ratio zstd, Static Heuristic Rules).
- [ ] **Trade-off Plot Generator:** Create `benchmarks/plot_tradeoffs.py` generating Pareto frontier curves (Compression Ratio vs. Energy Consumed per Byte), deadline adherence rates, and bandit regret convergence plots.
