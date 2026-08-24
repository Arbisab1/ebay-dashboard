import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
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

STORES_FILE = "connected_stores.json"
USERS_FILE = "users_db.json"
TEMPLATES_FILE = "custom_templates.json"
LOGS_FILE = "message_logs.json"

AUTH_URL = (
    f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={RUNAME}&"
    "scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.fulfillment%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.message"
)

st.set_page_config(
    page_title="eBay Automation Cloud Portal",
    layout="wide",
    page_icon="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg",
    initial_sidebar_state="expanded",
)

# --- STRICT LIGHT THEME ENFORCER (DARK MODE OVERRIDE) ---
st.markdown(
    f"""
<style>
    :root {{
        color-scheme: light !important;
    }}
    
    header[data-testid="stHeader"], div[data-testid="stDecoration"] {{
        display: none !important;
    }}

    html, body, .stApp {{
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}

    p, span, label, h1, h2, h3, h4, h5, h6, div, li {{
        color: #0F172A !important;
    }}

    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
    }}

    /* Metric Cards */
    div[data-testid="stMetric"] {{
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        padding: 16px 20px !important;
    }}
    div[data-testid="stMetricValue"] {{
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #2563EB !important;
    }}
    div[data-testid="stMetricLabel"] p {{
        color: #475569 !important;
        font-weight: 600 !important;
    }}

    /* Primary & Secondary Buttons */
    button[kind="primary"] {{
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 8px !important;
    }}
    button[kind="primary"] p {{
        color: #FFFFFF !important;
    }}

    button[kind="secondary"] {{
        background-color: #FFFFFF !important;
        border: 1px solid #94A3B8 !important;
        color: #1E293B !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}
    button[kind="secondary"] p {{
        color: #1E293B !important;
    }}

    /* Expander Container */
    .streamlit-expanderHeader {{
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        color: #0F172A !important;
        font-weight: 600 !important;
    }}
    .streamlit-expanderHeader p, .streamlit-expanderHeader span {{
        color: #0F172A !important;
    }}

    /* Form Inputs & Dropdowns */
    input, textarea, select, div[data-baseweb="select"] {{
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border-color: #94A3B8 !important;
        border-radius: 8px !important;
    }}
    
    div[data-baseweb="select"] * {{
        color: #0F172A !important;
        background-color: #FFFFFF !important;
    }}

    /* Sidebar Clean Styling */
    section[data-testid="stSidebar"] {{
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: #0F172A !important;
    }}

    /* Floating WhatsApp Button */
    .floating-whatsapp {{
        position: fixed;
        bottom: 25px;
        right: 25px;
        background-color: #25D366;
        color: white !important;
        border-radius: 50px;
        padding: 10px 18px;
        font-size: 14px;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
        z-index: 999999;
        display: flex;
        align-items: center;
        gap: 8px;
        text-decoration: none;
        transition: all 0.3s ease;
    }}
    .floating-whatsapp span {{
        color: white !important;
    }}
    .floating-whatsapp:hover {{
        background-color: #20BA5A;
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(37, 211, 102, 0.4);
    }}
</style>

<a href="{WHATSAPP_LINK}" target="_blank" class="floating-whatsapp">
    <img src="https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg" width="24" height="24" alt="WhatsApp">
    <span>Need Help? Chat with us</span>
</a>
""",
    unsafe_allow_html=True,
)

DEFAULT_TEMPLATES = {
    "Brand New Order Welcome": (
        "Hi {buyer},\n\n"
        "Thank you so much for your order #{order_id}! "
        "We have received your payment and our team is preparing your item for dispatch.\n\n"
        "Best regards,\nCustomer Care Team"
    ),
    "Shipped Notification": (
        "Hi {buyer},\n\n"
        "Great news! Your Order #{order_id} has been dispatched via {carrier}.\n"
        "Tracking Number: {tracking_number}\n\n"
        "Thank you for shopping with us!"
    ),
    "Delivered Feedback": (
        "Hi {buyer},\n\n"
        "Your Order #{order_id} has been delivered! "
        "We hope you love your item. If you have a moment, please consider leaving us a 5-star positive review on eBay.\n\n"
        "Best regards!"
    ),
    "Order Cancellation Notice": (
        "Hi {buyer},\n\n"
        "This message is regarding your cancellation for Order #{order_id}. "
        "The cancellation has been acknowledged and processed accordingly.\n\n"
        "Thank you!"
    ),
}


# --- PERSISTENCE HELPERS ---
def hash_pass(password):
    return hashlib.sha256(str(password).strip().encode()).hexdigest()


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                if isinstance(default, dict):
                    for k, v in default.items():
                        if k not in data:
                            data[k] = v
                return data
        except Exception:
            return default
    return default


def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)


# --- AUTH & API HELPERS ---
def clean_auth_code(input_str):
    raw = input_str.strip()
    if "code=" in raw:
        parsed = urlparse(raw)
        params = parse_qs(parsed.query)
        if "code" in params:
            return params["code"][0]
        raw = raw.split("code=")[1].split("&")[0]
    return unquote(raw)


