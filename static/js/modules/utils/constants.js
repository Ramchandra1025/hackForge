/**
 * Application Constants
 */

window.HF = window.HF || {};

const HFConstants = {
  // API endpoints
  API: {
    BASE: '/api',
    AUTH: '/api/auth',
    USERS: '/api/users',
    TEAMS: '/api/teams',
    PROJECTS: '/api/projects',
    TASKS: '/api/tasks',
    FILES: '/api/files',
    CHAT: '/api/chat',
    AI: '/api/ai',
    DEPLOYMENTS: '/api/deployments',
    MEETINGS: '/api/meetings',
    NOTIFICATIONS: '/api/notifications',
    WIKI: '/api/wiki',
    SEARCH: '/api/search',
    ADMIN: '/api/admin'
  },

  // User roles
  ROLES: {
    OWNER: 'owner',
    ADMIN: 'admin',
    DEVELOPER: 'developer',
    DESIGNER: 'designer',
    VIEWER: 'viewer',
    JUDGE: 'judge'
  },

  // Task status
  TASK_STATUS: {
    TODO: 'todo',
    IN_PROGRESS: 'in_progress',
    IN_REVIEW: 'in_review',
    DONE: 'done',
    BLOCKED: 'blocked'
  },

  // Task priority
  TASK_PRIORITY: {
    CRITICAL: 'critical',
    HIGH: 'high',
    MEDIUM: 'medium',
    LOW: 'low'
  },

  // Deployment platforms
  DEPLOYMENT_PLATFORMS: {
    NETLIFY: 'netlify',
    RAILWAY: 'railway',
    GITHUB_PAGES: 'github_pages',
    VERCEL: 'vercel'
  },

  // Notification types
  NOTIFICATION_TYPES: {
    MESSAGE: 'message',
    MENTION: 'mention',
    TASK_ASSIGNED: 'task_assigned',
    TASK_COMMENT: 'task_comment',
    DEPLOYMENT: 'deployment',
    MEETING: 'meeting',
    AI_ACTION: 'ai_action',
    SYSTEM: 'system'
  },

  // AI action types
  AI_ACTIONS: {
    GENERATE_README: 'generate_readme',
    REVIEW_CODE: 'review_code',
    PLAN_SPRINT: 'plan_sprint',
    FIND_BUGS: 'find_bugs',
    GENERATE_PPT: 'generate_ppt',
    ANALYZE_DATA: 'analyze_data'
  },

  // File types
  FILE_TYPES: {
    TEXT: 'text',
    IMAGE: 'image',
    VIDEO: 'video',
    AUDIO: 'audio',
    CODE: 'code',
    DOCUMENT: 'document',
    ARCHIVE: 'archive',
    OTHER: 'other'
  },

  // Socket.IO events
  SOCKET_EVENTS: {
    // Editor
    EDITOR_CHANGE: 'editor:change',
    CURSOR_MOVE: 'cursor:move',
    SELECTION_CHANGE: 'selection:change',

    // Presence
    PRESENCE_ONLINE: 'presence:online',
    PRESENCE_OFFLINE: 'presence:offline',
    PRESENCE_IDLE: 'presence:idle',

    // Chat
    CHAT_MESSAGE: 'chat:message',
    CHAT_TYPING: 'chat:typing',
    CHAT_REACTION: 'chat:reaction',

    // Notifications
    NOTIFICATION_NEW: 'notification:new',
    NOTIFICATION_READ: 'notification:read',

    // Whiteboard
    WHITEBOARD_DRAW: 'whiteboard:draw',
    WHITEBOARD_CLEAR: 'whiteboard:clear',
    WHITEBOARD_SYNC: 'whiteboard:sync',

    // Collaboration
    COLLABORATION_SYNC: 'collaboration:sync',
    TASK_UPDATE: 'task:update',
    FILE_UPDATE: 'file:update'
  },

  // Theme options
  THEMES: {
    DARK: 'dark',
    LIGHT: 'light',
    CYBERPUNK: 'cyberpunk'
  },

  // Local storage keys (use sparingly)
  STORAGE_KEYS: {
    THEME: 'hf_theme',
    SIDEBAR_COLLAPSED: 'hf_sidebar_collapsed',
    RECENT_PROJECTS: 'hf_recent_projects',
    EDITOR_SETTINGS: 'hf_editor_settings'
  },

  // Limits
  LIMITS: {
    MAX_TEAM_MEMBERS: 10,
    MAX_UPLOAD_SIZE: 500 * 1024 * 1024, // 500 MB
    MAX_FILE_NAME: 255,
    MAX_TITLE_LENGTH: 200,
    MAX_DESCRIPTION_LENGTH: 5000,
    NOTIFICATION_LIMIT: 100,
    CHAT_MESSAGE_LIMIT: 50
  },

  // Timeouts
  TIMEOUTS: {
    DEBOUNCE_DELAY: 300,
    THROTTLE_DELAY: 500,
    PRESENCE_UPDATE: 5000,
    NOTIFICATION_TIMEOUT: 5000,
    SOCKET_RECONNECT: 5000
  }
};

window.HFConstants = HFConstants;
