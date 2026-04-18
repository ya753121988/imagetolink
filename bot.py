import os
import io
import requests
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, send_file
from pymongo import MongoClient
import gridfs
import telebot
from telebot import types
from datetime import datetime
from bson.objectid import ObjectId
import functools

app = Flask(__name__)
app.secret_key = "ultimate_premium_poster_pro_v10_private"

# --- MongoDB Connection (User Provided) ---
MONGO_URI = "mongodb+srv://roxiw19528:roxiw19528@cluster0.vl508y4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['poster_pro_v10_db']
fs = gridfs.GridFS(db)

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
            "type": "config", "admin_pass": "admin123", 
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

# --- Premium Glass UI CSS ---
UI_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    :root { --primary: #6366f1; --accent: #c026d3; --dark: #0f172a; --glass: rgba(255, 255, 255, 0.05); }
    body { background: var(--dark); color: #f1f5f9; font-family: 'Inter', sans-serif; margin: 0; overflow-x: hidden; }
    .glass { background: var(--glass); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; transition: 0.3s; }
    .btn-premium { background: linear-gradient(135deg, var(--primary), var(--accent)); border: none; color: white; border-radius: 12px; font-weight: 700; transition: 0.3s; padding: 12px 25px; }
    .btn-premium:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(99, 102, 241, 0.4); color: white; }
    .nav-bar { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.1); position: sticky; top: 0; z-index: 1000; }
    .poster-img { width: 100%; height: 200px; object-fit: cover; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1); }
    .ad-slot { background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px dashed #444; min-height: 90px; display: flex; align-items: center; justify-content: center; margin: 15px 0; }
    .form-control { background: rgba(0,0,0,0.2) !important; color: white !important; border: 1px solid #334155 !important; }
    .table-dark { background: transparent !important; }
</style>
"""

# --- Serve Files (Own API Link) ---
@app.route('/f/<file_id>')
def serve_file(file_id):
    try:
        file_data = fs.get(ObjectId(file_id))
        return send_file(io.BytesIO(file_data.read()), mimetype=file_data.content_type)
    except: return "File Not Found", 404

# --- User Home Page ---
@app.route('/')
def home():
    s = get_config()
    files = list(files_col.find().sort("_id", -1).limit(16))
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Poster Hub - Private Hosting</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        {{ style | safe }}{{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    </head>
    <body>
        <div class="nav-bar p-3"><div class="container d-flex justify-content-between align-items-center">
        <span class="fw-bold text-primary">🚀 POSTER ENGINE</span>
        <a href="/login" class="text-white text-decoration-none small">Admin Access</a></div></div>
        <div class="container py-5 text-center">
            <h1 class="fw-bold mb-3">Upload & Host <span class="text-primary">Private</span></h1>
            <p class="text-secondary mb-5">Upload your posters directly to our MongoDB Cloud and get 16+ links.</p>
            <div class="row justify-content-center mb-5">
                <div class="col-md-7">
                    <div class="glass p-5">
                        <form action="/web_upload" method="POST" enctype="multipart/form-data" id="upForm">
                            <label for="file" style="cursor:pointer;" class="w-100 p-4 border-2 border-dashed border-secondary rounded-4">
                                <i class="fas fa-image fa-4x text-primary mb-3"></i>
                                <h4>Select Poster to Generate Links</h4>
                            </label>
                            <input type="file" id="file" name="file" style="display:none;" onchange="document.getElementById('upForm').submit();" accept="image/*">
                        </form>
                    </div>
                </div>
            </div>
            <div class="ad-slot">{{ s.ad_top | safe }}</div>
            <h4 class="text-start fw-bold mb-4">Latest Public Feed</h4>
            <div class="row g-4">
                {% for f in files %}
                <div class="col-md-3 col-6">
                    <div class="glass p-2">
                        <img src="/f/{{ f.file_id }}" class="poster-img mb-2">
                        <a href="/view/{{ f._id }}" class="btn btn-premium w-100 btn-sm">Get 16 Links</a>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="ad-slot">{{ s.ad_footer | safe }}</div>
        </div>
    </body>
    </html>
    """, style=UI_STYLE, s=s, files=files)

# --- Web Upload ---
@app.route('/web_upload', methods=['POST'])
def web_upload():
    if 'file' not in request.files: return redirect('/')
    file = request.files['file']
    if file.filename == '': return redirect('/')
    file_id = fs.put(file.read(), filename=file.filename, content_type=file.content_type)
    base_url = f"{request.host_url}f/{str(file_id)}"
    links = {fmt: f"{base_url}?format={fmt}" for fmt in FORMATS}
    ins_id = files_col.insert_one({"file_id": str(file_id), "links": links, "date": datetime.now()}).inserted_id
    return redirect(url_for('view_file', id=str(ins_id)))

# --- View Poster Page ---
@app.route('/view/<id>')
def view_file(id):
    f = files_col.find_one({"_id": ObjectId(id)})
    s = get_config()
    if not f: return "File Not Found", 404
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Download Poster - {{ id }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        {{ style | safe }}{{ s.ad_social | safe }}{{ s.ad_popunder | safe }}
    </head>
    <body class="py-4">
        <div class="container text-center">
            <div class="ad-slot">{{ s.ad_top | safe }}</div>
            <div class="glass p-4 mx-auto shadow-lg" style="max-width: 800px;">
                <h3 class="fw-bold mb-4">Poster Ready!</h3>
                <img src="/f/{{ f.file_id }}" class="rounded shadow mb-4" style="max-height: 350px; border: 3px solid var(--primary);">
                <div class="ad-slot">{{ s.ad_mid | safe }}</div>
                <div class="row g-2">
                    {% for fmt, link in f.links.items() %}
                    <div class="col-4 col-md-3"><a href="{{ link }}" target="_blank" class="btn btn-premium w-100 py-2 btn-sm">{{ fmt.upper() }}</a></div>
                    {% endfor %}
                </div>
            </div>
            <div class="ad-slot">{{ s.ad_footer | safe }}</div>
        </div>
    </body>
    </html>
    """, style=UI_STYLE, s=s, f=f)

# --- Admin Section ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == get_config()['admin_pass']:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template_string("""
    <body style="background:#0f172a; display:flex; align-items:center; justify-content:center; height:100vh;">
        <div class="glass p-5 text-center" style="width:380px;">
            <h2 style="color:white;" class="mb-4 fw-bold">Admin Portal</h2>
            <form method="POST">
                <input type="password" name="password" class="form-control mb-3" placeholder="Enter Admin Pass">
                <button class="btn btn-premium w-100">Unlock Panel</button>
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
    <html lang="en">
    <head><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">{{ style | safe }}</head>
    <body>
        <nav class="nav-bar p-3 d-flex justify-content-between container-fluid"><span class="fw-bold">ADMIN PRO (GridFS)</span><div><a href="/admin" class="text-white me-3">Settings</a><a href="/admin/gallery" class="text-white me-3">Gallery</a><a href="/logout" class="text-danger">Logout</a></div></nav>
        <div class="container mt-4">
            <div class="row g-3 text-center mb-4">
                <div class="col-md-6"><div class="glass p-4"><h6>Total Files</h6><h2 class="text-primary fw-bold">{{ poster_c }}</h2></div></div>
                <div class="col-md-6"><div class="glass p-4"><h6>Active Bots</h6><h2 class="text-primary fw-bold">{{ bot_c }}</h2></div></div>
            </div>
            <form action="/save_settings" method="POST" class="glass p-4 row g-3">
                <div class="col-md-6"><label>Admin Password</label><input type="text" name="admin_pass" class="form-control" value="{{ s.admin_pass }}"></div>
                <div class="col-md-6"><label>Popunder Code</label><textarea name="ad_popunder" class="form-control" rows="1">{{ s.ad_popunder }}</textarea></div>
                <div class="col-md-4"><label>Top Banner</label><textarea name="ad_top" class="form-control" rows="1">{{ s.ad_top }}</textarea></div>
                <div class="col-md-4"><label>Middle Banner</label><textarea name="ad_mid" class="form-control" rows="1">{{ s.ad_mid }}</textarea></div>
                <div class="col-md-4"><label>Footer Banner</label><textarea name="ad_footer" class="form-control" rows="1">{{ s.ad_footer }}</textarea></div>
                <div class="col-12"><button class="btn btn-premium w-100">Save All System Configuration</button></div>
            </form>
            <div class="row g-3 mt-1">
                <div class="col-md-6"><div class="glass p-4"><h6>Bots</h6><form action="/add_bot" method="POST" class="input-group mb-2"><input type="text" name="token" class="form-control" placeholder="Token"><button class="btn btn-primary">Add</button></form>
                {% for b in bots %}<div class="small d-flex justify-content-between p-1 border-bottom border-secondary">{{ b.token[:20] }}... <a href="/del_bot/{{ b._id }}" class="text-danger">×</a></div>{% endfor %}</div></div>
                <div class="col-md-6"><div class="glass p-4"><h6>Channels</h6><form action="/add_channel" method="POST" class="input-group mb-2"><input type="text" name="cid" class="form-control" placeholder="-100..."><button class="btn btn-dark">Add</button></form>
                {% for c in chans %}<div class="small d-flex justify-content-between p-1 border-bottom border-secondary">{{ c.channel_id }} <a href="/del_chan/{{ c._id }}" class="text-danger">×</a></div>{% endfor %}</div></div>
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
        <div class="container mt-4"><div class="row g-3">
            {% for f in files %}
            <div class="col-md-3 col-6"><div class="glass p-2 text-center"><img src="/f/{{ f.file_id }}" class="poster-img mb-2">
            <div class="d-flex gap-1"><a href="/view/{{ f._id }}" class="btn btn-primary btn-sm flex-grow-1">Links</a><a href="/delete/{{ f._id }}" class="btn btn-danger btn-sm">Delete</a></div></div></div>
            {% endfor %}
        </div>
        <div class="d-flex justify-content-center my-5">{% if page > 1 %}<a href="?page={{ page-1 }}" class="btn btn-secondary me-2">Prev</a>{% endif %}<span class="p-2">Page {{ page }} of {{ total_p }}</span>{% if page < total_p %}<a href="?page={{ page+1 }}" class="btn btn-secondary ms-2">Next</a>{% endif %}</div></div>
    </body></html>
    """, style=UI_STYLE, files=files, page=page, total_p=total_p, total=total)

# --- Multi-Bot Logic ---
@app.route('/webhook/<token>', methods=['POST'])
def webhook(token):
    try:
        bot = telebot.TeleBot(token)
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        if update.message:
            msg = update.message
            user = msg.from_user
            if not check_join(bot, user.id):
                markup = types.InlineKeyboardMarkup()
                for ch in list(channels_col.find()):
                    markup.add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{ch['channel_id'].replace('-100','')}"))
                bot.send_message(msg.chat.id, "🛑 আপনি জয়েন নেই! নিচে দেওয়া চ্যানেলে জয়েন করে আবার ট্রাই করুন।", reply_markup=markup)
                return "OK", 200

            if msg.text == "/start":
                info = f"👋 Welcome **{user.first_name}**!\n🆔 ID: `{user.id}`\nআমাকে কোনো ইমেজ পাঠান আমি সরাসরি লিঙ্ক দিব।"
                try:
                    photos = bot.get_user_profile_photos(user.id)
                    if photos.total_count > 0: bot.send_photo(msg.chat.id, photos.photos[0][-1].file_id, caption=info, parse_mode="Markdown")
                    else: bot.send_message(msg.chat.id, info, parse_mode="Markdown")
                except: bot.send_message(msg.chat.id, info, parse_mode="Markdown")
            
            elif msg.content_type in ['photo', 'document']:
                bot.send_chat_action(msg.chat.id, 'upload_document')
                f_id = msg.photo[-1].file_id if msg.content_type == 'photo' else msg.document.file_id
                f_info = bot.get_file(f_id)
                f_content = bot.download_file(f_info.file_path)
                stored_id = fs.put(f_content, filename="poster", content_type="image/jpeg")
                b_url = f"{request.host_url}f/{str(stored_id)}"
                links = {fmt: f"{b_url}?fmt={fmt}" for fmt in FORMATS}
                ins = files_col.insert_one({"file_id": str(stored_id), "links": links, "date": datetime.now()})
                bot.reply_to(msg, f"✅ Poster Uploaded to My Server!\n🔗 Download Links: {request.host_url}view/{str(ins.inserted_id)}")
    except: pass
    return "OK", 200

# --- Standard Actions ---
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
    f = files_col.find_one({"_id": ObjectId(id)})
    if f: fs.delete(ObjectId(f['file_id']))
    files_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin/gallery')

@app.route('/logout')
def logout(): session.pop('logged_in', None); return redirect('/login')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
