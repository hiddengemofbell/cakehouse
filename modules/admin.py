from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from datetime import date
import calendar
import os
import json
import cloudinary
import cloudinary.uploader
from modules import db
from modules.models import User, Booking, Cake, StaffPermission, Category, CakeReaction, BookingSpec
from modules.decorators import admin_required

# Roles config file
ROLES_FILE = os.path.join(os.path.dirname(__file__), '..', 'roles_config.json')

def load_roles():
    """Load available roles from config"""
    default_roles = ['customer', 'staff', 'admin']
    if os.path.exists(ROLES_FILE):
        try:
            with open(ROLES_FILE, 'r') as f:
                data = json.load(f)
                return data.get('roles', default_roles)
        except:
            return default_roles
    return default_roles

def save_roles(roles):
    """Save roles to config"""
    with open(ROLES_FILE, 'w') as f:
        json.dump({'roles': roles}, f)

# Configure Cloudinary directly from env vars (bypasses app.config timing issues)
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

admin_bp = Blueprint('admin', __name__)

# Admin dashboard - business stats and recent orders
# Replace your existing dashboard() route in admin.py with this:

@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    from sqlalchemy import func, extract
    from datetime import datetime, date
    import calendar as cal_mod

    today = date.today()

    # ── Recent orders (last 20) ──
    recent_orders_raw = db.session.query(
        Booking.booking_id.label('id'),
        User.name,
        User.email,
        Cake.design_name.label('cake_type'),
        Booking.pickup_date.label('event_date'),
        Booking.booking_status.label('status'),
        Booking.total_price.label('total'),
        BookingSpec.flavor,
        BookingSpec.size,
        BookingSpec.theme,
        BookingSpec.layers,
        BookingSpec.motif_color,
        BookingSpec.phone,
        BookingSpec.cake_message,
        Booking.pickup_time,
        BookingSpec.notes,
        BookingSpec.quantity,
        Booking.budget,
        Booking.pay_method,
        Booking.created_at
    ).join(User, Booking.user_id == User.user_id)\
     .outerjoin(Cake, Booking.cake_id == Cake.cake_id)\
     .order_by(Booking.created_at.desc()).limit(20).all()

    recent_orders = [
        {
            'id':           o.id,
            'name':         o.name,
            'email':        o.email,
            'cake_type':    o.cake_type or 'Custom Design',
            'event_date':   o.event_date.isoformat() if o.event_date else None,
            'event_time':   o.pickup_time or '—',
            'total':        float(o.total) if o.total else 0,
            'status':       o.status.lower() if o.status else 'pending',
            'flavor':       o.flavor,
            'size':         o.size,
            'theme':        o.theme or '',
            'layers':       o.layers or '',
            'motif_color':  o.motif_color or '',
            'phone':        o.phone or '',
            'cake_message': o.cake_message or '',
            'notes':        o.notes or '',
            'quantity':     o.quantity,
            'budget':       float(o.budget) if o.budget else 0,
            'pay_method':   o.pay_method,
            'created_at':   o.created_at.isoformat() if o.created_at else None,
        }
        for o in recent_orders_raw
    ]
    # ── Summary stats ──
    total_bookings  = Booking.query.count()
    pending_count   = Booking.query.filter_by(booking_status='Pending').count()
    accepted_count  = Booking.query.filter_by(booking_status='Accepted').count()
    declined_count  = Booking.query.filter_by(booking_status='Declined').count()
    cancelled_count = Booking.query.filter_by(booking_status='Cancelled').count()

    total_revenue = db.session.query(
        func.coalesce(func.sum(Booking.total_price), 0)
    ).filter_by(booking_status='Accepted').scalar()

    # ── Monthly orders this year (for chart) ──
    monthly_data = db.session.query(
        extract('month', Booking.pickup_date).label('month'),
        func.count(Booking.booking_id).label('count')
    ).filter(
        extract('year', Booking.pickup_date) == today.year
    ).group_by('month').all()

    monthly_orders = [0] * 12
    for row in monthly_data:
        monthly_orders[int(row.month) - 1] = row.count

    # ── Monthly revenue this year (for chart) ──
    monthly_rev_data = db.session.query(
        extract('month', Booking.pickup_date).label('month'),
        func.coalesce(func.sum(Booking.total_price), 0).label('revenue')
    ).filter(
        Booking.booking_status == 'Accepted',
        extract('year', Booking.pickup_date) == today.year
    ).group_by('month').all()

    monthly_revenue = [0.0] * 12
    for row in monthly_rev_data:
        monthly_revenue[int(row.month) - 1] = float(row.revenue)

    # ── Top 5 most ordered flavors ──
    top_flavors = db.session.query(
        BookingSpec.flavor,
        func.count(Booking.booking_id).label('count')
    ).group_by(BookingSpec.flavor)\
     .order_by(func.count(Booking.booking_id).desc())\
     .limit(5).all()

    top_flavors = [{'flavor': r.flavor, 'count': r.count} for r in top_flavors]

    # ── Top 5 most ordered sizes ──
    top_sizes = db.session.query(
        BookingSpec.size,
        func.count(Booking.booking_id).label('count')
    ).group_by(BookingSpec.size)\
     .order_by(func.count(Booking.booking_id).desc())\
     .limit(5).all()

    top_sizes = [{'size': r.size, 'count': r.count} for r in top_sizes]

    # ── This month stats ──
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

    return render_template(
        'admin/dashboard.html',
        title='Admin Dashboard',
        recent_orders=recent_orders,
        total_bookings=total_bookings,
        pending_count=pending_count,
        accepted_count=accepted_count,
        declined_count=declined_count,
        cancelled_count=cancelled_count,
        total_revenue=float(total_revenue),
        monthly_orders=monthly_orders,
        monthly_revenue=monthly_revenue,
        top_flavors=top_flavors,
        top_sizes=top_sizes,
        this_month_orders=this_month_orders,
        this_month_revenue=float(this_month_revenue),
    )

