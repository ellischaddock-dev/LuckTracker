from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

st.set_page_config(page_title="Cheesepionship Luck Tracker", page_icon="⚽", layout="wide")
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "results.csv"
SEASONS_FILE = DATA_DIR / "seasons.csv"
TEAMS_FILE = DATA_DIR / "teams.csv"

@st.cache_data
def load_results(file_version):
    df = pd.read_csv(DATA_FILE)
    numeric = ["gameweek", "home_score", "away_score"]
    df[numeric] = df[numeric].apply(pd.to_numeric)
    df["season"] = df["season"].astype(str)
    return df.sort_values(["season", "gameweek"]).reset_index(drop=True)

@st.cache_data
def load_season_settings(file_version):
    settings = pd.read_csv(SEASONS_FILE, dtype={"season": str})
    settings["draw_margin"] = pd.to_numeric(settings["draw_margin"])
    return settings.set_index("season")["draw_margin"].to_dict()

@st.cache_data
def load_team_abbreviations(file_version):
    teams = pd.read_csv(TEAMS_FILE)
    if "abbreviation" not in teams.columns:
        return {team: team for team in teams["team"]}
    return {
        row.team: row.abbreviation if pd.notna(row.abbreviation) and str(row.abbreviation).strip() else row.team
        for row in teams.itertuples(index=False)
    }

def long_results(fixtures, draw_margin):
    home = fixtures.rename(columns={"home_team":"team","away_team":"opponent","home_score":"score","away_score":"opponent_score"})
    away = fixtures.rename(columns={"away_team":"team","home_team":"opponent","away_score":"score","home_score":"opponent_score"})
    cols=["season","gameweek","team","opponent","score","opponent_score"]
    games=pd.concat([home[cols],away[cols]],ignore_index=True)
    margin=games["score"]-games["opponent_score"]
    games["result"]=np.select([margin>draw_margin, margin<-draw_margin],["W","L"],default="D")
    games["league_points"]=games["result"].map({"W":3,"D":1,"L":0})
    games["margin"]=margin
    return games.sort_values(["gameweek","team"]).reset_index(drop=True)

def add_all_play(games, draw_margin):
    records=[]
    for (season,gw), group in games.groupby(["season","gameweek"]):
        scores=group.set_index("team")["score"].to_dict()
        weekly_mean=np.mean(list(scores.values())); weekly_median=np.median(list(scores.values()))
        for team,score in scores.items():
            comparisons=[]
            for other, other_score in scores.items():
                if other==team: continue
                diff=score-other_score
                comparisons.append(3 if diff>draw_margin else 0 if diff<-draw_margin else 1)
            expected=np.mean(comparisons)
            records.append({"season":season,"gameweek":gw,"team":team,"all_play_points":expected,
                            "all_play_wins":sum(x==3 for x in comparisons),"all_play_draws":sum(x==1 for x in comparisons),
                            "weekly_rank":1+sum(v>score for v in scores.values()),"weekly_mean":weekly_mean,
                            "weekly_median":weekly_median})
    metrics=pd.DataFrame(records)
    result=games.merge(metrics,on=["season","gameweek","team"],how="left")
    result["weekly_luck"]=result["league_points"]-result["all_play_points"]
    return result

def standings(games, all_time=False):
    table=games.groupby("team").agg(P=("gameweek","count"),W=("result",lambda s:(s=="W").sum()),
        D=("result",lambda s:(s=="D").sum()),L=("result",lambda s:(s=="L").sum()),
        Pts=("league_points","sum"),PF=("score","sum"),PA=("opponent_score","sum"),
        Expected_Pts=("all_play_points","sum"),Schedule_Luck=("weekly_luck","sum"),
        Avg_Opp_Score=("opponent_score","mean"),Avg_Weekly_Rank=("weekly_rank","mean")).reset_index()
    table["Diff"]=table.PF-table.PA
    table["PPG"]=table.Pts/table.P
    table["Expected_PPG"]=table.Expected_Pts/table.P
    table["Luck_per_game"]=table.Schedule_Luck/table.P
    if all_time:
        table=table.sort_values(["PPG","PF"],ascending=[False,False]).reset_index(drop=True)
    else:
        table=table.sort_values(["Pts","PF"],ascending=[False,False]).reset_index(drop=True)
    table.insert(0,"Pos",range(1,len(table)+1))
    return table

