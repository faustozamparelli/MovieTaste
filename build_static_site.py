from pathlib import Path
from itertools import combinations
from html import escape
import re

import numpy as np
import pandas as pd


ROOT = Path(".")
SITE_DIR = ROOT / "site"
OUTPUT_DIR = SITE_DIR / "outputs"
ASSET_DIR = SITE_DIR / "assets"
RATING_BUCKETS = [x / 2 for x in range(1, 11)]
MIN_GROUP_RATERS = 3


def username_from_export(path):
    match = re.match(r"letterboxd-(.*)-\d{4}-\d{2}-\d{2}-.*-utc$", path.name)
    return match.group(1) if match else path.name


def normalize_title(value):
    value = str(value or "").strip().lower()
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def add_film_key(df):
    df = df.copy()
    df["Name"] = df["Name"].fillna("").astype(str)
    df["Year"] = df["Year"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    df["title_norm"] = df["Name"].map(normalize_title)
    df["film_key"] = df["title_norm"] + " (" + df["Year"].astype(str).str.strip() + ")"
    df["film"] = df["Name"] + " (" + df["Year"].astype(str).str.strip() + ")"
    return df


def read_export_csv(path):
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def pct(series):
    return 100 * series.mean() if len(series) else np.nan


def fmt_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{value:.2f}"
    return value


def display_df(df):
    if df.empty:
        return '<p class="empty">Nessuna riga trovata per questa sezione.</p>'
    shown = df.copy()
    for col in shown.columns:
        if col in VALUE_LABELS:
            shown[col] = shown[col].map(lambda value: VALUE_LABELS[col].get(value, value))
        shown[col] = shown[col].map(fmt_value)
    shown = shown.rename(columns=COLUMN_LABELS)
    return shown.to_html(index=False, classes="data-table", border=0, escape=True)


COLUMN_LABELS = {
    "user": "utente",
    "films considered": "film considerati",
    "rated films": "film votati",
    "reviewed films": "film recensiti",
    "average rating": "voto medio",
    "median rating": "voto centrale",
    "signal": "indicazione",
    "average_rating": "voto medio",
    "rating_std": "variabilità dei voti",
    "favorite_tier_pct": "% voti 4.5 o 5",
    "low_rating_pct": "% voti bassi",
    "middle_rating_pct": "% voti medi",
    "pair": "coppia",
    "common rated films": "film votati da entrambi",
    "mean abs diff": "differenza media",
    "median abs diff": "differenza centrale",
    "% exactly equal": "% voti identici",
    "% within 0.5": "% entro mezza stella",
    "strong disagreements": "grandi disaccordi",
    "film": "film",
    "difference": "differenza",
    "raters": "persone che hanno votato",
    "average": "media del gruppo",
    "spread": "distanza min-max",
    "std dev": "dispersione",
    "outlier": "persona fuori dal gruppo",
    "direction": "direzione",
    "outlier rating": "suo voto",
    "others average": "media degli altri",
}


VALUE_LABELS = {
    "signal": {
        "most generous": "più generoso",
        "strictest": "più severo",
        "most polarized": "più polarizzato",
        "most moderate": "più moderato",
    },
    "direction": {
        "higher": "più alto",
        "lower": "più basso",
    },
}


def save_output(df, filename):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / filename, index=False)


def render_interpretation(paragraphs):
    if not paragraphs:
        return ""
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]
    body = "\n".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)
    return f'<div class="interpretation"><h3>Interpretazione</h3>{body}</div>'


def section(section_id, eyebrow, title, description, df, filename=None, note=None, interpretation=None):
    eyebrow_html = f'<p class="eyebrow">{escape(eyebrow)}</p>' if eyebrow else ""
    note_html = f'<p class="note">{escape(note)}</p>' if note else ""
    interpretation_html = render_interpretation(interpretation)
    return f"""
    <section id="{escape(section_id)}" class="report-section">
      <div class="section-copy">
        {eyebrow_html}
        <h2>{escape(title)}</h2>
        <p>{escape(description)}</p>
        {note_html}
        {interpretation_html}
      </div>
      <div class="table-wrap">
        {display_df(df)}
      </div>
    </section>
    """


