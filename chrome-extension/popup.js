// Check if the extension is active on the current tab
chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
  const statusDiv = document.getElementById('status');
  const currentUrl = tabs[0].url;
  
  if (currentUrl && (currentUrl.includes('localhost') || currentUrl.includes('127.0.0.1'))) {
    statusDiv.textContent = '✅ Active on this page';
    statusDiv.classList.add('active');
  } else {
    statusDiv.textContent = '⚠️ Not active - Open Optuna Dashboard';
    statusDiv.classList.remove('active');
  }
});