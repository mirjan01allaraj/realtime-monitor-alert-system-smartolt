let regions = {};
let activeTabId = null;
let labelHistory = [];
let logsIntervalHandle = null;

// DOM refs
const regionsDiv       = document.getElementById("regions");
const addBtn           = document.getElementById("addRegion");
const clearAllBtn      = document.getElementById("clearAll");
const testNotifBtn     = document.getElementById("testNotif");
const intervalSelector = document.getElementById("intervalSelector");
const statusIndicator  = document.getElementById("statusIndicator");
const lastUpdateTime   = document.getElementById("lastUpdateTime");
const startBtn         = document.getElementById("startBtn");
const stopBtn          = document.getElementById("stopBtn");

const notifLogPanel    = document.getElementById("notifLogPanel");
const systemLogPanel   = document.getElementById("systemLogPanel");
const toggleNotifBtn   = document.getElementById("toggleNotifLog");
const toggleSystemBtn  = document.getElementById("toggleSystemLog");
const exportLogBtn     = document.getElementById("exportSystemLog");

// ----- System log helper (popup → backend via background) -----
function logSystemPopup(message) {
  chrome.runtime.sendMessage({
    type: "systemLog",
    source: "popup",
    message
  });
}

// ---------------- INIT ----------------
document.addEventListener("DOMContentLoaded", () => {

  logSystemPopup("Popup opened");

  // Get active tab + ensure content.js injected
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    if (!tabs || !tabs[0]) {
      logSystemPopup("No active tab found on popup open");
      return;
    }
    activeTabId = tabs[0].id;

    chrome.scripting.executeScript(
      {
        target: { tabId: activeTabId },
        files: ["content.js"]
      },
      () => {
        logSystemPopup("content.js injected into tab " + activeTabId);
      }
    );
  });

  // Load stored config
  chrome.storage.sync.get(
    ["regions", "monitorInterval", "monitorEnabled", "labelHistory"],
    res => {
      regions      = res.regions || {};
      labelHistory = res.labelHistory || [];

      const savedInterval = res.monitorInterval || 10000;
      intervalSelector.value = savedInterval;

      const enabled = !!res.monitorEnabled;
      updateStatusDisplay(enabled);

      if (Object.keys(regions).length === 0) {
        regions = {
          region_online:  { label: "Online",        selector: "" },
          region_offline: { label: "Total offline", selector: "" }
        };
        chrome.storage.sync.set({ regions });
        logSystemPopup("Initialized default regions (Online + Total offline)");
      }

      refreshLabelHistoryList();
      renderRegions();
    }
  );

  // Wire buttons
  addBtn.onclick       = onAddRegion;
  clearAllBtn.onclick  = onClearAll;
  testNotifBtn.onclick = onTestNotification;

  startBtn.onclick = () => {
    chrome.storage.sync.set({ monitorEnabled: true });
    chrome.runtime.sendMessage({ type: "setMonitorEnabled", value: true });
    updateStatusDisplay(true);
    logSystemPopup("Monitoring START requested");
  };

  stopBtn.onclick = () => {
    chrome.storage.sync.set({ monitorEnabled: false });
    chrome.runtime.sendMessage({ type: "setMonitorEnabled", value: false });
    updateStatusDisplay(false);
    logSystemPopup("Monitoring STOP requested");
  };

  intervalSelector.onchange = () => {
    const ms = Number(intervalSelector.value);
    chrome.storage.sync.set({ monitorInterval: ms });
    chrome.runtime.sendMessage({ type: "setInterval", value: ms });
    logSystemPopup("Interval changed to " + ms + " ms");
  };

  toggleNotifBtn.onclick  = toggleNotifLog;
  toggleSystemBtn.onclick = toggleSystemLog;
  exportLogBtn.onclick    = exportSystemLog;

  // start logs polling
  startLogsPolling();
});

// ---------------- STATUS UI ----------------
function updateStatusDisplay(enabled) {
  statusIndicator.textContent = enabled ? "🟢 Running" : "🔴 Stopped";
}

