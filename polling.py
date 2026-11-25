import time
import requests

from config import config
from core.storage import boot
from routes.webhook import _handle_message, _handle_callback  # reuse existing handlers
from flask import Flask

# _handle_message / _handle_callback use current_app.logger — give them an app context
from app import app

API = f"https://api.telegram.org/bot{config['bot_token']}"

ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "chat_member"]


def get_updates(offset=None, timeout=20):
    params = {
        'timeout': timeout,
        'allowed_updates': ALLOWED_UPDATES,
    }
    if offset is not None:
        params['offset'] = offset
    try:
        r = requests.get(f"{API}/getUpdates", params=params, timeout=timeout + 10)
        data = r.json()
        if data.get('ok'):
            return data['result']
    except Exception as e:
        print(f"[poll] getUpdates error: {e}")
    return []


def run_polling():
    boot()  # ensure dirs/JSON exist
    offset = None
    print("🤖 Polling started...")
    while True:
        try:
            with app.app_context():          # so current_app.logger works
                updates = get_updates(offset)
                for update in updates:
                    offset = update['update_id'] + 1
                    try:
                        cb = update.get('callback_query')
                        if cb:
                            _handle_callback(cb)
                            continue
                        msg = update.get('message')
                        if msg:
                            _handle_message(msg)
                    except Exception as e:
                        print(f"[poll] handler error: {e}")
            time.sleep(0)  # interval=0
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[poll] loop error: {e}")
            time.sleep(1)   # avoid tight spin on fatal errors


if __name__ == '__main__':
    run_polling()