import os
import json
import requests
from flask import current_app

from config import config


def _api(method):
    return f"https://api.telegram.org/bot{config['bot_token']}/{method}"


def send_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    payload = {'chat_id': chat_id, 'text': text}
    if parse_mode:
        payload['parse_mode'] = parse_mode
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(_api('sendMessage'), data=payload, timeout=10)
        if r.status_code == 200:
            return True
        # Retry once without parse_mode (handles Markdown entity errors)
        if parse_mode:
            current_app.logger.warning(f"sendMessage failed: {r.status_code} {r.text[:200]}")
            payload.pop('parse_mode', None)
            r2 = requests.post(_api('sendMessage'), data=payload, timeout=10)
            return r2.status_code == 200
        return False
    except Exception as e:
        current_app.logger.warning(f"sendMessage exception: {e}")
        return False


def send_photo(chat_id, photo_path, caption):
    try:
        size = os.path.getsize(photo_path)
        if size < 100:
            current_app.logger.warning(f"sendPhoto skipped: too small ({size}b)")
            return False
        with open(photo_path, 'rb') as fh:
            r = requests.post(
                _api('sendPhoto'),
                files={'photo': fh},
                data={'chat_id': chat_id, 'caption': caption},
                timeout=20
            )
        return r.status_code == 200
    except Exception as e:
        current_app.logger.warning(f"sendPhoto exception: {e}")
        return False

# core/telegram.py me add karo
def send_chat_action(chat_id, action='typing'):
    import requests
    try:
        requests.post(
            f"{API_URL}/sendChatAction",
            json={'chat_id': chat_id, 'action': action},
            timeout=5
        )
    except Exception:
        pass


def send_location(chat_id, lat, lng):
    try:
        r = requests.post(
            _api('sendLocation'),
            data={'chat_id': chat_id, 'latitude': lat, 'longitude': lng},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        current_app.logger.warning(f"sendLocation exception: {e}")
        return False


def answer_callback(callback_id, text=None):
    data = {'callback_query_id': callback_id}
    if text:
        data['text'] = text
    try:
        requests.post(_api('answerCallbackQuery'), data=data, timeout=10)
    except Exception:
        pass


def copy_message(chat_id, from_chat_id, message_id):
    """Copy a message (no 'forwarded from' tag). Returns (status_code, description)."""
    try:
        r = requests.post(
            _api('copyMessage'),
            data={'chat_id': chat_id, 'from_chat_id': from_chat_id, 'message_id': message_id},
            timeout=10
        )
        desc = ''
        try:
            desc = r.json().get('description', '')
        except Exception:
            pass
        return r.status_code, desc
    except Exception:
        return 0, 'exception'


def get_chat_member(chat_id, user_id):
    try:
        r = requests.get(_api('getChatMember'),
                         params={'chat_id': chat_id, 'user_id': user_id},
                         timeout=10)
        if r.status_code != 200:
            return None
        return r.json().get('result', {}).get('status', '')
    except Exception:
        return None


def set_webhook(url):
    r = requests.post(_api('setWebhook'), data={'url': url}, timeout=10)
    return r.json()


def get_webhook_info():
    r = requests.get(_api('getWebhookInfo'), timeout=10)
    return r.json()
