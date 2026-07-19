const sendBtn = document.getElementById("sendBtn");
const statusText = document.getElementById("statusText");
const titleContainer = document.getElementById("titleContainer");
const formatSelect = document.getElementById("formatSelect");
const warningContainer = document.getElementById("warningContainer");

let activeTabUrl = "";
let activeTabTitle = "";
let netscapeCookies = "";
let inspectedTitle = "";
let exportTvEnabled = false;

// Netscape converter helper
function convertToNetscape(cookies) {
  if (!cookies || cookies.length === 0) return "";
  let output = "# Netscape HTTP Cookie File\n# http://curl.haxx.se/rfc/cookie_spec.html\n# This is a generated file! Do not edit.\n\n";
  for (let c of cookies) {
    let domain = c.domain;
    let includeSubdomains = domain.startsWith(".") ? "TRUE" : "FALSE";
    let path = c.path || "/";
    let secure = c.secure ? "TRUE" : "FALSE";
    let expirationDate = c.expirationDate ? Math.round(c.expirationDate) : 0;
    let name = c.name;
    let value = c.value;
    
    output += `${domain}\t${includeSubdomains}\t${path}\t${secure}\t${expirationDate}\t${name}\t${value}\n`;
  }
  return output;
}

// Map height to label (matches desktop app format mapping)
function mapHeightToLabel(height) {
  if (height >= 2160) return "4K (2160p)";
  if (height >= 1440) return "2K (1440p)";
  if (height >= 1080) return "1080p";
  if (height >= 720) return "720p";
  if (height >= 480) return "480p";
  return `${height}p`;
}

function checkResolutionWarning() {
  if (!warningContainer) return;
  const chosenResolution = formatSelect.value;
  let isAbove1080 = false;
  
  if (chosenResolution === "Default (Best)") {
    isAbove1080 = true;
  } else {
    const match = chosenResolution.match(/(\d+)p/);
    if (match) {
      const height = parseInt(match[1], 10);
      if (height > 1080) {
        isAbove1080 = true;
      }
    }
  }
  
  if (exportTvEnabled && isAbove1080) {
    warningContainer.style.display = "block";
  } else {
    warningContainer.style.display = "none";
  }
}

formatSelect.addEventListener("change", checkResolutionWarning);

// Populate dropdown with fallback standard resolutions
function populateFallbackResolutions() {
  formatSelect.innerHTML = "";
  const fallbacks = [
    { value: "Default (Best)", label: "Default (Best Quality)" },
    { value: "1080p", label: "1080p Full HD" },
    { value: "720p", label: "720p HD" },
    { value: "480p", label: "480p SD" },
    { value: "Audio Only (MP3)", label: "Audio Only (MP3)" }
  ];
  for (let opt of fallbacks) {
    let el = document.createElement("option");
    el.value = opt.value;
    el.textContent = opt.label;
    formatSelect.appendChild(el);
  }
  formatSelect.value = "Default (Best)";
  formatSelect.disabled = false;
  sendBtn.disabled = false;
  checkResolutionWarning();
}

// Initialize active tab details and query inspection
async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) {
    titleContainer.textContent = "Error: Active tab not found.";
    statusText.textContent = "Downloader App: Error ❌";
    return;
  }
  
  activeTabUrl = tab.url;
  activeTabTitle = tab.title;
  inspectedTitle = tab.title; // fallback
  
  // 1. Check if desktop application is running
  fetch("http://127.0.0.1:8283/")
    .then(res => res.json())
    .then(data => {
      if (data.status === "running") {
        statusText.textContent = "Downloader App: Connected ✅";
        statusText.style.color = "#A6E3A1";
        
        // App is connected, now grab cookies and request inspection
        titleContainer.textContent = "Inspecting media streams...";
        chrome.cookies.getAll({ url: activeTabUrl }, (cookies) => {
          netscapeCookies = convertToNetscape(cookies);
          runInspection();
        });
      }
    })
    .catch(err => {
      statusText.textContent = "Downloader App: Not Running ❌";
      statusText.style.color = "#F38BA8";
      titleContainer.textContent = "Please launch the desktop app first.";
    });
}

function runInspection() {
  fetch("http://127.0.0.1:8283/inspect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: activeTabUrl, cookies: netscapeCookies })
  })
  .then(res => res.json())
  .then(data => {
    // Capture export_tv status from python back-end
    exportTvEnabled = data.export_tv || false;
    
    if (data.success) {
      inspectedTitle = data.title;
      titleContainer.textContent = data.title;
      
      // Populate with inspected formats
      formatSelect.innerHTML = "";
      
      // Add dynamic formats
      if (data.resolutions && data.resolutions.length > 0) {
        // Add Default (Best) option
        let defOpt = document.createElement("option");
        defOpt.value = "Default (Best)";
        defOpt.textContent = "Default (Best Quality)";
        formatSelect.appendChild(defOpt);

        for (let resHeight of data.resolutions) {
          let el = document.createElement("option");
          el.value = `${resHeight}p`;
          el.textContent = mapHeightToLabel(resHeight);
          formatSelect.appendChild(el);
        }
      } else {
        // No custom resolutions returned, fall back to standard resolutions
        populateFallbackResolutions();
        return;
      }
      
      // Add Audio option at the end
      let audioOpt = document.createElement("option");
      audioOpt.value = "Audio Only (MP3)";
      audioOpt.textContent = "Audio Only (MP3)";
      formatSelect.appendChild(audioOpt);
      
      // Default selection
      formatSelect.value = "Default (Best)";
      formatSelect.disabled = false;
      sendBtn.disabled = false;
      checkResolutionWarning();
    } else {
      throw new Error(data.error);
    }
  })
  .catch(err => {
    // If inspection fails (e.g. timeout or non-media site), fall back to standard selectors
    console.warn("Inspection failed, using fallbacks:", err);
    titleContainer.textContent = activeTabTitle;
    populateFallbackResolutions();
  });
}

sendBtn.addEventListener("click", () => {
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending to Downloader...";
  
  const chosenResolution = formatSelect.value;
  
  fetch("http://127.0.0.1:8283/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: activeTabUrl,
      title: inspectedTitle,
      resolution: chosenResolution,
      cookies: netscapeCookies
    })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      sendBtn.textContent = "Sent to App Successfully! 🎉";
      sendBtn.style.backgroundColor = "#A6E3A1";
      sendBtn.style.color = "#11111B";
      setTimeout(() => {
        window.close(); // Close extension popup automatically
      }, 1200);
    } else {
      throw new Error(data.error);
    }
  })
  .catch(err => {
    sendBtn.textContent = "Failed to Send!";
    sendBtn.style.backgroundColor = "#F38BA8";
    setTimeout(() => {
      sendBtn.disabled = false;
      sendBtn.textContent = "Send to Downloader";
      sendBtn.style.backgroundColor = "#89B4FA";
    }, 2000);
  });
});

// Run
init();
