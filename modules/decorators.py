from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


# ── Must be logged in as a customer ──
def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        if current_user.role != 'customer':
            flash('Access denied.', 'error')
            return redirect(url_for('main.landing'))
        return f(*args, **kwargs)
    return decorated


# ── Must be logged in as staff or admin ──
def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        if current_user.role not in ['staff', 'admin']:
            flash('Access denied.', 'error')
            return redirect(url_for('main.landing'))
        return f(*args, **kwargs)
    return decorated


# ── Must be logged in as admin only ──
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            flash('Access denied.', 'error')
            return redirect(url_for('main.landing'))
        return f(*args, **kwargs)
    return decorated
