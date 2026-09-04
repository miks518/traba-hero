export default defineBackground(() => {
  // Open the side panel when the extension action is clicked
  browser.action.onClicked.addListener(async (tab) => {
    if (tab.id) {
      // @ts-ignore - sidePanel API is available in Chrome MV3
      await chrome.sidePanel.open({ tabId: tab.id });
    }
  });

  // Open sidepanel from content script floating button
  browser.runtime.onMessage.addListener((msg, sender) => {
    if (!sender.tab) return;
    if (msg.action === 'OPEN_SIDEPANEL_AND_PICK') {
      const tabId = sender.tab.id;
      if (tabId) {
        // @ts-ignore - sidePanel API is available in Chrome MV3
        chrome.sidePanel.open({ tabId }).catch(console.error);
      }
    }
  });
});
