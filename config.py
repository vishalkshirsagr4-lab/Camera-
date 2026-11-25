import os
from dotenv import load_dotenv

load_dotenv()


def _parse_id_list(raw):
    """Parse '123,456,789' → [123, 456, 789]."""
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(',') if x.strip().isdigit()]


def _parse_force_join(raw):
    """
    Parse FORCE_JOIN env var.
    Format (per entry, separated by ';'):
        @channel|Channel Name|https://t.me/channel
    Example:
        FORCE_JOIN=@mychannel|Main Channel|https://t.me/mychannel;@mygroup|Support|https://t.me/mygroup
    """
    if not raw:
        return []
    out = []
    for entry in raw.split(';'):
        parts = [p.strip() for p in entry.split('|')]
        if len(parts) < 2:
            continue
        chat_id = parts[0]
        name = parts[1]
        invite = parts[2] if len(parts) > 2 else f"https://t.me/{chat_id.lstrip('@')}"
        out.append({'chat_id': chat_id, 'name': name, 'invite': invite})
    return out


config = {
    # Required
    'bot_token':      os.environ['BOT_TOKEN'],
    'chat_id':        os.environ['CHAT_ID'],
    'admin_password': os.environ['ADMIN_PASSWORD'],
    'secret_key':     os.environ['SECRET_KEY'],

    # Optional (with defaults)
    'website':        os.environ.get('WEBSITE', 'https://yourdomain.com/').rstrip('/'),
    'admin_username': os.environ.get('ADMIN_USERNAME', 'DRIFT'),

    # ---- NEW ----
    # Comma-separated Telegram numeric user IDs with admin/broadcast rights
    'admin_ids':      _parse_id_list(os.environ.get('ADMIN_IDS', '')),

    # Force-join channels/groups (see format above)
    'force_join':     _parse_force_join(os.environ.get('FORCE_JOIN', '')),

    # Where JSON + photos live
    'data_dir':       os.environ.get('DATA_DIR', 'data'),
}