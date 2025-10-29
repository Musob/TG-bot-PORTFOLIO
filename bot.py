# bot.py
import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BotCommand, BotCommandScopeDefault
from aiogram.filters import Command
from aiogram.enums import ContentType
import aiomysql

# --- Sozlamalar --- #
BOT_TOKEN = "8426552781:AAEwp8xSxxaDJ0iXB0_aIKH0bvtVv6z7_-U"
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = "$Musobek04"
DB_NAME = "test_db"

FILES_DIR = "files"
os.makedirs(FILES_DIR, exist_ok=True)

# --- Helper --- #
def normalize_text(s: str) -> str:
    return s.strip().lower()

# --- QA Service --- #
class QAService:
    def __init__(self, pool):
        self.pool = pool

    async def initialize_tables(self):
        """Jadvallarni yaratish"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Admins jadvali
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS admins (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL UNIQUE,
                        full_name VARCHAR(255),
                        username VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # messages_log jadvali
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS messages_log (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        full_name VARCHAR(255),
                        username VARCHAR(255),
                        message_text TEXT,
                        file_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # qa jadvali
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS qa (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await conn.commit()

    async def is_admin(self, user_id: int):
        """Foydalanuvchi admin ekanligini tekshirish"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM admins WHERE user_id = %s", (user_id,))
                return await cur.fetchone() is not None

    async def add_admin(self, user_id: int, full_name: str, username: str):
        """Yangi admin qo'shish"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(
                        "INSERT INTO admins (user_id, full_name, username) VALUES (%s, %s, %s)",
                        (user_id, full_name, username)
                    )
                    await conn.commit()
                    return True
                except:
                    return False

    async def remove_admin(self, user_id: int):
        """Adminni olib tashlash"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM admins WHERE user_id = %s", (user_id,))
                await conn.commit()
                return cur.rowcount > 0

    async def get_admins(self):
        """Barcha adminlarni olish"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id, full_name, username FROM admins")
                return await cur.fetchall()

    async def find_answer(self, text: str):
        if not text:
            return None
            
        text = normalize_text(text)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT answer FROM qa WHERE LOWER(question) = %s LIMIT 1", (text,)
                )
                row = await cur.fetchone()
                if row:
                    return row[0]
                await cur.execute(
                    "SELECT answer FROM qa WHERE LOWER(question) LIKE %s ORDER BY CHAR_LENGTH(question) DESC LIMIT 1",
                    (f"%{text}%",)
                )
                row = await cur.fetchone()
                if row:
                    return row[0]
        return None

    async def add_qa(self, question: str, answer: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO qa (question, answer) VALUES (%s, %s)", 
                    (question.strip(), answer.strip())
                )
                await conn.commit()

    async def delete_qa(self, question: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM qa WHERE LOWER(question) = %s", 
                    (normalize_text(question),)
                )
                await conn.commit()
                return cur.rowcount > 0

    async def get_all_qa(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT question, answer FROM qa ORDER BY id")
                return await cur.fetchall()

    async def log_message(self, user_id: int, full_name: str, username: str, text: str = None, file_path: str = None):
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO messages_log (user_id, full_name, username, message_text, file_path) VALUES (%s, %s, %s, %s, %s)",
                        (user_id, full_name, username, text, file_path)
                    )
                    await conn.commit()
        except Exception as e:
            print(f"Log yozishda xato: {e}")

    async def get_stats(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM messages_log")
                total_msgs = await cur.fetchone()
                
                await cur.execute("SELECT COUNT(*) FROM messages_log WHERE file_path IS NOT NULL")
                total_imgs = await cur.fetchone()
                
                await cur.execute("SELECT COUNT(*) FROM qa")
                total_qa = await cur.fetchone()
                
                await cur.execute("SELECT COUNT(DISTINCT user_id) FROM messages_log")
                total_users = await cur.fetchone()
                
                await cur.execute("SELECT COUNT(*) FROM admins")
                total_admins = await cur.fetchone()
                
                return {
                    'total_messages': total_msgs[0],
                    'total_images': total_imgs[0],
                    'total_qa': total_qa[0],
                    'total_users': total_users[0],
                    'total_admins': total_admins[0]
                }

# --- MySQL Pool --- #
async def create_pool():
    return await aiomysql.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        charset='utf8mb4',
        autocommit=False,
        minsize=1,
        maxsize=10
    )

# --- Bot Buyruqlarini sozlash --- #
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam ko'rsatish"),
        BotCommand(command="ask", description="Savol berish"),
        BotCommand(command="addqa", description="Yangi savol qo'shish (Admin)"),
        BotCommand(command="deleteqa", description="Savolni o'chirish (Admin)"),
        BotCommand(command="listqa", description="Barcha savollarni ko'rish (Admin)"),
        BotCommand(command="stats", description="Statistika (Admin)"),
        BotCommand(command="admin", description="Admin paneli (Admin)"),
        BotCommand(command="cancel", description="Jarayonni bekor qilish")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

# --- Bot --- #
pending_add = {}
pending_delete = {}
pending_add_admin = {}

async def start_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    try:
        pool = await create_pool()
        qa_service = QAService(pool)
        await qa_service.initialize_tables()
        print("✅ MySQL ga muvaffaqiyatli ulandi")
    except Exception as e:
        print(f"❌ MySQL ga ulanishda xato: {e}")
        return

    # Bot buyruqlarini sozlash
    await set_bot_commands(bot)

    # --- Helper funksiyalar --- #
    async def is_user_admin(user_id: int):
        return await qa_service.is_admin(user_id)

    # --- Handlers --- #
    @dp.message(Command("start", "help"))
    async def cmd_start(message: Message):
        user_id = message.from_user.id
        is_admin = await is_user_admin(user_id)
        
        admin_text = ""
        if is_admin:
            admin_text = (
                "\n\n👑 **Siz admin sifatida tizimga kirgansiz!**\n"
                "🛠 **Admin buyruqlari:**\n"
                "/admin - Admin paneli\n"
                "/addqa - Yangi savol qo'shish\n"
                "/deleteqa - Savolni o'chirish\n"
                "/listqa - Barcha savollarni ko'rish\n"
                "/stats - Statistika\n"
                "/addadmin - Yangi admin qo'shish"
            )
        
        await message.reply(
            "🤖 QA Botga xush kelibsiz!\n\n"
            "📖 **Foydalanish qo'llanmasi:**\n"
            "• Har qanday savolingizni yozing, men javob berishga harakat qilaman\n"
            "• Agar men javob bera olmasam, admin ga murojaat qiling\n\n"
            "🛠 **Asosiy buyruqlar:**\n"
            "/ask - Savol berish\n"
            "/help - Yordam olish" + admin_text
        )

    @dp.message(Command("admin"))
    async def cmd_admin(message: Message):
        if not await is_user_admin(message.from_user.id):
            await message.reply("❌ Bu buyruq faqat admin uchun.")
            return
        
        admins = await qa_service.get_admins()
        admin_list = "\n".join([f"• {full_name} (@{username}) - {user_id}" for user_id, full_name, username in admins])
        
        await message.reply(
            f"👑 **Admin Panel**\n\n"
            f"📊 **Adminlar ro'yxati:**\n{admin_list}\n\n"
            f"🛠 **Admin buyruqlari:**\n"
            f"/addadmin - Yangi admin qo'shish\n"
            f"/addqa - Savol qo'shish\n"
            f"/listqa - Savollarni ko'rish\n"
            f"/stats - Statistika"
        )

    @dp.message(Command("addadmin"))
    async def cmd_addadmin(message: Message):
        if not await is_user_admin(message.from_user.id):
            await message.reply("❌ Bu buyruq faqat admin uchun.")
            return
        
        # Foydalanuvchini reply qilganmi tekshirish
        if not message.reply_to_message:
            await message.reply(
                "👥 **Yangi admin qo'shish:**\n\n"
                "Boshqa foydalanuvchini admin qilish uchun:\n"
                "1. Uning xabarini reply qiling\n"
                "2. /addadmin buyrug'ini yozing\n\n"
                "Yoki admin qilmoqchi bo'lgan foydalanuvchi ID sini yozing:"
            )
            pending_add_admin[message.chat.id] = True
            return
        
        # Reply orqali admin qo'shish
        target_user = message.reply_to_message.from_user
        success = await qa_service.add_admin(target_user.id, target_user.full_name, target_user.username or "")
        
        if success:
            await message.reply(f"✅ @{target_user.username} admin sifatida qo'shildi!")
        else:
            await message.reply("❌ Admin qo'shishda xatolik yoki u allaqachon admin!")

    @dp.message(Command("ask"))
    async def cmd_ask(message: Message):
        await message.reply("❓ Savolingizni yozing va men javob berishga harakat qilaman!")

    @dp.message(Command("addqa"))
    async def cmd_addqa(message: Message):
        if not await is_user_admin(message.from_user.id):
            await message.reply("❌ Bu buyruq faqat admin uchun.")
            return
        
        pending_add[message.chat.id] = {'stage': 1, 'question': None}
        await message.reply(
            "📝 **Yangi savol qo'shish:**\n"
            "1. Avval savolni yozing\n"
            "2. Keyin javobni yozing\n\n"
            "📥 Savolni yozing:"
        )

    @dp.message(Command("deleteqa"))
    async def cmd_deleteqa(message: Message):
        if not await is_user_admin(message.from_user.id):
            await message.reply("❌ Bu buyruq faqat admin uchun.")
            return
        
        pending_delete[message.chat.id] = True
        await message.reply("🗑 O'chirmoqchi bo'lgan savolni yozing:")

    @dp.message(Command("listqa"))
    async def cmd_listqa(message: Message):
        if not await is_user_admin(message.from_user.id):
            await message.reply("❌ Bu buyruq faqat admin uchun.")
            return
        
        try:
            qa_list = await qa_service.get_all_qa()
            if not qa_list:
                await message.reply("📭 Hozircha savol-javoblar mavjud emas.")
                return
            
            response = "📚 **Barcha savol-javoblar:**\n\n"
            for i, (question, answer) in enumerate(qa_list, 1):
                qa_text = f"{i}. **Savol:** {question}\n   **Javob:** {answer}\n\n"
                if len(response + qa_text) > 4000:
                    await message.reply(response)
                    response = qa_text
                else:
                    response += qa_text
            
            await message.reply(response)
        except Exception as e:
            await message.reply(f"❌ Xatolik: {e}")

    @dp.message(Command("stats"))
    async def cmd_stats(message: Message):
        if not await is_user_admin(message.from_user.id):
            await message.reply("❌ Bu buyruq faqat admin uchun.")
            return
        
        try:
            stats = await qa_service.get_stats()
            stats_text = (
                "📊 **Bot Statistika:**\n\n"
                f"• 👥 Foydalanuvchilar: {stats['total_users']}\n"
                f"• 💬 Jami xabarlar: {stats['total_messages']}\n"
                f"• 🖼 Jami rasmlar: {stats['total_images']}\n"
                f"• ❓ Savol-javoblar: {stats['total_qa']}\n"
                f"• 👑 Adminlar: {stats['total_admins']}\n\n"
                f"📈 **Faollik:** {stats['total_messages']} ta xabar"
            )
            await message.reply(stats_text)
        except Exception as e:
            await message.reply(f"❌ Statistika olishda xato: {e}")

    @dp.message(Command("cancel"))
    async def cmd_cancel(message: Message):
        chat_id = message.chat.id
        if chat_id in pending_add:
            pending_add.pop(chat_id)
            await message.reply("✅ Savol qo'shish bekor qilindi.")
        elif chat_id in pending_delete:
            pending_delete.pop(chat_id)
            await message.reply("✅ Savol o'chirish bekor qilindi.")
        elif chat_id in pending_add_admin:
            pending_add_admin.pop(chat_id)
            await message.reply("✅ Admin qo'shish bekor qilindi.")
        else:
            await message.reply("ℹ️ Hech qanday jarayon yo'q.")

    @dp.message(F.content_type == ContentType.TEXT)
    async def handle_text(message: Message):
        try:
            chat_id = message.chat.id
            user_id = message.from_user.id
            text = message.text

            # Log yozish
            await qa_service.log_message(
                user_id=user_id,
                full_name=message.from_user.full_name or "",
                username=message.from_user.username or "",
                text=text
            )

            # Admin qo'shish (ID orqali)
            if chat_id in pending_add_admin and await is_user_admin(user_id):
                pending_add_admin.pop(chat_id)
                try:
                    target_user_id = int(text.strip())
                    # Bu yerda target_user_id ga mos foydalanuvchi ma'lumotlarini olish kerak
                    # Hozircha oddiy versiya
                    success = await qa_service.add_admin(target_user_id, "Unknown", "unknown")
                    if success:
                        await message.reply(f"✅ {target_user_id} admin sifatida qo'shildi!")
                    else:
                        await message.reply("❌ Admin qo'shishda xatolik!")
                except ValueError:
                    await message.reply("❌ Noto'g'ri ID format! Faqat raqam kiriting.")
                return

            # Savol o'chirish
            if chat_id in pending_delete and await is_user_admin(user_id):
                pending_delete.pop(chat_id)
                success = await qa_service.delete_qa(text)
                if success:
                    await message.reply("✅ Savol muvaffaqiyatli o'chirildi!")
                else:
                    await message.reply("❌ Savol topilmadi yoki o'chirilmadi.")
                return

            # Savol qo'shish
            if chat_id in pending_add and await is_user_admin(user_id):
                state = pending_add[chat_id]
                if state['stage'] == 1:
                    state['question'] = text.strip()
                    state['stage'] = 2
                    await message.reply("📝 Endi javobni yozing:")
                    return
                elif state['stage'] == 2:
                    await qa_service.add_qa(state['question'], text.strip())
                    await message.reply("✅ Savol-javob muvaffaqiyatli qo'shildi!")
                    pending_add.pop(chat_id)
                    return

            # Oddiy savolga javob
            ans = await qa_service.find_answer(text)
            if ans:
                await message.reply(f"💡 {ans}")
            else:
                await message.reply("❌ Kechirasiz, men buni bilmayman.")

        except Exception as e:
            print(f"❌ Matn qayta ishlashda xato: {e}")
            await message.reply("❌ Xatolik yuz berdi.")

    # Rasm handler va boshqalar...
    @dp.message(F.content_type == ContentType.PHOTO)
    async def handle_photo(message: Message):
        try:
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = os.path.join(FILES_DIR, f"{photo.file_id}.jpg")
            await bot.download_file(file.file_path, destination=file_path)
            
            text = message.caption or None
            await qa_service.log_message(
                user_id=message.from_user.id,
                full_name=message.from_user.full_name or "",
                username=message.from_user.username or "",
                text=text,
                file_path=file_path
            )
            
            await message.reply("✅ Rasm saqlandi!")
            
        except Exception as e:
            print(f"❌ Rasm qayta ishlashda xato: {e}")
            await message.reply("❌ Rasmni qayta ishlashda xatolik.")

    print("🤖 Bot ishga tushdi...")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        print(f"❌ Bot ishga tushirishda xato: {e}")
    finally:
        if 'pool' in locals():
            pool.close()
            await pool.wait_closed()
        await bot.session.close()

if __name__ == "__main__":
    print("🚀 Botni ishga tushirish...")
    asyncio.run(start_bot())

