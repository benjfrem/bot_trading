import os
import requests
from utils.exchange.exchange_utils import log_event

def send_message(text: str) -> None:
    """
    Envoie un message Telegram via le bot configuré.
    Ne doit pas bloquer la logique principale en cas d'erreur.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log_event("❌ Telegram TOKEN ou CHAT_ID non configurés", "error")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        response = requests.post(url, data=payload, timeout=5)
        if not response.ok:
            log_event(f"❌ Échec envoi Telegram: {response.text}", "error")
    except Exception as e:
        log_event(f"❌ Exception envoi Telegram: {e}", "error")
