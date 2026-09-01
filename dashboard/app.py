"""
Predictive Multi-Objective Compression Selection — Live Telemetry Dashboard

Interactive Streamlit web dashboard visualizing edge telemetry, Shannon entropy,
Pareto-optimal compression decisions, and cumulative bandwidth/energy savings.
"""

import os
import time
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

    decisions_df, outcomes_df = load_data()

    if outcomes_df.empty and decisions_df.empty:
        st.info("No telemetry logs found yet. Run the pipeline (`python -m edge.main_loop`) to stream data!")
        # Show simulated sample view for preview
        if st.sidebar.button("Generate Sample Demo Data"):
            from edge.stage1_acquisition import AcquisitionStage
            from edge.stage2_features import FeatureExtractionStage
            from edge.stage3_predictor import PredictorStage
            from edge.stage4_decision import DecisionStage
            from edge.stage5_compression import CompressionStage
            from cloud.receiver import CloudReceiver

            s1 = AcquisitionStage(window_size=5)
            s2 = FeatureExtractionStage()
            s3 = PredictorStage()
            s4 = DecisionStage()
            s5 = CompressionStage()
            cloud = CloudReceiver()

            for _ in range(5):
                win = s1.acquire_window()
                feats = s2.extract_features(win)
                pred = s3.predict(win)
                dec = s4.select_strategy(feats, pred)
                comp = s5.compress_payload(win, dec)
                cloud.receive_and_process_payload({
                    "window_id": dec["window_id"],
                    "compressor": comp["compressor_used"],
                    "compression_level": comp["compression_level"],
                    "raw_size_bytes": comp["raw_size_bytes"],
                    "compressed_size_bytes": comp["compressed_size_bytes"],
                    "execution_time_ms": comp["execution_time_ms"],
                    "cpu_energy_proxy_uj": comp["cpu_energy_proxy_uj"],
                    "payload_bytes": comp["compressed_payload"],
                    "transfer_time_ms": 2.5
                })
            st.rerun()
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
            elif not recent_decisions.empty and "compressor" in recent_decisions.columns:
                codec_counts = recent_decisions["compressor"].value_counts()
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

