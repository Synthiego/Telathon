"""
Binance Red Packet Monitor — Railway Edition
=============================================
Monitors a Telegram group/channel for Binance red packet links
from specific senders and logs alerts (visible in Railway dashboard).

Environment Variables:
    API_ID           - Telegram API ID (integer)
    API_HASH         - Telegram API hash (string)
    PHONE            - Your Telegram phone number e.g. +91XXXXXXXXXX
    WATCH_CHATS      - Comma-separated chats e.g. @group1,@group2
    ALLOWED_SENDERS  - Comma-separated senders e.g. @user1,123456789
                       Leave empty to monitor ALL senders
    COOLDOWN_SECONDS - (optional) Default: 60
    SESSION_B64      - Base64-encoded .session file (generated locally first)
"""

import asyncio
import base64
import os
import re
import time
from datetime import datetime

try:
    from telethon import TelegramClient, events
except ImportError:
    raise ImportError("Run: pip install telethon")

# ── Load session from env (Railway) ───────────────────────────────────────────
session_b64 = os.environ.get("SESSION_B64")
if session_b64:
    with open("redpacket_session.session", "wb") as f:
        f.write(base64.b64decode(session_b64))
    print("✅ Session loaded from SESSION_B64 env var")

# ── Config ─────────────────────────────────────────────────────────────────────
API_ID   = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
PHONE    = os.environ["PHONE"]

WATCH_CHATS     = [c.strip() for c in os.environ["WATCH_CHATS"].split(",") if c.strip()]
_senders_raw    = os.environ.get("ALLOWED_SENDERS", "")
ALLOWED_SENDERS = [s.strip() for s in _senders_raw.split(",") if s.strip()]
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "60"))

# ── Red packet URL pattern ─────────────────────────────────────────────────────
REDPACKET_PATTERN = re.compile(
    r"https?://(?:www\.)?binance\.(?:com|me)/en/red-packet/[A-Za-z0-9\-_?=&]+",
    re.IGNORECASE
)

# ── State ──────────────────────────────────────────────────────────────────────
seen_urls: dict[str, float] = {}


def is_allowed_sender(sender) -> bool:
    if not ALLOWED_SENDERS:
        return True
    if sender is None:
        return False
    sender_id       = getattr(sender, "id", None)
    sender_username = (getattr(sender, "username", None) or "").lower()
    for allowed in ALLOWED_SENDERS:
        allowed = allowed.strip()
        if allowed.startswith("@"):
            if sender_username == allowed.lstrip("@").lower():
                return True
        else:
            try:
                if sender_id == int(allowed):
                    return True
            except ValueError:
                pass
    return False


def alert(url: str, sender_name: str, chat_name: str):
    now = time.time()
    if url in seen_urls and (now - seen_urls[url]) < COOLDOWN_SECONDS:
        return
    seen_urls[url] = now
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"  🎁 BINANCE RED PACKET DETECTED")
    print(f"  Time   : {ts}")
    print(f"  From   : {sender_name}")
    print(f"  Chat   : {chat_name}")
    print(f"  Link   : {url}")
    print(f"{'='*55}\n")


async def main():
    client = TelegramClient("redpacket_session", API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    print(f"✅ Logged in as : {me.first_name} (@{me.username})")
    print(f"👀 Watching     : {WATCH_CHATS}")
    print(f"🎯 Senders      : {ALLOWED_SENDERS or 'ALL'}")
    print(f"⏱  Cooldown     : {COOLDOWN_SECONDS}s")
    print("\nMonitor running — waiting for red packets...\n")

    @client.on(events.NewMessage(chats=WATCH_CHATS))
    async def handler(event):
        text = event.message.message or ""
        urls = REDPACKET_PATTERN.findall(text)
        if not urls:
            return

        sender = await event.get_sender()
        if not is_allowed_sender(sender):
            return

        sender_name = (
            f"@{sender.username}" if getattr(sender, "username", None)
            else getattr(sender, "first_name", str(getattr(sender, "id", "?")))
        )
        chat = await event.get_chat()
        chat_name = getattr(chat, "title", None) or getattr(chat, "username", "Unknown")

        for url in urls:
            alert(url, sender_name, chat_name)

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
