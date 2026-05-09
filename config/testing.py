"""Testing configuration"""
import os

DEBUG = True
TESTING = True

# Flask
SECRET_KEY = "test-secret-key"
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# JWT
JWT_SECRET = "test-jwt-secret"
JWT_EXPIRY = 3600

# Email (EmailJS)
EMAILJS_SERVICE_ID = os.getenv("EMAILJS_SERVICE_ID")
EMAILJS_TEMPLATE_ID = os.getenv("EMAILJS_TEMPLATE_ID")
EMAILJS_PUBLIC_KEY = os.getenv("EMAILJS_PUBLIC_KEY")

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Redis
REDIS_URL = "redis://localhost:6379/1"

# Upload
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif',
    'py', 'js', 'ts', 'json', 'html', 'css'
}

# CORS
CORS_ORIGINS = ["http://localhost:5000", "http://localhost:3000"]

# Rate limiting
RATELIMIT_ENABLED = False

# Server
HOST = "127.0.0.1"
PORT = 5000
