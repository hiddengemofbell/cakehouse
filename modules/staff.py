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

# Dashboard / Bookings list
@staff_bp.route('/staff/dashboard')
@staff_bp.route('/staff/bookings')
@staff_required
def bookings():
    status_filter = request.args.get('status', 'all')
    query = Booking.query.order_by(Booking.created_at.desc())
    if status_filter != 'all':
        query = query.filter_by(booking_status=status_filter.capitalize())
    all_bookings = query.all()
    users = {u.user_id: u for u in User.query.all()}
    progress_map = {}
    for cp in CakeProgress.query.order_by(CakeProgress.updated_at.desc()).all():
        if cp.booking_id not in progress_map:
            progress_map[cp.booking_id] = cp.cake_status
    counts = {
        'all':       Booking.query.count(),
        'pending':   Booking.query.filter_by(booking_status='Pending').count(),
        'accepted':  Booking.query.filter_by(booking_status='Accepted').count(),
        'declined':  Booking.query.filter_by(booking_status='Declined').count(),
        'cancelled': Booking.query.filter_by(booking_status='Cancelled').count(),
    }
    perm = StaffPermission.query.filter_by(user_id=current_user.user_id).first()
    return render_template('staff/bookings.html',
                           bookings=all_bookings, users=users,
                           progress_map=progress_map,
                           counts=counts, active=status_filter, perm=perm)

# Accept or decline a booking (requires can_approve_orders permission)
@staff_bp.route('/staff/bookings/<int:booking_id>/respond', methods=['POST'])
@staff_required
def respond_booking(booking_id):
    if not check_permission('can_approve_orders'):
        flash('You do not have permission to approve/decline bookings.', 'error')
        return redirect(url_for('staff.bookings'))

    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('booking_status')
    if new_status == 'Accepted':
        price = request.form.get('total_price', '').strip()
        if not price:
            flash('Please set a price before accepting.', 'error')
            return redirect(url_for('staff.bookings', status=request.args.get('status', 'all')))
        booking.booking_status = 'Accepted'
        booking.total_price = float(price)
        db.session.commit()
        flash('Booking accepted and price set.', 'success')
    elif new_status == 'Declined':
        reason = request.form.get('decline_reason', '').strip()
        if not reason:
            flash('Please provide a reason for declining.', 'error')
            return redirect(url_for('staff.bookings', status=request.args.get('status', 'all')))
        booking.booking_status = 'Declined'
        booking.decline_reason = reason
        db.session.commit()
        flash('Booking declined.', 'error')
    return redirect(url_for('staff.bookings', status=request.args.get('status', 'all')))

# Set the price after accepting a booking (requires can_set_price permission)
@staff_bp.route('/staff/bookings/<int:booking_id>/set_price', methods=['POST'])
@staff_required
def set_price(booking_id):
    if not check_permission('can_set_price'):
        flash('You do not have permission to set prices.', 'error')
        return redirect(url_for('staff.bookings'))

    booking = Booking.query.get_or_404(booking_id)
    price = request.form.get('total_price', '').strip()
    if price:
        booking.total_price = float(price)
        db.session.commit()
        flash('Price updated.', 'success')
    return redirect(url_for('staff.bookings', status='accepted'))

# Update cake progress (requires can_update_progress permission)
@staff_bp.route('/staff/bookings/<int:booking_id>/progress', methods=['POST'])
@staff_required
def update_progress(booking_id):
    if not check_permission('can_update_progress'):
        flash('You do not have permission to update cake progress.', 'error')
        return redirect(url_for('staff.bookings'))

    booking = Booking.query.get_or_404(booking_id)
    cake_status = request.form.get('cake_status')
    if cake_status in ['not_started', 'ongoing', 'completed']:
        progress = CakeProgress(
            booking_id=booking_id,
            cake_status=cake_status,
            updated_by=current_user.user_id
        )
        db.session.add(progress)
        db.session.commit()
        flash('Progress updated.', 'success')
    return redirect(url_for('staff.bookings', status='accepted'))

# Gallery — staff sees approved+visible photos + pending uploads awaiting admin approval
@staff_bp.route('/staff/gallery')
@staff_required
def gallery():
    cakes      = Cake.query.filter_by(is_visible=True, is_approved=True).all()
    pending    = Cake.query.filter_by(is_approved=False).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template('staff/gallery.html', cakes=cakes, pending=pending,
                           categories=categories)

# Upload a new cake photo (requires can_edit_gallery permission)
@staff_bp.route('/staff/gallery/upload', methods=['POST'])
@staff_required
def upload_cake():
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

# Calendar view
@staff_bp.route('/staff/calendar')
@staff_required
def calendar():
    from datetime import datetime as dt
    import calendar as cal_mod
    year  = int(request.args.get('year',  dt.today().year))
    month = int(request.args.get('month', dt.today().month))

    # All accepted bookings for this month
    bookings = Booking.query.filter(
        Booking.booking_status == 'Accepted',
        db.extract('year',  Booking.pickup_date) == year,
        db.extract('month', Booking.pickup_date) == month
    ).all()

    users = {u.user_id: u for u in User.query.all()}

    # Group bookings by day
    by_day = {}
    for b in bookings:
        day = b.pickup_date.day
        by_day.setdefault(day, []).append(b)

    # Build calendar grid (list of weeks, each week = 7 days or None)
    cal = cal_mod.monthcalendar(year, month)
    month_name = dt(year, month, 1).strftime('%B %Y')

    # Prev / next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    return render_template('calendar.html',
        cal=cal, by_day=by_day, users=users,
        month_name=month_name, year=year, month=month,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        max_per_day=3, role='staff'
    )
