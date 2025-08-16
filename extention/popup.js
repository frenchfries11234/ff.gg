// popup.js

document.addEventListener("DOMContentLoaded", () => {
  const output = document.getElementById("output");

  const isRosterUrl = (u) => {
    try {
      if (!u.hostname.includes("fantasy.espn.com")) return false;
      if (!/^\/football\/team\/?$/.test(u.pathname)) return false;
      const sp = u.searchParams;
      return !!sp.get("leagueId") && !!sp.get("teamId");
    } catch { return false; }
  };

  const showRosterHint = (extra = "") => {
    output.innerHTML = [
      "I couldn’t find your team/roster on this page.",
      "Please open your <b>Team Roster</b> page in this league, then click the button again.",
      '<small>URL should look like: <code>https://fantasy.espn.com/football/team?leagueId=...&teamId=...</code></small>',
      extra && `<div style="margin-top:6px;color:#666">${extra}</div>`
    ].filter(Boolean).join("<br/>");
  };

  const showActualError = (msg) => {
    output.innerHTML = `<b>Error:</b> ${msg}`;
  };

  // Send a message; if no receiver, inject content.js and retry once.
  function sendToContent(tabId, message) {
    return new Promise((resolve, reject) => {
      chrome.tabs.sendMessage(tabId, message, (res) => {
        if (chrome.runtime.lastError || !res) {
          // Try injecting the content script, then retry once
          chrome.scripting.executeScript(
            { target: { tabId }, files: ["content.js"] },
            () => {
              if (chrome.runtime.lastError) {
                return reject(new Error(chrome.runtime.lastError.message));
              }
              chrome.tabs.sendMessage(tabId, message, (res2) => {
                if (chrome.runtime.lastError || !res2) {
                  return reject(new Error(chrome.runtime.lastError?.message || "No response from content script"));
                }
                resolve(res2);
              });
            }
          );
        } else {
          resolve(res);
        }
      });
    });
  }

  document.getElementById("getTeamNameBtn").addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url) {
      output.textContent = "No active tab.";
      return;
    }

    const url = new URL(tab.url);

    if (!url.hostname.includes("fantasy.espn.com")) {
      output.innerHTML =
        `This extension only works on <a href="https://fantasy.espn.com" target="_blank" style="color: #0d6efd;">fantasy.espn.com</a>.`;
      return;
    }

    try {
      const response = await sendToContent(tab.id, { action: "getTeamName" });

      const hasTeam = Boolean(response?.teamName);
      const hasPlayers = Array.isArray(response?.players) && response.players.length > 0;

      if (!(hasTeam && hasPlayers)) {
        if (isRosterUrl(url)) {
          const dbg = response?.scrapeDebug;
          const details = dbg ? ` (cells=${dbg.cellCount ?? 0}, players=${dbg.playerCount ?? 0})` : "";
          // Show the *real* error with debug numbers so you know what's failing
          output.innerHTML = `<b>Error:</b> Roster not detected on this page${details}. Try refreshing; if it persists, ESPN likely changed the DOM.`;
        } else {
          showRosterHint();
        }
        return;
      }

      // === Success flow (auth + POST) ===
      chrome.identity.getAuthToken({ interactive: true }, (token) => {
        if (chrome.runtime.lastError || !token) {
          showActualError("Google auth error");
          return;
        }
        fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
          headers: { Authorization: "Bearer " + token },
        })
          .then((r) => r.json())
          .then((userInfo) => {
            fetch("http://localhost:10000/api/team", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                teamName: response.teamName,
                email: userInfo.email,
                seasonId: response.seasonId,
                leagueId: response.leagueId,
                leagueName: response.leagueName,
                teamId: response.teamId,
                players: response.players || [],
              }),
            });
            output.innerHTML =
              `Team: <a href="http://localhost:10000/teams" target="_blank" style="color: #4dabf7;">${response.teamName}</a><br/>` +
              `Players captured: ${response.players.length}`;
          })
          .catch(() => showActualError("Google auth error"));
      });
    } catch (err) {
      // Messaging failed twice (even after injection)
      if (isRosterUrl(url)) {
        showActualError(`Could not connect to page (${err.message}). Try reloading the tab and the extension.`);
      } else {
        showRosterHint("(Tip: open your team’s roster page for this league.)");
      }
    }
  });
});
