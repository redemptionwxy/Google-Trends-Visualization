#!/usr/bin/env python3
"""
Search Trends Atlas — explore Google Year-in-Search trending queries by
country and year (2001-2020), on a world map with a time slider, a category
filter, word clouds, and on-demand English translation.

Data: trends.csv  (columns: location, year, category, rank, query)

Run:
    pip install streamlit pandas plotly wordcloud matplotlib
    pip install deep-translator        # only needed for the translate toggle
    streamlit run trends_explorer.py

Notes
-----
* TRENDING searches (biggest spikes vs the prior year), not highest-volume.
* China / Russia / South Korea reflect Google users only (Baidu/Yandex/Naver lead).
* Translation uses deep-translator's free online endpoint: approximate,
  auto-detects source language (leaves English as-is), and is cached to
  translation_cache.json so each term is translated only once.
"""

import os
import json
import unicodedata
from collections import Counter

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from wordcloud import WordCloud

DATA_PATH = "trends.csv"
CACHE_PATH = "translation_cache.json"

NAME_FIXES = {"Czechia": "Czech Republic", "Myanmar (Burma)": "Myanmar"}
NON_MAP = {"Global", "Hong Kong", "Puerto Rico"}

FONT_CANDIDATES = {
    "cjk": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msyh.ttc"],
    "thai": ["/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
             "C:/Windows/Fonts/tahoma.ttf"],
    "arabic": ["/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
               "C:/Windows/Fonts/arial.ttf"],
    "hebrew": ["/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
               "C:/Windows/Fonts/arial.ttf"],
}

