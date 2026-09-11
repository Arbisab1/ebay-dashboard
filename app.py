import base64
from datetime import datetime, timedelta, timezone
import email.message
import hashlib
import io
import json
import os
import random
import re
import smtplib
import time
from urllib.parse import parse_qs, unquote, urlparse
import pandas as pd
import requests
import streamlit as st

# --- CONFIGURATION ---
WHATSAPP_NUMBER = "923011234527"
WHATSAPP_DEFAULT_MSG = "Hello Nawaz, I need help with the eBay Automation Dashboard."
WHATSAPP_LINK = f"https://wa.me/{WHATSAPP_NUMBER}?text={requests.utils.quote(WHATSAPP_DEFAULT_MSG)}"

CLIENT_ID = st.secrets.get(
    "EBAY_CLIENT_ID",
    os.getenv("EBAY_CLIENT_ID", "NawazIqb-eBayAuto-PRD-d254d2f41-10c98af7"),
)
CLIENT_SECRET = st.secrets.get(
    "EBAY_CLIENT_SECRET",
    os.getenv("EBAY_CLIENT_SECRET", "PRD-254d2f418365-a9a4-43a0-bc81-4af2"),
)
RUNAME = st.secrets.get(
    "EBAY_RUNAME",
    os.getenv("EBAY_RUNAME", "Nawaz_Iqbal-NawazIqb-eBayAu-pifoqzze"),
)

HARDCODED_GMAIL = "Nawazarbi69@gmail.com"
HARDCODED_APP_PASSWORD = "lxkotbrfjmaozlnc"

SMTP_EMAIL = st.secrets.get("SMTP_EMAIL", os.getenv("SMTP_EMAIL", HARDCODED_GMAIL)).strip()
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", os.getenv("SMTP_PASSWORD", HARDCODED_APP_PASSWORD)).strip()

STORES_FILE = "connected_stores.json"
USERS_FILE = "users_db.json"
TEMPLATES_FILE = "custom_templates.json"
LOGS_FILE = "message_logs.json"

AUTH_URL = (
    f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={RUNAME}&"
    "scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.fulfillment%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.finances%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.message%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fbuy.browse%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.compliance"
)

st.set_page_config(
    page_title="eBay Automation Cloud Portal",
    layout="wide",
    page_icon="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg",
    initial_sidebar_state="expanded",
)

# --- PROFESSIONAL SAAS ENTERPRISE UI STYLING ---
st.markdown(
    """

""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
[
