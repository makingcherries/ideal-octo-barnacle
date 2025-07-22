import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import google.generativeai as genai  # Gemini import

# --- Streamlit Theming (NFL Style) ---
st.set_page_config(page_title="Welcome to the QWERK", layout="wide", initial_sidebar_state="expanded")
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

st.title("Welcome to the QWERK")

# --- API KEYS ---
odds_api_key = st.secrets["the_odds_api"]["key"]
gemini_api_key = st.secrets.get("gemini_api_key") or st.text_input("Enter your Gemini API key for advanced analysis:", type="password")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel("gemini-pro")

# --- NFL Weeks ---
CURRENT_YEAR = datetime.now().year
NFL_WEEKS = list(range(1, 19))  # Weeks 1-18 regular season
WEEK_LABELS = [f"Week {w}" for w in NFL_WEEKS]

selected_week_idx = st.sidebar.selectbox("Select NFL Week", range(len(WEEK_LABELS)), format_func=lambda i: WEEK_LABELS[i])
selected_week = NFL_WEEKS[selected_week_idx]

# --- Odds Fetcher ---
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

odds_data, odds_error = get_odds(odds_api_key)

if odds_error:
    st.error(f"Odds API error: {odds_error}")
    st.stop()
if not odds_data:
    st.info("No odds data available at this time.")
    st.stop()

# --- NFL Team Colors (add all as you wish) ---
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

# --- Data Processing ---
def get_approx_week(game_date):
    # Approximate NFL week based on the start of September (UTC-aware)
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
team_options = [t for t in teams if t in TEAM_COLORS] + [t for t in teams if t not in TEAM_COLORS]

# --- Helper: Odds Table Details ---
def add_odds_details(df):
    # Consensus line: average price for each market/team
    consensus = df.groupby(["Market", "Team"]).agg(
        Consensus_Price=("Price", "mean"),
        Consensus_Point=("Point", "mean"),
        Best_Price=("Price", "max"),
        Worst_Price=("Price", "min"),
        Book_Count=("Bookmaker", "count")
    ).reset_index()
    # Implied probability (for American odds)
    def implied_prob(price):
        if price > 0:
            return round(100 / (price + 100) * 100, 1)
        else:
            return round(abs(price) / (abs(price) + 100) * 100, 1)
    consensus["Implied_Prob_%"] = consensus["Consensus_Price"].apply(implied_prob)
    return consensus

def best_odds_row(df):
    # Returns a row with the best price for each market/team
    idx = df.groupby(['Market', 'Team'])["Price"].idxmax()
    best = df.loc[idx][["Market","Team","Bookmaker","Price","Point","Bookmaker URL"]]
    return best.reset_index(drop=True)

# --- Streamlit Tabs ---
tab1, tab2, tab3 = st.tabs(["Current Odds", "Best QWERKY Bets", "Team Commentary"])

# --- Tab 1: Current Odds ---
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
                # Consensus & best odds tables
                details = add_odds_details(market_df)
                st.markdown("**Consensus Odds (average, best, worst, implied probability, #books):**")
                st.dataframe(details, use_container_width=True)
                st.markdown("**Best Available Odds per Bookmaker:**")
                st.dataframe(best_odds_row(market_df), use_container_width=True)
                # All odds
                st.markdown(f"<b>All {market.replace('h2h','moneyline')} odds:</b>", unsafe_allow_html=True)
                disp_df = market_df[["Bookmaker", "Team", "Price", "Point", "Bookmaker URL"]].sort_values("Bookmaker")
                disp_df = disp_df.rename(columns={"Bookmaker URL":"Book URL"})
                st.dataframe(disp_df, use_container_width=True)
        # Plot
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

# --- Tab 2: Best QWERKY Bets ---
with tab2:
    st.header("Best QWERKY Bets")
    st.write("Get best bets according to advanced statistical analysis (powered by Gemini).")
    if st.button("Analyze Best Bets", key="analyze_bets") and gemini_api_key:
        prompt = (
            f"You are an expert NFL betting analyst with access to 15 years of NFL data. "
            f"Analyze the current NFL week {selected_week} odds and provide the three best bets: "
            f"one against the spread, one over/under, and one moneyline. "
            f"Explain your reasoning in detail, referencing statistical trends, team matchups, and historical outcomes."
        )
        with st.spinner("Analyzing best bets..."):
            try:
                response = gemini_model.generate_content(prompt)
                analysis = response.text
                st.markdown(analysis)
            except Exception as e:
                st.error(f"Gemini Analysis error: {e}")
    elif not gemini_api_key:
        st.info("Enter your Gemini API key above to enable advanced analysis.")

# --- Tab 3: Team Commentary ---
with tab3:
    st.header("Team Commentary")
    commentary_team = st.selectbox("Select Team for Commentary:", team_options, key="commentary_team")
    team_color = TEAM_COLORS.get(commentary_team, NFL_ACCENT)
    st.markdown(
        f"<h4 style='color:{team_color};'>5 Reasons to Bet on {commentary_team} (Week {selected_week}):</h4>",
        unsafe_allow_html=True
    )
    if st.button("Generate Commentary", key="generate_commentary") and gemini_api_key:
        prompt = (
            f"List and explain 5 compelling reasons, based on 15 years of NFL data and current week {selected_week} odds, "
            f"why betting on {commentary_team} is a strong choice for this week. Reference advanced trends, "
            f"matchups, and relevant statistics."
        )
        with st.spinner("Generating commentary..."):
            try:
                response = gemini_model.generate_content(prompt)
                commentary = response.text
                st.markdown(commentary)
            except Exception as e:
                st.error(f"Gemini Commentary error: {e}")
    elif not gemini_api_key:
        st.info("Enter your Gemini API key above to enable commentary.")

st.caption("Odds data provided by The Odds API. Advanced analysis powered by the QWERK engine.")
