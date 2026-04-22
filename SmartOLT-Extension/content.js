// content.js — Data Provider + Picker + Clean Values for SmartOLT regions

console.log("Content script injected & active");

let picking = false;
let activeRegionId = null;

// ---------------- HIGHLIGHT BOX (for picker) ----------------
const highlightBox = document.createElement("div");
highlightBox.style.position = "fixed";
highlightBox.style.zIndex = "999999999";
highlightBox.style.border = "2px solid red";
highlightBox.style.pointerEvents = "none";
highlightBox.style.display = "none";
document.body.appendChild(highlightBox);

// ---------------- CLEAN VALUE FILTER ----------------
function cleanValue(v) {
  if (!v) return null;

  v = v.trim();

  // Reject transient junk while SmartOLT reloads
  if (
    v === "" ||
    v === "-" ||
    v === "—" ||
    v.toUpperCase() === "N/A"
  ) {
    return null;
  }

  return v;
}

// ---------------- READ ALL REGIONS ----------------
async function readAllRegions() {
  try {
    return await new Promise(resolve => {
      chrome.storage.sync.get(["regions"], res => {
        const regions = res.regions || {};
        const data = {};

        for (const [id, info] of Object.entries(regions)) {
          try {
            const sel = info.selector;
            if (!sel || !sel.trim()) continue;

            const el = document.querySelector(sel);
            if (!el) continue;

            const raw = (el.innerText || el.textContent || "").trim();
            const value = cleanValue(raw);
            if (value == null) {
              console.warn("Skipping invalid value for", id, "raw:", raw);
              continue;
            }

            data[id] = {
              label: info.label,
              value
            };

          } catch (innerErr) {
            console.warn("Region read failed:", id, innerErr);
            continue;
          }
        }

        resolve(data);
      });
    });
  } catch (err) {
    console.error("FATAL ERROR IN readAllRegions — RECOVERING", err);
    return {}; // never break the monitor
  }
}

// ---------------- MESSAGE LISTENER ----------------
chrome.runtime.onMessage.addListener(async (msg) => {

  // Called by background.js → read all region values for real monitoring
  if (msg.type === "getValues") {
    const data = await readAllRegions();
    chrome.runtime.sendMessage({
      type: "valuesResponse",
      data
    });
  }

  // Popup test notification → current snapshot
  if (msg.type === "requestCurrentValues") {
    const data = await readAllRegions();
    chrome.runtime.sendMessage({
      type: "currentValues",
      values: data
    });
  }

  // Picker start
  if (msg.type === "startPicker") {
    startPicker(msg.regionId);
  }
});

// ---------------- PICKER LOGIC ----------------
function startPicker(regionId) {
  picking = true;
  activeRegionId = regionId;

  window.addEventListener("mouseover", onHover, true);
  window.addEventListener("mouseout", onLeave, true);
  window.addEventListener("click", onClick, true);

  console.log("Picker started for region:", regionId);
}

function onHover(e) {
  if (!picking) return;

  const el = e.composedPath()[0];
  if (!el || !el.getBoundingClientRect) return;

  const r = el.getBoundingClientRect();
  highlightBox.style.top = r.top + "px";
  highlightBox.style.left = r.left + "px";
  highlightBox.style.width = r.width + "px";
  highlightBox.style.height = r.height + "px";
  highlightBox.style.display = "block";
}

function onLeave() {
  if (picking) highlightBox.style.display = "none";
}

function onClick(e) {
  if (!picking) return;

  e.preventDefault();
  e.stopImmediatePropagation();

  const el = e.composedPath()[0];
  const selector = generateSelector(el);

  picking = false;
  highlightBox.style.display = "none";

  window.removeEventListener("mouseover", onHover, true);
  window.removeEventListener("mouseout", onLeave, true);
  window.removeEventListener("click", onClick, true);

  chrome.runtime.sendMessage({
    type: "elementPicked",
    regionId: activeRegionId,
    selector: selector
  });

  console.log("Region saved:", activeRegionId, selector);
}

// Generate a simple selector for picked element
function generateSelector(el) {
  if (!el) return null;

  if (el.id) return `#${el.id}`;

  if (el.className) {
    const cls = el.className.toString().trim().split(/\s+/).join(".");
    return `${el.tagName.toLowerCase()}.${cls}`;
  }

  return el.tagName.toLowerCase();
}
