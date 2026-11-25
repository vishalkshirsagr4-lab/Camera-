import time
import datetime
import threading

from flask import current_app

from config import config
from core.storage import load_json, save_json
from core.telegram import send_message, copy_message


def save_user(user):
    """Called on every Telegram update. Adds/updates user record."""
    if not user or not user.get('id'):
        return
    users = load_json('users.json')
    uid = str(user['id'])
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if uid not in users:
        users[uid] = {
            'id': user['id'],
            'first_name': user.get('first_name', ''),
            'last_name': user.get('last_name', ''),
            'username': user.get('username', ''),
            'language': user.get('language_code', ''),
            'first_seen': now,
            'last_seen': now,
            'is_bot': user.get('is_bot', False),
            'messages': 0,
            'links_created': 0,
        }
    users[uid]['last_seen'] = now
    users[uid]['messages'] = users[uid].get('messages', 0) + 1
    save_json('users.json', users)


def bump_links_count(uid):
    users = load_json('users.json')
    uid = str(uid)
    if uid in users:
        users[uid]['links_created'] = users[uid].get('links_created', 0) + 1
        save_json('users.json', users)


def _broadcast_worker(source_message_id, admin_chat_id):
    """Runs in a thread. Copies admin's message to all users."""
    users = load_json('users.json')
    total = len(users)
    sent = failed = blocked = 0

    send_message(admin_chat_id, f"📢 Broadcasting to {total} users...", parse_mode=None)

    for uid in users.keys():
        status = copy_message(uid, admin_chat_id, source_message_id)
        if status == 200:
            sent += 1
        elif status == 0:
            failed += 1
        else:
            # Can't easily check body here; treat 4xx as blocked
            blocked += 1
        time.sleep(0.05)  # rate limit safety

    send_message(
        admin_chat_id,
        f"✅ Broadcast complete\n\nTotal: {total}\n✅ Sent: {sent}\n❌ Failed: {failed}\n🚫 Blocked: {blocked}",
        parse_mode=None
    )


def broadcast_all_async(source_message_id, admin_chat_id):
    t = threading.Thread(
        target=_broadcast_worker,
        args=(source_message_id, admin_chat_id),
        daemon=True
    )
    t.start()