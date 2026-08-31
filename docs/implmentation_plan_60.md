# Predictive Multi-Objective Compression Selection — 60% Implementation Roadmap

**Platform:** Raspberry Pi 3B+ (Broadcom BCM2837 SoC)  
**Core Pipeline:** Acquisition → Feature Extraction → State Prediction → Decision Engine → Compression → Transmission → Cloud Feedback  

---

## 0. What "60%" Means in this System

| Stage | Included at 60%? | Implementation Depth & Hardware Integration |
|---|---|---|
| **1. Data Acquisition & Windowing** | ✅ Full | Live hardware ingestion via `RPiTelemetryHub` (DHT22 on GPIO4, CSI Camera via Picamera2, and BCM2837 SoC metrics via `vcgencmd`/`psutil`). |
| **2. Feature Extraction** | ✅ Full | Pure-Python zero-dependency Shannon Entropy ($H$), Variance ($\sigma^2$), Rate of Change ($\text{RoC}$), and window summary bounds. |
| **3. State & Resource Predictor** | ✅ Full | EWMA forecasting for next-window SoC thermal state, CPU load, and network bandwidth. |
| **4. Multi-Objective Decision Engine** | ⚠️ Partial | Utility scoring ($w_1 \cdot \text{Ratio} - w_2 \cdot \text{Energy} - w_3 \cdot \text{Latency} - w_4 \cdot \text{Error}$) with hard error constraints ($\epsilon$). Online contextual bandit weights are logged to `logs/decisions.csv` for post-60% learning. |
| **5. Compression Execution** | ✅ Full | Real codecs (LZ4, Zstandard, Bzip2, Snappy, Delta) with real measured execution timing, size ratios, and CPU/energy consumption. |
| **6. Transmission Manager** | ✅ Full | Socket/HTTP transmission with dynamic threshold deferral and network bandwidth emulation via Linux `tc`/`netem`. |
| **7. Cloud Receiver & Outcome Store** | ⚠️ Partial | Decompression verification, outcome vector logging (`logs/outcomes.csv`), and live dashboard streaming. |

---

## 1. Repository Structure

```
Predictive-Multi-Objective-Compression-Selection/
├── edge/                          # Edge node running on Raspberry Pi 3B+
│   ├── config.py                  # Hyperparameters (N=50, T_max=5.0s, weights, RPi config)
│   ├── stage1_acquisition.py      # Window class & AcquisitionStage engine
│   ├── stage2_features.py         # FeatureExtractionStage (Entropy, Var, RoC)
│   ├── stage3_predictor.py        # EWMA Resource & Network State Predictor
│   ├── stage4_decision.py         # Multi-Objective Decision Engine
│   ├── stage5_compression.py      # Dynamic Compression Engine
│   ├── stage6_transmission.py     # Network Transmission & Deferral Manager
│   ├── main_loop.py               # Orchestrator running Stages 1–6 per window
│   └── sensors/
│       ├── rpi_system_reader.py   # Native RPi 3B+ SoC metrics (vcgencmd, psutil, /sys, /proc)
│       ├── telemetry_source.py    # Unified RPiTelemetryHub hardware coordinator
│       ├── camera_reader.py       # CSI/USB camera reader (Picamera2 / OpenCV / CLI)
│       └── dht22_reader.py        # Physical DHT22 GPIO sensor driver
├── cloud/                         # Cloud / Server Receiver
│   ├── receiver.py                # Stage 7 socket/HTTP ingestion server
│   └── outcome_store.py           # Persistent outcome logger
├── dashboard/                     # Web Dashboard
│   └── app.py                     # Streamlit live telemetry & Pareto visualization
├── docs/                          # Documentation
│   ├── stage1_stage2_guide.md     # Stage 1 & 2 mathematical foundations and hardware guide
│   └── implmentation_plan_60.md   # Phase-by-phase implementation roadmap
├── tests/                         # Automated Unit Tests (29 Test Cases)
│   ├── test_rpi_system_reader.py  # Tests for vcgencmd parsing & psutil metrics
│   ├── test_stage1.py             # Tests for acquisition batching & windowing
│   ├── test_stage2.py             # Tests for Shannon entropy, variance, and RoC
│   ├── test_camera_reader.py      # Tests for RAM frame capture & stream buffers
│   └── test_stage3.py ... test_stage7.py
├── requirements.txt               # Lightweight edge node dependencies (armv7l compatible)
├── requirements-dashboard.txt     # Full cloud/dashboard dependencies
└── helpful_commands.txt           # CLI cheatsheet for quick testing
```

---

## 2. Phase 1 — Hardware Assembly & Wiring (Completed)

1. **Raspberry Pi 3B+**: Broadcom BCM2837 SoC with `libraspberrypi-bin` and `vcgencmd` enabled.
2. **DHT22 Sensor**:
   - VCC → 3.3V (Pin 1)
   - DATA → GPIO4 (Pin 7) with 10kΩ pull-up to 3.3V
   - GND → Ground (Pin 9)
3. **CSI Camera Module**: Attached to the 15-pin CSI connector via ribbon cable (supporting OV5647 / IMX219 via `Picamera2` on Unicam `/dev/media2` and ISP `/dev/media0`).
4. **On-Die SoC Telemetry Reader**:
   - `vcgencmd measure_temp` → CPU/SoC Core Temperature (°C)
   - `vcgencmd measure_clock arm` / `core` → ARM CPU & GPU Core Frequencies (MHz)
   - `vcgencmd measure_volts core` / `sdram_c/i/p` → Core & SDRAM Voltages (V)
   - `vcgencmd get_throttled` → Decoded 20-bit under-voltage and thermal throttling bitmask
   - `psutil` → CPU utilization %, 1m/5m/15m load averages, and RAM usage metrics

