import os
import sys
import time
import threading
import traceback
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

_poller_started = False


def _start_poller():
    global _poller_started
    if _poller_started:
        return
    _poller_started = True
    time.sleep(2)
    print(f"[poller] thread alive, pid={os.getpid()}", flush=True)
    try:
        from polling import run_polling
        run_polling()
    except Exception:
        print("[poller] CRASHED:", flush=True)
        traceback.print_exc()
        sys.stderr.flush()


if os.environ.get('DISABLE_POLLER') != '1':
    print(f"[app] spawning poller thread (pid={os.getpid()})", flush=True)
    threading.Thread(target=_start_poller, daemon=True, name="tg-poller").start()

# in app.py — add at the bottom, before app.run()


def _poller_watchdog():
    """Restart the poller thread if it dies."""
    global _poller_started
    while True:
        time.sleep(60)
        # If the poller thread is gone but we expect it to be running
        if os.environ.get('DISABLE_POLLER') != '1':
            alive = any(t.name == "tg-poller" and t.is_alive()
                        for t in threading.enumerate())
            if not alive:
                print("[watchdog] poller dead, restarting...", flush=True)
                _poller_started = False
                threading.Thread(target=_start_poller, daemon=True, name="tg-poller").start()

threading.Thread(target=_poller_watchdog, daemon=True, name="watchdog").start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"[app] starting Flask on port {port}", flush=True)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
