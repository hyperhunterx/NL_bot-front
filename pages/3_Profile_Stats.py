# front-engagement-bot/pages/3_Profile_Stats.py
import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import logging
import time

# --- Configuration ---
BOT_API_URL = st.secrets.get("BOT_API_URL", None)
API_KEY = st.secrets.get("BOT_API_KEY", None)
HEADERS = {'X-API-Key': API_KEY} if API_KEY else {}

# --- Helper Functions ---
@st.cache_data(ttl=60) # Cache data for 60 seconds
def fetch_stats_data_from_api():
    """Loads the profile stats data from the backend API."""
    if not BOT_API_URL: return None, "BOT_API_URL secret is not configured."
    # Assuming backend endpoint is /all_logs
    api_endpoint = f"{BOT_API_URL}/all_logs"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and 'profiles' in data and isinstance(data['profiles'], dict):
            logging.info(f"Successfully fetched stats data for {len(data['profiles'])} profiles.")
            return data['profiles'], None # Return the dictionary of profiles
        else:
             logging.error(f"API Error: Unexpected stats data format: {data}")
             return None, "API Error: Invalid stats format received."
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass
        logging.error(f"API Stats Fetch Error: {e}")
        return None, f"API Error fetching stats: {error_detail}"
    except json.JSONDecodeError:
        logging.error(f"API Stats Fetch Error: Invalid JSON response")
        return None, "Invalid stats JSON response from API."

# Keep your formatting function
def format_stat_value(key, value):
    """Formats values for better display."""
    if value is None: return "N/A"
    if isinstance(value, float) and ('rate' in key or 'ctr' in key): return f"{value:.1%}"
    if isinstance(value, str) and "date" in key:
        try: return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        except: return value # Keep original on parse error
    if key == "is_email_active": return "Yes" if str(value).upper() == "TRUE" else "No"
    if key == "notes" and isinstance(value, str) and len(value) > 150: return value[:150] + "..."
    return str(value)

# --- Streamlit Page Layout ---
st.set_page_config(layout="wide", page_title="Profile Stats (Remote)")
st.title("📊 Profile Statistics (Remote)")
st.caption("View summary statistics for each profile from the backend API.")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Check API Config ---
if not BOT_API_URL: st.error("🚨 Critical Error: BOT_API_URL secret is not set."); st.stop()
if not API_KEY: st.warning("⚠️ Warning: BOT_API_KEY secret not set.")

# --- Load Data ---
profile_stats_data, error = fetch_stats_data_from_api()

if error:
    st.error(f"Failed to load profile statistics: {error}")
    st.info("Ensure the backend API has an endpoint (e.g., `/all_logs`) that serves `logs/all_profiles_log.json`.")
    st.stop()
elif not profile_stats_data:
    st.info("No profile statistics data found in the backend.")
    # Don't stop, allow viewing empty state
else:
     st.success(f"Loaded statistics for {len(profile_stats_data)} profiles.")


# --- Sidebar Controls ---
# (Keep implementation as before, using the fetched profile_stats_data)
st.sidebar.header("Stats View Controls")
view_mode = st.sidebar.radio("View Mode:", ('Single Profile', 'All Profiles Table'), key='stats_view_mode', horizontal=True)
st.sidebar.markdown("---")

profile_ids = sorted(list(profile_stats_data.keys())) if profile_stats_data else []

if view_mode == 'Single Profile':
    st.sidebar.subheader("Select Profile")
    if not profile_ids: st.sidebar.warning("No profiles found.") ; selected_profile_id = None
    else:
        if 'stats_selected_profile_id' not in st.session_state or st.session_state.stats_selected_profile_id not in profile_ids:
            st.session_state.stats_selected_profile_id = profile_ids[0]
        selected_profile_id = st.sidebar.selectbox("Profile:", options=profile_ids, key='stats_selected_profile_id')
else:
    st.sidebar.subheader("All Profiles View")
    st.sidebar.info("Showing summary statistics for all profiles.")
    selected_profile_id = None

st.sidebar.divider()
st.sidebar.info("Navigate using sidebar (top left) for other pages.")


