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


def _log(msg):
    """Safe logger — works outside request context too."""
    try:
        current_app.logger.info(msg)
    except Exception:
        print(f"[broadcast] {msg}")



def _broadcast_worker(source_message_id, admin_chat_id):
    """Runs in a thread. Copies admin's message to all users."""
    _log(f"broadcast worker started: msg_id={source_message_id}, admin={admin_chat_id}")

    if not source_message_id:
        _log("ERROR: source_message_id is None — aborting")
        send_message(admin_chat_id, "❌ Broadcast failed: message_id missing.", parse_mode=None)
        return

    users = load_json('users.json')
    total = len(users)
    sent = failed = blocked = 0
    failed_ids = []
    blocked_ids = []

    _log(f"broadcasting to {total} users: {list(users.keys())}")
    send_message(admin_chat_id, f"📢 Broadcasting to {total} users...", parse_mode=None)

    for i, uid in enumerate(users.keys(), 1):
        try:
            status, desc = copy_message(uid, admin_chat_id, source_message_id)
            _log(f"[{i}/{total}] copy to {uid}: status={status} desc={(desc or '')[:100]}")
            if status == 200:
                sent += 1
            elif status == 403 or 'blocked' in (desc or '').lower() or 'not found' in (desc or '').lower():
                blocked += 1
                blocked_ids.append(uid)
            else:
                failed += 1
                failed_ids.append(f"{uid}({status})")
        except Exception as e:
            _log(f"copy exception for {uid}: {e}")
            failed += 1
            failed_ids.append(f"{uid}(exc)")
        time.sleep(0.05)

    summary = (
        f"✅ Broadcast complete\n\n"
        f"Total: {total}\n✅ Sent: {sent}\n❌ Failed: {failed}\n🚫 Blocked: {blocked}"
    )
    if failed_ids:
        summary += f"\n\n❌ Failed IDs:\n" + "\n".join(failed_ids[:10])
    if blocked_ids:
        summary += f"\n\n🚫 Blocked IDs:\n" + "\n".join(blocked_ids[:10])

    _log(summary.replace("\n", " | "))
    send_message(admin_chat_id, summary, parse_mode=None)


def broadcast_all_async(source_message_id, admin_chat_id):
    _log(f"broadcast_all_async called: msg_id={source_message_id}, admin={admin_chat_id}")
    t = threading.Thread(
        target=_broadcast_worker,
        args=(source_message_id, admin_chat_id),
        daemon=True
    )
    t.start()
    _log(f"broadcast thread started")
