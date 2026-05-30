import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_telegram(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Invia un messaggio Telegram via REST API (nessun polling, nessun conflitto).

    parse_mode: "Markdown" (default) | "HTML" | "" (plain text)
    In caso di errore 400 (parse error Markdown), ritenta senza parse_mode.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERRORE notifier: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID non configurati "
              "(controlla il file .env nella cartella del bot)")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Telegram ha un limite di 4096 caratteri per messaggio
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]

    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text":    chunk,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(url, json=payload, timeout=15)
        except requests.RequestException as e:
            print(f"Errore di rete Telegram: {e}")
            return False

        if not response.ok:
            err = response.json() if response.content else {}
            code = err.get("error_code", response.status_code)
            desc = err.get("description", response.text[:200])
            print(f"Errore Telegram {code}: {desc}")

            # Se errore di parsing Markdown, riprova in plain text
            if code == 400 and parse_mode:
                print("  Ritento senza parse_mode (plain text)...")
                payload.pop("parse_mode", None)
                try:
                    r2 = requests.post(url, json=payload, timeout=15)
                    if r2.ok:
                        print("  Inviato in plain text.")
                        continue
                    else:
                        print(f"  Fallito anche in plain text: {r2.text[:200]}")
                except requests.RequestException as e2:
                    print(f"  Errore di rete (retry): {e2}")
            return False

    return True
