from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from modules import db
from modules.models import Booking, CakeProgress, Feedback

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def place_booking():
    if request.method == 'POST':
        new_booking = Booking(
            user_id=current_user.user_id,
            cake_id=request.form.get('cake_id') or None,
            design_notes=request.form['design_notes'],
            quantity=int(request.form['quantity']),
            size=request.form['size'],
            flavor=request.form['flavor'],
            special_notes=request.form.get('special_notes'),
            pickup_date=request.form['pickup_date'],
            budget=request.form['budget'],
            pay_method=request.form['pay_method']
        )
        db.session.add(new_booking)
        db.session.commit()
        return jsonify({'message': 'Booking placed!', 'booking_id': new_booking.booking_id})

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
        return jsonify({'message': 'Unauthorized'}), 403
    if booking.booking_status != 'Pending':
        return jsonify({'message': 'Only pending bookings can be cancelled'}), 400
    booking.booking_status = 'Cancelled'
    db.session.commit()
    return jsonify({'message': 'Booking cancelled'})

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