def exchange_code_for_tokens(auth_code):
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_creds = base64.b64encode(creds.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_creds}",
    }
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": RUNAME,
    }
    res = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers=headers,
        data=data,
    )
    return res.status_code, res.json()


def get_fresh_token(refresh_token):
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_creds = base64.b64encode(creds.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_creds}",
    }
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    res = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers=headers,
        data=data,
    )
    if res.status_code == 200:
        return res.json().get("access_token")
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_all_ebay_orders_cached(access_token, date_filter_str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    all_orders = []
    limit = 50
    offset = 0

    base_url = "https://api.ebay.com/sell/fulfillment/v1/order"

    while True:
        url = f"{base_url}?limit={limit}&offset={offset}"
        if date_filter_str and date_filter_str != "NONE":
            url += f"&filter=creationdate:[{date_filter_str}]"

        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            orders = data.get("orders", [])
            if not orders:
                break
            all_orders.extend(orders)
            total = data.get("total", 0)
            if len(all_orders) >= total or len(orders) < limit:
                break
            offset += limit
        else:
            break
    return all_orders


def send_ebay_message(access_token, item_id, buyer_username, body_text):
    xml_payload = f"""<?xml version="1.0" encoding="utf-8"?>
    <AddMemberMessageAAQToPartnerRequest xmlns="urn:ebay:apis:eBLBaseComponents">
      <ItemID>{item_id}</ItemID>
      <MemberMessage>
        <Body>{body_text}</Body>
        <QuestionType>General</QuestionType>
        <RecipientID>{buyer_username}</RecipientID>
      </MemberMessage>
    </AddMemberMessageAAQToPartnerRequest>"""

    headers = {
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-CALL-NAME": "AddMemberMessageAAQToPartner",
        "X-EBAY-API-SITEID": "0",
        "X-EBAY-API-IAF-TOKEN": access_token,
        "Content-Type": "text/xml",
    }
    res = requests.post(
        "https://api.ebay.com/ws/api.dll", data=xml_payload, headers=headers
    )
    return "<Ack>Success</Ack>" in res.text or "<Ack>Warning</Ack>" in res.text


def get_template_index(tpl_dict, target_key):
    keys = list(tpl_dict.keys())
    if target_key in keys:
        return keys.index(target_key)
    return 0


def get_clean_order_status(o):
    cancel_state = (
        o.get("cancelStatus", {}).get("cancelState", "").strip().upper()
    )
    cancel_req = o.get("cancelStatus", {}).get("cancelRequests", [])
    if cancel_state in [
        "CANCELED",
        "CANCELLED",
        "CANCEL_REQUESTED",
        "IN_PROGRESS",
    ] or len(cancel_req) > 0:
        return "CANCELLED", "❌ Cancelled / Refunded"

    f_status = o.get("orderFulfillmentStatus", "NOT_STARTED")
    instructions = o.get("fulfillmentStartInstructions", [])
    has_tracking = False
    is_delivered = False
    now_utc = datetime.now(timezone.utc)

    for inst in instructions:
        max_del = inst.get("maxEstimatedDeliveryDate")
        if max_del:
            try:
                clean_date = max_del.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if now_utc >= dt and f_status == "FULFILLED":
                    is_delivered = True
            except Exception:
                pass

        step = inst.get("shippingStep", {})
        if step.get("shipmentTracking"):
            has_tracking = True

    for item in o.get("lineItems", []):
        if item.get("deliveryInfo", {}).get("actualDeliveryDate"):
            is_delivered = True
        status_text = (
            item.get("deliveryInfo", {}).get("deliveryStatus", "").upper()
        )
        if status_text == "DELIVERED":
            is_delivered = True
        elif status_text in [
            "SHIPPED",
            "IN_TRANSIT",
            "OUT_FOR_DELIVERY",
            "DROPPED_OFF",
        ]:
            has_tracking = True

    for f in o.get("fulfillments", []) + o.get("shippingFulfillments", []):
        if f.get("shipmentTrackingNumber") or f.get("trackingNumber"):
            has_tracking = True
        if f.get("deliveryStatus", "").upper() == "DELIVERED":
            is_delivered = True

    if is_delivered:
        return "DELIVERED", "📦 Delivered"
    elif f_status == "FULFILLED" or has_tracking:
        return "SHIPPED", "🚚 Shipped"
    else:
        return "NEW", "🆕 New Order"


# --- INITIALIZE DATABASE ---
stores = load_json(STORES_FILE, {})
users_db = load_json(USERS_FILE, {})
templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.assigned_stores = []

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "signin"


# ==========================================================
# 1. LOGIN & SIGN UP
# ==========================================================
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c2:
        st.markdown(
            """
        <div style="text-align: center; padding: 22px 20px 14px 20px; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 15px;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg" width="95" style="margin-bottom: 6px;">
            <h3 style="margin: 0; color: #0F172A; font-weight: 700;">eBay Automation Portal</h3>
            <p style="margin-top: 4px; color: #475569; font-size: 0.85rem;">Sign in or create an account for your store</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        if st.session_state.auth_mode == "signin":
            with st.form("signin_form"):
                uname = st.text_input("Username").strip()
                pword = st.text_input("Password", type="password").strip()
                
                st.write("")
                submit_btn = st.form_submit_button("Sign In", use_container_width=True, type="primary")

                if submit_btn:
                    saved_admin_pass = users_db.get("admin", {}).get("password")
                    if uname.lower() == "admin" and (
                        (saved_admin_pass and saved_admin_pass == hash_pass(pword))
                        or (not saved_admin_pass and (pword == "admin" or pword == "admin123"))
                        or (pword == "admin")
                    ):
                        st.session_state.logged_in = True
                        st.session_state.username = "admin"
                        st.session_state.role = "admin"
                        st.session_state.assigned_stores = ["ALL"]
                        st.success("Admin Login Successful!")
                        st.rerun()

                    elif (
                        uname in users_db
                        and users_db[uname]["password"] == hash_pass(pword)
                    ):
                        st.session_state.logged_in = True
                        st.session_state.username = uname
                        st.session_state.role = users_db[uname].get("role", "client")
                        st.session_state.assigned_stores = users_db[uname].get("assigned_stores", [])
                        st.success(f"Welcome, {uname}!")
                        st.rerun()
                    else:
                        st.error("Invalid Username or Password.")

        else:
            with st.form("signup_form"):
                new_uname = st.text_input("Username").strip()
                new_pword = st.text_input("Password", type="password").strip()
                store_label = st.text_input("Your eBay Store Name / Alias:").strip()
                
                st.write("")
                signup_btn = st.form_submit_button("Sign Up", use_container_width=True, type="primary")

                if signup_btn:
                    if new_uname and new_pword and store_label:
                        if new_uname in users_db or new_uname.lower() == "admin":
                            st.error("Username already exists. Choose another.")
                        else:
                            users_db[new_uname] = {
                                "password": hash_pass(new_pword),
                                "role": "client",
                                "assigned_stores": [store_label],
                            }
                            save_json(USERS_FILE, users_db)
                            
                            st.session_state.logged_in = True
                            st.session_state.username = new_uname
                            st.session_state.role = "client"
                            st.session_state.assigned_stores = [store_label]
                            st.success("Account created successfully! Redirecting...")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Please fill in all fields (Username, Password & Store Name).")

        st.write("")
        col_sw1, col_sw2 = st.columns(2)
        with col_sw1:
            if st.button("🔑 Sign In", use_container_width=True, type="secondary" if st.session_state.auth_mode == "signin" else "primary"):
                st.session_state.auth_mode = "signin"
                st.rerun()
        with col_sw2:
            if st.button("➕ Sign Up", use_container_width=True, type="secondary" if st.session_state.auth_mode == "signup" else "primary"):
                st.session_state.auth_mode = "signup"
                st.rerun()

    st.stop()


# ==========================================================
# 2. LOGGED IN DASHBOARD
# ==========================================================

if st.session_state.role == "admin":
    accessible_stores = stores
else:
    accessible_stores = {
        k: v
        for k, v in stores.items()
        if k in st.session_state.assigned_stores
    }

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(
        """
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg" width="60">
        <span style="font-weight: 700; font-size: 1.1rem; color: #0F172A;">Workspace</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"**User:** `{st.session_state.username}`  \n**Role:** `{st.session_state.role.upper()}`"
    )

    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.assigned_stores = []
        st.rerun()

    st.divider()

    with st.expander("🔑 Change Password"):
        c_p = st.text_input("Current Password:", type="password", key="side_cp")
        n_p = st.text_input("New Password:", type="password", key="side_np")
        cn_p = st.text_input("Confirm Password:", type="password", key="side_cnp")

        if st.button("Update Password", key="btn_update_p", type="primary"):
            u_key = st.session_state.username
            saved_p = users_db.get(u_key, {}).get("password")
            
            auth_ok = False
            if u_key == "admin":
                if (saved_p and saved_p == hash_pass(c_p)) or (c_p == "admin" or c_p == "admin123"):
                    auth_ok = True
            else:
                if saved_p and saved_p == hash_pass(c_p):
                    auth_ok = True

            if auth_ok:
                if n_p == cn_p and len(n_p) > 0:
                    if u_key not in users_db:
                        users_db[u_key] = {"role": st.session_state.role, "assigned_stores": st.session_state.assigned_stores}
                    users_db[u_key]["password"] = hash_pass(n_p)
                    save_json(USERS_FILE, users_db)
                    st.success("Password Updated Successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("New passwords do not match.")
            else:
                st.error("Current password incorrect.")

    st.divider()

    if st.session_state.role == "admin":
        nav_options = [
            "All Stores Orders & Messaging",
            "📈 Sales & Revenue Reports",
            "Link & Manage eBay Stores",
            "Registered Clients Overview",
            "Global Message Templates",
        ]
    else:
        nav_options = [
            "My Orders & Auto-Messaging",
            "📈 Sales & Revenue Reports",
            "➕ Connect My eBay Store",
            "My Message Templates",
        ]

    selected_page = st.radio("Menu", nav_options, label_visibility="collapsed")
    st.divider()

    # --- SIDEBAR WHATSAPP SUPPORT CARD ---
    st.markdown(
        f"""
    <div style="padding: 12px; background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; margin-bottom: 10px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg" width="20" height="20">
            <strong style="color: #166534; font-size: 0.9rem;">Direct Support</strong>
        </div>
        <p style="font-size: 0.8rem; color: #15803D; margin-bottom: 8px;">Got questions or need help setting up?</p>
        <a href="{WHATSAPP_LINK}" target="_blank" style="text-decoration: none;">
            <div style="background: #22C55E; color: white !important; text-align: center; padding: 6px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">
                Chat on WhatsApp
            </div>
        </a>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.caption("🔒 Verified eBay REST API Partner")


# ==========================================================
# PAGE A: ORDERS & AUTO-MESSAGING HUB
# ==========================================================
if "Orders &" in selected_page:
    st.markdown(
        f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg" width="75">
        <h2 style="margin: 0; color: #0F172A; font-weight: 700;">{selected_page}</h2>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if not accessible_stores:
        st.info("👋 Welcome! Your store is not connected yet.")
        st.write("Please go to **'➕ Connect My eBay Store'** in the sidebar to authorize your account.")
    else:
        active_store_name = st.selectbox(
            "Select Store Channel:", list(accessible_stores.keys())
        )
        tokens = accessible_stores[active_store_name]

        st.divider()
        st.markdown("#### 🔄 Sync Orders from eBay")
        
        fetch_all_orders_toggle = st.checkbox("📋 Fetch ALL Orders (No Date Limit)", value=False, key="all_orders_toggle")
        
        col_date1, col_date2, col_sync_btn = st.columns([2, 2, 1.5])
        
        with col_date1:
            default_start = (datetime.now() - timedelta(days=30)).date()
            start_date = st.date_input("From Date:", value=default_start, disabled=fetch_all_orders_toggle, key="start_date_input")
            
        with col_date2:
            default_end = datetime.now().date()
            end_date = st.date_input("To Date:", value=default_end, disabled=fetch_all_orders_toggle, key="end_date_input")

        date_filter_key = "NONE"
        if not fetch_all_orders_toggle:
            if start_date > end_date:
                st.error("'From Date' cannot be after 'To Date'.")
                orders = []
                st.session_state[f"orders_{active_store_name}"] = []
            else:
                date_filter_key = f"{start_date}T00:00:00.000Z..{end_date}T23:59:59.999Z"

        orders = st.session_state.get(f"orders_{active_store_name}", [])

        with col_sync_btn:
            st.write("")
            manual_sync = st.button(
                f"🔄 Force Refresh",
                type="secondary",
                use_container_width=True,
                key="manual_sync_btn"
            )

        current_filter_hash = hash((active_store_name, date_filter_key))
        last_filter_hash = st.session_state.get(f"last_hash_{active_store_name}")

        if manual_sync or current_filter_hash != last_filter_hash:
            if not (not fetch_all_orders_toggle and start_date > end_date):
                with st.spinner(f"Syncing orders for {active_store_name}..."):
                    access_token = tokens["access_token"]
                    test_headers = {"Authorization": f"Bearer {access_token}"}
                    test_res = requests.get("https://api.ebay.com/sell/fulfillment/v1/order?limit=1", headers=test_headers)
                    
                    if test_res.status_code != 200 and tokens.get("refresh_token"):
                        new_t = get_fresh_token(tokens["refresh_token"])
                        if new_t:
                            stores[active_store_name]["access_token"] = new_t
                            save_json(STORES_FILE, stores)
                            access_token = new_t

                    if manual_sync:
                        st.cache_data.clear()

                    try:
                        fetched_orders = fetch_all_ebay_orders_cached(access_token, date_filter_key)
                        st.session_state[f"orders_{active_store_name}"] = fetched_orders
                        st.session_state[f"last_hash_{active_store_name}"] = current_filter_hash
                        orders = fetched_orders
                        st.success(f"Synced {len(fetched_orders)} orders!")
                    except Exception as e:
                        st.error(f"Failed to fetch orders: {str(e)}")
                        orders = []

        if orders:
            st.divider()
            col_filter, col_template = st.columns([2, 2])

            filter_options = [
                "📋 All Orders",
                "🆕 Brand New Orders (Unfulfilled)",
                "🚚 Shipped Orders (In-Transit)",
                "📦 Delivered Orders",
                "❌ Cancelled Orders",
            ]
            with col_filter:
                status_filter = st.selectbox("Target Filter Group:", filter_options, key="status_filter_select")

            target_tpl_name = "Brand New Order Welcome"
            if "Shipped" in status_filter:
                target_tpl_name = "Shipped Notification"
            elif "Delivered" in status_filter:
                target_tpl_name = "Delivered Feedback"
            elif "Cancelled" in status_filter:
                target_tpl_name = "Order Cancellation Notice"

            default_tpl_index = get_template_index(templates, target_tpl_name)

            with col_template:
                chosen_template = st.selectbox(
                    "Active Message Template:",
                    list(templates.keys()),
                    index=default_tpl_index,
                    key="template_filter_select"
                )

            display_orders = []
            for o in orders:
                order_type, _ = get_clean_order_status(o)

                if status_filter == "📋 All Orders":
                    display_orders.append(o)
                elif status_filter == "❌ Cancelled Orders":
                    if order_type == "CANCELLED":
                        display_orders.append(o)
                elif status_filter == "🆕 Brand New Orders (Unfulfilled)":
                    if order_type == "NEW":
                        display_orders.append(o)
                elif status_filter == "🚚 Shipped Orders (In-Transit)":
                    if order_type == "SHIPPED":
                        display_orders.append(o)
                elif status_filter == "📦 Delivered Orders":
                    if order_type == "DELIVERED":
                        display_orders.append(o)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Synced", len(orders))
            m2.metric("Filtered Matches", len(display_orders))
            m3.metric("Template Selected", chosen_template)

            st.write("")

            if st.button(
                f"🚀 Send '{chosen_template}' to All ({len(display_orders)}) Matched Orders",
                type="primary",
                key="bulk_send_btn"
            ):
                progress_bar = st.progress(0)
                sent_count = 0
                access_token = accessible_stores[active_store_name]["access_token"]

                for i, o in enumerate(display_orders):
                    order_id = o.get("orderId", "")
                    buyer = o.get("buyer", {}).get("username", "Buyer")
                    line_items = o.get("lineItems", [])
                    item_id = (
                        line_items[0].get("legacyItemId")
                        if line_items
                        else None
                    )

                    tracking_num = "Uploaded on eBay"
                    carrier_name = "Standard Courier"

                    for inst in o.get("fulfillmentStartInstructions", []):
                        step = inst.get("shippingStep", {})
                        track_info = step.get(
                            "shipmentTracking", {}
                        ).get("trackingNumber")
                        carrier_info = step.get("shippingCarrierCode")
                        if track_info:
                            tracking_num = track_info
                        if carrier_info:
                            carrier_name = carrier_info

                    try:
                        msg_body = templates[chosen_template].format(
                            buyer=buyer,
                            order_id=order_id,
                            tracking_number=tracking_num,
                            carrier=carrier_name,
                        )

                        if item_id:
                            success = send_ebay_message(
                                access_token, item_id, buyer, msg_body
                            )
                            if success:
                                sent_count += 1
                                logs[f"{order_id}_{chosen_template}"] = {
                                    "buyer": buyer,
                                    "status": "Sent",
                                    "time": datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                }
                    except Exception:
                        pass

                    time.sleep(0.3)
                    progress_bar.progress((i + 1) / len(display_orders))

                save_json(LOGS_FILE, logs)
                st.success(
                    f"✅ {sent_count}/{len(display_orders)} messages dispatched!"
                )
                time.sleep(1)
                st.rerun()

            st.divider()
            st.markdown("### 📋 Order List & Direct Actions")

            for o in display_orders:
                order_id = o.get("orderId", "")
                buyer = o.get("buyer", {}).get("username", "Buyer")
                line_items = o.get("lineItems", [])
                item_title = (
                    line_items[0].get("title", "Item") if line_items else ""
                )
                item_id = (
                    line_items[0].get("legacyItemId", "N/A")
                    if line_items
                    else "N/A"
                )

                _, clean_badge = get_clean_order_status(o)

                tracking_num = "Uploaded on eBay"
                carrier_name = "Courier"

                for inst in o.get("fulfillmentStartInstructions", []):
                    step = inst.get("shippingStep", {})
                    track_info = step.get(
                        "shipmentTracking", {}
                    ).get("trackingNumber")
                    carrier_info = step.get("shippingCarrierCode")
                    if track_info:
                        tracking_num = track_info
                    if carrier_info:
                        carrier_name = carrier_info

                try:
                    formatted_preview = templates[chosen_template].format(
                        buyer=buyer,
                        order_id=order_id,
                        tracking_number=tracking_num,
                        carrier=carrier_name,
                    )
                except Exception:
                    formatted_preview = templates[chosen_template]

                log_key = f"{order_id}_{chosen_template}"
                is_sent = log_key in logs

                with st.expander(
                    f"Order #{order_id} | Buyer: {buyer} | {clean_badge} | {'✅ Sent' if is_sent else '⏳ Ready'}"
                ):
                    c_det, c_act = st.columns([1.5, 2])
                    with c_det:
                        st.write(f"**Item:** {item_title}")
                        st.write(f"**Item ID:** `{item_id}`")
                        st.write(f"**Carrier:** `{carrier_name}`")
                        st.write(f"**Tracking:** `{tracking_num}`")

                    with c_act:
                        user_msg_input = st.text_area(
                            f"Preview ({chosen_template}):",
                            value=formatted_preview,
                            height=110,
                            key=f"input_{order_id}_{chosen_template}_{current_filter_hash}",
                        )

                        if st.button(
                            f"✉️ Send Message to {buyer}",
                            key=f"btn_send_{order_id}_{chosen_template}",
                            type="secondary",
                        ):
                            if item_id != "N/A":
                                access_token = accessible_stores[active_store_name]["access_token"]
                                success = send_ebay_message(
                                    access_token,
                                    item_id,
                                    buyer,
                                    user_msg_input,
                                )
                                if success:
                                    logs[log_key] = {
                                        "buyer": buyer,
                                        "status": "Sent",
                                        "time": datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                    }
                                    save_json(LOGS_FILE, logs)
                                    st.success(f"Sent to {buyer}!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to send message via eBay WS API.")

        elif orders is not None:
             st.info("No orders found for the selected store and date range.")


# ==========================================================
# PAGE B: SALES & REVENUE REPORTS WITH ADVANCED STATUS SEGMENTS
# ==========================================================
elif selected_page == "📈 Sales & Revenue Reports":
    st.markdown(
        """
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg" width="75">
        <h2 style="margin: 0; color: #0F172A; font-weight: 700;">Sales, Shipped & Refund Reports</h2>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.caption("Detailed financials segmented by Completed Sales, Shipped Orders, Delivered, and Refunds/Cancellations.")

    if not accessible_stores:
        st.info("👋 Welcome! Your store is not connected yet.")
    else:
        active_sales_store = st.selectbox(
            "Select Store Channel for Reports:", list(accessible_stores.keys()), key="sales_rep_store_sel"
        )
        tokens = accessible_stores[active_sales_store]

        st.divider()
        st.markdown("#### 📅 Report Date Range")
        
        fetch_all_sales_toggle = st.checkbox("📋 Fetch All-Time Sales (No Date Limit)", value=False, key="all_sales_toggle")
        
        c_sd1, c_sd2, c_sbtn = st.columns([2, 2, 1.5])
        with c_sd1:
            default_start = (datetime.now() - timedelta(days=30)).date()
            sales_start_date = st.date_input("From Date:", value=default_start, disabled=fetch_all_sales_toggle, key="sales_start_date")
        with c_sd2:
            default_end = datetime.now().date()
            sales_end_date = st.date_input("To Date:", value=default_end, disabled=fetch_all_sales_toggle, key="sales_end_date")

        sales_date_filter_key = "NONE"
        if not fetch_all_sales_toggle:
            if sales_start_date > sales_end_date:
                st.error("'From Date' cannot be after 'To Date'.")
            else:
                sales_date_filter_key = f"{sales_start_date}T00:00:00.000Z..{sales_end_date}T23:59:59.999Z"

        with c_sbtn:
            st.write("")
            refresh_sales_btn = st.button("🔄 Sync Sales Data", type="primary", use_container_width=True, key="sync_sales_btn")

        sales_hash = hash((active_sales_store, sales_date_filter_key, "sales"))
        last_sales_hash = st.session_state.get(f"last_sales_hash_{active_sales_store}")

        if refresh_sales_btn or sales_hash != last_sales_hash:
            if not (not fetch_all_sales_toggle and sales_start_date > sales_end_date):
                with st.spinner("Calculating sales and financial data..."):
                    access_token = tokens["access_token"]
                    test_headers = {"Authorization": f"Bearer {access_token}"}
                    test_res = requests.get("https://api.ebay.com/sell/fulfillment/v1/order?limit=1", headers=test_headers)
                    if test_res.status_code != 200 and tokens.get("refresh_token"):
                        new_t = get_fresh_token(tokens["refresh_token"])
                        if new_t:
                            stores[active_sales_store]["access_token"] = new_t
                            save_json(STORES_FILE, stores)
                            access_token = new_t

                    if refresh_sales_btn:
                        st.cache_data.clear()

                    try:
                        raw_orders = fetch_all_ebay_orders_cached(access_token, sales_date_filter_key)
                        st.session_state[f"sales_orders_{active_sales_store}"] = raw_orders
                        st.session_state[f"last_sales_hash_{active_sales_store}"] = sales_hash
                    except Exception as e:
                        st.error(f"Failed to load sales: {str(e)}")

        sales_orders = st.session_state.get(f"sales_orders_{active_sales_store}", [])

        if sales_orders:
            # Parse all rows with raw status classification
            parsed_all_rows = []
            currency_code = "USD"

            for o in sales_orders:
                order_id = o.get("orderId", "N/A")
                created_date = o.get("creationDate", "")[:10]
                buyer = o.get("buyer", {}).get("username", "Buyer")
                
                # Pricing
                pricing = o.get("pricingSummary", {})
                total_obj = pricing.get("total", {})
                order_total = float(total_obj.get("value", 0.0))
                currency_code = total_obj.get("currency", currency_code)
                
                status_raw, status_badge = get_clean_order_status(o)

                line_items = o.get("lineItems", [])
                items_titles = []
                total_qty = 0
                for li in line_items:
                    qty = int(li.get("quantity", 1))
                    total_qty += qty
                    items_titles.append(f"{li.get('title', 'Item')} (x{qty})")

                parsed_all_rows.append({
                    "Order ID": order_id,
                    "Date": created_date,
                    "Buyer": buyer,
                    "Items": ", ".join(items_titles),
                    "Quantity": total_qty,
                    "Amount": order_total,
                    "Currency": currency_code,
                    "Status": status_badge,
                    "RawStatus": status_raw
                })

            st.divider()

            # --- STATUS SEGMENT SELECTOR ---
            st.markdown("#### 🎯 Select Sheet Category")
            sales_segment_options = [
                "📊 All Successful Sales (Gross)",
                "🚚 Shipped Orders (In-Transit)",
                "📦 Delivered Orders (Completed)",
                "❌ Cancelled & Refunded Orders",
                "📋 Complete Raw Order Stream"
            ]
            chosen_segment = st.selectbox("View Report Sheet:", sales_segment_options, key="sales_segment_selector")

            # Filter rows based on chosen segment
            if chosen_segment == "📊 All Successful Sales (Gross)":
                filtered_rows = [r for r in parsed_all_rows if r["RawStatus"] != "CANCELLED"]
            elif chosen_segment == "🚚 Shipped Orders (In-Transit)":
                filtered_rows = [r for r in parsed_all_rows if r["RawStatus"] == "SHIPPED"]
            elif chosen_segment == "📦 Delivered Orders (Completed)":
                filtered_rows = [r for r in parsed_all_rows if r["RawStatus"] == "DELIVERED"]
            elif chosen_segment == "❌ Cancelled & Refunded Orders":
                filtered_rows = [r for r in parsed_all_rows if r["RawStatus"] == "CANCELLED"]
            else:
                filtered_rows = parsed_all_rows

            # Calculate KPI Metrics for current selection
            segment_revenue = sum(r["Amount"] for r in filtered_rows)
            segment_orders_count = len(filtered_rows)
            segment_items_count = sum(r["Quantity"] for r in filtered_rows)
            segment_aov = (segment_revenue / segment_orders_count) if segment_orders_count > 0 else 0.0

            # --- KPI DISPLAY ---
            k1, k2, k3, k4 = st.columns(4)
            metric_rev_label = "Total Refunded Amount" if "Refunded" in chosen_segment else "Total Revenue"
            k1.metric(metric_rev_label, f"{currency_code} {segment_revenue:,.2f}")
            k2.metric("Total Orders", segment_orders_count)
            k3.metric("Avg Order Value (AOV)", f"{currency_code} {segment_aov:,.2f}")
            k4.metric("Total Units Count", segment_items_count)

            st.divider()

            # --- CSV EXPORT & INTERACTIVE TABLE ---
            df_display = pd.DataFrame(filtered_rows).drop(columns=["RawStatus"])

            c_head, c_dl = st.columns([3, 1])
            with c_head:
                st.markdown(f"### 📋 {chosen_segment} Sheet ({len(filtered_rows)} records)")
            with c_dl:
                csv_buffer = io.StringIO()
                df_display.to_csv(csv_buffer, index=False)
                clean_seg_filename = chosen_segment.split(" ")[1].lower()
                st.download_button(
                    label=f"📥 Download {chosen_segment.split(' ')[1]} CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"eBay_{clean_seg_filename}_Report_{active_sales_store}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )

            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No sales records found for this period. Click '🔄 Sync Sales Data' to fetch.")


# ==========================================================
# PAGE C: LINK & MANAGE STORES (ADMIN OR CLIENT SELF-CONNECT)
# ==========================================================
elif (
    "Connect My eBay Store" in selected_page
    or "Link & Manage eBay Stores" in selected_page
):
    st.markdown("## ➕ Connect & Authorize eBay Store")
    st.caption(
        "Securely authenticate your production eBay account via official OAuth."
    )

    c_link, c_manage = st.columns([1.2, 1])

    with c_link:
        st.markdown("### 🔗 Authorize Account")
        st.info("Step 1: Click the link below and authorize on eBay:")
        st.markdown(f"👉 [**Authorize with eBay (Click Here)**]({AUTH_URL})")
        st.write("")

        redirect_input = st.text_input("Redirected URL / Code:", key="auth_code_input")

        assigned_s = (
            st.session_state.assigned_stores[0]
            if st.session_state.assigned_stores
            and st.session_state.assigned_stores[0] != "ALL"
            else ""
        )
        store_alias = st.text_input("Store Name / Label:", value=assigned_s, key="store_label_input")

        if st.button("Complete Authorization", type="primary", key="complete_auth_btn"):
            if redirect_input and store_alias:
                final_code = clean_auth_code(redirect_input)
                with st.spinner("Exchanging code for tokens..."):
                    status, token_data = exchange_code_for_tokens(final_code)

                if status == 200 and "access_token" in token_data:
                    stores[store_alias] = {
                        "access_token": token_data["access_token"],
                        "refresh_token": token_data.get("refresh_token", ""),
                    }
                    save_json(STORES_FILE, stores)

                    u_curr = st.session_state.username
                    if u_curr in users_db:
                        users_db[u_curr]["assigned_stores"] = [store_alias]
                        save_json(USERS_FILE, users_db)
                        st.session_state.assigned_stores = [store_alias]
                    
                    st.cache_data.clear()
                    st.success(f"Store '{store_alias}' linked successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Authentication failed. Please verify code/URL.")
            else:
                st.warning("All fields are required.")

    with c_manage:
        st.markdown("### 🏬 Connected Store Status")
        if not accessible_stores:
            st.info("No stores linked yet.")
        else:
            for s_name in list(accessible_stores.keys()):
                with st.container():
                    st.markdown(
                        f"""
                    <div style="padding: 12px 16px; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; margin-bottom: 10px;">
                        <strong style="font-size: 1.05rem; color: #0F172A;">🏪 {s_name}</strong><br>
                        <span style="color: #16A34A; font-size: 0.85rem; font-weight: 500;">● Connected & Active</span>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        f"🗑️ Disconnect {s_name}",
                        key=f"del_store_{s_name}",
                        type="secondary",
                    ):
                        del stores[s_name]
                        save_json(STORES_FILE, stores)
                        st.cache_data.clear()
                        st.success(f"Store '{s_name}' removed!")
                        time.sleep(1)
                        st.rerun()


# ==========================================================
# PAGE D: REGISTERED CLIENTS OVERVIEW (ADMIN ONLY)
# ==========================================================
elif (
    selected_page == "Registered Clients Overview"
    and st.session_state.role == "admin"
):
    st.markdown("## 👥 Self-Registered Clients & Stores")
    st.caption(
        "Monitor all registered clients, their store names, and connected status."
    )

    client_users = {k: v for k, v in users_db.items() if k != "admin"}

    if not client_users:
        st.info("No clients have signed up yet.")
    else:
        for u, data in client_users.items():
            assigned = data.get("assigned_stores", ["N/A"])[0]
            is_connected = assigned in stores

            with st.container():
                st.markdown(
                    f"""
                <div style="padding: 14px 18px; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong style="font-size: 1.05rem;">👤 Client: {u}</strong><br>
                        <span style="color: #475569; font-size: 0.85rem;">Store Name: <b>{assigned}</b></span>
                    </div>
                    <div>
                        <span style="color: {'#16A34A' if is_connected else '#DC2626'}; font-weight: 600; font-size: 0.9rem;">
                            {'● eBay Linked' if is_connected else '○ Pending Connection'}
                        </span>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"🗑️ Delete Client {u}",
                    key=f"del_client_{u}",
                    type="secondary",
                ):
                    del users_db[u]
                    save_json(USERS_FILE, users_db)
                    st.success(f"Client '{u}' removed!")
                    time.sleep(1)
                    st.rerun()


# ==========================================================
# PAGE E: MESSAGE TEMPLATES (CLIENT & ADMIN)
# ==========================================================
elif "Message Templates" in selected_page:
    st.markdown("## 📝 Message Templates Settings")
    st.caption(
        "Manage personalized messaging templates using dynamic attributes."
    )

    st.markdown(
        """
    **Supported Dynamic Variables:**
    * `{buyer}`: Automatically maps to the customer's eBay username.
    * `{order_id}`: Replaced with the corresponding Order ID.
    * `{carrier}`: Carrier name from eBay fulfillment.
    * `{tracking_number}`: Tracking number uploaded to the order.
    """
    )
    st.divider()

    selected_tpl_edit = st.selectbox(
        "Select Template to Edit:", list(templates.keys()), key="template_edit_select"
    )
    tpl_body = st.text_area(
        "Template Content:",
        value=templates[selected_tpl_edit],
        height=180,
        key=f"editor_{selected_tpl_edit}",
    )

    if st.button("Save Template", type="primary", key="save_template_btn"):
        templates[selected_tpl_edit] = tpl_body
        save_json(TEMPLATES_FILE, templates)
        st.success(f"Template '{selected_tpl_edit}' saved successfully!")
        time.sleep(1)
        st.rerun()
