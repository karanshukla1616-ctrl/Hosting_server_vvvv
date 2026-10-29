import sqlite3
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# ================= CONFIGURATION =================
TOKEN = "9113864833:AAFIVUXUCS4Rv-3Yitl6KRd_aTCApbY3BC0"  # Apna BotFather ka token yahan dalein
ADMIN_ID = 8680144387 # Apna Telegram Numeric User ID yahan dalein
CHANNEL_USERNAME = (
    "@sellingboy12"  # Aapka channel jahan user ko join/subscribe karna hai
)

bot = telebot.TeleBot(TOKEN)

# ================= DATABASE SETUP =================
conn = sqlite3.connect("hosting_bot.db", check_same_thread=False)
cursor = conn.cursor()

# 1. Users Table (Approval Status ke sath)
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS bot_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    status TEXT DEFAULT 'PENDING'
)
"""
)

# 2. File Hosting Table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS hosted_files (
    file_code INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    file_type TEXT,
    file_name TEXT
)
"""
)

# 3. Custom Welcomes & Links Table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS group_welcomes (
    chat_id INTEGER PRIMARY KEY,
    welcome_text TEXT
)
"""
)
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS link_blocker (
    chat_id INTEGER PRIMARY KEY,
    status TEXT
)
"""
)
conn.commit()


# ================= HELPER: CHECK CHANNEL MEMBERSHIP =================
def check_channel_join(user_id):
  try:
    member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
    if member.status in ["member", "administrator", "creator"]:
      return True
  except:
    pass
  return False


# ================= START & APPROVAL SYSTEM =================
@bot.message_handler(commands=["start"])
def send_start(message):
  user = message.from_user

  # Check karein agar user database me pehle se hai ya nahi
  cursor.execute("SELECT status FROM bot_users WHERE user_id = ?", (user.id,))
  res = cursor.fetchone()

  if not res:
    # Naya user hai toh PENDING status ke sath save karo aur Admin ko request bhejo
    cursor.execute(
        "INSERT INTO bot_users (user_id, username, status) VALUES (?, ?, 'PENDING')",
        (user.id, user.username or user.first_name),
    )
    conn.commit()

    # Admin ko approval ke liye notification bhejo
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}"),
        InlineKeyboardButton("❌ Deny", callback_data=f"den_{user.id}"),
    )
    try:
      bot.send_message(
          ADMIN_ID,
          f"👤 **New User Approval Request:**\nNaam: {user.first_name}\nUsername: @{user.username or 'None'}\nID: `{user.id}`",
          reply_markup=markup,
          parse_mode="Markdown",
      )
    except Exception as e:
      print(f"Admin ko message bhejne me error: {e}")

    bot.reply_to(
        message,
        "⏳ **Aapka account review me hai!**\nAdmin dwara approve hone ke baad hi aap bot ka use kar payenge. Kripya intezaar karein.",
        parse_mode="Markdown",
    )
    return

  user_status = res[0]

  if user_status == "PENDING":
    bot.reply_to(
        message,
        "⏳ Aapki request abhi **Pending** hai. Admin ke approve karne ka wait karein.",
    )
    return

  if user_status == "DENIED":
    bot.reply_to(
        message, "❌ Aapki request admin dwara **Deny** kar di gayi hai."
    )
    return

  # Agar APPROVED hai, toh channel join check karo
  if not check_channel_join(user.id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📢 Channel Join Karein", url="https://t.me/sellingboy12")
    )
    markup.add(
        InlineKeyboardButton(
            "🔄 Check Status", url=f"https://t.me/{bot.get_me().username}?start=start"
        )
    )
    bot.send_message(
        message.chat.id,
        "⚠️ Bot ko use karne ke liye pehle hamara official channel join karein!",
        reply_markup=markup,
    )
    return

  # Agar sab theek hai (Approved + Channel Joined)
  if " " in message.text:
    file_code = message.text.split()[1]
    if file_code != "start":
      cursor.execute(
          "SELECT file_id, file_type FROM hosted_files WHERE file_code = ?",
          (file_code,),
      )
      f_res = cursor.fetchone()
      if f_res:
        f_id, f_type = f_res[0], f_res[1]
        if f_type == "document":
          bot.send_document(
              message.chat.id, f_id, caption="📁 **Hosted File Downloaded**"
          )
        elif f_type == "photo":
          bot.send_photo(
              message.chat.id, f_id, caption="🖼️ **Hosted Photo Downloaded**"
          )
        elif f_type == "video":
          bot.send_video(
              message.chat.id, f_id, caption="🎬 **Hosted Video Downloaded**"
          )
        return
      else:
        bot.reply_to(message, "❌ File nahi mili ya link invalid hai.")
        return

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton(
          "➕ Bot ko Group me Jodein",
          url=f"https://t.me/{bot.get_me().username}?startgroup=true",
      )
  )

  bot.send_message(
      message.chat.id,
      f"👋 **Namaste {user.first_name}!**\n\nAapka account approved hai. Aap koi bhi file bhej kar link bana sakte hain ya group me welcome/link blocker use kar sakte hain.",
      reply_markup=markup,
      parse_mode="Markdown",
  )


