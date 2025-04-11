# front-engagement-bot/pages/2_Settings_Editor.py 123
import streamlit as st
import requests
import json
import time
import logging
from collections import OrderedDict # Keep if render_setting relies on it

# Try importing PyYAML for safe loading/dumping on the frontend if needed
try:
    import yaml as pyyaml
    PYYAML_AVAILABLE = True
except ImportError:
    PYYAML_AVAILABLE = False
    logging.warning("PyYAML not installed. Cannot edit YAML fields like 'session_types'.")

# --- Configuration ---
BOT_API_URL = st.secrets.get("BOT_API_URL", None)
API_KEY = st.secrets.get("BOT_API_KEY", None)
HEADERS = {'X-API-Key': API_KEY} if API_KEY else {}

# --- Helper Functions ---

@st.cache_data(ttl=30) # Cache settings for 30 seconds
def fetch_settings_data_from_api():
    """Fetches the settings data from the backend API."""
    if not BOT_API_URL: return None, "BOT_API_URL secret is not configured."
    api_endpoint = f"{BOT_API_URL}/settings"
    try:
        response = requests.get(api_endpoint, headers=HEADERS, timeout=15)
        response.raise_for_status()
        settings_data = response.json()
        # Ensure it's a dictionary
        if isinstance(settings_data, dict):
            logging.info("Settings fetched successfully.")
            return settings_data, None
        else:
            logging.error(f"API Error: Settings format received is not a dictionary: {type(settings_data)}")
            return None, "API Error: Invalid settings format received."
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass
        logging.error(f"API Settings Fetch Error: {e}")
        return None, f"API Error fetching settings: {error_detail}"
    except json.JSONDecodeError:
        logging.error("API Settings Fetch Error: Invalid JSON response")
        return None, "Invalid settings JSON response from API."

def save_settings_via_api(settings_data):
    """Sends the updated settings dictionary to the backend API."""
    if not BOT_API_URL: return False, "BOT_API_URL not set."
    api_endpoint = f"{BOT_API_URL}/settings"
    try:
        # Make sure data being sent is basic Python types (dict, list, str, int, etc.)
        response = requests.post(api_endpoint, headers=HEADERS, json=settings_data, timeout=20)
        response.raise_for_status()
        return True, response.json().get("message", "Settings saved successfully.")
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass
        logging.error(f"API Settings Save Error: {e}")
        return False, f"API Error saving settings: {error_detail}"
    except json.JSONDecodeError:
        logging.error("API Settings Save Error: Invalid JSON response")
        return False, "Invalid JSON response from API after saving."


