# Cheesepionship Luck Tracker

A Streamlit app for a 12-team Fantrax fantasy football league. It uses the league's five-point draw margin to calculate standings, all-play expected points, schedule luck, fixture comparisons and season records.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Update each gameweek

Edit `data/results.csv` and add six rows in this format:

```csv
season,gameweek,home_team,home_score,away_team,away_score
2025-26,39,Team A,101.25,Team B,94.00
```

Commit and push the change to GitHub. Streamlit Community Cloud will reload the repository.

## Deploy

1. Create a GitHub repository and upload every file in this folder.
2. In Streamlit Community Cloud, choose **Create app**.
3. Select the repository and branch.
4. Set the main file path to `app.py`.
5. Deploy.

## Data rules

- Each gameweek should contain six fixtures and all 12 teams exactly once.
- A win requires a margin greater than five points.
- A margin from -5 through +5 is a draw.
- Team names must remain consistent across gameweeks.

The included CSV was extracted from `Luck Tracker Template - Cheesepionship 25-26.xlsx`.
