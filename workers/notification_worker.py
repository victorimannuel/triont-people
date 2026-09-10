import time

from app import create_app
from extensions import db
from services.notification_outbox_service import process_next_notification


def run():
    app = create_app()
    with app.app_context():
        while True:
            try:
                processed = process_next_notification()
            except Exception as exc:
                db.session.rollback()
                print(f'Notification worker error: {exc}', flush=True)
                processed = False
            time.sleep(0.2 if processed else 1)


if __name__ == '__main__':
    run()
