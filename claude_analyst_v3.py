"""
claude_analyst_v3.py
--------------------
Analista LLM con web search integrato via Anthropic API.
Sostituisce Groq/Llama (v1/v2) con Claude + strumento web_search.

Upgrade rispetto a v1/v2:
- Claude cerca autonomamente news, earnings date, consensus analisti
- Non serve pre-fetching esterno di macro_context/news_context
- Esclude automaticamente titoli con earnings imminenti o news negative
- Produce gli stessi segnali BUY del sistema esistente, ma con filtro qualitativo reale

Uso:
    from claude_analyst_v3 import generate_report
    report = generate_report(filtered_snapshot, "24/05/2026")
"""

import os
import json
import anthropic

# --- Configurazione -----------------------------------------------------------
MODEL      = "claude-haiku-4-5"   # Veloce e economico per uso settimanale
MAX_TOKENS = 2500
MAX_SEARCHES = 25   # max web search calls per sessione (limite costo/velocita)

# --- System prompt ------------------------------------------------------------
SYSTEM_PROMPT = """Sei un analista finanziario senior specializzato in equity trading settimanale.
Ricevi snapshot tecnico pre-filtrato di azioni e produci segnali BUY per la settimana.

HAI ACCESSO A WEB SEARCH: usalo per arricchire l'analisi con dati fondamentali aggiornati.

WORKFLOW OBBLIGATORIO:
1. Identifica i 5-6 candidati tecnici piu' promettenti dallo snapshot
2. Per ciascuno cerca con web_search:
   - News recenti (query: "TICKER stock news this week")
   - Data prossimo earnings (query: "TICKER earnings date 2026")
   - Consensus analisti (query: "TICKER analyst rating target price")
3. Filtra: escludi titoli con earnings nei prossimi 10 giorni o news negative importanti
4. Seleziona max 3 segnali BUY finali

REGOLE FERREE:
- Max 3 segnali BUY in totale (0 e' accettabile se non ci sono setup validi)
- Escludi titoli con earnings < 10 giorni (rischio evento non prezzabile)
- Escludi titoli con notizie negative significative (guidance tagliata, CEO dimesso, scandali)
- Setup tecnico richiesto: RSI < 70, MACD rialzista, sopra almeno una SMA
- SL = 1.5x ATR settimanale dal prezzo di entrata
- TP = 4.5x ATR settimanale (R:R 3:1)

FORMATO OBBLIGATORIO per ogni segnale BUY:

*[BUY] TICKER*
Prezzo: X | Var. sett.: +X%
RSI: X | MACD: rialzista | SMA: sopra 20/50
News: [headline chiave trovata o "Nessuna news rilevante"]
Earnings: [data prossimo report es. "15 Aug 2026" o "N/D"]
Consensus: [es. "18 Buy / 5 Hold | Target: $245" o "N/D"]
Setup: [1-2 righe — motivo tecnico + qualitativo del trade]
SL: X (~1.5x ATR weekly)
TP: X (~4.5x ATR weekly, R:R 3:1)
R:R: 3:1

Se nessun titolo merita BUY: scrivi solo "Nessun setup BUY convincente questa settimana."
Concludi sempre con: Sentiment: Risk-On / Risk-Off / Misto"""

# --- Template prompt utente ---------------------------------------------------
USER_TEMPLATE = """Snapshot di mercato — settimana del {date}

{count} asset hanno superato il pre-filtro tecnico su circa 253 analizzati (USA + Europa):

{snapshot_json}

Analizza i candidati con web search, applica il filtro qualitativo e seleziona max 3 segnali BUY.
Sii selettivo: meglio 0 segnali che segnali deboli."""


# --- Funzioni -----------------------------------------------------------------

def get_api_key() -> str:
    """Cerca ANTHROPIC_API_KEY in variabile d'ambiente o config.py."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        from config import ANTHROPIC_API_KEY
        return ANTHROPIC_API_KEY
    except (ImportError, AttributeError):
        pass
    raise ValueError(
        "ANTHROPIC_API_KEY non trovata.\n"
        "Imposta la variabile d'ambiente ANTHROPIC_API_KEY "
        "oppure aggiungila a config.py / .env"
    )


def extract_text(response) -> str:
    """Estrae il testo finale dalla risposta Anthropic (ignora tool_use blocks)."""
    parts = []
    for block in response.content:
        if hasattr(block, "text") and block.text:
            parts.append(block.text)
    return "\n".join(parts).strip()


SYSTEM_PROMPT_JSON = """Sei un analista finanziario senior specializzato in equity trading settimanale.
Ricevi snapshot tecnico pre-filtrato di azioni e produci segnali BUY strutturati.

HAI ACCESSO A WEB SEARCH: usalo per trovare news recenti, data prossimo earnings e consensus analisti.

