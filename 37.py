import os
import random
import sqlite3
import telebot
import yt_dlp
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN ="8949158355:AAFSD2VnL-55ELMcnAbcrP-BcCIVcaXUebk"
OWNER_ID = 1443724632  # آيدي المالك الخاص بك

bot = telebot.TeleBot(TOKEN)

if not os.path.exists('downloads'):
    os.makedirs('downloads')

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            is_banned INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS captcha (
            user_id INTEGER PRIMARY KEY,
            code TEXT,
            step TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    return conn, conn.cursor()

def is_user_banned(user_id):
    conn, cursor = get_db()
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res and res[0] == 1

def get_setting(key):
    conn, cursor = get_db()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def set_setting(key, value):
    conn, cursor = get_db()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

# --- لوحة الأزرار الدائمة للمالك ---
def get_owner_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("تحديث الصورة المتحركة"),
        KeyboardButton("تحديث ملف الكوكيز"),
        KeyboardButton("فحص حالة الكوكيز"),
        KeyboardButton("حذف ملف الكوكيز"),
        KeyboardButton("عدد المستخدمين"),
        KeyboardButton("حظر مستخدم"),
        KeyboardButton("إلغاء حظر مستخدم"),
        KeyboardButton("إذاعة للجميع")
    )
    return markup

def smart_reply(message, text, parse_mode=None):
    user_id = message.from_user.id
    if user_id == OWNER_ID:
        return bot.reply_to(message, text, parse_mode=parse_mode, reply_markup=get_owner_keyboard())
    else:
        return bot.reply_to(message, text, parse_mode=parse_mode)

def smart_send(chat_id, user_id, text, parse_mode=None):
    if user_id == OWNER_ID:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=get_owner_keyboard())
    else:
        return bot.send_message(chat_id, text, parse_mode=parse_mode)

