"""Classificazione stance-only: riempie serenity_stance_cache.json e basta.

Leggero (niente download prezzi / backtest): pensato per girare a intervalli
via Task Scheduler. Classifica gli eventi non ancora in cache finche' la quota
Groq regge, salva, esce. Ogni run riprende da dove il precedente si e' fermato.

Uso: ./venv/Scripts/python.exe serenity_classify.py [--tweets PATH]
"""
import argparse
import os
import subprocess
import tempfile

from groq import Groq

from config import GROQ_API_KEY
from serenity_data import load_tweets, build_fresh_events
from serenity_stance import classify_event, load_cache, save_cache


def _ensure_repo():
    """Clona/aggiorna il repo dati e ritorna il path del JSON tweet."""
    tmp = os.path.join(tempfile.gettempdir(), "serenity_repo")
    if not os.path.exists(tmp):
        subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/yan-labs/serenity-aleabitoreddit.git", tmp],
                       check=True)
    else:
        subprocess.run(["git", "-C", tmp, "pull"], check=False)
    return os.path.join(tmp, "data", "aleabitoreddit_tweets.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tweets", help="path archivio (default: clona il repo)")
    args = ap.parse_args()

    tweets_path = args.tweets or _ensure_repo()
    events = build_fresh_events(load_tweets(tweets_path))
    cache = load_cache()

    todo = [e for e in events if f"{e['ticker']}:{e['tweet_ids'][0]}" not in cache]
    print(f"Eventi totali: {len(events)} | gia' in cache: {len(cache)} | da fare: {len(todo)}")

    client = Groq(api_key=GROQ_API_KEY)
    done = 0
    for e in todo:
        before = len(cache)
        classify_event(e, client, cache)
        if len(cache) == before:
            # nessuna nuova entry = quota esaurita (fallimenti non cachati): stop
            print("Quota Groq esaurita, mi fermo. Il prossimo run riprende da qui.")
            break
        done += 1
        if done % 25 == 0:
            save_cache(cache)
            print(f"  classificati {done} questo run (cache {len(cache)})")
    save_cache(cache)
    print(f"Fatto: +{done} questo run | cache totale {len(cache)}/{len(events)}")


if __name__ == "__main__":
    main()
