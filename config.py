import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_here')
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/kims_ordering_system'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
