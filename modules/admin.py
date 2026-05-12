from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from datetime import date
import calendar
import os
import cloudinary
import cloudinary.uploader
from modules import db
from modules.models import User, Booking, CakeProgress, Cake, Feedback, StaffPermission, Category
from modules.decorators import admin_required

# Configure Cloudinary directly from env vars (bypasses app.config timing issues)
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

admin_bp = Blueprint('admin', __name__)

# Admin dashboard - business stats and recent orders
@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    total_orders = Booking.query.count()
    revenue = db.session.query(db.func.sum(Booking.total_price)).scalar() or 0
    pending = Booking.query.filter_by(booking_status='Pending').count()
    completed = Booking.query.filter_by(booking_status='Accepted').join(CakeProgress).filter(CakeProgress.cake_status == 'completed').count()
    recent = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()

    return jsonify({
        'total_orders': total_orders,
        'revenue': str(revenue),
        'pending': pending,
        'completed': completed,
        'recent_orders': [{
            'booking_id': b.booking_id,
            'user_id': b.user_id,
            'design_notes': b.design_notes,
            'pickup_date': b.pickup_date.isoformat(),
            'booking_status': b.booking_status
        } for b in recent]
    })

# View all cake designs — approved + pending approval
@admin_bp.route('/admin/gallery')
@admin_required
def gallery():
    cakes      = Cake.query.filter_by(is_approved=True).all()
    pending    = Cake.query.filter_by(is_approved=False).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/gallery.html', cakes=cakes, pending=pending, categories=categories)

# Add new cake design (admin uploads are auto-approved)
@admin_bp.route('/admin/gallery/add', methods=['POST'])
@admin_required
def add_cake():
    image_url = None
    file = request.files.get('image')
    if file and file.filename:
        result = cloudinary.uploader.upload(file, folder='lizas-cakehouse')
        image_url = result['secure_url']

    category = request.form.get('category', '').strip()

    # Auto-save new category to the Category table if it doesn't exist yet
    if category and not Category.query.filter_by(name=category).first():
        db.session.add(Category(name=category))

    new_cake = Cake(
        design_name=request.form.get('design_name'),
        description=request.form.get('description'),
        category=category,
        base_price=request.form.get('base_price') or 0,
        image_url=image_url,
        is_approved=True
    )
    db.session.add(new_cake)
    db.session.commit()
    flash('Photo uploaded successfully!', 'success')
    return redirect(url_for('admin.gallery'))

# Approve a staff-uploaded photo
@admin_bp.route('/admin/gallery/<int:cake_id>/approve', methods=['POST'])
@admin_required
def approve_cake(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    cake.is_approved = True
    db.session.commit()
    flash(f'"{cake.design_name}" approved and is now visible in the gallery.', 'success')
    return redirect(url_for('admin.gallery'))

# Reject (delete) a staff-uploaded photo
@admin_bp.route('/admin/gallery/<int:cake_id>/reject', methods=['POST'])
@admin_required
def reject_cake(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    Booking.query.filter_by(cake_id=cake_id).update({'cake_id': None})
    db.session.delete(cake)
    db.session.commit()
    flash('Photo rejected and removed.', 'error')
    return redirect(url_for('admin.gallery'))

# Add a new category (from the Manage Categories modal)
@admin_bp.route('/admin/categories/add', methods=['POST'])
@admin_required
def add_category():
    name = request.form.get('name', '').strip()
    if name and not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name))
        db.session.commit()
        flash(f'Category "{name}" added.', 'success')
    else:
        flash('Category already exists or name is empty.', 'error')
    return redirect(url_for('admin.gallery'))

# Delete a category (admin only — does NOT delete cakes in that category)
@admin_bp.route('/admin/categories/<int:category_id>/delete', methods=['POST'])
@admin_required
def delete_category(category_id):
    cat = Category.query.get_or_404(category_id)
    db.session.delete(cat)
    db.session.commit()
    flash(f'Category "{cat.name}" deleted.', 'success')
    return redirect(url_for('admin.gallery'))

