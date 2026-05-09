"""
HackForge - Error Handlers and Response Utilities
"""

import logging
from flask import jsonify, request

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'message': str(e)}), 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401
    
    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Forbidden', 'message': 'Insufficient permissions'}), 403
    
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'message': str(e)}), 404
    
    @app.errorhandler(413)
    def request_too_large(e):
        return jsonify({'error': 'File too large', 'message': 'Upload exceeds size limit'}), 413
    
    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({'error': 'Validation error', 'message': str(e)}), 422
    
    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({'error': 'Rate limited', 'message': 'Too many requests'}), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({'error': 'Internal server error', 'message': 'Something went wrong'}), 500


def success(data=None, message=None, status=200, meta=None):
    """Standardized success response"""
    response = {'success': True}
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    if meta:
        response['meta'] = meta
    return jsonify(response), status


def error(message, status=400, details=None):
    """Standardized error response"""
    response = {'success': False, 'error': message}
    if details:
        response['details'] = details
    return jsonify(response), status


def paginate(items, total, page, per_page):
    """Paginated response"""
    return {
        'items': items,
        'meta': {
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }
    }


def validate_required(data: dict, fields: list) -> tuple:
    """Validate required fields in request data"""
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, None


def get_pagination_params():
    """Extract pagination parameters from request"""
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
    return page, per_page