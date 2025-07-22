import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone

# Optional: import google.generativeai as genai if you have Gemini, or remove if not using LLM at all

# --- Streamlit Theming (Light/NFL Style) ---
st.set_page_config(page_title="Welcome to the QWERK", layout="wide", initial_sidebar_state="expanded")
NFL_LIGHT = "#FAFAFA"
NFL_ACCENT = "#013369"
NFL_RED = "#D50A0A"
NFL_SILVER = "#A5ACAF"
NFL_WHITE = "#FFFFFF"
NFL_BLACK = "#101820"

st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {NFL_LIGHT};
            color: {NFL_BLACK};
        }}
        .css-1v0mbdj, .css-10trblm, .css-1d391kg, .st-bb, .st-at, .st-cq, .st-ce {{
            color: {NFL_BLACK} !important;
        }}
        .stButton > button {{
            background-color: {NFL_ACCENT};
            color: {NFL_WHITE};
            border-radius: 8px;
            border: 2px solid {NFL_SILVER};
            font-weight: bold;
        }}
        .stSelectbox > div {{background: "#FAFAFA"}}
        .stDataFrame, .stPlotlyChart {{
            background-color: {NFL_WHITE} !important;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: {NFL_ACCENT} !important;
            font-family: "Arial Black", Arial, sans-serif;
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
            background: {NFL_ACCENT} !important;
            color: {NFL_WHITE} !important;
        }}
        .css-18e3th9 {{
            background-color: {NFL_WHITE} !important;
        }}
        .stTextInput>div>div>input, .stTextArea>div>textarea {{
            background-color: {NFL_WHITE} !important;
            color: {NFL_BLACK} !important;
        }}
    </style>
    """, unsafe_allow_html=True,
)

st.title("Welcome to the QWERK")

# --- API KEYS ---
odds_api_key = st.secrets["the_odds_api"]["key"]
rapid_api_key = st.secrets.get("rapid_api_key")
# Remove Gemini/Bing API key usage and related logic

CURRENT_YEAR = datetime.now().year
NFL_WEEKS = list(range(1, 19))
WEEK_LABELS = [f"Week {w}" for w in NFL_WEEKS]
selected_week_idx = st.sidebar.selectbox("Select NFL Week", range(len(WEEK_LABELS)), format_func=lambda i: WEEK_LABELS[i])
selected_week = NFL_WEEKS[selected_week_idx]

# --- Odds API Fetcher ---
@st.cache_data(ttl=600)
def get_odds(odds_api_key):
    url = f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/"
    params = {
        "apiKey": odds_api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american"
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return None, r.json().get("msg", "Failed to fetch data.")
    return r.json(), None

# --- RapidAPI Fetcher Example: NFL stats for current week ---
@st.cache_data(ttl=1800)
def get_weekly_stats(rapid_api_key, week, year):
    # Replace with your actual rapidapi stats endpoint and parameters
    url = f"https://api-nfl-stats-example.p.rapidapi.com/nfl/week-stats"
    headers = {
        "X-RapidAPI-Key": rapid_api_key,
        "X-RapidAPI-Host": "api-nfl-stats-example.p.rapidapi.com"
    }
    params = {"week": week, "season": year}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        return None, r.json().get("message", "Failed to fetch data.")
    return r.json(), None

odds_data, odds_error = get_odds(odds_api_key)
stats_data, stats_error = get_weekly_stats(rapid_api_key, selected_week, CURRENT_YEAR) if rapid_api_key else (None, "No Rapid API Key provided.")

if odds_error:
    st.error(f"Odds API error: {odds_error}")
    st.stop()
if not odds_data:
    st.info("No odds data available at this time.")
    st.stop()
if stats_error and rapid_api_key:
    st.warning(f"RapidAPI Stats error: {stats_error}")

TEAM_COLORS = {
    "Arizona Cardinals": "#97233F",
    "Atlanta Falcons": "#A71930",
    "Baltimore Ravens": "#241773",
    "Buffalo Bills": "#00338D",
    "Carolina Panthers": "#0085CA",
    "Chicago Bears": "#0B162A",
    "Cincinnati Bengals": "#FB4F14",
    "Cleveland Browns": "#311D00",
    "Dallas Cowboys": "#041E42",
    "Denver Broncos": "#002244",
    "Detroit Lions": "#0076B6",
    "Green Bay Packers": "#203731",
    "Houston Texans": "#03202F",
    "Indianapolis Colts": "#002C5F",
    "Jacksonville Jaguars": "#006778",
    "Kansas City Chiefs": "#E31837",
    "Las Vegas Raiders": "#000000",
    "Los Angeles Chargers": "#002A5E",
    "Los Angeles Rams": "#003594",
    "Miami Dolphins": "#008E97",
    "Minnesota Vikings": "#4F2683",
    "New England Patriots": "#002244",
    "New Orleans Saints": "#D3BC8D",
    "New York Giants": "#0B2265",
    "New York Jets": "#125740",
    "Philadelphia Eagles": "#004C54",
    "Pittsburgh Steelers": "#FFB612",
    "San Francisco 49ers": "#AA0000",
    "Seattle Seahawks": "#002244",
    "Tampa Bay Buccaneers": "#D50A0A",
    "Tennessee Titans": "#4B92DB",
    "Washington Commanders": "#5A1414",
}

def get_approx_week(game_date):
    season_start = datetime(CURRENT_YEAR, 9, 2, tzinfo=timezone.utc)
    return 1 + ((game_date - season_start).days // 7)

games_list = []
teams = set()
for game in odds_data:
    home = game["home_team"]
    away = game["away_team"]
    commence_time = pd.to_datetime(game["commence_time"])
    week = get_approx_week(commence_time)
    teams.update([home, away])
    for bookmaker in game.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            for outcome in market.get("outcomes", []):
                games_list.append({
                    "Week": week,
                    "Game": f"{home} vs {away}",
                    "Home": home,
                    "Away": away,
                    "Team": outcome["name"],
                    "Opponent": away if outcome["name"] == home else home,
                    "Bookmaker": bookmaker["title"],
                    "Market": market["key"],
                    "Price": outcome.get("price"),
                    "Point": outcome.get("point"),
                    "Date": commence_time,
                    "Bookmaker URL": bookmaker.get("url", ""),
                    "Kickoff": commence_time.strftime('%A, %b %d, %Y, %I:%M %p')
                })

odds_df = pd.DataFrame(games_list)
odds_df = odds_df[odds_df["Week"] == selected_week]
teams = sorted(list(set(odds_df["Home"]).union(set(odds_df["Away"]))))
team_options = teams

def add_odds_details(df):
    consensus = df.groupby(["Market", "Team"]).agg(
        Consensus_Price=("Price", "mean"),
        Consensus_Point=("Point", "mean"),
        Best_Price=("Price", "max"),
        Worst_Price=("Price", "min"),
        Book_Count=("Bookmaker", "count")
    ).reset_index()
    def implied_prob(price):
        if price > 0:
            return round(100 / (price + 100) * 100, 1)
        else:
            return round(abs(price) / (abs(price) + 100) * 100, 1)
    consensus["Implied_Prob_%"] = consensus["Consensus_Price"].apply(implied_prob)
    return consensus

def best_odds_row(df):
    idx = df.groupby(['Market', 'Team'])["Price"].idxmax()
    best = df.loc[idx][["Market","Team","Bookmaker","Price","Point","Bookmaker URL"]]
    return best.reset_index(drop=True)

def condense_stats(stats_data):
    if not stats_data or "teams" not in stats_data:
        return "No stats available."
    lines = []
    for team in stats_data["teams"]:
        lines.append(
            f"{team['name']}: Off Rank {team.get('offense_rank','?')}, Def Rank {team.get('defense_rank','?')}, Injuries {team.get('injuries','?')}, Last 5 {team.get('last5','?')}"
        )
    return "\n".join(lines)

def game_contexts(odds_df, stats_data):
    stats_lookup = {}
    if stats_data and "teams" in stats_data:
        for team in stats_data["teams"]:
            stats_lookup[team["name"]] = team
    games = []
    for game in odds_df.groupby("Game"):
        rows = game[1]
        home = rows.iloc[0]["Home"]
        away = rows.iloc[0]["Away"]
        kickoff = rows.iloc[0]["Kickoff"]
        game_odds = rows[["Market", "Team", "Price", "Point", "Bookmaker"]].to_dict(orient="records")
        home_stats = stats_lookup.get(home, {})
        away_stats = stats_lookup.get(away, {})
        games.append({
            "game": f"{home} vs {away}",
            "kickoff": kickoff,
            "home": home,
            "away": away,
            "odds": game_odds,
            "home_stats": home_stats,
            "away_stats": away_stats
        })
    return games

games_for_prompt = game_contexts(odds_df, stats_data)

tab1, tab2, tab3 = st.tabs(
    ["Current Odds", "Team Commentary", "Raw Data"]
)

with tab1:
    st.header("Current Odds")
    selected_team = st.selectbox(
        "Select NFL Team",
        team_options,
        format_func=lambda t: f"{t}",
    )
    team_color = TEAM_COLORS.get(selected_team, NFL_ACCENT)
    team_games = odds_df[(odds_df["Home"] == selected_team) | (odds_df["Away"] == selected_team)]

    if team_games.empty:
        st.write("No game found for this team in the selected week.")
    else:
        opponent = team_games.iloc[0]['Opponent']
        st.markdown(
            f"<h3 style='color:{team_color};'>Odds for {selected_team} <span style='color:{NFL_SILVER};'>vs</span> {opponent}</h3>",
            unsafe_allow_html=True
        )
        kickoff = team_games.iloc[0]["Kickoff"]
        st.markdown(
            f"<b>Kickoff:</b> {kickoff}", unsafe_allow_html=True
        )

        for market in ["spreads", "totals", "h2h"]:
            market_df = team_games[team_games["Market"] == market]
            if not market_df.empty:
                st.subheader(market.replace("h2h", "Moneyline").capitalize())
                details = add_odds_details(market_df)
                st.markdown("**Consensus Odds (average, best, worst, implied probability, #books):**")
                st.dataframe(details, use_container_width=True)
                st.markdown("**Best Available Odds per Bookmaker:**")
                st.dataframe(best_odds_row(market_df), use_container_width=True)
                st.markdown(f"<b>All {market.replace('h2h','moneyline')} odds:</b>", unsafe_allow_html=True)
                disp_df = market_df[["Bookmaker", "Team", "Price", "Point", "Bookmaker URL"]].sort_values("Bookmaker")
                disp_df = disp_df.rename(columns={"Bookmaker URL":"Book URL"})
                st.dataframe(disp_df, use_container_width=True)
        st.write("Bookmaker Odds Comparison:")
        fig = px.bar(
            team_games,
            x="Bookmaker",
            y="Price",
            color="Market",
            barmode="group",
            hover_data=["Team", "Point"],
            title=f"Odds Comparison for {selected_team}",
            color_discrete_sequence=[NFL_ACCENT, NFL_SILVER, NFL_RED]
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Team Commentary")
    commentary_team = st.selectbox("Select Team for Commentary:", team_options, key="commentary_team")
    team_color = TEAM_COLORS.get(commentary_team, NFL_ACCENT)
    st.markdown(
        f"<h4 style='color:{team_color};'>Stats for {commentary_team} (Week {selected_week}):</h4>",
        unsafe_allow_html=True
    )
    if stats_data and "teams" in stats_data:
        stats_lookup = {team['name']: team for team in stats_data['teams']}
        team_stats = stats_lookup.get(commentary_team, {})
        st.write(team_stats)
    else:
        st.write("No stats available for this team.")

with tab3:
    st.header("Raw Data (for debugging or reference)")
    with st.expander("Show Odds Table"):
        st.dataframe(odds_df, use_container_width=True)
    with st.expander("Show Weekly Stats (Raw)"):
        st.write(stats_data)

st.caption("Odds by The Odds API. Weekly stats via RapidAPI.")
