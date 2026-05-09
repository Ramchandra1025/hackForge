/**
 * Dropdown Menu System
 */

window.HF = window.HF || {};

const HFDropdown = {
  dropdowns: [],

  /**
   * Create dropdown menu
   */
  create(trigger, options = {}) {
    const {
      items = [],
      placement = 'bottom', // bottom, top, left, right
      closeOnClick = true,
      className = ''
    } = options;

    const dropdownId = `dropdown-${Date.now()}`;
    
    // Create dropdown menu
    const menu = document.createElement('div');
    menu.className = `hf-dropdown hf-dropdown-${placement} ${className}`;
    menu.id = dropdownId;
    menu.setAttribute('style', 'display: none;');

    // Add items
    items.forEach(item => {
      if (item.type === 'divider') {
        const divider = document.createElement('div');
        divider.className = 'hf-dropdown-divider';
        menu.appendChild(divider);
      } else {
        const menuItem = document.createElement('a');
        menuItem.href = '#';
        menuItem.className = `hf-dropdown-item ${item.className || ''}`;
        menuItem.innerHTML = item.icon ? `<span class="hf-icon">${item.icon}</span> ${item.label}` : item.label;
        
        menuItem.addEventListener('click', (e) => {
          e.preventDefault();
          if (item.onClick) item.onClick(e);
          if (closeOnClick) HFDropdown.close(dropdownId);
        });

        menu.appendChild(menuItem);
      }
    });

    // Attach to DOM
    trigger.parentElement.appendChild(menu);

    // Toggle on trigger click
    trigger.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      HFDropdown.toggle(dropdownId);
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!trigger.contains(e.target) && !menu.contains(e.target)) {
        HFDropdown.close(dropdownId);
      }
    });

    this.dropdowns.push(dropdownId);
    return menu;
  },

  /**
   * Toggle dropdown
   */
  toggle(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    if (dropdown) {
      const isOpen = dropdown.style.display !== 'none';
      this.closeAll();
      if (!isOpen) {
        dropdown.style.display = 'block';
        dropdown.classList.add('active');
      }
    }
  },

  /**
   * Open dropdown
   */
  open(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    if (dropdown) {
      this.closeAll();
      dropdown.style.display = 'block';
      dropdown.classList.add('active');
    }
  },

  /**
   * Close dropdown
   */
  close(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    if (dropdown) {
      dropdown.style.display = 'none';
      dropdown.classList.remove('active');
    }
  },

  /**
   * Close all dropdowns
   */
  closeAll() {
    this.dropdowns.forEach(id => this.close(id));
  }
};

window.HFDropdown = HFDropdown;
