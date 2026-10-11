import asyncio
import logging
import sys

# Đảm bảo UTF-8 cho stdout/stderr trên Windows để in emoji không bị lỗi
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config.settings import settings
from database.db import init_db
from handlers import common, budget, report, expense
from schedulers.reminders import setup_scheduler

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    """Hàm khởi chạy chính của Telegram Bot."""
    if not settings.telegram_bot_token:
        logger.error("Chua cau hinh TELEGRAM_BOT_TOKEN trong file .env!")
        print("\n[LỖI]: Vui lòng tạo file .env từ .env.example và điền TELEGRAM_BOT_TOKEN cùng GROQ_API_KEY trước khi chạy!\n")
        return

    if not settings.groq_api_key:
        logger.warning("Chua cau hinh GROQ_API_KEY. Tinh nang nhan dien AI co the khong hoat dong.")

    # 1. Khởi tạo Database
    logger.info("Dang khoi tao co so du lieu SQLite...")
    await init_db()
    logger.info("Co so du lieu da san sang.")

    # 2. Khởi tạo Bot & Dispatcher
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    # 3. Đăng ký các Router (Thứ tự quan trọng: common -> budget -> report -> expense cuối cùng)
    dp.include_router(common.router)
    dp.include_router(budget.router)
    dp.include_router(report.router)
    dp.include_router(expense.router)

    # 4. Khởi chạy Scheduler nhắc nhở
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info(f"Da khoi chay lich nhac nho luc {settings.reminder_hour:02d}:{settings.reminder_minute:02d} moi toi.")

    # 5. Xóa webhook tồn đọng và bắt đầu Polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot dang chay va lang nghe tin nhan tren Telegram...")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot da dung.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot da tat.")
