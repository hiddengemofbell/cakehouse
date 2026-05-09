from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
import os
import cloudinary
import cloudinary.uploader
from modules import db
from modules.models import User, Booking, CakeProgress, Cake, StaffPermission, Category
from modules.decorators import staff_required

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

staff_bp = Blueprint('staff', __name__)

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
@staff_required
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
@staff_required
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
@staff_required
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
@staff_required
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

# Gallery — staff sees approved+visible photos; can upload (pending admin approval)
@staff_bp.route('/staff/gallery')
@staff_required
def gallery():
    cakes      = Cake.query.filter_by(is_visible=True, is_approved=True).all()
    can_upload = check_permission('can_edit_gallery')
    categories = Category.query.order_by(Category.name).all()
    return render_template('staff/gallery.html', cakes=cakes,
                           can_upload=can_upload, categories=categories)

# Upload a new cake photo (requires can_edit_gallery permission)
@staff_bp.route('/staff/gallery/upload', methods=['POST'])
@staff_required
def upload_cake():
    if not check_permission('can_edit_gallery'):
        flash('You do not have permission to upload photos.', 'error')
        return redirect(url_for('staff.gallery'))

    image_url = None
    file = request.files.get('image')
    if file and file.filename:
        result = cloudinary.uploader.upload(file, folder='lizas-cakehouse')
        image_url = result['secure_url']

    category = request.form.get('category', '').strip()
    if category and not Category.query.filter_by(name=category).first():
        db.session.add(Category(name=category))

    new_cake = Cake(
        design_name=request.form.get('design_name'),
        description=request.form.get('description'),
        category=category,
        base_price=0,
        image_url=image_url,
        is_approved=False   # needs admin approval before showing to customers
    )
    db.session.add(new_cake)
    db.session.commit()
    flash('Photo submitted! It will appear in the gallery once approved by an admin.', 'success')
    return redirect(url_for('staff.gallery'))

# Edit a cake design (requires can_edit_gallery permission)
@staff_bp.route('/staff/gallery/<int:cake_id>/edit', methods=['POST'])
@staff_required
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
@staff_required
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
@staff_required
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
