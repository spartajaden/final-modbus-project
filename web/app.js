const THREE_HOURS_MS = 3 * 60 * 60 * 1000;

const state = {
  busy: false,
  connected: false,
  running: false,
  history: [],
  nextRecordAt: Date.now() + THREE_HOURS_MS,
};

const els = {
  connectBtn: document.querySelector("#connectBtn"),
  startBtn: document.querySelector("#startBtn"),
  stopBtn: document.querySelector("#stopBtn"),
  createRecordBtn: document.querySelector("#createRecordBtn"),
  downloadLatestBtn: document.querySelector("#downloadLatestBtn"),
  connectionBadge: document.querySelector("#connectionBadge"),
  runBadge: document.querySelector("#runBadge"),
  factoryScene: document.querySelector("#factoryScene"),
  productionLamp: document.querySelector("#productionLamp"),
  sortingLamp: document.querySelector("#sortingLamp"),
  pusherArm: document.querySelector("#pusherArm"),
  targetIp: document.querySelector("#targetIp"),
  targetPort: document.querySelector("#targetPort"),
  visionValue: document.querySelector("#visionValue"),
  detectedColor: document.querySelector("#detectedColor"),
  pusherState: document.querySelector("#pusherState"),
  recordFile: document.querySelector("#recordFile"),
  blueCount: document.querySelector("#blueCount"),
  greenCount: document.querySelector("#greenCount"),
  chart: document.querySelector("#countChart"),
  recordTimer: document.querySelector("#recordTimer"),
  recordList: document.querySelector("#recordList"),
  toast: document.querySelector("#toast"),
};

