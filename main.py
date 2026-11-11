import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from akipy import Akinator
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("demon-nawaf")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SOLVER_URL = os.getenv("AKIPY_SOLVER_URL", "").strip() or None
games = {}
game_locks = {}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health"):
            self.send_response(404)
            self.end_headers()
            return
        body = b"OK - Demon Nawaf Bot is running"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("Health server listening on port %s", port)


def keyboard_question():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("نعم", callback_data="a:0"),
            InlineKeyboardButton("لا", callback_data="a:1"),
        ],
        [
            InlineKeyboardButton("لا أعرف", callback_data="a:2"),
            InlineKeyboardButton("غالبًا", callback_data="a:3"),
            InlineKeyboardButton("غالبًا لا", callback_data="a:4"),
        ],
        [InlineKeyboardButton("إنهاء اللعبة", callback_data="stop")],
    ])


def keyboard_guess():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("نعم، صحيح", callback_data="guess:yes"),
            InlineKeyboardButton("لا، خطأ", callback_data="guess:no"),
        ],
        [InlineKeyboardButton("إنهاء اللعبة", callback_data="stop")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧞 ابدأ ديمون نواف", callback_data="start")]
    ])
    await update.effective_message.reply_text(
        "أهلًا بك في ديمون نواف!\nفكّر في شخصية، وأنا بحاول أخمّنها.\n"
        "اضغط الزر وخلّنا نبدأ 👇",
        reply_markup=keyboard,
    )


async def begin_game(query, user_id):
    old = games.pop(user_id, None)
    if old is not None:
        try:
            await asyncio.to_thread(old.__exit__, None, None, None)
        except Exception:
            pass

    await query.edit_message_text("🧞 جاري تجهيز ديمون نواف...")
    try:
        aki = Akinator(solver_url=SOLVER_URL) if SOLVER_URL else Akinator()
        await asyncio.to_thread(aki.__enter__)
        await asyncio.to_thread(
            aki.start_game, language="ar", game_mode="c", child_mode=False
        )
        games[user_id] = aki
        game_locks[user_id] = asyncio.Lock()
        await show_current(query, aki)
    except Exception:
        log.exception("Could not start Akinator game")
        await query.edit_message_text(
            "تعذّر الاتصال بأكيناتور حاليًا. جرّب تبدأ لعبة جديدة بعد قليل.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("إعادة المحاولة", callback_data="start")]
            ]),
        )


async def show_current(query, aki):
    if aki.win:
        name = getattr(aki, "name_proposition", None) or "شخصية غير معروفة"
        description = getattr(aki, "description_proposition", None) or ""
        text = f"🎯 أتوقع أن الشخصية هي: *{name}*"
        if description:
            text += f"\n\n_{description}_"
        text += "\n\nهل خمنت صح؟"
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard_guess()
        )
    elif aki.finished or aki.no_question:
        await query.edit_message_text(
            "انتهت الأسئلة وما قدرت أوصل للشخصية 😅",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("العب مرة ثانية", callback_data="start")]
            ]),
        )
        games.pop(query.from_user.id, None)
    else:
        question = aki.question or "هل يمكنك الإجابة عن هذا السؤال؟"
        await query.edit_message_text(
            f"🧞 *ديمون نواف*\n\n{question}",
            parse_mode="Markdown",
            reply_markup=keyboard_question(),
        )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data or ""

    if action == "start":
        await begin_game(query, user_id)
        return

    aki = games.get(user_id)
    if action == "stop":
        if aki is not None:
            games.pop(user_id, None)
            try:
                await asyncio.to_thread(aki.__exit__, None, None, None)
            except Exception:
                pass
        await query.edit_message_text(
            "تم إنهاء اللعبة.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ابدأ لعبة جديدة", callback_data="start")]
            ]),
        )
        return

    if aki is None:
        await query.edit_message_text(
            "ما عندك لعبة شغالة. ابدأ لعبة جديدة 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ابدأ", callback_data="start")]
            ]),
        )
        return

    lock = game_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        try:
            if action.startswith("a:"):
                answer_id = int(action.split(":", 1)[1])
                await asyncio.to_thread(aki.answer, answer_id)
            elif action == "guess:yes":
                await asyncio.to_thread(aki.choose)
                games.pop(user_id, None)
                await query.edit_message_text(
                    f"🎉 عرفت الشخصية!\nكانت: *{aki.name_proposition}*",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("العب مرة ثانية", callback_data="start")]
                    ]),
                )
                return
            elif action == "guess:no":
                await asyncio.to_thread(aki.exclude)
            else:
                return
            await show_current(query, aki)
        except Exception:
            log.exception("Akinator action failed")
            games.pop(user_id, None)
            await query.edit_message_text(
                "صار خطأ أثناء الاتصال بأكيناتور وانتهت اللعبة. حاول تبدأ من جديد.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("لعبة جديدة", callback_data="start")]
                ]),
            )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled Telegram error: %s", context.error)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN environment variable")

    start_health_server()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_error_handler(on_error)
    log.info("Demon Nawaf bot is starting")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
