const stateEls = {
  phase: document.querySelector("#phase"),
  battery: document.querySelector("#battery"),
  altitude: document.querySelector("#altitude"),
  link: document.querySelector("#link"),
  gps: document.querySelector("#gps"),
  wind: document.querySelector("#wind"),
  reason: document.querySelector("#reason"),
  updated: document.querySelector("#updated"),
  obstacle: document.querySelector("#obstacle"),
  vibration: document.querySelector("#vibration"),
  temperature: document.querySelector("#temperature"),
  stabilization: document.querySelector("#stabilization"),
  eventCount: document.querySelector("#eventCount"),
  alerts: document.querySelector("#alerts"),
  manualToggle: document.querySelector("#manualToggle"),
  windSpeed: document.querySelector("#windSpeed"),
  windSpeedLabel: document.querySelector("#windSpeedLabel"),
  windGust: document.querySelector("#windGust"),
  windGustLabel: document.querySelector("#windGustLabel"),
};

const mapCanvas = document.querySelector("#map");
const mapCtx = mapCanvas.getContext("2d");
const videoCanvas = document.querySelector("#video");
const videoCtx = videoCanvas.getContext("2d");

let latest = null;

async function sendCommand(command, extra = {}) {
  await fetch("/api/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, ...extra }),
  });
  await refresh();
}

document.querySelectorAll("button[data-command]").forEach((button) => {
  button.addEventListener("click", () => sendCommand(button.dataset.command));
});

stateEls.manualToggle.addEventListener("change", () => {
  sendCommand("manual_override", { enabled: stateEls.manualToggle.checked });
});

let windTimer = null;
function queueWindUpdate() {
  clearTimeout(windTimer);
  stateEls.windSpeedLabel.textContent = `${Number(stateEls.windSpeed.value).toFixed(1)} m/s`;
  stateEls.windGustLabel.textContent = `${Number(stateEls.windGust.value).toFixed(1)} m/s`;
  windTimer = setTimeout(() => {
    sendCommand("wind", {
      speed_mps: Number(stateEls.windSpeed.value),
      gust_mps: Number(stateEls.windGust.value),
    });
  }, 160);
}

stateEls.windSpeed.addEventListener("input", queueWindUpdate);
stateEls.windGust.addEventListener("input", queueWindUpdate);

document.querySelectorAll("button[data-detection]").forEach((button) => {
  button.addEventListener("click", () => sendCommand("inject_detection", { kind: button.dataset.detection }));
});

async function refresh() {
  const response = await fetch("/api/state");
  latest = await response.json();
  renderState(latest);
  renderMap(latest);
  renderVideo(latest);
}

function renderState(state) {
  stateEls.phase.textContent = state.phase;
  stateEls.battery.textContent = `${state.battery_percent.toFixed(0)}%`;
  stateEls.altitude.textContent = `${state.altitude_m.toFixed(1)} m`;
  stateEls.link.textContent = `${state.link_quality.toFixed(0)}%`;
  stateEls.gps.textContent = `${state.gps_quality.toFixed(0)}%`;
  stateEls.wind.textContent = `${state.wind_speed_mps.toFixed(1)} m/s`;
  stateEls.reason.textContent = state.last_reason;
  stateEls.obstacle.value = state.obstacle_distance_m;
  stateEls.vibration.value = state.vibration;
  stateEls.temperature.value = state.temperature_c;
  stateEls.stabilization.value = state.stabilization_effort;
  stateEls.windSpeed.value = state.wind_speed_mps;
  stateEls.windGust.value = state.wind_gust_mps;
  stateEls.windSpeedLabel.textContent = `${state.wind_speed_mps.toFixed(1)} m/s`;
  stateEls.windGustLabel.textContent = `${state.wind_gust_mps.toFixed(1)} m/s`;
  stateEls.manualToggle.checked = state.manual_override;
  stateEls.updated.textContent = new Date(state.updated_at || Date.now()).toLocaleTimeString();
  stateEls.eventCount.textContent = `${state.events.length} events`;

  stateEls.alerts.innerHTML = "";
  const events = [...state.events].reverse().slice(0, 12);
  for (const event of events) {
    const item = document.createElement("li");
    item.className = event.severity;
    item.innerHTML = `<strong>${event.message}</strong><span>${event.kind} · ${(event.confidence * 100).toFixed(0)}% · (${event.x}, ${event.y})</span>`;
    stateEls.alerts.appendChild(item);
  }
}

