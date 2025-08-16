// content.js
(() => {
  'use strict';

  // Prevent double-injection (e.g., MAIN world executeScript + content script)
  if (window.__FF_EXT_CONTENT_ACTIVE__) return;
  window.__FF_EXT_CONTENT_ACTIVE__ = true;

  // --- helpers (scoped; safe to re-inject) ---
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const qtext = (root, sel) => {
    const el = root.querySelector(sel);
    return el ? el.textContent.trim() : null;
  };

  const isVisible = (el) => {
    if (!el) return false;
    const cs = window.getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") return false;
    if (el.closest('[aria-hidden="true"]')) return false;
    return el.getClientRects().length > 0;
  };

  // Roster cells (ESPN sometimes renders sticky/duplicate columns)
  const getPlayerCells = () => [
    ...document.querySelectorAll(".table--cell.player__column"),
    ...document.querySelectorAll(".player__column"),
  ];

  // Extract ESPN player id from link href (fallback)
  const extractIdFromHref = (href = "") => {
    const m =
      href.match(/\/id\/(\d+)\b/) ||                 // .../id/3040152/...
      href.match(/[?&]playerId=(\d+)\b/i) ||         // ?playerId=3040152
      href.match(/\/players\/[^/]*\/(\d+)\b/i);      // /players/xxx/3040152
    return m ? m[1] : null;
  };

  // Extract ESPN player id from headshot img src
  const extractIdFromHeadshot = (scopeEl) => {
    const row = scopeEl.closest("tr") || scopeEl;
    const img = row.querySelector('img[src*="headshots"][src*="/players/full/"]');
    const src = img?.getAttribute("src") || "";
    const m =
      src.match(/\/players\/full\/(\d+)\.png\b/i) ||
      src.match(/img=\/i\/headshots\/[^/]+\/players\/full\/(\d+)\.png\b/i);
    return m ? m[1] : null;
  };

  // Wait for visible roster cells
  const waitForRosterCells = async (timeoutMs = 4000) => {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) {
      const cells = getPlayerCells().filter(isVisible);
      if (cells.length > 0) return cells;
      await sleep(150);
    }
    return [];
  };

  // Build cleaned, de-duped player list
  const buildPlayersFromCells = (cells) => {
    const seen = new Set();
    const players = [];

    for (const el of cells) {
      const a = el.querySelector('.player-column__athlete a:not(.playerinfo__news)');
      const name = a?.textContent?.trim() || null;
      const team = qtext(el, ".playerinfo__playerteam");

      if (!name || !team || !name.trim() || !team.trim()) continue;

      const idFromHead = extractIdFromHeadshot(el);
      const idFromHref = extractIdFromHref(a?.getAttribute("href") || "");
      const espnId = idFromHead || idFromHref || null;

      const key = espnId || `${name}|${team}`;
      if (seen.has(key)) continue;
      seen.add(key);

      players.push({
        espnId,
        name: name.trim(),
        team: team.trim().toUpperCase(),
      });
    }
    return players;
  };

  // Generic wait helper (for late-rendered nodes)
  const waitFor = async (finder, timeout = 2500, step = 120) => {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      const node = finder();
      if (node) return node;
      await sleep(step);
    }
    return null;
  };

  // --- message handler ---
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action !== "getTeamName") return;

    (async () => {
      const url = new URL(window.location.href);
      const leagueId = url.searchParams.get("leagueId");
      const teamId = url.searchParams.get("teamId");
      const seasonId = url.searchParams.get("seasonId");

      // team name (page header)
      const teamElement = document.querySelector(".teamName.truncate");
      const teamName = teamElement?.textContent?.trim() || null;

      // league name from specific container (your requested selector)
      const leagueAnchor = await waitFor(() =>
        [...document.querySelectorAll(
          '.team-details-secondary a[href^="/football/league?leagueId="], ' +
          '.team-details-secondary a.AnchorLink[href^="/football/league?leagueId="]'
        )].find(a => {
          const txt = a.textContent?.trim() || "";
          return txt && !/^league$/i.test(txt); // skip generic "League"
        })
      );
      const leagueName = leagueAnchor?.textContent?.trim() || null;

      // roster players
      const cells = await waitForRosterCells(5000);
      const players = buildPlayersFromCells(cells);

      sendResponse({
        teamName,
        seasonId,
        leagueId,
        leagueName,
        teamId,
        players,
        scrapeDebug: { cellCount: cells.length, path: location.pathname },
      });
    })();

    // async response
    return true;
  });
})();
