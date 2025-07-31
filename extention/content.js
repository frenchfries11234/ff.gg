// content.js

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getTeamName") {
    const teamElement = document.querySelector('.teamName.truncate');
    if (teamElement) {
      const teamName = teamElement.textContent.trim();
      sendResponse({ teamName: teamName });
    } else {
      sendResponse({ teamName: null });
    }
  }

  // Return true to indicate async response
  return true;
});
