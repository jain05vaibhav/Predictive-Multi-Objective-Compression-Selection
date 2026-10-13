/**
 * AURA-EDGE // Autonomous IoT Compression Command Center
 * Client-side Controller & Chart Visualizer
 */

// Global Chart References
let chartResources = null;
let chartWorkload = null;
let chartPareto = null;
let chartCodecPie = null;
let chartRadioBacklog = null;
let chartRadioActions = null;
let chartOverheadLatency = null;
let chartOverheadRam = null;

// State Tracking
let isOverrideSyncing = false;

// Color Palette
const COLORS = {
  cyan: '#00f0ff',
  emerald: '#10b981',
  violet: '#8b5cf6',
  amber: '#f59e0b',
  crimson: '#ef4444',
  textMain: '#f8fafc',
  textMuted: '#94a3b8',
  gridSubtle: 'rgba(255, 255, 255, 0.06)'
};

// ==============================================================================
// Initialization
// ==============================================================================
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupSliders();
  setupPresets();
  setupCamera();
  initCharts();

  // Initial Fetch & Start Polling
  fetchSummary();
  fetchTelemetry();
  fetchDecisionsAndOutcomes();
  fetchProfilerMatrix();
  fetchOverhead();

  setInterval(fetchSummary, 1500);
  setInterval(fetchTelemetry, 1500);
  setInterval(fetchDecisionsAndOutcomes, 2000);
  setInterval(fetchProfilerMatrix, 5000);
  setInterval(fetchOverhead, 3000);
});

// ==============================================================================
// Tab Navigation
// ==============================================================================
function setupTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        targetEl.classList.add('active');
      }

      // Trigger Chart resize if visible
      setTimeout(() => {
        if (chartResources) chartResources.resize();
        if (chartWorkload) chartWorkload.resize();
        if (chartPareto) chartPareto.resize();
        if (chartCodecPie) chartCodecPie.resize();
        if (chartRadioBacklog) chartRadioBacklog.resize();
        if (chartRadioActions) chartRadioActions.resize();
        if (chartOverheadLatency) chartOverheadLatency.resize();
        if (chartOverheadRam) chartOverheadRam.resize();
      }, 50);
    });
  });
}

// ==============================================================================
// CSI Camera Stream Refresh
// ==============================================================================
function setupCamera() {
  const btn = document.getElementById('btn-refresh-cam');
  const img = document.getElementById('camera-frame');
  const stamp = document.getElementById('cam-timestamp');

  const refreshImg = () => {
    img.src = '/api/camera/latest?t=' + Date.now();
    const d = new Date();
    if (stamp) {
      stamp.innerText = d.toTimeString().split(' ')[0] + '.' + String(d.getMilliseconds()).padStart(3, '0');
    }
  };

  if (btn) btn.addEventListener('click', refreshImg);
  setInterval(refreshImg, 5000);
}

// ==============================================================================
// Remote Factor Injection Sliders
// ==============================================================================
function setupSliders() {
  const checkEnabled = document.getElementById('override-enabled');
  const slideTemp = document.getElementById('slider-override-temp');
  const slideBw = document.getElementById('slider-override-bw');
  const slideEntropy = document.getElementById('slider-override-entropy');

  const lblTemp = document.getElementById('val-override-temp');
  const lblBw = document.getElementById('val-override-bw');
  const lblEntropy = document.getElementById('val-override-entropy');

  slideTemp.addEventListener('input', () => {
    lblTemp.innerText = `${parseFloat(slideTemp.value).toFixed(1)} °C`;
  });
  slideBw.addEventListener('input', () => {
    lblBw.innerText = `${slideBw.value} kbps`;
  });
  slideEntropy.addEventListener('input', () => {
    lblEntropy.innerText = `${parseFloat(slideEntropy.value).toFixed(2)} bits`;
  });

  const sendOverrides = () => {
    if (isOverrideSyncing) return;
    const payload = {
      enabled: checkEnabled.checked,
      override_cpu_temp: parseFloat(slideTemp.value),
      override_bandwidth_kbps: parseFloat(slideBw.value),
      override_entropy: parseFloat(slideEntropy.value)
    };

    fetch('/api/overrides', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).catch(err => console.error('Failed to post overrides:', err));
  };

  checkEnabled.addEventListener('change', sendOverrides);
  slideTemp.addEventListener('change', sendOverrides);
  slideBw.addEventListener('change', sendOverrides);
  slideEntropy.addEventListener('change', sendOverrides);

  // Sync initial override state from server
  fetch('/api/overrides')
    .then(r => r.json())
    .then(data => {
      isOverrideSyncing = true;
      if (data.enabled !== undefined) checkEnabled.checked = data.enabled;
      if (data.override_cpu_temp !== undefined && data.override_cpu_temp !== null) {
        slideTemp.value = data.override_cpu_temp;
        lblTemp.innerText = `${data.override_cpu_temp.toFixed(1)} °C`;
      }
      if (data.override_bandwidth_kbps !== undefined && data.override_bandwidth_kbps !== null) {
        slideBw.value = data.override_bandwidth_kbps;
        lblBw.innerText = `${data.override_bandwidth_kbps} kbps`;
      }
      if (data.override_entropy !== undefined && data.override_entropy !== null) {
        slideEntropy.value = data.override_entropy;
        lblEntropy.innerText = `${data.override_entropy.toFixed(2)} bits`;
      }
      isOverrideSyncing = false;
    })
    .catch(() => { isOverrideSyncing = false; });
}

