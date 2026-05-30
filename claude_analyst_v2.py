"""
Versione v2 dell'analista LLM — integra contesto macro e notizie recenti.
Usa lo stesso modello Groq di v1 ma con prompt arricchito.
"""

from groq import Groq
import json
from config import GROQ_API_KEY

SYSTEM_PROMPT = """Sei un analista finanziario esperto che integra analisi tecnica, analisi macro e notizie recenti.
Ogni lunedi ricevi: (1) il contesto macro e settoriale della settimana, (2) notizie recenti sui candidati, (3) uno snapshot tecnico pre-filtrato.

REGOLE FERREE:
- Seleziona DA 0 A 3 segnali BUY in totale (su tutte le categorie insieme).
- Se non trovi setup convincenti, scrivi solo "Nessun setup BUY convincente questa settimana."
- Non mandare mai segnali SELL o WATCH nel report finale.
- Setup tecnico solido e' necessario ma non sufficiente: il contesto macro e le notizie devono supportare il trade.
- In regime Risk-Off (VIX > 25): preferisci settori difensivi (energia, healthcare, difesa), evita growth/tech speculativo.
- In regime Risk-On: puoi includere AI/tech/robotica con buon setup tecnico.
- Dai priorita' ad azioni nei settori con momentum settimanale positivo.
- Se ci sono notizie negative significative su un titolo (causa legale, earnings mancati, profit warning, CEO dimesso), escludilo anche se tecnicamente valido — segnalalo brevemente.
- Ogni segnale deve avere: RSI non in ipercomprato (< 70), MACD favorevole, prezzo sopra almeno una SMA.
- Usa SL a circa 1.5x ATR settimanale e TP a circa 4.5x ATR (R:R 3:1).

Formato OBBLIGATORIO per ogni segnale BUY:

*[BUY] TICKER*
Prezzo: X | Var. sett.: +X%
RSI: X | MACD: rialzista | SMA: sopra 20/50
Settore: X | Notizie: positive/neutrali/negative
Setup: [1-2 righe max — includi perche' il macro supporta questo trade]
SL: X (~1.5x ATR weekly)
TP: X (~4.5x ATR weekly, R:R 3:1)
R:R: 3:1
Uscita: al raggiungimento di SL o TP (nessun limite temporale)

Concludi sempre con una riga: Sentiment: Risk-On / Risk-Off / Misto"""

USER_TEMPLATE = """Snapshot di mercato — settimana del {date}

{macro_context}

{news_context}

=== CANDIDATI TECNICI ===
{count} asset hanno superato il pre-filtro tecnico su {total_universe} analizzati:

{snapshot_json}

Analizza tutti i candidati integrando contesto macro, notizie e tecnica. Seleziona al massimo 3 segnali BUY. Sii selettivo: meglio 0 segnali che segnali deboli."""


SYSTEM_PROMPT_JSON = """Sei un analista finanziario esperto. Ogni lunedi ricevi contesto macro, notizie e snapshot tecnico.

REGOLE:
- Seleziona DA 0 A {max_positions} segnali BUY (su tutte le categorie).
- Setup tecnico solido + macro favorevole + notizie non negative = segnale valido.
- In Risk-Off (VIX>30): solo settori difensivi. In Risk-On: puoi includere tech/AI.
- RSI < 70, MACD favorevole, prezzo sopra almeno una SMA.
- Se notizie negative significative su un titolo: escludilo.

Rispondi SOLO con un array JSON valido (nessun testo fuori):
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

USER_TEMPLATE_JSON = """Settimana del {date}

{macro_context}

{news_context}

=== CANDIDATI TECNICI ({count} su {total}) ===
{snapshot_json}

Seleziona al massimo {max_positions} segnali BUY. Rispondi SOLO con JSON array."""


def generate_signals(
    snapshot: dict,
    date: str,
    macro_context: str = "",
    news_context: str = "",
    max_positions: int = 3,
) -> list:
    """Restituisce List[dict] con segnali BUY via Groq (gratuito). Usata da main_v3.py."""
    import json as _json
    client = Groq(api_key=GROQ_API_KEY)
    count = sum(len(v) for v in snapshot.values())

    system = SYSTEM_PROMPT_JSON.format(max_positions=max_positions)
    prompt = USER_TEMPLATE_JSON.format(
        date=date,
        macro_context=macro_context or "(non disponibile)",
        news_context=news_context or "(non disponibile)",
        count=count,
        total=247,
        snapshot_json=_json.dumps(snapshot, indent=2, ensure_ascii=False),
        max_positions=max_positions,
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=800,
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    try:
        signals = _json.loads(raw)
        if isinstance(signals, list):
            return signals[:max_positions]
    except _json.JSONDecodeError:
        start, end = raw.find("["), raw.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return _json.loads(raw[start:end])[:max_positions]
            except Exception:
                pass
    return []


def generate_report(snapshot: dict, date: str, macro_context: str = "", news_context: str = "") -> str:
    client = Groq(api_key=GROQ_API_KEY)

    count = sum(len(v) for v in snapshot.values())
    prompt = USER_TEMPLATE.format(
        date=date,
        macro_context=macro_context or "(contesto macro non disponibile)",
        news_context=news_context or "(notizie non disponibili)",
        count=count,
        total_universe="207",
        snapshot_json=json.dumps(snapshot, indent=2, ensure_ascii=False),
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1500,
        temperature=0.3,
    )

    return response.choices[0].message.content
