from telethon import TelegramClient, events
import re
import asyncio
import json
import os

# ──────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────

API_ID = 24146111
API_HASH = "dc7ef3f00ab268edd8fc8f46ec464456"

SOURCE_CHANNELS = [-1001754252633]               # откуда парсим
TARGET_CHANNEL = -1001916023629                  # куда постим

# Фразы, которые полностью удаляем из поста
REMOVE_PHRASES = [
    "👉 Топор +18. Подписаться",
    "👉 Топор Live. Подписаться",
]

# Директория данных в Amvera (монтируется как /data)
DATA_DIR = "/data"

# Пути к файлам внутри /data (или локально в текущей папке, если /data нет)
SESSION_NAME = "parser_session"                  # имя сессии без .session
SESSION_FILE = os.path.join(DATA_DIR, f"{SESSION_NAME}.session")
BANNED_FILE  = os.path.join(DATA_DIR, "banned.json")

# Если /data недоступна — fallback на текущую директорию
if not os.path.exists(DATA_DIR):
    print(f"Директория {DATA_DIR} не найдена → используем текущую папку")
    SESSION_FILE = f"{SESSION_NAME}.session"
    BANNED_FILE = "data/banned.json"

# ──────────────────────────────────────────────
# Работа с banned.json
# ──────────────────────────────────────────────

def load_banned_phrases():
    if os.path.exists(BANNED_FILE):
        try:
            with open(BANNED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    print(f"{BANNED_FILE} содержит не список → пустой")
                    return []
        except Exception as e:
            print(f"Ошибка чтения {BANNED_FILE}: {e}")
            return []
    else:
        print(f"Файл {BANNED_FILE} не найден → пустой список")
        return []

def save_banned_phrases(phrases):
    try:
        os.makedirs(os.path.dirname(BANNED_FILE), exist_ok=True)  # создаём /data если нужно
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump(phrases, f, ensure_ascii=False, indent=2)
        print(f"Сохранено {len(phrases)} запрещённых фраз в {BANNED_FILE}")
    except Exception as e:
        print(f"Ошибка сохранения {BANNED_FILE}: {e}")

# Загружаем запрещённые фразы при старте
BANNED_PHRASES = load_banned_phrases()

# ──────────────────────────────────────────────
# Клиент Telethon с сессией в /data
# ──────────────────────────────────────────────

client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

# ──────────────────────────────────────────────
# Функции очистки
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'https?://\S+', '', text)

    for phrase in BANNED_PHRASES:
        text = text.replace(phrase, '')

    for phrase in REMOVE_PHRASES:
        text = text.replace(phrase, '')

    text = re.sub(r'\[\s*\]\s*\(\s*[^)]*\s*\)?', '', text)
    text = re.sub(r'\[\s*?\]\s*', '', text)
    text = re.sub(r'\(\s*?\)', '', text)
    text = text.replace('](', '').replace('([', '').replace('])', '')

    text = re.sub(r'\s*\n\s*', '\n', text)
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip()

def is_banned(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(p.lower() in lower for p in BANNED_PHRASES)

# ──────────────────────────────────────────────
# Обработчик сообщений
# ──────────────────────────────────────────────

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    msg = event.message
    text = msg.text or ""

    preview = text[:100].replace('\n', ' ').replace('\r', ' ')
    print(f"[IN]  {preview}...")

    if is_banned(text):
        print("     → пропущен (запрещённая фраза)")
        return

    text = clean_text(text)

    if not text and not msg.media:
        print("     → пропуск: пустой текст без медиа")
        return

    try:
        await client.send_message(
            TARGET_CHANNEL,
            text,
            parse_mode='md',
            file=msg.media,
            link_preview=False,
            silent=True
        )
        print("     → отправлено")
    except Exception as e:
        print(f"     → ошибка: {str(e)}")

# ──────────────────────────────────────────────
# Команды управления запрещёнными фразами
# ──────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r'^/ban\s+(.+)$'))
async def cmd_ban(event):
    phrase = event.pattern_match.group(1).strip()
    if not phrase:
        await event.reply("Укажи фразу после /ban")
        return
    if phrase in BANNED_PHRASES:
        await event.reply("Уже в бан-листе")
        return
    BANNED_PHRASES.append(phrase)
    save_banned_phrases(BANNED_PHRASES)
    await event.reply(f"✅ Добавлено в бан: `{phrase}`\nВсего запретов: {len(BANNED_PHRASES)}")

@client.on(events.NewMessage(pattern=r'^/unban\s+(.+)$'))
async def cmd_unban(event):
    phrase = event.pattern_match.group(1).strip()
    if phrase in BANNED_PHRASES:
        BANNED_PHRASES.remove(phrase)
        save_banned_phrases(BANNED_PHRASES)
        await event.reply(f"❌ Убрано из бана: `{phrase}`\nВсего запретов: {len(BANNED_PHRASES)}")
    else:
        await event.reply("Не найдено в бан-листе")

@client.on(events.NewMessage(pattern=r'^/listban$'))
async def cmd_listban(event):
    if not BANNED_PHRASES:
        await event.reply("Бан-лист пуст")
        return
    lines = "\n".join(f"• {p}" for p in BANNED_PHRASES)
    await event.reply(f"Запрещённые фразы ({len(BANNED_PHRASES)}):\n{lines}")

# ──────────────────────────────────────────────
# Запуск
# ──────────────────────────────────────────────

async def main():
    await client.start()
    me = await client.get_me()
    print(f"Бот запущен: {me.first_name} (@{me.username or 'нет @'})")
    print(f"Сессия: {SESSION_FILE}")
    print(f"Загружено {len(BANNED_PHRASES)} запрещённых фраз из {BANNED_FILE}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())