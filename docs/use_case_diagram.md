# Simple UML Use Case Diagram (Quick Overview)
## Predictive Multi-Objective Compression Selection System

---

## 1. Quick Overview Diagram

<div align="center">

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 440" width="100%" height="440" style="background:#ffffff; font-family:'Segoe UI', Arial, sans-serif;">
  <!-- Grid Background -->
  <defs>
    <pattern id="grid_sm" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#f2f2f2" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#grid_sm)" />

  <!-- Diagram Title -->
  <text x="25" y="30" font-size="14" font-style="italic" fill="#555555" font-weight="bold">Simple Use Case Diagram (At a Glance)</text>

  <!-- ================= SYSTEM BOUNDARY BOX ================= -->
  <rect x="200" y="45" width="370" height="375" rx="14" fill="#ffffff" stroke="#222222" stroke-width="2" />
  <text x="385" y="70" font-size="14" font-weight="bold" fill="#222222" text-anchor="middle">Predictive Compression System</text>

  <!-- ================= LEFT ACTORS ================= -->
  
  <!-- Actor 1: Sensors & Camera -->
  <g transform="translate(80, 130)">
    <circle cx="0" cy="-25" r="11" fill="#ffffff" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="-14" x2="0" y2="12" stroke="#111111" stroke-width="2"/>
    <line x1="-16" y1="-5" x2="16" y2="-5" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="12" x2="-12" y2="35" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="12" x2="12" y2="35" stroke="#111111" stroke-width="2"/>
    <text x="0" y="52" font-size="11" font-weight="bold" fill="#111111" text-anchor="middle">Sensors &amp; Camera</text>
  </g>

  <!-- Actor 2: Operator / User -->
  <g transform="translate(80, 310)">
    <circle cx="0" cy="-25" r="11" fill="#ffffff" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="-14" x2="0" y2="12" stroke="#111111" stroke-width="2"/>
    <line x1="-16" y1="-5" x2="16" y2="-5" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="12" x2="-12" y2="35" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="12" x2="12" y2="35" stroke="#111111" stroke-width="2"/>
    <text x="0" y="52" font-size="11" font-weight="bold" fill="#111111" text-anchor="middle">Operator / User</text>
  </g>

  <!-- ================= RIGHT ACTOR ================= -->
  
  <!-- Actor 3: Cloud Receiver -->
  <g transform="translate(680, 220)">
    <circle cx="0" cy="-25" r="11" fill="#ffffff" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="-14" x2="0" y2="12" stroke="#111111" stroke-width="2"/>
    <line x1="-16" y1="-5" x2="16" y2="-5" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="12" x2="-12" y2="35" stroke="#111111" stroke-width="2"/>
    <line x1="0" y1="12" x2="12" y2="35" stroke="#111111" stroke-width="2"/>
    <text x="0" y="52" font-size="11" font-weight="bold" fill="#111111" text-anchor="middle">Cloud Receiver</text>
  </g>

  <!-- ================= USE CASE ELLIPSES ================= -->

  <!-- UC1: Collect Sensor & Camera Data -->
  <g>
    <ellipse cx="330" cy="115" rx="85" ry="20" fill="#d9f2ff" stroke="#003366" stroke-width="1.8" />
    <text x="330" y="119" font-size="11" font-weight="bold" fill="#002244" text-anchor="middle">1. Collect Sensor Data</text>
  </g>

  <!-- UC2: Choose Best Codec & Compress -->
  <g>
    <ellipse cx="340" cy="175" rx="95" ry="20" fill="#d9f2ff" stroke="#003366" stroke-width="1.8" />
    <text x="340" y="179" font-size="11" font-weight="bold" fill="#002244" text-anchor="middle">2. Pick Best Codec &amp; Compress</text>
  </g>

  <!-- UC3: Send Packet over TCP -->
  <g>
    <ellipse cx="320" cy="240" rx="80" ry="20" fill="#d9f2ff" stroke="#003366" stroke-width="1.8" />
    <text x="320" y="244" font-size="11" font-weight="bold" fill="#002244" text-anchor="middle">3. Send over TCP</text>
  </g>

  <!-- UC4: Buffer Offline in RAM (Extend UC3) -->
  <g>
    <ellipse cx="485" cy="240" rx="72" ry="20" fill="#d9f2ff" stroke="#003366" stroke-width="1.8" />
    <text x="485" y="237" font-size="10" font-weight="bold" fill="#002244" text-anchor="middle">4. Buffer Offline</text>
    <text x="485" y="249" font-size="10" font-weight="bold" fill="#002244" text-anchor="middle">(If Wi-Fi Drops)</text>
  </g>

  <!-- UC5: Decompress & Check Zero Loss -->
  <g>
    <ellipse cx="460" cy="305" rx="88" ry="20" fill="#d9f2ff" stroke="#003366" stroke-width="1.8" />
    <text x="460" y="309" font-size="11" font-weight="bold" fill="#002244" text-anchor="middle">5. Decompress (Zero Loss)</text>
  </g>

  <!-- UC6: View Live Dashboard & Sliders -->
  <g>
    <ellipse cx="330" cy="370" rx="90" ry="20" fill="#d9f2ff" stroke="#003366" stroke-width="1.8" />
    <text x="330" y="374" font-size="11" font-weight="bold" fill="#002244" text-anchor="middle">6. Live Dashboard &amp; Sliders</text>
  </g>

  <!-- ================= STRAIGHT CONNECTING LINES ================= -->

  <!-- Lines from Sensors & Camera (96, 125) -->
  <line x1="100" y1="125" x2="248" y2="115" stroke="#333333" stroke-width="1.6" />
  <line x1="100" y1="125" x2="248" y2="175" stroke="#333333" stroke-width="1.6" />

  <!-- Lines from Operator / User (100, 305) -->
  <line x1="100" y1="305" x2="250" y2="180" stroke="#333333" stroke-width="1.6" />
  <line x1="100" y1="305" x2="245" y2="370" stroke="#333333" stroke-width="1.6" />

  <!-- Lines to Cloud Receiver (660, 215) -->
  <line x1="400" y1="240" x2="660" y2="215" stroke="#333333" stroke-width="1.6" />
  <line x1="545" y1="305" x2="660" y2="215" stroke="#333333" stroke-width="1.6" />

  <!-- <<extend>> from UC4 to UC3 -->
  <line x1="413" y1="240" x2="400" y2="240" stroke="#444444" stroke-width="1.5" stroke-dasharray="4,3" />
  <polygon points="400,240 408,236 408,244" fill="#444444" />
  <text x="408" y="228" font-size="9" font-style="italic" fill="#555555" text-anchor="middle">&lt;&lt;extend&gt;&gt;</text>

</svg>
```

</div>

---

## 2. Simple Explanation (In 6 Bullet Points)

1. **Sensors & Camera $\to$ Collect Sensor Data:** Reads temperature, humidity, CPU stats, and camera picture every second into a 5-sample batch.
2. **Pick Best Codec & Compress:** Calculates entropy and predicts temperature/CPU; automatically picks the best algorithm (**LZ4**, **ZSTD**, **Delta-Zlib**, or **Passthrough**).
3. **Send over TCP:** Streams the compressed packet over the network to the laptop/cloud.
4. **Buffer Offline:** If the Wi-Fi drops, packets automatically save into a RAM queue and send when Wi-Fi returns.
5. **Decompress (Zero Loss):** The cloud receiver restores the original data with $100\%$ accuracy ($\varepsilon = 0.0\%$).
6. **Live Dashboard & Sliders:** The operator views live graphs on Streamlit and can move sliders to test high heat or low bandwidth scenarios.
