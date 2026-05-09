from flask import Blueprint, render_template
from modules.decorators import customer_required

main_bp = Blueprint('main', __name__)

# Public — anyone can see this
@main_bp.route('/')
def landing():
    return render_template('landing.html')

# Public — anyone can see this
@main_bp.route('/about_us')
def AboutUs():
    return render_template('customer/about_us.html')

# Logged-in customers only
@main_bp.route('/home')
@customer_required
def home():
    return render_template('customer/home.html')

# Logged-in customers only
@main_bp.route('/booking_page')
@customer_required
def booking_page():
    return render_template('customer/my_bookings.html')
