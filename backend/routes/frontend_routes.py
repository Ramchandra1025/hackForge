"""HackForge - Frontend Routes (serve SPA)"""
from flask import Blueprint, render_template, send_from_directory
import os

frontend_bp = Blueprint('frontend', __name__)


@frontend_bp.route('/')
def index():
    return render_template('index.html')


@frontend_bp.route('/auth')
def auth():
    return render_template('auth.html')


@frontend_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@frontend_bp.route('/workspace')
def workspace():
    return render_template('workspace.html')


@frontend_bp.route('/loading')
def loading():
    return render_template('loading.html')


# Catch-all for SPA routing
@frontend_bp.route('/<path:path>')
def spa_fallback(path):
    # Serve static files normally
    if '.' in path.split('/')[-1]:
        return send_from_directory('static', path)
    # Otherwise serve SPA
    return render_template('index.html')