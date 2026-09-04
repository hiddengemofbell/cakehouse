from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
import os
import cloudinary
import cloudinary.uploader
from modules import db
from modules.models import User, Booking, Cake, StaffPermission, Category, BookingSpec
from modules.decorators import staff_required
import os

staff_bp = Blueprint('staff', __name__)

# Check if staff has a specific permission (admin always has all permissions)
def check_permission(permission_name):
    if current_user.role == 'admin':
        return True
    perm = StaffPermission.query.filter_by(user_id=current_user.user_id).first()
    if not perm:
        return False
    return getattr(perm, permission_name, False)

# Dashboard - Staff overview and stats
@staff_bp.route('/staff/dashboard')
@staff_required
def dashboard():
    from sqlalchemy import func, extract
    from datetime import date

    today = date.today()

    # ── Dashboard stats ──
    total_bookings = Booking.query.count()
    pending_count = Booking.query.filter_by(booking_status='Pending').count()
    accepted_count = Booking.query.filter_by(booking_status='Accepted').count()
    declined_count = Booking.query.filter_by(booking_status='Declined').count()
    cancelled_count = Booking.query.filter_by(booking_status='Cancelled').count()

    total_revenue = db.session.query(
        func.coalesce(func.sum(Booking.total_price), 0)
    ).filter_by(booking_status='Accepted').scalar()

    this_month_orders = Booking.query.filter(
        extract('year',  Booking.created_at) == today.year,
        extract('month', Booking.created_at) == today.month
    ).count()

    this_month_revenue = db.session.query(
        func.coalesce(func.sum(Booking.total_price), 0)
    ).filter(
        Booking.booking_status == 'Accepted',
        extract('year',  Booking.pickup_date) == today.year,
        extract('month', Booking.pickup_date) == today.month
    ).scalar()

    # Monthly orders this year (for chart)
    monthly_data = db.session.query(
        extract('month', Booking.pickup_date).label('month'),
        func.count(Booking.booking_id).label('count')
    ).filter(
        extract('year', Booking.pickup_date) == today.year
    ).group_by('month').all()

    monthly_orders = [0] * 12
    for row in monthly_data:
        monthly_orders[int(row.month) - 1] = row.count

    # Top 5 flavors
    top_flavors = db.session.query(
        BookingSpec.flavor,
        func.count(Booking.booking_id).label('count')
    ).join(Booking, BookingSpec.booking_id == Booking.booking_id)\
     .group_by(BookingSpec.flavor)\
     .order_by(func.count(Booking.booking_id).desc())\
     .limit(5).all()
    top_flavors = [{'flavor': r.flavor, 'count': r.count} for r in top_flavors]

    counts = {
        'all':       total_bookings,
        'pending':   pending_count,
        'accepted':  accepted_count,
        'declined':  declined_count,
        'cancelled': cancelled_count,
    }

    return render_template(
        'staff/dashboard.html',
        title='Staff Dashboard',
        counts=counts,
        total_revenue=float(total_revenue),
        this_month_orders=this_month_orders,
        this_month_revenue=float(this_month_revenue),
        monthly_orders=monthly_orders,
        top_flavors=top_flavors,
    )

# Bookings list
@staff_bp.route('/staff/bookings')
@staff_required
def bookings():
    from sqlalchemy import func, extract
    from datetime import date

    today = date.today()
    status_filter = request.args.get('status', 'all')

    query = Booking.query.order_by(Booking.created_at.desc())
    if status_filter != 'all':
        query = query.filter_by(booking_status=status_filter.capitalize())
    all_bookings = query.all()

    users = {u.user_id: u for u in User.query.all()}

    # Progress is now a direct column on Booking
    progress_map = {b.booking_id: b.cake_status or 'not_started' for b in all_bookings}

    counts = {
        'all':       Booking.query.count(),
        'pending':   Booking.query.filter_by(booking_status='Pending').count(),
        'accepted':  Booking.query.filter_by(booking_status='Accepted').count(),
        'declined':  Booking.query.filter_by(booking_status='Declined').count(),
        'cancelled': Booking.query.filter_by(booking_status='Cancelled').count(),
    }

    # ── Dashboard stats ──
    total_revenue = db.session.query(
        func.coalesce(func.sum(Booking.total_price), 0)
    ).filter_by(booking_status='Accepted').scalar()

    this_month_orders = Booking.query.filter(
        extract('year',  Booking.created_at) == today.year,
        extract('month', Booking.created_at) == today.month
    ).count()

    this_month_revenue = db.session.query(
        func.coalesce(func.sum(Booking.total_price), 0)
    ).filter(
        Booking.booking_status == 'Accepted',
        extract('year',  Booking.pickup_date) == today.year,
        extract('month', Booking.pickup_date) == today.month
    ).scalar()

    # Monthly orders this year (for chart)
    monthly_data = db.session.query(
        extract('month', Booking.pickup_date).label('month'),
        func.count(Booking.booking_id).label('count')
    ).filter(
        extract('year', Booking.pickup_date) == today.year
    ).group_by('month').all()

    monthly_orders = [0] * 12
    for row in monthly_data:
        monthly_orders[int(row.month) - 1] = row.count

    # Top 5 flavors
    top_flavors = db.session.query(
        BookingSpec.flavor,
        func.count(Booking.booking_id).label('count')
    ).join(Booking, BookingSpec.booking_id == Booking.booking_id)\
     .group_by(BookingSpec.flavor)\
     .order_by(func.count(Booking.booking_id).desc())\
     .limit(5).all()
    top_flavors = [{'flavor': r.flavor, 'count': r.count} for r in top_flavors]

    perm = StaffPermission.query.filter_by(user_id=current_user.user_id).first()

    return render_template(
        'staff/bookings.html',
        bookings=all_bookings,
        users=users,
        progress_map=progress_map,
        counts=counts,
        active=status_filter,
        perm=perm,
        # dashboard stats
        total_revenue=float(total_revenue),
        this_month_orders=this_month_orders,
        this_month_revenue=float(this_month_revenue),
        monthly_orders=monthly_orders,
        top_flavors=top_flavors,
    )
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
        booking.cake_status         = cake_status
        booking.progress_updated_by = current_user.user_id
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

    category_name = request.form.get('category', '').strip()
    cat = Category.query.filter_by(name=category_name).first()
    if not cat:
        cat = Category(name=category_name)
        db.session.add(cat)
        db.session.flush()

    new_cake = Cake(
        design_name=request.form.get('design_name'),
        description=request.form.get('description'),
        category_id=cat.category_id,
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
    cake.base_price  = data.get('base_price', cake.base_price)
    cake.image_url   = data.get('image_url', cake.image_url)

    category_name = data.get('category', '').strip()
    if category_name:
        cat = Category.query.filter_by(name=category_name).first()
        if not cat:
            cat = Category(name=category_name)
            db.session.add(cat)
            db.session.flush()
        cake.category_id = cat.category_id
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
