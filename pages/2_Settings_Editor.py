# front-engagement-bot/pages/2_Settings_Editor.py
import streamlit as st
import requests
import json
import time
import logging
# OrderedDict is not strictly needed if Python 3.7+ and API handles standard dict order for JSON
# from collections import OrderedDict 

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
        if isinstance(settings_data, dict):
            logging.info("Settings fetched successfully.")
            return settings_data, None
        else:
            logging.error(f"API Error: Settings format received is not a dictionary: {type(settings_data)}")
            return None, "API Error: Invalid settings format received."
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass # Ignore if response has no JSON error
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
        response = requests.post(api_endpoint, headers=HEADERS, json=settings_data, timeout=20)
        response.raise_for_status()
        return True, response.json().get("message", "Settings saved successfully.")
    except requests.exceptions.RequestException as e:
        error_detail = f"{type(e).__name__}"
        try: error_detail += f": {e.response.json().get('error', e.response.text)}"
        except: pass # Ignore if response has no JSON error
        logging.error(f"API Settings Save Error: {e}")
        return False, f"API Error saving settings: {error_detail}"
    except json.JSONDecodeError:
        logging.error("API Settings Save Error: Invalid JSON response")
        return False, "Invalid JSON response from API after saving."

def _label_from_key(key_str):
    """Helper to create a human-readable label from a settings key."""
    return key_str.replace('_', ' ').title()

# --- Widget Rendering (render_setting) ---
def render_setting(key_path, value, level=0):
    """Renders appropriate widget based on value type."""
    key = key_path[-1]
    label = _label_from_key(key)
    unique_key = '_'.join(map(str, key_path))
    indent_html = " " * (level * 4) # Using non-breaking space for indent

    if not isinstance(value, dict):
        col1, col2 = st.columns([0.4, 0.6])
        with col1:
            st.markdown(f"{indent_html}{label}:", unsafe_allow_html=True)
    else:
        st.markdown(f"{indent_html}**{label}:**", unsafe_allow_html=True)
        col2 = st.container()

    with col2:
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
            elif key == 'group_id': # Special handling for group_id string or None
                 st.text_input("_(blank for all!!)_", value=str(value) if value is not None else "", key=unique_key, label_visibility="visible")
            elif 'path' in key or 'file' in key: st.text_input("", value=value, key=unique_key, label_visibility="collapsed", help="File path on server")
            else: st.text_input("", value=value, key=unique_key, label_visibility="collapsed")
        elif isinstance(value, list):
            list_keys_textarea = ['sender_email', 'ad_identifiers', 'regular_engagement_skip_senders', 'serial_numbers']
            if key in list_keys_textarea:
                initial_text = "\n".join(map(str, value))
                
                # Calculate desired height, ensuring a base height even for empty list
                calculated_height = 60 + len(value) * 15 
                display_height = min(calculated_height, 200)

                # *** FIX: If the list is empty, set height to None (use Streamlit default) ***
                effective_height_for_widget = None if not value else display_height
                
                st.text_area(
                    f"_(One per line!!)_", 
                    value=initial_text,
                    height=effective_height_for_widget, 
                    key=unique_key,
                    label_visibility="visible"
                )
            elif key == 'session_types' and PYYAML_AVAILABLE and all(isinstance(item, dict) for item in value):
                 try:
                     yaml_text = pyyaml.dump(value, indent=2, default_flow_style=False)
                     st.text_area(f"_(Edit as YAML)_", value=yaml_text, height=200, key=unique_key, label_visibility="visible", help="Edit list in YAML format.")
                 except Exception as dump_err: st.error(f"Error preparing YAML for {key}: {dump_err}"); st.text_input("_(List - Error)_", value=str(value), disabled=True, key=unique_key, label_visibility="visible")
            elif key == 'session_types' and not PYYAML_AVAILABLE: st.warning("PyYAML needed to edit session_types."); st.text_input("_(List - Read Only)_", value=str(value), disabled=True, key=unique_key, label_visibility="visible")
            else: st.text_input(f"_(List - Read Only)_", value=str(value), disabled=True, key=unique_key, label_visibility="visible", help="Cannot edit this list type here.")
        elif isinstance(value, dict):
            st.markdown("---")
            for sub_key, sub_value in value.items(): render_setting(key_path + [sub_key], sub_value, level + 1)
        elif value is None and key == 'group_id': # Handles case where group_id is initially None
            st.text_input("_(blank for all!!)_", value="", key=unique_key, label_visibility="visible")
        elif value is None: # For other None values, usually display as disabled
            st.text_input("", value="None", disabled=True, key=unique_key, label_visibility="collapsed")
        else:
            st.text_input(f"_(Unknown Type: {type(value).__name__})_", value=str(value), disabled=True, key=unique_key, label_visibility="visible")

