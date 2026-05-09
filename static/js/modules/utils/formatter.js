/**
 * Data Formatting Utilities
 */

window.HF = window.HF || {};

const HFFormatter = {
  // Format currency
  formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  },

  // Format percentage
  formatPercentage(value, decimals = 0) {
    return (value * 100).toFixed(decimals) + '%';
  },

  // Format number with commas
  formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  },

  // Capitalize string
  capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
  },

  // Capitalize all words
  titleCase(str) {
    if (!str) return '';
    return str.replace(/\w\S*/g, (txt) => {
      return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
  },

  // Convert snake_case to camelCase
  toCamelCase(str) {
    return str.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
  },

  // Convert camelCase to snake_case
  toSnakeCase(str) {
    return str.replace(/([A-Z])/g, '_$1').toLowerCase();
  },

  // Format task status
  formatTaskStatus(status) {
    const statusMap = {
      'todo': 'To Do',
      'in_progress': 'In Progress',
      'in_review': 'In Review',
      'done': 'Done',
      'blocked': 'Blocked'
    };
    return statusMap[status] || status;
  },

  // Format task priority
  formatTaskPriority(priority) {
    const priorityMap = {
      'critical': 'Critical',
      'high': 'High',
      'medium': 'Medium',
      'low': 'Low'
    };
    return priorityMap[priority] || priority;
  },

  // Format role
  formatRole(role) {
    const roleMap = {
      'owner': 'Owner',
      'admin': 'Admin',
      'developer': 'Developer',
      'designer': 'Designer',
      'viewer': 'Viewer',
      'judge': 'Judge'
    };
    return roleMap[role] || role;
  },

  // Format notification type
  formatNotificationType(type) {
    const typeMap = {
      'message': 'Message',
      'mention': 'Mention',
      'task_assigned': 'Task Assigned',
      'task_comment': 'Task Comment',
      'deployment': 'Deployment',
      'meeting': 'Meeting',
      'ai_action': 'AI Action',
      'system': 'System'
    };
    return typeMap[type] || type;
  },

  // Format code snippet
  formatCodeSnippet(code, language = 'javascript') {
    return `\`\`\`${language}\n${code}\n\`\`\``;
  },

  // Format Markdown to HTML (basic)
  markdownToHTML(text) {
    let html = text;
    
    // Headers
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    // Inline code
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');
    
    // Links
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    return html;
  },

  // Truncate text
  truncate(text, maxLength = 100, suffix = '...') {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - suffix.length) + suffix;
  },

  // Get initials from name
  getInitials(name) {
    if (!name) return '';
    return name.split(' ')
      .map((n) => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
  },

  // Format duration
  formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    const parts = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0) parts.push(`${secs}s`);

    return parts.join(' ');
  }
};

window.HFFormatter = HFFormatter;