def fixture_record(games, score_team, fixture_team, draw_margin):
    score_map=games.set_index(["gameweek","team"])["score"].to_dict()
    fixture_map=games.set_index(["gameweek","team"])["opponent"].to_dict()
    weeks=sorted(games.gameweek.unique())
    rows=[]
    for gw in weeks:
        opp=fixture_map[(gw,fixture_team)]
        # When the fixture owner played the score owner, preserve that head-to-head pairing.
        if opp==score_team:
            opp=fixture_team
        score=score_map[(gw,score_team)]
        opp_score=score_map[(gw,opp)]
        diff=score-opp_score
        result="W" if diff>draw_margin else "L" if diff<-draw_margin else "D"
        rows.append({"gameweek":gw,"opponent":opp,"score":score,"opponent_score":opp_score,"result":result,
                     "points":{"W":3,"D":1,"L":0}[result],"margin":diff})
    return pd.DataFrame(rows)

def swapped_fixture_standings(games, team_a, team_b, draw_margin):
    actual_table=standings(games)
    actual_positions=actual_table.set_index("team")["Pos"].to_dict()

    rec_a=fixture_record(games,team_a,team_b,draw_margin)
    rec_b=fixture_record(games,team_b,team_a,draw_margin)
    replacements={team_a:rec_a,team_b:rec_b}

    rows=[]
    for team, group in games.groupby("team"):
        if team in replacements:
            r=replacements[team]
            rows.append({
                "team":team,"P":len(r),"W":(r.result=="W").sum(),"D":(r.result=="D").sum(),
                "L":(r.result=="L").sum(),"Pts":r.points.sum(),"PF":r.score.sum(),
                "PA":r.opponent_score.sum(),"Diff":r.score.sum()-r.opponent_score.sum()
            })
        else:
            rows.append({
                "team":team,"P":len(group),"W":(group.result=="W").sum(),"D":(group.result=="D").sum(),
                "L":(group.result=="L").sum(),"Pts":group.league_points.sum(),"PF":group.score.sum(),
                "PA":group.opponent_score.sum(),"Diff":group.score.sum()-group.opponent_score.sum()
            })
    new_table=pd.DataFrame(rows).sort_values(["Pts","PF"],ascending=[False,False]).reset_index(drop=True)
    new_table.insert(0,"Pos",range(1,len(new_table)+1))
    new_positions=new_table.set_index("team")["Pos"].to_dict()
    return rec_a,rec_b,actual_table,new_table,actual_positions,new_positions

def longest_streak(results, accepted):
    best=0; current=0
    for result in results:
        if result in accepted: current+=1; best=max(best,current)
        else: current=0
    return best

def record_rows(games):
    unique=games.sort_values(["season","gameweek","team"]).drop_duplicates(["season","gameweek","team"])
    matches=unique[unique.team < unique.opponent].copy()
    matches["combined"]=matches.score+matches.opponent_score
    records=[]
    def where(row):
        return f"{row.season} · GW{row.gameweek}"
    def add(name,row,value):
        records.append({"Record":name,"Team / Match":row,"Value":value})
    r=unique.loc[unique.score.idxmax()]; add("Highest score",f"{r.team} — {where(r)}",f"{r.score:.2f}")
    r=unique.loc[unique.score.idxmin()]; add("Lowest score",f"{r.team} — {where(r)}",f"{r.score:.2f}")
    losses=unique[unique.result=="L"]
    if len(losses):
        r=losses.loc[losses.score.idxmax()]; add("Highest score in a loss",f"{r.team} vs {r.opponent} — {where(r)}",f"{r.score:.2f}")
    wins=unique[unique.result=="W"]
    if len(wins):
        r=wins.loc[wins.score.idxmin()]; add("Lowest score in a win",f"{r.team} vs {r.opponent} — {where(r)}",f"{r.score:.2f}")
        r=wins.loc[wins.margin.idxmax()]; add("Biggest win",f"{r.team} vs {r.opponent} — {where(r)}",f"{r.margin:.2f} pts")
        r=wins.loc[wins.margin.idxmin()]; add("Tightest win",f"{r.team} vs {r.opponent} — {where(r)}",f"{r.margin:.2f} pts")
    if len(matches):
        r=matches.loc[matches.combined.idxmax()]; add("Highest-scoring match",f"{r.team} vs {r.opponent} — {where(r)}",f"{r.combined:.2f}")
        r=matches.loc[matches.combined.idxmin()]; add("Lowest-scoring match",f"{r.team} vs {r.opponent} — {where(r)}",f"{r.combined:.2f}")
    for label,accepted in [("Longest winning streak",{"W"}),("Longest unbeaten streak",{"W","D"}),("Longest losing streak",{"L"}),("Longest winless streak",{"L","D"})]:
        vals=[]
        for (season_name,team),g in unique.sort_values(["season","gameweek"]).groupby(["season","team"]):
            vals.append((longest_streak(g.result.tolist(),accepted),team,season_name))
        length,team,season_name=max(vals); add(label,f"{team} — {season_name}",str(length))
    return pd.DataFrame(records)

