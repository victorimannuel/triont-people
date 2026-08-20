from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
try:
    from flask_migrate import Migrate
except ImportError:
    Migrate = None

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate() if Migrate else None
