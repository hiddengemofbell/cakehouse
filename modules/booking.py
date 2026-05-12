from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from modules import db
from modules.models import Booking, CakeProgress, Feedback

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def place_booking():
    if request.method == 'POST':
        # Build design_notes from order detail fields
        theme   = request.form.get('theme', '').strip()
        size    = request.form.get('size', '').strip()
        layers  = request.form.get('layers', '').strip()
        motif   = request.form.get('motif', '').strip()
        design_notes = f"Theme: {theme} | Size: {size} | Layers: {layers} | Motif/Color: {motif}"

        # Build special_notes from contact extras + cake message + notes
        phone       = request.form.get('phone', '').strip()
        social      = request.form.get('social', '').strip()
        cake_msg    = request.form.get('cake_message', '').strip()
        extra_notes = request.form.get('notes', '').strip()
        pickup_time = request.form.get('pickup_time', '').strip()
        special_notes_parts = []
        if phone:        special_notes_parts.append(f"Phone: {phone}")
        if social:       special_notes_parts.append(f"Social: {social}")
        if cake_msg:     special_notes_parts.append(f"Cake message: {cake_msg}")
        if pickup_time:  special_notes_parts.append(f"Pickup time: {pickup_time}")
        if extra_notes:  special_notes_parts.append(f"Notes: {extra_notes}")
        special_notes = " | ".join(special_notes_parts)

        # Check 3 orders per day limit
        from datetime import date as date_type, datetime
        pickup_date_str = request.form.get('pickup_date')
        pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
        existing_bookings = Booking.query.filter_by(
            pickup_date=pickup_date,
            booking_status='Pending'
        ).count()

        if existing_bookings >= 3:
            flash('Sorry! This date is fully booked. Please choose another date.', 'error')
            return redirect(url_for('bookings.place_booking'))

        new_booking = Booking(
            user_id=current_user.user_id,
            flavor=request.form.get('flavor', 'Custom'),
            size=size,
            design_notes=design_notes,
            special_notes=special_notes or None,
            quantity=int(request.form.get('quantity', 1)),
            pickup_date=pickup_date,
            budget=request.form.get('budget', 0),
            pay_method=request.form.get('pay_method', 'TBD')
        )
        db.session.add(new_booking)
        db.session.commit()
        flash('Your booking has been submitted! We\'ll get back to you soon.', 'success')
        return redirect(url_for('bookings.place_booking'))

    return render_template('customer/booking_form.html')

@bookings_bp.route('/bookings')
@login_required
def bookings():
    user_bookings = Booking.query.filter_by(user_id=current_user.user_id).all()
    result = []
    for b in user_bookings:
        booking_data = {
            'booking_id': b.booking_id,
            'cake_id': b.cake_id,
            'design_notes': b.design_notes,
            'quantity': b.quantity,
            'size': b.size,
            'flavor': b.flavor,
            'special_notes': b.special_notes,
            'pickup_date': b.pickup_date.isoformat(),
            'budget': str(b.budget),
            'total_price': str(b.total_price) if b.total_price is not None else None,
            'pay_method': b.pay_method
        }

        if b.booking_status == 'Accepted':
            # Show cake status instead of booking status
            progress = CakeProgress.query.filter_by(booking_id=b.booking_id).order_by(CakeProgress.updated_at.desc()).first()
            booking_data['status'] = progress.cake_status if progress else 'not_started'
        else:
            booking_data['status'] = b.booking_status

        result.append(booking_data)

    return jsonify(result)

@bookings_bp.route('/bookings/<int:booking_id>/progress')
@login_required
def booking_progress(booking_id):
    progress = CakeProgress.query.filter_by(booking_id=booking_id).order_by(CakeProgress.updated_at.desc()).first()
    if not progress:
        return jsonify({'message': 'No progress found for this booking'}), 404
    return jsonify({
        'cake_status': progress.cake_status,
        'updated_by': progress.updated_by,
        'updated_at': progress.updated_at.isoformat()
    })

@bookings_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.user_id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('main.booking_page'))
    if booking.booking_status != 'Pending':
        flash('Only pending bookings can be cancelled.', 'error')
        return redirect(url_for('main.booking_page'))
    booking.booking_status = 'Cancelled'
    db.session.commit()
    flash('Your order has been cancelled.', 'success')
    return redirect(url_for('main.booking_page'))

@bookings_bp.route('/bookings/<int:booking_id>/feedback', methods=['POST'])
@login_required
def submit_feedback(booking_id):
    data = request.get_json()
    rating = data.get('rating')
    comment = data.get('comment')

    if not rating or not (1 <= rating <= 5):
        return jsonify({'message': 'Rating must be between 1 and 5'}), 400

    feedback = Feedback(booking_id=booking_id, user_id=current_user.user_id, rating=rating, comment=comment)
    db.session.add(feedback)
    db.session.commit()

    return jsonify({'message': 'Feedback submitted successfully'})

