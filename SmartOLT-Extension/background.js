// background.js – alarm + backend bridge + system log + notifications
// Uses backend at http://127.0.0.1:5005
// getValues is fire-and-forget: content.js sends valuesResponse via runtime.sendMessage.

const BACKEND_BASE = "http://127.0.0.1:5005";

let monitorEnabled    = false;
let monitorIntervalMs = 10000;
let monitorTimer      = null;

// ---------------- SYSTEM LOG → backend ----------------
function sendSystemLog(source, message) {
  fetch(`${BACKEND_BASE}/syslog`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, message })
  }).catch(err => {
    console.error("System log error:", err);
  });
}

// ---------------- HELPERS TO CALL BACKEND ----------------
function postToBackend(path, bodyObj) {
  fetch(`${BACKEND_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bodyObj || {})
  }).catch(err => {
    console.error(`Backend ${path} error:`, err);
    sendSystemLog("background", `Backend ${path} error: ${err}`);
  });
}

// ---------------- MONITOR TIMER ----------------
function startMonitorTimer() {
  if (monitorTimer) {
    clearInterval(monitorTimer);
    monitorTimer = null;
  }

  if (!monitorEnabled) {
    sendSystemLog("background", "Monitor timer not started because monitorEnabled=false");
    return;
  }

  monitorTimer = setInterval(() => {
    chrome.tabs.query(
      { url: "*://orient-net.smartolt.com/*" },
      tabs => {
        if (!tabs || !tabs.length) {
          sendSystemLog("background", "Monitoring tick: no SmartOLT tab found");
          return;
        }

        const tabId = tabs[0].id;
        const now   = new Date().toLocaleTimeString();

        try {
          chrome.tabs.sendMessage(tabId, { type: "getValues" });
          sendSystemLog("background", `Monitoring tick → sent getValues to tab ${tabId} at ${now}`);
        } catch (err) {
          console.error("Error calling sendMessage(getValues):", err);
          sendSystemLog("background", "Exception calling getValues: " + err);
        }
      }
    );
  }, monitorIntervalMs);

  sendSystemLog(
    "background",
    `Monitor timer started (interval=${monitorIntervalMs} ms, enabled=${monitorEnabled})`
  );
}

function stopMonitorTimer() {
  if (monitorTimer) {
    clearInterval(monitorTimer);
    monitorTimer = null;
    sendSystemLog("background", "Monitor timer stopped");
  }
}

// ---------------- INITIALIZATION ----------------
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["monitorEnabled", "monitorInterval"], res => {
    monitorEnabled    = !!res.monitorEnabled;
    monitorIntervalMs = res.monitorInterval || 10000;

    sendSystemLog(
      "background",
      `onInstalled: monitorEnabled=${monitorEnabled}, monitorIntervalMs=${monitorIntervalMs}`
    );

    if (monitorEnabled) {
      startMonitorTimer();
    }
  });
});

// ---------------- MESSAGE HANDLER ----------------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  // 1) Start / Stop from popup
  if (msg.type === "setMonitorEnabled") {
    monitorEnabled = !!msg.value;
    chrome.storage.sync.set({ monitorEnabled });

    if (monitorEnabled) {
      sendSystemLog("background", "Monitoring enabled via popup");
      startMonitorTimer();
    } else {
      sendSystemLog("background", "Monitoring disabled via popup");
      stopMonitorTimer();
    }
  }

  // 2) Interval change from popup
  if (msg.type === "setInterval") {
    monitorIntervalMs = Number(msg.value) || 10000;
    chrome.storage.sync.set({ monitorInterval: monitorIntervalMs });
    sendSystemLog("background", `Monitoring interval set to ${monitorIntervalMs} ms`);

    if (monitorEnabled) {
      startMonitorTimer();
    }
  }

  // 3) Values from content.js for REAL monitoring
  if (msg.type === "valuesResponse") {
    const data = msg.data || {};
    const now  = new Date().toLocaleTimeString();

    // -------------------------------------------
    // 🔵 BLUE LOG: TAG SPECIAL → server e printon blu
    // -------------------------------------------
    let formatted = [];
    for (const [key, v] of Object.entries(data)) {
      formatted.push(` • ${v.label}: ${v.value}`);
    }

    const msgBlue =
      "[BLUE] valuesResponse (" + Object.keys(data).length + " regions at " + now + "):\n" +
      formatted.join("\n");

    sendSystemLog("background", msgBlue);

    // -------------------------------------------
    // FIX LOG FOR 00000
    // -------------------------------------------
    try {
      const vals = Object.values(data).map(v => parseInt(v.value));
      const allZero = vals.length > 0 && vals.every(x => x === 0);

      if (allZero) {
        sendSystemLog(
          "background",
          "[BLUE] ⚠️ ALL ZERO (00000) → backend will perform RETRY 3×2s"
        );
      }
    } catch {}

    // Send values to backend
    postToBackend("/update", { data });
  }

  // 4) Test notification
  if (msg.type === "triggerBackendTest") {
    const payload = msg.data || {};
    sendSystemLog(
      "background",
      `triggerBackendTest → Online=${payload.online}, Total=${payload.total}, PwrFail=${payload.pwrfail}, LoS=${payload.los}, NA=${payload.na}`
    );
    postToBackend("/test", payload);
  }

  // 5) Legacy path
  if (msg.type === "regionsData") {
    const data = msg.data || {};
    sendSystemLog(
      "background",
      `regionsData → forwarding ${Object.keys(data).length} regions to /update`
    );
    postToBackend("/update", { data });
  }

  // 6) Forward popup/content logs
  if (msg.type === "systemLog") {
    const source  = msg.source  || "unknown";
    const message = msg.message || "";
    sendSystemLog(source, message);
  }

  return true;
});
