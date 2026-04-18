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
app.secret_key = "ultimate_premium_poster_pro_v7"

# --- MongoDB Connection ---
MONGO_URI = "mongodb+srv://roxiw19528:roxiw19528@cluster0.vl508y4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['poster_pro_v3']
files_col = db['posters']
settings_col = db['settings']
bots_col = db['bots']
channels_col = db['channels']

FORMATS = ['jpg', 'jpeg', 'png', 'pdf', 'webp', 'svg', 'eps', 'psd', 'ai', 'tiff', 'gif', 'indd', 'bmp', 'raw', 'heic', 'avif']

# --- Helpers ---
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", "admin_pass": "admin123", 
            "cloud_name": "", "api_key": "", "api_secret": "", 
            "ad_popunder": "", "ad_social": "", "ad_top": "", "ad_mid": "", "ad_footer": ""
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

# --- Premium UI Style ---
UI_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap');
    :root { --primary: #6366f1; --accent: #c026d3; --dark-bg: #0f172a; --glass: rgba(255, 255, 255, 0.03); }
    body { background: var(--dark-bg); color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif; overflow-x: hidden; }
    .glass { background: var(--glass); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; transition: 0.3s; }
    .btn-grad { background: linear-gradient(135deg, var(--primary), var(--accent)); border: none; color: white; padding: 12px 28px; border-radius: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .btn-grad:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(99, 102, 241, 0.4); color: white; }
    .form-control { background: rgba(0,0,0,0.2) !important; border: 1px solid #334155 !important; color: white !important; border-radius: 12px; }
    .poster-thumb { border-radius: 18px; width: 100%; height: 220px; object-fit: cover; border: 2px solid rgba(255,255,255,0.05); }
    .ad-placeholder { background: rgba(255,255,255,0.02); border: 1px dashed #444; border-radius: 12px; padding: 10px; text-align: center; margin: 15px 0; }
    .nav-bar { background: rgba(15, 23, 42, 0.9); border-bottom: 1px solid rgba(255,255,255,0.1); position: sticky; top: 0; z-index: 1000; }
</style>
"""

# --- Routes ---

@app.route('/')
def home():
    s = get_config()
    files = list(files_col.find().sort("_id", -1).limit(16))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Poster Cloud - Premium Upload</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        {{ style | safe }}{{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    </head>
    <body>
        <div class="container py-5">
            <div class="text-center mb-5">
                <h1 class="fw-bold display-4">🚀 Poster <span class="text-primary">Cloud</span></h1>
                <p class="text-muted">Convert images to 16+ formats with high-speed links</p>
            </div>
            <div class="row justify-content-center mb-5">
                <div class="col-md-7">
                    <div class="glass p-5 text-center">
                        <form action="/web_upload" method="POST" enctype="multipart/form-data" id="uform">
                            <label for="upfile" style="cursor:pointer;" class="w-100 p-4 border-2 border-dashed border-secondary rounded-4">
                                <i class="fas fa-cloud-upload-alt fa-4x text-primary mb-3"></i>
                                <h3>Click to Upload Image</h3>
                                <p class="small text-muted">Supports all major image formats</p>
                            </label>
                            <input type="file" id="upfile" name="file" style="display:none;" onchange="document.getElementById('uform').submit();">
                        </form>
                    </div>
                </div>
            </div>
            <div class="ad-placeholder">{{ s.ad_top | safe }}</div>
            <h4 class="mb-4 fw-bold">Recent Uploads</h4>
            <div class="row g-4">
                {% for f in files %}
                <div class="col-md-3">
                    <div class="glass p-3 h-100 text-center">
                        <img src="{{ f.url }}" class="poster-thumb mb-3">
                        <a href="/view/{{ f._id }}" class="btn btn-grad w-100 btn-sm">Download Links</a>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="ad-placeholder">{{ s.ad_footer | safe }}</div>
        </div>
    </body>
    </html>
    """, style=UI_STYLE, s=s, files=files)

@app.route('/web_upload', methods=['POST'])
def web_upload():
    try:
        if 'file' not in request.files: return redirect('/')
        file = request.files['file']
        s = get_config()
        if not s['cloud_name']: return "Admin: Please set Cloudinary API Keys in /admin first!", 400
        
        cloudinary.config(cloud_name=s['cloud_name'], api_key=s['api_key'], api_secret=s['api_secret'], secure=True)
        res = cloudinary.uploader.upload(file, resource_type="auto")
        b_url = res['secure_url']
        links = {fmt: f"{b_url.rsplit('.', 1)[0]}.{fmt}" for fmt in FORMATS}
        
        ins = files_col.insert_one({"url": b_url, "links": links, "date": datetime.now()})
        return redirect(url_for('view_file', id=str(ins.inserted_id)))
    except Exception as e: return f"Error: {str(e)}", 500

@app.route('/view/<id>')
def view_file(id):
    f = files_col.find_one({"_id": ObjectId(id)})
    s = get_config()
    if not f: return "Not Found", 404
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Download Poster</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        {{ style | safe }}{{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    </head>
    <body>
        <div class="container py-4 text-center">
            <div class="ad-placeholder">{{ s.ad_top | safe }}</div>
            <div class="glass p-4 mx-auto" style="max-width: 850px;">
                <h3 class="mb-4">Successfully Converted!</h3>
                <img src="{{ file.url }}" class="rounded shadow border border-primary mb-4" style="max-height: 350px;">
                <div class="ad-placeholder">{{ s.ad_mid | safe }}</div>
                <div class="row g-2">
                    {% for fmt, link in file.links.items() %}
                    <div class="col-4 col-md-3"><a href="{{ link }}" target="_blank" class="btn btn-grad w-100 py-2 btn-sm">{{ fmt.upper() }}</a></div>
                    {% endfor %}
                </div>
            </div>
            <div class="ad-placeholder">{{ s.ad_footer | safe }}</div>
        </div>
    </body>
    </html>
    """, style=UI_STYLE, s=s, file=f)

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == get_config()['admin_pass']:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template_string("""
    <body style="background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh; color:white;">
        <div class="glass p-5 text-center" style="width:380px;">
            <h2 class="mb-4">Admin Hub</h2>
            <form method="POST">
                <input type="password" name="password" class="form-control mb-3" placeholder="Access Password">
                <button class="btn btn-grad w-100">Unlock Panel</button>
            </form>
        </div>
    </body>
    """, style=UI_STYLE)

@app.route('/admin')
@login_required
def admin_dashboard():
    s = get_config()
    bot_c = bots_col.count_documents({})
    poster_c = files_col.count_documents({})
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">{{ style | safe }}</head>
    <body>
        <nav class="nav-bar p-3 d-flex justify-content-between container-fluid">
            <span class="fw-bold text-primary">ADMIN PRO PANEL</span>
            <div><a href="/admin" class="text-white me-3 text-decoration-none">Settings</a><a href="/admin/gallery" class="text-white me-3 text-decoration-none">Gallery</a><a href="/logout" class="text-danger text-decoration-none">Logout</a></div>
        </nav>
        <div class="container mt-5">
            <div class="row g-4 mb-5">
                <div class="col-md-6"><div class="glass p-4 text-center"><h5>Total Posters</h5><h2 class="text-primary fw-bold">{{ poster_c }}</h2></div></div>
                <div class="col-md-6"><div class="glass p-4 text-center"><h5>Bots Active</h5><h2 class="text-primary fw-bold">{{ bot_c }}</h2></div></div>
            </div>
            <form action="/save_settings" method="POST" class="glass p-5 row g-3">
                <div class="col-md-3"><label>Admin Pass</label><input type="text" name="admin_pass" class="form-control" value="{{ s.admin_pass }}"></div>
                <div class="col-md-3"><label>Cloud Name</label><input type="text" name="cloud_name" class="form-control" value="{{ s.cloud_name }}"></div>
                <div class="col-md-3"><label>API Key</label><input type="text" name="api_key" class="form-control" value="{{ s.api_key }}"></div>
                <div class="col-md-3"><label>API Secret</label><input type="text" name="api_secret" class="form-control" value="{{ s.api_secret }}"></div>
                <div class="col-md-4"><label>Popunder</label><textarea name="ad_popunder" class="form-control" rows="2">{{ s.ad_popunder }}</textarea></div>
                <div class="col-md-4"><label>Top Ad</label><textarea name="ad_top" class="form-control" rows="2">{{ s.ad_top }}</textarea></div>
                <div class="col-md-4"><label>Mid Ad</label><textarea name="ad_mid" class="form-control" rows="2">{{ s.ad_mid }}</textarea></div>
                <div class="col-12 text-center mt-4"><button class="btn btn-grad px-5">Save All Settings</button></div>
            </form>
            <div class="row mt-4 g-4">
                <div class="col-md-6">
                    <div class="glass p-4">
                        <h5>Connect New Bot</h5>
                        <form action="/add_bot" method="POST"><input type="text" name="token" class="form-control mb-2" placeholder="Bot Token"><button class="btn btn-grad w-100 btn-sm">Add Bot</button></form>
                        <hr>{% for b in bots %}<div class="small d-flex justify-content-between">{{ b.token[:20] }}... <a href="/del_bot/{{ b._id }}" class="text-danger">×</a></div>{% endfor %}
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="glass p-4">
                        <h5>Force Join Channels</h5>
                        <form action="/add_channel" method="POST"><input type="text" name="cid" class="form-control mb-2" placeholder="Chat ID"><button class="btn btn-grad w-100 btn-sm">Add Channel</button></form>
                        <hr>{% for c in chans %}<div class="small d-flex justify-content-between">{{ c.channel_id }} <a href="/del_chan/{{ c._id }}" class="text-danger">×</a></div>{% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, style=UI_STYLE, s=s, bot_c=bot_c, poster_c=poster_c, bots=list(bots_col.find()), chans=list(channels_col.find()))

@app.route('/admin/gallery')
@login_required
def admin_gallery():
    page = request.args.get('page', 1, type=int)
    skip = (page - 1) * 16
    total = files_col.count_documents({})
    files = list(files_col.find().sort("_id", -1).skip(skip).limit(16))
    total_p = (total // 16) + (1 if total % 16 > 0 else 0)
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">{{ style | safe }}</head>
    <body>
        <nav class="nav-bar p-3 d-flex justify-content-between container-fluid"><span class="fw-bold">GALLERY ({{ total }})</span><a href="/admin" class="text-white">Back</a></nav>
        <div class="container mt-4"><div class="row g-4">
            {% for f in files %}
            <div class="col-md-3"><div class="glass p-2 text-center"><img src="{{ f.url }}" class="poster-thumb mb-2">
            <div class="d-flex gap-1"><a href="{{ f.url }}" target="_blank" class="btn btn-dark btn-sm flex-grow-1">Preview</a><a href="/view/{{ f._id }}" class="btn btn-primary btn-sm flex-grow-1">Links</a><a href="/delete/{{ f._id }}" class="btn btn-danger btn-sm">×</a></div></div></div>
            {% endfor %}
        </div>
        <div class="d-flex justify-content-center my-5">
            {% if page > 1 %}<a href="?page={{ page-1 }}" class="btn btn-secondary me-2">Prev</a>{% endif %}
            <span class="p-2">Page {{ page }} of {{ total_p }}</span>
            {% if page < total_p %}<a href="?page={{ page+1 }}" class="btn btn-secondary ms-2">Next</a>{% endif %}
        </div></div>
    </body></html>
    """, style=UI_STYLE, files=files, page=page, total_p=total_p, total=total)

@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    try:
        bot = telebot.TeleBot(token)
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        if update.message:
            msg = update.message
            if not check_join(bot, msg.from_user.id):
                bot.send_message(msg.chat.id, "Please join our channels first!")
                return "OK", 200
            if msg.text == "/start":
                u = msg.from_user
                info = f"👤 **Name:** {u.first_name}\n🆔 **ID:** `{u.id}`\nUsername: @{u.username or 'N/A'}"
                try:
                    photos = bot.get_user_profile_photos(u.id)
                    if photos.total_count > 0: bot.send_photo(msg.chat.id, photos.photos[0][-1].file_id, caption=info, parse_mode="Markdown")
                    else: bot.send_message(msg.chat.id, info, parse_mode="Markdown")
                except: bot.send_message(msg.chat.id, info, parse_mode="Markdown")
            elif msg.content_type in ['photo', 'document']:
                s = get_config()
                cloudinary.config(cloud_name=s['cloud_name'], api_key=s['api_key'], api_secret=s['api_secret'], secure=True)
                f_id = msg.photo[-1].file_id if msg.content_type == 'photo' else msg.document.file_id
                f_content = bot.download_file(bot.get_file(f_id).file_path)
                res = cloudinary.uploader.upload(f_content, resource_type="auto")
                b_url = res['secure_url']
                links = {fmt: f"{b_url.rsplit('.', 1)[0]}.{fmt}" for fmt in FORMATS}
                ins = files_col.insert_one({"url": b_url, "links": links, "date": datetime.now()})
                bot.reply_to(msg, f"✅ Done! View Links Here: {request.host_url}view/{str(ins.inserted_id)}")
    except: pass
    return "OK", 200

# --- Standard Functionality ---
@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    settings_col.update_one({"type": "config"}, {"$set": request.form.to_dict()}, upsert=True)
    return redirect('/admin')

@app.route('/add_bot', methods=['POST'])
@login_required
def add_bot():
    t = request.form.get('token')
    if t:
        bots_col.insert_one({"token": t})
        requests.get(f"https://api.telegram.org/bot{t}/setWebhook?url={request.host_url}webhook/{t}")
    return redirect('/admin')

@app.route('/del_bot/<id>')
@login_required
def del_bot(id):
    bots_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin')

@app.route('/add_channel', methods=['POST'])
@login_required
def add_channel():
    cid = request.form.get('cid')
    if cid: channels_col.insert_one({"channel_id": cid}); return redirect('/admin')

@app.route('/del_chan/<id>')
@login_required
def del_chan(id):
    channels_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin')

@app.route('/delete/<id>')
@login_required
def delete_file(id):
    files_col.delete_one({"_id": ObjectId(id)}); return redirect('/admin/gallery')

@app.route('/logout')
def logout():
    session.pop('logged_in', None); return redirect('/admin/login')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
