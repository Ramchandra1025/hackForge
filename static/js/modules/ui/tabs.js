/**
 * Tabs System
 */

window.HF = window.HF || {};

const HFTabs = {
  /**
   * Initialize tabs
   */
  init(containerSelector) {
    const container = document.querySelector(containerSelector);
    if (!container) return;

    const tabs = container.querySelectorAll('.hf-tab-button');
    const panels = container.querySelectorAll('.hf-tab-panel');

    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => {
        // Remove active class from all tabs and panels
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));

        // Add active class to clicked tab and corresponding panel
        tab.classList.add('active');
        panels[index]?.classList.add('active');
      });
    });

    // Activate first tab by default
    if (tabs.length > 0) {
      tabs[0].classList.add('active');
      panels[0]?.classList.add('active');
    }
  },

  /**
   * Switch to tab
   */
  switchTo(containerSelector, tabIndex) {
    const container = document.querySelector(containerSelector);
    if (!container) return;

    const tabs = container.querySelectorAll('.hf-tab-button');
    const panels = container.querySelectorAll('.hf-tab-panel');

    tabs.forEach(t => t.classList.remove('active'));
    panels.forEach(p => p.classList.remove('active'));

    tabs[tabIndex]?.classList.add('active');
    panels[tabIndex]?.classList.add('active');
  }
};

// Initialize tabs on load
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-tabs-container]').forEach(container => {
    HFTabs.init('[data-tabs-container]');
  });
});

window.HFTabs = HFTabs;
