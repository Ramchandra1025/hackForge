/**
 * Modal Dialog System
 */

window.HF = window.HF || {};

const HFModal = {
  activeModals: [],

  /**
   * Create and show a modal
   * @param {Object} options - Modal configuration
   * @returns {Element} Modal element
   */
  create(options = {}) {
    const {
      title = 'Modal',
      content = '',
      buttons = [],
      closable = true,
      size = 'md', // sm, md, lg, xl
      backdrop = true,
      id = `modal-${Date.now()}`
    } = options;

    // Create modal container
    const modalContainer = document.createElement('div');
    modalContainer.className = `hf-modal-overlay ${backdrop ? 'with-backdrop' : ''}`;
    modalContainer.id = id;

    // Create modal dialog
    const modal = document.createElement('div');
    modal.className = `hf-modal hf-modal-${size}`;

    // Header
    const header = document.createElement('div');
    header.className = 'hf-modal-header';
    header.innerHTML = `
      <h3 class="hf-modal-title">${HFHelpers.escapeHTML(title)}</h3>
      ${closable ? '<button class="hf-modal-close">&times;</button>' : ''}
    `;

    // Body
    const body = document.createElement('div');
    body.className = 'hf-modal-body';
    body.innerHTML = content;

    // Footer
    const footer = document.createElement('div');
    footer.className = 'hf-modal-footer';
    buttons.forEach(btn => {
      const button = document.createElement('button');
      button.className = `hf-btn hf-btn-${btn.type || 'secondary'}`;
      button.textContent = btn.label;
      button.onclick = btn.onClick || (() => {});
      footer.appendChild(button);
    });

    // Assemble modal
    modal.appendChild(header);
    modal.appendChild(body);
    if (buttons.length > 0) modal.appendChild(footer);
    modalContainer.appendChild(modal);

    // Attach to DOM
    document.body.appendChild(modalContainer);

    // Event listeners
    const closeBtn = header.querySelector('.hf-modal-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.close(id));
    }

    if (backdrop) {
      modalContainer.addEventListener('click', (e) => {
        if (e.target === modalContainer) {
          this.close(id);
        }
      });
    }

    this.activeModals.push(id);
    return modalContainer;
  },

  /**
   * Show alert modal
   */
  alert(title, message) {
    return new Promise((resolve) => {
      this.create({
        title,
        content: `<p>${HFHelpers.escapeHTML(message)}</p>`,
        buttons: [
          {
            label: 'OK',
            type: 'primary',
            onClick: () => {
              this.close(this.activeModals[this.activeModals.length - 1]);
              resolve();
            }
          }
        ]
      });
    });
  },

  /**
   * Show confirmation modal
   */
  confirm(title, message) {
    return new Promise((resolve) => {
      const id = `modal-${Date.now()}`;
      this.create({
        id,
        title,
        content: `<p>${HFHelpers.escapeHTML(message)}</p>`,
        buttons: [
          {
            label: 'Cancel',
            type: 'secondary',
            onClick: () => {
              this.close(id);
              resolve(false);
            }
          },
          {
            label: 'OK',
            type: 'primary',
            onClick: () => {
              this.close(id);
              resolve(true);
            }
          }
        ]
      });
    });
  },

  /**
   * Show prompt modal
   */
  prompt(title, message, defaultValue = '') {
    return new Promise((resolve) => {
      const id = `modal-${Date.now()}`;
      const content = `
        <p>${HFHelpers.escapeHTML(message)}</p>
        <input type="text" class="hf-input" value="${HFHelpers.escapeHTML(defaultValue)}" placeholder="Enter value" />
      `;

      const modal = this.create({
        id,
        title,
        content,
        buttons: [
          {
            label: 'Cancel',
            type: 'secondary',
            onClick: () => {
              this.close(id);
              resolve(null);
            }
          },
          {
            label: 'OK',
            type: 'primary',
            onClick: () => {
              const input = document.querySelector(`#${id} .hf-input`);
              const value = input ? input.value : null;
              this.close(id);
              resolve(value);
            }
          }
        ]
      });
    });
  },

  /**
   * Close modal
   */
  close(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('closing');
      setTimeout(() => {
        modal.remove();
        this.activeModals = this.activeModals.filter(id => id !== modalId);
      }, 300);
    }
  },

  /**
   * Close all modals
   */
  closeAll() {
    this.activeModals.forEach(id => this.close(id));
  }
};

window.HFModal = HFModal;
