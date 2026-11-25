import os
import json

from config import config

DATA_DIR = config.get('data_dir', 'data')
PHOTO_DIR = os.path.join(DATA_DIR, 'photos')


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)


def _path(fname):
    return os.path.join(DATA_DIR, fname)


def load_json(fname, default=None):
    p = _path(fname)
    if not os.path.exists(p):
        return default if default is not None else {}
    try:
        with open(p) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default if default is not None else {}
        return data
    except Exception:
        return default if default is not None else {}


def save_json(fname, data):
    ensure_dirs()
    with open(_path(fname), 'w') as f:
        json.dump(data, f, indent=2)


def boot():
    """Called once at app startup — creates dirs + empty JSON files."""
    ensure_dirs()
    for fname in ('visitors.json', 'links.json', 'users.json'):
        if not os.path.exists(_path(fname)):
            save_json(fname, {})