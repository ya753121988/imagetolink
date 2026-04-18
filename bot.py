import os
import requests
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader
import telebot
from telebot import types
from datetime import datetime
from bson.objectid import ObjectId
import functools

app = Flask(__name__)
app.secret_key = "ultimate_poster_pro_v5_key"

# --- MongoDB Connection (Provided by User) ---
MONGO_URI = "mongodb+srv://roxiw19528:roxiw19528@cluster0.vl508y4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['poster_pro_db']
files_col = db['posters']
settings_col = db['settings']
bots_col = db['bots']
channels_col = db['channels']

# ১৬টি ফরম্যাটের লিস্ট
FORMATS = ['jpg', 'jpeg', 'png', 'pdf', 'webp', 'svg', 'eps', 'psd', 'ai', 'tiff', 'gif', 'indd', 'bmp', 'raw', 'heic', 'avif']

# --- Helpers ---
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", 
            "admin_pass": "admin123", 
            "cloud_name": "", 
            "api_key": "", 
            "api_secret": "", 
            "ad_popunder": "", 
            "ad_social": "", 
            "ad_top": "", 
            "ad_mid": "", 
            "ad_footer": ""
        }
        settings_col.insert_one(conf)
    return conf

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_join(bot, user_id):
    channels = list(channels_col.find())
    if not channels: return True
    for ch in channels:
        try:
            status = bot.get_chat_member(ch['channel_id'], user_id).status
            if status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

# --- HTML Templates (Premium & Responsive) ---