# Edit existing cake design
@admin_bp.route('/admin/gallery/<int:cake_id>/edit', methods=['POST'])
@admin_required
def edit_cake(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    cake.design_name = request.form.get('design_name', cake.design_name)
    cake.description  = request.form.get('description', cake.description)
    cake.category     = request.form.get('category', cake.category)
    cake.is_visible   = 'is_visible' in request.form

    # Only replace image if a new file was uploaded
    file = request.files.get('image')
    if file and file.filename:
        result = cloudinary.uploader.upload(file, folder='lizas-cakehouse')
        cake.image_url = result['secure_url']

    db.session.commit()
    flash('Photo updated.', 'success')
    return redirect(url_for('admin.gallery'))

# Delete cake design from gallery
@admin_bp.route('/admin/gallery/<int:cake_id>/delete', methods=['POST'])
@admin_required
def delete_cake(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    # Unlink any bookings referencing this cake before deleting
    Booking.query.filter_by(cake_id=cake_id).update({'cake_id': None})
    db.session.delete(cake)
    db.session.commit()
    flash('Photo deleted.', 'success')
    return redirect(url_for('admin.gallery'))

# Manage all bookings
@admin_bp.route('/admin/bookings')
@admin_required
def bookings():
    status_filter = request.args.get('status', 'all')
    query = Booking.query.order_by(Booking.created_at.desc())
    if status_filter != 'all':
        query = query.filter_by(booking_status=status_filter.capitalize())
    all_bookings = query.all()
    users = {u.user_id: u for u in User.query.all()}
    # Latest progress per booking
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
    return render_template('admin/bookings.html',
                           bookings=all_bookings, users=users,
                           progress_map=progress_map,
                           counts=counts, active=status_filter)

# Accept a booking (price required)
@admin_bp.route('/admin/bookings/<int:booking_id>/accept', methods=['POST'])
@admin_required
def accept_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    price = request.form.get('total_price', '').strip()
    if not price:
        flash('Please set a price before accepting.', 'error')
        return redirect(url_for('admin.bookings', status=request.args.get('status', 'all')))
    booking.booking_status = 'Accepted'
    booking.total_price = float(price)
    db.session.commit()
    flash('Booking accepted and price set.', 'success')
    return redirect(url_for('admin.bookings', status=request.args.get('status', 'all')))

# Decline a booking (reason required)
@admin_bp.route('/admin/bookings/<int:booking_id>/decline', methods=['POST'])
@admin_required
def decline_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    reason = request.form.get('decline_reason', '').strip()
    if not reason:
        flash('Please provide a reason for declining.', 'error')
        return redirect(url_for('admin.bookings', status=request.args.get('status', 'all')))
    booking.booking_status = 'Declined'
    booking.decline_reason = reason
    db.session.commit()
    flash('Booking declined.', 'error')
    return redirect(url_for('admin.bookings', status=request.args.get('status', 'all')))

# Set total price
@admin_bp.route('/admin/bookings/<int:booking_id>/set_price', methods=['POST'])
@admin_required
def set_price(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    price = request.form.get('total_price', '').strip()
    if price:
        booking.total_price = float(price)
        db.session.commit()
        flash('Price updated.', 'success')
    return redirect(url_for('admin.bookings', status='accepted'))

# Update cake progress
@admin_bp.route('/admin/bookings/<int:booking_id>/progress', methods=['POST'])
@admin_required
def update_progress(booking_id):
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
    return redirect(url_for('admin.bookings', status='accepted'))


# View all users
@admin_bp.route('/admin/users')
@admin_required
def manage_users():
    users = User.query.all()
    return jsonify([{
        'user_id': u.user_id,
        'name': u.name,
        'email': u.email,
        'role': u.role
    } for u in users])

# Change user role
@admin_bp.route('/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() if request.is_json else request.form
    new_role = data.get('role')
    if new_role not in ['customer', 'staff', 'admin']:
        return jsonify({'message': 'Invalid role'}), 400

    old_role = user.role
    user.role = new_role
    db.session.commit()

    # Auto-create permissions record when promoting to staff
    if new_role == 'staff' and old_role != 'staff':
        existing_perm = StaffPermission.query.filter_by(user_id=user_id).first()
        if not existing_perm:
            perm = StaffPermission(user_id=user_id)
            db.session.add(perm)
            db.session.commit()

    # Remove permissions record when demoting from staff
    if old_role == 'staff' and new_role != 'staff':
        perm = StaffPermission.query.filter_by(user_id=user_id).first()
        if perm:
            db.session.delete(perm)
            db.session.commit()

    return jsonify({'message': f'User role updated to {new_role}'})

# Delete user account
@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # Delete staff permissions if exists
    perm = StaffPermission.query.filter_by(user_id=user_id).first()
    if perm:
        db.session.delete(perm)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User account deleted!'})

# View staff permissions
@admin_bp.route('/admin/users/<int:user_id>/permissions')
@admin_required
def view_permissions(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != 'staff':
        return jsonify({'message': 'User is not a staff member'}), 400

    perm = StaffPermission.query.filter_by(user_id=user_id).first()
    if not perm:
        return jsonify({'message': 'No permissions record found'}), 404

    return jsonify({
        'user_id': user.user_id,
        'name': user.name,
        'can_edit_gallery': perm.can_edit_gallery,
        'can_approve_orders': perm.can_approve_orders,
        'can_update_progress': perm.can_update_progress,
        'can_set_price': perm.can_set_price
    })

# Toggle a specific staff permission
@admin_bp.route('/admin/users/<int:user_id>/permissions', methods=['POST'])
@admin_required
def update_permissions(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != 'staff':
        return jsonify({'message': 'User is not a staff member'}), 400

    perm = StaffPermission.query.filter_by(user_id=user_id).first()
    if not perm:
        perm = StaffPermission(user_id=user_id)
        db.session.add(perm)

    data = request.get_json() if request.is_json else request.form

    if 'can_edit_gallery' in data:
        perm.can_edit_gallery = data.get('can_edit_gallery') in [True, 'true', '1', 'on']
    if 'can_approve_orders' in data:
        perm.can_approve_orders = data.get('can_approve_orders') in [True, 'true', '1', 'on']
    if 'can_update_progress' in data:
        perm.can_update_progress = data.get('can_update_progress') in [True, 'true', '1', 'on']
    if 'can_set_price' in data:
        perm.can_set_price = data.get('can_set_price') in [True, 'true', '1', 'on']

    db.session.commit()
    return jsonify({
        'message': 'Permissions updated!',
        'can_edit_gallery': perm.can_edit_gallery,
        'can_approve_orders': perm.can_approve_orders,
        'can_update_progress': perm.can_update_progress,
        'can_set_price': perm.can_set_price
    })

# Calendar view
@admin_bp.route('/admin/calendar')
@admin_required
def calendar():
    from datetime import datetime as dt
    import calendar as cal_mod
    year  = int(request.args.get('year',  dt.today().year))
    month = int(request.args.get('month', dt.today().month))

    bookings = Booking.query.filter(
        Booking.booking_status == 'Accepted',
        db.extract('year',  Booking.pickup_date) == year,
        db.extract('month', Booking.pickup_date) == month
    ).all()

    users = {u.user_id: u for u in User.query.all()}

    by_day = {}
    for b in bookings:
        day = b.pickup_date.day
        by_day.setdefault(day, []).append(b)

    cal = cal_mod.monthcalendar(year, month)
    month_name = dt(year, month, 1).strftime('%B %Y')

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
        max_per_day=3, role='admin'
    )


# Reports - sales data with monthly/yearly/custom view
@admin_bp.route('/admin/reports')
@admin_required
def reports():
    view = request.args.get('view', 'month')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    today = date.today()

    if start_date_str and end_date_str:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    elif view == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:
        start_date = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day)

    bookings = Booking.query.filter_by(booking_status='Accepted').filter(
        Booking.pickup_date.between(start_date, end_date)
    ).all()

    total_sales = sum(float(b.total_price or 0) for b in bookings)
    total_orders = len(bookings)

    # Group sales by date for line graph
    daily_sales = {}
    for b in bookings:
        date_str = b.pickup_date.isoformat()
        if date_str not in daily_sales:
            daily_sales[date_str] = 0
        daily_sales[date_str] += float(b.total_price or 0)

    return jsonify({
        'total_sales': str(total_sales),
        'total_orders': total_orders,
        'daily_sales': daily_sales,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    })