function renderMap(state) {
  const w = mapCanvas.width;
  const h = mapCanvas.height;
  const pad = 48;
  const scaleX = (x) => pad + (x / 100) * (w - pad * 2);
  const scaleY = (y) => h - pad - (y / 100) * (h - pad * 2);
  const fence = state.config.geofence;

  mapCtx.clearRect(0, 0, w, h);
  mapCtx.fillStyle = "#0d1113";
  mapCtx.fillRect(0, 0, w, h);

  mapCtx.strokeStyle = "#26353a";
  mapCtx.lineWidth = 1;
  for (let i = 0; i <= 10; i += 1) {
    const x = pad + (i / 10) * (w - pad * 2);
    const y = pad + (i / 10) * (h - pad * 2);
    mapCtx.beginPath();
    mapCtx.moveTo(x, pad);
    mapCtx.lineTo(x, h - pad);
    mapCtx.moveTo(pad, y);
    mapCtx.lineTo(w - pad, y);
    mapCtx.stroke();
  }

  mapCtx.strokeStyle = "#63cdda";
  mapCtx.lineWidth = 3;
  mapCtx.strokeRect(
    scaleX(fence.min_x),
    scaleY(fence.max_y),
    scaleX(fence.max_x) - scaleX(fence.min_x),
    scaleY(fence.min_y) - scaleY(fence.max_y),
  );

  drawRoute(state, scaleX, scaleY);
  drawPath(state.path, scaleX, scaleY);
  drawEvents(state.events, scaleX, scaleY);
  drawDrone(state, scaleX, scaleY);
}

function drawRoute(state, scaleX, scaleY) {
  mapCtx.strokeStyle = "#f6c85f";
  mapCtx.setLineDash([8, 8]);
  mapCtx.lineWidth = 2;
  mapCtx.beginPath();
  state.config.waypoints.forEach((point, index) => {
    const x = scaleX(point.x);
    const y = scaleY(point.y);
    if (index === 0) mapCtx.moveTo(x, y);
    else mapCtx.lineTo(x, y);
  });
  mapCtx.stroke();
  mapCtx.setLineDash([]);

  state.config.waypoints.forEach((point, index) => {
    mapCtx.fillStyle = index === state.current_waypoint ? "#f6c85f" : "#8c7b43";
    mapCtx.beginPath();
    mapCtx.arc(scaleX(point.x), scaleY(point.y), 7, 0, Math.PI * 2);
    mapCtx.fill();
  });
}

function drawPath(path, scaleX, scaleY) {
  if (!path.length) return;
  mapCtx.strokeStyle = "#51d88a";
  mapCtx.lineWidth = 3;
  mapCtx.beginPath();
  path.forEach((point, index) => {
    const x = scaleX(point.x);
    const y = scaleY(point.y);
    if (index === 0) mapCtx.moveTo(x, y);
    else mapCtx.lineTo(x, y);
  });
  mapCtx.stroke();
}

function drawEvents(events, scaleX, scaleY) {
  for (const event of events.slice(-12)) {
    mapCtx.fillStyle = event.severity === "critical" ? "#ff6b64" : event.severity === "warning" ? "#f6c85f" : "#63cdda";
    mapCtx.beginPath();
    mapCtx.arc(scaleX(event.x), scaleY(event.y), 8, 0, Math.PI * 2);
    mapCtx.fill();
  }
}

