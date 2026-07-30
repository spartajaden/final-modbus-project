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
  shutdownServerBtn: document.querySelector("#shutdownServerBtn"),
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
  blueReportCount: document.querySelector("#blueReportCount"),
  greenReportCount: document.querySelector("#greenReportCount"),
  reportRange: document.querySelector("#reportRange"),
  machineAvg: document.querySelector("#machineAvg"),
  machineDoneCount: document.querySelector("#machineDoneCount"),
  pusherAvg: document.querySelector("#pusherAvg"),
  pusherDoneCount: document.querySelector("#pusherDoneCount"),
  eventTableBody: document.querySelector("#eventTableBody"),
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
  els.shutdownServerBtn.disabled = isBusy;
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
  let response;
  try {
    response = await fetch(url, options);
  } catch (fetchError) {
    const error = new Error("서버가 꺼져 있습니다.");
    error.code = "server_process_off";
    throw error;
  }

  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.error || `Request failed: ${response.status}`);
    error.code = payload.code;
    error.statusPayload = payload.status;
    throw error;
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
    if (error.statusPayload) {
      renderStatus(error.statusPayload);
    }
    if (error.code === "factory_io_server_off" || error.code === "server_process_off") {
      renderBadge(els.connectionBadge, "서버 꺼짐", "warn");
      showToast("서버가 꺼져 있습니다.");
    } else {
      showToast(error.message);
    }
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

async function shutdownWebServer() {
  if (!window.confirm("웹 서버를 종료할까요? 종료 후에는 이 페이지를 새로 열 수 없습니다.")) {
    return;
  }

  try {
    setBusy(true);
    await requestJson("/api/shutdown", { method: "POST" });
    state.connected = false;
    state.running = false;
    renderBadge(els.connectionBadge, "서버 꺼짐", "warn");
    renderBadge(els.runBadge, "Stopped", "off");
    els.connectBtn.textContent = "연결";
    showToast("웹 서버를 종료했습니다.");
  } catch (error) {
    if (error.code === "server_process_off") {
      renderBadge(els.connectionBadge, "서버 꺼짐", "warn");
      showToast("서버가 꺼져 있습니다.");
    } else {
      showToast(error.message);
    }
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
  els.connectBtn.textContent = connected ? "연결 해제" : "연결";
  els.connectBtn.classList.toggle("danger", connected);
  els.connectBtn.classList.toggle("secondary", !connected);
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

  els.targetIp.textContent = "localhost";
  els.targetPort.textContent = status.target?.port ?? "-";
  els.visionValue.textContent = connected ? (modbus.vision_value ?? "-") : "Not connected";
  els.detectedColor.textContent = connected ? colorFromSnapshot(snapshot) : "Not connected";
  els.pusherState.textContent = connected ? (modbus.pusher_busy ? "Active" : "Idle") : "Not connected";
  els.recordFile.textContent = status.modbus_record_file || "-";

  const blue = modbus.blue_count ?? status.counts?.blue ?? 0;
  const green = modbus.green_count ?? status.counts?.green ?? 0;
  els.blueCount.textContent = blue;
  els.greenCount.textContent = green;
  els.blueReportCount.textContent = blue;
  els.greenReportCount.textContent = green;
  updateReportStats();

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
  } else {
    previous.time = next.time;
  }

  if (state.history.length > 80) {
    state.history.shift();
  }
}

function updateReportStats(fileCount = null) {
  const history = state.history;
  const first = history[0];
  const last = history[history.length - 1];
  const blue = Number(els.blueCount.textContent || 0);
  const green = Number(els.greenCount.textContent || 0);
  const total = blue + green;
  const rangeText = first && last
    ? `${formatFullDate(first.time)} ~ ${formatFullDate(last.time)}`
    : "-";
  const csvCount = fileCount ?? Number(els.reportRange.dataset.csvCount || 0);

  els.reportRange.dataset.csvCount = String(csvCount);
  els.reportRange.textContent = `기록 범위: ${rangeText} · CSV ${csvCount}개`;

  const elapsedSeconds = first && last ? Math.max(0, (last.time - first.time) / 1000) : 0;
  const machineDone = total > 0 ? total : 0;
  const pusherDone = blue > 0 ? blue : 0;
  const machineAvg = machineDone > 1 && elapsedSeconds > 0 ? elapsedSeconds / machineDone : null;
  const pusherAvg = pusherDone > 1 && elapsedSeconds > 0 ? elapsedSeconds / pusherDone : null;

  els.machineAvg.textContent = machineAvg ? `${machineAvg.toFixed(2)} s` : "-";
  els.machineDoneCount.textContent = `${machineDone}회 완료`;
  els.pusherAvg.textContent = pusherAvg ? `${pusherAvg.toFixed(2)} s` : "-";
  els.pusherDoneCount.textContent = `${pusherDone}회 완료`;

  const rows = [
    ["state_change", Math.max(0, history.length - 1)],
    ["blue_counted", blue],
    ["green_counted", green],
    ["machine_done", machineDone],
    ["pusher_cycle_done", pusherDone],
  ];

  els.eventTableBody.innerHTML = rows
    .map(([name, count]) => `<tr><td>${name}</td><td>${count}</td></tr>`)
    .join("");
}