# Control Panel route - Manage users and assign roles
@admin_bp.route('/admin/controlpanel')
@admin_required
def controlpanel():
    users = User.query.all()
    permissions = {}
    for sp in StaffPermission.query.all():
        permissions[sp.user_id] = sp
    roles = load_roles()
    return render_template('admin/controlpanel.html', users=users, permissions=permissions, roles=roles)

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

    category_name = request.form.get('category', '').strip()

    # Find or create the Category row, then use its ID
    cat = Category.query.filter_by(name=category_name).first()
    if not cat:
        cat = Category(name=category_name)
        db.session.add(cat)
        db.session.flush()   # get cat.category_id before commit

    new_cake = Cake(
        design_name=request.form.get('design_name'),
        description=request.form.get('description'),
        category_id=cat.category_id,
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
    CakeReaction.query.filter_by(cake_id=cake_id).delete()
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
    cake.is_visible   = 'is_visible' in request.form

    category_name = request.form.get('category', '').strip()
    if category_name:
        cat = Category.query.filter_by(name=category_name).first()
        if not cat:
            cat = Category(name=category_name)
            db.session.add(cat)
            db.session.flush()
        cake.category_id = cat.category_id

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
    CakeReaction.query.filter_by(cake_id=cake_id).delete()
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
    # Progress is now a direct column on Booking
    progress_map = {b.booking_id: b.cake_status or 'not_started' for b in all_bookings}
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
        booking.cake_status         = cake_status
        booking.progress_updated_by = current_user.user_id
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
    available_roles = load_roles()
    
    if new_role not in available_roles:
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

    # Delete all related records first to avoid foreign key violations
    CakeReaction.query.filter_by(user_id=user_id).delete()

    # Null out progress_updated_by references before deleting user
    Booking.query.filter_by(progress_updated_by=user_id).update({'progress_updated_by': None})

    # Delete bookings belonging to this user
    bookings = Booking.query.filter_by(user_id=user_id).all()
    for b in bookings:
        db.session.delete(b)

    # Delete staff permissions if exists
    StaffPermission.query.filter_by(user_id=user_id).delete()

    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User account deleted!'})

# Get all available roles
@admin_bp.route('/admin/roles')
@admin_required
def get_roles():
    roles = load_roles()
    return jsonify({'roles': roles})

# Add a new role
@admin_bp.route('/admin/roles/add', methods=['POST'])
@admin_required
def add_role():
    data = request.get_json() if request.is_json else request.form
    role_name = data.get('role_name', '').strip().lower()
    
    if not role_name or not role_name.replace('_', '').isalnum():
        return jsonify({'message': 'Invalid role name'}), 400
    
    roles = load_roles()
    if role_name in roles:
        return jsonify({'message': 'Role already exists'}), 400
    
    roles.append(role_name)
    save_roles(roles)
    flash(f'Role "{role_name}" added successfully!', 'success')
    return jsonify({'message': f'Role "{role_name}" created', 'roles': roles})

# Delete a role
@admin_bp.route('/admin/roles/<role_name>/delete', methods=['POST'])
@admin_required
def delete_role(role_name):
    # Protect default roles
    if role_name in ['customer', 'staff', 'admin']:
        return jsonify({'message': 'Cannot delete default roles'}), 400
    
    roles = load_roles()
    if role_name not in roles:
        return jsonify({'message': 'Role not found'}), 404
    
    # Check if any users have this role
    users_with_role = User.query.filter_by(role=role_name).count()
    if users_with_role > 0:
        return jsonify({'message': f'Cannot delete role: {users_with_role} user(s) have this role'}), 400
    
    roles.remove(role_name)
    save_roles(roles)
    flash(f'Role "{role_name}" deleted', 'success')
    return jsonify({'message': f'Role "{role_name}" deleted', 'roles': roles})

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