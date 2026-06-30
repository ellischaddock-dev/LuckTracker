# Cheesepionship Luck Tracker

A Streamlit app for a Fantrax fantasy football league. It calculates standings, all-play expected points, schedule luck, fixture comparisons and season records using the draw rule configured for each season.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Add or update results

Edit `data/results.csv`. Each fixture is one row:

```csv
season,gameweek,home_team,home_score,away_team,away_score
2025-26,39,Team A,101.25,Team B,94.00
```

A gameweek should contain one fixture for every pair of teams playing that week.

## Configure each season's draw rule

Edit `data/seasons.csv` and add one row for every season included in `results.csv`:

```csv
season,draw_margin
2025-26,5
2024-25,0
```

- `5` means scores within five points, inclusive, are draws. A win requires a margin greater than five.
- `0` means only an exact tie is a draw. Any positive margin is a win.

The app stops with a clear warning if results exist for a season that has not been added to `seasons.csv`.

## Team abbreviations

Homepage headline cards use abbreviations from `data/teams.csv`:

```csv
team,abbreviation
Team Beige,BGE
```

Teams without a configured abbreviation fall back to their full name.

## Deploy

1. Upload every file in this folder to a GitHub repository.
2. In Streamlit Community Cloud, choose **Create app**.
3. Select the repository and branch.
4. Set the main file path to `app.py`.
5. Deploy.

Commit and push future CSV updates to GitHub. Streamlit Community Cloud will reload the repository.
