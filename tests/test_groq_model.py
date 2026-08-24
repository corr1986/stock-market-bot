"""Il modello Groq deve stare in un solo posto (config.GROQ_MODEL).

Groq dismette i modelli senza preavviso: il 24/08/2026 la sparizione di
llama-3.3-70b-versatile ha fatto fallire i segnali V3 del lunedì. Con l'id
centralizzato la prossima dismissione si risolve cambiando una riga.
"""

import re
from pathlib import Path

import config

BASE = Path(__file__).resolve().parent.parent

# File che parlano con Groq
GROQ_MODULES = [
    "claude_analyst.py",
    "claude_analyst_v2.py",
    "serenity_stance.py",
]


def test_config_expone_il_modello_groq():
    assert isinstance(config.GROQ_MODEL, str) and config.GROQ_MODEL


def test_nessun_modello_hardcoded_nei_moduli_groq():
    # Un id di modello letterale passato a model= vanifica la centralizzazione.
    offenders = []
    for name in GROQ_MODULES:
        src = (BASE / name).read_text(encoding="utf-8")
        for m in re.finditer(r"model\s*=\s*([\"'])([^\"']+)\1", src):
            offenders.append(f"{name}: {m.group(2)}")
    assert not offenders, f"modello hardcoded, usare config.GROQ_MODEL: {offenders}"


def test_modello_dismesso_non_piu_referenziato():
    dead = "llama-3.3-70b-versatile"
    hits = [n for n in GROQ_MODULES
            if dead in (BASE / n).read_text(encoding="utf-8")]
    assert not hits, f"modello dismesso ancora presente in: {hits}"


def test_max_tokens_sufficienti_per_modelli_reasoning():
    # I modelli gpt-oss consumano il budget in reasoning prima di rispondere:
    # con max_tokens troppo bassi finish_reason='length' e content vuoto.
    assert config.GROQ_MAX_TOKENS_STANCE >= 300
    assert config.GROQ_MAX_TOKENS_SIGNALS >= 800
