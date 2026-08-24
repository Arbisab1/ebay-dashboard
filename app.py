import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import requests

# --- Set Page Configuration ---
st.set_page_config(
    page_title="eBay Automation Portal",
    page_icon="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg", # Path to eBay icon
    layout="centered",
    initial_sidebar_state="collapsed", # Hide sidebar by default
)

# --- Define custom CSS to match image_4.png exactly ---
custom_css = """
<style>
    /* 1. Global Page Styles */
    [data-testid="stAppViewContainer"] {
        background-color: #f4f6f8; /* Light gray page background */
    }
    
    [data-testid="stHeader"] {
        background: rgba(0,0,0,0); # Hide Streamlit header
    }

    /* 2. Style the main content area */
    .stMainBlockContainer {
        padding-top: 5rem;
    }

    /* 3. Style Input Fields (Username/Password) */
    .stTextInput input {
        background-color: transparent !important;
        border: 1px solid #c9d2db !important;
        border-radius: 8px !important;
        padding: 10px 15px !important;
        color: #1a1a1a !important;
    }
    .stTextInput input:focus {
        border-color: #8da3b8 !important;
        box-shadow: none !important;
    }
    .stTextInput label {
        color: #555 !important; # Label color
        font-weight: 500;
    }

    /* 4. Style the Red 'Sign In' Button */
    .stButton > button {
        background-color: #de3d4e !important; # The red color from image
        color: white !important;
        border: none !important;
        border-radius: 20px !important; # Rounded corners
        padding: 8px 30px !important;
        width: 100%; # Full width
        font-weight: bold;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: #bd3140 !important; # Darker red on hover
        color: white !important;
    }

    /* 5. Custom styles for the top panel */
    .top-panel {
        background-color: white;
        border: 1px solid #e0e6ed;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .top-panel img {
        display: block;
        margin: 0 auto;
        max-height: 40px;
    }
    .top-panel h1 {
        text-align: center;
        color: #1a1a1a;
        font-size: 28px;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 0;
    }
</style>
"""

# --- Inject custom CSS ---
st.markdown(custom_css, unsafe_allow_html=True)

# =========================================
# === MAIN PORTAL FRONTHEND STARTS HERE ===
# =========================================

# --- 1. Top Panel (Logo + Title) ---
st.markdown(
    """
    <div class="top-panel">
        <img src="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg" alt="eBay Logo">
        <h1>eBay Automation Portal</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- 2. Login Form Section ---
# Use a centered column for proper spacing
col1, login_col, col3 = st.columns([0.1, 2.8, 0.1])

with login_col:
    # Use stylable_container to allow CSS customization of form elements
    with stylable_container(
        key="login_form_container",
        css_styles="""
            [data-testid="stForm"] {
                background-color: white;
                border: 1px solid #e0e6ed;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }
        """
    ):
        with st.form(key='login_form'):
            # Text inputs matching the image labels
            st.text_input("Username", key="login_username")
            st.text_input("Password", key="login_password", type="password")

            st.write("") # Spacing

            # Red Sign In button matching image
            submit_button = st.form_submit_button(label='Sign In')
            
            # Form Submission Logic (add actual authentication here later)
            if submit_button:
                # Add authentication logic
                pass

# --- Footer: Optional add browser taskbar mimic ---
st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
