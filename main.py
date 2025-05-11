# 🌟 استيراد المكتبات اللازمة
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    JobQueue
)
import logging
import nest_asyncio
import asyncio
from datetime import datetime, timedelta
import pytz
from tabulate import tabulate
import json
import os

# 🔄 تفعيل nest_asyncio للسماح بتشغيل event loop داخل بيئات Jupyter/Colab
nest_asyncio.apply()

# 🔑 توكن البوت (يجب أن يكون سرياً في التطبيقات الحقيقية)
TOKEN = "7563226990:AAFg2E5-f6EcVEjBK7ph5w8Q064P4daZlj0"

# 📝 إعداد تسجيل الأخطاء (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🗃️ حالات المحادثة
ADD_NUMBER, DELETE_NUMBER, SCHEDULE_HOUR, SCHEDULE_AMPM = range(4)

# ⏰ تحديد المنطقة الزمنية لليمن
YEMEN_TZ = pytz.timezone('Asia/Aden')

# 💾 تحميل الأرقام المحفوظة من ملف JSON (كل مستخدم له أرقامه الخاصة)
def load_saved_numbers():
    if os.path.exists(SAVED_NUMBERS_FILE):
        try:
            with open(SAVED_NUMBERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # التأكد من أن البيانات مهيأة بشكل صحيح
            if not isinstance(data, dict):
                return {}
            return data
        except Exception as e:
            logger.error(f"خطأ في تحميل الأرقام المحفوظة: {e}")
            return {}
    return {}

# 💾 تحميل الأوقات المجدولة من ملف JSON
def load_scheduled_times():
    if os.path.exists(SCHEDULED_TIMES_FILE):
        try:
            with open(SCHEDULED_TIMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"خطأ في تحميل الأوقات المجدولة: {e}")
            return {}
    return {}

# 💾 حفظ الأرقام المحفوظة في ملف JSON
def save_numbers_to_file(numbers):
    try:
        with open(SAVED_NUMBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(numbers, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ في حفظ الأرقام المحفوظة: {e}")

# 💾 حفظ الأوقات المجدولة في ملف JSON
def save_scheduled_times(times):
    try:
        with open(SCHEDULED_TIMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(times, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ في حفظ الأوقات المجدولة: {e}")

# 💾 تهيئة تخزين الأرقام المحفوظة والأوقات المجدولة
SAVED_NUMBERS_FILE = "saved_numbers.json"
SCHEDULED_TIMES_FILE = "scheduled_times.json"
saved_numbers = load_saved_numbers()
scheduled_times = load_scheduled_times() if os.path.exists(SCHEDULED_TIMES_FILE) else {}
scheduled_jobs = {}

# 🌐 إعداد متصفح Chrome
def setup_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return chrome_options

# 🔍 دالة لجلب معلومات الرصيد
def get_adsl_info(phone_number):
    try:
        # 🚀 تشغيل المتصفح
        driver = webdriver.Chrome(options=setup_chrome_options())
        driver.get("http://adsl-yemen.com/adsl4.php")
        # 📱 إدخال رقم الهاتف
        phone_input = driver.find_element(By.ID, "mobileInputADSL")
        phone_input.send_keys(phone_number)
        phone_input.send_keys(Keys.ENTER)
        # ⏳ انتظار تحميل النتائج
        time.sleep(5)
        # 📊 استخراج البيانات
        current_balance = driver.find_element(By.XPATH,
                                             "//div[contains(text(), 'الرصيد الحالي')]/following-sibling::div").text
        package_value = driver.find_element(By.XPATH,
                                           "//div[contains(text(), 'قيمة الباقة')]/following-sibling::div").text
        expiry_date = driver.find_element(By.XPATH,
                                        "//div[contains(text(), 'تاريخ الانتهاء')]/following-sibling::div").text
        driver.quit()  # 🛑 إغلاق المتصفح
        return {
            'current_balance': current_balance,
            'package_value': package_value,
            'expiry_date': expiry_date,
            'timestamp': datetime.now(YEMEN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"حدث خطأ أثناء استعلام الرصيد: {e}")
        return None

# 📨 دالة لإرسال نتائج الاستعلام
async def send_balance_info(update, phone_number, info):
    if info:
        response = (
            f"📊 *نتائج استعلام رصيد ADSL*\n"
            f"══════════════════════════\n"
            f"📱 *الرقم:* `{phone_number}`\n"
            f"⏰ *وقت الاستعلام:* {info['timestamp']}\n"
            f"💵 *الرصيد الحالي:* `{info['current_balance']}`\n"
            f"💰 *قيمة الباقة:* `{info['package_value']}`\n"
            f"📅 *تاريخ الانتهاء:* `{info['expiry_date']}`\n"
            f"✨ يمكنك إضافة هذا الرقم إلى المحفوظات للاستعلام عنه لاحقاً"
        )
    else:
        response = (
            "⚠️ *عذراً، تعذر الحصول على معلومات الرصيد*\n"
            "══════════════════════════\n"
            "🛑 *الأسباب المحتملة:*\n"
            "• الرقم غير مسجل في خدمة ADSL\n"
            "• وجود مشكلة تقنية مؤقتة\n"
            "• خطأ في الاتصال بالخادم\n"
            "🔍 يرجى التأكد من الرقم والمحاولة لاحقاً"
        )
    if isinstance(update, Update):
        await update.message.reply_text(response, parse_mode='Markdown')
    else:
        await update.reply_text(response, parse_mode='Markdown')

# 🎉 أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إرسال رسالة ترحيبية احترافية مع قائمة الأزرار"""
    user = update.effective_user
    # 🌈 رسالة ترحيبية شاملة
    welcome_message = (
        f"✨ *مرحباً بك {user.first_name} في بوت استعلام رصيد ADSL اليمن* ✨\n"
        "🚀 *خدمات البوت المتكاملة:*\n"
        "▫️ استعلام فوري عن رصيد أي خط ADSL\n"
        "▫️ إدارة الأرقام المحفوظة بسهولة\n"
        "▫️ جدولة استعلامات تلقائية يومية\n"
        "▫️ عرض التقارير المفصلة\n"
        "📌 *كيفية الاستخدام:*\n"
        "▪️ أرسل رقم الهاتف مباشرة للاستعلام الفوري\n"
        "▪️ أو استخدم القائمة أدناه للوصول إلى جميع الميزات\n"
        "🔘 *الرجاء اختيار أحد الخيارات التالية:*"
    )
    keyboard = [
        [InlineKeyboardButton("➕ إضافة رقم جديد", callback_data='add_number'),
         InlineKeyboardButton("🗂️ عرض الأرقام", callback_data='show_numbers')],
        [InlineKeyboardButton("🔍 استعلام الأرقام", callback_data='query_numbers'),
         InlineKeyboardButton("🗑️ إدارة الأرقام", callback_data='manage_numbers')],
        [InlineKeyboardButton("⏰ جدولة تلقائية", callback_data='schedule_query'),
         InlineKeyboardButton("ℹ️ المساعدة", callback_data='help')],
        [InlineKeyboardButton("🔄 تحديث البوت", callback_data='refresh')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # إنشاء مجلد للمستخدم إذا لم يكن موجوداً
    chat_id = str(update.effective_chat.id)
    if chat_id not in saved_numbers:
        saved_numbers[chat_id] = {}
    
    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

# 📩 معالجة الرسائل النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة طلبات الاستعلام الفوري"""
    phone_number = update.message.text.strip()
    # 🔍 التحقق من صحة الرقم
    if not phone_number.isdigit() or len(phone_number) != 8:
        await update.message.reply_text(
            "⚠️ *يرجى إدخال رقم هاتف صحيح*\n"
            "══════════════════════════\n"
            "📌 *الشروط المطلوبة:*\n"
            "• يجب أن يتكون الرقم من 8 أرقام\n"
            "• يجب أن يحتوي على أرقام فقط\n"
            "• مثال: `71234567`\n"
            "🔍 الرجاء إدخال الرقم بشكل صحيح",
            parse_mode='Markdown'
        )
        return
    
    # ⏳ إعلام المستخدم بالمعالجة
    processing_msg = await update.message.reply_text(
        "⏳ *جاري معالجة طلبك...*\n"
        "══════════════════════════\n"
        "📡 يتم الآن الاتصال بخادم ADSL\n"
        "⏱️ قد يستغرق الأمر بضع ثوانٍ...",
        parse_mode='Markdown'
    )
    
    # 🔎 تنفيذ الاستعلام
    info = get_adsl_info(phone_number)
    
    # ✉️ إرسال النتيجة
    await processing_msg.delete()
    await send_balance_info(update, phone_number, info)
    
    # عرض خيار إضافة الرقم إلى المحفوظات
    if info:
        keyboard = [
            [InlineKeyboardButton("💾 حفظ الرقم", callback_data=f'save_{phone_number}')],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❔ *هل ترغب في حفظ هذا الرقم للاستعلام عنه لاحقاً؟*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# 🛠️ معالجة الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'add_number':
        await query.edit_message_text(
            "📝 *إضافة رقم جديد للمحفوظات*\n"
            "══════════════════════════\n"
            "📱 يرجى إرسال رقم الهاتف المكون من 8 أرقام\n"
            "✏️ مثال: `71234567`\n"
            "🔙 للعودة اضغط /start",
            parse_mode='Markdown'
        )
        return ADD_NUMBER
    
    elif query.data == 'manage_numbers':
        chat_id = str(query.from_user.id)
        user_numbers = saved_numbers.get(chat_id, {})
        
        if not user_numbers:
            await query.edit_message_text(
                "⚠️ *لا توجد أرقام محفوظة*\n"
                "══════════════════════════\n"
                "لم تقم بإضافة أي أرقام إلى المحفوظات بعد\n"
                "➕ يمكنك إضافة أرقام جديدة من القائمة الرئيسية",
                parse_mode='Markdown'
            )
            return
        
        keyboard = []
        for num in user_numbers:
            keyboard.append([InlineKeyboardButton(f"✏️ {num}", callback_data=f'edit_{num}')])
            keyboard.append([InlineKeyboardButton(f"🗑️ حذف {num}", callback_data=f'delete_{num}')])
        keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗂️ *إدارة الأرقام المحفوظة*\n"
            "══════════════════════════\n"
            "🔘 اختر الرقم الذي تريد إدارته:\n"
            "✏️ زر التعديل - لعرض خيارات التعديل\n"
            "🗑️ زر الحذف - لإزالة الرقم من المحفوظات",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return DELETE_NUMBER
    
    elif query.data == 'show_numbers':
        chat_id = str(query.from_user.id)
        user_numbers = saved_numbers.get(chat_id, {})
        
        if not user_numbers:
            await query.edit_message_text(
                "📋 *الأرقام المحفوظة*\n"
                "══════════════════════════\n"
                "⚠️ لا توجد أرقام محفوظة حالياً\n"
                "➕ يمكنك إضافة أرقام جديدة من القائمة الرئيسية",
                parse_mode='Markdown'
            )
            return
        
        numbers_list = "\n".join([f"• 📱 `{num}`" for num in user_numbers])
        await query.edit_message_text(
            f"📋 *قائمة الأرقام المحفوظة*\n"
            f"══════════════════════════\n"
            f"{numbers_list}\n"
            f"🔢 *العدد الإجمالي:* {len(user_numbers)}\n"
            f"🔍 يمكنك استعلام هذه الأرقام دفعة واحدة من القائمة الرئيسية",
            parse_mode='Markdown'
        )
    
    elif query.data == 'query_numbers':
        chat_id = str(query.from_user.id)
        user_numbers = saved_numbers.get(chat_id, {})
        
        if not user_numbers:
            await query.edit_message_text(
                "⚠️ *لا توجد أرقام محفوظة*\n"
                "══════════════════════════\n"
                "لم تقم بإضافة أي أرقام إلى المحفوظات بعد\n"
                "➕ يمكنك إضافة أرقام جديدة من القائمة الرئيسية",
                parse_mode='Markdown'
            )
            return
        
        # استعلام فوري عن جميع الأرقام المحفوظة
        processing_msg = await query.message.reply_text(
            "⏳ *جاري استعلام الأرقام المحفوظة*\n"
            "══════════════════════════\n"
            "📡 يتم الآن جلب أحدث المعلومات عن جميع الأرقام\n"
            "⏱️ قد تستغرق العملية بعض الوقت...",
            parse_mode='Markdown'
        )
        
        # حذف الرسائل السابقة إذا وجدت
        if 'last_query_messages' in context.user_data:
            for msg_id in context.user_data['last_query_messages']:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    logger.error(f"فشل في حذف الرسالة السابقة: {e}")
        
        # إنشاء قائمة لتخزين رسائل النتائج
        context.user_data['last_query_messages'] = []
        
        # خيارات العرض للمستخدم
        keyboard = [
            [InlineKeyboardButton("📊 عرض كجدول", callback_data='view_table')],
            [InlineKeyboardButton("📩 عرض كرسائل", callback_data='view_messages')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            "📊 *اختر طريقة عرض النتائج*\n"
            "══════════════════════════\n"
            "• 📊 جدول: عرض النتائج في جدول منظم\n"
            "• 📩 رسائل: عرض كل نتيجة في رسالة منفصلة\n"
            "🔢 *عدد الأرقام:* {}".format(len(user_numbers)),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == 'view_table':
        chat_id = str(query.from_user.id)
        user_numbers = saved_numbers.get(chat_id, {})
        
        # إنشاء جدول للنتائج
        table_data = []
        for num in user_numbers:
            info = get_adsl_info(num)
            if info:
                table_data.append([
                    num,
                    info['current_balance'],
                    info['expiry_date'],
                    info['timestamp']
                ])
            else:
                table_data.append([
                    num,
                    "❌ فشل",
                    "❌ فشل",
                    datetime.now(YEMEN_TZ).strftime("%Y-%m-%d %H:%M:%S")
                ])
        
        # تنسيق النتائج كجدول
        headers = ["📱 الرقم", "💵 الرصيد", "📅 الانتهاء", "⏰ آخر تحديث"]
        table = tabulate(table_data, headers=headers, tablefmt="grid")
        
        response = (
            "📊 *نتائج الاستعلام عن الأرقام المحفوظة*\n"
            "══════════════════════════\n"
            f"```\n{table}\n```\n"
            f"🔢 *عدد الأرقام:* {len(user_numbers)}\n"
            f"⏱️ *وقت الانتهاء:* {datetime.now(YEMEN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
            "✨ تم الانتهاء من عملية الاستعلام بنجاح"
        )
        
        msg = await query.message.reply_text(response, parse_mode='Markdown')
        context.user_data['last_query_messages'].append(msg.message_id)
        
        # إضافة زر للعودة
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("اضغط على الزر أدناه للعودة إلى القائمة الرئيسية", reply_markup=reply_markup)
    
    elif query.data == 'view_messages':
        chat_id = str(query.from_user.id)
        user_numbers = saved_numbers.get(chat_id, {})
        
        # إرسال كل نتيجة في رسالة منفصلة
        for num in user_numbers:
            info = get_adsl_info(num)
            if info:
                response = (
                    f"📊 *نتائج استعلام رصيد ADSL*\n"
                    f"══════════════════════════\n"
                    f"📱 *الرقم:* `{num}`\n"
                    f"⏰ *وقت الاستعلام:* {info['timestamp']}\n"
                    f"💵 *الرصيد الحالي:* `{info['current_balance']}`\n"
                    f"💰 *قيمة الباقة:* `{info['package_value']}`\n"
                    f"📅 *تاريخ الانتهاء:* `{info['expiry_date']}`"
                )
            else:
                response = (
                    f"⚠️ *فشل في استعلام الرقم*\n"
                    f"══════════════════════════\n"
                    f"📱 *الرقم:* `{num}`\n"
                    f"⏰ *وقت المحاولة:* {datetime.now(YEMEN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"🛑 لم يتمكن البوت من الحصول على معلومات هذا الرقم"
                )
            
            msg = await query.message.reply_text(response, parse_mode='Markdown')
            context.user_data['last_query_messages'].append(msg.message_id)
        
        # إرسال ملخص النتائج
        summary_msg = await query.message.reply_text(
            f"✅ *تم الانتهاء من استعلام جميع الأرقام*\n"
            f"══════════════════════════\n"
            f"🔢 *عدد الأرقام:* {len(user_numbers)}\n"
            f"⏱️ *وقت الانتهاء:* {datetime.now(YEMEN_TZ).strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode='Markdown'
        )
        context.user_data['last_query_messages'].append(summary_msg.message_id)
        
        # إضافة زر للعودة
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("اضغط على الزر أدناه للعودة إلى القائمة الرئيسية", reply_markup=reply_markup)
    
    elif query.data == 'schedule_query':
        keyboard = [
            [InlineKeyboardButton("🕐 1 ", callback_data='hour_1'),
             InlineKeyboardButton("🕑 2 ", callback_data='hour_2'),
             InlineKeyboardButton("🕒 3 ", callback_data='hour_3')],
            [InlineKeyboardButton("🕓 4 ", callback_data='hour_4'),
             InlineKeyboardButton("🕔 5 ", callback_data='hour_5'),
             InlineKeyboardButton("🕕 6 ", callback_data='hour_6')],
            [InlineKeyboardButton("🕖 7 ", callback_data='hour_7'),
             InlineKeyboardButton("🕗 8 ", callback_data='hour_8'),
             InlineKeyboardButton("🕘 9 ", callback_data='hour_9')],
            [InlineKeyboardButton("🕙 10 ", callback_data='hour_10'),
             InlineKeyboardButton("🕚 11 ", callback_data='hour_11'),
             InlineKeyboardButton("🕛 12 ", callback_data='hour_12')],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏰ *جدولة الاستعلام التلقائي*\n"
            "══════════════════════════\n"
            "📅 يرجى تحديد الساعة المطلوبة للاستعلام اليومي\n"
            "⏱️ سيتم إجراء الاستعلام تلقائياً في الوقت المحدد",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return SCHEDULE_HOUR
    
    elif query.data == 'help':
        help_text = (
            "ℹ️ *دليل استخدام البوت*\n"
            "══════════════════════════\n"
            "🔹 *إضافة رقم جديد*:\n"
            "   - اضغط على ➕ إضافة رقم\n"
            "   - أرسل الرقم المكون من 8 أرقام\n"
            "🔹 *عرض الأرقام المحفوظة*:\n"
            "   - يعرض قائمة بالأرقام المحفوظة الخاصة بك\n"
            "🔹 *استعلام الأرقام المحفوظة*:\n"
            "   - يجلب أحدث معلومات جميع الأرقام المحفوظة\n"
            "🔹 *إدارة الأرقام*:\n"
            "   - تعديل أو حذف الأرقام المحفوظة\n"
            "🔹 *جدولة استعلام*:\n"
            "   - ضبط استعلام تلقائي يومي في وقت محدد\n"
            "📌 *ملاحظات مهمة*:\n"
            "   - يمكنك إرسال أي رقم مباشرة للاستعلام الفوري\n"
            "   - الاستعلامات المجدولة تتطلب وجود أرقام محفوظة\n"
            "   - يتم تحديث البيانات عند كل استعلام\n"
            "🔧 *للإبلاغ عن مشاكل*:\n"
            "   - راسل المطور @username"
        )
        await query.edit_message_text(help_text, parse_mode='Markdown')
    
    elif query.data == 'back':
        await start(update, context)
    
    elif query.data == 'new_query':
        await query.edit_message_text(
            "🔍 *استعلام جديد*\n"
            "══════════════════════════\n"
            "📱 يرجى إرسال رقم الهاتف المكون من 8 أرقام\n"
            "✏️ مثال: `71234567`",
            parse_mode='Markdown'
        )
    
    elif query.data == 'refresh':
        await query.edit_message_text(
            "🔄 *جاري تحديث البوت...*\n"
            "══════════════════════════\n"
            "⏱️ يرجى الانتظار قليلاً...",
            parse_mode='Markdown'
        )
        await asyncio.sleep(2)
        await start(update, context)
    
    elif query.data.startswith('save_'):
        phone_number = query.data[5:]
        chat_id = str(query.from_user.id)
        
        # إنشاء مجلد للمستخدم إذا لم يكن موجودًا
        if chat_id not in saved_numbers:
            saved_numbers[chat_id] = {}
        
        saved_numbers[chat_id][phone_number] = True
        save_numbers_to_file(saved_numbers)  # حفظ التغييرات في الملف
        
        await query.edit_message_text(
            f"✅ *تمت العملية بنجاح*\n"
            f"══════════════════════════\n"
            f"تم حفظ الرقم `{phone_number}` في المحفوظات\n"
            f"📋 يمكنك عرض وإدارة الأرقام المحفوظة من القائمة الرئيسية",
            parse_mode='Markdown'
        )
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("اضغط على الزر أدناه للعودة إلى القائمة الرئيسية", reply_markup=reply_markup)
    
    elif query.data.startswith('edit_'):
        phone_number = query.data[5:]
        await query.edit_message_text(
            f"✏️ *تعديل الرقم {phone_number}*\n"
            f"══════════════════════════\n"
            f"هذه الميزة قيد التطوير حالياً\n"
            f"📌 يمكنك حذف الرقم وإضافته مرة أخرى\n"
            f"🔙 سيتم إضافة خيارات التعديل في التحديثات القادمة",
            parse_mode='Markdown'
        )
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("اضغط على الزر أدناه للعودة إلى القائمة الرئيسية", reply_markup=reply_markup)

# ➕ إضافة رقم إلى المحفوظات
async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text.strip()
    chat_id = str(update.effective_user.id)
    
    if not phone_number.isdigit() or len(phone_number) != 8:
        await update.message.reply_text(
            "⚠️ *رقم غير صالح*\n"
            "══════════════════════════\n"
            "📌 *الشروط المطلوبة:*\n"
            "• يجب أن يتكون الرقم من 8 أرقام\n"
            "• يجب أن يحتوي على أرقام فقط\n"
            "📱 يرجى إرسال الرقم بشكل صحيح",
            parse_mode='Markdown'
        )
        return ADD_NUMBER
    
    # إنشاء مجلد للمستخدم إذا لم يكن موجودًا
    if chat_id not in saved_numbers:
        saved_numbers[chat_id] = {}
    
    saved_numbers[chat_id][phone_number] = True
    save_numbers_to_file(saved_numbers)  # حفظ التغييرات في الملف
    
    await update.message.reply_text(
        f"✅ *تمت الإضافة بنجاح*\n"
        f"══════════════════════════\n"
        f"• *الرقم المضاف:* `{phone_number}`\n"
        f"• *تاريخ الإضافة:* {datetime.now(YEMEN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📋 يمكنك الآن إدارة هذا الرقم من القائمة الرئيسية",
        parse_mode='Markdown'
    )
    
    # عرض زر للعودة أو إضافة رقم جديد
    keyboard = [
        [InlineKeyboardButton("➕ إضافة رقم آخر", callback_data='add_number')],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "❔ *هل ترغب في إضافة رقم آخر؟*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

# 🗑️ حذف رقم من المحفوظات
async def delete_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('delete_'):
        chat_id = str(query.from_user.id)
        num_to_delete = query.data[7:]
        
        if chat_id in saved_numbers and num_to_delete in saved_numbers[chat_id]:
            del saved_numbers[chat_id][num_to_delete]
            save_numbers_to_file(saved_numbers)  # حفظ التغييرات في الملف
            
            await query.edit_message_text(
                f"✅ *تم الحذف بنجاح*\n"
                f"══════════════════════════\n"
                f"• *الرقم المحذوف:* `{num_to_delete}`\n"
                f"• *تاريخ الحذف:* {datetime.now(YEMEN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📋 يمكنك إضافة أرقام جديدة من القائمة الرئيسية",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "⚠️ *تعذر الحذف*\n"
                "══════════════════════════\n"
                "• الرقم المطلوب غير موجود في المحفوظات\n"
                "📋 يرجى التحقق من الأرقام المحفوظة والمحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    
    keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("اضغط على الزر أدناه للعودة إلى القائمة الرئيسية", reply_markup=reply_markup)
    return ConversationHandler.END

# ⏰ جدولة استعلام تلقائي (اختيار الساعة)
async def schedule_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('hour_'):
        hour = int(query.data[5:])
        context.user_data['scheduled_hour'] = hour
        
        keyboard = [
            [InlineKeyboardButton("🌅 صباحاً (AM)", callback_data='ampm_AM')],
            [InlineKeyboardButton("🌇 مساءً (PM)", callback_data='ampm_PM')],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⏰ *تحديد وقت الجدولة*\n"
            f"══════════════════════════\n"
            f"• *الساعة المحددة:* {hour}\n"
            f"🌅 يرجى تحديد الفترة الزمنية (صباحاً/مساءً)",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return SCHEDULE_AMPM
    
    await start(update, context)
    return ConversationHandler.END

# 🌇 تحديد الفترة الزمنية (صباح/مساء)
async def schedule_ampm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if not hasattr(context, 'job_queue') or context.job_queue is None:
        await query.edit_message_text(
            "⚠️ *تعذر إعداد الجدولة*\n"
            "══════════════════════════\n"
            "حدث خطأ تقني في نظام الجدولة\n"
            "🔄 يرجى المحاولة مرة أخرى لاحقاً",
            parse_mode='Markdown'
        )
        await start(update, context)
        return ConversationHandler.END
    
    if query.data.startswith('ampm_'):
        ampm = query.data[5:]
        hour = context.user_data.get('scheduled_hour', 12)
        chat_id = query.message.chat_id
        chat_id_str = str(chat_id)
        
        # تحويل إلى توقيت 24 ساعة
        if ampm == 'PM' and hour < 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0
        
        # حفظ الوقت المجدول في الملف
        scheduled_times[chat_id_str] = {
            'hour': hour,
            'minute': 0,
            'ampm': ampm
        }
        save_scheduled_times(scheduled_times)
        
        # حساب وقت الجدولة بتوقيت اليمن
        now = datetime.now(YEMEN_TZ)
        scheduled_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # إذا كان الوقت المحدد قد مضى اليوم، نضيف يوم
        if scheduled_time < now:
            scheduled_time += timedelta(days=1)
        
        # حساب الفترة حتى الجدولة
        delta = scheduled_time - now
        seconds_until = delta.total_seconds()
        
        # إعداد المهمة المجدولة
        if chat_id in scheduled_jobs:
            scheduled_jobs[chat_id].schedule_removal()
        
        try:
            job = context.job_queue.run_repeating(
                auto_query_callback,
                interval=timedelta(days=1),
                first=timedelta(seconds=seconds_until),
                chat_id=chat_id
            )
            scheduled_jobs[chat_id] = job
            
            await query.edit_message_text(
                f"✅ *تمت الجدولة بنجاح*\n"
                f"══════════════════════════\n"
                f"• *وقت الاستعلام:* {hour % 12 or 12} {'صباحاً' if ampm == 'AM' else 'مساءً'}\n"
                f"• سيبدأ الاستعلام التلقائي يومياً في الوقت المحدد\n"
                f"📋 يمكنك تعديل الإعدادات في أي وقت من القائمة الرئيسية",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"خطأ في الجدولة: {e}")
            await query.edit_message_text(
                "⚠️ *تعذر إعداد الجدولة*\n"
                "══════════════════════════\n"
                "حدث خطأ تقني أثناء محاولة جدولة الاستعلام\n"
                "🔄 يرجى المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
    
    keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("اضغط على الزر أدناه للعودة إلى القائمة الرئيسية", reply_markup=reply_markup)
    return ConversationHandler.END

# 🔄 الاستعلام التلقائي عن الأرقام المحفوظة
async def auto_query_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    chat_id_str = str(chat_id)
    
    if chat_id_str not in saved_numbers or not saved_numbers[chat_id_str]:
        await context.bot.send_message(
            chat_id,
            "⚠️ *لا توجد أرقام محفوظة*\n"
            "══════════════════════════\n"
            "لم يتم العثور على أي أرقام محفوظة للاستعلام عنها\n"
            "➕ يرجى إضافة أرقام أولاً من القائمة الرئيسية",
            parse_mode='Markdown'
        )
        return
    
    processing_msg = await context.bot.send_message(
        chat_id,
        "⏳ *جاري تنفيذ الاستعلام التلقائي*\n"
        "══════════════════════════\n"
        "📡 يتم الآن جلب أحدث المعلومات عن الأرقام المحفوظة\n"
        "⏱️ يرجى الانتظار...",
        parse_mode='Markdown'
    )
    
    # إنشاء جدول للنتائج
    table_data = []
    for num in saved_numbers[chat_id_str]:
        info = get_adsl_info(num)
        if info:
            table_data.append([
                num,
                info['current_balance'],
                info['expiry_date'],
                info['timestamp']
            ])
        else:
            table_data.append([
                num,
                "❌ فشل",
                "❌ فشل",
                datetime.now(YEMEN_TZ).strftime("%Y-%m-%d %H:%M:%S")
            ])
    
    # تنسيق النتائج كجدول
    headers = ["📱 الرقم", "💵 الرصيد", "📅 الانتهاء", "⏰ آخر تحديث"]
    table = tabulate(table_data, headers=headers, tablefmt="grid")
    
    response = (
        "⏰ *نتائج الاستعلام التلقائي*\n"
        "══════════════════════════\n"
        f"```\n{table}\n```\n"
        f"🔢 *عدد الأرقام:* {len(saved_numbers[chat_id_str])}\n"
        f"⏱️ *وقت الانتهاء:* {datetime.now(YEMEN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n"
        "✨ تم الانتهاء من عملية الاستعلام بنجاح"
    )
    
    await processing_msg.delete()
    await context.bot.send_message(chat_id, response, parse_mode='Markdown')

# ⏰ دالة للتحقق من الأوقات المجدولة وإرسال التنبيهات
async def check_scheduled_times(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(YEMEN_TZ)
    current_hour = now.hour
    current_minute = now.minute
    
    for chat_id_str, time_data in scheduled_times.items():
        try:
            chat_id = int(chat_id_str)
            scheduled_hour = time_data['hour']
            scheduled_minute = time_data.get('minute', 0)
            
            if current_hour == scheduled_hour and current_minute == scheduled_minute:
                await context.bot.send_message(
                    chat_id,
                    f"⏰ *تنبيه الوقت المجدول*\n"
                    f"══════════════════════════\n"
                    f"حان الوقت المحدد للاستعلام التلقائي!\n"
                    f"• الساعة: {scheduled_hour % 12 or 12} {'صباحاً' if scheduled_hour < 12 else 'مساءً'}\n"
                    f"📡 جاري إجراء الاستعلام الآن...",
                    parse_mode='Markdown'
                )
                # تنفيذ الاستعلام التلقائي
                await auto_query_callback(context)
        except Exception as e:
            logger.error(f"خطأ في التحقق من الوقت المجدول لـ {chat_id_str}: {e}")

# ⚠️ معالجة الأخطاء
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إدارة الأخطاء"""
    logger.error(msg="حدث خطأ في البوت:", exc_info=context.error)
    
    if update.message:
        await update.message.reply_text(
            "⛔ *عذراً، حدث خطأ غير متوقع*\n"
            "══════════════════════════\n"
            "لقد واجهنا مشكلة تقنية أثناء معالجة طلبك\n"
            "🔄 يرجى المحاولة مرة أخرى لاحقاً\n"
            "📧 للدعم الفني، يرجى التواصل مع المسؤول",
            parse_mode='Markdown'
        )

# 🚀 تشغيل البوت
async def run_bot():
    # إنشاء Application مع JobQueue
    application = ApplicationBuilder().token(TOKEN).build()
    
    # إضافة مهمة دورية للتحقق من الأوقات المجدولة كل دقيقة
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            check_scheduled_times,
            interval=60.0,  # كل دقيقة
            first=10.0      # البدء بعد 10 ثواني
        )
    
    # إعداد معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            ADD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_number)],
            DELETE_NUMBER: [CallbackQueryHandler(delete_number)],
            SCHEDULE_HOUR: [CallbackQueryHandler(schedule_hour)],
            SCHEDULE_AMPM: [CallbackQueryHandler(schedule_ampm)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    # 🛠️ تسجيل المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    logger.info("🤖 البوت يعمل...")
    await application.run_polling()

# التأكد من تثبيت المكتبة بالكامل
try:
    from telegram.ext import JobQueue
except ImportError:
    logger.error("❌ لم يتم تثبيت JobQueue. يرجى تثبيت المكتبة باستخدام:")
    logger.error('pip install "python-telegram-bot[job-queue]"')
    exit(1)

# التشغيل الرئيسي
if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("⏹️ إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}")