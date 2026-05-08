from modules import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(50), nullable=False, default='customer')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def get_id(self):
        return str(self.user_id)


class Cake(db.Model):
    cake_id = db.Column(db.Integer, primary_key=True)
    design_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=False)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.Text, nullable=True)
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Booking(db.Model):
    booking_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    cake_id = db.Column(db.Integer, db.ForeignKey('cake.cake_id'), nullable=True)
    design_notes = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    size = db.Column(db.String(50), nullable=False)
    flavor = db.Column(db.String(100), nullable=False)
    special_notes = db.Column(db.Text, nullable=True)
    pickup_date = db.Column(db.Date, nullable=False)
    booking_status = db.Column(db.String(50), default='Pending')
    budget = db.Column(db.Numeric(10, 2), nullable=False)
    pay_method = db.Column(db.String(50), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())


class CakeProgress(db.Model):
    progress_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.booking_id'), nullable=False)
    cake_status = db.Column(db.String(50), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Feedback(db.Model):
    feedback_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.booking_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


# Staff permissions - admin toggles what each staff can do
class StaffPermission(db.Model):
    permission_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False, unique=True)
    can_edit_gallery = db.Column(db.Boolean, default=False)
    can_approve_orders = db.Column(db.Boolean, default=False)
    can_update_progress = db.Column(db.Boolean, default=False)
    can_set_price = db.Column(db.Boolean, default=False)


# Customer like/dislike reactions on cake designs
class CakeReaction(db.Model):
    reaction_id = db.Column(db.Integer, primary_key=True)
    cake_id = db.Column(db.Integer, db.ForeignKey('cake.cake_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    reaction = db.Column(db.String(10), nullable=False)  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # One reaction per customer per cake
    __table_args__ = (db.UniqueConstraint('cake_id', 'user_id', name='unique_cake_user_reaction'),)