raw=load_results(DATA_FILE.stat().st_mtime_ns)
season_settings=load_season_settings(SEASONS_FILE.stat().st_mtime_ns)
team_abbreviations=load_team_abbreviations(TEAMS_FILE.stat().st_mtime_ns)
seasons=sorted(raw.season.unique(),reverse=True)
season=st.sidebar.selectbox("Season",["All time"]+seasons)
is_all_time=season=="All time"

if is_all_time:
    missing=[s for s in seasons if s not in season_settings]
    if missing:
        st.error("No draw margin has been configured for: " + ", ".join(missing) + ". Add them to data/seasons.csv.")
        st.stop()
    game_parts=[]
    for season_name, season_fixtures in raw.groupby("season", sort=False):
        margin=float(season_settings[season_name])
        game_parts.append(add_all_play(long_results(season_fixtures, margin), margin))
    games=pd.concat(game_parts, ignore_index=True).sort_values(["season","gameweek","team"]).reset_index(drop=True)
    week_range=None
    draw_margin=None
else:
    season_raw=raw[raw.season==season]
    if season not in season_settings:
        st.error(f"No draw margin has been configured for season {season}. Add it to data/seasons.csv.")
        st.stop()
    draw_margin=float(season_settings[season])
    max_week=int(season_raw.gameweek.max())
    week_range=st.sidebar.slider("Gameweeks",1,max_week,(1,max_week))
    filtered_raw=season_raw[season_raw.gameweek.between(*week_range)]
    games=add_all_play(long_results(filtered_raw, draw_margin), draw_margin)

teams=sorted(games.team.unique())
selected_team=st.sidebar.selectbox("Team", teams, key="global_team")
page=st.sidebar.radio("Page",["League overview","Team analysis","Fixture comparison","Season records","Methodology"])
if is_all_time:
    st.sidebar.caption("All seasons combined. Each season uses its own configured draw margin.")
else:
    margin_text = "Only exact ties are draws" if draw_margin == 0 else f"Draw margin: ±{draw_margin:g} points"
    st.sidebar.caption(f"{margin_text}. A win requires a margin greater than {draw_margin:g}.")

st.title("⚽ Cheesepionship Luck Tracker")
if is_all_time:
    st.caption(f"All time · {len(seasons)} seasons")
else:
    st.caption(f"{season} · Gameweeks {week_range[0]}–{week_range[1]}")