# --- Update Logic ---
def build_updated_settings(original_data_structure, key_path):
    """Recursively builds the updated settings dict from st.session_state, ensuring type correctness."""
    if isinstance(original_data_structure, dict):
        updated_dict = {} # Standard dict is fine for Python 3.7+
        for key, original_value in original_data_structure.items():
            current_key_path = key_path + [key]
            widget_key = '_'.join(map(str, current_key_path))

            if isinstance(original_value, dict):
                updated_dict[key] = build_updated_settings(original_value, current_key_path)
            elif widget_key in st.session_state:
                widget_value = st.session_state[widget_key]
                try:
                    if isinstance(original_value, bool):
                        updated_dict[key] = bool(widget_value)
                    elif isinstance(original_value, int):
                        updated_dict[key] = int(widget_value) # st.number_input returns correct type
                    elif isinstance(original_value, float):
                        updated_dict[key] = float(widget_value) # st.number_input returns correct type
                    elif key == 'group_id': # Specific handling for group_id (str or None)
                        updated_dict[key] = str(widget_value).strip() if str(widget_value).strip() else None
                    elif isinstance(original_value, str): # General strings
                        updated_dict[key] = str(widget_value)
                    elif isinstance(original_value, list):
                        # Handle list conversions based on key
                        if key in ['sender_email', 'ad_identifiers', 'regular_engagement_skip_senders']:
                            updated_dict[key] = [line.strip() for line in str(widget_value).splitlines() if line.strip()]
                        elif key == 'serial_numbers':
                            # *** FIX: Ensure serial_numbers are parsed as list of ints ***
                            processed_list = []
                            # widget_value from st.text_area is a string
                            for line in str(widget_value).splitlines():
                                stripped_line = line.strip()
                                if stripped_line.isdigit():
                                    processed_list.append(int(stripped_line))
                                elif stripped_line: # Log non-empty, non-digit lines
                                    logging.warning(f"Invalid serial number entry '{stripped_line}' for key '{widget_key}' will be skipped.")
                            updated_dict[key] = processed_list
                        elif key == 'session_types' and PYYAML_AVAILABLE:
                            parsed_yaml = pyyaml.safe_load(str(widget_value))
                            updated_dict[key] = parsed_yaml if isinstance(parsed_yaml, list) else original_value
                        else: # Fallback for other lists (e.g., session_types if PyYAML not available)
                            logging.warning(f"List '{key}' at '{widget_key}' has no specific parsing or PyYAML is unavailable. Reverting to original value.")
                            updated_dict[key] = original_value
                    elif original_value is None: # If original was None (and not group_id already handled)
                        updated_dict[key] = None # Keep it None (e.g. for disabled fields that were None)
                    else: # Fallback for any unhandled type from widget
                        logging.warning(f"Unhandled original type for key '{key}' (type: {type(original_value).__name__}). Assigning widget value '{widget_value}' directly.")
                        updated_dict[key] = widget_value
                except ValueError as ve:
                    st.error(f"Invalid input for '{_label_from_key(key)}': '{widget_value}'. Please enter a valid number. Original value restored. ({ve})")
                    logging.warning(f"ValueError processing widget {widget_key} (value: {widget_value}): {ve}")
                    updated_dict[key] = original_value
                except Exception as e:
                    st.error(f"Error processing field '{_label_from_key(key)}'. Original value restored. Error: {e}")
                    logging.warning(f"Exception processing widget {widget_key} (value: {widget_value}): {e}")
                    updated_dict[key] = original_value
            else: # Widget not in session_state (e.g. a new key added to settings file but not rendered yet)
                updated_dict[key] = original_value
        return updated_dict
    return original_data_structure # Should not be reached if top-level is always a dict

