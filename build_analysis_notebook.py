from pathlib import Path
from textwrap import dedent

import nbformat as nbf


def md(text):
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text):
    return nbf.v4.new_code_cell(dedent(text).strip())


cells = [
    md(
        """
        # Letterboxd Friends Taste Analysis

        This notebook compares movie taste across the Letterboxd exports in this folder.

        Scope:

        - Use only `ratings.csv` and `reviews.csv`.
        - Ignore watched-only history, likes, watchlists, lists, comments, deleted exports, and orphaned exports.
        - Match films by normalized `Name + Year`, not by Letterboxd URI.
        - Reviewed-but-unrated films count for user activity only; rating comparisons use films with ratings.
        """
    ),
    code(
        r'''
        from pathlib import Path
        from itertools import combinations
        import re

        import numpy as np
        import pandas as pd

        ROOT = Path(".")
        RATING_BUCKETS = [x / 2 for x in range(1, 11)]
        MIN_GROUP_RATERS = 3

        pd.set_option("display.max_rows", 100)
        pd.set_option("display.max_columns", 80)
        pd.set_option("display.width", 160)
        pd.options.display.float_format = "{:.2f}".format


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
        '''
    ),
    md(
        """
        ## Load Ratings And Reviews

        Ratings come from `ratings.csv` plus review rows that include a rating. If the same user has a rating in both places, `ratings.csv` is preferred.
        """
    ),
    code(
        r'''
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

        # Prefer explicit ratings.csv values when duplicate user-film ratings exist.
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
        print(f"Loaded {len(users)} users: {', '.join(users)}")
        print(f"Rated user-film rows: {len(ratings)}")
        print(f"Reviewed user-film rows: {len(reviewed_films)}")
        print(f"Considered user-film rows: {len(considered_films)}")
        '''
    ),
    md(
        """
        ## User Summary

        Bucket columns show the percentage of each user's ratings that fall into each exact Letterboxd rating value.
        """
    ),
    code(
        r'''
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
            .sort_index()
        )

        user_summary
        '''
    ),
    md(
        """
        ## Rating Personality

        These labels summarize rating behavior, not taste quality.
        """
    ),
    code(
        r'''
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

        personality_signals
        '''
    ),
    md(
        """
        ## Pairwise Similarity

        Only films rated by both users are used here. The table is sorted from most similar to most dissimilar by mean absolute rating difference.
        """
    ),
    code(
        r'''
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

        pairwise_similarity
        '''
    ),
    md(
        """
        ## Pairwise Detail Tables

        For each pair, inspect the biggest disagreements, exact matches, shared favorites, and shared dislikes.
        """
    ),
    code(
        r'''
        for user_a, user_b in combinations(users, 2):
            common = pairwise_detail_frames[(user_a, user_b)]
            print(f"\n\n=== {user_a} / {user_b} ===")

            print("\nBiggest disagreements")
            display(common[["film", user_a, user_b, "difference"]].head(10))

            print("\nExact same ratings")
            display(common.loc[common["difference"] == 0, ["film", user_a, user_b, "difference"]].sort_values("film").head(10))

            print("\nShared favorites")
            display(
                common.loc[(common[user_a] >= 4.5) & (common[user_b] >= 4.5), ["film", user_a, user_b, "difference"]]
                .sort_values(["difference", "film"])
                .head(10)
            )

            print("\nShared dislikes")
            display(
                common.loc[(common[user_a] <= 2.5) & (common[user_b] <= 2.5), ["film", user_a, user_b, "difference"]]
                .sort_values(["difference", "film"])
                .head(10)
            )
        '''
    ),
    md(
        """
        ## Group Metrics

        Group tables use films rated by at least 3 users.
        """
    ),
    code(
        r'''
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
        )

        print(f"Group-qualified films: {len(group_metrics)}")
        group_metrics.head(50)
        '''
    ),
    md(
        """
        ## Consensus And Divisiveness

        Consensus favorites require average rating `>= 4.0` and spread `<= 1.0`.

        Consensus dislikes require average rating `<= 3.0` and spread `<= 1.0`.

        Divisive films are sorted by spread, then standard deviation.
        """
    ),
    code(
        r'''
        consensus_favorites = (
            group_metrics[(group_metrics["average"] >= 4.0) & (group_metrics["spread"] <= 1.0)]
            .sort_values(["average", "spread"], ascending=[False, True])
        )

        consensus_dislikes = (
            group_metrics[(group_metrics["average"] <= 3.0) & (group_metrics["spread"] <= 1.0)]
            .sort_values(["average", "spread"], ascending=[True, True])
        )

        most_divisive = group_metrics.sort_values(["spread", "std dev"], ascending=[False, False])

        print("Consensus favorites")
        display(consensus_favorites.head(20))

        print("Consensus dislikes")
        display(consensus_dislikes.head(20))

        print("Most divisive films")
        display(most_divisive.head(20))
        '''
    ),
    md(
        """
        ## One Person Against The Group

        A user is an outlier when their rating differs from the average rating of the other users by at least `1.5` stars.
        """
    ),
    code(
        r'''
        outlier_rows = []

        for film, row in rating_matrix.loc[group_metrics.index].iterrows():
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

        print(f"Outlier cases: {len(outliers)}")
        outliers.head(30)
        '''
    ),
    md(
        """
        ## Thresholds To Tweak Later

        Useful values are defined near the top of the notebook:

        - `MIN_GROUP_RATERS = 3`
        - consensus favorite: average `>= 4.0`, spread `<= 1.0`
        - consensus dislike: average `<= 3.0`, spread `<= 1.0`
        - outlier: absolute difference from the other users' average `>= 1.5`
        """
    ),
]


notebook = nbf.v4.new_notebook()
notebook["cells"] = cells
notebook["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {
        "name": "python",
        "pygments_lexer": "ipython3",
    },
}

nbf.write(notebook, Path("analysis.ipynb"))
print(f"Wrote analysis.ipynb with {len(cells)} cells")
