"""
Edge Node Configuration (Raspberry Pi 3B+ / Broadcom BCM2837 SoC)

Defines system-wide hyperparameters for all 8 architecture stages:
- Stage 1: Window size N & sampling timeout
- Stage 2: Feature extraction histogram bins
- Stage 3: EWMA predictive forecasting alpha & risk thresholds (O1)
- Stage 4: Self-calibrating profiler learning rate beta (O4)
- Stage 5: Decision engine weights, error bounds epsilon, and bandit learning rate eta (O2, O3)
- Stage 7: Joint radio duty-cycle sleep intervals (O5)
"""

# Stage 1: Window & Sampling Settings
WINDOW_SIZE_N = 50
DEFAULT_SAMPLE_TIMEOUT = 5.0

# Stage 2: Feature Extraction Settings
FEATURE_NUM_BINS = 16

# Stage 3: Multi-Signal Predictor Settings (Objective O1)
PREDICTOR_ALPHA = 0.3          # EWMA smoothing factor alpha in (0, 1)
PREDICTOR_BETA = 0.2           # Holt's trend extrapolation factor
DEFAULT_THERMAL_LIMIT_C = 80.0
THROTTLING_TEMP_WARNING_C = 70.0
DEFAULT_BANDWIDTH_KBPS = 1000.0
CRITICAL_BANDWIDTH_KBPS = 30.0

# Stage 4: Self-Calibrating Hardware Profiler (Objective O4)
PROFILER_BETA = 0.15           # Profiler calibration moving-average rate beta in (0, 1)

# Stage 5: Hierarchical Decision Engine & Online Policy (Objectives O2, O3)
# Multi-objective baseline weights (w1: Ratio, w2: Energy, w3: Latency, w4: Error compatibility)
WEIGHT_W1 = 0.40
WEIGHT_W2 = 0.30
WEIGHT_W3 = 0.20
WEIGHT_W4 = 0.10

# Rule-Based Safety Gate Error Bounds epsilon (Objective O2)
EPSILON = 0.05                 # Default error threshold
EPSILON_CRITICAL = 0.000000    # Strict 0% error bound for safety-critical telemetry
EPSILON_ROUTINE = 0.05         # Looser error bound for routine telemetry

# Contextual Bandit Online Policy (Objective O3)
BANDIT_ETA = 0.05              # Online policy learning rate eta

# Stage 7: Joint Radio Duty-Cycle Co-Scheduler (Objective O5)
RADIO_BASE_SLEEP_S = 0.2       # Sleep duration between active sends
RADIO_DEFERRED_SLEEP_S = 2.5   # Extended sleep duration during deferral / low-power mode

# Raspberry Pi SoC Interfaces
RPI_VCGENCMD_BIN = "vcgencmd"
ALPHA = PREDICTOR_ALPHA        # Backwards compatibility alias
