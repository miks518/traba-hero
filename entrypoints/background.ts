export default defineBackground(() => {
  // Open the side panel when the extension action is clicked
  browser.action.onClicked.addListener(async (tab) => {
    if (tab.id) {
      // @ts-ignore - sidePanel API is available in Chrome MV3
      await chrome.sidePanel.open({ tabId: tab.id });
    }
  });
});