function drawChart() {
  const canvas = els.chart;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  ctx.scale(ratio, ratio);

  const width = rect.width;
  const height = rect.height;
  const leftPad = 46;
  const rightPad = 72;
  const topPad = 22;
  const bottomPad = 42;
  const plotLeft = leftPad;
  const plotRight = width - rightPad;
  const plotTop = topPad;
  const plotBottom = height - bottomPad;
  const plotWidth = plotRight - plotLeft;
  const plotHeight = plotBottom - plotTop;
  const history = state.history.length ? state.history : [{ time: new Date(), blue: 0, green: 0 }];
  const maxSeen = Math.max(1, ...history.flatMap((item) => [item.blue, item.green]));
  const maxValue = Math.max(10, Math.ceil((maxSeen + 1) / 2) * 2);

  ctx.clearRect(0, 0, width, height);

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#e8edf3";
  ctx.lineWidth = 1;
  const yStep = maxValue <= 12 ? 1 : 2;
  for (let value = 0; value <= maxValue; value += yStep) {
    const y = plotBottom - (value / maxValue) * plotHeight;
    ctx.beginPath();
    ctx.moveTo(plotLeft, y);
    ctx.lineTo(plotRight, y);
    ctx.stroke();
  }

  ctx.fillStyle = "#64748b";
  ctx.font = "12px Segoe UI, Arial";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let value = 0; value <= maxValue; value += yStep) {
    const y = plotBottom - (value / maxValue) * plotHeight;
    ctx.fillText(String(value), plotLeft - 25, y);
  }

  function xFor(index) {
    if (history.length === 1) {
      return plotLeft;
    }
    return plotLeft + (plotWidth / (history.length - 1)) * index;
  }

  function yFor(value) {
    return plotBottom - (value / maxValue) * plotHeight;
  }

  function drawArea(key, color) {
    if (!history.length) {
      return;
    }
    const gradient = ctx.createLinearGradient(0, plotTop, 0, plotBottom);
    gradient.addColorStop(0, color.replace("1)", "0.18)"));
    gradient.addColorStop(1, color.replace("1)", "0.02)"));
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.moveTo(xFor(0), plotBottom);
    history.forEach((item, index) => {
      const x = xFor(index);
      const y = yFor(item[key]);
      if (index === 0) {
        ctx.lineTo(x, y);
      } else {
        const previous = history[index - 1];
        const prevX = xFor(index - 1);
        const prevY = yFor(previous[key]);
        const midX = prevX + (x - prevX) * 0.5;
        ctx.lineTo(midX, prevY);
        ctx.lineTo(midX, y);
        ctx.lineTo(x, y);
      }
    });
    ctx.lineTo(xFor(history.length - 1), plotBottom);
    ctx.closePath();
    ctx.fill();
  }

  function drawStepLine(key, color, labelOffset) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 3.2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    history.forEach((item, index) => {
      const x = xFor(index);
      const y = yFor(item[key]);
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        const previous = history[index - 1];
        const prevX = xFor(index - 1);
        const prevY = yFor(previous[key]);
        const midX = prevX + (x - prevX) * 0.5;
        ctx.lineTo(midX, prevY);
        ctx.lineTo(midX, y);
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    const last = history[history.length - 1];
    const lastX = xFor(history.length - 1);
    const lastY = yFor(last[key]);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = color;
    ctx.font = "700 12px Segoe UI, Arial";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(`${key === "blue" ? "Blue" : "Green"} ${last[key]}`, lastX + 10, lastY + labelOffset);
  }

  drawArea("green", "rgba(37, 166, 106, 1)");
  drawArea("blue", "rgba(47, 126, 216, 1)");
  drawStepLine("green", "#25a66a", -12);
  drawStepLine("blue", "#2f7ed8", 12);

  ctx.strokeStyle = "#d4dae3";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(plotLeft, plotBottom);
  ctx.lineTo(plotRight, plotBottom);
  ctx.stroke();

  const firstTime = history[0]?.time instanceof Date ? history[0].time : new Date();
  const lastTime = history[history.length - 1]?.time instanceof Date ? history[history.length - 1].time : firstTime;
  const timeFormat = new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  ctx.fillStyle = "#64748b";
  ctx.font = "12px Segoe UI, Arial";
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  ctx.fillText(timeFormat.format(firstTime), plotLeft, plotBottom + 22);
  ctx.textAlign = "right";
  ctx.fillText(timeFormat.format(lastTime), plotRight, plotBottom + 22);
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

function formatFullDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

async function refreshSnapshot() {
  try {
    const snapshot = await requestJson("/api/snapshot");
    renderStatus(snapshot.status, snapshot);
    addHistory(snapshot);
    updateReportStats();
    drawChart();
  } catch (error) {
    if (error.code === "server_process_off") {
      renderBadge(els.connectionBadge, "서버 꺼짐", "warn");
      return;
    }

    try {
      const status = await requestJson("/api/status");
      renderStatus(status);
      addHistory({ status, modbus: {} });
      updateReportStats();
      drawChart();
    } catch (statusError) {
      if (statusError.code === "server_process_off") {
        renderBadge(els.connectionBadge, "서버 꺼짐", "warn");
      }
    }
  }
}

async function refreshRecords() {
  try {
    const payload = await requestJson("/api/records");
    const files = payload.files || [];
    els.downloadLatestBtn.disabled = files.length === 0;
    updateReportStats(files.length);

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
  if (state.connected) {
    postAction("/api/disconnect", "Factory I/O disconnected.");
  } else {
    postAction("/api/connect", "Factory I/O connection checked.");
  }
});

els.startBtn.addEventListener("click", () => {
  postAction("/api/start", "Process started.");
});

els.stopBtn.addEventListener("click", () => {
  postAction("/api/stop", "Process stopped.");
});

els.shutdownServerBtn.addEventListener("click", () => {
  shutdownWebServer();
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
