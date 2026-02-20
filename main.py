import telebot
import sqlite3
import os
import random
import pandas as pd
from telebot import types

# Render'da Environment Variables qismiga BOT_TOKEN ni qo'shing
TOKEN = os.getenv('BOT_TOKEN', '8549416953:AAFtVScYoBHoegqdzeOh5IwrD7LhoK0ftqs')
bot = telebot.TeleBot(TOKEN)

# Foydalanuvchi qadamlarini vaqtinchalik saqlash
user_data = {}

def init_db():
    conn = sqlite3.connect('rush_final.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS tests (test_id INTEGER PRIMARY KEY, keys TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (user_id INTEGER, test_id INTEGER, name TEXT, correct INTEGER, score REAL,
                       PRIMARY KEY (user_id, test_id))''')
    conn.commit()
    conn.close()

def get_keyboard(q_num, mode, test_id="0"):
    markup = types.InlineKeyboardMarkup(row_width=4)
    row = [types.InlineKeyboardButton(ch, callback_data=f"{mode}_{q_num}_{ch.lower()}_{test_id}") for ch in ['A', 'B', 'C', 'D']]
    markup.add(*row)
    return markup

@bot.message_handler(commands=['start'])
def welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🆕 Test Tuzish", "✍️ Test Ishlash")
    markup.add("🏆 Reyting", "📊 Excel Yuklash")
    bot.send_message(message.chat.id, "👋 Rush Module interaktiv botiga xush kelibsiz!", reply_markup=markup)

# --- TEST TUZISH ---
@bot.message_handler(func=lambda m: m.text == "🆕 Test Tuzish")
def start_tuzish(message):
    uid = message.from_user.id
    user_data[uid] = {'keys': '', 'step': 1}
    bot.send_message(message.chat.id, "📝 **1-savol** uchun to'g'ri javobni tanlang:", 
                     reply_markup=get_keyboard(1, "set"), parse_mode="Markdown")

# --- TEST ISHLASH ---
@bot.message_handler(func=lambda m: m.text == "✍️ Test Ishlash")
def input_id(message):
    msg = bot.send_message(message.chat.id, "🔢 Test ID raqamini kiriting:")
    bot.register_next_step_handler(msg, verify_test_id)

def verify_test_id(message):
    t_id = message.text.strip()
    conn = sqlite3.connect('rush_final.db')
    cursor = conn.cursor()
    cursor.execute("SELECT keys FROM tests WHERE test_id = ?", (t_id,))
    res = cursor.fetchone()
    conn.close()

    if not res:
        bot.reply_to(message, "❌ Bunday test topilmadi!")
        return

    msg = bot.send_message(message.chat.id, "👤 Ism-familiyangizni kiriting:")
    bot.register_next_step_handler(msg, start_solving, t_id, res[0])

def start_solving(message, t_id, correct_keys):
    uid = message.from_user.id
    user_data[uid] = {'ans': '', 'step': 1, 'name': message.text, 'keys': correct_keys, 'tid': t_id}
    bot.send_message(message.chat.id, f"📝 Test ID: {t_id}\n**1-savol** javobini tanlang:", 
                     reply_markup=get_keyboard(1, "solve", t_id), parse_mode="Markdown")

# --- CALLBACK QUERY ---
@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
    data = call.data.split('_')
    mode, q_num, ans, t_id = data[0], int(data[1]), data[2], data[3]
    uid = call.from_user.id

    if uid not in user_data: return

    if mode == "set":
        user_data[uid]['keys'] += ans
        if q_num < 45:
            next_q = q_num + 1
            bot.edit_message_text(f"📝 **{next_q}-savol** uchun to'g'ri javobni tanlang:", 
                                 call.message.chat.id, call.message.message_id, 
                                 reply_markup=get_keyboard(next_q, "set"), parse_mode="Markdown")
        else:
            new_id = random.randint(1000, 9999)
            conn = sqlite3.connect('rush_final.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tests VALUES (?, ?)", (new_id, user_data[uid]['keys']))
            conn.commit()
            conn.close()
            bot.edit_message_text(f"✅ **Test yaratildi!**\n\n🔢 ID: `{new_id}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            del user_data[uid]

    elif mode == "solve":
        user_data[uid]['ans'] += ans
        if q_num < 45:
            next_q = q_num + 1
            bot.edit_message_text(f"📝 Test ID: {t_id}\n**{next_q}-savol** javobini tanlang:", 
                                 call.message.chat.id, call.message.message_id, 
                                 reply_markup=get_keyboard(next_q, "solve", t_id), parse_mode="Markdown")
        else:
            finish_test(call)

def finish_test(call):
    uid = call.from_user.id
    d = user_data[uid]
    correct = sum(1 for i in range(45) if d['ans'][i] == d['keys'][i])
    perc = round((correct/45)*100, 1)

    conn = sqlite3.connect('rush_final.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?)", (uid, d['tid'], d['name'], correct, perc))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM results WHERE test_id = ? AND score > ?", (d['tid'], perc))
    rank = cursor.fetchone()[0] + 1
    conn.close()

    bot.edit_message_text(f"🏁 **Natijangiz:**\n👤 {d['name']}\n✅ To'g'ri: {correct}/45\n📊 Ball: {perc}%\n🏆 O'rin: {rank}", 
                         call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    del user_data[uid]

# --- REYTING VA EXCEL ---
@bot.message_handler(func=lambda m: m.text in ["🏆 Reyting", "📊 Excel Yuklash"])
def ask_id_for_extra(message):
    action = "rating" if message.text == "🏆 Reyting" else "excel"
    msg = bot.send_message(message.chat.id, f"🔢 Test ID raqamini yuboring ({action}):")
    bot.register_next_step_handler(msg, process_extra, action)

def process_extra(message, action):
    t_id = message.text.strip()
    conn = sqlite3.connect('rush_final.db')
    if action == "rating":
        cursor = conn.cursor()
        cursor.execute("SELECT name, correct, score FROM results WHERE test_id = ? ORDER BY score DESC LIMIT 15", (t_id,))
        rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Natijalar topilmadi.")
        else:
            res = f"🏆 **Test {t_id} bo'yicha TOP-15:**\n\n"
            for i, r in enumerate(rows, 1):
                res += f"{i}. {r[0]} — {r[1]} ta ({r[2]}%)\n"
            bot.send_message(message.chat.id, res, parse_mode="Markdown")
    else:
        df = pd.read_sql_query(f"SELECT name as 'F.I.SH', correct as 'To''g'ri', score as 'Ball' FROM results WHERE test_id = {t_id} ORDER BY score DESC", conn)
        if df.empty:
            bot.send_message(message.chat.id, "📭 Natijalar mavjud emas.")
        else:
            path = f"results_{t_id}.xlsx"
            df.to_excel(path, index=False)
            with open(path, 'rb') as f:
                bot.send_document(message.chat.id, f, caption=f"📊 Test {t_id} natijalari")
    conn.close()

if __name__ == '__main__':
    init_db()
    bot.infinity_polling()
