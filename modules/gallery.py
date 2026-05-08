from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from modules import db
from modules.models import Cake

gallery_bp = Blueprint('gallery', __name__)

@gallery_bp.route('/gallery')
def gallery():
    category = request.args.get('category')  # e.g. /gallery?category=Birthday
    
    if category:
        cakes = Cake.query.filter_by(is_visible=True, category=category).all()
    else:
        cakes = Cake.query.filter_by(is_visible=True).all()
    
    return render_template('customer/gallery.html', cakes=cakes)

@gallery_bp.route('/gallery/<int:cake_id>')
def cake_detail(cake_id):
    cake = Cake.query.get_or_404(cake_id)
    return jsonify({'cake_id': cake.cake_id, 'design_name': cake.design_name, 'description': cake.description, 'category': cake.category, 'base_price': str(cake.base_price), 'image_url': cake.image_url})