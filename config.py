import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'people-dev-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///people_dev.db',
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
    }
    AUTO_CREATE_DB = os.environ.get('AUTO_CREATE_DB', 'true').lower() == 'true'
