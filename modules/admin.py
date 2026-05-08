from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date
import calendar
from modules import db
from modules.models import User, Booking, CakeProgress, Cake, Feedback, StaffPermission

admin_bp = Blueprint('admin', __name__)

# Admin dashboard - business stats and recent orders
@admin_bp.route('/admin/dashboard')
@login_required
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

# View all cake designs (admin sees hidden ones too)
@admin_bp.route('/admin/gallery')
@login_required
def gallery():
    cakes = Cake.query.all()
    return render_template('admin/gallery.html', cakes=cakes)

# Add new cake design to gallery
@admin_bp.route('/admin/gallery/add', methods=['GET', 'POST'])
@login_required
def add_cake():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        new_cake = Cake(
            design_name=data.get('design_name'),
            description=data.get('description'),
            category=data.get('category'),
            base_price=data.get('base_price'),
            image_url=data.get('image_url')
        )
        db.session.add(new_cake)
        db.session.commit()
        return jsonify({'message': 'Cake design added!', 'cake_id': new_cake.cake_id})

    return render_template('admin/gallery.html')

# Edit existing cake design
@admin_bp.route('/admin/gallery/<int:cake_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cake(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        cake.design_name = data.get('design_name', cake.design_name)
        cake.description = data.get('description', cake.description)
        cake.category = data.get('category', cake.category)
        cake.base_price = data.get('base_price', cake.base_price)
        cake.image_url = data.get('image_url', cake.image_url)
        cake.is_visible = data.get('is_visible', cake.is_visible)
        db.session.commit()
        return jsonify({'message': 'Cake design updated!'})

    return jsonify({
        'cake_id': cake.cake_id,
        'design_name': cake.design_name,
        'description': cake.description,
        'category': cake.category,
        'base_price': str(cake.base_price),
        'image_url': cake.image_url,
        'is_visible': cake.is_visible
    })

# Delete cake design from gallery
@admin_bp.route('/admin/gallery/<int:cake_id>/delete', methods=['POST'])
@login_required
def delete_cake(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    db.session.delete(cake)
    db.session.commit()
    return jsonify({'message': 'Cake design deleted!'})

# View all users
@admin_bp.route('/admin/users')
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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

# Reports - sales data with monthly/yearly/custom view
@admin_bp.route('/admin/reports')
@login_required
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