from config import config
from core.telegram import get_chat_member, send_message


def is_admin(tg_user_id):
    return int(tg_user_id) in [int(x) for x in config.get('admin_ids', [])]


def _is_member(chat_id, user_id):
    status = get_chat_member(chat_id, user_id)
    return status in ('creator', 'administrator', 'member')


def check_force_join(tg_user_id):
    """Returns (ok, missing_channels)."""
    missing = []
    for ch in config.get('force_join', []):
        if not _is_member(ch['chat_id'], tg_user_id):
            missing.append(ch)
    return (len(missing) == 0, missing)


def send_force_join_prompt(chat_id, missing):
    buttons = [[{'text': f"➡️ Join {ch['name']}", 'url': ch['invite']}] for ch in missing]
    buttons.append([{'text': '✅ Verify Join', 'callback_data': 'check_join'}])
    send_message(
        chat_id,
        "🔒 *Access Locked*\n\nJoin the channels below to use this bot:",
        reply_markup={'inline_keyboard': buttons},
    )