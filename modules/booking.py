from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from modules import db
from modules.models import Booking, BookingSpec
from modules.validators import BookingSchema, validate
import cloudinary
import cloudinary.uploader

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def place_booking():
    if request.method == 'POST':
        from datetime import datetime

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

        # ── Pickup time range check (must be 8:00 AM – 10:00 PM) ──
        if pickup_time:
            try:
                ph, pm = map(int, pickup_time.split(':'))
                total_minutes = ph * 60 + pm
                if total_minutes < 8 * 60 or total_minutes > 22 * 60:
                    field_errors['pickup_time'] = 'Pickup time must be between 8:00 AM and 10:00 PM.'
            except ValueError:
                field_errors['pickup_time'] = 'Invalid pickup time.'

        # ── Phone validation ──
        _, phone_errors = validate(BookingSchema, {'phone': phone})
        if phone_errors:
            field_errors['phone'] = phone_errors[0]

        # ── Pickup date + daily limit check ──
        pickup_date = None
        if not pickup_date_str:
            field_errors['pickup_date'] = 'Please select a pickup date.'
        else:
            try:
                pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
                existing = Booking.query.filter(
                    Booking.pickup_date == pickup_date,
                    Booking.booking_status.in_(['Pending', 'Accepted'])
                ).count()
                if existing >= 3:
                    field_errors['pickup_date'] = 'This date is fully booked. Please choose another date.'
            except ValueError:
                field_errors['pickup_date'] = 'Invalid date selected.'

        # ── Downpayment proof upload ──
        proof_file = request.files.get('downpayment_proof')
        if not proof_file or not proof_file.filename:
            field_errors['downpayment_proof'] = 'Please upload your downpayment screenshot.'

        # ── If any errors, re-render form with data intact ──
        if field_errors:
            return render_template('customer/booking_form.html',
                                   fd=fd, field_errors=field_errors)

        # Upload proof to Cloudinary
        upload_result = cloudinary.uploader.upload(
            proof_file,
            folder='lizas-cakehouse/downpayments'
        )
        proof_url = upload_result['secure_url']

        # ── All good — save booking + spec ──
        new_booking = Booking(
            user_id           = current_user.user_id,
            pickup_date       = pickup_date,
            pickup_time       = pickup_time or None,
            budget            = fd.get('budget', 0),
            pay_method        = fd.get('pay_method', 'TBD'),
            downpayment_proof = proof_url,
        )
        db.session.add(new_booking)
        db.session.flush()  # get booking_id before commit

        new_spec = BookingSpec(
            booking_id   = new_booking.booking_id,
            flavor       = fd.get('flavor', 'Custom'),
            size         = size,
            quantity     = int(fd.get('quantity', 1) or 1),
            theme        = theme or None,
            layers       = layers or None,
            motif_color  = motif or None,
            cake_message = cake_msg or None,
            notes        = extra_notes or None,
            phone        = phone or None,
            social       = social or None,
        )
        db.session.add(new_spec)
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
        s = b.spec  # BookingSpec (may be None for very old records)
        booking_data = {
            'booking_id':   b.booking_id,
            'cake_id':      b.cake_id,
            'flavor':       s.flavor       if s else None,
            'size':         s.size         if s else None,
            'theme':        s.theme        if s else None,
            'layers':       s.layers       if s else None,
            'motif_color':  s.motif_color  if s else None,
            'cake_message': s.cake_message if s else None,
            'notes':        s.notes        if s else None,
            'phone':        s.phone        if s else None,
            'quantity':     s.quantity     if s else None,
            'pickup_date':  b.pickup_date.isoformat(),
            'pickup_time':  b.pickup_time,
            'budget':       str(b.budget),
            'total_price':  str(b.total_price) if b.total_price is not None else None,
            'pay_method':   b.pay_method,
        }

        if b.booking_status == 'Accepted':
            booking_data['status'] = b.cake_status or 'not_started'
        else:
            booking_data['status'] = b.booking_status

        result.append(booking_data)

    return jsonify(result)

@bookings_bp.route('/bookings/<int:booking_id>/progress')
@login_required
def booking_progress(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return jsonify({
        'cake_status': booking.cake_status or 'not_started',
        'updated_by':  booking.progress_updated_by,
        'updated_at':  booking.updated_at.isoformat() if booking.updated_at else None
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
    from datetime import datetime
    data = request.get_json()
    rating = data.get('rating')
    comment = data.get('comment')

    if not rating or not (1 <= int(rating) <= 5):
        return jsonify({'message': 'Rating must be between 1 and 5'}), 400

    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.user_id:
        return jsonify({'message': 'Unauthorized'}), 403

    booking.rating      = int(rating)
    booking.comment     = comment
    booking.feedback_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Feedback submitted successfully'})

