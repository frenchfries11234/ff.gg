document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("getTeamNameBtn").addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      const url = new URL(tab.url);

      // ✅ Only allow on fantasy.espn.com
      if (!url.hostname.includes("fantasy.espn.com")) {
        const output = document.getElementById("output");
        output.innerHTML = `This extention only works on <a href="https://fantasy.espn.com" target="_blank" style="color: #0d6efd;">fantasy.espn.com</a>.`;
        return;
      }

      chrome.tabs.sendMessage(tab.id, { action: "getTeamName" }, (response) => {
        const output = document.getElementById("output");
        console.log("Response from content script:", response);

        if (response?.teamName) {



          try {
            chrome.identity.getAuthToken({ interactive: true }, function (token) {
              if (chrome.runtime.lastError || !token) {
                console.error("Auth error:", chrome.runtime.lastError?.message);
                output.textContent = "Google auth error";
                return;
              }

              fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
                headers: {
                  Authorization: "Bearer " + token
                }
              })
                .then(res => res.json())
                .then(userInfo => {
                  console.log("User email:", userInfo.email);

                  fetch("http://localhost:10000/api/team", {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                      teamName: response.teamName,
                      email: userInfo.email,
                      leagueId: response.leagueId,
                      teamId: response.teamId,
                      seasonId: response.seasonId
                    })
                  });
                })
                .catch(err => {
                  console.error("User info fetch failed:", err);
                  output.textContent = "Google auth error";
                });
            });
          } catch (err) {
            console.error("Google auth block failed:", err);
            output.textContent = "Google auth error";
          }

          output.innerHTML = `Team: <a href="http://localhost:10000/teams" target="_blank" style="color: #4dabf7;">${response.teamName}</a>`;
        } else {
          output.textContent = "Team name not found.";
        }
      });
    });
  });
});