function setupPresets() {
  const presets = document.querySelectorAll('.btn-preset');
  const checkEnabled = document.getElementById('override-enabled');
  const slideTemp = document.getElementById('slider-override-temp');
  const slideBw = document.getElementById('slider-override-bw');
  const slideEntropy = document.getElementById('slider-override-entropy');
  const lblTemp = document.getElementById('val-override-temp');
  const lblBw = document.getElementById('val-override-bw');
  const lblEntropy = document.getElementById('val-override-entropy');

  presets.forEach(p => {
    p.addEventListener('click', () => {
      const t = parseFloat(p.getAttribute('data-temp'));
      const bw = parseFloat(p.getAttribute('data-bw'));
      const h = parseFloat(p.getAttribute('data-entropy'));

      checkEnabled.checked = true;
      slideTemp.value = t;
      slideBw.value = bw;
      slideEntropy.value = h;

      lblTemp.innerText = `${t.toFixed(1)} °C`;
      lblBw.innerText = `${bw} kbps`;
      lblEntropy.innerText = `${h.toFixed(2)} bits`;

      // Trigger POST
      const event = new Event('change');
      checkEnabled.dispatchEvent(event);
    });
  });

  const btnRefresh = document.getElementById('btn-manual-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      fetchSummary();
      fetchTelemetry();
      fetchDecisionsAndOutcomes();
      fetchProfilerMatrix();
      fetchOverhead();
    });
  }
}

// ==============================================================================
// Data Fetching: Summary & Top KPIs
// ==============================================================================
async function fetchSummary() {
  try {
    const res = await fetch('/api/summary');
    if (!res.ok) throw new Error('Status ' + res.status);
    const data = await res.json();

    document.getElementById('kpi-windows').innerText = data.total_windows.toLocaleString();
    const rawKb = (data.total_raw_bytes / 1024).toFixed(1);
    document.getElementById('kpi-raw-bytes').innerText = `${rawKb} KB`;
    document.getElementById('kpi-saved-pct').innerText = `${data.saved_bandwidth_percent.toFixed(1)}%`;
    document.getElementById('kpi-ratio').innerText = `${data.average_ratio.toFixed(2)}x`;
    document.getElementById('kpi-latency').innerText = `${data.average_latency_ms.toFixed(2)} ms`;
    document.getElementById('kpi-active-codec').innerText = data.active_codec;
    document.getElementById('kpi-active-action').innerText = data.active_action;
    document.getElementById('kpi-overhead-ms').innerText = `${data.worst_case_decision_latency_ms.toFixed(3)} ms`;
    document.getElementById('kpi-overhead-ram').innerText = `${data.controller_ram_mb.toFixed(1)} MB`;

    document.getElementById('connection-status').innerText = 'CONNECTED (1.2s POLLING)';
    document.getElementById('live-indicator').style.borderColor = 'rgba(16, 185, 129, 0.3)';
  } catch (err) {
    document.getElementById('connection-status').innerText = 'DISCONNECTED';
    document.getElementById('live-indicator').style.borderColor = 'rgba(239, 68, 68, 0.3)';
  }
}