---

## 3. Phase 2 — Stage 1: Data Acquisition & Windowing (Completed)

- **Engine:** `AcquisitionStage` ([edge/stage1_acquisition.py](file:///c:/Users/Vaibhav/Desktop/projects/project-1/edge/stage1_acquisition.py))
- **Source Coordinator:** `RPiTelemetryHub` ([edge/sensors/telemetry_source.py](file:///c:/Users/Vaibhav/Desktop/projects/project-1/edge/sensors/telemetry_source.py))
- **Algorithm:**
  - Accumulates continuous telemetry samples into a `Window` object.
  - Batches by `WINDOW_SIZE_N = 50` samples or timeout `DEFAULT_SAMPLE_TIMEOUT = 5.0` seconds.
  - Provides in-memory byte serialization via `window.to_bytes()`.
- **Validation:** 6 unit tests passing in [tests/test_stage1.py](file:///c:/Users/Vaibhav/Desktop/projects/project-1/tests/test_stage1.py).

---

## 4. Phase 3 — Stage 2: Feature Extraction (Completed)

- **Engine:** `FeatureExtractionStage` ([edge/stage2_features.py](file:///c:/Users/Vaibhav/Desktop/projects/project-1/edge/stage2_features.py))
- **Zero-Dependency Fast-Math Architecture:**
  - **Shannon Entropy ($H$):** Discretized histogram binning over 16 buckets ($0.0 \le H \le 4.0$).
  - **Variance ($\sigma^2$):** Sample dispersion measurement.
  - **Rate of Change ($\text{RoC}$):** Mean step-to-step absolute transition magnitude.
  - **Summary Bounds:** `min_val`, `max_val`, `mean_val`, `sample_count`.
- **Validation:** 5 unit tests passing in [tests/test_stage2.py](file:///c:/Users/Vaibhav/Desktop/projects/project-1/tests/test_stage2.py).

---

## 5. Phase 4 — Stage 3: Resource & Network State Predictor

- **Purpose:** Forecast next-window CPU load, SoC temperature, and network bandwidth rather than reacting to stale measurements.
- **Algorithm (EWMA):**
  $$\hat{x}_{t+1} = \alpha \cdot x_t + (1 - \alpha) \cdot \hat{x}_t \quad (\alpha = 0.3)$$
- **Inputs:** Rolling history of CPU load, SoC temperature, and network latency.
- **Outputs:** `predicted_state = { "cpu_load": float, "cpu_temp": float, "bandwidth": float }`

---

## 6. Phase 5 — Stage 5: Compression Execution Engine

- **Candidate Codec Registry:**
  - **LZ4** (Ultra-fast streaming, lowest CPU load)
  - **Zstandard** (Balanced high-speed, scalable ratio)
  - **Bzip2 / Deflate** (High-ratio comparison baseline)
  - **Delta + Compressor** (Consecutive differential encoding for environmental telemetry)
  - **Passthrough ("none")** (Zero-compression fallback)
- **Outputs:** `{ compressed_bytes, compression_ratio, energy_uj, execution_time_ms }`

---

## 7. Phase 6 — Stage 4: Multi-Objective Decision Engine

- **Error-Bounded Pareto Optimization:**
  1. Filter candidates exceeding reconstruction error threshold $\epsilon$ (e.g. lossy codecs).
  2. Normalize objective dimensions: Ratio, Energy, Latency, Error to $[0, 1]$.
  3. Compute composite utility score:
     $$\text{Score} = w_1 \cdot \text{Ratio}_{\text{norm}} - w_2 \cdot \text{Energy}_{\text{norm}} - w_3 \cdot \text{Latency}_{\text{norm}} - w_4 \cdot \text{Error}_{\text{norm}}$$
  4. Dynamic weight adaptation (e.g. increase $w_2$ when battery/power is constrained; increase $w_3$ when network deadlines are tight).
  5. Select winning strategy: $\text{decision} = \arg\max(\text{Score})$.
  6. Log decision context to `logs/decisions.csv`.

---

## 8. Phase 7 — Stage 6: Transmission Manager

- **Purpose:** Transmit compressed payloads or buffer locally when network degrades.
- **Network Simulation (`network_sim/netem_profiles.sh`):**
  - Linux `tc`/`netem` profiles to simulate 4G/WiFi degradation (e.g. `rate 100kbit`, `delay 200ms`, `loss 5%`).
  - Dynamic deferral queue that flushes upon network recovery.

---

## 9. Phase 8 — Stage 7: Cloud Receiver & Outcome Logging

- Ingests incoming socket packets, decompresses payloads, and logs outcome metrics to `logs/outcomes.csv`.
- Feeds live metrics into the Streamlit Web Dashboard for interactive review.

---

## 10. Phase 9 — Integration & Demo Dashboard

- **`edge/main_loop.py`:** Orchestrates the live end-to-end loop across Stages 1–6.
- **`dashboard/app.py`:** Live Streamlit UI showing:
  - Real-time telemetry sparklines
  - Shannon entropy & compressibility index
  - Predicted vs. actual resource utilization
  - Winning compression algorithm and score breakdown vs. rejected candidates
  - Cumulative bandwidth and energy savings
