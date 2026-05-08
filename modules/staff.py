from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from modules import db
from modules.models import User, Booking, CakeProgress, Cake, StaffPermission

staff_bp = Blueprint('staff', __name__)

# Only staff and admin can access these routes
def staff_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['staff', 'admin']:
            return jsonify({'message': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Check if staff has a specific permission (admin always has all permissions)
def check_permission(permission_name):
    if current_user.role == 'admin':
        return True
    perm = StaffPermission.query.filter_by(user_id=current_user.user_id).first()
    if not perm:
        return False
    return getattr(perm, permission_name, False)

# Dashboard - overview of all bookings
@staff_bp.route('/staff/dashboard')
@login_required
@staff_or_admin_required
def dashboard():
    bookings = Booking.query.all()
    return jsonify([{
        'booking_id': b.booking_id,
        'user_id': b.user_id,
        'design_notes': b.design_notes,
        'size': b.size,
        'flavor': b.flavor,
        'pickup_date': b.pickup_date.isoformat(),
        'booking_status': b.booking_status,
        'total_price': str(b.total_price)
    } for b in bookings])

# Accept or decline a booking (requires can_approve_orders permission)
@staff_bp.route('/staff/bookings/<int:booking_id>/respond', methods=['POST'])
@login_required
@staff_or_admin_required
def respond_booking(booking_id):
    if not check_permission('can_approve_orders'):
        return jsonify({'message': 'You do not have permission to approve/decline bookings'}), 403

    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json() if request.is_json else request.form
    new_status = data.get('booking_status')
    if new_status not in ['Accepted', 'Declined']:
        return jsonify({'message': 'Invalid status'}), 400

    booking.booking_status = new_status
    db.session.commit()
    return jsonify({'message': f'Booking {new_status}'})

# Set the price after accepting a booking (requires can_set_price permission)
@staff_bp.route('/staff/bookings/<int:booking_id>/set_price', methods=['POST'])
@login_required
@staff_or_admin_required
def set_price(booking_id):
    if not check_permission('can_set_price'):
        return jsonify({'message': 'You do not have permission to set prices'}), 403

    booking = Booking.query.get_or_404(booking_id)
    if booking.booking_status != 'Accepted':
        return jsonify({'message': 'Booking must be accepted first'}), 400

    data = request.get_json() if request.is_json else request.form
    price = data.get('total_price')
    booking.total_price = price
    db.session.commit()
    return jsonify({'message': f'Price set to {price}'})

# Update cake progress (requires can_update_progress permission)
@staff_bp.route('/staff/bookings/<int:booking_id>/progress', methods=['POST'])
@login_required
@staff_or_admin_required
def update_progress(booking_id):
    if not check_permission('can_update_progress'):
        return jsonify({'message': 'You do not have permission to update cake progress'}), 403

    booking = Booking.query.get_or_404(booking_id)
    if booking.booking_status != 'Accepted':
        return jsonify({'message': 'Booking must be accepted first'}), 400

    data = request.get_json() if request.is_json else request.form
    cake_status = data.get('cake_status')
    if cake_status not in ['not_started', 'ongoing', 'completed']:
        return jsonify({'message': 'Invalid cake status'}), 400

    progress = CakeProgress(
        booking_id=booking_id,
        cake_status=cake_status,
        updated_by=current_user.user_id
    )
    db.session.add(progress)
    db.session.commit()
    return jsonify({'message': f'Cake status updated to {cake_status}'})

# Edit a cake design (requires can_edit_gallery permission)
@staff_bp.route('/staff/gallery/<int:cake_id>/edit', methods=['POST'])
@login_required
@staff_or_admin_required
def edit_cake(cake_id):
    if not check_permission('can_edit_gallery'):
        return jsonify({'message': 'You do not have permission to edit gallery'}), 403

    cake = Cake.query.get_or_404(cake_id)
    data = request.get_json() if request.is_json else request.form
    cake.design_name = data.get('design_name', cake.design_name)
    cake.description = data.get('description', cake.description)
    cake.category = data.get('category', cake.category)
    cake.base_price = data.get('base_price', cake.base_price)
    cake.image_url = data.get('image_url', cake.image_url)
    db.session.commit()
    return jsonify({'message': 'Cake design updated!'})

# Calendar view - groups accepted bookings by pickup date
@staff_bp.route('/staff/calendar')
@login_required
@staff_or_admin_required
def calendar():
    bookings = Booking.query.filter_by(booking_status='Accepted').all()
    calendar_data = {}
    for b in bookings:
        date_str = b.pickup_date.isoformat()
        if date_str not in calendar_data:
            calendar_data[date_str] = []
        calendar_data[date_str].append({
            'booking_id': b.booking_id,
            'design_notes': b.design_notes,
            'size': b.size
        })
    return jsonify(calendar_data)

# Shows all bookings for a specific date (when staff clicks a date)
@staff_bp.route('/staff/calendar/<string:date>')
@login_required
@staff_or_admin_required
def calendar_date(date):
    bookings = Booking.query.filter_by(pickup_date=date, booking_status='Accepted').all()
    return jsonify([{
        'booking_id': b.booking_id,
        'user_id': b.user_id,
        'design_notes': b.design_notes,
        'size': b.size,
        'flavor': b.flavor,
        'booking_status': b.booking_status,
        'total_price': str(b.total_price)
    } for b in bookings])