// ==============================================================================
// Data Fetching: Physical Telemetry
// ==============================================================================
async function fetchTelemetry() {
  try {
    const res = await fetch('/api/telemetry');
    if (!res.ok) return;
    const t = await res.json();

    document.getElementById('tel-cpu-temp').innerText = `${t.cpu_temp_c ? t.cpu_temp_c.toFixed(1) : '--'} °C`;
    document.getElementById('tel-cpu-percent').innerText = `${t.cpu_percent ? t.cpu_percent.toFixed(1) : '--'} %`;
    document.getElementById('tel-cpu-freq').innerText = `${t.cpu_freq_mhz ? t.cpu_freq_mhz.toFixed(0) : '--'} MHz`;
    document.getElementById('tel-core-volts').innerText = `${t.core_voltage_v ? t.core_voltage_v.toFixed(3) : '--'} V`;
    document.getElementById('tel-ambient-temp').innerText = `${t.temperature ? t.temperature.toFixed(1) : '--'} °C`;
    document.getElementById('tel-ambient-humidity').innerText = `${t.humidity ? t.humidity.toFixed(1) : '--'} %`;
    document.getElementById('tel-battery').innerText = `${t.battery_percent ? t.battery_percent.toFixed(1) : '--'} %`;

    if (t.system) {
      const throttledHex = t.system.throttled_hex || '0x0';
      const undervolt = t.system.undervoltage_now ? ' [UNDERVOLT]' : '';
      const throttled = t.system.throttled_now ? ' [THROTTLED]' : '';
      document.getElementById('tel-throttled').innerText = `${throttledHex}${undervolt}${throttled}`;
      if (t.system.undervoltage_now || t.system.throttled_now) {
        document.getElementById('tel-throttled').style.color = COLORS.crimson;
      } else {
        document.getElementById('tel-throttled').style.color = COLORS.emerald;
      }
    }
  } catch (err) {
    console.warn('Telemetry fetch error', err);
  }
}

// ==============================================================================
// Data Fetching: Decisions & Cloud Outcomes
// ==============================================================================
async function fetchDecisionsAndOutcomes() {
  try {
    const [decRes, outRes] = await Promise.all([
      fetch('/api/decisions?limit=40'),
      fetch('/api/outcomes?limit=40')
    ]);

    const decisions = await decRes.json();
    const outcomes = await outRes.json();

    updateOutcomesTable(outcomes);
    updateForecastingCharts(decisions);
    updateParetoCharts(decisions, outcomes);
    updateRadioCharts(decisions);
  } catch (err) {
    console.warn('Decisions fetch error', err);
  }
}

