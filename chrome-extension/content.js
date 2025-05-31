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
      console.log(`Found study ID ${match[1]} using pattern ${pattern}`);
      return match[1];
    }
  }
  
  // Try to extract from page content as fallback
  const pageText = document.body.textContent;
  const contentMatch = pageText.match(/Study\s+ID[:\s]+(\d+)/i) ||
                      pageText.match(/study[_-]?id[:\s]+(\d+)/i);
  
  if (contentMatch) {
    console.log(`Found study ID ${contentMatch[1]} from page content`);
    return contentMatch[1];
  }
  
  console.log('Could not determine study ID from URL or content');
  console.log('Current URL:', window.location.href);
  return null;
}

/**
 * Make API call to update trial note
 */
async function updateTrialNote(studyId, trialId, action) {
  try {
    console.log(`Attempting to update trial ${trialId} with action: ${action}`);
    console.log(`Study ID: ${studyId}, Current URL: ${window.location.href}`);
    
    // Try different API endpoint patterns that Optuna Dashboard might use
    const possibleEndpoints = [
      `/api/studies/${studyId}/trials/${trialId}/note`,
      `/api/studies/${studyId}/trials/${trialId}/user_attrs/note`,
      `/studies/${studyId}/trials/${trialId}/note`,
      `/api/trials/${trialId}/note`,
    ];

    // First, try to get the current note
    let currentNote = '';
    let noteVersion = 0;
    let workingGetEndpoint = null;
    
    for (const endpoint of possibleEndpoints) {
      try {
        console.log(`Trying GET ${endpoint}`);
        const noteResponse = await fetch(endpoint, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          }
        });

        console.log(`GET ${endpoint} response: ${noteResponse.status}`);
        if (noteResponse.ok) {
          const noteData = await noteResponse.json();
          console.log(`Note data from ${endpoint}:`, noteData);
          currentNote = noteData.body || noteData.note || noteData.value || '';
          noteVersion = noteData.version || 0;
          workingGetEndpoint = endpoint;
          console.log(`Successfully got note from ${endpoint}: "${currentNote}"`);
          break;
        }
      } catch (e) {
        console.log(`Failed to get note from ${endpoint}:`, e);
      }
    }

    // Append the action to the note
    const newNote = currentNote + (currentNote ? '\n\n' : '') + action.toUpperCase();
    console.log(`New note content: "${newNote}"`);

    // Try to update the note using the working endpoint first, then others
    const endpointsToTry = workingGetEndpoint ? 
      [workingGetEndpoint, ...possibleEndpoints.filter(e => e !== workingGetEndpoint)] : 
      possibleEndpoints;

    for (const endpoint of endpointsToTry) {
      try {
        console.log(`Trying PUT ${endpoint}`);
        const updateResponse = await fetch(endpoint, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            version: noteVersion,
            body: newNote,
            note: newNote,
            value: newNote,
          })
        });

        console.log(`PUT ${endpoint} response: ${updateResponse.status}`);
        if (updateResponse.ok) {
          console.log(`Successfully updated note via ${endpoint}`);
          return true;
        } else {
          const errorText = await updateResponse.text();
          console.log(`PUT ${endpoint} failed: ${updateResponse.status} - ${errorText}`);
        }
      } catch (e) {
        console.log(`Error with PUT ${endpoint}:`, e);
      }
    }

    // If PUT fails, try POST
    for (const endpoint of endpointsToTry) {
      try {
        console.log(`Trying POST ${endpoint}`);
        const postResponse = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            body: newNote,
            note: newNote,
            value: newNote,
          })
        });

        console.log(`POST ${endpoint} response: ${postResponse.status}`);
        if (postResponse.ok) {
          console.log('Successfully updated note via POST');
          return true;
        }
      } catch (e) {
        console.log(`POST ${endpoint} failed:`, e);
      }
    }

    throw new Error('All API endpoint attempts failed');

  } catch (error) {
    console.error(`Error updating trial note:`, error);
    showNotification(`Failed to update trial: ${error.message}`, 'error');
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
    console.log(`Button clicked: ${action} for trial ${trialNumber}`);
    e.stopPropagation();
    e.preventDefault();
    
    const studyId = getStudyIdFromUrl();
    console.log(`Study ID: ${studyId}`);
    
    if (!studyId) {
      console.error('Could not determine study ID');
      showNotification('Error: Could not determine study ID', 'error');
      return;
    }

    console.log(`Disabling button and starting ${action} for trial ${trialNumber}`);
    button.disabled = true;
    button.classList.add('loading');
    
    const success = await updateTrialNote(studyId, trialId, action);
    console.log(`Update result: ${success}`);
    
    if (success) {
      showNotification(`Trial ${trialNumber} marked for ${action}`, 'success');
      button.classList.add('success');
      console.log('Reloading page in 2 seconds...');
      // Refresh the page after a short delay to show updated state
      setTimeout(() => {
        window.location.reload();
      }, 2000);
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
  
  console.log(`Found ${trialItems.length} trial items`);
  
  trialItems.forEach(item => {
    const trialText = item.textContent || '';
    const trialMatch = trialText.match(/Trial\s+(\d+)/);
    
    if (!trialMatch) return;
    
    const trialNumber = trialMatch[1];
    const trialKey = `trial-${trialNumber}`;
    
    // Skip if already processed
    if (processedTrials.has(trialKey)) return;
    
    // Skip if buttons already exist
    if (item.querySelector('.optuna-quick-actions-container')) return;
    
    const trialId = trialNumber;
    
    console.log(`Adding buttons to trial ${trialNumber}`);
    
    // Create button container for this specific trial
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'optuna-quick-actions-container';
    buttonContainer.style.display = 'none'; // Hidden by default
    
    // Add buttons
    buttonContainer.appendChild(createActionButton('prune', trialNumber, trialId));
    buttonContainer.appendChild(createActionButton('fail', trialNumber, trialId));
    
    // Position container as overlay without affecting layout
    const itemRect = item.getBoundingClientRect();
    item.style.position = item.style.position || 'relative';
    
    buttonContainer.style.position = 'fixed'; // Use fixed instead of absolute
    buttonContainer.style.right = '20px';
    buttonContainer.style.top = (itemRect.top + itemRect.height / 2 - 14) + 'px';
    buttonContainer.style.zIndex = '1001';
    buttonContainer.style.display = 'flex';
    buttonContainer.style.gap = '4px';
    buttonContainer.style.opacity = '0';
    buttonContainer.style.transition = 'opacity 0.2s ease';
    buttonContainer.style.pointerEvents = 'auto';
    
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
    
    // Append to body instead of trial item to avoid layout interference
    document.body.appendChild(buttonContainer);
    
    // Update position on scroll
    const updatePosition = () => {
      const newRect = item.getBoundingClientRect();
      buttonContainer.style.top = (newRect.top + newRect.height / 2 - 14) + 'px';
    };
    
    // Store reference for cleanup
    item._buttonContainer = buttonContainer;
    item._updatePosition = updatePosition;
    
    processedTrials.add(trialKey);
  });
}

/**
 * Add floating action button for the current trial detail view
 */
function addFloatingActionButton() {
  // Remove existing floating buttons first
  removeFloatingActionButtons();
  
  // Look for trial detail header with more specific detection
  const trialHeaderMatch = document.body.textContent.match(/Trial\s+(\d+)\s+\(trial_id=(\d+)\)/);
  
  if (!trialHeaderMatch) {
    console.log('No trial header found for floating buttons');
    return;
  }
  
  // Check if we're actually on a trial detail page (not just trial list)
  const hasNoteSection = document.body.textContent.includes('Note');
  const hasValueSection = document.body.textContent.includes('Value');
  const hasParameterSection = document.body.textContent.includes('Parameter');
  const hasStartedAt = document.body.textContent.includes('Started At');
  
  // More stringent check for trial detail page
  const isTrialDetailPage = (hasNoteSection && hasValueSection) || 
                           (hasParameterSection && hasStartedAt) ||
                           document.querySelector('textarea, [contenteditable="true"]'); // Note editing area
  
  if (!isTrialDetailPage) {
    console.log('Not on trial detail page, skipping floating buttons');
    return;
  }
  
  const trialNumber = trialHeaderMatch[1];
  const trialId = trialHeaderMatch[2];
  
  console.log(`Adding floating buttons for trial ${trialNumber} (ID: ${trialId})`);
  
  // Create floating action container with stable positioning
  const floatingContainer = document.createElement('div');
  floatingContainer.className = 'optuna-floating-actions';
  floatingContainer.style.position = 'fixed';
  floatingContainer.style.bottom = '30px';
  floatingContainer.style.right = '30px';
  floatingContainer.style.display = 'flex';
  floatingContainer.style.flexDirection = 'column';
  floatingContainer.style.gap = '10px';
  floatingContainer.style.zIndex = '10000';
  
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
  console.log('Floating buttons added successfully');
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
let lastUrl = location.href;
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