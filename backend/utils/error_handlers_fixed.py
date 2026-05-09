"""Error handlers for Flask app"""
from flask import jsonify, request


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


def register_error_handlers(app):
    """Register all error handlers"""

    @app.errorhandler(400)
    def bad_request(err):
        return jsonify({'error': 'Bad request', 'message': str(err.description)}), 400

    @app.errorhandler(401)
    def unauthorized(err):
        return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401

    @app.errorhandler(403)
    def forbidden(err):
        return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403

    @app.errorhandler(404)
    def not_found(err):
        return jsonify({'error': 'Not found', 'message': 'Resource not found'}), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(err):
        return jsonify({'error': 'Rate limit exceeded', 'message': 'Too many requests'}), 429

    @app.errorhandler(500)
    def internal_error(err):
        return jsonify({'error': 'Internal server error', 'message': str(err)}), 500

    @app.errorhandler(Exception)
    def handle_exception(err):
        return jsonify({'error': 'Error', 'message': str(err)}), 500
