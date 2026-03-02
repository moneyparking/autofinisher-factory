#!/usr/bin/env python3
import os
import sys
import requests
import argparse

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    if not TOKEN or not CHAT_ID:
        print("[!] Ошибка: Нет ключей Telegram в .env")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Уведомление в Telegram успешно отправлено!")
    except Exception as e:
        print(f"[!] Ошибка отправки в Telegram: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Путь к файлу с текстом отчета")
    args = parser.parse_args()

    if args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            message = f.read()
    else:
        message = "🟢 <b>Autofinisher Factory</b>: Тестовое сообщение."

    send_telegram_message(message)

if __name__ == "__main__":
    main()
