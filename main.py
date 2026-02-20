import telebot
import sqlite3
import os
from telebot import types

# --- SOZLAMALAR ---
# Render'da Environment Variables qismiga BOT_TOKEN va ADMIN_ID ni qo'shing
TOKEN = os.getenv('BOT_TOKEN', '8549416953:AAFtVScYoBHoegqdzeOh5IwrD7LhoK0ftqs')
ADMIN_ID = int(os.getenv('ADMIN_ID', '5890942200'))

bot = telebot.TeleBot(TOKEN)

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('rush_module.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS test_keys (id INTEGER PRIMARY KEY, keys TEXT)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (user_id INTEGER PRIMARY KEY, name TEXT, correct INTEGER, score REAL)''')
    conn.commit()
    conn.close()

# --- ADMIN BUYRUQLARI ---

@bot.message_handler(commands=['testtuzish'])
def start_test_creation(message):
    if message.from_user.id == ADMIN_ID:
        msg = bot.send_message(message.chat.id, "📝 **Yangi test yaratish.**\n\n45 ta to'g'ri javobni bir qatorda yuboring (Masalan: abcd...):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_keys)
    else:
        bot.reply_to(message, "⛔️ Bu buyruq faqat admin uchun!")

def save_keys(message):
    keys = message.text.lower().strip()
    if len(keys) != 45:
        bot.reply_to(message, f"❌ Xato! 45 ta bo'lishi kerak. Siz {len(keys)} ta yubordingiz. /testtuzish")
        return

    conn = sqlite3.connect('rush_module.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM test_keys")
    cursor.execute("INSERT INTO test_keys (keys) VALUES (?)", (keys,))
    cursor.execute("DELETE FROM results")  # Yangi test uchun natijalarni tozalash
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Kalitlar saqlandi! O'quvchilar /test ni boshlashlari mumkin.")

# --- O'QUVCHI BUYRUQLARI ---

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "👋 **Rush Module botiga xush kelibsiz!**\n\n🔹 Test topshirish: /test\n🏆 Reyting: /rating")

@bot.message_handler(commands=['test'])
def start_test(message):
    msg = bot.send_message(message.chat.id, "👤 Ism va familiyangizni kiriting:")
    bot.register_next_step_handler(msg, get_name)

def get_name(message):
    full_name = message.text
    msg = bot.send_message(message.chat.id, f"Rahmat, **{full_name}**. \n\n45 ta javobingizni yuboring:")
    bot.register_next_step_handler(msg, check_student_answers, full_name)

def check_student_answers(message, name):
    user_ans = message.text.lower().strip()
    
    conn = sqlite3.connect('rush_module.db')
    cursor = conn.cursor()
    cursor.execute("SELECT keys FROM test_keys")
    row = cursor.fetchone()

    if not row:
        bot.reply_to(message, "⚠️ Hozircha faol test yo'q.")
        conn.close()
        return

    true_keys = row[0]
    if len(user_ans) != 45:
        bot.reply_to(message, f"❌ Xato! Javoblar 45 ta bo'lishi kerak. /test")
        conn.close()
        return

    correct = sum(1 for i in range(45) if user_ans[i] == true_keys[i])
    score_percent = (correct / 45) * 100

    cursor.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?)", 
                   (message.from_user.id, name, correct, round(score_percent, 1)))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM results WHERE score > ?", (score_percent,))
    rank = cursor.fetchone()[0] + 1
    conn.close()

    bot.reply_to(message, f"🏁 **Natijangiz:**\n\n👤 {name}\n✅ To'g'ri: {correct}\n📊 Ball: {score_percent:.1f}%\n🏆 O'rin: {rank}")

@bot.message_handler(commands=['rating'])
def get_rating(message):
    conn = sqlite3.connect('rush_module.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, correct, score FROM results ORDER BY score DESC LIMIT 20")
    data = cursor.fetchall()
    conn.close()

    if not data:
        bot.send_message(message.chat.id, "📭 Natijalar yo'q.")
        return

    text = "🏆 **TOP 20 REYTING:**\n\n"
    for i, user in enumerate(data, 1):
        text += f"{i}. {user[0]} — {user[1]} ta ({user[2]}%)\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

if __name__ == '__main__':
    init_db()
    print("Bot ishladi...")
    bot.infinity_polling()