# --- Widget Rendering (render_setting) ---
# Keep the function from your previous version (assuming it worked)
# This function takes a python dict/list/value and renders the appropriate widget
def render_setting(key_path, value, level=0):
    """Renders appropriate widget based on value type."""
    key = key_path[-1]
    label = key.replace('_', ' ').title()
    unique_key = '_'.join(map(str, key_path))
    indent_html = " " * (level * 4)

    # Use columns for layout if not a dictionary itself
    if not isinstance(value, dict):
        col1, col2 = st.columns([0.4, 0.6]) # Adjust ratio as needed
        with col1:
            st.markdown(f"{indent_html}{label}:", unsafe_allow_html=True)
    else: # For dictionaries, just render the header
        st.markdown(f"{indent_html}**{label}:**", unsafe_allow_html=True)
        col2 = st.container() # Use a container for widgets inside dict

    with col2: # Widget rendering happens here or below for dicts
        if isinstance(value, bool):
            st.checkbox("", value=value, key=unique_key, label_visibility="collapsed")
        elif isinstance(value, int):
            min_val, max_val, step = None, None, 1
            if key == 'threads': min_val, max_val = 1, 4
            if 'interval' in key or 'wait' in key or 'age' in key: min_val = 0
            if key == 'backup_interval': min_val = 5
            st.number_input("", value=value, min_value=min_val, max_value=max_val, step=step, key=unique_key, label_visibility="collapsed")
        elif isinstance(value, float):
             min_val, max_val, step = None, None, 0.01
             if 'rate' in key or 'ctr' in key or 'probability' in key: min_val, max_val, step = 0.0, 1.0, 0.01
             elif key == 'random_variance': min_val, max_val, step = 0.0, 1.0, 0.05
             st.number_input("", value=value, min_value=min_val, max_value=max_val, step=step, format="%.2f", key=unique_key, label_visibility="collapsed")
        elif isinstance(value, str):
            if key == 'mode':
                options = ["prod", "dev"]; index = options.index(value) if value in options else 0
                st.selectbox("", options=options, index=index, key=unique_key, label_visibility="collapsed")
            elif key == 'log_level':
                 options = ["debug", "info", "warning", "error", "critical"]; index = options.index(value.lower()) if value.lower() in options else 1
                 st.selectbox("", options=options, index=index, key=unique_key, label_visibility="collapsed")
            elif key == 'group_id':
                 st.text_input("_(blank for all)_", value=str(value) if value is not None else "", key=unique_key, label_visibility="visible") # Label needed here
            elif 'path' in key or 'file' in key: st.text_input("", value=value, key=unique_key, label_visibility="collapsed", help="File path on server")
            else: st.text_input("", value=value, key=unique_key, label_visibility="collapsed")
        elif isinstance(value, list):
            list_keys_textarea = ['sender_email', 'ad_identifiers', 'regular_engagement_skip_senders', 'serial_numbers']
            if key in list_keys_textarea:
                initial_text = "\n".join(map(str, value))
                height = 60 + len(value) * 15
                st.text_area(f"_(One per line)_", value=initial_text, height=min(height, 200), key=unique_key, label_visibility="visible")
            elif key == 'session_types' and PYYAML_AVAILABLE and all(isinstance(item, dict) for item in value):
                 try:
                     yaml_text = pyyaml.dump(value, indent=2, default_flow_style=False)
                     st.text_area(f"_(Edit as YAML)_", value=yaml_text, height=200, key=unique_key, label_visibility="visible", help="Edit list in YAML format.")
                 except Exception as dump_err: st.error(f"Error preparing YAML for {key}: {dump_err}"); st.text_input("_(List - Error)_", value=str(value), disabled=True, key=unique_key, label_visibility="visible")
            elif key == 'session_types' and not PYYAML_AVAILABLE: st.warning("PyYAML needed to edit session_types."); st.text_input("_(List - Read Only)_", value=str(value), disabled=True, key=unique_key, label_visibility="visible")
            else: st.text_input(f"_(List - Read Only)_", value=str(value), disabled=True, key=unique_key, label_visibility="visible", help="Cannot edit this list type here.")
        elif isinstance(value, dict):
            st.markdown("---") # Separator before nested items
            for sub_key, sub_value in value.items(): render_setting(key_path + [sub_key], sub_value, level + 1)
        elif value is None and key == 'group_id': st.text_input("_(blank for all)_", value="", key=unique_key, label_visibility="visible")
        elif value is None: st.text_input("", value="None", disabled=True, key=unique_key, label_visibility="collapsed")
        else: st.text_input(f"_(Unknown Type: {type(value).__name__})_", value=str(value), disabled=True, key=unique_key, label_visibility="visible")

# --- Update Logic ---
# Keep the function from the previous plan to reconstruct the dict from st.session_state
def build_updated_settings(original_data_structure, key_path):
    """Recursively builds the updated settings dict from st.session_state."""
    if isinstance(original_data_structure, dict):
        updated_dict = {}
        for key, original_value in original_data_structure.items():
            current_key_path = key_path + [key]
            if isinstance(original_value, dict):
                updated_dict[key] = build_updated_settings(original_value, current_key_path)
            else:
                 widget_key = '_'.join(map(str, current_key_path))
                 if widget_key in st.session_state:
                     widget_value = st.session_state[widget_key]
                     try: # Add more robust type conversion/parsing
                         if isinstance(original_value, bool): updated_dict[key] = bool(widget_value)
                         elif isinstance(original_value, int): updated_dict[key] = int(widget_value)
                         elif isinstance(original_value, float): updated_dict[key] = float(widget_value)
                         elif isinstance(original_value, list) and key in ['sender_email', 'ad_identifiers', 'regular_engagement_skip_senders']: updated_dict[key] = [line.strip() for line in widget_value.splitlines() if line.strip()]
                         elif isinstance(original_value, list) and key == 'serial_numbers': updated_dict[key] = [int(line.strip()) for line in widget_value.splitlines() if line.strip().isdigit()]
                         elif isinstance(original_value, list) and key == 'session_types' and PYYAML_AVAILABLE:
                              parsed = pyyaml.safe_load(widget_value); updated_dict[key] = parsed if isinstance(parsed, list) else original_value
                         elif key == 'group_id': updated_dict[key] = widget_value if widget_value else None
                         elif isinstance(original_value, str): updated_dict[key] = str(widget_value)
                         else: updated_dict[key] = widget_value # Fallback: assign widget value directly
                     except Exception as e:
                          st.warning(f"Error processing widget '{widget_key}' value '{widget_value}'. Keeping original. Error: {e}")
                          logging.warning(f"Error processing widget {widget_key}: {e}")
                          updated_dict[key] = original_value # Keep original on error
                 else: updated_dict[key] = original_value # Keep original if no widget found
        return updated_dict
    else: return original_data_structure # Return non-dicts as is


