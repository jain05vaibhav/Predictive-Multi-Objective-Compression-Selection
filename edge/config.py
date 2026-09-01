"""
Edge Node Configuration (Raspberry Pi 3B+)
"""

# Window & Algorithm Hyperparameters
WINDOW_SIZE_N = 50
ALPHA = 0.1
EPSILON = 0.05

# Weights w1-w4
WEIGHT_W1 = 0.4
WEIGHT_W2 = 0.3
WEIGHT_W3 = 0.2
WEIGHT_W4 = 0.1

# Raspberry Pi 3B+ Hardware Settings
RPI_VCGENCMD_BIN = "vcgencmd"
DEFAULT_SAMPLE_TIMEOUT = 5.0

# Stage 3 Predictor Settings
PREDICTOR_ALPHA = 0.3
DEFAULT_THERMAL_LIMIT_C = 80.0
THROTTLING_TEMP_WARNING_C = 70.0
DEFAULT_BANDWIDTH_KBPS = 1000.0