if page=="League overview":
    table=standings(games, all_time=is_all_time)
    luck_metric="Luck_per_game" if is_all_time else "Schedule_Luck"
    luckiest=table.loc[table[luck_metric].idxmax()]; unluckiest=table.loc[table[luck_metric].idxmin()]
    c1,c2,c3,c4=st.columns(4)
    leader_value=f"{table.iloc[0].PPG:.2f} PPG" if is_all_time else f"{table.iloc[0].Pts:.0f} pts"
    luck_suffix=" per game" if is_all_time else " pts"
    c1.metric("League leader",team_abbreviations.get(table.iloc[0].team, table.iloc[0].team),leader_value)
    c2.metric("Luckiest",team_abbreviations.get(luckiest.team, luckiest.team),f"{luckiest[luck_metric]:+.2f}{luck_suffix}")
    c3.metric("Unluckiest",team_abbreviations.get(unluckiest.team, unluckiest.team),f"{unluckiest[luck_metric]:+.2f}{luck_suffix}")
    highest_scorer=table.loc[table.PF.idxmax()]
    c4.metric("Highest scorer",team_abbreviations.get(highest_scorer.team, highest_scorer.team),f"{highest_scorer.PF:.2f}")
    st.subheader("Standings and schedule luck")
    if is_all_time:
        show=table.rename(columns={"Expected_PPG":"Expected PPG","Luck_per_game":"Luck per game","Avg_Opp_Score":"Avg opponent"})
        st.dataframe(show[["Pos","team","P","W","D","L","Pts","PPG","PF","PA","Diff","Expected PPG","Luck per game","Avg opponent"]],hide_index=True,use_container_width=True,
            column_config={"PPG":st.column_config.NumberColumn(format="%.3f"),"Expected PPG":st.column_config.NumberColumn(format="%.3f"),"Luck per game":st.column_config.NumberColumn(format="%+.3f"),"PF":st.column_config.NumberColumn(format="%.2f"),"PA":st.column_config.NumberColumn(format="%.2f")})
        chart = table[["team", "PPG", "Expected_PPG"]].rename(columns={"PPG":"Actual points per game","Expected_PPG":"Expected points per game"})
    else:
        show=table.rename(columns={"Expected_Pts":"Expected pts","Schedule_Luck":"Luck","Avg_Opp_Score":"Avg opponent","Avg_Weekly_Rank":"Avg weekly rank"})
        st.dataframe(show[["Pos","team","P","W","D","L","Pts","PF","PA","Diff","Expected pts","Luck","Avg opponent","Avg weekly rank"]],hide_index=True,use_container_width=True,
            column_config={"Luck":st.column_config.NumberColumn(format="%+.2f"),"Expected pts":st.column_config.NumberColumn(format="%.2f"),"PF":st.column_config.NumberColumn(format="%.2f"),"PA":st.column_config.NumberColumn(format="%.2f")})
        chart = table[["team", "Pts", "Expected_Pts"]].rename(columns={"Pts": "Actual points", "Expected_Pts": "Expected points"})
    chart = chart.melt(id_vars="team",var_name="Point type",value_name="Points")
    order_col="PPG" if is_all_time else "Pts"
    team_order = table.sort_values(order_col, ascending=False)["team"].tolist()
    st.subheader("Actual versus all-play expected points" + (" per game" if is_all_time else ""))
    comparison_chart = (
        alt.Chart(chart)
        .mark_bar()
        .encode(
            y=alt.Y("team:N", sort=team_order, title=None),
            x=alt.X("Points:Q", title="League points"),
            yOffset=alt.YOffset("Point type:N"),
            color=alt.Color("Point type:N", title=None),
            tooltip=[
                alt.Tooltip("team:N", title="Team"),
                alt.Tooltip("Point type:N"),
                alt.Tooltip("Points:Q", format=".2f"),
            ],
        )
        .properties(height=max(360, len(table) * 34))
    )
    st.altair_chart(comparison_chart, use_container_width=True)

