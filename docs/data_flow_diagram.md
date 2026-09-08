# Software Engineering Data Flow Diagram (DFD)
## Predictive Multi-Objective Compression Selection System

---

## 1. Overview & Software Engineering Standards

This document presents the **Data Flow Diagram (DFD)** for the **Predictive Multi-Objective Compression Selection Pipeline** spanning the **Raspberry Pi 3B+ Edge Device**, the **TCP Network Channel**, the **Cloud Ingestion Service**, and the **Interactive Streamlit Dashboard**.

### Notation Standard: Yourdon & DeMarco
- **External Entities ($E_n$)**: External actors, physical environments, or hardware sources outside software boundaries.
- **Processes ($P_n$)**: Software operations transforming input data streams into output data streams.
- **Data Stores ($D_n$)**: Volatile or persistent storage locations (RAM sliding buffers, FIFO queues, CSV outcome ledgers, JSON configs).
- **Data Flows (Solid/Dashed Directed Arrows)**: Formally typed data flowing between entities, processes, and stores.

---

## 2. Level-0: Context Data Flow Diagram

The Level-0 Context Diagram establishes the highest-level operational boundary between external actors and the system.

```mermaid
flowchart LR
    E1["🌡️ E1: Physical Sensors & Hardware<br/>(DHT22, OV5647 Camera, BCM2837 SoC)"]
    E2["👤 E2: System Operator / Dashboard User"]

    SYS(["⚙️ Predictive Multi-Objective Compression System<br/>(Edge Pipeline + Cloud Ingestion + Analytics)"])

    E1 -->|"DF0.1: Raw Sensor Measurements & JPEG Frames"| SYS
    SYS -->|"DF0.2: Decompressed Telemetry, Camera Feed & Analytics"| E2
    E2 -->|"DF0.3: Simulation Overrides & Codec Forcing"| SYS

    classDef entity fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef system fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px,color:#4a148c;

    class E1,E2 entity;
    class SYS system;
```

---

## 3. Level-1: Detailed Data Flow Diagram

The Level-1 DFD decomposes the system into its primary functional processes across the Edge and Cloud layers, detailing storage interactions, queueing resilience, and the closed-loop control channel.

```mermaid
flowchart TD
    %% External Entities
    E1["🔌 E1: Hardware Sensors<br/>(DHT22, CSI Camera, BCM2837 SoC)"]
    E2["👤 E2: Dashboard User / Operator"]

    %% Data Stores
    D1[("💾 D1: RAM Sliding Buffer<br/>(5-Sample Window)")]
    D2[("💾 D2: RAM FIFO Queue<br/>(Offline Deferral)")]
    D3[("📁 D3: decisions.csv<br/>(Weights, Entropy, Forecasts)")]
    D4[("📁 D4: outcomes.csv<br/>(Decompressed Metrics)")]
    D5[("⚙️ D5: edge_overrides.json<br/>(Control Parameters)")]

    %% Edge Processes
    subgraph EDGE ["🖥️ Edge Device Layer (Raspberry Pi 3B+)"]
        P1["⚙️ P1: Telemetry Acquisition & Windowing<br/>(Stage 1)"]
        P2["⚙️ P2: Statistical Feature Extraction<br/>(Stage 2)"]
        P3["⚙️ P3: EWMA State Forecasting<br/>(Stage 3)"]
        P4["⚙️ P4: Multi-Objective Decision Engine<br/>(Stage 4)"]
        P5["⚙️ P5: Multi-Codec Compression Engine<br/>(Stage 5)"]
        P6["⚙️ P6: Transmission & Deferral Manager<br/>(Stage 6)"]
    end

    %% Cloud & Dashboard Processes
    subgraph CLOUD ["☁️ Cloud & Presentation Layer"]
        P7["⚙️ P7: Cloud Ingestion & Decompression<br/>(Stage 7)"]
        P8["📊 P8: Streamlit Live Visualization<br/>(Dashboard)"]
    end

    %% Data Flows
    E1 -->|"DF1: Raw Sensor Signals & Camera Frames"| P1
    D5 -.->|"DF2: Active Override Injections"| P1
    
    P1 -->|"DF3: 1-sec Sample"| D1
    D1 -->|"DF4: 5-Sample Multimodal Window"| P1
    
    P1 -->|"DF5: Serialized Window JSON"| P2
    P1 -->|"DF6: Raw Payload Bytes"| P5

    P2 -->|"DF7: Entropy H(X), Variance, RoC"| P4
    
    P1 -->|"DF8: Current Edge SoC State"| P3
    P3 -->|"DF9: 1-Step Ahead State Forecasts"| P4
    
    P4 -->|"DF10: Optimal Codec Selection"| P5
    P4 -->|"DF11: Decision Audit Record"| D3
    
    P5 -->|"DF12: Binary Compressed Packet"| P6
    
    %% Resilience & Network Handling
    P6 -.->|"DF13a: Network Offline: Enqueue Deferred"| D2
    D2 -.->|"DF13b: Network Active: Dequeue Oldest"| P6
    
    %% Transmission to Cloud
    P6 ==>|"DF14: TCP Socket Stream (Length-Prefixed)"| P7
    
    P7 -->|"DF15: TCP ACK / Health Response"| P6
    P7 -->|"DF16: Outcome Audit Record"| D4
    P7 -->|"DF17: Reconstructed Frame (latest_frame.jpg)"| P8
    
    D4 -->|"DF18: Outcome Telemetry Stream"| P8
    D3 -->|"DF19: Decision Telemetry Stream"| P8
    
    P8 -->|"DF20: Live Performance Metrics & Visuals"| E2
    E2 -->|"DF21: Slider Tweaks & Codec Overrides"| P8
    P8 -->|"DF22: Persist Override Parameters"| D5

    %% Styling
    classDef entity fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef process fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef store fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#bf360c;

    class E1,E2 entity;
    class P1,P2,P3,P4,P5,P6,P7,P8 process;
    class D1,D2,D3,D4,D5 store;
```

