# Letterboxd Friends Analysis Plan

## Scope

Analyze movie taste using only each user's Letterboxd `ratings.csv` and `reviews.csv`.

Do not use:

- `watched.csv`
- `watchlist.csv`
- `likes/`
- lists
- comments
- deleted or orphaned exports

Films should be matched by normalized `Name + Year`, not by Letterboxd URI, because review and rating exports can use different URIs for the same film.

## User Summary

For each user, calculate:

- Total films considered: unique films that are either rated or reviewed
- Rated films
- Reviewed films
- Average rating
- Median rating
- Percentage of ratings in each exact Letterboxd bucket:
  - `0.5`
  - `1.0`
  - `1.5`
  - `2.0`
  - `2.5`
  - `3.0`
  - `3.5`
  - `4.0`
  - `4.5`
  - `5.0`

Reviewed-but-unrated films count for user activity, but not for rating comparisons.

## Rating Personality

Keep this descriptive and simple, based on rating distribution:

- Generous: high average rating and many `4.5` or `5.0` ratings
- Strict: lower average rating and many ratings at or below `2.5`
- Polarized: high rating standard deviation
- Moderate: low rating standard deviation and many ratings around `3.0` or `3.5`

## Pairwise Similarity

For every pair of users, using only films both users rated, calculate:

- Common rated films
- Mean absolute rating difference
- Median absolute rating difference
- Percentage of exactly equal ratings
- Percentage within `0.5` stars
- Strong disagreements: rating difference `>= 2.0`

Sort the pairwise table by mean absolute rating difference ascending:

- Most similar pairs at the top
- Most dissimilar pairs at the bottom

Even pairs with fewer common films should still be included, with the common film count clearly visible.

## Pairwise Detail Tables

For each pair, show:

- Biggest disagreements
- Exact same ratings
- Shared favorites: both users rated the film `>= 4.5`
- Shared dislikes: both users rated the film `<= 2.5`

## Group Metrics

Use films rated by at least 3 out of 4 users.

For each qualifying film, calculate:

- Number of raters
- Average group rating
- Rating spread: `max rating - min rating`
- Rating standard deviation

## Group Tables

Consensus favorites:

- Rated by at least 3 users
- Average rating `>= 4.0`
- Rating spread `<= 1.0`

Consensus dislikes:

- Rated by at least 3 users
- Average rating `<= 3.0`
- Rating spread `<= 1.0`

Most divisive films:

- Rated by at least 3 users
- Sort by rating spread descending
- Then sort by standard deviation descending

One person against the group:

- Rated by at least 3 users
- A user is an outlier when `abs(user rating - average rating of the other users) >= 1.5`
