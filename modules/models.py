from modules import db
from flask_login import UserMixin


class Category(db.Model):
    category_id = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(80), unique=True, nullable=False)


class User(db.Model, UserMixin):
    user_id       = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role          = db.Column(db.String(50), nullable=False, default='customer')
    created_at    = db.Column(db.DateTime, default=db.func.current_timestamp())

    def get_id(self):
        return str(self.user_id)


class Cake(db.Model):
    cake_id     = db.Column(db.Integer, primary_key=True)
    design_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # FK to Category instead of storing the name string directly
    category_id = db.Column(db.Integer, db.ForeignKey('category.category_id'), nullable=False)
    category    = db.relationship('Category', backref='cakes', lazy=True)

    base_price  = db.Column(db.Numeric(10, 2), nullable=False)
    image_url   = db.Column(db.Text, nullable=True)
    is_visible  = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=True)  # False = staff upload awaiting admin approval
    created_at  = db.Column(db.DateTime, default=db.func.current_timestamp())


class Booking(db.Model):
    booking_id  = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    cake_id     = db.Column(db.Integer, db.ForeignKey('cake.cake_id'), nullable=True)

    # Scheduling & payment
    pickup_date       = db.Column(db.Date,          nullable=False)
    pickup_time       = db.Column(db.String(10),     nullable=True)
    budget            = db.Column(db.Numeric(10, 2), nullable=False)
    pay_method        = db.Column(db.String(50),     nullable=False)
    total_price       = db.Column(db.Numeric(10, 2), nullable=True)
    downpayment_proof = db.Column(db.Text,           nullable=True)

    # Status
    booking_status       = db.Column(db.String(50), default='Pending')
    decline_reason       = db.Column(db.Text,        nullable=True)
    cake_status          = db.Column(db.String(50),  default='not_started')  # not_started | ongoing | completed
    progress_updated_by  = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=True)

    # Feedback (one per booking; NULL = not yet submitted)
    rating      = db.Column(db.Integer,  nullable=True)
    comment     = db.Column(db.Text,     nullable=True)
    feedback_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(),
                           onupdate=db.func.current_timestamp())

    # 1-to-1 relationship to cake spec
    spec = db.relationship('BookingSpec', backref='booking', uselist=False,
                           cascade='all, delete-orphan')


class BookingSpec(db.Model):
    """Cake customization details — split from Booking to keep that table lean."""
    spec_id    = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.booking_id'),
                           nullable=False, unique=True)

    flavor      = db.Column(db.String(100), nullable=False)
    size        = db.Column(db.String(50),  nullable=False)
    quantity    = db.Column(db.Integer,     nullable=False, default=1)
    theme       = db.Column(db.String(150), nullable=True)
    layers      = db.Column(db.String(50),  nullable=True)
    motif_color = db.Column(db.String(100), nullable=True)
    cake_message= db.Column(db.String(200), nullable=True)
    notes       = db.Column(db.Text,        nullable=True)
    phone       = db.Column(db.String(20),  nullable=True)
    social      = db.Column(db.String(100), nullable=True)


class StaffPermission(db.Model):
    permission_id      = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('user.user_id'),
                                   nullable=False, unique=True)
    can_edit_gallery   = db.Column(db.Boolean, default=False)
    can_approve_orders = db.Column(db.Boolean, default=False)
    can_update_progress= db.Column(db.Boolean, default=False)
    can_set_price      = db.Column(db.Boolean, default=False)


class CakeReaction(db.Model):
    """One like/dislike per customer per cake."""
    reaction_id = db.Column(db.Integer, primary_key=True)
    cake_id     = db.Column(db.Integer, db.ForeignKey('cake.cake_id'),  nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.user_id'),  nullable=False)
    reaction    = db.Column(db.String(10), nullable=False)  # 'like' or 'dislike'
    created_at  = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.UniqueConstraint('cake_id', 'user_id', name='uq_cake_user_reaction'),
    )
