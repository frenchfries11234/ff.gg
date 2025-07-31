// popup.js

document.getElementById('getTeamNameBtn').addEventListener('click', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    chrome.tabs.sendMessage(tabs[0].id, { action: "getTeamName" }, (response) => {
      const output = document.getElementById('output');
      if (response?.teamName) {
        output.textContent = "Team: " + response.teamName;

        // Send to your Flask backend
        fetch("http://localhost:10000/api/team", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ teamName: response.teamName })
        })
        .then(res => res.json())
        .then(data => console.log("Saved:", data))
        .catch(err => console.error("Failed to save:", err));
      } else {
        output.textContent = "TS name not found.";
      }
    });
  });
});

