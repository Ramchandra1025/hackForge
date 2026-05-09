/**
 * Context Menu System
 */

window.HF = window.HF || {};

const HFContextMenu = {
  currentMenu: null,

  /**
   * Show context menu
   */
  show(event, items = []) {
    event.preventDefault();
    event.stopPropagation();

    // Remove previous menu
    if (this.currentMenu) {
      this.currentMenu.remove();
    }

    // Create context menu
    const menu = document.createElement('div');
    menu.className = 'hf-context-menu';
    menu.style.position = 'fixed';
    menu.style.top = event.clientY + 'px';
    menu.style.left = event.clientX + 'px';

    // Add items
    items.forEach(item => {
      if (item.type === 'divider') {
        const divider = document.createElement('div');
        divider.className = 'hf-context-menu-divider';
        menu.appendChild(divider);
      } else {
        const menuItem = document.createElement('a');
        menuItem.href = '#';
        menuItem.className = `hf-context-menu-item ${item.className || ''}`;
        menuItem.innerHTML = item.icon ? `<span class="hf-icon">${item.icon}</span> ${item.label}` : item.label;

        menuItem.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (item.onClick) item.onClick(e);
          this.hide();
        });

        menu.appendChild(menuItem);
      }
    });

    // Attach to DOM
    document.body.appendChild(menu);
    this.currentMenu = menu;

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!menu.contains(e.target)) {
        this.hide();
      }
    });
  },

  /**
   * Hide context menu
   */
  hide() {
    if (this.currentMenu) {
      this.currentMenu.remove();
      this.currentMenu = null;
    }
  }
};

// Close context menu on any click
document.addEventListener('click', () => {
  HFContextMenu.hide();
});

window.HFContextMenu = HFContextMenu;
