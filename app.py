from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

st.set_page_config(page_title="Cheesepionship Luck Tracker", page_icon="⚽", layout="wide")
DATA_FILE = Path(__file__).parent / "data" / "results.csv"
DRAW_MARGIN = 5.0

@st.cache_data
def load_results():
    df = pd.read_csv(DATA_FILE)
    numeric = ["gameweek", "home_score", "away_score"]
    df[numeric] = df[numeric].apply(pd.to_numeric)
    return df.sort_values(["season", "gameweek"]).reset_index(drop=True)

def long_results(fixtures):
    home = fixtures.rename(columns={"home_team":"team","away_team":"opponent","home_score":"score","away_score":"opponent_score"})
    away = fixtures.rename(columns={"away_team":"team","home_team":"opponent","away_score":"score","home_score":"opponent_score"})
    cols=["season","gameweek","team","opponent","score","opponent_score"]
    games=pd.concat([home[cols],away[cols]],ignore_index=True)
    margin=games["score"]-games["opponent_score"]
    games["result"]=np.select([margin>DRAW_MARGIN, margin<-DRAW_MARGIN],["W","L"],default="D")
    games["league_points"]=games["result"].map({"W":3,"D":1,"L":0})
    games["margin"]=margin
    return games.sort_values(["gameweek","team"]).reset_index(drop=True)

def add_all_play(games):
    records=[]
    for (season,gw), group in games.groupby(["season","gameweek"]):
        scores=group.set_index("team")["score"].to_dict()
        weekly_mean=np.mean(list(scores.values())); weekly_median=np.median(list(scores.values()))
        for team,score in scores.items():
            comparisons=[]
            for other, other_score in scores.items():
                if other==team: continue
                diff=score-other_score
                comparisons.append(3 if diff>DRAW_MARGIN else 0 if diff<-DRAW_MARGIN else 1)
            expected=np.mean(comparisons)
            records.append({"season":season,"gameweek":gw,"team":team,"all_play_points":expected,
                            "all_play_wins":sum(x==3 for x in comparisons),"all_play_draws":sum(x==1 for x in comparisons),
                            "weekly_rank":1+sum(v>score for v in scores.values()),"weekly_mean":weekly_mean,
                            "weekly_median":weekly_median})
    metrics=pd.DataFrame(records)
    result=games.merge(metrics,on=["season","gameweek","team"],how="left")
    result["weekly_luck"]=result["league_points"]-result["all_play_points"]
    return result

def standings(games):
    table=games.groupby("team").agg(P=("gameweek","count"),W=("result",lambda s:(s=="W").sum()),
        D=("result",lambda s:(s=="D").sum()),L=("result",lambda s:(s=="L").sum()),
        Pts=("league_points","sum"),PF=("score","sum"),PA=("opponent_score","sum"),
        Expected_Pts=("all_play_points","sum"),Schedule_Luck=("weekly_luck","sum"),
        Avg_Opp_Score=("opponent_score","mean"),Avg_Weekly_Rank=("weekly_rank","mean")).reset_index()
    table["Diff"]=table.PF-table.PA
    table["Luck_per_week"]=table.Schedule_Luck/table.P
    table=table.sort_values(["Pts","PF"],ascending=[False,False]).reset_index(drop=True)
    table.insert(0,"Pos",range(1,len(table)+1))
    return table

def fixture_record(games, score_team, fixture_team):
    score_map=games.set_index(["gameweek","team"])["score"].to_dict()
    fixture_map=games.set_index(["gameweek","team"])["opponent"].to_dict()
    weeks=sorted(games.gameweek.unique())
    rows=[]
    for gw in weeks:
        opp=fixture_map[(gw,fixture_team)]
        # When the fixture owner played the score owner, preserve that head-to-head pairing.
        if opp==score_team: opp=fixture_team
        score=score_map[(gw,score_team)]; opp_score=score_map[(gw,opp)]
        diff=score-opp_score; result="W" if diff>DRAW_MARGIN else "L" if diff<-DRAW_MARGIN else "D"
        rows.append({"gameweek":gw,"opponent":opp,"score":score,"opponent_score":opp_score,"result":result,
                     "points":{"W":3,"D":1,"L":0}[result]})
    return pd.DataFrame(rows)

def longest_streak(results, accepted):
    best=0; current=0
    for result in results:
        if result in accepted: current+=1; best=max(best,current)
        else: current=0
    return best