def build_analysis():
    exports = sorted(path for path in ROOT.glob("letterboxd-*-utc") if path.is_dir())
    rating_frames = []
    review_frames = []

    for export in exports:
        user = username_from_export(export)

        ratings = read_export_csv(export / "ratings.csv")
        if not ratings.empty:
            ratings = add_film_key(ratings)
            ratings["user"] = user
            ratings["source"] = "ratings.csv"
            ratings["Rating"] = pd.to_numeric(ratings["Rating"], errors="coerce")
            rating_frames.append(ratings[["user", "film_key", "film", "Name", "Year", "Rating", "source"]])

        reviews = read_export_csv(export / "reviews.csv")
        if not reviews.empty:
            reviews = add_film_key(reviews)
            reviews["user"] = user
            reviews["source"] = "reviews.csv"
            reviews["Rating"] = pd.to_numeric(reviews.get("Rating"), errors="coerce")
            review_frames.append(reviews[["user", "film_key", "film", "Name", "Year", "Rating", "Review", "source"]])

    raw_ratings = pd.concat(rating_frames, ignore_index=True) if rating_frames else pd.DataFrame()
    raw_reviews = pd.concat(review_frames, ignore_index=True) if review_frames else pd.DataFrame()

    review_ratings = raw_reviews.dropna(subset=["Rating"])[["user", "film_key", "film", "Name", "Year", "Rating", "source"]]
    all_rating_sources = pd.concat([raw_ratings, review_ratings], ignore_index=True)
    all_rating_sources["source_priority"] = all_rating_sources["source"].map({"ratings.csv": 0, "reviews.csv": 1})

    ratings = (
        all_rating_sources
        .sort_values(["user", "film_key", "source_priority"])
        .drop_duplicates(["user", "film_key"], keep="first")
        .drop(columns=["source_priority"])
        .reset_index(drop=True)
    )

    reviewed_films = (
        raw_reviews[["user", "film_key", "film", "Name", "Year"]]
        .drop_duplicates(["user", "film_key"])
        .reset_index(drop=True)
    )

    considered_films = (
        pd.concat(
            [
                ratings[["user", "film_key", "film", "Name", "Year"]],
                reviewed_films[["user", "film_key", "film", "Name", "Year"]],
            ],
            ignore_index=True,
        )
        .drop_duplicates(["user", "film_key"])
        .reset_index(drop=True)
    )

    users = sorted(considered_films["user"].unique())

    summary = (
        considered_films.groupby("user")["film_key"].nunique()
        .rename("films considered")
        .to_frame()
        .join(ratings.groupby("user")["film_key"].nunique().rename("rated films"))
        .join(reviewed_films.groupby("user")["film_key"].nunique().rename("reviewed films"))
        .join(ratings.groupby("user")["Rating"].mean().rename("average rating"))
        .join(ratings.groupby("user")["Rating"].median().rename("median rating"))
    )

    rating_counts = pd.crosstab(ratings["user"], ratings["Rating"])
    rating_percentages = rating_counts.div(rating_counts.sum(axis=1), axis=0).mul(100)

    for bucket in RATING_BUCKETS:
        if bucket not in rating_percentages:
            rating_percentages[bucket] = 0.0

    rating_percentages = (
        rating_percentages[RATING_BUCKETS]
        .rename(columns={bucket: f"% {bucket:.1f}" for bucket in RATING_BUCKETS})
    )

    user_summary = (
        summary.join(rating_percentages)
        .fillna({"rated films": 0, "reviewed films": 0})
        .reset_index()
        .sort_values("user")
    )

    personality = ratings.groupby("user").agg(
        average_rating=("Rating", "mean"),
        rating_std=("Rating", "std"),
        favorite_tier_pct=("Rating", lambda s: pct(s >= 4.5)),
        low_rating_pct=("Rating", lambda s: pct(s <= 2.5)),
        middle_rating_pct=("Rating", lambda s: pct(s.isin([3.0, 3.5]))),
    )

    personality_signals = pd.DataFrame(
        [
            ("most generous", personality.sort_values(["average_rating", "favorite_tier_pct"], ascending=False).index[0]),
            ("strictest", personality.sort_values(["low_rating_pct", "average_rating"], ascending=[False, True]).index[0]),
            ("most polarized", personality.sort_values("rating_std", ascending=False).index[0]),
            ("most moderate", personality.sort_values("rating_std", ascending=True).index[0]),
        ],
        columns=["signal", "user"],
    ).join(personality, on="user")

    pairwise_rows = []
    pairwise_detail_frames = {}

    for user_a, user_b in combinations(users, 2):
        a = ratings[ratings["user"] == user_a][["film_key", "film", "Rating"]].rename(columns={"Rating": user_a})
        b = ratings[ratings["user"] == user_b][["film_key", "Rating"]].rename(columns={"Rating": user_b})
        common = a.merge(b, on="film_key", how="inner")
        common["difference"] = (common[user_a] - common[user_b]).abs()
        common = common.sort_values(["difference", "film"], ascending=[False, True]).reset_index(drop=True)
        pairwise_detail_frames[(user_a, user_b)] = common

        pairwise_rows.append(
            {
                "pair": f"{user_a} / {user_b}",
                "common rated films": len(common),
                "mean abs diff": common["difference"].mean(),
                "median abs diff": common["difference"].median(),
                "% exactly equal": pct(common["difference"] == 0),
                "% within 0.5": pct(common["difference"] <= 0.5),
                "strong disagreements": int((common["difference"] >= 2.0).sum()),
            }
        )

    pairwise_similarity = (
        pd.DataFrame(pairwise_rows)
        .sort_values("mean abs diff", ascending=True)
        .reset_index(drop=True)
    )

    rating_matrix = ratings.pivot_table(index="film", columns="user", values="Rating", aggfunc="first")
    group_metrics = pd.DataFrame(
        {
            "raters": rating_matrix.notna().sum(axis=1),
            "average": rating_matrix.mean(axis=1),
            "spread": rating_matrix.max(axis=1) - rating_matrix.min(axis=1),
            "std dev": rating_matrix.std(axis=1, ddof=0),
        }
    )

    group_metrics = (
        group_metrics[group_metrics["raters"] >= MIN_GROUP_RATERS]
        .join(rating_matrix)
        .sort_values(["raters", "film"], ascending=[False, True])
        .reset_index()
    )

    consensus_favorites = (
        group_metrics[(group_metrics["average"] >= 4.0) & (group_metrics["spread"] <= 1.0)]
        .sort_values(["average", "spread"], ascending=[False, True])
        .reset_index(drop=True)
    )

    consensus_dislikes = (
        group_metrics[(group_metrics["average"] <= 3.0) & (group_metrics["spread"] <= 1.0)]
        .sort_values(["average", "spread"], ascending=[True, True])
        .reset_index(drop=True)
    )

    most_divisive = (
        group_metrics.sort_values(["spread", "std dev"], ascending=[False, False])
        .reset_index(drop=True)
    )

    outlier_rows = []
    indexed_group_metrics = group_metrics.set_index("film")

    for film, row in rating_matrix.loc[indexed_group_metrics.index].iterrows():
        user_ratings = row.dropna()
        if len(user_ratings) < MIN_GROUP_RATERS:
            continue

        for user, user_rating in user_ratings.items():
            others = user_ratings.drop(index=user)
            if len(others) < 2:
                continue
            others_average = others.mean()
            difference = user_rating - others_average
            if abs(difference) >= 1.5:
                outlier_rows.append(
                    {
                        "film": film,
                        "outlier": user,
                        "direction": "higher" if difference > 0 else "lower",
                        "outlier rating": user_rating,
                        "others average": others_average,
                        "difference": difference,
                    }
                )

    outliers = (
        pd.DataFrame(outlier_rows)
        .assign(abs_difference=lambda df: df["difference"].abs() if len(df) else pd.Series(dtype=float))
        .sort_values(["abs_difference", "film", "outlier"], ascending=[False, True, True])
        .drop(columns=["abs_difference"], errors="ignore")
        .reset_index(drop=True)
    )

    return {
        "users": users,
        "ratings": ratings,
        "reviewed_films": reviewed_films,
        "considered_films": considered_films,
        "user_summary": user_summary,
        "personality_signals": personality_signals,
        "pairwise_similarity": pairwise_similarity,
        "pairwise_detail_frames": pairwise_detail_frames,
        "group_metrics": group_metrics,
        "consensus_favorites": consensus_favorites,
        "consensus_dislikes": consensus_dislikes,
        "most_divisive": most_divisive,
        "outliers": outliers,
    }


