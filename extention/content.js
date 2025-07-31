// content.js

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getTeamName") {
    const url = new URL(window.location.href);
    const leagueId = url.searchParams.get("leagueId");
    const teamId = url.searchParams.get("teamId");
    const seasonId = url.searchParams.get("seasonId");

    const teamElement = document.querySelector('.teamName.truncate');
    if (teamElement && leagueId && teamId && seasonId) {
      const teamName = teamElement.textContent.trim();

      sendResponse({
        teamName,
        leagueId,
        teamId,
        seasonId
      });
    } else {
      sendResponse({
        teamName: null,
        leagueId: null,
        teamId: null,
        seasonId: null
      });
    }
  }

  // Return true to indicate async response
  return true;
});