---

## 4. Level-2: Subsystem Decomposition

### 4.1 Decision Subsystem (P4 Internal Flow)

```mermaid
flowchart LR
    subgraph P4_EXPANDED ["P4: Multi-Objective Decision Engine"]
        direction TB
        P4_1["P4.1: Compute State Penalties<br/>(Thermal & CPU Penalty Factors)"]
        P4_2["P4.2: Dynamic Objective Weighting<br/>(w1=Ratio, w2=Latency, w3=Energy, w4=Memory)"]
        P4_3["P4.3: Candidate Codec Scoring<br/>U(c) = w1·R(c) - w2·L(c) - w3·E(c) - w4·M(c)"]
        P4_4["P4.4: Argmax Selection & Fallback Safeguards"]

        P4_1 --> P4_2 --> P4_3 --> P4_4
    end

    IN1["From P2: Entropy H(X), RoC"] --> P4_2
    IN2["From P3: Forecast State"] --> P4_1
    P4_4 --> OUT["To P5: Selected Codec {LZ4, ZSTD, DELTA_ZLIB, NONE}"]
```

### 4.2 Compression Subsystem (P5 Internal Flow)

```mermaid
flowchart LR
    subgraph P5_EXPANDED ["P5: Compression Engine"]
        direction TB
        P5_1{"Selected Codec?"}
        P5_2["LZ4 Block Compressor<br/>(Ultra-Fast Latency)"]
        P5_3["ZSTD Stream Compressor<br/>(High Compression Ratio)"]
        P5_4["Delta-RLE + Zlib Compressor<br/>(Structured Temporal Telemetry)"]
        P5_5["Passthrough Handler<br/>(Uncompressed)"]
        P5_6["Packet Header Framing<br/>[1-Byte ID] + [4-Byte Original Length] + Payload"]

        P5_1 -->|LZ4| P5_2
        P5_1 -->|ZSTD| P5_3
        P5_1 -->|DELTA_ZLIB| P5_4
        P5_1 -->|NONE| P5_5

        P5_2 --> P5_6
        P5_3 --> P5_6
        P5_4 --> P5_6
        P5_5 --> P5_6
    end

    IN_RAW["From P1: Raw Window Bytes"] --> P5_1
    IN_CODEC["From P4: Selected Codec"] --> P5_1
    P5_6 --> OUT_PKT["To P6: Framed Compressed Packet"]
```

---

## 5. Comprehensive Data Flow Dictionary

