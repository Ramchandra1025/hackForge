"""Development configuration"""
import os

DEBUG = True
TESTING = False

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "jwt-secret-key")
JWT_EXPIRY = 3600 * 24 * 7  # 7 days

# Email (EmailJS)
EMAILJS_SERVICE_ID = os.getenv("EMAILJS_SERVICE_ID")
EMAILJS_TEMPLATE_ID = os.getenv("EMAILJS_TEMPLATE_ID")
EMAILJS_PUBLIC_KEY = os.getenv("EMAILJS_PUBLIC_KEY")

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Upload
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp',
    'mp4', 'avi', 'mov', 'webm',
    'mp3', 'wav', 'ogg',
    'zip', 'rar', '7z', 'tar', 'gz',
    'py', 'js', 'ts', 'jsx', 'tsx', 'java', 'cpp', 'c', 'go', 'rs',
    'html', 'css', 'scss', 'json', 'yaml', 'yml', 'xml',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'
}

# CORS
CORS_ORIGINS = ["http://localhost:5000", "http://localhost:3000"]

# Rate limiting
RATELIMIT_ENABLED = True
RATELIMIT_STORAGE_URL = os.getenv("REDIS_URL", "memory://")

# Server
HOST = "0.0.0.0"
PORT = 5000