// ---------------- LABEL HISTORY ----------------
function refreshLabelHistoryList() {
  const dl = document.getElementById("labelHistory");
  dl.innerHTML = "";
  labelHistory.forEach(lbl => {
    const opt = document.createElement("option");
    opt.value = lbl;
    dl.appendChild(opt);
  });
}

// ---------------- REGION RENDERING ----------------
function renderRegions() {
  regionsDiv.innerHTML = "";

  Object.entries(regions).forEach(([id, info]) => {
    const box = document.createElement("div");
    box.className = "region-box";
    box.dataset.id = id;

    box.innerHTML = `
      Label:
      <input list="labelHistory" class="label-input" value="${info.label || ""}">
      <br>
      Selector:
      <input class="selector-input" value="${info.selector || ""}" readonly>
      <button class="btn btn-pick">Pick</button>
    `;

    // label change
    box.querySelector(".label-input").oninput = e => {
      const val = e.target.value.trim();
      regions[id].label = val;
      chrome.storage.sync.set({ regions });

      if (val && !labelHistory.includes(val)) {
        labelHistory.push(val);
        chrome.storage.sync.set({ labelHistory });
        refreshLabelHistoryList();
      }
    };

    // pick element
    box.querySelector(".btn-pick").onclick = () => {
      if (!activeTabId) return;
      chrome.tabs.sendMessage(activeTabId, {
        type: "startPicker",
        regionId: id
      });
      logSystemPopup("Picker requested for region " + id);
    };

    regionsDiv.appendChild(box);
  });
}

// ---------------- BUTTON HANDLERS ----------------
function onAddRegion() {
  const id = "region_" + Date.now();
  regions[id] = { label: "", selector: "" };
  chrome.storage.sync.set({ regions });
  logSystemPopup("Added new region " + id);
  renderRegions();
}

function onClearAll() {
  if (!confirm("Clear all regions?")) return;
  regions = {};
  chrome.storage.sync.set({ regions });
  logSystemPopup("Cleared all regions");
  renderRegions();
}

function onTestNotification() {
  if (!activeTabId) return;
  logSystemPopup("User clicked Test Notification (Desktop + Telegram)");
  chrome.tabs.sendMessage(activeTabId, { type: "requestCurrentValues" });
}

// ---------------- LOG PANELS (LIVE) ----------------
function startLogsPolling() {
  if (logsIntervalHandle) return;

  logsIntervalHandle = setInterval(() => {
    fetch("http://127.0.0.1:5005/logs")
      .then(r => r.json())
      .then(data => {
        const notifLines  = data.notifications || [];
        const systemLines = data.system || [];
        renderNotifLog(notifLines);
        renderSystemLog(systemLines);
      })
      .catch(err => {
        if (systemLogPanel && systemLogPanel.style.display !== "none") {
          systemLogPanel.textContent = "Error loading logs: " + err;
        }
      });
  }, 1000);
}

function toggleNotifLog() {
  if (notifLogPanel.style.display === "none" || notifLogPanel.style.display === "") {
    notifLogPanel.style.display = "block";
    toggleNotifBtn.textContent = "Hide Log";
  } else {
    notifLogPanel.style.display = "none";
    toggleNotifBtn.textContent = "Show Log";
  }
}

function toggleSystemLog() {
  if (systemLogPanel.style.display === "none" || systemLogPanel.style.display === "") {
    systemLogPanel.style.display = "block";
    toggleSystemBtn.textContent = "Hide Log";
  } else {
    systemLogPanel.style.display = "none";
    toggleSystemBtn.textContent = "Show Log";
  }
}

