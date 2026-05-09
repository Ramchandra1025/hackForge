"""
HackForge Workspace - Main Application Entry Point
Production-grade collaborative developer platform
"""

import os
import logging
from flask import Flask, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from dotenv import load_dotenv

from backend.utils.db import init_db
from backend.utils.redis_client import init_redis
from backend.utils.error_handlers import register_error_handlers
from backend.utils.security import configure_security

# ─────────────────────────────────────────────────────────────
# Load Environment Variables
# ─────────────────────────────────────────────────────────────
load_dotenv()


# ─────────────────────────────────────────────────────────────
# Create Flask App
# ─────────────────────────────────────────────────────────────
def create_app():
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )

    # ─────────────────────────────────────────────────────────
    # Core Config
    # ─────────────────────────────────────────────────────────
    app.config['SECRET_KEY'] = os.getenv(
        'SECRET_KEY',
        'hackforge-dev-secret-change-in-production'
    )

    app.config['JWT_SECRET'] = os.getenv(
        'JWT_SECRET',
        'hackforge-jwt-secret-change-in-production'
    )

    app.config['JWT_EXPIRY'] = int(
        os.getenv('JWT_EXPIRY', 86400)
    )

    app.config['COOKIE_DOMAIN'] = os.getenv(
        'COOKIE_DOMAIN',
        None
    )

    app.config['DEBUG'] = os.getenv(
        'FLASK_DEBUG',
        'false'
    ).lower() == 'true'

    app.config['TESTING'] = False

    # ─────────────────────────────────────────────────────────
    # Supabase Config
    # ─────────────────────────────────────────────────────────
    app.config['SUPABASE_URL'] = os.getenv('SUPABASE_URL', '')

    # IMPORTANT:
    # Use SERVICE ROLE KEY to bypass RLS
    app.config['SUPABASE_SERVICE_KEY'] = os.getenv(
        'SUPABASE_SERVICE_KEY',
        ''
    )

    # fallback
    app.config['SUPABASE_KEY'] = os.getenv(
        'SUPABASE_KEY',
        app.config['SUPABASE_SERVICE_KEY']
    )

    # ─────────────────────────────────────────────────────────
    # Redis Config
    # ─────────────────────────────────────────────────────────
    app.config['REDIS_URL'] = os.getenv(
        'REDIS_URL',
        'redis://localhost:6379/0'
    )

    # ─────────────────────────────────────────────────────────
    # AI Config
    # ─────────────────────────────────────────────────────────
    app.config['GEMINI_API_KEY'] = os.getenv(
        'GEMINI_API_KEY',
        ''
    )

    # ─────────────────────────────────────────────────────────
    # Upload Config
    # ─────────────────────────────────────────────────────────
    app.config['MAX_UPLOAD_SIZE_MB'] = int(
        os.getenv('MAX_UPLOAD_SIZE_MB', 100)
    )

    app.config['ALLOWED_EXTENSIONS'] = os.getenv(
        'ALLOWED_EXTENSIONS',
        'jpg,jpeg,png,gif,webp,pdf,doc,docx,txt,md,py,js,ts,html,css,json,zip,tar,gz,mp4,mp3,svg,csv,xlsx'
    ).split(',')

    # ─────────────────────────────────────────────────────────
    # CORS Config
    # ─────────────────────────────────────────────────────────
    cors_origins = os.getenv(
        'CORS_ORIGINS',
        'http://localhost:5000,http://127.0.0.1:5000'
    ).split(',')

    app.config['CORS_ORIGINS'] = cors_origins

    # ─────────────────────────────────────────────────────────
    # Flask CORS
    # ─────────────────────────────────────────────────────────
    CORS(
        app,
        resources={r"/*": {"origins": cors_origins}},
        supports_credentials=True,
        allow_headers=[
            'Content-Type',
            'Authorization',
            'X-CSRF-Token'
        ],
        methods=[
            'GET',
            'POST',
            'PUT',
            'PATCH',
            'DELETE',
            'OPTIONS'
        ]
    )

    # ─────────────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s'
    )

    logger = logging.getLogger(__name__)

    logger.info("Starting HackForge Workspace")

    # ─────────────────────────────────────────────────────────
    # Initialize Services
    # ─────────────────────────────────────────────────────────
    try:
        init_db(app)
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    try:
        init_redis(app)
        logger.info("Redis initialized")
    except Exception as e:
        logger.warning(f"Redis init failed: {e}")

    try:
        configure_security(app)
        logger.info("Security configured")
    except Exception as e:
        logger.error(f"Security config failed: {e}")

    # ─────────────────────────────────────────────────────────
    # Register Blueprints
    # ─────────────────────────────────────────────────────────
    try:
        from backend.routes.auth_routes import auth_bp
        from backend.routes.file_routes import storage_routes as files_bp
        from backend.routes.team_routes import team_bp
        from backend.routes.project_routes import project_bp
        from backend.routes.task_routes import task_bp
        from backend.routes.chat_routes import chat_bp
        from backend.routes.storage_routes import storage_bp
        from backend.routes.ai_routes import ai_bp
        from backend.routes.deployment_routes import deployment_bp
        from backend.routes.notification_routes import notification_bp
        from backend.routes.search_routes import search_bp
        from backend.routes.meeting_routes import meeting_bp
        from backend.routes.wiki_routes import wiki_bp
        from backend.routes.analytics_routes import analytics_bp
        from backend.routes.admin_routes import admin_bp
        from backend.routes.integration_routes import integration_bp
        from backend.routes.frontend_routes import frontend_bp

        # frontend
        app.register_blueprint(frontend_bp)

        # api
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(files_bp, url_prefix='/api/files')
        app.register_blueprint(team_bp, url_prefix='/api/teams')
        app.register_blueprint(project_bp, url_prefix='/api/projects')
        app.register_blueprint(task_bp, url_prefix='/api/tasks')
        app.register_blueprint(chat_bp, url_prefix='/api/chat')
        app.register_blueprint(storage_bp, url_prefix='/api/storage')
        app.register_blueprint(ai_bp, url_prefix='/api/ai')
        app.register_blueprint(deployment_bp, url_prefix='/api/deployments')
        app.register_blueprint(notification_bp, url_prefix='/api/notifications')
        app.register_blueprint(search_bp, url_prefix='/api/search')
        app.register_blueprint(meeting_bp, url_prefix='/api/meetings')
        app.register_blueprint(wiki_bp, url_prefix='/api/wiki')
        app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
        app.register_blueprint(admin_bp, url_prefix='/api/admin')
        app.register_blueprint(integration_bp, url_prefix='/api/integrations')

        logger.info("Blueprints registered")

    except Exception as e:
        logger.error(f"Blueprint registration failed: {e}")

    # ─────────────────────────────────────────────────────────
    # Error Handlers
    # ─────────────────────────────────────────────────────────
    register_error_handlers(app)

    # ─────────────────────────────────────────────────────────
    # Health Check
    # ─────────────────────────────────────────────────────────
    @app.route('/api/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'service': 'HackForge Workspace'
        }), 200

    # ─────────────────────────────────────────────────────────
    # Root Route
    # ─────────────────────────────────────────────────────────
    @app.route('/')
    def home():
        return jsonify({
            'message': 'HackForge Workspace Running'
        })

    return app


