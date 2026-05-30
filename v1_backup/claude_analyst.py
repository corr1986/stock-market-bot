from groq import Groq
import json
from config import GROQ_API_KEY

SYSTEM_PROMPT = """Sei un analista finanziario esperto di trading algoritmico e analisi tecnica.
Ogni giorno lavorativo ricevi uno snapshot pre-filtrato dei mercati: i migliori candidati rialzisti tra indici globali, azioni USA e azioni europee.
Il trader opera manualmente solo in BUY (long).

REGOLE FERREE:
- Seleziona DA 0 A 3 segnali BUY in totale (su tutte le categorie insieme).
- Se non trovi setup rialzisti convincenti, manda 0 segnali — scrivi solo "Nessun setup BUY convincente questa settimana."
- Non mandare mai segnali SELL o WATCH nel report finale.
- Ogni segnale deve avere un setup tecnico chiaro: RSI non in ipercomprato, MACD favorevole, prezzo sopra almeno una media mobile.
- Usa SL a circa 1.5x ATR settimanale dal prezzo di entrata e TP a circa 4.5x ATR settimanale (R:R 3:1).
- Non imporre limiti temporali: il trade rimane aperto finche' SL o TP non vengono colpiti.

Formato OBBLIGATORIO per ogni segnale BUY:

*[BUY] TICKER*
Prezzo: X | Var. sett.: +X%
RSI: X | MACD: rialzista | SMA: sopra 20/50
Setup: [1-2 righe max]
SL: X (sotto supporto chiave, ~1.5x ATR weekly)
TP: X (obiettivo trend, ~4.5x ATR weekly, R:R 3:1)
R:R: 3:1
Uscita: al raggiungimento di SL o TP (nessun limite temporale)

Concludi sempre con una riga: Sentiment: Risk-On / Risk-Off / Misto"""

USER_TEMPLATE = """Snapshot di mercato — settimana del {date}

I seguenti {count} asset hanno superato il pre-filtro tecnico (migliori setup rialzisti su {total_universe} analizzati):

{snapshot_json}

Per gli indici usa il campo "name" come riferimento. Per USA/Europa usa il ticker direttamente (es. AAPL, AZN.L, SAP.DE).
Analizza tutti i candidati e seleziona al massimo 3 segnali BUY. Sii selettivo: meglio 0 segnali che segnali deboli."""


def generate_report(snapshot: dict, date: str) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    count = sum(len(v) for v in snapshot.values())
    prompt = USER_TEMPLATE.format(
        date=date,
        count=count,
        total_universe="207",  # 100 USA + 100 Europa + 7 indici
        snapshot_json=json.dumps(snapshot, indent=2, ensure_ascii=False)
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
        temperature=0.3,
    )

    return response.choices[0].message.content
