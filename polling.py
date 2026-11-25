import time
import requests

from config import config
from core.storage import boot
from routes.webhook import _handle_message, _handle_callback
from app import app as flask_app

API = f"https://api.telegram.org/bot{config['bot_token']}"

ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "chat_member"]


def delete_webhook():
    """Telegram rejects getUpdates while a webhook is registered."""
    try:
        r = requests.post(f"{API}/deleteWebhook", timeout=10)
        print(f"[poll] deleteWebhook: {r.status_code}")
    except Exception as e:
        print(f"[poll] deleteWebhook failed: {e}")


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
        print(f"[poll] getUpdates not ok: {data}")
    except Exception as e:
        print(f"[poll] getUpdates error: {e}")
    return []

def run_polling():
    boot()
    delete_webhook()
    offset = None
    print(f"[poll] polling started (pid={os.getpid()})", flush=True)
    while True:
        try:
            with flask_app.app_context():
                print(f"[poll] getUpdates offset={offset}", flush=True)
                updates = get_updates(offset)
                print(f"[poll] got {len(updates)} updates", flush=True)
                for update in updates:
                    offset = update['update_id'] + 1
                    try:
                        cb = update.get('callback_query')
                        if cb:
                            print(f"[poll] callback {cb.get('data')}", flush=True)
                            _handle_callback(cb)
                            continue
                        msg = update.get('message')
                        if msg:
                            print(f"[poll] message {msg.get('text', '')[:30]!r}", flush=True)
                            _handle_message(msg)
                    except Exception as e:
                        print(f"[poll] handler error: {e}", flush=True)
                        traceback.print_exc()
            time.sleep(0)
        except KeyboardInterrupt:
            print("[poll] stopping...", flush=True)
            break
        except Exception as e:
            print(f"[poll] loop error: {e}", flush=True)
            traceback.print_exc()
            time.sleep(1)


if __name__ == '__main__':
    run_polling()