st.set_page_config(page_title="Search Trends Atlas", layout="wide")
st.markdown("""
<style>
  .stApp { background:#0f1822; color:#e6edf3; }
  h1,h2,h3 { font-family:"Georgia",serif; letter-spacing:-.01em; }
  .rankrow { font-family:"SFMono-Regular",Consolas,monospace; font-size:.9rem;
             margin:.15rem 0; }
  .amber { color:#f0a830; }
  .muted { color:#8aa0b3; font-size:.85rem; }
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# data + translation cache
# ----------------------------------------------------------------------
@st.cache_data
def load():
    df = pd.read_csv(DATA_PATH)
    df["query"] = df["query"].astype(str)
    df["category"] = df["category"].astype(str)
    return df


def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def translate_many(terms, cache):
    """Translate any uncached terms to English (auto source). Mutates + saves."""
    todo = sorted({t for t in terms if t and t not in cache})
    if not todo:
        return
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        st.sidebar.error("Install deep-translator to use translation:\n"
                         "`pip install deep-translator`")
        for t in todo:           # avoid retrying every rerun
            cache[t] = t
        return
    tr = GoogleTranslator(source="auto", target="en")
    with st.spinner(f"Translating {len(todo)} new terms…"):
        for t in todo:
            try:
                cache[t] = tr.translate(t) or t
            except Exception:
                cache[t] = t     # degrade to original on failure
    save_cache(cache)


def en(term, cache):
    return cache.get(term, term)


# ----------------------------------------------------------------------
# word cloud
# ----------------------------------------------------------------------
def script_of(text):
    for ch in text:
        if not ch.isalpha():
            continue
        n = unicodedata.name(ch, "")
        if any(k in n for k in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL")):
            return "cjk"
        if "THAI" in n:
            return "thai"
        if "ARABIC" in n:
            return "arabic"
        if "HEBREW" in n:
            return "hebrew"
    return "latin"


def font_for(script):
    for path in FONT_CANDIDATES.get(script, []):
        if os.path.exists(path):
            return path
    return None


def make_wordcloud(weights):
    if not weights:
        return None, None
    dominant = Counter(script_of(q) for q in weights).most_common(1)[0][0]
    font = font_for(dominant) if dominant != "latin" else None
    missing = dominant in {"cjk", "thai"} and font is None
    wc = WordCloud(width=820, height=460, background_color="#0f1822",
                   colormap="YlOrBr", prefer_horizontal=0.95,
                   font_path=font).generate_from_frequencies(weights)
    return wc, (dominant if missing else None)


# ----------------------------------------------------------------------
if not os.path.exists(DATA_PATH):
    st.error(f"Can't find {DATA_PATH}. Put it next to this script.")
    st.stop()

df = load()
years = sorted(df["year"].unique())
if "tcache" not in st.session_state:
    st.session_state.tcache = load_cache()
cache = st.session_state.tcache

# --- sidebar: the translation control ---
st.sidebar.header("Display")
translate = st.sidebar.toggle("Translate to English", value=False,
                              help="Auto-detects language; English is left "
                                   "as-is. Cached so each term translates once.")
st.sidebar.caption("Uses an online service — approximate, needs internet.")

st.title("Search Trends Atlas")
st.markdown('<span class="muted">What the world searched, 2001–2020 — top '
            '<span class="amber">trending</span> queries by country '
            '(biggest spikes each year, not raw volume).</span>',
            unsafe_allow_html=True)

year = st.slider("Year", int(years[0]), int(years[-1]), int(years[-1]), 1)
year_df = df[df["year"] == year]

# --- world map ---
counts = (year_df[~year_df["location"].isin(NON_MAP)]
          .groupby("location").size().reset_index(name="n"))
counts["map_name"] = counts["location"].replace(NAME_FIXES)
fig = go.Figure(go.Choropleth(
    locations=counts["map_name"], locationmode="country names",
    z=counts["n"], text=counts["location"],
    colorscale=[[0, "#1c2b3a"], [1, "#f0a830"]],
    marker_line_color="#0f1822", marker_line_width=0.5, colorbar_title="queries"))
fig.update_geos(bgcolor="#0f1822", showframe=False, showcoastlines=False,
                landcolor="#16222f", projection_type="natural earth")
fig.update_layout(paper_bgcolor="#0f1822", margin=dict(l=0, r=0, t=0, b=0),
                  height=440, geo=dict(bgcolor="#0f1822"))
st.caption("Click a highlighted country to explore it, or pick one below.")
event = st.plotly_chart(fig, width="stretch", on_select="rerun", key="map")

clicked = None
try:
    pts = event["selection"]["points"]
    if pts:
        clicked = pts[0].get("text") or pts[0].get("location")
        inv = {v: k for k, v in NAME_FIXES.items()}
        clicked = inv.get(clicked, clicked)
except Exception:
    pass

all_locs = sorted(df["location"].unique())
if clicked in all_locs:
    st.session_state["country"] = clicked
if "country" not in st.session_state:
    st.session_state["country"] = ("United States" if "United States" in all_locs
                                   else all_locs[0])

c1, c2 = st.columns([1, 1])
country = c1.selectbox("Country", all_locs, key="country")

# --- category filter (scoped to this country-year) ---
cysel = year_df[year_df["location"] == country].sort_values("rank")
cats = sorted(cysel["category"].dropna().unique().tolist())
ALL = "All categories"

if translate:                       # translate category labels for the dropdown
    translate_many(cats, cache)

def cat_label(c):
    if c == ALL:
        return ALL
    return f"{c}  —  {en(c, cache)}" if translate and en(c, cache) != c else c

category = c2.selectbox("Category", [ALL] + cats, format_func=cat_label)

sel = cysel if category == ALL else cysel[cysel["category"] == category]

# ----------------------------------------------------------------------
st.subheader(f"{country} · {year}" + (f" · {en(category, cache) if translate else category}"
                                      if category != ALL else ""))

if sel.empty:
    yrs = sorted(df[df["location"] == country]["year"].unique())
    st.info(f"No data for {country} in {year}"
            + (f" under “{category}”." if category != ALL else ".")
            + f"  Years available: {', '.join(map(str, yrs)) or '—'}.")
else:

    if translate:
        translate_many(sel["query"].tolist(), cache)

    # weights for the cloud (English terms when translating -> no font issues)
    weights = {}
    for _, r in sel.iterrows():
        q = en(r["query"], cache) if translate else r["query"]
        q = (q or "").strip()
        if q and q.lower() != "nan":
            weights[q] = weights.get(q, 0) + max(1, 21 - int(r["rank"]))

    left, right = st.columns([3, 2])
    with left:
        wc, missing = make_wordcloud(weights)
        if wc is not None:
            f2, ax = plt.subplots(figsize=(8.2, 4.6))
            f2.patch.set_facecolor("#0f1822")
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(f2)
            if missing:
                st.caption(f"(Install a Noto {missing.upper()} font, or turn on "
                           "Translate to English, to render this script.)")
        else:
            st.write("No queries to visualise.")

    with right:
        st.markdown("**Top trending queries**")
        for _, r in sel.head(20).iterrows():
            q = r["query"]
            disp = en(q, cache) if translate else q
            orig = (f" <span class='muted'>· {q}</span>"
                    if translate and disp != q else "")
            cat = (f" <span class='muted'>· {r['category']}</span>"
                   if category == ALL else "")
            st.markdown(f"<div class='rankrow'><span class='amber'>"
                        f"{int(r['rank']):>2}</span> {disp}{orig}{cat}</div>",
                        unsafe_allow_html=True)

st.markdown("---")
st.caption("Source: Google Year in Search (Kaggle). Trending = biggest "
           "year-over-year spikes. Translation is machine-generated and approximate.")