elif page=="Team analysis":
    team=selected_team
    st.subheader(team)
    tg=games[games.team==team].sort_values(["season","gameweek"])
    total=tg.league_points.sum(); expected=tg.all_play_points.sum(); luck=total-expected
    c1,c2,c3,c4=st.columns(4)
    c1.metric("League points",f"{total:.0f}")
    c2.metric("Expected points",f"{expected:.2f}")
    c3.metric("Schedule luck",f"{luck:+.2f}")
    if is_all_time:
        c4.metric("Points per game",f"{total/len(tg):.3f}")
        by_season=(tg.groupby("season",as_index=False)
            .agg(league_points=("league_points","sum"),all_play_points=("all_play_points","sum"),games=("gameweek","count")))
        season_order=[s for s in sorted(seasons) if s in by_season.season.values]
        by_season["season"]=pd.Categorical(by_season["season"],categories=season_order,ordered=True)
        by_season=by_season.sort_values("season")
        by_season[["league_points","all_play_points"]]=by_season[["league_points","all_play_points"]].cumsum()
        cumulative=by_season.set_index("season")[["league_points","all_play_points"]]
        st.subheader("Cumulative actual and expected points by season")
        st.line_chart(cumulative)
        season_summary=(tg.groupby("season",as_index=False)
            .agg(P=("gameweek","count"),W=("result",lambda s:(s=="W").sum()),D=("result",lambda s:(s=="D").sum()),L=("result",lambda s:(s=="L").sum()),Pts=("league_points","sum"),Expected_Pts=("all_play_points","sum"),PF=("score","sum"),PA=("opponent_score","sum")))
        season_summary["PPG"]=season_summary.Pts/season_summary.P
        season_summary["Luck"]=season_summary.Pts-season_summary.Expected_Pts
        season_summary["Diff"]=season_summary.PF-season_summary.PA
        st.subheader("Season-by-season record")
        st.dataframe(season_summary[["season","P","W","D","L","Pts","PPG","Expected_Pts","Luck","PF","PA","Diff"]],hide_index=True,use_container_width=True,
            column_config={"PPG":st.column_config.NumberColumn(format="%.3f"),"Expected_Pts":st.column_config.NumberColumn(format="%.2f"),"Luck":st.column_config.NumberColumn(format="%+.2f"),"PF":st.column_config.NumberColumn(format="%.2f"),"PA":st.column_config.NumberColumn(format="%.2f"),"Diff":st.column_config.NumberColumn(format="%+.2f")})
    else:
        c4.metric("Average weekly rank",f"{tg.weekly_rank.mean():.2f} / {len(teams)}")
        cumulative=tg[["gameweek","league_points","all_play_points"]].copy(); cumulative[["league_points","all_play_points"]]=cumulative[["league_points","all_play_points"]].cumsum(); cumulative=cumulative.set_index("gameweek")
        st.subheader("Cumulative actual and expected points")
        st.line_chart(cumulative)
        detail=tg[["gameweek","opponent","score","opponent_score","result","league_points","all_play_points","weekly_luck","weekly_rank"]].copy()
        detail.columns=["GW","Opponent","Score","Opponent score","Result","Points","Expected points","Luck","Weekly rank"]
        st.subheader("Weekly detail")
        st.dataframe(detail,hide_index=True,use_container_width=True,column_config={"Luck":st.column_config.NumberColumn(format="%+.2f"),"Expected points":st.column_config.NumberColumn(format="%.2f")})

    st.subheader("Record against each opponent")
    opponent_record=(tg.groupby("opponent", as_index=False).agg(P=("gameweek","count"),W=("result",lambda s:(s=="W").sum()),D=("result",lambda s:(s=="D").sum()),L=("result",lambda s:(s=="L").sum()),Pts=("league_points","sum"),PF=("score","sum"),PA=("opponent_score","sum")).rename(columns={"opponent":"Opponent"}))
    opponent_record["PPG"]=opponent_record.Pts/opponent_record.P
    opponent_record["Diff"]=opponent_record.PF-opponent_record.PA
    opponent_record=opponent_record.sort_values(["PPG","Diff","PF"],ascending=[False,False,False]).reset_index(drop=True)
    cols=["Opponent","P","W","D","L","Pts"] + (["PPG"] if is_all_time else []) + ["PF","PA","Diff"]
    st.dataframe(opponent_record[cols],hide_index=True,use_container_width=True,column_config={"PPG":st.column_config.NumberColumn(format="%.3f"),"PF":st.column_config.NumberColumn(format="%.2f"),"PA":st.column_config.NumberColumn(format="%.2f"),"Diff":st.column_config.NumberColumn(format="%+.2f")})