# --- Streamlit Page ---
st.set_page_config(layout="wide", page_title="Settings Editor (Remote)")
st.title("⚙️ Bot Settings Editor (Remote)")
st.caption(f"Edit settings on the local machine via API: `{BOT_API_URL}`")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Check API Config ---
if not BOT_API_URL: st.error("🚨 Critical Error: BOT_API_URL secret is not set."); st.stop()
if not API_KEY: st.warning("⚠️ Warning: BOT_API_KEY secret not set.")

# --- Load Initial Settings ---
if 'current_settings_data' not in st.session_state: st.session_state.current_settings_data = None
if 'settings_fetch_error' not in st.session_state: st.session_state.settings_fetch_error = None

# Fetch only if not already loaded or if forced by reload button
if st.session_state.current_settings_data is None:
     with st.spinner("Loading settings from backend API..."):
         settings_data, error = fetch_settings_data_from_api()
         if error:
             st.session_state.settings_fetch_error = error
             st.session_state.current_settings_data = None # Ensure it's None on error
         else:
             st.session_state.current_settings_data = settings_data
             st.session_state.settings_fetch_error = None # Clear error on success
         st.rerun() # Rerun to display loaded data or error

# Display error if fetch failed on previous run
if st.session_state.settings_fetch_error:
     st.error(f"Failed to load settings: {st.session_state.settings_fetch_error}")
     if st.button("🔄 Retry Loading Settings"):
          st.session_state.current_settings_data = None # Force reload attempt
          st.rerun()
     st.stop()

# If data is loaded successfully
settings_data = st.session_state.current_settings_data
if settings_data:
    with st.form(key="settings_form"):
        # Render settings using the recursive function within expanders for organization
        if 'global' in settings_data:
             with st.expander("Global Settings", expanded=True): render_setting(['global'], settings_data['global'])
        if 'google_sheets' in settings_data:
             with st.expander("Google Sheets", expanded=True): render_setting(['google_sheets'], settings_data['google_sheets'])
        if 'newsletters' in settings_data:
             with st.expander("Newsletters", expanded=True):
                  nl_conf = settings_data['newsletters']
                  if isinstance(nl_conf, dict):
                      for nl_key, nl_value in nl_conf.items():
                           st.markdown(f"**{nl_key.replace('_', ' ').title()} Config:**")
                           render_setting(['newsletters', nl_key], nl_value, level=1) # level 1 inside expander
                           st.markdown("---")
        if 'engagement' in settings_data:
             with st.expander("Engagement Logic", expanded=True): render_setting(['engagement'], settings_data['engagement'])
        if 'query_settings' in settings_data:
             with st.expander("Query Settings", expanded=True): render_setting(['query_settings'], settings_data['query_settings'])

        st.divider()
        submitted = st.form_submit_button("💾 Save Settings to Bot", use_container_width=True, type="primary")

        if submitted:
            logging.info("Save clicked. Building updated settings dict...")
            updated_settings = build_updated_settings(settings_data, [])
            # st.write("Updated Settings Payload:") # Debug: View payload
            # st.json(updated_settings) # Debug: View payload
            with st.spinner("Sending updated settings to the bot API..."):
                 save_success, message = save_settings_via_api(updated_settings)
            if save_success:
                st.success(f"✅ {message}")
                st.cache_data.clear() # Clear fetch cache
                st.session_state.current_settings_data = None # Force reload
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ Failed to save settings: {message}")
else:
     # This case should ideally be handled by the error display above
     st.error("Could not load settings data to display the editor.")

# Add a manual reload button outside the form
st.divider()
if st.button("🔄 Reload Settings from Bot"):
     st.cache_data.clear()
     st.session_state.current_settings_data = None # Force reload on next run
     st.rerun()