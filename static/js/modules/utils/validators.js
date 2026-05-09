/**
 * Input Validators
 */

window.HF = window.HF || {};

const HFValidators = {
  // Validate password
  validatePassword(password) {
    if (password.length < 4 || password.length > 20) {
      return { valid: false, error: 'Password must be 4-20 characters' };
    }
    return { valid: true };
  },

  // Validate username
  validateUsername(username) {
    if (username.length < 3 || username.length > 30) {
      return { valid: false, error: 'Username must be 3-30 characters' };
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(username)) {
      return { valid: false, error: 'Username can only contain letters, numbers, underscores, and hyphens' };
    }
    return { valid: true };
  },

  // Validate email
  validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!re.test(email)) {
      return { valid: false, error: 'Invalid email format' };
    }
    return { valid: true };
  },

  // Validate URL
  validateURL(url) {
    try {
      new URL(url);
      return { valid: true };
    } catch (_) {
      return { valid: false, error: 'Invalid URL format' };
    }
  },

  // Validate team name
  validateTeamName(name) {
    if (name.length < 3 || name.length > 50) {
      return { valid: false, error: 'Team name must be 3-50 characters' };
    }
    return { valid: true };
  },

  // Validate project name
  validateProjectName(name) {
    if (name.length < 1 || name.length > 100) {
      return { valid: false, error: 'Project name must be 1-100 characters' };
    }
    return { valid: true };
  },

  // Validate task title
  validateTaskTitle(title) {
    if (title.length < 1 || title.length > 200) {
      return { valid: false, error: 'Task title must be 1-200 characters' };
    }
    return { valid: true };
  },

  // Validate file upload
  validateFileUpload(file, maxSize = 500 * 1024 * 1024) {
    if (file.size > maxSize) {
      return { valid: false, error: `File size exceeds ${HFHelpers.formatFileSize(maxSize)}` };
    }

    const allowedExtensions = [
      'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp',
      'mp4', 'avi', 'mov', 'webm',
      'mp3', 'wav', 'ogg',
      'zip', 'rar', '7z', 'tar', 'gz',
      'py', 'js', 'ts', 'jsx', 'tsx', 'java', 'cpp', 'c', 'go', 'rs',
      'html', 'css', 'scss', 'json', 'yaml', 'yml', 'xml',
      'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'
    ];

    const extension = file.name.split('.').pop().toLowerCase();
    if (!allowedExtensions.includes(extension)) {
      return { valid: false, error: `File type .${extension} is not allowed` };
    }

    return { valid: true };
  },

  // Validate OTP
  validateOTP(otp) {
    if (!/^\d{6}$/.test(otp)) {
      return { valid: false, error: 'OTP must be 6 digits' };
    }
    return { valid: true };
  },

  // Validate text length
  validateTextLength(text, min = 0, max = 1000) {
    if (text.length < min || text.length > max) {
      return { valid: false, error: `Text must be ${min}-${max} characters` };
    }
    return { valid: true };
  }
};

window.HFValidators = HFValidators;
