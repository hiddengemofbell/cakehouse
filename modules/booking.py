from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from modules import db
from modules.models import Booking, CakeProgress, Feedback
from modules.validators import BookingSchema, validate

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def place_booking():
    if request.method == 'POST':
        from datetime import datetime, timezone, timedelta

        # Collect all form values so we can send them back if there's an error
        fd = {k: request.form.get(k, '') for k in request.form}
        field_errors = {}   # { field_name: error message }

        theme   = fd.get('theme', '').strip()
        size    = fd.get('size', '').strip()
        layers  = fd.get('layers', '').strip()
        motif   = fd.get('motif', '').strip()
        phone       = fd.get('phone', '').strip()
        social      = fd.get('social', '').strip()
        cake_msg    = fd.get('cake_message', '').strip()
        extra_notes = fd.get('notes', '').strip()
        pickup_time = fd.get('pickup_time', '').strip()
        pickup_date_str = fd.get('pickup_date', '').strip()

        # ── Phone validation ──
        _, phone_errors = validate(BookingSchema, {'phone': phone})
        if phone_errors:
            field_errors['phone'] = phone_errors[0]

        # ── Business hours check (8 AM – 10 PM Philippine Time) ──
        PH_TZ = timezone(timedelta(hours=8))
        now_ph = datetime.now(PH_TZ)
        if now_ph.hour < 8 or now_ph.hour >= 22:
            field_errors['pickup_date'] = 'We only accept bookings from 8:00 AM – 10:00 PM (PH Time).'

        # ── Pickup date + daily limit check ──
        pickup_date = None
        if not pickup_date_str:
            field_errors['pickup_date'] = 'Please select a pickup date.'
        else:
            try:
                pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
                existing = Booking.query.filter_by(
                    pickup_date=pickup_date,
                    booking_status='Pending'
                ).count()
                if existing >= 3:
                    field_errors['pickup_date'] = 'This date is fully booked. Please choose another date.'
            except ValueError:
                field_errors['pickup_date'] = 'Invalid date selected.'

        # ── If any errors, re-render form with data intact ──
        if field_errors:
            return render_template('customer/booking_form.html',
                                   fd=fd, field_errors=field_errors)

        # ── All good — save booking ──
        design_notes = f"Theme: {theme} | Size: {size} | Layers: {layers} | Motif/Color: {motif}"
        special_notes_parts = []
        if phone:        special_notes_parts.append(f"Phone: {phone}")
        if social:       special_notes_parts.append(f"Social: {social}")
        if cake_msg:     special_notes_parts.append(f"Cake message: {cake_msg}")
        if pickup_time:  special_notes_parts.append(f"Pickup time: {pickup_time}")
        if extra_notes:  special_notes_parts.append(f"Notes: {extra_notes}")
        special_notes = " | ".join(special_notes_parts)

        new_booking = Booking(
            user_id=current_user.user_id,
            flavor=fd.get('flavor', 'Custom'),
            size=size,
            design_notes=design_notes,
            special_notes=special_notes or None,
            quantity=int(fd.get('quantity', 1) or 1),
            pickup_date=pickup_date,
            budget=fd.get('budget', 0),
            pay_method=fd.get('pay_method', 'TBD')
        )
        db.session.add(new_booking)
        db.session.commit()
        flash('Your booking has been submitted! We\'ll get back to you soon.', 'success')
        return redirect(url_for('bookings.place_booking'))

    return render_template('customer/booking_form.html', fd={}, field_errors={})

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

@bookings_bp.route('/bookings/<int:booking_id>')
@login_required
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.user_id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('main.booking_page'))
    return render_template('customer/booking_detail.html', b=booking)

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