function drawDrone(state, scaleX, scaleY) {
  const x = scaleX(state.x);
  const y = scaleY(state.y);
  mapCtx.save();
  mapCtx.translate(x, y);
  mapCtx.rotate((state.heading_deg * Math.PI) / 180);
  mapCtx.fillStyle = state.emergency_stop ? "#ff6b64" : "#eef5f2";
  mapCtx.beginPath();
  mapCtx.moveTo(18, 0);
  mapCtx.lineTo(-12, -10);
  mapCtx.lineTo(-7, 0);
  mapCtx.lineTo(-12, 10);
  mapCtx.closePath();
  mapCtx.fill();
  mapCtx.restore();

  mapCtx.fillStyle = "#a9bbb4";
  mapCtx.font = "14px system-ui";
  mapCtx.fillText(`${state.altitude_m.toFixed(0)} m`, x + 14, y - 14);

  mapCtx.strokeStyle = "#ff9f7a";
  mapCtx.lineWidth = 3;
  mapCtx.beginPath();
  mapCtx.moveTo(x, y);
  mapCtx.lineTo(x + state.wind_drift_x * 18, y - state.wind_drift_y * 18);
  mapCtx.stroke();
}

function renderVideo(state) {
  const w = videoCanvas.width;
  const h = videoCanvas.height;
  const t = Date.now() / 1000;
  const sky = videoCtx.createLinearGradient(0, 0, 0, h);
  sky.addColorStop(0, "#152b34");
  sky.addColorStop(0.58, "#1f3c3d");
  sky.addColorStop(1, "#17231b");
  videoCtx.fillStyle = sky;
  videoCtx.fillRect(0, 0, w, h);

  videoCtx.fillStyle = "#233d2d";
  for (let i = 0; i < 9; i += 1) {
    const x = ((i * 120 + t * 18 + state.x * 2) % (w + 140)) - 70;
    const y = h * 0.62 + Math.sin(i + t) * 12;
    videoCtx.fillRect(x, y, 80, h - y);
  }

  videoCtx.strokeStyle = "rgba(238, 245, 242, 0.28)";
  videoCtx.lineWidth = 2;
  videoCtx.strokeRect(w * 0.18, h * 0.18, w * 0.64, h * 0.56);
  videoCtx.beginPath();
  videoCtx.moveTo(w / 2 - 20, h / 2);
  videoCtx.lineTo(w / 2 + 20, h / 2);
  videoCtx.moveTo(w / 2, h / 2 - 20);
  videoCtx.lineTo(w / 2, h / 2 + 20);
  videoCtx.stroke();

  const recent = state.events[state.events.length - 1];
  if (recent) {
    const age = (Date.now() - Date.parse(recent.timestamp)) / 1000;
    if (age < 8) {
      const boxW = 150;
      const boxH = 88;
      const x = w * 0.52 + Math.sin(t) * 42;
      const y = h * 0.46 + Math.cos(t * 0.7) * 24;
      videoCtx.strokeStyle = recent.severity === "warning" ? "#f6c85f" : "#63cdda";
      videoCtx.lineWidth = 4;
      videoCtx.strokeRect(x, y, boxW, boxH);
      videoCtx.fillStyle = videoCtx.strokeStyle;
      videoCtx.font = "16px system-ui";
      videoCtx.fillText(`${recent.kind} ${(recent.confidence * 100).toFixed(0)}%`, x, y - 8);
    }
  }

  videoCtx.fillStyle = "rgba(16, 20, 23, 0.72)";
  videoCtx.fillRect(14, 14, 250, 70);
  videoCtx.fillStyle = "#eef5f2";
  videoCtx.font = "15px system-ui";
  videoCtx.fillText(`ALT ${state.altitude_m.toFixed(1)} m`, 28, 42);
  videoCtx.fillText(`HDG ${state.heading_deg.toFixed(0)} deg`, 28, 66);
  videoCtx.fillText(`ROLL ${state.roll_deg.toFixed(1)}`, 138, 42);
  videoCtx.fillText(`PITCH ${state.pitch_deg.toFixed(1)}`, 138, 66);
  videoCtx.fillText(state.phase, 28, 92);
}

setInterval(refresh, 700);
setInterval(() => latest && renderVideo(latest), 80);
refresh();