function renderNotifLog(lines) {
  if (!notifLogPanel) return;
  notifLogPanel.innerHTML = "";

  lines.forEach(line => {
    const div = document.createElement("div");

    if (line.includes("Offline Increased") || line.includes("Online Dropped Alert")) {
      div.className = "log-line-error";
    } else if (line.includes("Clients Restored") || line.includes("Connectivity Restored")) {
      div.className = "log-line-success";
    } else if (line.includes("TEST NOTIFICATION")) {
      div.className = "log-line-info";
    } else if (line.includes("Monitor Started")) {
      div.className = "log-line-info";
    } else {
      div.className = "log-line-default";
    }

    div.textContent = line;
    notifLogPanel.appendChild(div);
  });

  notifLogPanel.scrollTop = notifLogPanel.scrollHeight;
}

function renderSystemLog(lines) {
  if (!systemLogPanel) return;
  systemLogPanel.innerHTML = "";

  lines.forEach(line => {
    const lower = line.toLowerCase();
    const div = document.createElement("div");

    // Highlight Telegram-specific statuses
    if (lower.includes("telegram sent ok")) {
      div.className = "log-line-success";
    } else if (lower.includes("telegram send failed") || lower.includes("telegram exception")) {
      div.className = "log-line-error";
    } else if (lower.includes("error") || lower.includes("failed") || lower.includes("fatal")) {
      div.className = "log-line-error";
    } else if (lower.includes("warn")) {
      div.className = "log-line-warn";
    } else if (lower.includes("started") || lower.includes("connected") || lower.includes("restored")) {
      div.className = "log-line-success";
    } else {
      div.className = "log-line-default";
    }

    div.textContent = line;
    systemLogPanel.appendChild(div);
  });

  systemLogPanel.scrollTop = systemLogPanel.scrollHeight;
}

// ---------------- EXPORT SYSTEM LOG ----------------
function exportSystemLog() {
  fetch("http://127.0.0.1:5005/export_system_log")
    .then(r => r.json())
    .then(data => {
      if (data.status === "ok") {
        alert("System log exported:\n" + data.file + "\n\nCheck the Logs folder next to monitor_server.py");
        logSystemPopup("System log exported to " + data.file);
      } else {
        alert("Export failed: " + (data.message || "Unknown error"));
        logSystemPopup("System log export failed: " + (data.message || "Unknown error"));
      }
    })
    .catch(err => {
      alert("Export failed: " + err);
      logSystemPopup("System log export error: " + err);
    });
}

// ---------------- MESSAGE HANDLER FROM BACKGROUND/CONTENT ----------------
chrome.runtime.onMessage.addListener(msg => {

  if (msg.type === "elementPicked") {
    const id = msg.regionId;
    if (!regions[id]) regions[id] = { label: "", selector: "" };
    regions[id].selector = msg.selector;
    chrome.storage.sync.set({ regions });
    logSystemPopup("Selector saved for " + id + " → " + msg.selector);
    renderRegions();
  }

  // Snapshot for Test Notification (Desktop + Telegram)
  if (msg.type === "currentValues") {
    lastUpdateTime.textContent = new Date().toLocaleTimeString();

    let online  = null;
    let total   = null;
    let pwrfail = null;
    let los     = null;
    let na      = null;

    const values = msg.values || {};

    Object.values(values).forEach(r => {
      const lbl = (r.label || "").toLowerCase().trim();

      if (lbl.includes("online") && !lbl.includes("offline")) {
        online = r.value;
      } else if (lbl.includes("total") && lbl.includes("offline")) {
        total = r.value;
      } else if (lbl.includes("pwr") || lbl.includes("power fail") || lbl.includes("pwrfail")) {
        pwrfail = r.value;
      } else if (lbl.includes("los")) {
        los = r.value;
      } else if (lbl === "n/a" || lbl === "na" || lbl.includes("n/a")) {
        na = r.value;
      }
    });

    logSystemPopup(
      "Test values → Online=" + online +
      ", Total=" + total +
      ", PwrFail=" + pwrfail +
      ", LoS=" + los +
      ", NA=" + na
    );

    chrome.runtime.sendMessage({
      type: "triggerBackendTest",
      data: { online, total, pwrfail, los, na }
    });
  }
});
