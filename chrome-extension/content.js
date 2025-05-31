/**
 * Optuna Dashboard Quick Prune Chrome Extension
 * Adds quick action buttons to trials for easy pruning/failing
 */

// Configuration
const CONFIG = {
  checkInterval: 5000, // Check for new trials every 5 seconds (reduced from 1 second)
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
// Track if floating buttons are already added to avoid spam
let floatingButtonsAdded = false;
// Track last URL to detect navigation
let lastUrl = location.href;

/**
 * Extract study ID from the current URL
 */
function getStudyIdFromUrl() {
  // Try different URL patterns
  const patterns = [
    /studies\/(\d+)/,           // /studies/123
    /\/dashboard\/studies\/(\d+)/, // /dashboard/studies/123
    /study[_-]?id[=:](\d+)/i,   // study_id=123 or study-id:123
    /id[=:](\d+)/               // id=123
  ];
  
  for (const pattern of patterns) {
    const match = window.location.pathname.match(pattern) || 
                  window.location.search.match(pattern) ||
                  window.location.href.match(pattern);
    if (match) {
      return match[1];
    }
  }
  
  // Try to extract from page content as fallback
  const pageText = document.body.textContent;
  const contentMatch = pageText.match(/Study\s+ID[:\s]+(\d+)/i) ||
                      pageText.match(/study[_-]?id[:\s]+(\d+)/i);
  
  if (contentMatch) {
    return contentMatch[1];
  }
  
  return null;
}

/**
 * Update trial note using optuna-dashboard API
 */
async function updateTrialNote(studyId, trialId, action) {
  try {
    const endpoint = `/api/studies/${studyId}/${trialId}/note`;
    const actionCommand = action.toUpperCase();
    
    // First, get the current version from the API
    let currentVersion = 0;
    
    const getResponse = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (getResponse.ok) {
      const noteData = await getResponse.json();
      currentVersion = noteData.version || 0;
    } else if (getResponse.status === 404) {
      // Note doesn't exist yet, version will be 0
      currentVersion = 0;
    } else {
      throw new Error(`Failed to get current note version: ${getResponse.status} ${getResponse.statusText}`);
    }
    
    // Overwrite the note completely with just our action command
    const updateData = {
      body: actionCommand,
      version: currentVersion + 1
    };
    
    const updateResponse = await fetch(endpoint, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updateData)
    });
    
    if (updateResponse.ok) {
      showNotification(`Trial marked for ${action} - monitor will process it shortly!`, 'success');
      return true;
    } else if (updateResponse.status === 409) {
      // Version conflict - try once more with fresh version
      await new Promise(resolve => setTimeout(resolve, 500));
      return await updateTrialNote(studyId, trialId, action);
    } else {
      const errorText = await updateResponse.text();
      throw new Error(`Failed to update note: ${updateResponse.status} ${errorText}`);
    }
    
  } catch (error) {
    showNotification(`Failed to update trial: ${error.message}`, 'error');
    return false;
  }
}

/**
 * Create action button element
 */
function createActionButton(action, trialNumber, studyId) {
  const button = document.createElement('button');
  button.className = `optuna-quick-action optuna-quick-${action}`;
  button.innerHTML = `${CONFIG.buttonStyles[action].icon}`;
  button.title = `${action.charAt(0).toUpperCase() + action.slice(1)} Trial ${trialNumber}`;
  
  button.addEventListener('click', async (e) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (!studyId) {
      showNotification('Error: Could not determine study ID', 'error');
      return;
    }

    button.disabled = true;
    button.classList.add('loading');
    
    // Get the real trial ID from the trial number
    const trialId = await getTrialIdFromNumber(studyId, trialNumber);
    
    const success = await updateTrialNote(studyId, trialId, action);
    
    if (success) {
      button.classList.add('success');
      // Reload the page after a delay to show the updated trial state
      setTimeout(() => {
        window.location.reload();
      }, 3000);
    } else {
      button.disabled = false;
      button.classList.remove('loading');
    }
  });
  
  return button;
}

/**
 * Create floating action button element (for trial detail view)
 */
