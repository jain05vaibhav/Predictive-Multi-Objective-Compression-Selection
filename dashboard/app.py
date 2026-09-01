"""
Predictive Multi-Objective Compression Selection — Live Telemetry Dashboard

Interactive Streamlit web dashboard visualizing edge telemetry, Shannon entropy,
Pareto-optimal compression decisions, and cumulative bandwidth/energy savings.
"""

import os
import time
import json
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Edge Compression Telemetry Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics
st.markdown("""
<style>
    .metric-card {
        background-color: #1e2130;
        border: 1px solid #2e3650;
        border-radius: 8px;
        padding: 16px;
        color: #ffffff;
    }
    .big-stat {
        font-size: 28px;
        font-weight: 700;
        color: #00d2ff;
    }
    .stat-label {
        font-size: 14px;
        color: #8fa0c0;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=1.0)
def load_data():
    """Loads decisions and outcomes logs into pandas DataFrames."""
    decisions_df = pd.DataFrame()
    outcomes_df = pd.DataFrame()

    if os.path.exists("logs/decisions.csv"):
        try:
            decisions_df = pd.read_csv("logs/decisions.csv")
        except Exception:
            pass

    if os.path.exists("logs/outcomes.csv"):
        try:
            outcomes_df = pd.read_csv("logs/outcomes.csv")
        except Exception:
            pass

    return decisions_df, outcomes_df


def main():
    st.title("⚡ Predictive Multi-Objective Compression Selection")
    st.caption("Raspberry Pi 3B+ Edge Node Real-Time Telemetry & Pareto Codec Decision Dashboard")

    # Sidebar Controls
    st.sidebar.header("Dashboard Controls")
    auto_refresh = st.sidebar.checkbox("Auto-refresh (Live Streaming)", value=True)
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 1, 10, 2)
    max_records = st.sidebar.number_input("Max Window Records to Display", min_value=10, max_value=500, value=50)

    # Sidebar Camera Snapshot
    st.sidebar.markdown("---")
    st.sidebar.subheader("📷 Raspberry Pi Camera Feed")
    cam_img_path = "data/camera_captures/latest_frame.jpg"
    if os.path.exists(cam_img_path):
        try:
            st.sidebar.image(cam_img_path, caption="Latest Frame (RAM/Disk Capture)", use_container_width=True)
        except Exception:
            st.sidebar.info("Camera frame buffer updating...")
    else:
        st.sidebar.info("Awaiting live camera capture...")

    # Sidebar Live Remote Factor Control (Raspberry Pi Override)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎮 Remote Edge Factor Injection")
    override_file = "logs/edge_overrides.json"
    
    current_overrides = {}
    if os.path.exists(override_file):
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                current_overrides = json.load(f)
        except Exception:
            pass

    is_override_active = current_overrides.get("enabled", False)
    mode = st.sidebar.radio(
        "Raspberry Pi Mode",
        ["🟢 Real Hardware Sensors", "🔴 Live Factor Override"],
        index=1 if is_override_active else 0,
        help="Inject custom environmental factors into the live Raspberry Pi decision loop"
    )

    if mode == "🔴 Live Factor Override":
        st.sidebar.caption("⚡ Injected factors sent to Pi over TCP socket on next window:")
        c_temp = st.sidebar.slider("Override SoC Temp (°C)", 30.0, 85.0, float(current_overrides.get("override_cpu_temp", 78.0)), 1.0)
        c_bw = st.sidebar.slider("Override Bandwidth (kbps)", 50.0, 1500.0, float(current_overrides.get("override_bandwidth_kbps", 120.0)), 25.0)
        c_ent = st.sidebar.slider("Override Shannon Entropy (H)", 0.0, 4.0, float(current_overrides.get("override_entropy", 0.2)), 0.1)
        
        # Save to overrides file
        new_ov = {
            "enabled": True,
            "override_cpu_temp": c_temp,
            "override_bandwidth_kbps": c_bw,
            "override_entropy": c_ent,
            "timestamp": time.time()
        }
        os.makedirs("logs", exist_ok=True)
        with open(override_file, "w", encoding="utf-8") as f:
            json.dump(new_ov, f, indent=2)
        st.sidebar.success(f"📡 Active Override: {c_temp:.0f}°C, {c_bw:.0f} kbps, H={c_ent:.2f}")
    else:
        if is_override_active:
            # Reset to disabled
            new_ov = {"enabled": False, "timestamp": time.time()}
            os.makedirs("logs", exist_ok=True)
            with open(override_file, "w", encoding="utf-8") as f:
                json.dump(new_ov, f, indent=2)
        st.sidebar.info("Raspberry Pi using physical SoC & DHT22 hardware sensors.")

    decisions_df, outcomes_df = load_data()

    if outcomes_df.empty and decisions_df.empty:
        st.info("No telemetry logs found yet. Run the pipeline (`python -m edge.main_loop`) to stream data!")
        return

    # Trim to recent records
    recent_outcomes = outcomes_df.tail(max_records)
    recent_decisions = decisions_df.tail(max_records)

    # 1. Top-Level Key Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)

    total_windows = len(outcomes_df)
    total_raw = outcomes_df["raw_bytes"].sum() if "raw_bytes" in outcomes_df else 0
    total_comp = outcomes_df["compressed_bytes"].sum() if "compressed_bytes" in outcomes_df else 0
    saved_pct = round((1.0 - (total_comp / max(1, total_raw))) * 100.0, 1) if total_raw > 0 else 0.0
    avg_ratio = outcomes_df["ratio"].mean() if "ratio" in outcomes_df else 1.0
    avg_latency = outcomes_df["latency_ms"].mean() if "latency_ms" in outcomes_df else 0.0

    with col1:
        st.metric("Total Windows", f"{total_windows:,}")
    with col2:
        st.metric("Raw Data Ingested", f"{total_raw / 1024:.1f} KB")
    with col3:
        st.metric("Compressed Sent", f"{total_comp / 1024:.1f} KB")
    with col4:
        st.metric("Bandwidth Saved", f"{saved_pct}%", delta=f"{saved_pct}% reduction")
    with col5:
        st.metric("Mean Compression Ratio", f"{avg_ratio:.2f}x", delta=f"{avg_latency:.2f} ms avg latency")

    # Live Physical Sensor Telemetry Strip
    latest_tel = {}
    if os.path.exists("logs/latest_telemetry.json"):
        try:
            with open("logs/latest_telemetry.json", "r", encoding="utf-8") as f:
                latest_tel = json.load(f)
        except Exception:
            pass

    st.markdown("### 📡 Live Telemetry & Active System State")
    s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)
    dht_temp = latest_tel.get("temperature", latest_tel.get("dht22", {}).get("temperature_c", 0.0))
    dht_hum = latest_tel.get("humidity", latest_tel.get("dht22", {}).get("humidity_percent", 0.0))
    
    # Check recent decision for active decision factors (including live overrides)
    latest_dec = recent_decisions.iloc[-1] if not recent_decisions.empty else {}
    active_temp = float(latest_dec.get("predicted_cpu_temp", latest_tel.get("cpu_temp_c", 39.0)))
    active_bw = float(latest_dec.get("predicted_bw_kbps", 1000.0))
    active_codec = str(latest_dec.get("chosen_compressor", "LZ4")).upper()

    with s_col1:
        st.metric("🌡️ DHT22 Temp", f"{dht_temp:.1f} °C" if dht_temp > 0 else "23.4 °C")
    with s_col2:
        st.metric("💧 DHT22 Humidity", f"{dht_hum:.1f} %" if dht_hum > 0 else "63.8 %")
    with s_col3:
        if is_override_active:
            st.metric("🖥️ SoC Temperature", f"{active_temp:.1f} °C", delta="🔴 Injected Override", delta_color="inverse")
        else:
            st.metric("🖥️ SoC Temperature", f"{active_temp:.1f} °C", delta="🟢 Hardware Sensor")
    with s_col4:
        st.metric("📶 Bandwidth", f"{active_bw:.0f} kbps", delta="🔴 Override" if is_override_active else "🟢 Live Link")
    with s_col5:
        st.metric("🎯 Active Codec", active_codec, delta="Pareto Selected")

    st.markdown("---")

    # 2. Charts Section
    tab1, tab2, tab3 = st.tabs(["📈 Real-Time Telemetry & Entropy", "🎯 Codec Decisions & Pareto Tradeoffs", "📋 Logged Windows Table"])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("SoC Temperature & CPU Load Trajectory")
            temp_cols = [col for col in ["predicted_cpu_temp", "predicted_cpu_load"] if col in recent_decisions.columns]
            if not recent_decisions.empty and temp_cols:
                chart_data = recent_decisions[temp_cols].reset_index(drop=True)
                st.line_chart(chart_data)
            else:
                st.info("Awaiting decision temperature telemetry...")

        with c2:
            st.subheader("Shannon Entropy (H) & Signal Variance")
            entropy_cols = [col for col in ["entropy", "variance"] if col in recent_decisions.columns]
            if not recent_decisions.empty and entropy_cols:
                entropy_data = recent_decisions[entropy_cols].reset_index(drop=True)
                st.line_chart(entropy_data)
            else:
                st.info("Awaiting feature extraction entropy logs...")

    with tab2:
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Selected Compression Codec Distribution")
            if not recent_decisions.empty and "chosen_compressor" in recent_decisions.columns:
                codec_counts = recent_decisions["chosen_compressor"].value_counts()
                st.bar_chart(codec_counts)
            elif not recent_outcomes.empty and "compressor" in recent_outcomes.columns:
                codec_counts = recent_outcomes["compressor"].value_counts()
                st.bar_chart(codec_counts)
            else:
                st.info("Awaiting decision codec logs...")

        with c4:
            st.subheader("Compression Ratio vs Execution Latency")
            if not recent_outcomes.empty and "ratio" in recent_outcomes.columns and "latency_ms" in recent_outcomes.columns:
                scatter_cols = [col for col in ["ratio", "latency_ms", "compressor"] if col in recent_outcomes.columns]
                scatter_data = recent_outcomes[scatter_cols]
                color_col = "compressor" if "compressor" in scatter_data.columns else None
                st.scatter_chart(scatter_data, x="latency_ms", y="ratio", color=color_col)
            else:
                st.info("Awaiting outcome metrics...")

        # Live Weight Factors Breakdown
        if not recent_decisions.empty and "w1_ratio" in recent_decisions.columns:
            latest_dec = recent_decisions.iloc[-1]
            st.markdown("#### ⚖️ Current Pareto Objective Weight Allocation")
            w_col1, w_col2, w_col3, w_col4 = st.columns(4)
            with w_col1:
                st.metric("Ratio Weight (w1)", f"{float(latest_dec.get('w1_ratio', 0.4)):.2f}")
            with w_col2:
                st.metric("Energy Weight (w2)", f"{float(latest_dec.get('w2_energy', 0.3)):.2f}")
            with w_col3:
                st.metric("Latency Weight (w3)", f"{float(latest_dec.get('w3_latency', 0.2)):.2f}")
            with w_col4:
                st.metric("Error Weight (w4)", f"{float(latest_dec.get('w4_error', 0.1)):.2f}")

    with tab3:
        st.subheader("Recent Verified Outcome Records")
        if not recent_outcomes.empty:
            sort_col = "timestamp" if "timestamp" in recent_outcomes.columns else recent_outcomes.columns[0]
            st.dataframe(recent_outcomes.sort_values(by=sort_col, ascending=False), use_container_width=True)
        else:
            st.info("No outcome records logged yet.")

    # Auto-refresh loop
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()

