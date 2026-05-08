from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static') 
    #../templates points it to the correct templates folder. same applies to static


    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    from modules.main import main_bp
    from modules.auth import auth
    from modules.admin import admin_bp
    from modules.booking import bookings_bp
    from modules.gallery import gallery_bp
    from modules.staff import staff_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth)
    app.register_blueprint(admin_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(staff_bp)

    return app