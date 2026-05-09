"""HackForge - Application Constants"""

# Roles
ROLES = ['owner', 'admin', 'developer', 'designer', 'viewer', 'judge']

# Task statuses
TASK_STATUSES = ['backlog', 'todo', 'in_progress', 'review', 'done', 'cancelled']

# Task priorities
TASK_PRIORITIES = ['critical', 'high', 'medium', 'low']

# Project statuses
PROJECT_STATUSES = ['planning', 'active', 'paused', 'completed', 'archived']

# Deployment statuses
DEPLOY_STATUSES = ['pending', 'building', 'deploying', 'live', 'failed', 'cancelled']

# File size limits
MAX_CHUNK_SIZE = 5 * 1024 * 1024   # 5MB chunks

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Cache TTLs (seconds)
CACHE_SHORT = 60
CACHE_MEDIUM = 300
CACHE_LONG = 3600

# Team limits
MAX_TEAM_MEMBERS = 10
MAX_PROJECTS_PER_TEAM = 50

# AI
AI_MAX_CONTEXT_TOKENS = 8000
AI_MEMORY_LIMIT = 100