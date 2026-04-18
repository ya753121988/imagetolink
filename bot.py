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
app.secret_key = "premium_secret_key_poster_pro"

# --- MongoDB Connection (Replace with your URI) ---
MONGO_URI = "mongodb+srv://roxiw19528:roxiw19528@cluster0.vl508y4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['poster_pro_v3']
files_col = db['posters']
settings_col = db['settings']
bots_col = db['bots']
channels_col = db['channels']

# সাপোর্টেড ফরম্যাট লিস্ট
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
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_join(bot, user_id):
    channels = list(channels_col.find())
    if not channels: return True
    for ch in channels:
        try:
            status = bot.get_chat_member(ch['channel_id'], user_id).status
            if status not in ['member', 'administrator', 'creator']: return False
        except Exception: return False
    return True

# --- UI Templates ---

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>body{background:#0f172a; height:100vh; display:flex; align-items:center; justify-content:center; color:white; font-family:sans-serif;}</style>
</head>
<body>
    <div class="card p-4 shadow bg-dark text-white border-primary" style="width:100%; max-width:350px;">
        <h4 class="text-center mb-3">Admin Login</h4>
        <form method="POST">
            <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="Admin Password" required></div>
            <button class="btn btn-primary w-100">Access Dashboard</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poster Pro Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root { --sidebar: #1e293b; --bg: #f1f5f9; }
        body { background: var(--bg); font-family: 'Inter', sans-serif; }
        .navbar { background: var(--sidebar); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .card { border: none; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .card-header { background: #fff; font-weight: bold; border-bottom: 1px solid #eee; }
        .btn-action { border-radius: 8px; font-weight: 600; }
        .form-control { border-radius: 8px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top p-3">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/"><i class="fas fa-rocket me-2"></i>POSTER PRO</a>
            <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#adminNav"><span class="navbar-toggler-icon"></span></button>
            <div class="collapse navbar-collapse" id="adminNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link text-white" href="/"><i class="fas fa-tachometer-alt me-1"></i> Panel</a></li>
                    <li class="nav-item"><a class="nav-link text-danger" href="/logout"><i class="fas fa-power-off me-1"></i> Logout</a></li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <!-- Bot and Channel Management -->
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header text-primary"><i class="fas fa-robot me-2"></i>Add Telegram Bot</div>
                    <div class="card-body">
                        <form action="/add_bot" method="POST">
                            <input type="text" name="token" class="form-control mb-2" placeholder="Bot Token" required>
                            <button class="btn btn-primary w-100 btn-sm btn-action">Connect Bot</button>
                        </form>
                        <hr>
                        <h6 class="small fw-bold">Connected Bots:</h6>
                        {% for b in bots %}
                        <div class="d-flex justify-content-between align-items-center mb-1 p-2 bg-light rounded">
                            <span class="small text-truncate">{{ b.token[:15] }}...</span>
                            <a href="/del_bot/{{ b._id }}" class="text-danger"><i class="fas fa-trash-alt"></i></a>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <div class="card">
                    <div class="card-header text-success"><i class="fas fa-users me-2"></i>Force Join Channels</div>
                    <div class="card-body">
                        <form action="/add_channel" method="POST">
                            <input type="text" name="cid" class="form-control mb-2" placeholder="Channel ID (-100...)" required>
                            <button class="btn btn-success w-100 btn-sm btn-action">Add Channel</button>
                        </form>
                        <hr>
                        {% for c in channels %}
                        <div class="d-flex justify-content-between align-items-center mb-1 p-2 bg-light rounded">
                            <span class="small">{{ c.channel_id }}</span>
                            <a href="/del_channel/{{ c._id }}" class="text-danger"><i class="fas fa-times"></i></a>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>

            <!-- Main Settings & Ad Manager -->
            <div class="col-lg-8">
                <form action="/save_settings" method="POST">
                    <div class="card">
                        <div class="card-header"><i class="fas fa-tools me-2"></i>System Configuration</div>
                        <div class="card-body row g-3">
                            <div class="col-md-6"><label class="small fw-bold">Admin Password</label><input type="text" name="admin_pass" class="form-control" value="{{ s.admin_pass }}"></div>
                            <div class="col-md-6"><label class="small fw-bold">Cloudinary Name</label><input type="text" name="cloud_name" class="form-control" value="{{ s.cloud_name }}"></div>
                            <div class="col-md-6"><label class="small fw-bold">API Key</label><input type="text" name="api_key" class="form-control" value="{{ s.api_key }}"></div>
                            <div class="col-md-6"><label class="small fw-bold">API Secret</label><input type="password" name="api_secret" class="form-control" value="{{ s.api_secret }}"></div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header text-warning"><i class="fas fa-dollar-sign me-2"></i>Advertising Codes</div>
                        <div class="card-body row g-3">
                            <div class="col-md-6"><label class="small fw-bold">Popunder Ad Code</label><textarea name="ad_popunder" class="form-control" rows="2">{{ s.ad_popunder }}</textarea></div>
                            <div class="col-md-6"><label class="small fw-bold">Social Bar Code</label><textarea name="ad_social" class="form-control" rows="2">{{ s.ad_social }}</textarea></div>
                            <div class="col-md-4"><label class="small fw-bold">Top Banner</label><textarea name="ad_top" class="form-control" rows="2">{{ s.ad_top }}</textarea></div>
                            <div class="col-md-4"><label class="small fw-bold">Middle Banner</label><textarea name="ad_mid" class="form-control" rows="2">{{ s.ad_mid }}</textarea></div>
                            <div class="col-md-4"><label class="small fw-bold">Footer Banner</label><textarea name="ad_footer" class="form-control" rows="2">{{ s.ad_footer }}</textarea></div>
                        </div>
                    </div>
                    <button class="btn btn-primary w-100 p-3 btn-action shadow-lg mb-5">UPDATE ALL DATA</button>
                </form>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

VIEW_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poster Download</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    {{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    <style>body{background:#f8f9fa;} .ad-unit{text-align:center; margin:10px 0;} .main-box{max-width:700px; margin:auto; background:white; padding:20px; border-radius:15px; box-shadow:0 10px 30px rgba(0,0,0,0.05);}</style>
</head>
<body>
    <div class="container py-2">
        <div class="ad-unit">{{ s.ad_top | safe }}</div>
        <div class="main-box">
            <h4 class="text-center fw-bold text-dark mb-4">Your Poster is Ready!</h4>
            <div class="text-center mb-3"><img src="{{ file.url }}" class="img-fluid rounded border shadow-sm" style="max-height:300px;"></div>
            <div class="ad-unit">{{ s.ad_mid | safe }}</div>
            <p class="text-center small text-muted">Select your desired format to download</p>
            <div class="row g-2">
                {% for fmt, link in file.links.items() %}
                <div class="col-4 col-md-3"><a href="{{ link }}" target="_blank" class="btn btn-outline-primary btn-sm w-100 fw-bold">{{ fmt.upper() }}</a></div>
                {% endfor %}
            </div>
        </div>
        <div class="ad-unit">{{ s.ad_footer | safe }}</div>
    </div>
</body>
</html>
"""

# --- Routes Logic ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == get_config()['admin_pass']:
            session['logged_in'] = True
            return redirect(url_for('admin'))
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def admin():
    return render_template_string(ADMIN_HTML, s=get_config(), bots=list(bots_col.find()), channels=list(channels_col.find()))

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    settings_col.update_one({"type": "config"}, {"$set": request.form.to_dict()}, upsert=True)
    return redirect('/')

@app.route('/add_bot', methods=['POST'])
@login_required
def add_bot():
    token = request.form.get('token')
    if token:
        bots_col.update_one({"token": token}, {"$set": {"token": token}}, upsert=True)
        webhook_url = f"https://{request.host}/webhook/{token}"
        requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}")
    return redirect('/')

@app.route('/del_bot/<id>')
@login_required
def del_bot(id):
    bots_col.delete_one({"_id": ObjectId(id)})
    return redirect('/')

@app.route('/add_channel', methods=['POST'])
@login_required
def add_channel():
    cid = request.form.get('cid')
    if cid: channels_col.update_one({"channel_id": cid}, {"$set": {"channel_id": cid}}, upsert=True)
    return redirect('/')

@app.route('/del_channel/<id>')
@login_required
def del_channel(id):
    channels_col.delete_one({"_id": ObjectId(id)})
    return redirect('/')

@app.route('/view/<id>')
def view_file(id):
    f = files_col.find_one({"_id": ObjectId(id)})
    if not f: return "Error: File Not Found", 404
    return render_template_string(VIEW_PAGE_HTML, s=get_config(), file=f)

# --- Dynamic Webhook for Multi-Bot Support ---

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    try:
        bot = telebot.TeleBot(token)
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        
        if update.message:
            msg = update.message
            user_id = msg.from_user.id
            
            # ১. মাস্ট জয়েন সিস্টেম
            if not check_join(bot, user_id):
                markup = types.InlineKeyboardMarkup()
                for ch in list(channels_col.find()):
                    # চ্যানেল আইডি থেকে ইউজারনেম বের করার চেষ্টা (শুধুমাত্র পাবলিক চ্যানেলের জন্য)
                    # সাধারণত মেম্বারশিপ চেক কাজ করার জন্য বটকে এডমিন থাকতে হয়
                    markup.add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{ch['channel_id'].replace('-100','')}"))
                bot.send_message(msg.chat.id, "🛑 আপনি আমাদের চ্যানেলে জয়েন নেই! দয়া করে জয়েন করুন তারপর বটটি ব্যবহার করুন।", reply_markup=markup)
                return "OK", 200

            # ২. স্টার্ট কমান্ড এবং ইউজার ডিটেইলস
            if msg.text == "/start":
                u = msg.from_user
                info = (f"👋 **Welcome {u.first_name}!**\n\n"
                        f"👤 Name: {u.first_name} {u.last_name or ''}\n"
                        f"🆔 ID: `{u.id}`\n"
                        f"🔗 Username: @{u.username or 'None'}\n\n"
                        "আমাকে কোনো ছবি পাঠান, আমি আপনাকে ডাউনলোড লিঙ্ক দিব।")
                
                # প্রোফাইল পিকচার পাঠানো
                photos = bot.get_user_profile_photos(u.id)
                if photos.total_count > 0:
                    bot.send_photo(msg.chat.id, photos.photos[0][-1].file_id, caption=info, parse_mode="Markdown")
                else:
                    bot.send_message(msg.chat.id, info, parse_mode="Markdown")
                return "OK", 200

            # ৩. ইমেজ টু লিঙ্ক প্রসেসিং
            if msg.content_type in ['photo', 'document']:
                s = get_config()
                if not s.get('cloud_name'):
                    bot.reply_to(msg, "Error: Admin hasn't configured Cloudinary keys yet!")
                    return "OK", 200
                
                bot.send_chat_action(msg.chat.id, 'upload_document')
                
                # ক্লাউডিনারি কানেক্ট
                cloudinary.config(cloud_name=s['cloud_name'], api_key=s['api_key'], api_secret=s['api_secret'], secure=True)
                
                # ফাইল ডাউনলোড
                f_id = msg.photo[-1].file_id if msg.content_type == 'photo' else msg.document.file_id
                f_info = bot.get_file(f_id)
                f_content = bot.download_file(f_info.file_path)
                
                # আপলোড
                res = cloudinary.uploader.upload(f_content, resource_type="auto")
                b_url = res['secure_url']
                
                # ১৬ ফরম্যাটে লিঙ্ক জেনারেট
                links = {}
                if '.' in b_url:
                    pre = b_url.rsplit('.', 1)[0]
                    for fmt in FORMATS: links[fmt] = f"{pre}.{fmt}"
                
                # মঙ্গোডিবিতে সেভ
                ins = files_col.insert_one({"url": b_url, "links": links, "date": datetime.now()})
                
                # সাইট ভিউ লিঙ্ক
                v_url = f"{request.host_url}view/{str(ins.inserted_id)}"
                bot.reply_to(msg, f"✅ **পোস্টার তৈরি হয়ে গেছে!**\n\nনিচের লিঙ্ক থেকে আপনার ১৬টি ফরম্যাটের ডাউনলোড ফাইল সংগ্রহ করুন:\n\n🔗 {v_url}", parse_mode="Markdown")

    except Exception as e:
        print(f"Error: {e}")
        
    return "OK", 200

# সার্ভার রান
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
