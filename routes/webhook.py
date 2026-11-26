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
        cb = update.get('callback_query')
        if cb:
            return _handle_callback(cb)

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
        if is_admin(from_id):
            send_message(from_id, "✅ Admin verified! Welcome to the bot.", parse_mode=None)
            return 'OK', 200
        ok, missing = check_force_join(from_id)
        if ok:
            send_message(from_id, "✅ Verification complete. Welcome!", parse_mode=None)
        else:
            send_force_join_prompt(from_id, missing)
        return 'OK', 200

    # Gate everything else
    ok, missing = check_force_join(from_id)
    if not ok and not is_admin(from_id):
        send_force_join_prompt(from_id, missing)
        return 'OK', 200

    if data == 'help':
        send_message(
            from_id,
            "✨ *HELP & GUIDE*\n\n"
            "Welcome! This bot menu provides information and account support.\n\n"
            "🔹 Use /start to reopen the main menu.\n"
            "🔹 Only interact with links and pages when you understand what they do.\n"
            "🔹 Never share private photos, passwords, OTPs or sensitive information.\n\n"
            "Need assistance? Contact the bot administrator.",
            parse_mode='Markdown'
        )

    elif data == 'privacy':
        send_message(
            from_id,
            "🛡️ *PRIVACY & CONSENT*\n\n"
            "Only use camera, location or device features when the person using the device has clearly understood the request and actively agreed.\n\n"
            "Do not use this bot to secretly monitor, identify or collect another person's information.\n"
            "You can decline permission at any time.",
            parse_mode='Markdown'
        )

    elif data == 'broadcast':
        if not is_admin(from_id):
            send_message(from_id, "❌ Admin only.", parse_mode=None)
            return 'OK', 200
        _pending[from_id] = 'broadcast'
        send_message(from_id, "📢 Send the announcement to broadcast. /cancel to abort.", parse_mode=None)

    elif data == 'users':
        if not is_admin(from_id):
            send_message(from_id, "❌ Admin only.", parse_mode=None)
            return 'OK', 200
        users = load_json('users.json')
        lines = [f"👥 *Total Users:* {len(users)}\\n"]
        for i, (uid, u) in enumerate(list(users.items())[:30], 1):
            name = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or "No name"
            uname = f"@{u['username']}" if u.get('username') else "—"
            lines.append(f"{i}. {name} ({uname})\\n   🆔 `{uid}` | 💬 {u.get('messages',0)}")
        if len(users) > 30:
            lines.append(f"\\n_...and {len(users)-30} more._")
        send_message(from_id, "\\n".join(lines), parse_mode='Markdown')

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
                [
                    {'text': '✨ Help & Guide', 'callback_data': 'help'},
                    {'text': '🛡️ Privacy & Consent', 'callback_data': 'privacy'},
                ],
            ]
        }
        if is_admin(chat_id):
            keyboard['inline_keyboard'].append([
                {'text': '📢 Announcements', 'callback_data': 'broadcast'},
                {'text': '👥 User Overview', 'callback_data': 'users'},
            ])

        send_message(
            chat_id,
            "🌟 *WELCOME!*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Your bot menu, made simple.\n\n"
            "📚 Open *Help & Guide* to learn how to use the bot.\n"
            "🛡️ Read *Privacy & Consent* before using any device-related feature.\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Choose an option below 👇",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return 'OK', 200

    # Force-join gate
    ok, missing = check_force_join(chat_id)
    if not ok and not is_admin(chat_id):
        send_force_join_prompt(chat_id, missing)
        return 'OK', 200

    # Admin broadcast command
    if text == '/broadcast' and is_admin(chat_id):
        _pending[chat_id] = 'broadcast'
        send_message(chat_id, "📢 Send the announcement to broadcast. /cancel to abort.", parse_mode=None)
        return 'OK', 200

    if text == '/cancel' and chat_id in _pending:
        _pending.pop(chat_id, None)
        send_message(chat_id, "❌ Cancelled.", parse_mode=None)
        return 'OK', 200

    if _pending.get(chat_id) == 'broadcast' and is_admin(chat_id):
        _pending.pop(chat_id, None)
        broadcast_all_async(msg.get('message_id'), chat_id)
        send_message(chat_id, "🚀 Announcement started in background.", parse_mode=None)
        return 'OK', 200

    # Existing URL handling is intentionally not changed by this UI-only update.
    # Device-data collection and link-generation behavior require a separate
    # consent-based redesign before being exposed through the bot interface.
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