def record_rows(games):
    unique=games.sort_values(["gameweek","team"]).drop_duplicates(["gameweek","team"])
    matches=unique[unique.team < unique.opponent].copy()
    matches["combined"]=matches.score+matches.opponent_score
    records=[]
    def add(name,row,value):
        records.append({"Record":name,"Team / Match":row,"Value":value})
    r=unique.loc[unique.score.idxmax()]; add("Highest score",f"{r.team} — GW{r.gameweek}",f"{r.score:.2f}")
    r=unique.loc[unique.score.idxmin()]; add("Lowest score",f"{r.team} — GW{r.gameweek}",f"{r.score:.2f}")
    losses=unique[unique.result=="L"]
    if len(losses): r=losses.loc[losses.score.idxmax()]; add("Highest score in a loss",f"{r.team} vs {r.opponent} — GW{r.gameweek}",f"{r.score:.2f}")
    wins=unique[unique.result=="W"]
    if len(wins):
        r=wins.loc[wins.score.idxmin()]; add("Lowest score in a win",f"{r.team} vs {r.opponent} — GW{r.gameweek}",f"{r.score:.2f}")
        r=wins.loc[wins.margin.idxmax()]; add("Biggest win",f"{r.team} vs {r.opponent} — GW{r.gameweek}",f"{r.margin:.2f} pts")
        r=wins.loc[wins.margin.idxmin()]; add("Tightest win",f"{r.team} vs {r.opponent} — GW{r.gameweek}",f"{r.margin:.2f} pts")
    if len(matches):
        r=matches.loc[matches.combined.idxmax()]; add("Highest-scoring match",f"{r.team} vs {r.opponent} — GW{r.gameweek}",f"{r.combined:.2f}")
        r=matches.loc[matches.combined.idxmin()]; add("Lowest-scoring match",f"{r.team} vs {r.opponent} — GW{r.gameweek}",f"{r.combined:.2f}")
    for label,accepted in [("Longest winning streak",{"W"}),("Longest unbeaten streak",{"W","D"}),("Longest losing streak",{"L"}),("Longest winless streak",{"L","D"})]:
        vals=[]
        for team,g in unique.sort_values("gameweek").groupby("team"):
            vals.append((longest_streak(g.result.tolist(),accepted),team))
        length,team=max(vals); add(label,team,str(length))
    return pd.DataFrame(records)

raw=load_results()
seasons=sorted(raw.season.unique(),reverse=True)
season=st.sidebar.selectbox("Season",seasons)
season_raw=raw[raw.season==season]
max_week=int(season_raw.gameweek.max())
week_range=st.sidebar.slider("Gameweeks",1,max_week,(1,max_week))
filtered_raw=season_raw[season_raw.gameweek.between(*week_range)]
games=add_all_play(long_results(filtered_raw))
teams=sorted(games.team.unique())
page=st.sidebar.radio("Page",["League overview","Team analysis","Fixture comparison","Season records","Methodology"])
st.sidebar.caption(f"Draw margin: ±{DRAW_MARGIN:g} points. A win requires a margin greater than {DRAW_MARGIN:g}.")

st.title("⚽ Cheesepionship Luck Tracker")
st.caption(f"{season} · Gameweeks {week_range[0]}–{week_range[1]}")

