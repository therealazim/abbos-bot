import telebot
import sqlite3
import os
import random
import pandas as pd
from telebot import types
from threading import Thread
from flask import Flask

TOKEN = os.getenv('BOT_TOKEN', '8549416953:AAFtVScYoBHoegqdzeOh5IwrD7LhoK0ftqs')
bot = telebot.TeleBot(TOKEN)

# Render port xatosi uchun
server = Flask('')
@server.route('/')
def home(): return "Bot is running!"
def run(): server.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

def init_db():
    conn = sqlite3.connect('rush_v6.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS tests (test_id INTEGER PRIMARY KEY, keys TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (user_id INTEGER, test_id INTEGER, name TEXT, correct INTEGER, score REAL,
                       PRIMARY KEY (user_id, test_id))''')
    conn.commit()
    conn.close()

# Foydalanuvchi tanlovlarini vaqtinchalik saqlash
# {user_id: {'answers': ['A', 'A', ...], 'mode': 'set/solve', 'tid': '123', 'name': '...'} }
user_sessions = {}

def create_grid_keyboard(uid):
    session = user_sessions.get(uid)
    if not session: return None
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = []
    ans_list = session['answers']
    
    for i in range(45):
        current_val = ans_list[i]
        # Tugma matni: "1:A"
        btn_text = f"{i+1}:{current_val}"
        callback = f"click_{i}"
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=callback))
    
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("✅ TASDIQLASH (TAYYOR)", callback_data="submit_all"))
    return markup

@bot.message_handler(commands=['start'])
def welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🆕 Test Tuzish", "✍️ Test Ishlash")
    markup.add("🏆 Reyting", "📊 Excel Yuklash")
    bot.send_message(message.chat.id, "👋 Rush Module interaktiv botiga xush kelibsiz!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🆕 Test Tuzish")
def start_tuzish(message):
    uid = message.from_user.id
    user_sessions[uid] = {'answers': ['A']*45, 'mode': 'set'}
    bot.send_message(message.chat.id, "📝 45 ta savol uchun to'g'ri kalitlarni belgilang:\n(Raqamni bossangiz harf o'zgaradi)", 
                     reply_markup=create_grid_keyboard(uid))

@bot.message_handler(func=lambda m: m.text == "✍️ Test Ishlash")
def input_id(message):
    msg = bot.send_message(message.chat.id, "🔢 Test ID raqamini kiriting:")
    bot.register_next_step_handler(msg, get_id_solve)

def get_id_solve(message):
    tid = message.text.strip()
    conn = sqlite3.connect('rush_v6.db')
    cursor = conn.cursor()
    cursor.execute("SELECT keys FROM tests WHERE test_id = ?", (tid,))
    res = cursor.fetchone()
    conn.close()
    if not res:
        bot.reply_to(message, "❌ Test topilmadi.")
        return
    msg = bot.send_message(message.chat.id, "👤 Ism-familiyangizni kiriting:")
    bot.register_next_step_handler(msg, run_solver, tid, res[0])

def run_solver(message, tid, keys):
    uid = message.from_user.id
    user_sessions[uid] = {'answers': ['A']*45, 'mode': 'solve', 'tid': tid, 'correct_keys': keys, 'name': message.text}
    bot.send_message(message.chat.id, f"📝 Test ID: {tid}\nJavoblaringizni belgilang:", 
                     reply_markup=create_grid_keyboard(uid))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    if uid not in user_sessions:
        bot.answer_callback_query(call.id, "Sessiya muddati tugagan. Qaytadan boshlang.")
        return

    if call.data.startswith("click_"):
        index = int(call.data.split("_")[1])
        # Harfni almashtirish: A -> B -> C -> D -> A
        current = user_sessions[uid]['answers'][index]
        next_val = {'A':'B', 'B':'C', 'C':'D', 'D':'A'}[current]
        user_sessions[uid]['answers'][index] = next_val
        
        # Faqat klaviaturani yangilash (xabar matni o'zgarmaydi)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                      reply_markup=create_grid_keyboard(uid))
        bot.answer_callback_query(call.id)

    elif call.data == "submit_all":
        data = user_sessions[uid]
        final_keys = "".join(data['answers']).lower()
        
        if data['mode'] == 'set':
            new_id = random.randint(1000, 9999)
            conn = sqlite3.connect('rush_v6.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tests VALUES (?, ?)", (new_id, final_keys))
            conn.commit()
            conn.close()
            bot.edit_message_text(f"✅ Test yaratildi! ID: `{new_id}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        
        else:
            correct = sum(1 for i in range(45) if final_keys[i] == data['correct_keys'][i])
            perc = round((correct/45)*100, 1)
            conn = sqlite3.connect('rush_v6.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?)", (uid, data['tid'], data['name'], correct, perc))
            conn.commit()
            conn.close()
            bot.edit_message_text(f"🏁 Natija: {correct}/45 ({perc}%)", call.message.chat.id, call.message.message_id)
        
        del user_sessions[uid]
        bot.answer_callback_query(call.id, "Muvaffaqiyatli saqlandi!")

# (Reyting va Excel qismlari yuqoridagidek qoladi...)

if __name__ == '__main__':
    init_db()
    Thread(target=run).start()
    bot.infinity_polling(timeout=20)
