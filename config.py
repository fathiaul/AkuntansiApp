# config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'your-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'pos.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
# untuk menyimpan database atau basis data