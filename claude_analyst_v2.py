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