elif page=="Fixture comparison":
    if is_all_time:
        st.info("Fixture comparison is available for individual seasons only, because teams and fixture structures differ across seasons.")
        st.stop()
    st.write("Swap the two selected teams' fixture lists while keeping each team's own weekly scores. Weeks where they played each other remain unchanged.")
    score_team=selected_team
    st.caption(f"Using scores from **{score_team}**, selected in the sidebar.")
    fixture_options=[team for team in teams if team != score_team]
    fixture_team=st.selectbox("Use fixtures from",fixture_options)

    if score_team==fixture_team:
        st.info("Select two different teams to compare their swapped fixture outcomes.")
    else:
        rec_a,rec_b,actual_table,new_table,actual_positions,new_positions=swapped_fixture_standings(games,score_team,fixture_team,draw_margin)
        actual_lookup=actual_table.set_index("team")

        def summary_row(team, swapped_record):
            actual=actual_lookup.loc[team]
            new_pos=int(new_positions[team])
            old_pos=int(actual_positions[team])
            return {
                "Team":team,
                "Actual position":old_pos,
                "New position":new_pos,
                "Position change":old_pos-new_pos,
                "Actual points":int(actual.Pts),
                "New points":int(swapped_record.points.sum()),
                "Points change":int(swapped_record.points.sum()-actual.Pts),
                "W":int((swapped_record.result=="W").sum()),
                "D":int((swapped_record.result=="D").sum()),
                "L":int((swapped_record.result=="L").sum()),
                "PF":float(swapped_record.score.sum()),
                "PA":float(swapped_record.opponent_score.sum()),
                "Diff":float(swapped_record.score.sum()-swapped_record.opponent_score.sum()),
            }

        summary=pd.DataFrame([summary_row(score_team,rec_a),summary_row(fixture_team,rec_b)])
        st.subheader("Results after swapping fixtures")
        st.dataframe(
            summary,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Position change":st.column_config.NumberColumn(help="Positive means the team moves up the table.",format="%+d"),
                "Points change":st.column_config.NumberColumn(format="%+d"),
                "PF":st.column_config.NumberColumn(format="%.2f"),
                "PA":st.column_config.NumberColumn(format="%.2f"),
                "Diff":st.column_config.NumberColumn(format="%+.2f"),
            },
        )

        left,right=st.columns(2)
        for container,team,record,borrowed_from in [
            (left,score_team,rec_a,fixture_team),
            (right,fixture_team,rec_b,score_team),
        ]:
            with container:
                st.subheader(team)
                old_pos=int(actual_positions[team]); new_pos=int(new_positions[team])
                actual_pts=int(actual_lookup.loc[team,"Pts"]); new_pts=int(record.points.sum())
                m1,m2,m3=st.columns(3)
                m1.metric("League position",new_pos,f"{old_pos-new_pos:+d} places")
                m2.metric("League points",new_pts,f"{new_pts-actual_pts:+d}")
                m3.metric("Record",f"{(record.result=='W').sum()}-{(record.result=='D').sum()}-{(record.result=='L').sum()}")
                detail=record.rename(columns={
                    "gameweek":"GW","opponent":"Opponent","score":"Score","opponent_score":"Opponent score",
                    "result":"Result","points":"Points","margin":"Margin"
                })
                st.caption(f"Using {borrowed_from}'s fixtures")
                st.dataframe(detail[["GW","Opponent","Score","Opponent score","Result","Points","Margin"]],hide_index=True,use_container_width=True)

        st.subheader("Revised league table")
        revised=new_table.copy()
        revised["Change"]=revised.apply(lambda r: actual_positions[r.team]-r.Pos,axis=1)
        st.dataframe(
            revised[["Pos","Change","team","P","W","D","L","Pts","PF","PA","Diff"]],
            hide_index=True,
            use_container_width=True,
            column_config={"Change":st.column_config.NumberColumn(format="%+d"),"PF":st.column_config.NumberColumn(format="%.2f"),"PA":st.column_config.NumberColumn(format="%.2f"),"Diff":st.column_config.NumberColumn(format="%+.2f")},
        )

elif page=="Season records":
    st.subheader("Records for selected gameweeks")
    st.dataframe(record_rows(games),hide_index=True,use_container_width=True)
    group_cols=["season","gameweek"] if is_all_time else ["gameweek"]
    weekly = games.groupby(group_cols).agg(highest_score=("score", "max"),average_score=("score", "mean"),lowest_score=("score", "min")).reset_index()
    weekly = weekly.rename(columns={"highest_score":"Highest score","average_score":"Average score","lowest_score":"Lowest score"})
    st.subheader("Scoring by gameweek")
    if is_all_time:
        weekly["Season / GW"]=weekly["season"].astype(str)+" · GW"+weekly["gameweek"].astype(str)
        st.line_chart(weekly.set_index("Season / GW")[["Highest score","Average score","Lowest score"]])
    else:
        st.line_chart(weekly.set_index("gameweek"))

else:
    st.markdown(f"""
### How luck is measured
For every gameweek, each team is hypothetically compared with every other team in that season using the configured draw margin.

- win: score is higher by **more than the season's draw margin** — 3 points
- draw: score difference is **within the season's draw margin, inclusive** — 1 point
- loss: score is lower by **more than the season's draw margin** — 0 points

{"Each season uses the draw margin configured in data/seasons.csv." if is_all_time else f"The current season's draw margin is **{draw_margin:g}**. A margin of `0` means only an exact tie is a draw."}

The average points from those hypothetical matchups is the team's **all-play expected points** for that week.

**Schedule luck = actual league points − all-play expected points.**

A positive number means the team's real fixture produced more points than its weekly score would normally earn. A negative number means it ran into stronger-than-usual opposition.

### Fixture comparison
The comparison keeps a team's own scores but gives it another team's opponents. When the two selected teams played each other, that game remains a head-to-head match so neither team is compared with itself.

### Important limitation
This measures fixture and opponent luck. It does not attempt to measure injuries, transfers, lineup decisions, postponed matches, or underlying player performance.
""")