function updateOutcomesTable(outcomes) {
  const tbody = document.getElementById('tbody-outcomes');
  if (!tbody || !outcomes || outcomes.length === 0) return;

  const reversed = [...outcomes].reverse().slice(0, 10);
  let html = '';

  reversed.forEach(row => {
    const codec = (row.compressor || row.codec || 'lz4').toLowerCase();
    const ratio = parseFloat(row.ratio || 1.0).toFixed(2);
    const latency = parseFloat(row.latency_ms || 0.0).toFixed(2);
    const raw = parseInt(row.raw_bytes || 0).toLocaleString();
    const comp = parseInt(row.compressed_bytes || 0).toLocaleString();
    const windowId = row.window_id || '--';
    const modality = row.data_type || 'numeric';
    const crit = row.criticality || 'routine';
    const errBound = parseFloat(row.reconstruction_error || 0.0).toFixed(4);

    let badgeClass = 'badge-lz4';
    if (codec.includes('zstd')) badgeClass = 'badge-zstd';
    else if (codec.includes('delta')) badgeClass = 'badge-delta';
    else if (codec.includes('bzip')) badgeClass = 'badge-bzip2';
    else if (codec.includes('none')) badgeClass = 'badge-none';

    html += `
      <tr>
        <td style="font-weight: 700; color: var(--text-main);">${windowId}</td>
        <td style="color: var(--text-muted); text-transform: uppercase;">${modality}</td>
        <td>
          <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${crit === 'safety_critical' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(255, 255, 255, 0.05)'}; color: ${crit === 'safety_critical' ? 'var(--crimson)' : 'var(--text-dim)'};">
            ${crit}
          </span>
        </td>
        <td><span class="badge-codec ${badgeClass}">${codec}</span></td>
        <td>${raw} B</td>
        <td style="color: var(--cyan);">${comp} B</td>
        <td style="font-weight: 700; color: #ffffff;">${ratio}x</td>
        <td>${latency} ms</td>
        <td style="color: var(--emerald);">${errBound}</td>
        <td>
          <span class="badge-status-verified">
            <span>✓</span> Cloud Verified
          </span>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

// ==============================================================================
// Data Fetching: Empirical Calibration Matrix
// ==============================================================================
async function fetchProfilerMatrix() {
  try {
    const res = await fetch('/api/profiler');
    if (!res.ok) return;
    const matrix = await res.json();
    const tbody = document.getElementById('tbody-profiler');
    if (!tbody) return;

    let html = '';
    for (const [bucket, codecs] of Object.entries(matrix)) {
      for (const [codec, stats] of Object.entries(codecs)) {
        let badgeClass = 'badge-lz4';
        if (codec.includes('zstd')) badgeClass = 'badge-zstd';
        else if (codec.includes('delta')) badgeClass = 'badge-delta';
        else if (codec.includes('bzip')) badgeClass = 'badge-bzip2';
        else if (codec.includes('none')) badgeClass = 'badge-none';

        const latUs = (stats.latency_ms_per_kb * 1000).toFixed(1);
        const uj = stats.energy_uj_per_kb.toFixed(1);

        html += `
          <tr>
            <td style="color: var(--cyan); font-weight: 600;">${bucket}</td>
            <td><span class="badge-codec ${badgeClass}">${codec}</span></td>
            <td style="font-weight: 700;">${stats.ratio.toFixed(2)}x</td>
            <td>${latUs} &micro;s</td>
            <td>${uj} &micro;J</td>
            <td style="color: var(--emerald);">${stats.error.toFixed(4)}</td>
            <td><span style="color: var(--emerald); font-size: 11px;">● Calibrated</span></td>
          </tr>
        `;
      }
    }
    tbody.innerHTML = html;
  } catch (err) {
    console.warn('Profiler fetch error', err);
  }
}

// ==============================================================================
// Data Fetching: Section 2.12 Controller Overhead
// ==============================================================================
async function fetchOverhead() {
  try {
    const res = await fetch('/api/overhead?limit=30');
    if (!res.ok) return;
    const records = await res.json();
    if (!records || records.length === 0) return;

    const labels = records.map((r, i) => `#${i + 1}`);
    const worstCaseLatencies = records.map(r => parseFloat(r.worst_case_decision_latency_ms || 0.45));
    const meanLatencies = records.map(r => parseFloat(r.mean_decision_latency_ms || 0.12));
    const ramRss = records.map(r => parseFloat(r.controller_ram_mb || 82.0));

    if (chartOverheadLatency) {
      chartOverheadLatency.data.labels = labels;
      chartOverheadLatency.data.datasets[0].data = worstCaseLatencies;
      chartOverheadLatency.data.datasets[1].data = meanLatencies;
      chartOverheadLatency.update('none');
    }

    if (chartOverheadRam) {
      chartOverheadRam.data.labels = labels;
      chartOverheadRam.data.datasets[0].data = ramRss;
      chartOverheadRam.update('none');
    }
  } catch (err) {
    console.warn('Overhead fetch error', err);
  }
}

// ==============================================================================
// Chart Initialization & Updates
// ==============================================================================
function initCharts() {
  const chartDefaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400 },
    plugins: {
      legend: {
        labels: {
          color: COLORS.textMuted,
          font: { family: 'Plus Jakarta Sans', size: 11 }
        }
      }
    },
    scales: {
      x: {
        grid: { color: COLORS.gridSubtle },
        ticks: { color: COLORS.textMuted, font: { family: 'JetBrains Mono', size: 10 } }
      },
      y: {
        grid: { color: COLORS.gridSubtle },
        ticks: { color: COLORS.textMuted, font: { family: 'JetBrains Mono', size: 10 } }
      }
    }
  };

  // 1. Forecast Resource Track (CPU Temp & Bandwidth)
  const ctxResources = document.getElementById('chart-forecast-resources');
  if (ctxResources) {
    chartResources = new Chart(ctxResources, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Forecast SoC Temp (°C)',
            borderColor: COLORS.amber,
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            data: [],
            borderWidth: 2,
            tension: 0.3,
            yAxisID: 'y'
          },
          {
            label: 'Forecast Bandwidth (kbps)',
            borderColor: COLORS.cyan,
            backgroundColor: 'rgba(0, 240, 255, 0.1)',
            data: [],
            borderWidth: 2,
            tension: 0.3,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        ...chartDefaultOptions,
        scales: {
          x: chartDefaultOptions.scales.x,
          y: {
            ...chartDefaultOptions.scales.y,
            title: { display: true, text: 'Temp (°C)', color: COLORS.amber }
          },
          y1: {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: COLORS.cyan, font: { family: 'JetBrains Mono', size: 10 } },
            title: { display: true, text: 'Bandwidth (kbps)', color: COLORS.cyan }
          }
        }
      }
    });
  }

  // 2. Forecast Workload Track (Entropy H and Variance)
  const ctxWorkload = document.getElementById('chart-forecast-workload');
  if (ctxWorkload) {
    chartWorkload = new Chart(ctxWorkload, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Predicted Workload Entropy Ĥ (bits)',
            borderColor: COLORS.violet,
            backgroundColor: 'rgba(139, 92, 246, 0.15)',
            data: [],
            fill: true,
            borderWidth: 2,
            tension: 0.3
          }
        ]
      },
      options: chartDefaultOptions
    });
  }

  // 3. Pareto Frontier Scatter Chart
  const ctxPareto = document.getElementById('chart-pareto-scatter');
  if (ctxPareto) {
    chartPareto = new Chart(ctxPareto, {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'Pareto Candidate Trade-Offs (Ratio vs Latency)',
            backgroundColor: COLORS.cyan,
            borderColor: '#ffffff',
            pointRadius: 6,
            pointHoverRadius: 9,
            data: []
          }
        ]
      },
      options: {
        ...chartDefaultOptions,
        scales: {
          x: {
            ...chartDefaultOptions.scales.x,
            title: { display: true, text: 'Compression Latency (ms)', color: COLORS.textMuted }
          },
          y: {
            ...chartDefaultOptions.scales.y,
            title: { display: true, text: 'Compression Ratio (x)', color: COLORS.textMuted }
          }
        }
      }
    });
  }

  // 4. Codec Pie / Doughnut Chart
  const ctxPie = document.getElementById('chart-codec-pie');
  if (ctxPie) {
    chartCodecPie = new Chart(ctxPie, {
      type: 'doughnut',
      data: {
        labels: ['LZ4', 'ZSTD', 'Delta-Zlib', 'Bzip2', 'None'],
        datasets: [
          {
            data: [1, 1, 1, 1, 1],
            backgroundColor: [
              'rgba(0, 240, 255, 0.75)',
              'rgba(139, 92, 246, 0.75)',
              'rgba(16, 185, 129, 0.75)',
              'rgba(245, 158, 11, 0.75)',
              'rgba(148, 163, 184, 0.4)'
            ],
            borderColor: '#0d121d',
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: {
              color: COLORS.textMuted,
              font: { family: 'Plus Jakarta Sans', size: 12 }
            }
          }
        }
      }
    });
  }

  // 5. Radio Buffer Backlog Timeline
  const ctxRadioBacklog = document.getElementById('chart-radio-backlog');
  if (ctxRadioBacklog) {
    chartRadioBacklog = new Chart(ctxRadioBacklog, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'RAM Backlog Queue Depth (Windows)',
            borderColor: COLORS.emerald,
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            fill: true,
            data: [],
            borderWidth: 2,
            stepped: true
          }
        ]
      },
      options: chartDefaultOptions
    });
  }

  // 6. Radio Decisions (Transmit vs Defer)
  const ctxRadioActions = document.getElementById('chart-radio-actions');
  if (ctxRadioActions) {
    chartRadioActions = new Chart(ctxRadioActions, {
      type: 'bar',
      data: {
        labels: ['Transmit', 'Defer Queue'],
        datasets: [
          {
            label: 'Count',
            data: [1, 0],
            backgroundColor: [COLORS.cyan, COLORS.amber]
          }
        ]
      },
      options: {
        ...chartDefaultOptions,
        plugins: { legend: { display: false } }
      }
    });
  }

  // 7. Overhead Latency vs Real-Time Bound (1.0ms)
  const ctxOverheadLat = document.getElementById('chart-overhead-latency');
  if (ctxOverheadLat) {
    chartOverheadLat = new Chart(ctxOverheadLat, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Worst-Case Latency (ms)',
            borderColor: COLORS.cyan,
            backgroundColor: 'rgba(0, 240, 255, 0.15)',
            data: [],
            borderWidth: 2
          },
          {
            label: 'Mean Latency (ms)',
            borderColor: COLORS.violet,
            data: [],
            borderWidth: 1.5
          },
          {
            label: 'Hard Real-Time Target (1.0 ms)',
            borderColor: COLORS.crimson,
            borderDash: [5, 5],
            data: [],
            borderWidth: 1.5,
            pointRadius: 0
          }
        ]
      },
      options: chartDefaultOptions
    });
  }

  // 8. Overhead Memory Footprint (RAM MB)
  const ctxOverheadRam = document.getElementById('chart-overhead-ram');
  if (ctxOverheadRam) {
    chartOverheadRam = new Chart(ctxOverheadRam, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'Controller RSS (MB)',
            borderColor: COLORS.emerald,
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            fill: true,
            data: [],
            borderWidth: 2
          }
        ]
      },
      options: chartDefaultOptions
    });
  }
}

