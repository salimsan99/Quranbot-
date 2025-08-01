import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, CallbackContext,
    Filters, MessageHandler
)
import sqlite3
import os
from dotenv import load_dotenv

# تحميل التوكن من ملف .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "@quran_voice_1"  # اسم قناتك

# إعداد قاعدة البيانات
conn = sqlite3.connect('quran_voice.db')
c = conn.cursor()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قائمة الشيوخ المتاحة
SHEIKHS = ["نورين محمد صديق", "محمد عثمان حاج"]

# حالة المستخدم لتخزين التقدم
user_state = {}

def is_user_subscribed(user_id, context: CallbackContext):
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطأ في التحقق من الاشتراك: {e}")
        return False

def start(update: Update, context: CallbackContext):
    """بدء المحادثة مع المستخدم"""
    user = update.effective_user
    user_id = user.id
    
    # التحقق من الاشتراك
    if not is_user_subscribed(user_id, context):
        keyboard = [
            [InlineKeyboardButton("اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")]
        ]
        update.message.reply_text(
            "📢 مرحباً بك في بوت القرآن الكريم!\n"
            "⚠️ يجب عليك الاشتراك في قناتنا أولاً لاستخدام البوت:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        return
    
    # إذا كان مشتركاً، نعرض قائمة الشيوخ
    show_sheikhs_menu(update, context)

def show_sheikhs_menu(update: Update, context: CallbackContext):
    """عرض قائمة الشيوخ"""
    buttons = []
    for sheikh in SHEIKHS:
        buttons.append([InlineKeyboardButton(sheikh, callback_data=f"sheikh_{sheikh}")])
    
    # إضافة زر للخطب
    buttons.append([InlineKeyboardButton("الخطب", callback_data="lectures")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        update.callback_query.edit_message_text(
            "👳 اختر الشيخ الذي تريد الاستماع لتلاوته:",
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(
            "👳 اختر الشيخ الذي تريد الاستماع لتلاوته:",
            reply_markup=reply_markup
        )

def get_suras_for_sheikh(sheikh: str, page: int = 0, per_page: int = 10):
    """الحصول على السور للشيخ مع التقسيم إلى صفحات"""
    c.execute("SELECT sura_title FROM audio_files WHERE sheikh=? AND type='quran'", (sheikh,))
    all_suras = [row[0] for row in c.fetchall()]
    
    total_pages = (len(all_suras) // per_page + (1 if len(all_suras) % per_page > 0 else 0)
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_suras = all_suras[start_idx:end_idx]
    
    return page_suras, page, total_pages

def show_suras_page(update: Update, context: CallbackContext, sheikh: str, page: int = 0):
    """عرض صفحة من السور"""
    suras, current_page, total_pages = get_suras_for_sheikh(sheikh, page)
    
    if not suras:
        update.callback_query.answer("لا توجد سور متاحة لهذا الشيخ")
        return
    
    # إنشاء لوحة المفاتيح للسور
    buttons = []
    for sura in suras:
        buttons.append([InlineKeyboardButton(sura, callback_data=f"sura_{sura}")])
    
    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{sheikh}_{current_page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"صفحة {current_page+1}/{total_pages}", callback_data="current_page"))
    
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{sheikh}_{current_page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # زر العودة
    buttons.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_sheikhs")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    update.callback_query.edit_message_text(
        f"📖 اختر سورة من تلاوة الشيخ {sheikh}:",
        reply_markup=reply_markup
    )

def send_audio_file(update: Update, context: CallbackContext, sura: str, sheikh: str):
    """إرسال ملف الصوت للسورة المطلوبة"""
    c.execute("SELECT file_id FROM audio_files WHERE sura_title=? AND sheikh=? AND type='quran'", (sura, sheikh))
    result = c.fetchone()
    
    if result:
        file_id = result[0]
        context.bot.send_audio(
            chat_id=update.callback_query.message.chat_id,
            audio=file_id,
            title=f"سورة {sura} - الشيخ {sheikh}",
            performer="القرآن الكريم"
        )
        # إظهار رسالة توضيحية مع زر العودة
        keyboard = [[InlineKeyboardButton("🔙 العودة للسور", callback_data=f"back_to_suras_{sheikh}")]]
        update.callback_query.message.reply_text(
            "✅ تم إرسال التلاوة بنجاح\n"
            "استمع وارفع صوتك بالقرآن الكريم",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.callback_query.answer("⛔ لم يتم العثور على السورة المطلوبة", show_alert=True)

def button_handler(update: Update, context: CallbackContext):
    """معالجة الأزرار"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # التحقق من الاشتراك أولاً
    if not is_user_subscribed(user_id, context):
        keyboard = [
            [InlineKeyboardButton("اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")]
        ]
        query.edit_message_text(
            "⚠️ يجب عليك الاشتراك في قناتنا أولاً لاستخدام البوت:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        return
    
    # معالجة الأحداث المختلفة
    if data == "check_subscription":
        if is_user_subscribed(user_id, context):
            show_sheikhs_menu(update, context)
        else:
            query.answer("❌ لم تشترك بعد! اشترك ثم اضغط تحقق", show_alert=True)
    
    elif data.startswith("sheikh_"):
        sheikh = data.split("_", 1)[1]
        show_suras_page(update, context, sheikh)
    
    elif data.startswith("page_"):
        _, sheikh, page = data.split("_", 2)
        show_suras_page(update, context, sheikh, int(page))
    
    elif data.startswith("sura_"):
        sura = data.split("_", 1)[1]
        # استرجاع الشيخ من حالة المستخدم أو من الرسالة
        sheikh = user_state.get(user_id, {}).get("current_sheikh")
        if not sheikh:
            # محاولة استخراج من الرسالة
            message_text = query.message.text
            for s in SHEIKHS:
                if s in message_text:
                    sheikh = s
                    break
        
        if sheikh:
            send_audio_file(update, context, sura, sheikh)
        else:
            query.answer("حدث خطأ! يرجى المحاولة مرة أخرى", show_alert=True)
    
    elif data == "lectures":
        show_lectures_menu(update, context)
    
    elif data == "back_to_sheikhs":
        show_sheikhs_menu(update, context)
    
    elif data.startswith("back_to_suras_"):
        sheikh = data.split("_", 3)[3]
        show_suras_page(update, context, sheikh)

def show_lectures_menu(update: Update, context: CallbackContext):
    """عرض قائمة الخطب"""
    c.execute("SELECT DISTINCT sura_title, sheikh FROM audio_files WHERE type='lecture'")
    lectures = c.fetchall()
    
    if not lectures:
        update.callback_query.answer("لا توجد خطب متاحة حالياً")
        return
    
    buttons = []
    for title, sheikh in lectures:
        buttons.append([InlineKeyboardButton(f"{title} - {sheikh}", callback_data=f"lecture_{title}_{sheikh}")])
    
    buttons.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_sheikhs")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    update.callback_query.edit_message_text(
        "📢 اختر خطبة للاستماع:",
        reply_markup=reply_markup
    )

def send_lecture(update: Update, context: CallbackContext, title: str, sheikh: str):
    """إرسال خطبة"""
    c.execute("SELECT file_id FROM audio_files WHERE sura_title=? AND sheikh=? AND type='lecture'", (title, sheikh))
    result = c.fetchone()
    
    if result:
        file_id = result[0]
        context.bot.send_audio(
            chat_id=update.callback_query.message.chat_id,
            audio=file_id,
            title=f"{title} - الشيخ {sheikh}",
            performer="الخطبة"
        )
    else:
        update.callback_query.answer("⛔ لم يتم العثور على الخطبة المطلوبة", show_alert=True)

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء جدول إذا لم يكن موجوداً
    c.execute('''CREATE TABLE IF NOT EXISTS audio_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        sura_title TEXT NOT NULL,
        sheikh TEXT NOT NULL,
        file_id TEXT NOT NULL UNIQUE,
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    
    # بدء البوت
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # إضافة المعالجات
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # معالج للاشتراك في القناة
    dp.add_handler(MessageHandler(Filters.text("✅ تحقق من الاشتراك") | Filters.regex(r'اشترك'), start))
    
    logger.info("بدأ البوت في العمل...")
    updater.start_polling()
    updater.idle()
    conn.close()

if __name__ == "__main__":
    main()