# --- Streamlit Page ---
st.set_page_config(layout="wide", page_title="Settings Editor (Remote)")
st.title("⚙️ Bot Settings Editor (Remote)")
st.caption(f"Edit settings on the bot machine via API: `{BOT_API_URL}`")

# Configure basic logging for the Streamlit app itself (optional)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [SETTINGS_PAGE] - %(message)s')

# --- Check API Config ---
if not BOT_API_URL: st.error("🚨 Critical Error: BOT_API_URL secret is not set in Streamlit Cloud."); st.stop()
if not API_KEY: st.warning("⚠️ Warning: BOT_API_KEY secret not set. API requests might fail if authentication is required.")

# --- Load Initial Settings ---
if 'current_settings_data' not in st.session_state: st.session_state.current_settings_data = None
if 'settings_fetch_error' not in st.session_state: st.session_state.settings_fetch_error = None

if st.session_state.current_settings_data is None and st.session_state.settings_fetch_error is None:
     with st.spinner("Loading settings from backend API..."):
         settings_data, error = fetch_settings_data_from_api()
         if error:
             st.session_state.settings_fetch_error = error
             st.session_state.current_settings_data = None
         else:
             st.session_state.current_settings_data = settings_data
             st.session_state.settings_fetch_error = None
         st.rerun()

if st.session_state.settings_fetch_error:
     st.error(f"Failed to load settings: {st.session_state.settings_fetch_error}")
     if st.button("🔄 Retry Loading Settings"):
          st.session_state.current_settings_data = None
          st.session_state.settings_fetch_error = None # Clear error to allow retry
          st.rerun()
     st.stop()

settings_data_to_display = st.session_state.current_settings_data

if settings_data_to_display:
    with st.form(key="settings_form"):
        # Render settings using the recursive function within expanders for organization
        # Common top-level keys, adjust as per your actual settings structure
        common_keys = ['global', 'google_sheets', 'newsletters', 'engagement', 'query_settings']
        
        for top_key in common_keys:
            if top_key in settings_data_to_display:
                with st.expander(_label_from_key(top_key), expanded=True):
                    if top_key == 'newsletters' and isinstance(settings_data_to_display[top_key], dict):
                        # Special handling for newsletters if it's a dict of configs
                        for nl_key, nl_value in settings_data_to_display[top_key].items():
                           st.markdown(f"**{_label_from_key(nl_key)} Config:**")
                           render_setting([top_key, nl_key], nl_value, level=1)
                           if nl_key != list(settings_data_to_display[top_key].keys())[-1]: st.markdown("---") # Separator between newsletter configs
                    else:
                        render_setting([top_key], settings_data_to_display[top_key])
            
        # Render any other top-level keys not in common_keys
        other_keys = [k for k in settings_data_to_display if k not in common_keys]
        if other_keys:
            with st.expander("Other Settings", expanded=False):
                for top_key in other_keys:
                    render_setting([top_key], settings_data_to_display[top_key])

        st.divider()
        submitted = st.form_submit_button("💾 Save Settings to Bot", use_container_width=True, type="primary")

        if submitted:
            logging.info("Save button clicked. Building updated settings dictionary...")
            updated_settings = build_updated_settings(settings_data_to_display, [])
            
            # For debugging the payload:
            # st.write("Updated Settings Payload (for debugging):")
            # st.json(updated_settings) 

            with st.spinner("Sending updated settings to the bot API..."):
                 save_success, message = save_settings_via_api(updated_settings)
            if save_success:
                st.success(f"✅ {message}")
                st.cache_data.clear() # Clear fetch cache to get fresh data
                st.session_state.current_settings_data = None # Force reload
                st.session_state.settings_fetch_error = None
                time.sleep(1) # Brief pause for user to see success message
                st.rerun()
            else:
                st.error(f"❌ Failed to save settings: {message}")
else:
     if not st.session_state.settings_fetch_error: # Only show if not already showing a fetch error
        st.info("Waiting for settings data to load...")

st.divider()
if st.button("🔄 Reload Settings from Bot"):
     st.cache_data.clear()
     st.session_state.current_settings_data = None
     st.session_state.settings_fetch_error = None
     st.rerun()