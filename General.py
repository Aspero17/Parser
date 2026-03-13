from telethon import TelegramClient, events
import re
import asyncio
import json
import os
import sys

# ──────────────────────────────────────────────
# Попытка загрузить секретный config из /data
# ──────────────────────────────────────────────

CONFIG_PATH = "/data/config.py"

if os.path.exists(CONFIG_PATH):
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", CONFIG_PATH)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    API_ID = config.API_ID
    API_HASH = config.API_HASH
    SOURCE_CHANNELS = config.SOURCE_CHANNELS
    TARGET_CHANNEL = config.TARGET_CHANNEL
    REMOVE_PHRASES = config.REMOVE_PHRASES
else:
    print(f"❌ Файл config.py не найден в {CONFIG_PATH}")
    sys.exit(1)

# ──────────────────────────────────────────────
# Директория данных
# ──────────────────────────────────────────────

DATA_DIR = "/data"
SESSION_NAME = "parser_session"
SESSION_FILE = os.path.join(DATA_DIR, f"{SESSION_NAME}.session")
BANNED_FILE  = os.path.join(DATA_DIR, "banned.json")

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
        except Exception as e:
            print(f"Ошибка чтения {BANNED_FILE}: {e}")
    return []

def save_banned_phrases(phrases):
    try:
        os.makedirs(os.path.dirname(BANNED_FILE), exist_ok=True)
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump(phrases, f, ensure_ascii=False, indent=2)
        print(f"Сохранено {len(phrases)} запрещённых фраз в {BANNED_FILE}")
    except Exception as e:
        print(f"Ошибка сохранения {BANNED_FILE}: {e}")

BANNED_PHRASES = load_banned_phrases()

# ──────────────────────────────────────────────
# Клиент Telethon
# ──────────────────────────────────────────────

client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

# ──────────────────────────────────────────────
# Функции очистки
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'https?://\S+', '', text)
    for phrase in BANNED_PHRASES + REMOVE_PHRASES:
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
    print(f"[IN]  {text[:100].replace(chr(10), ' ')}...")
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
# Команды управления banned.json
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