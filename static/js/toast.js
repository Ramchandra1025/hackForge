/**
 * Toast Notification System
 */

window.HF = window.HF || {};

const HFToast = {
  container: null,

  /**
   * Initialize toast container
   */
  init() {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'hf-toast-container';
      this.container.className = 'hf-toast-container';
      document.body.appendChild(this.container);
    }
  },

  /**
   * Show toast
   */
  show(message, type = 'info', duration = 3000) {
    this.init();

    const toast = document.createElement('div');
    toast.className = `hf-toast hf-toast-${type}`;
    toast.innerHTML = `
      <div class="hf-toast-content">
        ${this._getIcon(type)}
        <span class="hf-toast-message">${HFHelpers.escapeHTML(message)}</span>
      </div>
      <button class="hf-toast-close">&times;</button>
    `;

    this.container.appendChild(toast);

    // Close button
    const closeBtn = toast.querySelector('.hf-toast-close');
    closeBtn.addEventListener('click', () => this._remove(toast));

    // Auto remove
    if (duration > 0) {
      setTimeout(() => this._remove(toast), duration);
    }

    return toast;
  },

  /**
   * Success toast
   */
  success(message, duration = 3000) {
    return this.show(message, 'success', duration);
  },

  /**
   * Error toast
   */
  error(message, duration = 5000) {
    return this.show(message, 'error', duration);
  },

  /**
   * Warning toast
   */
  warning(message, duration = 4000) {
    return this.show(message, 'warning', duration);
  },

  /**
   * Info toast
   */
  info(message, duration = 3000) {
    return this.show(message, 'info', duration);
  },

  /**
   * Loading toast
   */
  loading(message) {
    return this.show(message, 'loading', 0);
  },

  /**
   * Get icon for toast type
   */
  _getIcon(type) {
    const icons = {
      'success': '✓',
      'error': '✕',
      'warning': '⚠',
      'info': 'ℹ',
      'loading': '⟳'
    };
    return `<span class="hf-toast-icon">${icons[type] || ''}</span>`;
  },

  /**
   * Remove toast
   */
  _remove(toast) {
    toast.classList.add('closing');
    setTimeout(() => toast.remove(), 300);
  }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  HFToast.init();
});

window.HFToast = HFToast;
