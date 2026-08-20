from routes.auth import auth_bp
from routes.common import main_bp

# Import sub-route modules to bind decorators to main_bp
import routes.dashboard
import routes.leaves
import routes.calendar
import routes.approvals
import routes.admin

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
