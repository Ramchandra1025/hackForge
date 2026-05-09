/**
 * API Client
 */

window.HF = window.HF || {};

const HFAPI = {
  baseURL: '/api',
  timeout: 30000,

  /**
   * Make API request
   */
  async request(endpoint, options = {}) {
    const {
      method = 'GET',
      headers = {},
      body = null,
      timeout = this.timeout
    } = options;

    const url = this.baseURL + endpoint;

    const config = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers
      }
    };

    if (body) {
      config.body = JSON.stringify(body);
    }

    // Add timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    config.signal = controller.signal;

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      console.error('API Error:', error);
      throw error;
    }
  },

  // Auth APIs
  auth: {
    signup: (email, username, password) => HFAPI.request('/auth/signup', {
      method: 'POST',
      body: { email, username, password }
    }),

    verifyOTP: (email, otp) => HFAPI.request('/auth/verify-otp', {
      method: 'POST',
      body: { email, otp }
    }),

    login: (emailOrUsername, password) => HFAPI.request('/auth/login', {
      method: 'POST',
      body: { emailOrUsername, password }
    }),

    logout: () => HFAPI.request('/auth/logout', { method: 'POST' }),

    forgotPassword: (email) => HFAPI.request('/auth/forgot-password', {
      method: 'POST',
      body: { email }
    }),

    resetPassword: (email, otp, newPassword) => HFAPI.request('/auth/reset-password', {
      method: 'POST',
      body: { email, otp, newPassword }
    })
  },

  // User APIs
  users: {
    getProfile: () => HFAPI.request('/users/profile'),

    updateProfile: (data) => HFAPI.request('/users/profile', {
      method: 'PATCH',
      body: data
    }),

    searchUsers: (query) => HFAPI.request(`/users/search?q=${encodeURIComponent(query)}`),

    getUser: (userId) => HFAPI.request(`/users/${userId}`)
  },

  // Team APIs
  teams: {
    list: () => HFAPI.request('/teams'),

    create: (data) => HFAPI.request('/teams', {
      method: 'POST',
      body: data
    }),

    get: (teamId) => HFAPI.request(`/teams/${teamId}`),

    update: (teamId, data) => HFAPI.request(`/teams/${teamId}`, {
      method: 'PATCH',
      body: data
    }),

    delete: (teamId) => HFAPI.request(`/teams/${teamId}`, { method: 'DELETE' }),

    getMembers: (teamId) => HFAPI.request(`/teams/${teamId}/members`),

    addMember: (teamId, userId, role) => HFAPI.request(`/teams/${teamId}/members`, {
      method: 'POST',
      body: { userId, role }
    }),

    removeMember: (teamId, userId) => HFAPI.request(`/teams/${teamId}/members/${userId}`, {
      method: 'DELETE'
    }),

    updateMemberRole: (teamId, userId, role) => HFAPI.request(`/teams/${teamId}/members/${userId}`, {
      method: 'PATCH',
      body: { role }
    })
  },

  // Project APIs
  projects: {
    list: () => HFAPI.request('/projects'),

    create: (data) => HFAPI.request('/projects', {
      method: 'POST',
      body: data
    }),

    get: (projectId) => HFAPI.request(`/projects/${projectId}`),

    update: (projectId, data) => HFAPI.request(`/projects/${projectId}`, {
      method: 'PATCH',
      body: data
    }),

    delete: (projectId) => HFAPI.request(`/projects/${projectId}`, { method: 'DELETE' })
  },

  // Task APIs
  tasks: {
    list: (projectId) => HFAPI.request(`/tasks?projectId=${projectId}`),

    create: (data) => HFAPI.request('/tasks', {
      method: 'POST',
      body: data
    }),

    get: (taskId) => HFAPI.request(`/tasks/${taskId}`),

    update: (taskId, data) => HFAPI.request(`/tasks/${taskId}`, {
      method: 'PATCH',
      body: data
    }),

    delete: (taskId) => HFAPI.request(`/tasks/${taskId}`, { method: 'DELETE' }),

    addComment: (taskId, content) => HFAPI.request(`/tasks/${taskId}/comments`, {
      method: 'POST',
      body: { content }
    }),

    getComments: (taskId) => HFAPI.request(`/tasks/${taskId}/comments`)
  },

  // File APIs
  files: {
    list: (projectId) => HFAPI.request(`/files?projectId=${projectId}`),

    get: (fileId) => HFAPI.request(`/files/${fileId}`),

    delete: (fileId) => HFAPI.request(`/files/${fileId}`, { method: 'DELETE' }),

    getVersions: (fileId) => HFAPI.request(`/files/${fileId}/versions`),

    getSignedURL: (fileId) => HFAPI.request(`/files/${fileId}/signed-url`)
  },

  // AI APIs
  ai: {
    reviewCode: (code) => HFAPI.request('/ai/review', {
      method: 'POST',
      body: { code }
    }),

    generateReadme: (projectDescription) => HFAPI.request('/ai/readme', {
      method: 'POST',
      body: { projectDescription }
    }),

    findBugs: (code) => HFAPI.request('/ai/bugs', {
      method: 'POST',
      body: { code }
    }),

    planSprint: (tasks) => HFAPI.request('/ai/sprint', {
      method: 'POST',
      body: { tasks }
    }),

    getMemory: () => HFAPI.request('/ai/memory')
  },

  // Deployment APIs
  deployments: {
    list: (projectId) => HFAPI.request(`/deployments?projectId=${projectId}`),

    create: (data) => HFAPI.request('/deployments', {
      method: 'POST',
      body: data
    }),

    get: (deploymentId) => HFAPI.request(`/deployments/${deploymentId}`),

    getLogs: (deploymentId) => HFAPI.request(`/deployments/${deploymentId}/logs`)
  }
};

window.HFAPI = HFAPI;
