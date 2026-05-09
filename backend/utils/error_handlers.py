"""Error handlers for Flask app"""
from flask import jsonify

"""Error handlers for Flask app"""
from flask import jsonify, request
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def success(data=None, message='Success', status_code=200):
    """Format success response"""
    return jsonify({
        'success': True,
        'message': message,
        'data': data
    }), status_code


def error(message='Error', error_code='UNKNOWN_ERROR', status_code=400, details=None):
    """Format error response"""
    response = {
        'success': False,
        'error': error_code,
        'message': message
    }
    if details:
        response['details'] = details
    return jsonify(response), status_code


def validate_required(data, required_fields):
    """Validate required fields in request"""
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            missing.append(field)
    
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, None

def get_pagination_params(default_limit=20, max_limit=100):
    """Extract and validate pagination parameters from request"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', default_limit, type=int)
    
    # Validate
    if page < 1:
        page = 1
    if limit < 1:
        limit = default_limit
    if limit > max_limit:
        limit = max_limit
    
    offset = (page - 1) * limit
    return {'page': page, 'limit': limit, 'offset': offset}


def register_error_handlers(app):
    """Register all error handlers"""

    @app.errorhandler(400)
    def bad_request(err):
        return error('Bad request', 'BAD_REQUEST', 400, str(err.description))

    @app.errorhandler(401)
    def unauthorized(err):
        return error('Unauthorized', 'UNAUTHORIZED', 401)

    @app.errorhandler(403)
    def forbidden(err):
        return error('Forbidden', 'FORBIDDEN', 403)

    @app.errorhandler(404)
    def not_found(err):
        return error('Not found', 'NOT_FOUND', 404)

    @app.errorhandler(429)
    def rate_limit_exceeded(err):
        return error('Rate limit exceeded', 'RATE_LIMIT_EXCEEDED', 429)

    @app.errorhandler(500)
    def internal_error(err):
        logger.error(f"Internal error: {err}")
        return error('Internal server error', 'INTERNAL_ERROR', 500)

    @app.errorhandler(Exception)
    def handle_exception(err):
        logger.error(f"Unhandled exception: {err}")
        return error('An error occurred', 'INTERNAL_ERROR', 500)
