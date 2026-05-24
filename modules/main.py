from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user
from modules.decorators import customer_required
from modules.models import Booking

main_bp = Blueprint('main', __name__)

# Public — anyone can see this
@main_bp.route('/')
def landing():
    return render_template('landing.html')

# Public — anyone can see this
@main_bp.route('/about_us')
def AboutUs():
    return render_template('customer/about_us.html')

# Dashboard redirect based on user role
@main_bp.route('/dashboard')
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'staff':
        return redirect(url_for('staff.bookings'))
    else:
        return redirect(url_for('main.home'))

# Logged-in customers only
@main_bp.route('/home')
@customer_required
def home():
    return render_template('customer/home.html')

# Logged-in customers only
@main_bp.route('/booking_page')
@customer_required
def booking_page():
    bookings = Booking.query.filter_by(user_id=current_user.user_id)\
                            .order_by(Booking.created_at.desc()).all()
    return render_template('customer/my_bookings.html', bookings=bookings)