# ================= ADMIN APPROVAL BUTTON CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handling(call):
  if call.from_user.id != ADMIN_ID:
    bot.answer_callback_query(call.id, "❌ Aap admin nahi hain!", show_alert=True)
    return

  data = call.data
  if data.startswith("app_"):
    target_user_id = int(data.split("_")[1])
    cursor.execute(
        "UPDATE bot_users SET status = 'APPROVED' WHERE user_id = ?",
        (target_user_id,),
    )
    conn.commit()

    bot.answer_callback_query(call.id, "✅ User Approved!")
    bot.edit_message_text(
        f"✅ **User Approved Successfully!**\n(ID: `{target_user_id}`)",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
    )
    try:
      bot.send_message(
          target_user_id,
          "🎉 **Aapka account Admin dwara Approve kar diya gaya hai!**\nAb aap `/start` dabakar bot ka use kar sakte hain.",
          parse_mode="Markdown",
      )
    except:
      pass

  elif data.startswith("den_"):
    target_user_id = int(data.split("_")[1])
    cursor.execute(
        "UPDATE bot_users SET status = 'DENIED' WHERE user_id = ?",
        (target_user_id,),
    )
    conn.commit()

    bot.answer_callback_query(call.id, "❌ User Denied!")
    bot.edit_message_text(
        f"❌ **User Request Denied.**\n(ID: `{target_user_id}`)",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
    )
    try:
      bot.send_message(
          target_user_id,
          "❌ Aapka account request admin dwara deny kar diya gaya hai.",
      )
    except:
      pass


# ================= FILE HOSTING (PRIVATE CHAT) =================
@bot.message_handler(
    content_types=["document", "photo", "video"],
    func=lambda m: m.chat.type == "private",
)
def handle_file_hosting(message):
  # Check approval first
  cursor.execute(
      "SELECT status FROM bot_users WHERE user_id = ?", (message.from_user.id,)
  )
  res = cursor.fetchone()
  if not res or res[0] != "APPROVED":
    bot.reply_to(
        message,
        "❌ Aapka account abhi approved nahi hai, isliye file host nahi kar"
        " sakte.",
    )
    return

  file_id, f_type, f_name = "", "", "File"
  if message.document:
    file_id = message.document.file_id
    f_type = "document"
    f_name = message.document.file_name or "Document"
  elif message.photo:
    file_id = message.photo[-1].file_id
    f_type = "photo"
    f_name = "Photo"
  elif message.video:
    file_id = message.video.file_id
    f_type = "video"
    f_name = "Video"

  cursor.execute(
      "INSERT INTO hosted_files (file_id, file_type, file_name) VALUES (?, ?,"
      " ?)",
      (file_id, f_type, f_name),
  )
  conn.commit()
  file_code = cursor.lastrowid

  bot_username = bot.get_me().username
  share_link = f"https://t.me/{bot_username}?start={file_code}"

  bot.reply_to(
      message,
      f"✅ **File Successfully Hosted!**\n\n📁 **Name:** `{f_name}`\n🔗 **Link:**\n`{share_link}`",
      parse_mode="Markdown",
  )


# ================= RUN BOT =================
if __name__ == "__main__":
  print("🚀 Approval & Hosting Bot running successfully...")
  bot.infinity_polling(none_stop=True)