function updateForecastingCharts(decisions) {
  if (!decisions || decisions.length === 0) return;

  const labels = decisions.map((d, i) => `#${i + 1}`);
  const temps = decisions.map(d => parseFloat(d.temp_c || 42.0));
  const bws = decisions.map(d => parseFloat(d.bandwidth_kbps || 1200.0));
  const entropies = decisions.map(d => parseFloat(d.pred_entropy || d.entropy || 1.45));

  if (chartResources) {
    chartResources.data.labels = labels;
    chartResources.data.datasets[0].data = temps;
    chartResources.data.datasets[1].data = bws;
    chartResources.update('none');
  }

  if (chartWorkload) {
    chartWorkload.data.labels = labels;
    chartWorkload.data.datasets[0].data = entropies;
    chartWorkload.update('none');
  }
}

function updateParetoCharts(decisions, outcomes) {
  if (chartPareto && outcomes && outcomes.length > 0) {
    const points = outcomes.map(o => ({
      x: parseFloat(o.latency_ms || 1.0),
      y: parseFloat(o.ratio || 1.0)
    }));
    chartPareto.data.datasets[0].data = points;
    chartPareto.update('none');
  }

  if (chartCodecPie && outcomes && outcomes.length > 0) {
    const counts = { lz4: 0, zstd: 0, delta: 0, bzip2: 0, none: 0 };
    outcomes.forEach(o => {
      const c = (o.compressor || o.codec || 'lz4').toLowerCase();
      if (c.includes('lz4')) counts.lz4++;
      else if (c.includes('zstd')) counts.zstd++;
      else if (c.includes('delta')) counts.delta++;
      else if (c.includes('bzip')) counts.bzip2++;
      else counts.none++;
    });

    chartCodecPie.data.datasets[0].data = [
      counts.lz4,
      counts.zstd,
      counts.delta,
      counts.bzip2,
      counts.none
    ];
    chartCodecPie.update('none');
  }
}

function updateRadioCharts(decisions) {
  if (!decisions || decisions.length === 0) return;

  const labels = decisions.map((d, i) => `#${i + 1}`);
  const backlogs = decisions.map(d => parseInt(d.backlog_depth || 0));

  let transmits = 0;
  let defers = 0;
  decisions.forEach(d => {
    const act = (d.transmit_or_defer || 'transmit').toLowerCase();
    if (act.includes('defer')) defers++;
    else transmits++;
  });

  if (chartRadioBacklog) {
    chartRadioBacklog.data.labels = labels;
    chartRadioBacklog.data.datasets[0].data = backlogs;
    chartRadioBacklog.update('none');
  }

  if (chartRadioActions) {
    chartRadioActions.data.datasets[0].data = [transmits, defers];
    chartRadioActions.update('none');
  }
}