| Flow ID | Flow Name | Source | Destination | Data Structure / Content | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DF1** | Raw Sensor Signals | $E_1$ | $P_1$ | `float temp_c`, `float hum_pct`, `bytes jpeg`, `float cpu_pct` | Real-time physical GPIO & camera inputs. |
| **DF2** | Override Injections | $D_5$ | $P_1$ | `{"cpu_temperature": 78.5, "force_codec": "LZ4"}` | Live cloud-injected control parameters. |
| **DF3** | 1-sec Sample | $P_1$ | $D_1$ | `TelemetrySample` schema (JSON object) | Periodic timestamped sensor recording. |
| **DF4** | Multimodal Window | $D_1$ | $P_1$ | Array of 5 `TelemetrySample` + 1 Base64 Frame | Batch aggregation for block compression. |
| **DF5** | Serialized Window | $P_1$ | $P_2$ | Canonical JSON String (`str`) | Formatted payload for entropy/variance calculation. |
| **DF6** | Raw Payload Bytes | $P_1$ | $P_5$ | UTF-8 Encoded Byte Array (`bytes`) | Input payload to be compressed. |
| **DF7** | Statistical Features | $P_2$ | $P_4$ | `{"entropy": float, "variance": float, "roc": float}` | Information content and compressibility indicators. |
| **DF8** | Current State | $P_1$ | $P_3$ | `{"cpu_load": float, "temp_c": float, "bw_kbps": float}` | Current system telemetry for time-series memory. |
| **DF9** | State Forecasts | $P_3$ | $P_4$ | `{"pred_cpu": float, "pred_temp": float, "pred_bw": float}` | EWMA & Holt's trend 1-step ahead state projections. |
| **DF10**| Selected Codec ID | $P_4$ | $P_5$ | `CodecID (enum: 0=NONE, 1=LZ4, 2=ZSTD, 3=DELTA_ZLIB)` | Optimal algorithm for the current window. |
| **DF11**| Decision Audit | $P_4$ | $D_3$ | CSV Row: `[ts, chosen_codec, w1..w4, entropy, ...]` | Log entry recording optimization decisions. |
| **DF12**| Compressed Packet | $P_5$ | $P_6$ | Binary Header (5 bytes) + Compressed Byte Stream | Packaged compressed window. |
| **DF13a**| Defer Packet | $P_6$ | $D_2$ | In-Memory `queue.Queue` of Binary Packets | Offline backup buffer during connection failures. |
| **DF13b**| Dequeue Deferred | $D_2$ | $P_6$ | In-Memory `queue.Queue` elements | FIFO drain sequence when network recovers. |
| **DF14**| TCP Socket Stream | $P_6$ | $P_7$ | `[4-Byte Big-Endian Length Prefixed][Payload Bytes]` | Framed network socket stream over TCP. |
| **DF15**| TCP ACK / Health | $P_7$ | $P_6$ | JSON Response: `{"status": "ACK", "lossless": true}` | End-to-end receipt and integrity confirmation. |
| **DF16**| Outcome Audit | $P_7$ | $D_4$ | CSV Row: `[ts, codec, orig_size, comp_size, ratio, latency]` | Ground-truth verification log. |
| **DF17**| Latest Frame | $P_7$ | $P_8$ | JPEG File: `latest_frame.jpg` | Decompressed camera image for live dashboard. |
| **DF18**| Outcome Stream | $D_4$ | $P_8$ | Pandas DataFrame | Real-time performance time-series. |
| **DF19**| Decision Stream | $D_3$ | $P_8$ | Pandas DataFrame | Real-time objective weights and forecast tracking. |
| **DF20**| Visual Metrics | $P_8$ | $E_2$ | HTML5 / Canvas / Streamlit Graphs | Interactive UI for human operator. |
| **DF21**| Slider Tweaks | $E_2$ | $P_8$ | UI Event / Form Submission | Human-in-the-loop parameter adjustments. |
| **DF22**| Persist Override | $P_8$ | $D_5$ | JSON File: `logs/edge_overrides.json` | Persistent configuration sync. |

---

## 6. Software Engineering Quality Attributes & Architecture Principles

### 1. High Cohesion & Single Responsibility Principle (SRP)
- Each module performs exactly one bounded task.
- `stage1` acquires; `stage2` computes math; `stage3` forecasts; `stage4` makes multi-objective decisions; `stage5` transforms bytes; `stage6` transmits; `stage7` verifies.

### 2. Loose Coupling & Contract-Driven Design
- Stages interact strictly via strongly-typed schemas (`TelemetrySample`, canonical JSON strings, standardized binary packet framing).
- The network interface uses explicit 4-byte length prefixing to prevent TCP fragmentation issues.

### 3. Fault Tolerance & Zero Data Loss
- The transmission stage ($P_6$) encapsulates a non-blocking FIFO queue ($D_2$) allowing uninterrupted sensor operation even if the network fails completely.
- When connection re-establishes, backlogged packets are automatically drained and delivered in chronological order.

### 4. Zero-Loss Verification ($\varepsilon = 0.0\%$)
- Stage 7 enforces a strict lossless mathematical identity:
$$\text{DecodedData} \equiv \text{OriginalData} \implies \varepsilon = 0.0\%$$
- Any hash or byte discrepancy triggers an immediate anomaly flag.
