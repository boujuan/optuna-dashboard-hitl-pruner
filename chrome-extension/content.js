/**
 * Optuna Dashboard Quick Prune Chrome Extension
 * Adds quick action buttons to trials for easy pruning/failing
 */

// Configuration
const CONFIG = {
  checkInterval: 1000, // Check for new trials every second
  apiTimeout: 5000,
  buttonStyles: {
    prune: {
      color: '#ffa94d',
      hoverColor: '#ff922b',
      icon: '✂️'
    },
    fail: {
      color: '#ff6b6b', 
      hoverColor: '#ff5252',
      icon: '❌'
    }
  }
};

// Track processed trials to avoid duplicate buttons
const processedTrials = new Set();

/**
 * Extract study ID from the current URL
 */
function getStudyIdFromUrl() {
  const match = window.location.pathname.match(/studies\/(\d+)/);
  return match ? match[1] : null;
}

/**
 * Make API call to update trial note
 */
async function updateTrialNote(studyId, trialId, action) {
  try {
    // First, get the current note
    const noteResponse = await fetch(`/api/studies/${studyId}/trials/${trialId}/note`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    let currentNote = '';
    if (noteResponse.ok) {
      const noteData = await noteResponse.json();
      currentNote = noteData.body || '';
    }

    // Append the action to the note
    const newNote = currentNote + (currentNote ? '\n\n' : '') + action.toUpperCase();

    // Update the note
    const updateResponse = await fetch(`/api/studies/${studyId}/trials/${trialId}/note`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        version: 0, // This may need to be adjusted based on the actual API
        body: newNote
      })
    });

    if (!updateResponse.ok) {
      throw new Error(`Failed to update note: ${updateResponse.status}`);
    }

    return true;
  } catch (error) {
    console.error(`Error updating trial note:`, error);
    return false;
  }
}

/**
 * Create action button element
 */
