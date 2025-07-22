import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone

import google.generativeai as genai

# --- Streamlit Theming (NFL Style) ---
st.set_page_config(page_title="NFL Top 5 Bets Analyzer", layout="wide", initial_sidebar_state="expanded")
NFL_DARK = "#101820"
NFL_ACCENT = "#013369"
NFL_RED = "#D50A0A"
NFL_SILVER = "#A5ACAF"
NFL_WHITE = "#FFFFFF"

st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {NFL_DARK};
            color: {NFL_WHITE};
        }}
        .css-1v0mbdj, .css-10trblm, .css-1d391kg, .st-bb, .st-at, .st-cq, .st-ce {{
            color: {NFL_WHITE} !important;
        }}
        .stButton > button {{
            background-color: {NFL_ACCENT};
            color: {NFL_WHITE};
            border-radius: 8px;
            border: 2px solid {NFL_SILVER};
            font-weight: bold;
        }}
        .stSelectbox > div {{background: "#232b2b"}}
        .stDataFrame, .stPlotlyChart {{
            background-color: {NFL_DARK} !important;
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
            background-color: {NFL_DARK} !important;
        }}
    </style>
    """, unsafe_allow_html=True,
)

st.title("NFL Top 5 Bets Analyzer (Gemini-Powered)")

# --- API KEYS ---
odds_api_key = st.secrets["the_odds_api"]["key"]
rapid_api_key = st.secrets.get("rapid_api_key") or st.text_input("Enter your RapidAPI key for NFL stats:", type="password")
gemini_api_key = st.secrets.get("gemini_api_key") or st.text_input("Enter your Gemini API key for analysis:", type="password")
gemini_model = None

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    try:
        gemini_model = genai.GenerativeModel("models/gemini-1.5-flash")
    except Exception as e:
        st.error(f"Error loading Gemini model: {e}")
        gemini_model = None

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

# --- Data Processing ---
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

# --- Stats Helper: Condense stats for prompt (edit as needed for your API format) ---
def condense_stats(stats_data):
    # This is a sample function, adjust based on your real rapidapi response!
    # For example, you may want: team, offense_rank, defense_rank, injuries, etc.
    if not stats_data or "teams" not in stats_data:
        return "No stats available."
    lines = []
    for team in stats_data["teams"]:
        # Make sure to adapt keys to your actual API!
        lines.append(
            f"{team['name']}: Off Rank {team.get('offense_rank','?')}, Def Rank {team.get('defense_rank','?')}, Injuries {team.get('injuries','?')}, Last 5 {team.get('last5','?')}"
        )
    return "\n".join(lines)

# --- Per-Game Condensed Data for LLM ---
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
        # odds info for home/away/markets for this game
        game_odds = rows[["Market", "Team", "Price", "Point", "Bookmaker"]].to_dict(orient="records")
        # stats info for both teams
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

# --- Main Analysis Section ---
st.header(f"Gemini Analysis: Top 5 NFL Bets for Week {selected_week}")

if st.button("Analyze NFL Games & Recommend Top 5 Bets") and gemini_api_key and gemini_model:
    # Compose detailed context for each game
    full_game_context = ""
    for g in games_for_prompt:
        full_game_context += (
            f"Game: {g['game']} (Kickoff: {g['kickoff']})\n"
            f"Home stats: {g['home_stats']}\n"
            f"Away stats: {g['away_stats']}\n"
            f"Odds:\n"
        )
        for o in g["odds"]:
            full_game_context += f"  Market: {o['Market']}, Team: {o['Team']}, Price: {o['Price']}, Point: {o['Point']}, Bookmaker: {o['Bookmaker']}\n"
        full_game_context += "\n"

    prompt = f"""
You are an advanced NFL betting analyst with access to the latest odds and 15 years of NFL statistics. 
Below is this week's data for all NFL games, including odds and key team statistics.

---
{full_game_context}
---

Instructions:
1. For each game, provide a concise advanced analysis (strengths, weaknesses, trends, value in lines, etc.), referencing the given stats and odds.
2. After analyzing all games, select the 5 best games to bet on this week (can be spread, moneyline, or over/under).
3. For each of the top 5 bets, state clearly which bet to make (e.g. "Bears +3.5", "Over 48.0 in Eagles vs Cowboys") and provide a detailed rationale for why this is one of the best bets, using both the odds and stats provided.
4. Make sure the analysis is self-contained and actionable.

Output format:
- Per-game analysis
- Top 5 Bets section: List each bet, the game, and a rationale paragraph for each.

Begin your analysis below.
"""
    with st.spinner("Gemini is analyzing all NFL games and picking the top 5 bets..."):
        try:
            response = gemini_model.generate_content(prompt)
            analysis = response.text
            st.markdown(analysis)
        except Exception as e:
            st.error(f"Gemini Analysis error: {e}")
elif not gemini_api_key:
    st.info("Enter your Gemini API key above to enable advanced analysis.")

st.header("Raw Data (for debugging or reference)")
with st.expander("Show Odds Table"):
    st.dataframe(odds_df, use_container_width=True)
with st.expander("Show Weekly Stats (Raw)"):
    st.write(stats_data)

st.caption("Odds by The Odds API. Weekly stats via RapidAPI. Analysis powered by Gemini 1.5 Flash.")
