/**
 * Tooltip System
 */

window.HF = window.HF || {};

const HFTooltip = {
  /**
   * Create tooltip
   */
  create(element, text, options = {}) {
    const {
      placement = 'top', // top, bottom, left, right
      delay = 0,
      offset = 5
    } = options;

    element.addEventListener('mouseenter', () => {
      setTimeout(() => {
        const tooltip = document.createElement('div');
        tooltip.className = `hf-tooltip hf-tooltip-${placement}`;
        tooltip.textContent = text;

        document.body.appendChild(tooltip);

        const rect = element.getBoundingClientRect();
        let top, left;

        switch (placement) {
          case 'top':
            top = rect.top - tooltip.offsetHeight - offset;
            left = rect.left + (rect.width - tooltip.offsetWidth) / 2;
            break;
          case 'bottom':
            top = rect.bottom + offset;
            left = rect.left + (rect.width - tooltip.offsetWidth) / 2;
            break;
          case 'left':
            top = rect.top + (rect.height - tooltip.offsetHeight) / 2;
            left = rect.left - tooltip.offsetWidth - offset;
            break;
          case 'right':
            top = rect.top + (rect.height - tooltip.offsetHeight) / 2;
            left = rect.right + offset;
            break;
        }

        tooltip.style.top = top + 'px';
        tooltip.style.left = left + 'px';

        element.addEventListener('mouseleave', () => {
          tooltip.remove();
        });
      }, delay);
    });
  },

  /**
   * Create tooltips for elements with data-tooltip attribute
   */
  initAll() {
    document.querySelectorAll('[data-tooltip]').forEach(element => {
      const text = element.getAttribute('data-tooltip');
      const placement = element.getAttribute('data-tooltip-placement') || 'top';
      HFTooltip.create(element, text, { placement });
    });
  }
};

// Initialize tooltips on load
document.addEventListener('DOMContentLoaded', () => {
  HFTooltip.initAll();
});

window.HFTooltip = HFTooltip;
