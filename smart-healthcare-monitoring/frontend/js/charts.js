const charts = {};

function makeChart(id, label, color) {
  if (!window.Chart) throw new Error("Chart.js did not load. Check the browser connection and reload.");
  const context = document.getElementById(id).getContext("2d");
  return new window.Chart(context, {
    type: "line",
    data: { labels: [], datasets: [{ label, data: [], borderColor: color, backgroundColor: `${color}22`, fill: true, tension: 0.3, pointRadius: 2 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { intersect: false, mode: "index" },
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 6, maxRotation: 0 } } },
    },
  });
}

export function updateCharts(readings, risks) {
  if (!charts.heart) {
    charts.heart = makeChart("heart-chart", "BPM", "#e11d48");
    charts.spo2 = makeChart("spo2-chart", "SpO₂ %", "#2563eb");
    charts.temperature = makeChart("temperature-chart", "°C", "#ea580c");
    charts.risk = makeChart("risk-chart", "Risk score", "#0f6e5f");
  }
  const ordered = [...readings].sort((a, b) => a.Timestamp.localeCompare(b.Timestamp));
  const labels = ordered.map((item) => new Date(item.Timestamp).toLocaleTimeString());
  const byTimestamp = new Map(risks.map((item) => [item.Timestamp, item.RiskScore]));
  const datasets = [
    [charts.heart, ordered.map((item) => item.HeartRate)],
    [charts.spo2, ordered.map((item) => item.SpO2)],
    [charts.temperature, ordered.map((item) => item.Temperature)],
    [charts.risk, ordered.map((item) => byTimestamp.get(item.Timestamp) ?? null)],
  ];
  for (const [chart, values] of datasets) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update("none");
  }
}
