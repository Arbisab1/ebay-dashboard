import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import time
from urllib.parse import parse_qs, unquote, urlparse
import requests
import streamlit as st

# --- CONFIGURATION ---
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
    page_title="OrderPing — eBay Automation",
    layout="wide",
    page_icon="📦",
    initial_sidebar_state="collapsed",
)

# --- ORDERPING MINIMALIST SAAS CSS ---
st.markdown(
    """
<style>
    /* OrderPing Custom Theme */
    .stApp {
        background-color: #F8F8FA !important;
        color: #2D3748 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1100px !important;
    }

    /* Hero Typography */
    .hero-badge {
        font-size: 0.75rem;
        letter-spacing: 2px;
        color: #718096;
        text-transform: uppercase;
        font-weight: 700;
        text-align: center;
        margin-bottom: 12px;
    }

    .hero-title {
        font-size: 3.2rem;
        font-weight: 800;
        color: #1A202C;
        text-align: center;
        line-height: 1.15;
        margin-bottom: 16px;
        letter-spacing: -0.5px;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #718096;
        text-align: center;
        max-width: 650px;
        margin: 0 auto 30px auto;
        line-height: 1.5;
    }

    .journey-title {
        text-align: center;
        font-size: 1.35rem;
        font-weight: 700;
        color: #2D3748;
        margin-top: 50px;
        margin-bottom: 25px;
    }

    /* Buttons */
    button[kind="primary"] {
        background-color: #3B444F !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.4rem !important;
        border: none !important;
    }

    button[kind="secondary"] {
        background-color: transparent !important;
        color: #3B444F !important;
        border: 1px solid #CBD5E0 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    /* Cards */
    .step-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
    }
    
    div[data-testid="stMetricValue"] {
        color: #3B444F !important;
        font-weight: 700 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

DEFAULT_TEMPLATES = {
    "Brand New Order Welcome": (
        "Hi {buyer},\n\n"
        "Thank you for your order #{order_id}! "
        "We are preparing your package for dispatch.\n\n"
        "Best regards,\nCustomer Care"
    ),
    "Shipped Notification": (
        "Hi {buyer},\n\n"
        "Your Order #{order_id} has been dispatched via {carrier}.\n"
        "Tracking Number: {tracking_number}\n\n"
        "Thank you for your purchase!"
    ),
    "Delivered Feedback": (
        "Hi {buyer},\n\n"
        "Your Order #{order_id} has been delivered! "
        "We hope you enjoy your item. Please consider leaving us a 5-star review on eBay.\n\n"
        "Best regards!"
    ),
    "Order Cancellation Notice": (
        "Hi {buyer},\n\n"
        "This is regarding your cancellation for Order #{order_id}. "
        "Your cancellation has been processed.\n\n"
        "Thank you!"
    ),
}


# --- PERSISTENCE HELPERS ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()


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


DEFAULT_USERS = {
    "admin": {
        "password": hash_pass("admin123"),
        "role": "admin",
        "assigned_stores": ["ALL"],
    }
}


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


def fetch_all_ebay_orders(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    all_orders = []
    limit = 50
    offset = 0

    while True:
        url = f"https://api.ebay.com/sell/fulfillment/v1/order?limit={limit}&offset={offset}"
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
        return "CANCELLED", "❌ Cancelled"

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
        return "SHIPPED", "🚚 Shipped (In-Transit)"
    else:
        return "NEW", "🆕 New Order"


# --- INITIALIZE DATABASE ---
stores = load_json(STORES_FILE, {})
users_db = load_json(USERS_FILE, DEFAULT_USERS)
templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.assigned_stores = []
if "show_login" not in st.session_state:
    st.session_state.show_login = False


# ==========================================================
# ORDERPING TOP NAVBAR
# ==========================================================
c_nav1, c_nav2 = st.columns([3, 1])
with c_nav1:
    st.markdown(
        """
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 1.5rem;">📦</span>
        <span style="font-size: 1.3rem; font-weight: 800; color: #1A202C; letter-spacing: -0.5px;">OrderPing</span>
    </div>
    """,
        unsafe_allow_html=True,
    )
with c_nav2:
    if not st.session_state.logged_in:
        if st.button("Get started", type="primary", use_container_width=True):
            st.session_state.show_login = True
    else:
        if st.button("Logout", type="secondary", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.role = None
            st.rerun()

st.write("")

# ==========================================================
# 1. LANDING & LOGIN VIEW
# ==========================================================
if not st.session_state.logged_in:
    if not st.session_state.show_login:
        # Hero Section exactly like the image
        st.markdown(
            """
        <div style="margin-top: 30px;">
            <div class="hero-badge">EBAY AUTOMATION</div>
            <div class="hero-title">Every eBay buyer hears<br>from you — automatically.</div>
            <div class="hero-subtitle">
                Thank-you notes on order, tracking on dispatch, a delivery check-in and a feedback reminder. Written by you, sent by OrderPing.
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        c_b1, c_b2, c_b3 = st.columns([1, 1.2, 1])
        with c_b2:
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                st.markdown(
                    f"""
                <a href="{AUTH_URL}" target="_blank" style="text-decoration: none;">
                    <div style="background-color: #3B444F; color: white; padding: 10px 16px; border-radius: 8px; text-align: center; font-weight: 600; font-size: 0.95rem;">
                        Connect my eBay store
                    </div>
                </a>
                """,
                    unsafe_allow_html=True,
                )
            with c_btn2:
                if st.button("Open dashboard", use_container_width=True):
                    st.session_state.show_login = True
                    st.rerun()

        # Step cards
        st.markdown(
            "<div class='journey-title'>The whole order journey, covered</div>",
            unsafe_allow_html=True,
        )

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.markdown(
                """
            <div class="step-card">
                <small style="color: #A0AEC0; font-weight: 700;">01</small>
                <h4 style="margin: 6px 0; color: #2D3748;">New Order</h4>
                <p style="font-size: 0.82rem; color: #718096; margin: 0;">Instant thank you note sent as soon as payment is confirmed.</p>
            </div>
            """,
                unsafe_allow_html=True,
            )
        with s2:
            st.markdown(
                """
            <div class="step-card">
                <small style="color: #A0AEC0; font-weight: 700;">02</small>
                <h4 style="margin: 6px 0; color: #2D3748;">Dispatched</h4>
                <p style="font-size: 0.82rem; color: #718096; margin: 0;">Tracking number and carrier details shared automatically.</p>
            </div>
            """,
                unsafe_allow_html=True,
            )
        with s3:
            st.markdown(
                """
            <div class="step-card">
                <small style="color: #A0AEC0; font-weight: 700;">03</small>
                <h4 style="margin: 6px 0; color: #2D3748;">Delivered</h4>
                <p style="font-size: 0.82rem; color: #718096; margin: 0;">Friendly check-in asking for 5-star positive review.</p>
            </div>
            """,
                unsafe_allow_html=True,
            )
        with s4:
            st.markdown(
                """
            <div class="step-card">
                <small style="color: #A0AEC0; font-weight: 700;">04</small>
                <h4 style="margin: 6px 0; color: #2D3748;">Cancellation</h4>
                <p style="font-size: 0.82rem; color: #718096; margin: 0;">Automated confirmation for cancelled transactions.</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

    else:
        # Clean Login Form
        c_l1, c_l2, c_l3 = st.columns([1, 1.4, 1])
        with c_l2:
            st.markdown("### 🔐 Sign In to OrderPing")
            with st.form("login_form"):
                uname = st.text_input("Username")
                pword = st.text_input("Password", type="password")
                submit_btn = st.form_submit_button(
                    "Sign In", use_container_width=True, type="primary"
                )

                if submit_btn:
                    if (
                        uname in users_db
                        and users_db[uname]["password"] == hash_pass(pword)
                    ):
                        st.session_state.logged_in = True
                        st.session_state.username = uname
                        st.session_state.role = users_db[uname]["role"]
                        st.session_state.assigned_stores = users_db[uname].get(
                            "assigned_stores", []
                        )
                        st.success("Signed in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

            if st.button("← Back to home"):
                st.session_state.show_login = False
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

tab_names = [
    "📊 Orders & Automation",
    "➕ Link Store",
    "📝 Message Templates",
]
if st.session_state.role == "admin":
    tab_names.append("👥 User Access")

main_tabs = st.tabs(tab_names)

# --- TAB 1: ORDERS & MESSAGING HUB ---
with main_tabs[0]:
    if not accessible_stores:
        st.info(
            "No stores linked yet. Please use the **'Link Store'** tab to authorize your eBay account."
        )
    else:
        c_s1, c_s2 = st.columns([2, 1])
        with c_s1:
            active_store_name = st.selectbox(
                "Active Store Channel:", list(accessible_stores.keys())
            )
            tokens = accessible_stores[active_store_name]
        with c_s2:
            st.write("")
            if st.button(
                f"🔄 Sync Orders ({active_store_name})",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Fetching orders from eBay..."):
                    all_orders = fetch_all_ebay_orders(tokens["access_token"])
                    if not all_orders and tokens.get("refresh_token"):
                        new_t = get_fresh_token(tokens["refresh_token"])
                        if new_t:
                            stores[active_store_name]["access_token"] = new_t
                            save_json(STORES_FILE, stores)
                            all_orders = fetch_all_ebay_orders(new_t)

                    st.session_state[f"orders_{active_store_name}"] = all_orders
                    st.success(f"Loaded {len(all_orders)} orders!")

        orders = st.session_state.get(f"orders_{active_store_name}", [])

        if orders:
            st.divider()
            col_filter, col_template = st.columns([2, 2])

            filter_options = [
                "🆕 Brand New Orders (Unfulfilled)",
                "🚚 Shipped Orders (In-Transit)",
                "📦 Delivered Orders",
                "❌ Cancelled Orders",
                "📋 All Orders",
            ]
            with col_filter:
                status_filter = st.selectbox("Journey Stage Filter:", filter_options)

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
                    "Message Template:",
                    list(templates.keys()),
                    index=default_tpl_index,
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
            m1.metric("Synced Orders", len(orders))
            m2.metric("Filtered Matches", len(display_orders))
            m3.metric("Selected Template", chosen_template)

            st.write("")

            if st.button(
                f"🚀 Send '{chosen_template}' to All ({len(display_orders)}) Orders",
                type="primary",
            ):
                progress_bar = st.progress(0)
                sent_count = 0

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
                        track_info = step.get("shipmentTracking", {}).get(
                            "trackingNumber"
                        )
                        carrier_info = step.get("shippingCarrierCode")
                        if track_info:
                            tracking_num = track_info
                        if carrier_info:
                            carrier_name = carrier_info

                    msg_body = templates[chosen_template].format(
                        buyer=buyer,
                        order_id=order_id,
                        tracking_number=tracking_num,
                        carrier=carrier_name,
                    )

                    if item_id:
                        success = send_ebay_message(
                            tokens["access_token"], item_id, buyer, msg_body
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

                    time.sleep(0.3)
                    progress_bar.progress((i + 1) / len(display_orders))

                save_json(LOGS_FILE, logs)
                st.success(
                    f"✅ {sent_count}/{len(display_orders)} messages dispatched by OrderPing!"
                )

            st.divider()
            st.markdown("### 📋 Live Order Details")

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
                    track_info = step.get("shipmentTracking", {}).get(
                        "trackingNumber"
                    )
                    carrier_info = step.get("shippingCarrierCode")
                    if track_info:
                        tracking_num = track_info
                    if carrier_info:
                        carrier_name = carrier_info

                formatted_preview = templates[chosen_template].format(
                    buyer=buyer,
                    order_id=order_id,
                    tracking_number=tracking_num,
                    carrier=carrier_name,
                )

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
                            key=f"input_{order_id}_{chosen_template}_{status_filter}",
                        )

                        if st.button(
                            f"✉️ Send to {buyer}",
                            key=f"btn_send_{order_id}_{chosen_template}",
                            type="secondary",
                        ):
                            if item_id != "N/A":
                                success = send_ebay_message(
                                    tokens["access_token"],
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
                                    st.rerun()
                                else:
                                    st.error("Failed to send.")

# --- TAB 2: LINK STORE ---
with main_tabs[1]:
    st.markdown("### ➕ Connect eBay Account")
    st.markdown(f"[👉 **Click here to authorize with eBay**]({AUTH_URL})")
    st.write("")

    redirect_input = st.text_input("Paste Redirected URL / Authorization Code:")
    store_alias = st.text_input("Store Name / Alias:")

    if st.button("Save & Link Store", type="primary"):
        if redirect_input and store_alias:
            final_code = clean_auth_code(redirect_input)
            status, token_data = exchange_code_for_tokens(final_code)

            if status == 200 and "access_token" in token_data:
                stores[store_alias] = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token", ""),
                }
                save_json(STORES_FILE, stores)
                st.success(f"Store '{store_alias}' successfully connected!")
                st.rerun()
            else:
                st.error("Authorization failed. Check URL/Code.")
        else:
            st.warning("All fields are required.")

    if accessible_stores:
        st.divider()
        st.markdown("### 🏬 Manage Linked Stores")
        for s in list(accessible_stores.keys()):
            c_m1, c_m2 = st.columns([3, 1])
            with c_m1:
                st.write(f"**🏪 {s}** (Connected & Active)")
            with c_m2:
                if st.button(f"🗑️ Remove", key=f"del_{s}", type="secondary"):
                    del stores[s]
                    save_json(STORES_FILE, stores)
                    st.rerun()

# --- TAB 3: MESSAGE TEMPLATES ---
with main_tabs[2]:
    st.markdown("### 📝 Message Templates")
    selected_tpl_edit = st.selectbox(
        "Choose Template to Edit:", list(templates.keys())
    )
    tpl_body = st.text_area(
        "Template Body (use {buyer}, {order_id}, {carrier}, {tracking_number}):",
        value=templates[selected_tpl_edit],
        height=180,
    )
    if st.button("Save Template", type="primary"):
        templates[selected_tpl_edit] = tpl_body
        save_json(TEMPLATES_FILE, templates)
        st.success("Template saved!")
        st.rerun()

# --- TAB 4: ADMIN USER ACCESS ---
if st.session_state.role == "admin":
    with main_tabs[3]:
        st.markdown("### 👥 User Access Control")
        c_u1, c_u2 = st.columns([1, 1])
        with c_u1:
            st.markdown("#### Create New Client")
            new_uname = st.text_input("Username:")
            new_pword = st.text_input("Password:", type="password")
            store_choices = list(stores.keys())
            assigned_store = st.selectbox(
                "Assign Store:",
                store_choices if store_choices else ["No stores"],
            )

            if st.button("Create Account", type="primary"):
                if new_uname and new_pword and assigned_store != "No stores":
                    if new_uname in users_db:
                        st.error("User exists!")
                    else:
                        users_db[new_uname] = {
                            "password": hash_pass(new_pword),
                            "role": "client",
                            "assigned_stores": [assigned_store],
                        }
                        save_json(USERS_FILE, users_db)
                        st.success(f"Account for '{new_uname}' created!")
                        st.rerun()
                else:
                    st.warning("All fields are required.")

        with c_u2:
            st.markdown("#### Existing Users")
            for u, data in users_db.items():
                st.write(
                    f"**👤 {u}** ({data['role'].upper()}) — Store: {data.get('assigned_stores')}"
                )