function setBusy(isBusy) {
  state.busy = isBusy;
  els.connectBtn.disabled = isBusy;
  els.startBtn.disabled = isBusy || !state.connected;
  els.stopBtn.disabled = isBusy || (!state.connected && !state.running);
  els.createRecordBtn.disabled = isBusy;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.classList.remove("show");
  }, 3200);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function postAction(path, successMessage) {
  try {
    setBusy(true);
    const status = await requestJson(path, { method: "POST" });
    if (path === "/api/start") {
      state.history = [];
    }
    renderStatus(status);
    showToast(successMessage);
    await refreshSnapshot();
    await refreshRecords();
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

async function createRecordFile(isAutomatic = false) {
  try {
    setBusy(true);
    const payload = await requestJson("/api/records/new", { method: "POST" });
    state.nextRecordAt = Date.now() + THREE_HOURS_MS;
    renderStatus(payload.status);
    await refreshRecords();
    showToast(isAutomatic ? "Auto CSV file created." : "New CSV file created.");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

function colorFromSnapshot(snapshot) {
  const modbus = snapshot?.modbus;
  if (!modbus) {
    return "-";
  }
  if (modbus.blue_detected) {
    return "Blue";
  }
  if (modbus.vision_value === 4) {
    return "Green";
  }
  if (modbus.vision_value === 0 || modbus.vision_value === false) {
    return "None";
  }
  return "Unknown";
}

function renderBadge(element, text, mode) {
  element.textContent = text;
  element.classList.remove("on", "off", "warn");
  element.classList.add(mode);
}

function renderStatus(status, snapshot = null) {
  const connected = Boolean(status.connected);
  state.connected = connected;
  state.running = Boolean(status.running);

  renderBadge(
    els.connectionBadge,
    connected ? "Modbus connected" : "Click Connect",
    connected ? "on" : "warn",
  );
  renderBadge(
    els.runBadge,
    state.running ? "Running" : "Stopped",
    state.running ? "on" : "off",
  );

  els.factoryScene.classList.toggle("running", state.running);
  els.factoryScene.classList.toggle("stopped", !state.running);
  els.productionLamp.classList.toggle("on", Boolean(status.threads?.production));
  els.sortingLamp.classList.toggle("on", Boolean(status.threads?.sorting));

  const modbus = snapshot?.modbus || {};
  els.pusherArm.classList.toggle("active", Boolean(modbus.pusher_busy));

  els.targetIp.textContent = status.target?.ip_address || "-";
  els.targetPort.textContent = status.target?.port ?? "-";
  els.visionValue.textContent = connected ? (modbus.vision_value ?? "-") : "Not connected";
  els.detectedColor.textContent = connected ? colorFromSnapshot(snapshot) : "Not connected";
  els.pusherState.textContent = connected ? (modbus.pusher_busy ? "Active" : "Idle") : "Not connected";
  els.recordFile.textContent = status.modbus_record_file || "-";

  const blue = modbus.blue_count ?? status.counts?.blue ?? 0;
  const green = modbus.green_count ?? status.counts?.green ?? 0;
  els.blueCount.textContent = blue;
  els.greenCount.textContent = green;

  if (!state.busy) {
    els.startBtn.disabled = !connected;
    els.stopBtn.disabled = !connected && !state.running;
  }
}

function addHistory(snapshot) {
  const status = snapshot.status || {};
  const modbus = snapshot.modbus || {};
  const next = {
    time: new Date(),
    blue: modbus.blue_count ?? status.counts?.blue ?? 0,
    green: modbus.green_count ?? status.counts?.green ?? 0,
  };

  const previous = state.history[state.history.length - 1];
  if (!previous || previous.blue !== next.blue || previous.green !== next.green) {
    state.history.push(next);
  } else if (state.history.length === 0) {
    state.history.push(next);
  }

  if (state.history.length > 40) {
    state.history.shift();
  }
}

function drawChart() {
  const canvas = els.chart;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(320 * ratio));
  ctx.scale(ratio, ratio);

  const width = rect.width;
  const height = 320;
  const pad = 42;
  const plotWidth = width - pad * 2;
  const plotHeight = height - pad * 2;
  const history = state.history.length ? state.history : [{ blue: 0, green: 0 }];
  const maxValue = Math.max(5, ...history.flatMap((item) => [item.blue, item.green]));

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#d8e0ec";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= 5; i += 1) {
    const y = pad + (plotHeight / 5) * i;
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
  }
  ctx.stroke();

  ctx.fillStyle = "#667085";
  ctx.font = "12px Segoe UI, Arial";
  for (let i = 0; i <= 5; i += 1) {
    const value = Math.round(maxValue - (maxValue / 5) * i);
    const y = pad + (plotHeight / 5) * i + 4;
    ctx.fillText(String(value), 10, y);
  }

  function drawLine(key, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    history.forEach((item, index) => {
      const x = pad + (history.length === 1 ? 0 : (plotWidth / (history.length - 1)) * index);
      const y = pad + plotHeight - (item[key] / maxValue) * plotHeight;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    ctx.fillStyle = color;
    history.forEach((item, index) => {
      const x = pad + (history.length === 1 ? 0 : (plotWidth / (history.length - 1)) * index);
      const y = pad + plotHeight - (item[key] / maxValue) * plotHeight;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  drawLine("blue", "#2563eb");
  drawLine("green", "#159947");

  ctx.fillStyle = "#172033";
  ctx.font = "700 13px Segoe UI, Arial";
  ctx.fillText("Blue", width - 120, 24);
  ctx.fillText("Green", width - 70, 24);
}

function formatSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(seconds) {
  if (!seconds) {
    return "-";
  }
  return new Date(seconds * 1000).toLocaleString("ko-KR");
}

async function refreshSnapshot() {
  try {
    const snapshot = await requestJson("/api/snapshot");
    renderStatus(snapshot.status, snapshot);
    addHistory(snapshot);
    drawChart();
  } catch (error) {
    const status = await requestJson("/api/status");
    renderStatus(status);
    addHistory({ status, modbus: {} });
    drawChart();
  }
}

async function refreshRecords() {
  try {
    const payload = await requestJson("/api/records");
    const files = payload.files || [];
    els.downloadLatestBtn.disabled = files.length === 0;

    if (!files.length) {
      els.recordList.innerHTML = '<div class="record-row"><strong>No CSV files yet.</strong><span>Start the process or create a CSV file.</span></div>';
      return;
    }

    els.recordList.innerHTML = files
      .map(
        (file) => `
          <div class="record-row">
            <div>
              <strong>${file.name}</strong>
              <span>${formatDate(file.modified)} - ${formatSize(file.size)}</span>
            </div>
            <div class="record-buttons">
              <a class="download-link" href="/api/records/${encodeURIComponent(file.name)}">Download</a>
              <button class="delete-record" data-record="${file.name}">Delete</button>
            </div>
          </div>
        `,
      )
      .join("");
  } catch (error) {
    els.recordList.innerHTML = `<div class="record-row"><strong>${error.message}</strong></div>`;
  }
}

async function deleteRecordFile(name) {
  if (!window.confirm(`Delete ${name}?`)) {
    return;
  }

  try {
    setBusy(true);
    await requestJson(`/api/records/${encodeURIComponent(name)}`, { method: "DELETE" });
    await refreshRecords();
    showToast("CSV file deleted.");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

function updateRecordTimer() {
  const remaining = Math.max(0, state.nextRecordAt - Date.now());
  const totalSeconds = Math.ceil(remaining / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  els.recordTimer.textContent = `Next CSV auto-create: ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  if (remaining <= 0 && !state.busy) {
    state.nextRecordAt = Date.now() + THREE_HOURS_MS;
    createRecordFile(true);
  }
}

els.connectBtn.addEventListener("click", () => {
  postAction("/api/connect", "Factory I/O connection checked.");
});

els.startBtn.addEventListener("click", () => {
  postAction("/api/start", "Process started.");
});

els.stopBtn.addEventListener("click", () => {
  postAction("/api/stop", "Process stopped.");
});

els.createRecordBtn.addEventListener("click", () => {
  createRecordFile(false);
});

els.downloadLatestBtn.addEventListener("click", () => {
  window.location.href = "/api/records/latest";
});

els.recordList.addEventListener("click", (event) => {
  const button = event.target.closest(".delete-record");
  if (!button) {
    return;
  }
  deleteRecordFile(button.dataset.record);
});

window.addEventListener("resize", drawChart);

refreshSnapshot();
refreshRecords();
updateRecordTimer();
setInterval(refreshSnapshot, 1200);
setInterval(refreshRecords, 5000);
setInterval(updateRecordTimer, 1000);
