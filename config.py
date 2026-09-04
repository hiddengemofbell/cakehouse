import os
from dotenv import load_dotenv
load_dotenv()

def _fix_db_url(url):
    if not url:
        return url
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql://') and '+psycopg2' not in url:
        url = url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    return url

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'lizas-cakehouse-dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = _fix_db_url(os.getenv('DATABASE_URL', ''))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')