# ─────────────────────────────────────────────────────────────
# Create SocketIO
# ─────────────────────────────────────────────────────────────
def create_socketio(app):

    socketio = SocketIO(
        app,

        # FIXED SOCKET CORS
        cors_allowed_origins="*",

        async_mode='threading',

        logger=True,
        engineio_logger=True,

        cookie='hackforge_sid',

        manage_session=False,

        ping_timeout=60,
        ping_interval=25,

        transports=['polling', 'websocket']
    )

    # Register Socket Handlers
    from backend.services.socket_service import register_socket_handlers
    from backend.sockets.chat_socket import register_chat_socket
    from backend.sockets.collaboration_socket import register_collaboration_socket
    from backend.sockets.notification_socket import register_notification_socket
    from backend.sockets.presence_socket import register_presence_socket
    from backend.sockets.terminal_socket import register_terminal_socket
    from backend.sockets.whiteboard_socket import register_whiteboard_socket

    register_socket_handlers(socketio)
    register_chat_socket(socketio)
    register_collaboration_socket(socketio)
    register_notification_socket(socketio)
    register_presence_socket(socketio)
    register_terminal_socket(socketio)
    register_whiteboard_socket(socketio)

    return socketio


# ─────────────────────────────────────────────────────────────
# Initialize App
# ─────────────────────────────────────────────────────────────
app = create_app()

socketio = create_socketio(app)


# ─────────────────────────────────────────────────────────────
# Main Entry
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':

    port = int(os.getenv('PORT', 5000))

    debug = os.getenv(
        'FLASK_DEBUG',
        'false'
    ).lower() == 'true'

    print(f"""
╔═══════════════════════════════════════════════════╗
║          HackForge Workspace Starting             ║
║          http://localhost:{port}                    ║
╚═══════════════════════════════════════════════════╝
    """)

    print("SUPABASE URL:", os.getenv("SUPABASE_URL"))
    # Check both common env var names for the service role key
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    anon_key = os.getenv("SUPABASE_ANON_KEY")

    if service_role_key:
        print("SUPABASE SERVICE ROLE KEY LOADED")
    else:
        print("WARNING: SUPABASE SERVICE ROLE KEY NOT FOUND (SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY)")

    if anon_key:
        print("SUPABASE ANON KEY LOADED")

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True
    )