# ১. ইউজার প্যানেল (Home Page with Upload System)
USER_PANEL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poster Hub - Unlimited Upload</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    {{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    <style>
        body { background: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
        .hero { background: #4f46e5; color: white; padding: 40px 0; border-radius: 0 0 30px 30px; }
        .upload-card { background: white; border-radius: 20px; padding: 25px; margin-top: -40px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border: none; }
        .drop-zone { border: 2px dashed #4f46e5; border-radius: 15px; padding: 30px; cursor: pointer; transition: 0.3s; color: #4f46e5; font-weight: bold; }
        .drop-zone:hover { background: #f0f0ff; }
        .poster-card { border-radius: 15px; overflow: hidden; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: 0.3s; }
        .poster-card:hover { transform: translateY(-5px); }
        .ad-box { text-align: center; margin: 20px 0; min-height: 50px; }
    </style>
</head>
<body>
    <div class="hero text-center">
        <div class="container">
            <h2 class="fw-bold">Poster Cloud Engine</h2>
            <p>Convert your image to 16+ professional links instantly</p>
        </div>
    </div>

    <div class="container">
        <!-- Web Upload -->
        <div class="row justify-content-center">
            <div class="col-md-7">
                <div class="card upload-card">
                    <form action="/web_upload" method="POST" enctype="multipart/form-data" id="upForm">
                        <label for="file-in" class="drop-zone w-100 text-center" id="dz">
                            <i class="fas fa-file-upload fa-3x mb-2"></i><br>
                            Click to Select Image & Convert
                        </label>
                        <input type="file" name="file" id="file-in" style="display:none;" onchange="startUp()" accept="image/*">
                    </form>
                    <div id="loader" class="text-center mt-3" style="display:none;">
                        <div class="spinner-border text-primary mb-2"></div><p>Generating Links...</p>
                    </div>
                    <div class="ad-box">{{ s.ad_mid | safe }}</div>
                </div>
            </div>
        </div>

        <div class="ad-box">{{ s.ad_top | safe }}</div>

        <!-- Recent Gallery -->
        <h5 class="mt-4 mb-3 fw-bold"><i class="fas fa-clock text-primary me-2"></i>Recent Creations</h5>
        <div class="row g-3">
            {% for f in files %}
            <div class="col-6 col-md-3">
                <div class="card poster-card h-100">
                    <img src="{{ f.url }}" class="card-img-top" style="height:140px; object-fit:cover;">
                    <div class="card-body p-2"><a href="/view/{{ f._id }}" class="btn btn-primary btn-sm w-100 rounded-pill">View 16 Links</a></div>
                </div>
            </div>
            {% endfor %}
        </div>
        <div class="ad-box">{{ s.ad_footer | safe }}</div>
    </div>

    <script>
        function startUp() {
            document.getElementById('dz').style.display = 'none';
            document.getElementById('loader').style.display = 'block';
            document.getElementById('upForm').submit();
        }
    </script>
</body>
</html>
"""

# ২. ভিউ পেজ (১৬টি লিঙ্ক এবং এড)
VIEW_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Poster</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    {{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    <style>
        body { background: #f3f4f6; }
        .main-card { max-width: 750px; margin: 20px auto; background: white; padding: 25px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
        .btn-fmt { text-transform: uppercase; font-weight: bold; font-size: 11px; border-radius: 8px; margin-bottom: 5px; }
        .ad-box { text-align: center; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="ad-box">{{ s.ad_top | safe }}</div>
        <div class="main-card">
            <h4 class="text-center fw-bold mb-4">Posters Successfully Generated</h4>
            <div class="text-center mb-4"><img src="{{ file.url }}" class="img-fluid rounded shadow border" style="max-height: 280px;"></div>
            <div class="ad-box">{{ s.ad_mid | safe }}</div>
            <div class="row g-2">
                {% for fmt, link in file.links.items() %}
                <div class="col-4 col-md-3"><a href="{{ link }}" target="_blank" class="btn btn-outline-primary btn-fmt w-100">{{ fmt }}</a></div>
                {% endfor %}
            </div>
        </div>
        <div class="ad-box">{{ s.ad_footer | safe }}</div>
    </div>
</body>
</html>
"""

# ৩. এডমিন প্যানেল
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: #f8fafc; font-size: 13px; }
        .navbar { background: #1e293b; color: white; }
        .card { border-radius: 12px; border: none; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .card-header { background: #fff; font-weight: bold; border-bottom: 1px solid #f1f5f9; }
        .sidebar-link { display: block; padding: 10px; color: #475569; text-decoration: none; border-radius: 8px; }
        .sidebar-link:hover { background: #f1f5f9; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg mb-4 p-3">
        <div class="container"><a class="navbar-brand text-white fw-bold" href="/admin">PRO PANEL</a><a href="/logout" class="btn btn-danger btn-sm">Logout</a></div>
    </nav>
    <div class="container">
        <div class="row">
            <div class="col-lg-4">
                <div class="card p-3">
                    <form action="/add_bot" method="POST">
                        <label class="fw-bold mb-2">Connect New Bot</label>
                        <input type="text" name="token" class="form-control mb-2" placeholder="Bot Token" required>
                        <button class="btn btn-primary btn-sm w-100 mb-3">Add & Auto Webhook</button>
                    </form>
                    <div class="small border p-2" style="max-height: 100px; overflow-y: auto;">
                        {% for b in bots %}<div class="d-flex justify-content-between mb-1">{{ b.token[:15] }}... <a href="/del_bot/{{ b._id }}" class="text-danger">×</a></div>{% endfor %}
                    </div>
                </div>
                <div class="card p-3">
                    <form action="/add_channel" method="POST">
                        <label class="fw-bold mb-2">Force Join (Channel ID)</label>
                        <input type="text" name="cid" class="form-control mb-2" placeholder="-100..." required>
                        <button class="btn btn-dark btn-sm w-100 mb-3">Add Channel</button>
                    </form>
                    <div class="small border p-2">
                        {% for c in channels %}<div class="d-flex justify-content-between mb-1">{{ c.channel_id }} <a href="/del_channel/{{ c._id }}" class="text-danger">×</a></div>{% endfor %}
                    </div>
                </div>
            </div>
            <div class="col-lg-8">
                <form action="/save_settings" method="POST">
                    <div class="card p-3">
                        <h6 class="fw-bold border-bottom pb-2">Main Configuration</h6>
                        <div class="row g-2 mt-1">
                            <div class="col-md-6"><label>Admin Password</label><input type="text" name="admin_pass" class="form-control" value="{{ s.admin_pass }}"></div>
                            <div class="col-md-6"><label>Cloud Name</label><input type="text" name="cloud_name" class="form-control" value="{{ s.cloud_name }}"></div>
                            <div class="col-md-6"><label>API Key</label><input type="text" name="api_key" class="form-control" value="{{ s.api_key }}"></div>
                            <div class="col-md-6"><label>API Secret</label><input type="password" name="api_secret" class="form-control" value="{{ s.api_secret }}"></div>
                        </div>
                    </div>
                    <div class="card p-3">
                        <h6 class="fw-bold border-bottom pb-2">Ads Management</h6>
                        <div class="row g-2 mt-1">
                            <div class="col-md-4"><label>Popunder</label><textarea name="ad_popunder" class="form-control" rows="2">{{ s.ad_popunder }}</textarea></div>
                            <div class="col-md-4"><label>Social Bar</label><textarea name="ad_social" class="form-control" rows="2">{{ s.ad_social }}</textarea></div>
                            <div class="col-md-4"><label>Top Ad</label><textarea name="ad_top" class="form-control" rows="2">{{ s.ad_top }}</textarea></div>
                            <div class="col-md-6"><label>Middle Ad</label><textarea name="ad_mid" class="form-control" rows="2">{{ s.ad_mid }}</textarea></div>
                            <div class="col-md-6"><label>Footer Ad</label><textarea name="ad_footer" class="form-control" rows="2">{{ s.ad_footer }}</textarea></div>
                        </div>
                    </div>
                    <button class="btn btn-primary w-100 p-3 fw-bold">SAVE ALL CHANGES</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ৪. লগইন পেজ
LOGIN_HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh;}</style></head>
<body><div class="card p-4 shadow bg-dark text-white" style="width:340px;">
<h5 class="text-center mb-4">Admin Dashboard</h5><form method="POST">
<input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
<button class="btn btn-primary w-100">Login</button></form></div></body></html>
"""

# --- Routes & Logic ---

@app.route('/')
def home():
    conf = get_config()
    files = list(files_col.find().sort("_id", -1).limit(20))
    return render_template_string(USER_PANEL_HTML, s=conf, files=files)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == get_config()['admin_pass']:
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_panel():
    return render_template_string(ADMIN_HTML, s=get_config(), bots=list(bots_col.find()), channels=list(channels_col.find()))

@app.route('/web_upload', methods=['POST'])
def web_upload():
    if 'file' not in request.files: return redirect('/')
    file = request.files['file']
    if file.filename == '': return redirect('/')
    s = get_config()
    cloudinary.config(cloud_name=s['cloud_name'], api_key=s['api_key'], api_secret=s['api_secret'], secure=True)
    res = cloudinary.uploader.upload(file, resource_type="auto")
    b_url = res['secure_url']
    links = {}
    if '.' in b_url:
        pre = b_url.rsplit('.', 1)[0]
        for fmt in FORMATS: links[fmt] = f"{pre}.{fmt}"
    ins = files_col.insert_one({"url": b_url, "links": links, "date": datetime.now()})
    return redirect(url_for('view_file', id=str(ins.inserted_id)))

@app.route('/view/<id>')
def view_file(id):
    f = files_col.find_one({"_id": ObjectId(id)})
    if not f: return "File Not Found", 404
    return render_template_string(VIEW_PAGE_HTML, s=get_config(), file=f)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    settings_col.update_one({"type": "config"}, {"$set": request.form.to_dict()}, upsert=True)
    return redirect(url_for('admin_panel'))

@app.route('/add_bot', methods=['POST'])
@login_required
def add_bot():
    token = request.form.get('token')
    if token:
        bots_col.update_one({"token": token}, {"$set": {"token": token}}, upsert=True)
        webhook_url = f"https://{request.host}/webhook/{token}"
        requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}")
    return redirect(url_for('admin_panel'))

@app.route('/del_bot/<id>')
@login_required
def del_bot(id):
    bots_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

@app.route('/add_channel', methods=['POST'])
@login_required
def add_channel():
    cid = request.form.get('cid')
    if cid: channels_col.update_one({"channel_id": cid}, {"$set": {"channel_id": cid}}, upsert=True)
    return redirect(url_for('admin_panel'))

@app.route('/del_channel/<id>')
@login_required
def del_channel(id):
    channels_col.delete_one({"_id": ObjectId(id)})
    return redirect(url_for('admin_panel'))

# --- Multi-Bot Webhook Logic ---

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    try:
        bot = telebot.TeleBot(token)
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        if update.message:
            msg = update.message
            u_id = msg.from_user.id
            if not check_join(bot, u_id):
                markup = types.InlineKeyboardMarkup()
                for ch in list(channels_col.find()):
                    markup.add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{ch['channel_id'].replace('-100','')}"))
                bot.send_message(msg.chat.id, "❌ আপনি জয়েন নেই!", reply_markup=markup)
                return "OK", 200

            if msg.text == "/start":
                user = msg.from_user
                info = f"👤 **Profile**\nName: {user.first_name}\nID: `{user.id}`\nUsername: @{user.username}"
                photos = bot.get_user_profile_photos(u_id)
                if photos.total_count > 0: bot.send_photo(msg.chat.id, photos.photos[0][-1].file_id, caption=info, parse_mode="Markdown")
                else: bot.send_message(msg.chat.id, info, parse_mode="Markdown")
                return "OK", 200

            if msg.content_type in ['photo', 'document']:
                s = get_config()
                cloudinary.config(cloud_name=s['cloud_name'], api_key=s['api_key'], api_secret=s['api_secret'], secure=True)
                f_id = msg.photo[-1].file_id if msg.content_type == 'photo' else msg.document.file_id
                f_info = bot.get_file(f_id)
                f_content = bot.download_file(f_info.file_path)
                res = cloudinary.uploader.upload(f_content, resource_type="auto")
                b_url = res['secure_url']
                links = {}
                if '.' in b_url:
                    pre = b_url.rsplit('.', 1)[0]
                    for fmt in FORMATS: links[fmt] = f"{pre}.{fmt}"
                ins = files_col.insert_one({"url": b_url, "links": links, "date": datetime.now()})
                bot.reply_to(msg, f"✅ পোস্টার রেডি!\n🔗 {request.host_url}view/{str(ins.inserted_id)}")
    except: pass
    return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
