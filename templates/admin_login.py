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