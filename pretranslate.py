#!/usr/bin/env python3
"""
Pre-bake English translations into trends.csv so the static web app can show
them with no backend. Adds a `query_en` column (auto-detects source language,
leaves English as-is). Translations are cached, so re-running is cheap.

Install:  pip install pandas deep-translator
Run:      python pretranslate.py
Result:   trends.csv gains a query_en column (original is backed up to
          trends.raw.csv on first run).
"""

import os
import json
import shutil
import pandas as pd

SRC = "trends.csv"
BACKUP = "trends.raw.csv"
CACHE = "translation_cache.json"

def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(c):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)

def main():
    if not os.path.exists(BACKUP):           # keep a pristine copy once
        shutil.copy(SRC, BACKUP)
        print(f"backed up original -> {BACKUP}")

    df = pd.read_csv(BACKUP)                  # always translate from the original
    df["query"] = df["query"].astype(str)
    cache = load_cache()

    todo = sorted({q for q in df["query"].unique() if q and q not in cache})
    print(f"{len(todo)} unique terms to translate "
          f"({len(cache)} already cached)")

    if todo:
        from deep_translator import GoogleTranslator
        tr = GoogleTranslator(source="auto", target="en")
        for i in range(0, len(todo), 20):    # batch to cut request count
            batch = todo[i:i+20]
            try:
                out = tr.translate_batch(batch)
            except Exception:
                out = []
                for t in batch:
                    try: out.append(tr.translate(t) or t)
                    except Exception: out.append(t)
            for t, e in zip(batch, out):
                cache[t] = e or t
            save_cache(cache)
            print(f"  {min(i+20, len(todo))}/{len(todo)}")

    df["query_en"] = df["query"].map(lambda q: cache.get(q, q))
    df.to_csv(SRC, index=False, encoding="utf-8")
    print(f"wrote {SRC} with query_en column ({len(df)} rows)")

if __name__ == "__main__":
    main()
