import os
import threading
from flask import Flask

from config import config
from core.storage import boot
from routes import register_blueprints


def create_app():
    app = Flask(__name__)
    app.secret_key = config['secret_key']
    app.logger.setLevel('INFO')

    boot()
    register_blueprints(app)
    return app


app = create_app()


def _start_poller():
    """Runs the Telegram long-polling loop in a background thread."""
    from polling import run_polling
    import time
    time.sleep(2)          # let Flask bind its port first
    try:
        run_polling()
    except Exception as e:
        app.logger.exception(f"Poller crashed: {e}")


# Start poller ONCE at import time (works under python app.py AND gunicorn -w 1)
if os.environ.get('DISABLE_POLLER') != '1':
    threading.Thread(target=_start_poller, daemon=True).start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
