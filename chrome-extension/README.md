# Optuna Dashboard Quick Prune Chrome Extension

This Chrome extension adds quick action buttons to the Optuna Dashboard for easy trial pruning and failing, eliminating the need to manually edit notes.

## Features

### 1. **Trial List Quick Actions**
- Hover over any trial in the list to see ✂️ (Prune) and ❌ (Fail) buttons
- Click a button to instantly mark the trial for pruning or failure
- The extension automatically adds "PRUNE" or "FAIL" to the trial's note

### 2. **Floating Action Buttons**
- When viewing a trial's details, floating buttons appear in the bottom-right corner
- Easy access to prune/fail actions while reviewing trial information

### 3. **Visual Feedback**
- Loading animation while processing
- Success confirmation
- Toast notifications for action results
- Page automatically refreshes to show updated state

## Installation

### Option 1: Load Unpacked (Development)

1. **Load the Extension in Chrome**
   - Open Chrome/Thorium and go to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top right)
   - Click "Load unpacked"
   - Select the `chrome-extension` folder

2. **Configure Your Batch Script**
   Add the extension to your Thorium browser launch:
   ```batch
   start "" "C:\...\chrome_proxy.exe" --profile-directory=Default --load-extension="\\wsl$\Debian\home\boujuan\optuna-dashboard-hitl-pruner\chrome-extension" --app="http://localhost:8080"
   ```

### Option 2: Pack Extension (Distribution)

1. **Create a Packaged Extension**
   - Go to `chrome://extensions/`
   - Click "Pack extension"
   - Select the `chrome-extension` folder as "Extension root directory"
   - Chrome will create a `.crx` file and `.pem` private key

2. **Install the Packaged Extension**
   - Drag and drop the `.crx` file into Chrome
   - Or use the generated extension ID with `--load-extension`

3. **For WSL Users**
   The extension folder is already complete with icons and ready to use directly.

## How It Works

**This extension works TOGETHER with your monitor system - it cannot work independently.**

1. The extension monitors the Optuna Dashboard pages
2. It injects action buttons into the trial list and detail views
3. When clicked, it makes API calls to update the trial's note with "PRUNE" or "FAIL"
4. Your existing monitor (human_trial_monitor.py) detects these keywords and takes action
5. The monitor actually changes the trial state - the extension just adds the keywords

## Technical Details

### API Integration
The extension uses Optuna Dashboard's REST API:
- `GET /api/studies/{study_id}/trials/{trial_id}/note` - Get current note
- `PUT /api/studies/{study_id}/trials/{trial_id}/note` - Update note

### Compatibility
- Works with Optuna Dashboard on `localhost` and `127.0.0.1`
- Automatically detects the study ID from the URL
- Handles dynamic content updates (React-based UI)

## Advantages Over Manual Approach

1. **Speed**: One click vs navigate → click note → type → save
2. **Consistency**: Always adds the exact keywords your monitor expects
3. **Visual Clarity**: Buttons only appear on hover, keeping the UI clean
4. **Batch Operations**: Quickly process multiple trials
5. **Less Error-Prone**: No typos in keywords

## Customization

You can modify the extension by editing:
- `config` object in `content.js` for timing and styling
- `styles.css` for button appearance
- Add more action types by extending the button creation logic

## Troubleshooting

1. **Buttons don't appear**: 
   - Refresh the page
   - Check that the extension is enabled in `chrome://extensions/`
   - Verify you're on a localhost URL

2. **Actions fail**:
   - Check browser console for errors
   - Ensure your monitor is running
   - Verify the API endpoints match your Optuna Dashboard version

3. **With WSL**:
   - Ensure the extension path is accessible from Windows
   - Use the `\\wsl$\` prefix in your batch file

## Future Improvements

- Add keyboard shortcuts (e.g., `P` for prune, `F` for fail)
- Batch selection mode for multiple trials
- Custom action keywords configuration
- Integration with your monitor's status