def write_styles():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    (ASSET_DIR / "styles.css").write_text(
        """
:root {
  color-scheme: light;
  --bg: #f7f7f4;
  --paper: #ffffff;
  --ink: #191a1d;
  --muted: #61636a;
  --line: #deded9;
  --accent: #00a85a;
  --accent-2: #ff7a1a;
  --accent-3: #2d9cdb;
  --accent-4: #c94f7c;
  --soft: #f0f2ee;
  --tint: #f4fbf7;
  --tint-warm: #fff7ed;
  --shadow: 0 10px 26px rgba(25, 26, 29, 0.07);
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
}

a {
  color: inherit;
}

.site-header {
  position: relative;
  background: var(--paper);
  color: var(--ink);
  border-bottom: 1px solid var(--line);
}

.site-header::before {
  content: "";
  display: block;
  height: 5px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2), var(--accent-3), var(--accent-4));
}

.hero {
  max-width: 1180px;
  margin: 0 auto;
  min-height: 58vh;
  padding: 56px 24px 34px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 420px);
  gap: 48px;
  align-items: center;
}

.hero h1 {
  max-width: 760px;
  margin: 0 0 18px;
  font-size: clamp(2.5rem, 7vw, 5.8rem);
  line-height: 0.94;
  letter-spacing: 0;
}

.hero h1::after {
  content: "";
  display: block;
  width: min(220px, 42vw);
  height: 8px;
  margin-top: 20px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.hero p {
  max-width: 660px;
  margin: 0;
  color: var(--muted);
  font-size: 1.08rem;
}

.hero-panel {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, #ffffff, var(--tint));
  border-radius: 8px;
  padding: 22px;
}

.hero-panel h2 {
  margin: 0 0 12px;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.hero-panel ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.hero-panel li {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
}

.hero-panel li:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.hero-panel span {
  color: var(--muted);
}

.hero-panel strong {
  font-size: 1.18rem;
  color: var(--accent);
}

.taste-bars {
  margin-top: 22px;
  border-top: 1px solid var(--line);
  padding-top: 18px;
}

.taste-bars h3 {
  margin: 0 0 12px;
  font-size: 0.92rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.taste-bars li {
  display: grid;
  grid-template-columns: minmax(92px, 1fr) minmax(110px, 1.35fr) auto;
  align-items: center;
  border-bottom: 0;
  padding: 5px 0;
}

.taste-bars i {
  height: 8px;
  border-radius: 999px;
  background: #e4e4df;
  overflow: hidden;
}

.taste-bars i::before {
  content: "";
  display: block;
  width: var(--value);
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.nav {
  max-width: 1180px;
  margin: 0 auto;
  padding: 14px 24px 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.nav a {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 7px 13px;
  text-decoration: none;
  font-size: 0.92rem;
}

.nav a {
  color: var(--ink);
  background: var(--paper);
  border-color: var(--line);
  transition: border-color 160ms ease, color 160ms ease, background 160ms ease;
}

.nav a:hover {
  color: #0f6f45;
  border-color: var(--accent);
  background: var(--tint);
}

main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 26px 24px 64px;
}

.intro {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 18px 0 34px;
}

.intro article {
  background: var(--paper);
  border: 1px solid var(--line);
  border-top: 4px solid var(--accent);
  border-radius: 8px;
  padding: 18px;
  box-shadow: var(--shadow);
}

.intro article:nth-child(2) {
  border-top-color: var(--accent-2);
}

.intro article:nth-child(3) {
  border-top-color: var(--accent-3);
}

.intro h2 {
  margin: 0 0 8px;
  font-size: 1.05rem;
}

.intro p {
  margin: 0;
  color: var(--muted);
}

.report-section {
  padding: 36px 0;
  border-top: 1px solid var(--line);
}

.section-copy {
  max-width: none;
  margin-bottom: 18px;
}

.section-copy > p {
  max-width: 860px;
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
}

h2 {
  margin: 0 0 10px;
  font-size: clamp(1.55rem, 3vw, 2.4rem);
  line-height: 1.12;
  letter-spacing: 0;
}

.section-copy h2::after {
  content: "";
  display: block;
  width: 76px;
  height: 5px;
  margin-top: 12px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.section-copy p {
  margin: 0 0 12px;
  color: var(--muted);
}

.note {
  color: var(--ink);
  font-weight: 600;
}

.interpretation,
.pair-interpretation {
  background: linear-gradient(180deg, var(--tint), #ffffff);
  border: 1px solid var(--line);
  border-left: 5px solid var(--accent);
  border-radius: 8px;
  margin: 14px 0 0;
  padding: 16px 18px;
  width: 100%;
}

.interpretation h3,
.pair-interpretation h3 {
  margin: 0 0 8px;
  color: #0f6f45;
  font-size: 1rem;
}

.interpretation p,
.pair-interpretation p {
  margin: 0 0 10px;
  color: var(--ink);
}

.interpretation p:last-child,
.pair-interpretation p:last-child {
  margin-bottom: 0;
}

.table-wrap {
  overflow-x: auto;
  background: var(--paper);
  border: 1px solid var(--line);
  border-top: 3px solid var(--accent-3);
  border-radius: 8px;
  box-shadow: var(--shadow);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.data-table th,
.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}

.data-table th {
  position: sticky;
  top: 0;
  background: linear-gradient(180deg, var(--soft), #ffffff);
  color: var(--ink);
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.data-table tbody tr:hover td {
  background: var(--tint-warm);
}

.data-table tr:last-child td {
  border-bottom: 0;
}

.pair-details {
  display: grid;
  gap: 14px;
}

details {
  background: var(--paper);
  border: 1px solid var(--line);
  border-left: 4px solid var(--accent-3);
  border-radius: 8px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

summary {
  cursor: pointer;
  padding: 16px 18px;
  font-weight: 800;
}

details[open] summary {
  color: #0f6f45;
}

.detail-grid {
  display: grid;
  gap: 16px;
  padding: 0 18px 18px;
}

.detail-grid h3 {
  margin: 4px 0 8px;
  font-size: 1rem;
}

.empty {
  margin: 0;
  padding: 16px;
  color: var(--muted);
}

.site-footer {
  border-top: 1px solid var(--line);
  padding: 26px 24px 42px;
  text-align: center;
  color: var(--muted);
}

@media (max-width: 880px) {
  .hero,
  .intro {
    grid-template-columns: 1fr;
  }

  .hero {
    min-height: auto;
    padding-top: 42px;
  }

  .nav {
    padding-top: 0;
  }

  .interpretation,
  .pair-interpretation {
    padding: 14px;
  }

  .data-table {
    font-size: 0.84rem;
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def fmt_number(value, digits=2):
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def join_items(items):
    items = [str(item) for item in items if str(item)]
    if not items:
        return "nessun titolo"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " e " + items[-1]


def films_from(df, limit=3):
    if df.empty or "film" not in df:
        return "nessun titolo"
    return join_items(df["film"].head(limit).tolist())


def top_rating_bucket(row):
    bucket_cols = [f"% {bucket:.1f}" for bucket in RATING_BUCKETS]
    available = [col for col in bucket_cols if col in row.index]
    if not available:
        return None, None
    bucket = max(available, key=lambda col: row[col])
    return bucket.replace("% ", ""), row[bucket]


def film_ratings_sentence(row, users):
    parts = []
    for user in users:
        if user in row.index and pd.notna(row[user]):
            parts.append(f"{user} {fmt_number(row[user])}")
    return ", ".join(parts)


def pair_tone(mean_diff):
    if mean_diff <= 0.60:
        return "molto allineata"
    if mean_diff <= 0.80:
        return "abbastanza allineata"
    if mean_diff <= 1.10:
        return "mista"
    return "molto distante"


def build_interpretations(data):
    user_summary = data["user_summary"]
    personality = data["personality_signals"]
    pairwise = data["pairwise_similarity"]
    group_metrics = data["group_metrics"]
    consensus_favorites = data["consensus_favorites"]
    consensus_dislikes = data["consensus_dislikes"]
    most_divisive = data["most_divisive"]
    outliers = data["outliers"]
    users = data["users"]

    most_active = user_summary.sort_values("films considered", ascending=False).iloc[0]
    most_reviews = user_summary.sort_values("reviewed films", ascending=False).iloc[0]
    highest_avg = user_summary.sort_values("average rating", ascending=False).iloc[0]
    lowest_avg = user_summary.sort_values("average rating", ascending=True).iloc[0]
    highest_bucket, highest_bucket_pct = top_rating_bucket(highest_avg)
    lowest_bucket, lowest_bucket_pct = top_rating_bucket(lowest_avg)

    signal_lookup = personality.set_index("signal")
    generous = signal_lookup.loc["most generous"]
    strict = signal_lookup.loc["strictest"]
    polarized = signal_lookup.loc["most polarized"]
    moderate = signal_lookup.loc["most moderate"]

    closest_pair = pairwise.iloc[0]
    farthest_pair = pairwise.iloc[-1]
    strongest_pair = pairwise.sort_values("common rated films", ascending=False).iloc[0]

    top_group = group_metrics.sort_values(["average", "spread"], ascending=[False, True]).head(3)
    lowest_group = group_metrics.sort_values(["average", "spread"], ascending=[True, True]).head(3)
    near_agreement_count = int((group_metrics["spread"] <= 0.5).sum())
    split_count = int((group_metrics["spread"] >= 2.0).sum())
    all_users_count = int((group_metrics["raters"] == len(users)).sum())

    favorite_text = (
        f"I preferiti condivisi più chiari sono {films_from(consensus_favorites)}."
        if not consensus_favorites.empty
        else "Non ci sono film che superano insieme la soglia di voto alto e accordo stretto."
    )
    dislike_text = (
        f"I titoli bocciati con più accordo sono {films_from(consensus_dislikes)}."
        if not consensus_dislikes.empty
        else "Non emerge una vera lista di film bocciati da tutti: i voti bassi condivisi sono pochi o troppo discordanti."
    )

    top_divisive = most_divisive.iloc[0] if not most_divisive.empty else None
    top_outlier = outliers.iloc[0] if not outliers.empty else None
    most_outlier_user = outliers["outlier"].value_counts().index[0] if not outliers.empty else None
    most_outlier_count = int(outliers["outlier"].value_counts().iloc[0]) if not outliers.empty else 0
    high_outliers = int((outliers["direction"] == "higher").sum()) if not outliers.empty else 0
    low_outliers = int((outliers["direction"] == "lower").sum()) if not outliers.empty else 0

    interpretations = {
        "user_summary": [
            f"{most_active['user']} è il profilo più ricco: compaiono {int(most_active['films considered'])} film considerati. {most_reviews['user']} è invece quello che scrive più recensioni, con {int(most_reviews['reviewed films'])} film recensiti.",
            f"Sul tono dei voti, {highest_avg['user']} è il più generoso con una media di {fmt_number(highest_avg['average rating'])}/5, mentre {lowest_avg['user']} usa voti leggermente più bassi, con {fmt_number(lowest_avg['average rating'])}/5. In pratica, quando confronti due utenti, tieni conto che non tutti usano le stelle con la stessa severità.",
            f"La distribuzione conferma questa differenza: per {highest_avg['user']} il voto più frequente è {highest_bucket} stelle ({fmt_number(highest_bucket_pct)}% dei suoi voti), mentre per {lowest_avg['user']} il voto più frequente è {lowest_bucket} stelle ({fmt_number(lowest_bucket_pct)}%). {most_active['user']}, avendo molti più film nel dataset, pesa soprattutto come archivio ampio di confronti.",
            f"Questa tabella va letta come taratura personale: una stella in più data da un utente molto severo non significa la stessa cosa di una stella in più data da un utente più generoso. Per questo le sezioni successive confrontano sempre anche le differenze tra persone, non solo le medie assolute.",
        ],
        "personality": [
            f"{generous['user']} tende ad amare di più ciò che guarda: quasi {fmt_number(generous['favorite_tier_pct'])}% dei suoi voti sono a 4.5 o 5 stelle.",
            f"{strict['user']} risulta il più severo per quota di voti bassi, mentre {polarized['user']} è anche il più variabile: non resta sempre nella zona media, ma si sposta più spesso tra entusiasmo e bocciatura. {moderate['user']} è il più regolare, quindi i suoi voti cambiano meno da un film all'altro.",
            f"Tradotto: {generous['user']} usa spesso la parte alta della scala, quindi un suo 4.5 o 5 segnala entusiasmo ma non è rarissimo. Al contrario, i voti bassi di {strict['user']} contano molto perché arrivano da un profilo che separa di più ciò che funziona da ciò che non funziona.",
            f"{moderate['user']} ha una variabilità di {fmt_number(moderate['rating_std'])}: tende a stare più vicino al centro e rende più interessanti i casi in cui esce dalla sua zona abituale. {polarized['user']}, con variabilità {fmt_number(polarized['rating_std'])}, è il profilo più utile per trovare film amati o rifiutati con decisione.",
        ],
        "pairwise": [
            f"La coppia più vicina è {closest_pair['pair']}: su {int(closest_pair['common rated films'])} film in comune, la differenza media è solo {fmt_number(closest_pair['mean abs diff'])} stelle. Vuol dire che spesso vedono gli stessi film in modo simile.",
            f"La coppia più distante è {farthest_pair['pair']}, con {fmt_number(farthest_pair['mean abs diff'])} stelle di differenza media. La coppia statisticamente più solida da leggere è {strongest_pair['pair']}, perché ha {int(strongest_pair['common rated films'])} film in comune.",
            f"Il dato più intuitivo è la quota entro mezza stella: {closest_pair['pair']} ci arriva nel {fmt_number(closest_pair['% within 0.5'])}% dei film comuni, mentre {farthest_pair['pair']} si ferma al {fmt_number(farthest_pair['% within 0.5'])}%. Questo racconta meglio della media quanto spesso due persone escono dalla sala con una sensazione simile.",
            f"I grandi disaccordi sono rari nella coppia più vicina ({int(closest_pair['strong disagreements'])}) e molto più presenti nella coppia più distante ({int(farthest_pair['strong disagreements'])}). Quindi la distanza non è solo una questione di mezzo voto: in alcuni casi cambia proprio il giudizio sul film.",
        ],
        "group_metrics": [
            f"Ci sono {len(group_metrics)} film votati da almeno {MIN_GROUP_RATERS} persone. I titoli con media più alta sono {films_from(top_group)}, mentre quelli con media più bassa sono {films_from(lowest_group)}.",
            "Questa sezione serve soprattutto per capire il gusto del gruppo: non guarda una singola amicizia, ma dove il gruppo converge o si separa.",
            f"{all_users_count} film sono stati votati da tutti e quattro, quindi sono i più solidi per parlare di gusto collettivo. In {near_agreement_count} film la distanza tra voto più basso e più alto resta entro mezza stella: lì il gruppo è praticamente allineato.",
            f"Al contrario, {split_count} film hanno almeno 2 stelle di distanza tra chi li ha apprezzati di più e chi li ha apprezzati di meno. Quelli sono i titoli più utili per capire le differenze vere tra i profili, perché non dipendono solo dal fatto che qualcuno voti un po' più alto in generale.",
        ],
        "consensus_favorites": [
            favorite_text,
            f"In totale ci sono {len(consensus_favorites)} film che il gruppo tende a trattare come preferiti condivisi: media alta e poca distanza tra i voti.",
            f"Il punto interessante è che questi non sono solo film con una media alta: sono film in cui nessuno si stacca troppo dagli altri. Per questo sono i titoli migliori da proporre come gusto comune del gruppo, non semplicemente come preferiti di una singola persona.",
            f"Se devi scegliere un film che abbia buone probabilità di piacere a tutti, questa è la sezione più utile: premia i film solidi e trasversali, non quelli che fanno impazzire una persona e lasciano tiepidi gli altri.",
        ],
        "consensus_dislikes": [
            dislike_text,
            f"In totale ci sono {len(consensus_dislikes)} film con giudizio basso e abbastanza condiviso. Se il numero è piccolo, significa che il gruppo litiga più facilmente sui film deboli che sui film amati.",
            "Questa lista è più severa di una semplice classifica dei voti bassi: un film entra qui solo se il gruppo lo valuta poco e senza grandi eccezioni. Se un titolo manca, può voler dire che qualcuno lo ha difeso abbastanza da rompere il consenso negativo.",
            "In pratica, queste sono le bocciature più condivisibili del dataset: non dicono che il film sia oggettivamente brutto, ma che dentro questo gruppo non ha trovato un vero sostenitore forte.",
        ],
        "divisive": [
            (
                f"Il film più divisivo è {top_divisive['film']}: tra il voto più basso e quello più alto ci sono {fmt_number(top_divisive['spread'])} stelle di distanza."
                if top_divisive is not None
                else "Non ci sono abbastanza film comuni per individuare veri titoli divisivi."
            ),
            "Qui conviene leggere i primi titoli come conversazioni potenzialmente interessanti: non sono necessariamente brutti o belli, sono quelli su cui il gruppo non è d'accordo.",
            (
                f"Nel caso principale, i voti sono: {film_ratings_sentence(top_divisive, users)}. Questo fa capire subito se la divisione nasce da una persona isolata o da due blocchi più equilibrati."
                if top_divisive is not None
                else "Quando mancano titoli divisivi, significa che il gruppo ha pochi film comuni o voti abbastanza vicini."
            ),
            "Questa è probabilmente la sezione più interessante per discutere: i film divisivi rivelano differenze di sensibilità, aspettative e tolleranza verso generi o stili specifici molto più delle classifiche dei preferiti.",
        ],
        "outliers": [
            (
                f"Il caso più forte è {top_outlier['outlier']} su {top_outlier['film']}: il suo voto è {fmt_number(top_outlier['outlier rating'])}, mentre gli altri stanno in media a {fmt_number(top_outlier['others average'])}."
                if top_outlier is not None
                else "Non ci sono casi forti in cui una persona si stacca nettamente dal resto del gruppo."
            ),
            "Questa sezione non dice chi ha ragione: mostra solo quando una persona ha visto un film in modo molto diverso dagli altri.",
            (
                f"La persona che compare più spesso come fuori dal gruppo è {most_outlier_user}, con {most_outlier_count} casi. Nel complesso ci sono {high_outliers} valutazioni molto più alte degli altri e {low_outliers} valutazioni molto più basse."
                if most_outlier_user is not None
                else "Non emerge nessun profilo che si stacchi spesso dagli altri."
            ),
            "Leggila come una lista di eccezioni personali: se una persona è fuori dal gruppo in alto, quel film probabilmente tocca una sua preferenza specifica; se è fuori dal gruppo in basso, forse quel titolo urta qualcosa che agli altri pesa meno.",
        ],
    }
    return interpretations


def write_site(data):
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    write_styles()
    interpretations = build_interpretations(data)

    detail_html = []
    for user_a, user_b in combinations(data["users"], 2):
        common = data["pairwise_detail_frames"][(user_a, user_b)]
        slug = re.sub(r"[^a-z0-9]+", "-", f"{user_a}-{user_b}".lower()).strip("-")
        detail_outputs = {
            f"{slug}-biggest-disagreements.csv": common[["film", user_a, user_b, "difference"]].head(10),
            f"{slug}-exact-same-ratings.csv": common.loc[common["difference"] == 0, ["film", user_a, user_b, "difference"]].sort_values("film").head(10),
            f"{slug}-shared-favorites.csv": (
                common.loc[(common[user_a] >= 4.5) & (common[user_b] >= 4.5), ["film", user_a, user_b, "difference"]]
                .sort_values(["difference", "film"])
                .head(10)
            ),
            f"{slug}-shared-dislikes.csv": (
                common.loc[(common[user_a] <= 2.5) & (common[user_b] <= 2.5), ["film", user_a, user_b, "difference"]]
                .sort_values(["difference", "film"])
                .head(10)
            ),
        }
        same_count = int((common["difference"] == 0).sum())
        favorite_count = int(((common[user_a] >= 4.5) & (common[user_b] >= 4.5)).sum())
        dislike_count = int(((common[user_a] <= 2.5) & (common[user_b] <= 2.5)).sum())
        mean_diff = float(common["difference"].mean()) if len(common) else 0.0
        within_half = pct(common["difference"] <= 0.5)
        strong_count = int((common["difference"] >= 2.0).sum())
        top_disagreements = films_from(detail_outputs[f"{slug}-biggest-disagreements.csv"], 3)
        top_matches = films_from(detail_outputs[f"{slug}-exact-same-ratings.csv"], 3)
        top_favorites = films_from(detail_outputs[f"{slug}-shared-favorites.csv"], 3)
        top_dislikes = films_from(detail_outputs[f"{slug}-shared-dislikes.csv"], 3)

        detail_html.append(
            f"""
            <details>
              <summary>{escape(user_a)} / {escape(user_b)}</summary>
              <div class="detail-grid">
                <div class="pair-interpretation">
                  <h3>Interpretazione</h3>
                  <p>Questa coppia è {escape(pair_tone(mean_diff))}: su {len(common)} film in comune, la distanza media è {fmt_number(mean_diff)} stelle. I disaccordi più evidenti sono su {escape(top_disagreements)}.</p>
                  <p>Nel {fmt_number(within_half)}% dei casi i due voti sono uguali o distano al massimo mezza stella. Questo è il dato più leggibile: più è alto, più i due profili reagiscono in modo simile agli stessi film.</p>
                  <p>Ci sono {same_count} voti identici, {favorite_count} preferiti condivisi e {dislike_count} bocciature condivise. Le coincidenze più immediate sono {escape(top_matches)}; i preferiti condivisi più chiari sono {escape(top_favorites)}; le bocciature condivise sono {escape(top_dislikes)}.</p>
                  <p>I grandi disaccordi sono {strong_count}. Quando compaiono, non indicano solo una piccola differenza di severità: segnalano film su cui le due persone hanno probabilmente letto qualità, difetti o aspettative in modo proprio diverso.</p>
                </div>
                <div>
                  <h3>Disaccordi più grandi</h3>
                  <p class="note">Sono i film in comune dove i due voti sono più lontani.</p>
                  <div class="table-wrap">{display_df(detail_outputs[f"{slug}-biggest-disagreements.csv"])}</div>
                </div>
                <div>
                  <h3>Voti identici</h3>
                  <p class="note">Sono i film a cui entrambe le persone hanno dato lo stesso voto.</p>
                  <div class="table-wrap">{display_df(detail_outputs[f"{slug}-exact-same-ratings.csv"])}</div>
                </div>
                <div>
                  <h3>Preferiti condivisi</h3>
                  <p class="note">Entrambe le persone hanno dato a questi film almeno 4.5 stelle.</p>
                  <div class="table-wrap">{display_df(detail_outputs[f"{slug}-shared-favorites.csv"])}</div>
                </div>
                <div>
                  <h3>Bocciature condivise</h3>
                  <p class="note">Entrambe le persone hanno dato a questi film al massimo 2.5 stelle.</p>
                  <div class="table-wrap">{display_df(detail_outputs[f"{slug}-shared-dislikes.csv"])}</div>
                </div>
              </div>
            </details>
            """
        )

    stats = [
        ("Utenti", len(data["users"])),
        ("Voti letti", len(data["ratings"])),
        ("Recensioni lette", len(data["reviewed_films"])),
        ("Film votati da 3+ persone", len(data["group_metrics"])),
    ]

    sections = [
        section(
            "user-summary",
            "",
            "Riassunto utenti",
            "Questa tabella mostra il profilo base di ogni persona: quanti film ha votato o recensito, qual è il suo voto medio e come distribuisce le stelle.",
            data["user_summary"],
            "user_summary.csv",
            "Serve per capire subito chi usa Letterboxd di più, chi scrive di più e chi tende a votare più alto o più basso.",
            interpretation=interpretations["user_summary"],
        ),
        section(
            "personality",
            "",
            "Stile di voto",
            "Queste etichette descrivono come una persona usa le stelle, non se ha gusti migliori o peggiori. Generoso significa voti più alti, severo più voti bassi, polarizzato più salti tra alto e basso, moderato voti più stabili.",
            data["personality_signals"],
            "rating_personality.csv",
            "Le percentuali sono semplici quote dei voti di quella persona. Per esempio, 4.5 o 5 stelle indica quanto spesso mette voti da favorito.",
            interpretation=interpretations["personality"],
        ),
        section(
            "pairwise",
            "",
            "Somiglianza tra coppie",
            "Qui ogni coppia viene confrontata solo sui film che entrambe le persone hanno votato. Una differenza media più bassa significa gusti più vicini.",
            data["pairwise_similarity"],
            "pairwise_similarity.csv",
            "Il numero di film in comune conta: una coppia con tanti film condivisi è più facile da interpretare.",
            interpretation=interpretations["pairwise"],
        ),
    ]

    group_sections = [
        section(
            "group-metrics",
            "",
            "Lettura del gruppo",
            "Questa parte include solo film votati da almeno tre persone. La media dice quanto il gruppo tende ad apprezzare un film; la distanza min-max dice quanto i voti sono lontani tra loro.",
            data["group_metrics"],
            "group_metrics.csv",
            "Una distanza di 0.5 vuol dire quasi accordo. Una distanza di 3.0 vuol dire gruppo molto diviso.",
            interpretation=interpretations["group_metrics"],
        ),
        section(
            "consensus-favorites",
            "",
            "Preferiti condivisi",
            "Sono i film che il gruppo ha apprezzato in modo abbastanza compatto: media almeno 4 stelle e al massimo 1 stella tra il voto più basso e quello più alto.",
            data["consensus_favorites"],
            "consensus_favorites.csv",
            "In parole semplici: voto alto e poco disaccordo.",
            interpretation=interpretations["consensus_favorites"],
        ),
        section(
            "consensus-dislikes",
            "",
            "Bocciature condivise",
            "Sono i film che il gruppo non ha valutato molto bene, sempre con un certo accordo: media massimo 3 stelle e al massimo 1 stella tra voto più basso e più alto.",
            data["consensus_dislikes"],
            "consensus_dislikes.csv",
            "In parole semplici: voto basso e poco disaccordo.",
            interpretation=interpretations["consensus_dislikes"],
        ),
        section(
            "divisive",
            "",
            "Film più divisivi",
            "Sono i film su cui il gruppo è meno d'accordo. La tabella mette prima i titoli con maggiore distanza tra voto basso e voto alto.",
            data["most_divisive"].head(20),
            "most_divisive.csv",
            "Qui vedi i primi 20 casi: bastano per capire dove nascono le differenze più forti.",
            interpretation=interpretations["divisive"],
        ),
        section(
            "outliers",
            "",
            "Una persona contro il gruppo",
            "Questa sezione trova i casi in cui una persona ha dato un voto distante almeno 1.5 stelle dalla media degli altri.",
            data["outliers"],
            "outliers.csv",
            "La direzione dice se quella persona ha votato più alto o più basso rispetto agli altri.",
            interpretation=interpretations["outliers"],
        ),
    ]

    stat_items = "\n".join(
        f"<li><span>{escape(label)}</span><strong>{escape(str(value))}</strong></li>"
        for label, value in stats
    )

    average_rows = data["user_summary"][["user", "average rating"]].sort_values("average rating", ascending=False)
    bar_items = "\n".join(
        (
            f'<li><span>{escape(str(row["user"]))}</span>'
            f'<i style="--value: {max(0, min(100, float(row["average rating"]) / 5 * 100)):.1f}%"></i>'
            f'<strong>{float(row["average rating"]):.2f}</strong></li>'
        )
        for _, row in average_rows.iterrows()
    )

    html = f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Analisi gusti Letterboxd</title>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body>
  <header class="site-header">
    <div class="hero">
      <div>
        <h1>Analisi gusti Letterboxd</h1>
        <p>Un report semplice sui profili Letterboxd di {escape(", ".join(data["users"]))}. Usa solo voti e recensioni, poi traduce i numeri in una lettura comprensibile.</p>
      </div>
      <aside class="hero-panel" aria-label="Totali del report">
        <h2>Totali del report</h2>
        <ul>
          {stat_items}
        </ul>
        <div class="taste-bars">
          <h3>Voto medio</h3>
          <ul>
            {bar_items}
          </ul>
        </div>
      </aside>
    </div>
    <nav class="nav" aria-label="Sezioni del report">
      <a href="#user-summary">Utenti</a>
      <a href="#personality">Stile di voto</a>
      <a href="#pairwise">Coppie</a>
      <a href="#pair-details">Dettagli coppie</a>
      <a href="#group-metrics">Gruppo</a>
      <a href="#consensus-favorites">Preferiti</a>
      <a href="#divisive">Divisivi</a>
      <a href="#outliers">Fuori dal gruppo</a>
    </nav>
  </header>

  <main>
    <div class="intro">
      <article>
        <h2>Che dati usa?</h2>
        <p>Usa solo voti e recensioni. Watchlist, like, commenti, righe eliminate e liste non entrano nell'analisi.</p>
      </article>
      <article>
        <h2>Come abbina i film?</h2>
        <p>I film vengono riconosciuti usando titolo ripulito e anno, così lo stesso titolo può essere confrontato tra profili diversi.</p>
      </article>
      <article>
        <h2>Come va letto?</h2>
        <p>I numeri descrivono abitudini e somiglianze in questi export. Non sono una classifica oggettiva del gusto.</p>
      </article>
    </div>

    {"".join(sections)}

    <section id="pair-details" class="report-section">
      <div class="section-copy">
        <h2>Dettaglio delle coppie</h2>
        <p>Apri una coppia per vedere i film dietro al punteggio di somiglianza. Qui si capisce dove due persone coincidono, dove si separano e quali preferiti o bocciature hanno in comune.</p>
      </div>
      <div class="pair-details">
        {"".join(detail_html)}
      </div>
    </section>

    {"".join(group_sections)}
  </main>

  <footer class="site-footer">
    Creato da faustozamparelli.
  </footer>
</body>
</html>
"""

    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")


def main():
    data = build_analysis()
    write_site(data)
    print(f"Wrote {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
