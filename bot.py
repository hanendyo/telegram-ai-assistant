import os
import logging
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from openai import OpenAI

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Konfigurasi Variabel
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [int(x.strip()) for x in os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").split(",") if x.strip()]
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

# Setup DB
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Fungsi Verifikasi User
def is_allowed(update: Update) -> bool:
    return update.effective_user.id in ALLOWED_USERS

# Setup AI Client
if AI_PROVIDER == "openai":
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
else:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def ask_ai(prompt: str) -> str:
    try:
        if AI_PROVIDER == "openai":
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Kamu adalah asisten pribadi pintar. Bantu user mengelola task, meringkas pekerjaan, dan menjawab pertanyaan dengan ramah dan ringkas."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        else:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(
                f"Kamu adalah asisten pribadi pintar. Jawab pertanyaan berikut dengan ramah dan ringkas:\n\n{prompt}"
            )
            return response.text
    except Exception as e:
        return f"Gagal menghubungi AI: {str(e)}"

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Halo Reyhan! Aku adalah asisten pribadimu. Kirimkan pesan atau copy chat WA di sini untuk aku rangkum. Gunakan /help untuk melihat perintah.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    help_text = (
        "Perintah yang tersedia:\n"
        "/tasks - Lihat daftar tugas\n"
        "/add <tugas> - Tambah tugas baru\n"
        "/done <id_tugas> - Selesaikan tugas\n"
        "/clear - Hapus semua tugas selesai"
    )
    await update.message.reply_text(help_text)

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, status FROM tasks")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("Tidak ada tugas saat ini.")
        return
        
    msg = "Daftar Tugas:\n"
    for row in rows:
        icon = "✅" if row[2] == "DONE" else "📌"
        msg += f"{icon} [{row[0]}] {row[1]}\n"
    await update.message.reply_text(msg)

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    task_text = " ".join(context.args)
    if not task_text:
        await update.message.reply_text("Format salah. Contoh: /add Review proposal kerja")
        return
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (task) VALUES (?)", (task_text,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"Berhasil menambahkan tugas: {task_text}")

async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    try:
        task_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Format salah. Contoh: /done 1")
        return
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = 'DONE' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"Tugas [{task_id}] ditandai selesai!")

async def clear_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE status = 'DONE'")
    conn.commit()
    conn.close()
    await update.message.reply_text("Semua tugas selesai telah dibersihkan.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    user_message = update.message.text
    
    # Jika pesan sangat panjang, otomatis asumsikan untuk dirangkum
    if len(user_message) > 200:
        prompt = f"Rangkum obrolan atau teks berikut ini menjadi poin-poin pekerjaan (task list) yang jelas:\n\n{user_message}"
        await update.message.reply_text("Teks cukup panjang, sedang merangkum...")
    else:
        prompt = user_message
        
    ai_response = await ask_ai(prompt)
    await update.message.reply_text(ai_response)

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("done", complete_task))
    app.add_handler(CommandHandler("clear", clear_done))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logging.info("Bot berjalan...")
    app.run_polling()

if __name__ == '__main__':
    main()