function createFloatingActionButton(action, trialNumber, trialId, studyId) {
  const button = document.createElement('button');
  button.className = `optuna-quick-action optuna-quick-${action}`;
  button.innerHTML = `${CONFIG.buttonStyles[action].icon}`;
  button.title = `${action.charAt(0).toUpperCase() + action.slice(1)} Trial ${trialNumber}`;
  
  button.addEventListener('click', async (e) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (!studyId) {
      showNotification('Error: Could not determine study ID', 'error');
      return;
    }

    button.disabled = true;
    button.classList.add('loading');
    
    // Get the real trial ID from the trial number (same as list buttons)
    const resolvedTrialId = await getTrialIdFromNumber(studyId, trialNumber);
    const success = await updateTrialNote(studyId, resolvedTrialId, action);
    
    if (success) {
      button.classList.add('success');
      // Reload the page after a delay to show the updated trial state
      setTimeout(() => {
        window.location.reload();
      }, 3000);
    } else {
      button.disabled = false;
      button.classList.remove('loading');
    }
  });
  
  return button;
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info', duration = 3000) {
  const notification = document.createElement('div');
  notification.className = `optuna-notification optuna-notification-${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  // Animate in
  setTimeout(() => {
    notification.classList.add('show');
  }, 10);
  
  // Remove after specified duration
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => {
      notification.remove();
    }, 300);
  }, duration);
}

/**
 * Get trial ID from trial number by fetching study data
 */
async function getTrialIdFromNumber(studyId, trialNumber) {
  try {
    const response = await fetch(`/api/studies/${studyId}`);
    if (response.ok) {
      const studyData = await response.json();
      const trial = studyData.trials.find(t => t.number === parseInt(trialNumber));
      if (trial) {
        return trial.trial_id;
      }
    }
  } catch (e) {
    // Fallback silently
  }
  
  // Fallback: assume trial number = trial ID (not always correct but better than nothing)
  return parseInt(trialNumber);
}

/**
 * Add hover listeners to trial list items
 */
function addButtonsToTrialList() {
  // Find trial elements more specifically
  const elements = document.querySelectorAll('*');
  const trialItems = [];
  
  elements.forEach(el => {
    const text = el.textContent || '';
    // Look for elements that start with "Trial X" where X is a number
    if (text.match(/^\s*Trial\s+\d+/) && 
        !text.includes('PRUNE') && 
        !text.includes('FAIL') &&
        // Should be a clickable element
        (el.tagName === 'LI' || el.tagName === 'A' || el.tagName === 'DIV' || 
         el.getAttribute('role') === 'button' || el.style.cursor === 'pointer')) {
      
      // Find the clickable parent (the actual trial list item)
      const listItem = el.closest('li, [role="button"], a, div[style*="cursor"]');
      if (listItem && !trialItems.includes(listItem)) {
        trialItems.push(listItem);
      }
    }
  });
  
  // Only log if there's a significant change in trial count (reduced spam)
  if (Math.abs(trialItems.length - (processedTrials.size || 0)) > 10) {
    console.log(`Found ${trialItems.length} trial items`);
  }
  
  trialItems.forEach(async (item) => {
    const trialText = item.textContent || '';
    const trialMatch = trialText.match(/Trial\s+(\d+)/);
    
    if (!trialMatch) return;
    
    const trialNumber = trialMatch[1];
    const trialKey = `trial-${trialNumber}`;
    
    // Skip if already processed
    if (processedTrials.has(trialKey)) return;
    
    // Skip if buttons already exist
    if (item.querySelector('.optuna-quick-actions-container')) return;
    
    // Get the study ID for API calls
    const studyId = getStudyIdFromUrl();
    if (!studyId) {
      return;
    }
    
    // Create button container for this specific trial
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'optuna-quick-actions-container';
    buttonContainer.style.display = 'none'; // Hidden by default
    
    // Add buttons (we'll resolve the real trial ID when the button is clicked)
    buttonContainer.appendChild(createActionButton('prune', trialNumber, studyId));
    buttonContainer.appendChild(createActionButton('fail', trialNumber, studyId));
    
    // Position container absolutely within the trial item
    item.style.position = 'relative';
    buttonContainer.style.position = 'absolute';
    buttonContainer.style.right = '10px';
    buttonContainer.style.top = '50%';
    buttonContainer.style.transform = 'translateY(-50%)';
    buttonContainer.style.zIndex = '1000';
    buttonContainer.style.display = 'flex';
    buttonContainer.style.gap = '5px';
    buttonContainer.style.opacity = '0';
    buttonContainer.style.transition = 'opacity 0.2s ease';
    
    // Add hover listeners - simplified approach
    item.addEventListener('mouseenter', () => {
      buttonContainer.style.opacity = '1';
    });
    
    item.addEventListener('mouseleave', () => {
      // Small delay to allow clicking buttons
      setTimeout(() => {
        if (!buttonContainer.matches(':hover')) {
          buttonContainer.style.opacity = '0';
        }
      }, 150);
    });
    
    // Keep buttons visible when hovering over them
    buttonContainer.addEventListener('mouseenter', () => {
      buttonContainer.style.opacity = '1';
    });
    
    buttonContainer.addEventListener('mouseleave', () => {
      buttonContainer.style.opacity = '0';
    });
    
    // Append to trial item
    item.appendChild(buttonContainer);
    
    processedTrials.add(trialKey);
  });
}

/**
 * Add floating action button for the current trial detail view
 */
function addFloatingActionButton() {
  // Skip if buttons already added and URL hasn't changed
  if (floatingButtonsAdded && location.href === lastUrl) {
    return;
  }
  
  // Remove existing floating buttons first
  removeFloatingActionButtons();
  floatingButtonsAdded = false;
  
  // Look for trial detail header - try multiple patterns
  let trialHeaderMatch = document.body.textContent.match(/Trial\s+(\d+)\s+\(trial_id=(\d+)\)/);
  
  if (!trialHeaderMatch) {
    // Try alternative patterns
    trialHeaderMatch = document.body.textContent.match(/Trial\s+(\d+).*trial_id[:\s]*(\d+)/);
  }
  
  if (!trialHeaderMatch) {
    // Try even simpler pattern - check if we're on a trial detail page by URL
    const urlMatch = window.location.pathname.match(/trials\/(\d+)/);
    if (urlMatch) {
      const trialNumber = urlMatch[1];
      
      // Try to find trial_id in the page content
      const trialIdMatch = document.body.textContent.match(/trial_id[:\s]*(\d+)/i) || 
                          document.body.textContent.match(/id[:\s]*(\d+)/);
      
      if (trialIdMatch) {
        trialHeaderMatch = [null, trialNumber, trialIdMatch[1]];
      }
    }
  }
  
  if (!trialHeaderMatch) {
    return;
  }
  
  // Check if we can find typical trial detail elements
  const hasNoteSection = document.body.textContent.includes('Note');
  const hasValueSection = document.body.textContent.includes('Value');
  const hasParameterSection = document.body.textContent.includes('Parameter');
  const hasTrialInfo = document.body.textContent.includes('State') || 
                      document.body.textContent.includes('Duration') ||
                      window.location.pathname.includes('/trials/');
  
  // If we have trial header and typical detail sections, show floating buttons
  if (hasNoteSection || hasValueSection || hasParameterSection || hasTrialInfo) {
    const trialNumber = trialHeaderMatch[1];
    
    const studyId = getStudyIdFromUrl();
    if (!studyId) {
      return;
    }
    
    // Create floating action container
    const floatingContainer = document.createElement('div');
    floatingContainer.className = 'optuna-floating-actions';
    
    // Create floating buttons using the same working function as list buttons
    const pruneBtn = createActionButton('prune', trialNumber, studyId);
    pruneBtn.innerHTML = `${CONFIG.buttonStyles.prune.icon} Prune`;
    pruneBtn.classList.add('floating');
    
    const failBtn = createActionButton('fail', trialNumber, studyId);
    failBtn.innerHTML = `${CONFIG.buttonStyles.fail.icon} Fail`;
    failBtn.classList.add('floating');
    
    floatingContainer.appendChild(pruneBtn);
    floatingContainer.appendChild(failBtn);
    
    document.body.appendChild(floatingContainer);
    floatingButtonsAdded = true;
    lastUrl = location.href;
  }
}

/**
 * Remove floating action buttons
 */
function removeFloatingActionButtons() {
  const existing = document.querySelector('.optuna-floating-actions');
  if (existing) {
    existing.remove();
  }
  floatingButtonsAdded = false;
}

/**
 * Main function to initialize the extension
 */
function initialize() {
  // Run immediately
  addButtonsToTrialList();
  addFloatingActionButton();
  
  // Set up mutation observer to handle dynamic content
  const observer = new MutationObserver(() => {
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
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    processedTrials.clear(); // Clear processed trials on navigation
    removeFloatingActionButtons(); // Remove floating buttons
    setTimeout(() => {
      addButtonsToTrialList();
      addFloatingActionButton();
    }, 500);
  }
}).observe(document, {subtree: true, childList: true});