WORKFLOW OBBLIGATORIO:
1. Identifica i 5-6 candidati tecnici piu' promettenti dallo snapshot
2. Per ciascuno cerca con web_search: news recenti, prossimi earnings, consensus analisti
3. Filtra: escludi titoli con earnings < 10 giorni o news negative importanti
4. Seleziona max {max_positions} segnali BUY finali

REGOLE FERREE:
- Max {max_positions} segnali BUY (0 e' accettabile)
- RSI < 70, MACD rialzista, sopra almeno una SMA
- Escludi earnings imminenti e news negative significative

Rispondi SOLO con JSON array valido (nessun testo fuori):
[
  {{
    "ticker": "AAPL",
    "category": "USA",
    "entry_price": 185.50,
    "sl": 176.50,
    "setup": "Motivazione 1 riga"
  }}
]
Se nessun segnale convincente: []"""

USER_TEMPLATE_JSON = """Snapshot di mercato — settimana del {date}

{count} asset hanno superato il pre-filtro tecnico:

{snapshot_json}

Analizza con web search, filtra, seleziona max {max_positions} segnali BUY. Rispondi SOLO con JSON array."""


def generate_signals(snapshot: dict, date: str, max_positions: int = 3) -> list:
    """
    Restituisce List[dict] con segnali BUY selezionati dall'LLM con web search.
    Ogni dict: ticker, category, entry_price, sl, setup.
    """
    client = anthropic.Anthropic(api_key=get_api_key())
    count  = sum(len(v) for v in snapshot.values())

    system = SYSTEM_PROMPT_JSON.format(max_positions=max_positions)
    user_msg = USER_TEMPLATE_JSON.format(
        date=date,
        count=count,
        snapshot_json=json.dumps(snapshot, indent=2, ensure_ascii=False),
        max_positions=max_positions,
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[{
                "type":     "web_search_20250305",
                "name":     "web_search",
                "max_uses": MAX_SEARCHES,
            }],
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = extract_text(response).strip()
        try:
            signals = json.loads(raw)
            if isinstance(signals, list):
                return signals[:max_positions]
        except json.JSONDecodeError:
            start, end = raw.find("["), raw.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])[:max_positions]
                except Exception:
                    pass
    except Exception as e:
        print(f"[claude_analyst_v3] generate_signals errore: {e}")
    return []


def generate_report(snapshot: dict, date: str) -> str:
    """
    Genera il report BUY settimanale con analisi qualitativa via web search.

    Args:
        snapshot: dict con chiavi "USA", "EUROPE", "INDICES" — output di pre_filter_snapshot()
        date:     stringa data leggibile es. "24/05/2026"

    Returns:
        Stringa con report formattato (segnali BUY + sentiment)
    """
    client = anthropic.Anthropic(api_key=get_api_key())
    count  = sum(len(v) for v in snapshot.values())

    user_msg = USER_TEMPLATE.format(
        date=date,
        count=count,
        snapshot_json=json.dumps(snapshot, indent=2, ensure_ascii=False),
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[{
                "type":     "web_search_20250305",
                "name":     "web_search",
                "max_uses": MAX_SEARCHES,
            }],
            messages=[{"role": "user", "content": user_msg}],
        )
        result = extract_text(response)
        return result if result else "Nessun setup BUY convincente questa settimana."

    except Exception as e:
        # Fallback: nessun web search, solo analisi tecnica
        print(f"[claude_analyst_v3] Errore API: {e} — fallback a analisi solo tecnica")
        try:
            response_fallback = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT.replace(
                    "HAI ACCESSO A WEB SEARCH: usalo per arricchire l'analisi con dati fondamentali aggiornati.",
                    "NON HAI ACCESSO A WEB SEARCH. Analizza solo i dati tecnici ricevuti."
                ).replace(
                    "WORKFLOW OBBLIGATORIO:\n1. Identifica i 5-6 candidati tecnici piu' promettenti dallo snapshot\n2. Per ciascuno cerca con web_search:\n   - News recenti (query: \"TICKER stock news this week\")\n   - Data prossimo earnings (query: \"TICKER earnings date 2026\")\n   - Consensus analisti (query: \"TICKER analyst rating target price\")\n3. Filtra: escludi titoli con earnings nei prossimi 10 giorni o news negative importanti\n4. Seleziona max 3 segnali BUY finali",
                    "WORKFLOW: Seleziona i 3 migliori candidati tecnici dallo snapshot e genera i segnali BUY."
                ),
                messages=[{"role": "user", "content": user_msg}],
            )
            return extract_text(response_fallback) or "Nessun setup BUY convincente questa settimana."
        except Exception as e2:
            return f"Errore generazione report: {e2}"
