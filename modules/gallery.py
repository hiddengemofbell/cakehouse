from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from modules import db
from modules.models import Cake, CakeReaction, Category

gallery_bp = Blueprint('gallery', __name__)


def get_likes(cakes):
    """Return (likes_dict, user_likes_set) for a list of cakes."""
    if not cakes:
        return {}, set()

    like_rows = db.session.query(
        CakeReaction.cake_id,
        func.count(CakeReaction.reaction_id)
    ).filter_by(reaction='like').group_by(CakeReaction.cake_id).all()
    likes = {cake_id: count for cake_id, count in like_rows}

    user_likes = set()
    if current_user.is_authenticated:
        user_likes = {
            r.cake_id for r in CakeReaction.query.filter_by(
                user_id=current_user.user_id, reaction='like'
            ).all()
        }

    return likes, user_likes


# Public gallery — approved + visible cakes only
# Logged-in customers get the customer template (with like + lightbox)
# Everyone else (public) gets the plain gallery template
@gallery_bp.route('/gallery')
def gallery():
    cakes = Cake.query.filter_by(is_visible=True, is_approved=True).all()
    likes, user_likes = get_likes(cakes)

    categories = Category.query.order_by(Category.name).all()

    if current_user.is_authenticated and current_user.role == 'customer':
        return render_template('customer/gallery.html',
                               cakes=cakes, likes=likes,
                               user_likes=user_likes, categories=categories)

    return render_template('gallery.html', cakes=cakes, categories=categories)


# Like toggle — customers only
# POST /gallery/<cake_id>/like  →  { liked: bool, total: int }
@gallery_bp.route('/gallery/<int:cake_id>/like', methods=['POST'])
@login_required
def toggle_like(cake_id):
    existing = CakeReaction.query.filter_by(
        cake_id=cake_id, user_id=current_user.user_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        liked = False
    else:
        r = CakeReaction(cake_id=cake_id, user_id=current_user.user_id, reaction='like')
        db.session.add(r)
        db.session.commit()
        liked = True

    total = CakeReaction.query.filter_by(cake_id=cake_id, reaction='like').count()
    return jsonify({'liked': liked, 'total': total})