# --- إعدادات التحميل المحسنة (مهلة 5 دقائق + تفكيك ودمج وترميز قوي لتجاوز القيود) ---
def get_ydl_opts(chat_id, is_youtube):
    opts = {
        'outtmpl': f'downloads/{chat_id}_%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'retries': 50,                # زيادة عدد محاولات إعادة الاتصال للمقاطع الكبيرة
        'fragment_retries': 50,       # زيادة محاولات جلب الأجزاء المتقطعة (مثل بنتريست ويوتيوب)
        'socket_timeout': 300,        # رفع المهلة إلى 5 دقائق (300 ثانية)
        'geo_bypass': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_warnings': True,
        'prefer_ffmpeg': True,        # الاعتماد على محرك التفكيك والدمج ffmpeg
        'continuedl': True,           # السماح بإكمال التحميل في حال حدوث قطع بالاتصال
    }
    
    if is_youtube:
        if os.path.exists('cookies.txt'):
            opts['cookiefile'] = 'cookies.txt'
        opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
    else:
        # إعدادات متطورة لبنتريست وباقي المنصات لضمان تفكيك ودمج أي صيغة معقدة
        opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        
    return opts

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "لا يوجد"
    full_name = message.from_user.full_name or "مستخدم"

    if is_user_banned(user_id):
        smart_reply(message, "❌ تم حظرك من استخدام هذا البوت.")
        return

    conn, cursor = get_db()
    cursor.execute('SELECT verified FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)', 
                       (user_id, username, full_name))
        conn.commit()

    if row and row[0] == 1:
        conn.close()
        send_main_menu(message)
        return

    captcha_code = str(random.randint(1000, 9999))
    cursor.execute('INSERT OR REPLACE INTO captcha (user_id, code, step) VALUES (?, ?, ?)', 
                   (user_id, captcha_code, 'waiting_captcha'))
    conn.commit()
    conn.close()

    gif_file_id = get_setting('welcome_gif')
    caption_text = "تمت برمجة هذا البوت بواسطة #حربي"
    
    try:
        if gif_file_id:
            bot.send_animation(message.chat.id, gif_file_id, caption=caption_text)
        else:
            bot.send_message(message.chat.id, caption_text)
    except Exception:
        bot.send_message(message.chat.id, caption_text)

    smart_send(message.chat.id, user_id, f"( قم بحل الكابتشا ) ارسل الارقام الظاهرة امامك\n\n`{captcha_code}`", parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'animation', 'document'])
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # --- معالجة حفظ ملف الكوكيز الجديد ---
    if message.content_type == 'document' and user_id == OWNER_ID:
        conn, cursor = get_db()
        cursor.execute('SELECT step FROM captcha WHERE user_id = ?', (user_id,))
        step_res = cursor.fetchone()
        conn.close()

        if step_res and step_res[0] == 'waiting_cookies':
            if message.document.file_name == 'cookies.txt':
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                with open('cookies.txt', 'wb') as new_file:
                    new_file.write(downloaded_file)
                
                conn, cursor = get_db()
                cursor.execute('DELETE FROM captcha WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
                
                smart_reply(message, "✅ تم تحديث ملف `cookies.txt` بنجاح وأصبح السكربت يستخدمه الآن!")
            else:
                smart_reply(message, "❌ خطأ: يجب أن يكون اسم الملف `cookies.txt` حصراً.")
            return

    # --- معالجة حفظ الصورة المتحركة للترحيب (GIF) ---
    if user_id == OWNER_ID:
        conn, cursor = get_db()
        cursor.execute('SELECT step FROM captcha WHERE user_id = ?', (user_id,))
        step_res = cursor.fetchone()
        conn.close()

        if step_res and step_res[0] == 'waiting_gif' and message.content_type == 'animation':
            file_id = message.animation.file_id
            set_setting('welcome_gif', file_id)
            
            conn, cursor = get_db()
            cursor.execute('DELETE FROM captcha WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            
            smart_reply(message, "✅ تم حفظ الصورة المتحركة بنجاح وتحديث رسالة الترحيب مع (#حربي)!")
            return

    if message.content_type != 'text':
        return

    if is_user_banned(user_id):
        return

    conn, cursor = get_db()

    # التحقق من الكابتشا
    cursor.execute('SELECT code, step FROM captcha WHERE user_id = ?', (user_id,))
    cap_data = cursor.fetchone()
    if cap_data and cap_data[1] == 'waiting_captcha':
        real_code = cap_data[0]
        if text == real_code:
            cursor.execute('UPDATE users SET verified = 1 WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM captcha WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            smart_reply(message, "✅ تم التحقق بنجاح!")
            send_main_menu(message)
            return
        else:
            conn.close()
            smart_reply(message, "❌ الكود غير صحيح. الرجاء إعادة إرسال الأربعة أرقام بدقة:")
            return

    cursor.execute('SELECT step FROM captcha WHERE user_id = ?', (user_id,))
    admin_step = cursor.fetchone()
    conn.close()

    if user_id == OWNER_ID and admin_step:
        step = admin_step[0]
        conn, cursor = get_db()
        cursor.execute('DELETE FROM captcha WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

        if step == 'waiting_ban':
            target = text.replace('@', '')
            conn, cursor = get_db()
            if target.isdigit():
                cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (int(target),))
            else:
                cursor.execute('UPDATE users SET is_banned = 1 WHERE username = ?', (target,))
            conn.commit()
            conn.close()
            smart_reply(message, f"🚫 تم حظر المستخدم: {target} بنجاح.")
            return

        elif step == 'waiting_unban':
            target = text.replace('@', '')
            conn, cursor = get_db()
            if target.isdigit():
                cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (int(target),))
            else:
                cursor.execute('UPDATE users SET is_banned = 0 WHERE username = ?', (target,))
            conn.commit()
            conn.close()
            smart_reply(message, f"✅ تم إلغاء حظر المستخدم: {target} بنجاح.")
            return

        elif step == 'waiting_broadcast':
            conn, cursor = get_db()
            cursor.execute('SELECT user_id FROM users')
            all_users = cursor.fetchall()
            conn.close()
            
            sent_count = 0
            for u in all_users:
                try:
                    bot.send_message(u[0], f"📢 **إشعار من الإدارة:**\n\n{text}", parse_mode="Markdown")
                    sent_count += 1
                except Exception:
                    pass
            smart_reply(message, f"📢 تم إرسال الإذاعة بنجاح إلى {sent_count} مستخدم.")
            return

    # --- أوامر أزرار المالك ---
    if user_id == OWNER_ID:
        if text == "تحديث الصورة المتحركة":
            conn, cursor = get_db()
            cursor.execute('INSERT OR REPLACE INTO captcha (user_id, code, step) VALUES (?, ?, ?)', (user_id, '', 'waiting_gif'))
            conn.commit()
            conn.close()
            smart_reply(message, "📸 أرسل الآن الصورة المتحركة (GIF) ليتم حفظها وعرضها مع رسالة (#حربي):")
            return

        elif text == "تحديث ملف الكوكيز":
            conn, cursor = get_db()
            cursor.execute('INSERT OR REPLACE INTO captcha (user_id, code, step) VALUES (?, ?, ?)', (user_id, '', 'waiting_cookies'))
            conn.commit()
            conn.close()
            smart_reply(message, "📂 أرسل الآن ملف `cookies.txt` ليتم تحديثه في السكربت:")
            return

        elif text == "فحص حالة الكوكيز":
            if not os.path.exists('cookies.txt'):
                smart_reply(message, "⚠️ ملف الكوكيز غير موجود في مسار البوت.")
            else:
                smart_reply(message, "🔍 جاري فحص ملف الكوكيز، انتظر قليلاً...")
                try:
                    with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': 'cookies.txt'}) as ydl:
                        ydl.extract_info("https://www.youtube.com/watch?v=BaW_jenozKc", download=False)
                    smart_reply(message, "✅ ملف الكوكيز يعمل بشكل صحيح ونشط!")
                except Exception as e:
                    smart_reply(message, f"❌ الكوكيز منتهي أو غير صالح:\n{str(e)}")
            return

        elif text == "حذف ملف الكوكيز":
            if os.path.exists('cookies.txt'):
                os.remove('cookies.txt')
                smart_reply(message, "🗑️ تم حذف ملف الكوكيز بنجاح.")
            else:
                smart_reply(message, "⚠️ لا يوجد ملف كوكيز ليتم حذفه.")
            return

        elif text == "عدد المستخدمين":
            conn, cursor = get_db()
            cursor.execute('SELECT user_id, username, full_name FROM users')
            users_list = cursor.fetchall()
            conn.close()
            
            count = len(users_list)
            details = f"📊 **إجمالي عدد المستخدمين:** {count}\n\n"
            for idx, u in enumerate(users_list, 1):
                details += f"{idx}. الاسم: {u[2]} | المعرف: @{u[1]} | الآيدي: `{u[0]}`\n"
            
            if len(details) > 4000:
                details = details[:4000] + "\n... (القائمة طويلة جداً)"
            
            smart_reply(message, details, parse_mode="Markdown")
            return

        elif text == "حظر مستخدم":
            conn, cursor = get_db()
            cursor.execute('INSERT OR REPLACE INTO captcha (user_id, code, step) VALUES (?, ?, ?)', (user_id, '', 'waiting_ban'))
            conn.commit()
            conn.close()
            smart_reply(message, "👤 أرسل الآن آيدي (ID) المستخدم أو معرفه (@username) لحظره:")
            return

        elif text == "إلغاء حظر مستخدم":
            conn, cursor = get_db()
            cursor.execute('INSERT OR REPLACE INTO captcha (user_id, code, step) VALUES (?, ?, ?)', (user_id, '', 'waiting_unban'))
            conn.commit()
            conn.close()
            smart_reply(message, "👤 أرسل الآن آيدي (ID) المستخدم أو معرفه (@username) لإلغاء حظره:")
            return

        elif text == "إذاعة للجميع":
            conn, cursor = get_db()
            cursor.execute('INSERT OR REPLACE INTO captcha (user_id, code, step) VALUES (?, ?, ?)', (user_id, '', 'waiting_broadcast'))
            conn.commit()
            conn.close()
            smart_reply(message, "📢 أرسل الآن نص الإذاعة ليتم إرساله لجميع المستخدمين:")
            return

    # التحقق من أن المستخدم مفعل
    conn, cursor = get_db()
    cursor.execute('SELECT verified FROM users WHERE user_id = ?', (user_id,))
    v_res = cursor.fetchone()
    conn.close()
    if not v_res or v_res[0] == 0:
        smart_reply(message, "الرجاء إرسال /start أولاً لإكمال التحقق.")
        return

    # --- معالجة تحميل الروابط ---
    if text.startswith('http'):
        is_yt = "youtube.com" in text or "youtu.be" in text
        msg = bot.reply_to(message, "⚡ جاري التحميل والمعالجة، قد يستغرق الأمر وقتاً للمقاطع الكبيرة...")
        chat_id = message.chat.id
        
        try:
            with yt_dlp.YoutubeDL(get_ydl_opts(chat_id, is_yt)) as ydl:
                info = ydl.extract_info(text, download=True)
                video_file = ydl.prepare_filename(info)

            if not video_file.endswith('.mp4'):
                base_ext = video_file.rsplit('.', 1)[0]
                new_video_file = base_ext + '.mp4'
                if os.path.exists(video_file):
                    os.rename(video_file, new_video_file)
                    video_file = new_video_file

            # 1. إرسال الفيديو مع التأكد من وجوده
            with open(video_file, 'rb') as f_vid:
                bot.send_video(chat_id, f_vid, caption="✅ تم التحميل بنجاح!")

            # 2. محاولة إرسال الملف الصوتي
            try:
                with open(video_file, 'rb') as f_aud:
                    bot.send_audio(chat_id, f_aud, title="Media Audio", caption="🎵 الملف الصوتي:")
            except Exception:
                pass

            bot.delete_message(chat_id, msg.message_id)
            if os.path.exists(video_file):
                os.remove(video_file)

        except Exception as e:
            try:
                bot.delete_message(chat_id, msg.message_id)
            except:
                pass
            smart_reply(message, f"❌ حدث خطأ أثناء المعالجة أو أن الملف كبير جداً:\n{str(e)}")

def send_main_menu(message):
    user_id = message.from_user.id
    welcome_text = "أهلاً بك! ❤️ أرسل رابط (يوتيوب، تيك توك، سناب شات، بنتريست، فيسبوك، أنستقرام) ليتم تحميله.."
    if user_id == OWNER_ID:
        welcome_text += "\n\n👑 **أهلاً بك أيها المالك، الأزرار مفعلة دائماً.**"
        bot.send_message(message.chat.id, welcome_text, reply_markup=get_owner_keyboard())
    else:
        bot.send_message(message.chat.id, welcome_text)

print("🚀 البوت يعمل بكفاءة تامة...")
bot.infinity_polling(skip_pending=True)
