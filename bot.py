# -*- coding: utf-8 -*-
import os
import io
import json
import requests
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, send_file
from pymongo import MongoClient
import gridfs
import telebot
from telebot import types
from datetime import datetime
from bson.objectid import ObjectId
import functools

# --- INITIALIZATION ---
app = Flask(__name__)
app.secret_key = "MONSTER_PROJECT_SECRET_KEY_ULTRA_MAX_V20"

# --- DATABASE CONNECTION (YOUR OWN MONGODB) ---
MONGO_URI = "mongodb+srv://roxiw19528:roxiw19528@cluster0.vl508y4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
try:
    client = MongoClient(MONGO_URI)
    db = client['poster_hosting_pro_db']
    fs = gridfs.GridFS(db)
    files_col = db['all_posters']
    settings_col = db['system_settings']
    bots_col = db['active_bots']
    channels_col = db['force_channels']
    users_col = db['bot_users']
    print("Database Connected Successfully!")
except Exception as e:
    print(f"DB Error: {e}")

# --- CONFIGURATION & CONSTANTS ---
FORMATS = [
    'jpg', 'jpeg', 'png', 'pdf', 'webp', 'svg', 'eps', 
    'psd', 'ai', 'tiff', 'gif', 'indd', 'bmp', 'raw', 'heic', 'avif'
]

# --- CORE HELPERS ---
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config",
            "admin_pass": "admin123",
            "ad_popunder": "",
            "ad_social": "",
            "ad_top": "",
            "ad_mid": "",
            "ad_footer": "",
            "site_name": "Poster Cloud API"
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