if page=="League overview":
    table=standings(games)
    luckiest=table.loc[table.Schedule_Luck.idxmax()]; unluckiest=table.loc[table.Schedule_Luck.idxmin()]
    c1,c2,c3,c4=st.columns(4)
    c1.metric("League leader",table.iloc[0].team,f"{table.iloc[0].Pts:.0f} pts")
    c2.metric("Luckiest",luckiest.team,f"{luckiest.Schedule_Luck:+.2f} pts")
    c3.metric("Unluckiest",unluckiest.team,f"{unluckiest.Schedule_Luck:+.2f} pts")
    c4.metric("Highest scorer",table.loc[table.PF.idxmax()].team,f"{table.PF.max():.2f}")
    st.subheader("Standings and schedule luck")
    show=table.rename(columns={"Expected_Pts":"Expected pts","Schedule_Luck":"Luck","Avg_Opp_Score":"Avg opponent","Avg_Weekly_Rank":"Avg weekly rank"})
    st.dataframe(show[["Pos","team","P","W","D","L","Pts","PF","PA","Diff","Expected pts","Luck","Avg opponent","Avg weekly rank"]],hide_index=True,use_container_width=True,
        column_config={"Luck":st.column_config.NumberColumn(format="%+.2f"),"Expected pts":st.column_config.NumberColumn(format="%.2f"),"PF":st.column_config.NumberColumn(format="%.2f"),"PA":st.column_config.NumberColumn(format="%.2f")})
    chart = table[["team", "Pts", "Expected_Pts"]].rename(
        columns={"Pts": "Actual points", "Expected_Pts": "Expected points"}
    )
    chart = chart.melt(
        id_vars="team",
        var_name="Point type",
        value_name="Points",
    )
    team_order = table.sort_values("Pts", ascending=False)["team"].tolist()
    st.subheader("Actual versus all-play expected points")
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
    team=st.selectbox("Team",teams)
    tg=games[games.team==team].sort_values("gameweek")
    total=tg.league_points.sum(); expected=tg.all_play_points.sum(); luck=total-expected
    c1,c2,c3,c4=st.columns(4)
    c1.metric("League points",f"{total:.0f}")
    c2.metric("Expected points",f"{expected:.2f}")
    c3.metric("Schedule luck",f"{luck:+.2f}")
    c4.metric("Average weekly rank",f"{tg.weekly_rank.mean():.2f} / {len(teams)}")
    cumulative=tg[["gameweek","league_points","all_play_points"]].copy(); cumulative[["league_points","all_play_points"]]=cumulative[["league_points","all_play_points"]].cumsum(); cumulative=cumulative.set_index("gameweek")
    st.subheader("Cumulative actual and expected points")
    st.line_chart(cumulative)
    detail=tg[["gameweek","opponent","score","opponent_score","result","league_points","all_play_points","weekly_luck","weekly_rank"]].copy()
    detail.columns=["GW","Opponent","Score","Opponent score","Result","Points","Expected points","Luck","Weekly rank"]
    st.subheader("Weekly detail")
    st.dataframe(detail,hide_index=True,use_container_width=True,column_config={"Luck":st.column_config.NumberColumn(format="%+.2f"),"Expected points":st.column_config.NumberColumn(format="%.2f")})

elif page=="Fixture comparison":
    st.write("Apply one team's weekly scores to another team's fixture list. Weeks where the two selected teams played each other retain that head-to-head pairing.")
    c1,c2=st.columns(2)
    score_team=c1.selectbox("Use scores from",teams)
    fixture_team=c2.selectbox("Use fixtures from",teams,index=min(1,len(teams)-1))
    comparison=fixture_record(games,score_team,fixture_team)
    actual=fixture_record(games,score_team,score_team)
    c1,c2,c3=st.columns(3)
    c1.metric("Actual points",int(actual.points.sum()))
    c2.metric("With selected fixtures",int(comparison.points.sum()))
    c3.metric("Difference",f"{comparison.points.sum()-actual.points.sum():+.0f}")
    st.dataframe(comparison,hide_index=True,use_container_width=True)

elif page=="Season records":
    st.subheader("Records for selected gameweeks")
    st.dataframe(record_rows(games),hide_index=True,use_container_width=True)
    weekly = games.groupby("gameweek").agg(
        highest_score=("score", "max"),
        average_score=("score", "mean"),
        lowest_score=("score", "min"),
    ).reset_index()
    weekly = weekly.rename(columns={
        "highest_score": "Highest score",
        "average_score": "Average score",
        "lowest_score": "Lowest score",
    })
    st.subheader("Scoring by gameweek")
    st.line_chart(weekly.set_index("gameweek"))

else:
    st.markdown("""
### How luck is measured
For every gameweek, each team is hypothetically compared with all 11 other scores using the same league rule:

- win: score is **more than 5 points higher** — 3 points
- draw: scores are **within 5 points inclusive** — 1 point
- loss: score is **more than 5 points lower** — 0 points

The average points from those 11 hypothetical matchups is the team's **all-play expected points** for that week.

**Schedule luck = actual league points − all-play expected points.**

A positive number means the team's real fixture produced more points than its weekly score would normally earn. A negative number means it ran into stronger-than-usual opposition.

### Fixture comparison
The comparison keeps a team's own scores but gives it another team's opponents. When the two selected teams played each other, that game remains a head-to-head match so neither team is compared with itself.

### Important limitation
This measures fixture and opponent luck. It does not attempt to measure injuries, transfers, lineup decisions, postponed matches, or underlying player performance.
""")
