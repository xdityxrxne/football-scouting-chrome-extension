// Toolbar button: grab the current Playmakerstats player page and send it to the local
// capture server (http://127.0.0.1:8765), which parses it into the Excel file.
// No automated browsing happens here: the person browses normally and clicks the button.

const SERVER = "http://127.0.0.1:8765/capture";
const PLAYER_URL = /^https:\/\/(www\.)?playmakerstats\.com\/player\/[^/]+\/\d+/;

function showToast(message, ok) {
  // Runs inside the page: small message in the top-right corner for a few seconds.
  const old = document.getElementById("spotter-toast");
  if (old) old.remove();
  const el = document.createElement("div");
  el.id = "spotter-toast";
  el.textContent = message;
  el.style.cssText =
    "position:fixed;top:16px;right:16px;z-index:2147483647;max-width:360px;" +
    "padding:12px 16px;border-radius:8px;font:14px/1.4 system-ui,sans-serif;color:#fff;" +
    "box-shadow:0 4px 16px rgba(0,0,0,.3);white-space:pre-line;" +
    (ok ? "background:#1b7f3b;" : "background:#b3261e;");
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ok ? 6000 : 10000);
}

function grabPage() {
  return { url: location.href, html: document.documentElement.outerHTML };
}

async function toast(tabId, message, ok) {
  try {
    await chrome.scripting.executeScript({ target: { tabId }, func: showToast, args: [message, ok] });
  } catch (e) {
    console.warn("toast failed", e);
  }
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab || !tab.id) return;
  if (!PLAYER_URL.test(tab.url || "")) {
    await toast(tab.id, "Open a Playmakerstats player page first, then click the button.", false);
    return;
  }
  await chrome.action.setBadgeText({ tabId: tab.id, text: "..." });
  try {
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: grabPage });
    const resp = await fetch(SERVER, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(result),
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok && data.ok) {
      const n = (data.missing || []).length;
      const extra = n ? ` (${n} field${n === 1 ? "" : "s"} missing)` : "";
      const review = data.needs_review ? "\nMarked 'Needs review' in the Excel file." : "";
      await toast(tab.id, `Saved: ${data.name}${extra}${review}`, true);
      await chrome.action.setBadgeText({ tabId: tab.id, text: "OK" });
    } else {
      await toast(tab.id, "Not saved: " + (data.error || `server error ${resp.status}`), false);
      await chrome.action.setBadgeText({ tabId: tab.id, text: "!" });
    }
  } catch (e) {
    await toast(
      tab.id,
      "Not saved: the Player Extractor is not running.\nDouble-click 'Player Extractor' on the Desktop, then try again.",
      false
    );
    await chrome.action.setBadgeText({ tabId: tab.id, text: "!" });
  }
  setTimeout(() => chrome.action.setBadgeText({ tabId: tab.id, text: "" }), 8000);
});
