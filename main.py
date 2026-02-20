import telebot
import sqlite3
import os
import random
from telebot import types

TOKEN = os.getenv('BOT_TOKEN', '8549416953:AAFtVScYoBHoegqdzeOh5IwrD7LhoK0ftqs')
bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('rush_v7.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS tests (test_id INTEGER PRIMARY KEY, keys TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS results (user_id INTEGER, test_id INTEGER, name TEXT, correct INTEGER, score REAL)')
    conn.commit()
    conn.close()

user_sessions = {}

# Har bir savol uchun A, B, C, D tugmalarini chiqaruvchi funksiya
def get_test_keyboard(uid, page=0):
    session = user_sessions[uid]
    markup = types.InlineKeyboardMarkup(row_width=5)
    
    # Bir safar 5 ta savolni ko'rsatish
    start_idx = page * 5
    end_idx = min(start_idx + 5, 45)
    
    for i in range(start_idx, end_idx):
        q_label = types.InlineKeyboardButton(f"S- {i+1}:", callback_data="ignore")
        btns = [types.InlineKeyboardButton(f"{ch}{'✅' if session['answers'][i]==ch else ''}", 
                callback_data=f"ans_{i}_{ch}_{page}") for ch in ['A', 'B', 'C', 'D']]
        markup.row(q_label, *btns)
    
    # Navigatsiya tugmalari
    nav_btns = []
    if page > 0:
        nav_btns.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if end_idx < 45:
        nav_btns.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
    markup.row(*nav_btns)
    
    if all(session['answers']): # Hamma belgilangan bo'lsa
        markup.row(types.InlineKeyboardButton("🏁 TESTNI YAKUNLASH", callback_data="finish_quiz"))
    
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🆕 Test Tuzish", "✍️ Test Ishlash")
    bot.send_message(message.chat.id, "Rush Module Botga xush kelibsiz!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🆕 Test Tuzish")
def start_tuzish(message):
    uid = message.from_user.id
    user_sessions[uid] = {'answers': [None]*45, 'mode': 'set'}
    bot.send_message(message.chat.id, "📝 Test kalitlarini kiriting (1-5 gacha):", 
                     reply_markup=get_test_keyboard(uid, 0))

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    uid = call.from_user.id
    if uid not in user_sessions: return

    data = call.data.split('_')
    
    if data[0] == "ans":
        idx, char, page = int(data[1]), data[2], int(data[3])
        user_sessions[uid]['answers'][idx] = char
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                      reply_markup=get_test_keyboard(uid, page))
        bot.answer_callback_query(call.id) # Loadingni to'xtatadi

    elif data[0] == "page":
        page = int(data[1])
        bot.edit_message_text(f"📝 Test savollari ({page*5+1}-{min(page*5+5, 45)}):", 
                              call.message.chat.id, call.message.message_id, 
                              reply_markup=get_test_keyboard(uid, page))

    elif data[0] == "finish_quiz":
        # Natijani saqlash mantiqi shu yerda...
        bot.send_message(call.message.chat.id, "✅ Test muvaffaqiyatli saqlandi!")
        bot.answer_callback_query(call.id)

if __name__ == '__main__':
    init_db()
    bot.infinity_polling()
