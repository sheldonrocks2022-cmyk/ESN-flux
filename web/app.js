const API = (window.ESN_FLUX_API_BASE || "").replace(/\/$/, "");
const $ = id => document.getElementById(id);

function setConnection(text, healthy = true) {
  $("connection").textContent = text;
  $("connection").style.borderColor = healthy ? "#168c8c" : "#7a2630";
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function drawChart(samples) {
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = rect.width * ratio;
  canvas.height = 220 * ratio;
  ctx.scale(ratio, ratio);
  const width = rect.width;
  const height = 220;
  ctx.clearRect(0, 0, width, height);
  const points = [...samples].reverse().slice(-60);
  if (!points.length) return;
  const max = Math.max(1, ...points.map(p => Number(p.players) || 0));
  ctx.strokeStyle = "#42e8f4";
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = height - ((Number(point.players) || 0) / max) * (height - 20) - 10;
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

async function getJSON(path) {
  const response = await fetch(`${API}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function refresh() {
  try {
    const [status, stats, history] = await Promise.all([
      getJSON("/api/smp/status"),
      getJSON("/api/smp/stats?limit=500"),
      getJSON("/api/smp/history?limit=60")
    ]);

    const online = Boolean(status.online);
    $("server-status").textContent = online ? "ONLINE" : "OFFLINE";
    $("server-status").style.color = online ? "#42e8f4" : "#ff5d66";
    $("server-detail").textContent = online ? "Flux can reach the SMP" : (status.error || "SMP is unreachable");
    $("players").textContent = status.players ?? 0;
    $("latency").textContent = status.latency_ms == null ? "—" : `${Math.round(status.latency_ms)} ms`;
    $("peak").textContent = stats.peak_players ?? 0;
    $("uptime").textContent = `${stats.uptime_pct ?? 0}%`;
    $("average-players").textContent = stats.average_players ?? 0;
    $("average-latency").textContent = stats.average_latency_ms == null ? "—" : `${stats.average_latency_ms} ms`;
    $("samples").textContent = stats.sample_count ?? 0;
    $("checked").textContent = `Updated ${formatTime(status.checked_at)}`;

    const players = status.player_names || [];
    $("player-list").innerHTML = players.length
      ? players.map(name => `<div class="player">${escapeHTML(name)}</div>`).join("")
      : `<div class="empty">${online && status.players > 0 ? "Player names are temporarily unavailable." : "No players online."}</div>`;
    drawChart(history.samples || []);
    setConnection("LIVE", true);
  } catch (error) {
    setConnection("API ERROR", false);
    $("server-detail").textContent = error.message;
  }
}

function escapeHTML(value) {
  return String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));
}

refresh();
setInterval(refresh, 30000);
window.addEventListener("resize", refresh);