function createActionButton(action, trialNumber, trialId) {
  const button = document.createElement('button');
  button.className = `optuna-quick-action optuna-quick-${action}`;
  button.innerHTML = `${CONFIG.buttonStyles[action].icon}`;
  button.title = `${action.charAt(0).toUpperCase() + action.slice(1)} Trial ${trialNumber}`;
  
  button.addEventListener('click', async (e) => {
    e.stopPropagation();
    e.preventDefault();
    
    const studyId = getStudyIdFromUrl();
    if (!studyId) {
      showNotification('Error: Could not determine study ID', 'error');
      return;
    }

    button.disabled = true;
    button.classList.add('loading');
    
    const success = await updateTrialNote(studyId, trialId, action);
    
    if (success) {
      showNotification(`Trial ${trialNumber} marked for ${action}`, 'success');
      button.classList.add('success');
      // Refresh the page after a short delay to show updated state
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } else {
      showNotification(`Failed to ${action} trial ${trialNumber}`, 'error');
      button.disabled = false;
      button.classList.remove('loading');
    }
  });
  
  return button;
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `optuna-notification optuna-notification-${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  // Animate in
  setTimeout(() => {
    notification.classList.add('show');
  }, 10);
  
  // Remove after 3 seconds
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => {
      notification.remove();
    }, 300);
  }, 3000);
}

/**
 * Add buttons to trial list items
 */
function addButtonsToTrialList() {
  // Multiple selectors to catch different possible structures
  const selectors = [
    // MUI ListItem containing trial text
    '[class*="MuiListItem"] [class*="MuiListItemText"]:has-text("Trial")',
    // Direct trial elements
    '[class*="trial"i]',
    // List items with Trial text
    'li:has(> div:has-text("Trial"))',
    'a:has(> div:has-text("Trial"))',
    // Generic approach - any clickable element with Trial text
    '[role="button"]:has-text("Trial"), [tabindex]:has-text("Trial")'
  ];
  
  // Try each selector
  let trialItems = [];
  for (const selector of selectors) {
    try {
      // Use a more compatible selector approach
      const elements = document.querySelectorAll('*');
      elements.forEach(el => {
        const text = el.textContent || '';
        if (text.includes('Trial') && text.match(/Trial\s+\d+/) && 
            !text.includes('PRUNE') && !text.includes('FAIL') &&
            (el.tagName === 'LI' || el.tagName === 'A' || el.tagName === 'DIV' || el.getAttribute('role') === 'button')) {
          // Check if this element or its parent is a list item
          const listItem = el.closest('li, [role="button"], a[href*="trials"]');
          if (listItem && !trialItems.includes(listItem)) {
            trialItems.push(listItem);
          }
        }
      });
      
      if (trialItems.length > 0) break;
    } catch (e) {
      console.debug('Selector failed:', selector, e);
    }
  }
  
  trialItems.forEach(item => {
    // Extract trial number from the text content
    const trialText = item.textContent || '';
    const trialMatch = trialText.match(/Trial\s+(\d+)/);
    
    if (!trialMatch) return;
    
    const trialNumber = trialMatch[1];
    const trialKey = `trial-${trialNumber}`;
    
    // Skip if already processed
    if (processedTrials.has(trialKey)) return;
    
    // Skip if buttons already exist
    if (item.querySelector('.optuna-quick-actions-container')) return;
    
    // The trial ID is typically the same as trial number in the API
    const trialId = trialNumber;
    
    // Create button container
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'optuna-quick-actions-container';
    
    // Add prune and fail buttons
    buttonContainer.appendChild(createActionButton('prune', trialNumber, trialId));
    buttonContainer.appendChild(createActionButton('fail', trialNumber, trialId));
    
    // Insert buttons into the trial item without affecting layout
    const originalPosition = item.style.position;
    if (!originalPosition || originalPosition === 'static') {
      item.style.position = 'relative';
    }
    
    // Ensure the item doesn't have extra padding/margin from our buttons
    buttonContainer.style.position = 'absolute';
    buttonContainer.style.margin = '0';
    buttonContainer.style.padding = '0';
    
    item.appendChild(buttonContainer);
    
    processedTrials.add(trialKey);
  });
}

/**
 * Add floating action button for the current trial detail view
 */
function addFloatingActionButton() {
  // Remove existing floating buttons first
  removeFloatingActionButtons();
  
  // Check if we're on a trial detail page with the specific pattern
  const trialHeaderMatch = document.body.textContent.match(/Trial\s+(\d+)\s+\(trial_id=(\d+)\)/);
  
  // Also check URL pattern to ensure we're on the correct page
  const isTrialDetailPage = window.location.pathname.includes('/trials/') && 
                           !window.location.pathname.endsWith('/trials') &&
                           trialHeaderMatch;
  
  if (!isTrialDetailPage) return;
  
  const trialNumber = trialHeaderMatch[1];
  const trialId = trialHeaderMatch[2];
  
  // Create floating action container
  const floatingContainer = document.createElement('div');
  floatingContainer.className = 'optuna-floating-actions';
  
  // Add prune button
  const pruneBtn = createActionButton('prune', trialNumber, trialId);
  pruneBtn.innerHTML = `${CONFIG.buttonStyles.prune.icon} Prune`;
  pruneBtn.classList.add('floating');
  
  // Add fail button
  const failBtn = createActionButton('fail', trialNumber, trialId);
  failBtn.innerHTML = `${CONFIG.buttonStyles.fail.icon} Fail`;
  failBtn.classList.add('floating');
  
  floatingContainer.appendChild(pruneBtn);
  floatingContainer.appendChild(failBtn);
  
  document.body.appendChild(floatingContainer);
}

/**
 * Remove floating action buttons
 */
function removeFloatingActionButtons() {
  const existing = document.querySelector('.optuna-floating-actions');
  if (existing) {
    existing.remove();
  }
}

/**
 * Main function to initialize the extension
 */
function initialize() {
  // Run immediately
  addButtonsToTrialList();
  addFloatingActionButton();
  
  // Set up mutation observer to handle dynamic content
  const observer = new MutationObserver((mutations) => {
    // Debounce to avoid too many calls
    clearTimeout(observer.timeout);
    observer.timeout = setTimeout(() => {
      addButtonsToTrialList();
      addFloatingActionButton();
    }, 100);
  });
  
  // Observe the entire document for changes
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
  
  // Also check periodically in case mutations are missed
  setInterval(() => {
    addButtonsToTrialList();
    addFloatingActionButton();
  }, CONFIG.checkInterval);
}

// Wait for the page to be ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialize);
} else {
  initialize();
}

// Listen for navigation changes (for single-page app behavior)
let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    processedTrials.clear(); // Clear processed trials on navigation
    setTimeout(() => {
      addButtonsToTrialList();
      addFloatingActionButton();
    }, 500);
  }
}).observe(document, {subtree: true, childList: true});