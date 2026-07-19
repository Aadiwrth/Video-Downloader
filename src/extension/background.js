chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "download-link",
    title: "Download link with Video Downloader",
    contexts: ["link", "video", "audio"]
  });
  
  chrome.contextMenus.create({
    id: "download-page",
    title: "Download active page with Video Downloader",
    contexts: ["page"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  let url = "";
  let title = tab ? tab.title : "";
  
  if (info.menuItemId === "download-link") {
    url = info.linkUrl;
    title = "Link Download";
  } else if (info.menuItemId === "download-page") {
    url = info.pageUrl;
  }
  
  if (url) {
    // Attempt to get cookies for the URL domain
    chrome.cookies.getAll({ url: url }, (cookies) => {
      const netscapeCookies = convertToNetscape(cookies);
      sendToDownloader(url, title, netscapeCookies);
    });
  }
});

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

function sendToDownloader(url, title, cookiesStr) {
  fetch("http://127.0.0.1:8283/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ 
      url: url, 
      title: title,
      cookies: cookiesStr 
    })
  })
  .then(response => response.json())
  .then(data => {
    console.log("Success:", data);
  })
  .catch((error) => {
    console.error("Error sending URL to downloader:", error);
  });
}