def is_subscribed(bot, user_id):
    channels = list(channels_col.find())
    if not channels: return True
    for ch in channels:
        try:
            status = bot.get_chat_member(ch['channel_id'], user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            continue # If bot is not admin in one channel, skip or handle as needed
    return True

# --- PREMIUM UI CSS (EXTENSIVE STYLING) ---
PREMIUM_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700;800&display=swap');
    :root {
        --primary: #6366f1;
        --secondary: #c026d3;
        --bg: #0b0f19;
        --glass: rgba(255, 255, 255, 0.03);
        --border: rgba(255, 255, 255, 0.08);
        --text: #f1f5f9;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: var(--bg); color: var(--text); font-family: 'Plus Jakarta Sans', sans-serif; line-height: 1.6; }
    .nav-premium { background: rgba(11, 15, 25, 0.8); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 1000; padding: 15px 0; }
    .glass-card { background: var(--glass); backdrop-filter: blur(15px); border: 1px solid var(--border); border-radius: 24px; padding: 30px; transition: 0.4s ease; }
    .glass-card:hover { border-color: var(--primary); transform: translateY(-5px); }
    .btn-main { background: linear-gradient(135deg, var(--primary), var(--secondary)); border: none; color: white; padding: 12px 30px; border-radius: 14px; font-weight: 700; transition: 0.3s; cursor: pointer; text-decoration: none; display: inline-block; }
    .btn-main:hover { opacity: 0.9; transform: scale(1.05); color: white; box-shadow: 0 10px 20px rgba(99, 102, 241, 0.3); }
    .form-control { background: #161b2c !important; border: 1px solid var(--border) !important; color: white !important; border-radius: 12px; padding: 12px; }
    .form-control:focus { border-color: var(--primary); box-shadow: none; }
    .poster-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; margin-top: 40px; }
    .poster-item img { width: 100%; height: 200px; object-fit: cover; border-radius: 18px; border: 1px solid var(--border); }
    .ad-slot { background: rgba(255,255,255,0.02); border: 1px dashed #444; border-radius: 15px; min-height: 90px; display: flex; align-items: center; justify-content: center; margin: 20px 0; }
    .sidebar { background: #111827; min-height: 100vh; border-right: 1px solid var(--border); padding: 30px 15px; }
    .sidebar a { color: #94a3b8; text-decoration: none; display: block; padding: 12px 15px; border-radius: 10px; margin-bottom: 5px; font-weight: 600; }
    .sidebar a.active { background: var(--primary); color: white; }
    @media (max-width: 768px) { .poster-grid { grid-template-columns: 1fr 1fr; } .hero-title { font-size: 2rem; } }
</style>
"""

# --- PUBLIC ROUTES ---

@app.route('/f/<file_id>')
def serve_file(file_id):
    try:
        file_obj = fs.get(ObjectId(file_id))
        return send_file(io.BytesIO(file_obj.read()), mimetype=file_obj.content_type)
    except:
        return "404 File Not Found", 404

@app.route('/')
def home():
    s = get_config()
    posters = list(files_col.find().sort("_id", -1).limit(12))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ s.site_name }} - Unlimited Image Hosting</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        {{ style | safe }}{{ s.ad_popunder | safe }}{{ s.ad_social | safe }}
    </head>
    <body>
        <nav class="nav-premium">
            <div class="container d-flex justify-content-between">
                <a href="/" class="fw-bold fs-4 text-white text-decoration-none">{{ s.site_name }}</a>
                <a href="/admin" class="btn btn-outline-light btn-sm rounded-pill">Admin Login</a>
            </div>
        </nav>
        <div class="container mt-5">
            <div class="text-center py-5">
                <h1 class="fw-extrabold display-3 hero-title">Professional Image <span class="text-primary">Hosting API</span></h1>
                <p class="text-secondary fs-5">Upload your posters and generate 16+ professional links instantly.</p>
            </div>
            <div class="row justify-content-center">
                <div class="col-lg-7">
                    <div class="glass-card text-center">
                        <form action="/upload_web" method="POST" enctype="multipart/form-data" id="mainUp">
                            <label for="up" class="w-100 p-5 border-2 border-dashed border-primary rounded-4" style="cursor:pointer">
                                <i class="fas fa-images fa-4x text-primary mb-3"></i>
                                <h3>Select Your Poster</h3>
                                <p class="small text-muted">Supports JPG, PNG, PSD, AI, PDF and more</p>
                            </label>
                            <input type="file" name="file" id="up" style="display:none" onchange="document.getElementById('mainUp').submit();">
                        </form>
                    </div>
                </div>
            </div>
            <div class="ad-slot">{{ s.ad_top | safe }}</div>
            <h4 class="mt-5 fw-bold"><i class="fas fa-bolt text-warning me-2"></i>Recent Public Uploads</h4>
            <div class="poster-grid">
                {% for p in posters %}
                <div class="poster-item">
                    <div class="glass-card p-2">
                        <img src="/f/{{ p.file_id }}" alt="poster">
                        <div class="p-2 text-center">
                            <a href="/view/{{ p._id }}" class="btn-main w-100 btn-sm">Get 16 Links</a>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="ad-slot">{{ s.ad_footer | safe }}</div>
        </div>
        <footer class="py-5 text-center text-muted">© {{ year }} {{ s.site_name }}. Professional Cloud API System.</footer>
    </body>
    </html>
    """, style=PREMIUM_STYLE, s=s, posters=posters, year=datetime.now().year)

@app.route('/upload_web', methods=['POST'])
def upload_web():
    if 'file' not in request.files: return redirect('/')
    file = request.files['file']
    if file.filename == '': return redirect('/')
    
    # Save to GridFS
    fid = fs.put(file.read(), filename=file.filename, content_type=file.content_type)
    
    # Generate Link Array
    base_url = f"{request.host_url}f/{str(fid)}"
    links = {fmt: f"{base_url}?format={fmt}" for fmt in FORMATS}
    
    ins_id = files_col.insert_one({
        "file_id": str(fid),
        "links": links,
        "date": datetime.now(),
        "type": "web"
    }).inserted_id
    
    return redirect(url_for('view_poster', id=str(ins_id)))

@app.route('/view/<id>')
def view_poster(id):
    s = get_config()
    p = files_col.find_one({"_id": ObjectId(id)})
    if not p: return "Poster Expired or Not Found", 404
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Download Poster - {{ s.site_name }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        {{ style | safe }}{{ s.ad_popunder | safe }}{{ s.ad_social | safe }}
    </head>
    <body class="py-4">
        <div class="container">
            <div class="ad-slot">{{ s.ad_top | safe }}</div>
            <div class="glass-card mx-auto text-center" style="max-width: 900px;">
                <h2 class="fw-bold mb-4">Poster Links Generated Successfully</h2>
                <img src="/f/{{ p.file_id }}" class="rounded shadow border border-primary mb-4" style="max-height: 400px; width: auto;">
                <div class="ad-slot">{{ s.ad_mid | safe }}</div>
                <h5 class="mb-4 text-start">Select format to download:</h5>
                <div class="row g-2">
                    {% for fmt, link in p.links.items() %}
                    <div class="col-md-3 col-6"><a href="{{ link }}" target="_blank" class="btn btn-outline-primary w-100 btn-sm fw-bold">{{ fmt.upper() }}</a></div>
                    {% endfor %}
                </div>
            </div>
            <div class="ad-slot">{{ s.ad_footer | safe }}</div>
        </div>
    </body>
    </html>
    """, style=PREMIUM_STYLE, s=s, p=p)

# --- ADMIN SECTION (ULTRA DETAILED) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == get_config()['admin_pass']:
            session['logged_in'] = True
            return redirect(url_for('admin_dash'))
    return render_template_string("""
    <body style="background:#0b0f19; height:100vh; display:flex; align-items:center; justify-content:center; color:white; font-family:sans-serif;">
        <div style="background:rgba(255,255,255,0.05); padding:40px; border-radius:24px; border:1px solid rgba(255,255,255,0.1); width:100%; max-width:400px; text-align:center;">
            <h2 class="mb-4">Admin Access</h2>
            <form method="POST">
                <input type="password" name="password" class="form-control mb-3" placeholder="Password" style="background:#161b2c; border:1px solid #333; color:white; width:100%; padding:12px; border-radius:12px;">
                <button type="submit" style="background:#6366f1; border:none; color:white; padding:12px; width:100%; border-radius:12px; font-weight:bold;">Login</button>
            </form>
        </div>
    </body>
    """)

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

@app.route('/admin')
@login_required
def admin_dash():
    s = get_config()
    post_count = files_col.count_documents({})
    bot_count = bots_col.count_documents({})
    bots = list(bots_col.find())
    chans = list(channels_col.find())
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">{{ style | safe }}</head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <div class="col-md-2 sidebar">
                    <h4 class="text-white fw-bold mb-4">ADMIN PRO</h4>
                    <a href="/admin" class="active">Settings</a>
                    <a href="/admin/posters">Posters Gallery</a>
                    <a href="/" target="_blank">View Site</a>
                    <a href="/logout" class="text-danger mt-5">Logout</a>
                </div>
                <div class="col-md-10 p-5">
                    <div class="row g-4 mb-4">
                        <div class="col-md-6"><div class="glass-card"><h6>Total Uploads</h6><h2>{{ post_count }}</h2></div></div>
                        <div class="col-md-6"><div class="glass-card"><h6>Active Bots</h6><h2>{{ bot_count }}</h2></div></div>
                    </div>
                    
                    <form action="/admin/save" method="POST" class="glass-card row g-3">
                        <h5 class="fw-bold">General & Ad Settings</h5>
                        <div class="col-md-4"><label>Admin Password</label><input type="text" name="admin_pass" class="form-control" value="{{ s.admin_pass }}"></div>
                        <div class="col-md-4"><label>Site Name</label><input type="text" name="site_name" class="form-control" value="{{ s.site_name }}"></div>
                        <div class="col-md-4"><label>Popunder Ad</label><textarea name="ad_popunder" class="form-control" rows="1">{{ s.ad_popunder }}</textarea></div>
                        <div class="col-md-3"><label>Social Bar</label><textarea name="ad_social" class="form-control" rows="1">{{ s.ad_social }}</textarea></div>
                        <div class="col-md-3"><label>Top Ad</label><textarea name="ad_top" class="form-control" rows="1">{{ s.ad_top }}</textarea></div>
                        <div class="col-md-3"><label>Mid Ad</label><textarea name="ad_mid" class="form-control" rows="1">{{ s.ad_mid }}</textarea></div>
                        <div class="col-md-3"><label>Footer Ad</label><textarea name="ad_footer" class="form-control" rows="1">{{ s.ad_footer }}</textarea></div>
                        <div class="col-12"><button class="btn-main">Save Configuration</button></div>
                    </form>

                    <div class="row mt-4 g-4">
                        <div class="col-md-6">
                            <div class="glass-card">
                                <h5>Add Telegram Bot</h5>
                                <form action="/admin/add_bot" method="POST" class="input-group mb-3">
                                    <input type="text" name="token" class="form-control" placeholder="Bot Token">
                                    <button class="btn btn-primary">Connect</button>
                                </form>
                                <div style="max-height: 200px; overflow-y: auto;">
                                    {% for b in bots %}
                                    <div class="d-flex justify-content-between border-bottom border-secondary py-2">
                                        <span class="small">{{ b.token[:20] }}...</span>
                                        <a href="/admin/del_bot/{{ b._id }}" class="text-danger small">Delete</a>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="glass-card">
                                <h5>Force Join Channels</h5>
                                <form action="/admin/add_chan" method="POST" class="input-group mb-3">
                                    <input type="text" name="cid" class="form-control" placeholder="Channel ID (-100...)">
                                    <button class="btn btn-primary">Add</button>
                                </form>
                                <div style="max-height: 200px; overflow-y: auto;">
                                    {% for c in chans %}
                                    <div class="d-flex justify-content-between border-bottom border-secondary py-2">
                                        <span class="small">{{ c.channel_id }}</span>
                                        <a href="/admin/del_chan/{{ c._id }}" class="text-danger small">Delete</a>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, style=PREMIUM_STYLE, s=s, post_count=post_count, bot_count=bot_count, bots=bots, chans=chans)

@app.route('/admin/posters')
@login_required
def admin_posters():
    page = request.args.get('page', 1, type=int)
    skip = (page-1) * 16
    total = files_col.count_documents({})
    posters = list(files_col.find().sort("_id", -1).skip(skip).limit(16))
    total_pages = (total // 16) + 1
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">{{ style | safe }}</head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <div class="col-md-2 sidebar">
                    <h4 class="text-white fw-bold mb-4">ADMIN PRO</h4>
                    <a href="/admin">Settings</a>
                    <a href="/admin/posters" class="active">Posters Gallery</a>
                    <a href="/">View Site</a>
                    <a href="/logout" class="text-danger mt-5">Logout</a>
                </div>
                <div class="col-md-10 p-5">
                    <h3 class="fw-bold mb-4 text-primary">Posters Gallery ({{ total }})</h3>
                    <div class="poster-grid">
                        {% for p in posters %}
                        <div class="poster-item">
                            <div class="glass-card p-2">
                                <img src="/f/{{ p.file_id }}" style="height:120px">
                                <div class="d-flex mt-2 gap-1">
                                    <a href="/view/{{ p._id }}" class="btn btn-sm btn-primary flex-grow-1">View</a>
                                    <a href="/admin/del_post/{{ p._id }}" class="btn btn-sm btn-danger">X</a>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                    <div class="mt-5 d-flex justify-content-center gap-2">
                        {% if page > 1 %}<a href="?page={{ page-1 }}" class="btn btn-secondary">Prev</a>{% endif %}
                        <span class="p-2">Page {{ page }} of {{ total_pages }}</span>
                        {% if page < total_pages %}<a href="?page={{ page+1 }}" class="btn btn-secondary">Next</a>{% endif %}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, style=PREMIUM_STYLE, posters=posters, total=total, page=page, total_pages=total_pages)

# --- ADMIN ACTIONS ---
@app.route('/admin/save', methods=['POST'])
@login_required
def admin_save():
    settings_col.update_one({"type": "config"}, {"$set": request.form.to_dict()}, upsert=True)
    return redirect('/admin')

@app.route('/admin/add_bot', methods=['POST'])
@login_required
def admin_add_bot():
    token = request.form.get('token')
    if token:
        bots_col.insert_one({"token": token})
        # Auto Webhook Connect
        requests.get(f"https://api.telegram.org/bot{token}/setWebhook?url={request.host_url}webhook/{token}")
    return redirect('/admin')

@app.route('/admin/del_bot/<id>')
@login_required
def admin_del_bot(id): bots_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin')

@app.route('/admin/add_chan', methods=['POST'])
@login_required
def admin_add_chan():
    cid = request.form.get('cid')
    if cid: channels_col.insert_one({"channel_id": cid})
    return redirect('/admin')

@app.route('/admin/del_chan/<id>')
@login_required
def admin_del_chan(id): channels_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin')

@app.route('/admin/del_post/<id>')
@login_required
def admin_del_post(id):
    p = files_col.find_one({"_id": ObjectId(id)})
    if p: fs.delete(ObjectId(p['file_id']))
    files_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/posters')

# --- BOT WEBHOOK (MULTI-BOT DISPATCHER) ---

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    try:
        bot = telebot.TeleBot(token)
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        
        if update.message:
            msg = update.message
            user = msg.from_user
            
            # --- FORCE JOIN CHECK ---
            if not is_subscribed(bot, user.id):
                kb = types.InlineKeyboardMarkup()
                chans = list(channels_col.find())
                for c in chans:
                    kb.add(types.InlineKeyboardButton("Join Channel", url=f"https://t.me/{c['channel_id'].replace('-100','')}"))
                bot.send_message(msg.chat.id, "❌ আপনি আমাদের চ্যানেলে জয়েন নেই! নিচে দেওয়া চ্যানেলে জয়েন করে আবার ট্রাই করুন।", reply_markup=kb)
                return "OK", 200

            # --- START COMMAND (USER INFO) ---
            if msg.text == "/start":
                # Get Profile Picture
                p_text = f"👋 **স্বাগতম {user.first_name}!**\n\n"
                p_text += f"👤 **Name:** {user.first_name} {user.last_name or ''}\n"
                p_text += f"🆔 **ID:** `{user.id}`\n"
                p_text += f"🔗 **Username:** @{user.username or 'None'}\n\n"
                p_text += "আমাকে যেকোনো পোস্টার পাঠান, আমি সেটির ১৬টি ফরম্যাটের লিঙ্ক দিব।"
                
                try:
                    photos = bot.get_user_profile_photos(user.id)
                    if photos.total_count > 0:
                        bot.send_photo(msg.chat.id, photos.photos[0][-1].file_id, caption=p_text, parse_mode="Markdown")
                    else:
                        bot.send_message(msg.chat.id, p_text, parse_mode="Markdown")
                except:
                    bot.send_message(msg.chat.id, p_text, parse_mode="Markdown")
                return "OK", 200
            
            # --- FILE HANDLING (IMAGE TO LINK) ---
            if msg.content_type in ['photo', 'document']:
                bot.send_chat_action(msg.chat.id, 'upload_document')
                
                # Download File
                if msg.content_type == 'photo':
                    fid = msg.photo[-1].file_id
                else:
                    fid = msg.document.file_id
                
                f_info = bot.get_file(fid)
                content = bot.download_file(f_info.file_path)
                
                # Save to My MongoDB GridFS
                stored_id = fs.put(content, filename=f"tg_{fid}", content_type="image/jpeg")
                
                # Generate Links
                base_url = f"{request.host_url}f/{str(stored_id)}"
                link_map = {fmt: f"{base_url}?format={fmt}" for fmt in FORMATS}
                
                ins_id = files_col.insert_one({
                    "file_id": str(stored_id),
                    "links": link_map,
                    "date": datetime.now(),
                    "type": "bot",
                    "user_id": user.id
                }).inserted_id
                
                bot.reply_to(msg, f"✅ **আপনার পোস্টার রেডি!**\n\n🔗 **ডাউনলোড লিঙ্ক:** {request.host_url}view/{str(ins_id)}", parse_mode="Markdown")

    except Exception as e:
        print(f"Webhook Error: {e}")
        
    return "OK", 200

# --- MAIN RUNNER ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