# --- Main Content Area ---
# (Keep implementation as before, using the fetched profile_stats_data)
if view_mode == 'Single Profile':
    if selected_profile_id and profile_stats_data and selected_profile_id in profile_stats_data:
        stats = profile_stats_data[selected_profile_id]
        st.header(f"Statistics for Profile: `{selected_profile_id}`")
        st.markdown(f"**Serial Number:** `{format_stat_value('serial_number', stats.get('serial_number'))}`")
        stats = profile_stats_data[selected_profile_id]
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Total Opens (NL)", stats.get('total_opens', 0))
        with col2: st.metric("Total Ad Clicks (NL)", stats.get('total_ad_clicks', 0))
        with col3: st.metric("Successful Sessions", stats.get('successful_sessions', 0))
        with col4: st.metric("Failed Sessions", stats.get('failed_sessions', 0), delta=stats.get('failed_sessions', 0), delta_color="inverse" if stats.get('failed_sessions', 0) > 0 else "off")
        st.markdown("---"); st.subheader("Detailed Stats")
        col_a, col_b = st.columns(2)
        all_keys = list(stats.keys()); midpoint = len(all_keys) // 2 + (len(all_keys) % 2)
        skip_keys = {'total_opens', 'total_ad_clicks', 'successful_sessions', 'failed_sessions', 'notes', 'user_id' , 'serial_number'}
        with col_a:
            for key in all_keys[:midpoint]:
                 if key not in skip_keys: st.markdown(f"**{key.replace('_', ' ').title()}:** `{format_stat_value(key, stats.get(key))}`")
        with col_b:
            for key in all_keys[midpoint:]:
                 if key not in skip_keys: st.markdown(f"**{key.replace('_', ' ').title()}:** `{format_stat_value(key, stats.get(key))}`")
        notes = stats.get('notes', '')
        if notes:
            with st.expander("Show Last Notes / Error"): st.code(notes, language=None)
    elif selected_profile_id: st.warning("Selected profile not found in current data.")
    else: st.info("Select a profile from the sidebar.")

elif view_mode == 'All Profiles Table':
    st.header("All Profile Statistics Summary")
    if not profile_stats_data: st.info("No profile statistics data available.")
    else:
        stats_list = list(profile_stats_data.values())
        df = pd.DataFrame(stats_list)
        desired_order = ['user_id', 'is_email_active', 'newsletter_name', 'successful_sessions', 'failed_sessions', 'total_opens', 'total_ad_clicks', 'total_non_ad_clicks', 'open_rate', 'ad_click_rate', 'regular_total_opens', 'regular_total_clicks', 'last_interaction_date', 'last_newsletter_interaction_date', 'last_newsletter_subject', 'last_action_type', 'session_type', 'target_engagements', 'daily_beehiiv_clicks', 'notes']
        cols_in_df = [col for col in desired_order if col in df.columns]
        remaining_cols = [col for col in df.columns if col not in cols_in_df]
        df_display = df[cols_in_df + remaining_cols].copy() # Use copy to avoid SettingWithCopyWarning
        # Apply formatting using .loc for safety
        if 'open_rate' in df_display.columns: df_display.loc[:, 'open_rate'] = pd.to_numeric(df_display['open_rate'], errors='coerce').map('{:.1%}'.format, na_action='ignore')
        if 'ad_click_rate' in df_display.columns: df_display.loc[:, 'ad_click_rate'] = pd.to_numeric(df_display['ad_click_rate'], errors='coerce').map('{:.1%}'.format, na_action='ignore')
        if 'is_email_active' in df_display.columns: df_display.loc[:, 'is_email_active'] = df_display['is_email_active'].apply(lambda x: "Yes" if str(x).upper() == "TRUE" else "No")
        # Format date columns if needed
        for col in ['last_interaction_date', 'last_newsletter_interaction_date']:
             if col in df_display.columns:
                  df_display.loc[:, col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').fillna("N/A")

        st.dataframe(df_display, use_container_width=True)
else: st.error("Invalid view mode.")