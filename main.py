import telebot
import sqlite3
import os
import random
from telebot import types

TOKEN = os.getenv('BOT_TOKEN', '8549416953:AAFtVScYoBHoegqdzeOh5IwrD7LhoK0ftqs')
bot = telebot.TeleBot(TOKEN)

# Foydalanuvchi jarayonlarini saqlash uchun vaqtinchalik lug'at
user_steps = {}

def init_db():
    conn = sqlite3.connect('rush_inline.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS tests (test_id INTEGER PRIMARY KEY, keys TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (user_id INTEGER, test_id INTEGER, name TEXT, correct INTEGER, score REAL,
                       PRIMARY KEY (user_id, test_id))''')
    conn.commit()
    conn.close()

# --- TUGMALAR GENERATORI ---
def generate_quiz_keyboard(question_num, mode, test_id=None):
    markup = types.InlineKeyboardMarkup(row_width=4)
    btns = [
        types.InlineKeyboardButton("A", callback_data=f"{mode}_{question_num}_a_{test_id}"),
        types.InlineKeyboardButton("B", callback_data=f"{mode}_{question_num}_b_{test_id}"),
        types.InlineKeyboardButton("C", callback_data=f"{mode}_{question_num}_c_{test_id}"),
        types.InlineKeyboardButton("D", callback_data=f"{mode}_{question_num}_d_{test_id}")
    ]
    markup.add(*btns)
    return markup

# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🆕 Test Tuzish", "✍️ Test Ishlash", "🏆 Reyting")
    bot.send_message(message.chat.id, "Rush Module Botiga xush kelibsiz!", reply_markup=markup)

# --- TEST TUZISH ---
@bot.message_handler(func=lambda m: m.text == "🆕 Test Tuzish")
@bot.message_handler(commands=['testtuzish'])
def start_create(message):
    user_steps[message.from_user.id] = {'keys': '', 'current_q': 1}
    bot.send_message(message.chat.id, "1-savol uchun to'g'ri javobni tanlang:", 
                     reply_markup=generate_quiz_keyboard(1, "set"))

# --- TEST ISHLASH ---
@bot.message_handler(func=lambda m: m.text == "✍️ Test Ishlash")
@bot.message_handler(commands=['test'])
def start_solve(message):
    msg = bot.send_message(message.chat.id, "🔢 Test ID raqamini kiriting:")
    bot.register_next_step_handler(msg, check_test_id)

def check_test_id(message):
    test_id = message.text.strip()
    conn = sqlite3.connect('rush_inline.db')
    cursor = conn.cursor()
    cursor.execute("SELECT keys FROM tests WHERE test_id = ?", (test_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        bot.reply_to(message, "❌ Test topilmadi.")
        return

    msg = bot.send_message(message.chat.id, "👤 Ism-familiyangizni kiriting:")
    bot.register_next_step_handler(msg, start_solving_quiz, test_id, row[0])

def start_solving_quiz(message, test_id, true_keys):
    user_steps[message.from_user.id] = {'ans': '', 'current_q': 1, 'name': message.text, 'true_keys': true_keys}
    bot.send_message(message.chat.id, f"Test ID: {test_id}\n1-savolga javobingiz:", 
                     reply_markup=generate_quiz_keyboard(1, "solve", test_id))

# --- CALLBACK QUERY (Tugmalar bosilganda) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    data = call.data.split('_')
    mode = data[0]      # set yoki solve
    q_num = int(data[1])
    answer = data[2]
    test_id = data[3]

    uid = call.from_user.id
    if uid not in user_steps: return

    if mode == "set":
        user_steps[uid]['keys'] += answer
        if q_num < 45:
            new_q = q_num + 1
            bot.edit_message_text(f"{new_q}-savol uchun to'g'ri javobni tanlang:", 
                                 call.message.chat.id, call.message.message_id, 
                                 reply_markup=generate_quiz_keyboard(new_q, "set"))
        else:
            new_id = random.randint(1000, 9999)
            conn = sqlite3.connect('rush_inline.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tests VALUES (?, ?)", (new_id, user_steps[uid]['keys']))
            conn.commit()
            conn.close()
            bot.edit_message_text(f"✅ Test tayyor! \n🔢 ID: `{new_id}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif mode == "solve":
        user_steps[uid]['ans'] += answer
        if q_num < 45:
            new_q = q_num + 1
            bot.edit_message_text(f"{new_q}-savolga javobingiz:", 
                                 call.message.chat.id, call.message.message_id, 
                                 reply_markup=generate_quiz_keyboard(new_q, "solve", test_id))
        else:
            process_final_results(call, test_id)

def process_final_results(call, test_id):
    uid = call.from_user.id
    name = user_steps[uid]['name']
    u_ans = user_steps[uid]['ans']
    t_keys = user_steps[uid]['true_keys']

    correct = sum(1 for i in range(45) if u_ans[i] == t_keys[i])
    score = round((correct / 45) * 100, 1)

    conn = sqlite3.connect('rush_inline.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?)", (uid, test_id, name, correct, score))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM results WHERE test_id = ? AND score > ?", (test_id, score))
    rank = cursor.fetchone()[0] + 1
    conn.close()

    bot.edit_message_text(f"🏁 Test tugadi!\n👤 {name}\n✅ To'g'ri: {correct}\n📊 Ball: {score}%\n🏆 O'rin: {rank}", 
                         call.message.chat.id, call.message.message_id)
    del user_steps[uid]

if __name__ == '__main__':
    init_db()
    bot.infinity_polling()
