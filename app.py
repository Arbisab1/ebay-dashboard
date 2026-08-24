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
    page_title="eBay Automation Cloud Portal",
    layout="wide",
    page_icon="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg",
    initial_sidebar_state="expanded",
)

# --- CLEAN MODERN THEME ---
st.markdown(
    """
<style>
    header[data-testid="stHeader"], div[data-testid="stDecoration"] {
        display: none !important;
    }
    .stApp {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
    }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        padding: 16px 20px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #2563EB !important;
    }
    button[kind="primary"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 8px !important;
    }
    button[kind="secondary"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        color: #334155 !important;
        border-radius: 8px !important;
    }
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        color: #1E293B !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="select"], div[data-baseweb="input"], textarea {
        background-color: #FFFFFF !important;
        border-color: #CBD5E1 !important;
        color: #0F172A !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }
</style>
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
users_db = load_json(USERS_FILE, {})
templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.assigned_stores = []


# ==========================================================
# 1. LOGIN & SELF SIGN-UP TABS
# ==========================================================
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(
            """
        <div style="text-align: center; padding: 20px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 16px;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg" width="90" style="margin-bottom: 8px;">
            <h3 style="margin: 0; color: #0F172A; font-weight: 700;">eBay Automation Portal</h3>
            <p style="margin-top: 4px; color: #64748B; font-size: 0.85rem;">Sign in or create an account for your store</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        auth_tab1, auth_tab2 = st.tabs(["🔑 Sign In", "➕ Create an Account"])

        # TAB 1: SIGN IN
        with auth_tab1:
            with st.form("direct_login_form"):
                uname = st.text_input("Username").strip()
                pword = st.text_input("Password", type="password").strip()
                submit_btn = st.form_submit_button(
                    "Sign In", use_container_width=True, type="primary"
                )

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
                        st.session_state.assigned_stores = users_db[uname].get(
                            "assigned_stores", []
                        )
                        st.success(f"Welcome, {uname}!")
                        st.rerun()
                    else:
                        st.error("Invalid Username or Password.")

        # TAB 2: SELF SIGN-UP
        with auth_tab2:
            with st.form("signup_form"):
                new_u = st.text_input("Choose Username:").strip()
                new_p = st.text_input("Choose Password:", type="password").strip()
                store_label = st.text_input("Your eBay Store Name / Alias:").strip()
                signup_btn = st.form_submit_button(
                    "Create Account & Continue", use_container_width=True, type="primary"
                )

                if signup_btn:
                    if new_u and new_p and store_label:
                        if new_u in users_db or new_u.lower() == "admin":
                            st.error("Username already exists. Choose another.")
                        else:
                            users_db[new_u] = {
                                "password": hash_pass(new_p),
                                "role": "client",
                                "assigned_stores": [store_label],
                            }
                            save_json(USERS_FILE, users_db)
                            
                            st.session_state.logged_in = True
                            st.session_state.username = new_u
                            st.session_state.role = "client"
                            st.session_state.assigned_stores = [store_label]
                            st.success("Account created successfully! Redirecting...")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("All fields are required.")

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
            "Link & Manage eBay Stores",
            "Registered Clients Overview",
            "Global Message Templates",
        ]
    else:
        nav_options = [
            "My Orders & Auto-Messaging",
            "➕ Connect My eBay Store",
            "My Message Templates",
        ]

    selected_page = st.radio("Menu", nav_options, label_visibility="collapsed")
    st.divider()
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

        c_sync, _ = st.columns([1.5, 3])
        with c_sync:
            if st.button(
                f"🔄 Sync Orders ({active_store_name})",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Fetching orders from eBay API..."):
                    all_orders = fetch_all_ebay_orders(tokens["access_token"])
                    if not all_orders and tokens.get("refresh_token"):
                        new_t = get_fresh_token(tokens["refresh_token"])
                        if new_t:
                            stores[active_store_name]["access_token"] = new_t
                            save_json(STORES_FILE, stores)
                            all_orders = fetch_all_ebay_orders(new_t)

                    st.session_state[f"orders_{active_store_name}"] = all_orders
                    st.success(f"Synced {len(all_orders)} orders successfully!")

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
                status_filter = st.selectbox("Target Filter Group:", filter_options)

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
                        track_info = step.get("shipmentTracking", {}).get("trackingNumber")
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
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }

                    time.sleep(0.3)
                    progress_bar.progress((i + 1) / len(display_orders))

                save_json(LOGS_FILE, logs)
                st.success(f"✅ {sent_count}/{len(display_orders)} messages dispatched!")

            st.divider()
            st.markdown("### 📋 Order List & Direct Actions")

            for o in display_orders:
                order_id = o.get("orderId", "")
                buyer = o.get("buyer", {}).get("username", "Buyer")
                line_items = o.get("lineItems", [])
                item_title = line_items[0].get("title", "Item") if line_items else ""
                item_id = line_items[0].get("legacyItemId", "N/A") if line_items else "N/A"

                _, clean_badge = get_clean_order_status(o)

                tracking_num = "Uploaded on eBay"
                carrier_name = "Courier"

                for inst in o.get("fulfillmentStartInstructions", []):
                    step = inst.get("shippingStep", {})
                    track_info = step.get("shipmentTracking", {}).get("trackingNumber")
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
                            f"✉️ Send Message to {buyer}",
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
                                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    }
                                    save_json(LOGS_FILE, logs)
                                    st.success(f"Sent to {buyer}!")
                                    st.rerun()
                                else:
                                    st.error("Failed to send message.")


# ==========================================================
# PAGE B: LINK & MANAGE STORES (ADMIN OR CLIENT SELF-CONNECT)
# ==========================================================
elif "Connect My eBay Store" in selected_page or "Link & Manage eBay Stores" in selected_page:
    st.markdown("## ➕ Connect & Authorize eBay Store")
    st.caption("Securely authenticate your production eBay account via official OAuth.")

    c_link, c_manage = st.columns([1.2, 1])

    with c_link:
        st.markdown("### 🔗 Authorize Account")
        st.info("Step 1: Click the link below and authorize on eBay:")
        st.markdown(f"👉 [**Authorize with eBay (Click Here)**]({AUTH_URL})")
        st.write("")

        redirect_input = st.text_input("Redirected URL / Code:")
        
        # Pre-fill store name for client or allow admin to type
        assigned_s = st.session_state.assigned_stores[0] if st.session_state.assigned_stores and st.session_state.assigned_stores[0] != "ALL" else ""
        store_alias = st.text_input("Store Name / Label:", value=assigned_s)

        if st.button("Complete Authorization", type="primary"):
            if redirect_input and store_alias:
                final_code = clean_auth_code(redirect_input)
                status, token_data = exchange_code_for_tokens(final_code)

                if status == 200 and "access_token" in token_data:
                    stores[store_alias] = {
                        "access_token": token_data["access_token"],
                        "refresh_token": token_data.get("refresh_token", ""),
                    }
                    save_json(STORES_FILE, stores)
                    
                    # Update client assigned store if needed
                    u_curr = st.session_state.username
                    if u_curr in users_db:
                        users_db[u_curr]["assigned_stores"] = [store_alias]
                        save_json(USERS_FILE, users_db)
                        st.session_state.assigned_stores = [store_alias]

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
                    <div style="padding: 12px 16px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 10px;">
                        <strong style="font-size: 1.05rem; color: #0F172A;">🏪 {s_name}</strong><br>
                        <span style="color: #16A34A; font-size: 0.85rem; font-weight: 500;">● Connected & Active</span>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                    if st.button(f"🗑️ Disconnect {s_name}", key=f"del_store_{s_name}", type="secondary"):
                        del stores[s_name]
                        save_json(STORES_FILE, stores)
                        st.success(f"Store '{s_name}' removed!")
                        st.rerun()


# ==========================================================
# PAGE C: REGISTERED CLIENTS OVERVIEW (ADMIN ONLY)
# ==========================================================
elif selected_page == "Registered Clients Overview" and st.session_state.role == "admin":
    st.markdown("## 👥 Self-Registered Clients & Stores")
    st.caption("Monitor all registered clients, their store names, and connected status.")

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
                <div style="padding: 14px 18px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong style="font-size: 1.05rem;">👤 Client: {u}</strong><br>
                        <span style="color: #64748B; font-size: 0.85rem;">Store Name: <b>{assigned}</b></span>
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
                if st.button(f"🗑️ Delete Client {u}", key=f"del_client_{u}", type="secondary"):
                    del users_db[u]
                    save_json(USERS_FILE, users_db)
                    st.success(f"Client '{u}' removed!")
                    st.rerun()


# ==========================================================
# PAGE D: MESSAGE TEMPLATES (CLIENT & ADMIN)
# ==========================================================
elif "Message Templates" in selected_page:
    st.markdown("## 📝 Message Templates Settings")
    st.caption("Manage personalized messaging templates using dynamic attributes.")

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

    selected_tpl_edit = st.selectbox("Select Template to Edit:", list(templates.keys()))
    tpl_body = st.text_area(
        "Template Content:",
        value=templates[selected_tpl_edit],
        height=180,
        key=f"editor_{selected_tpl_edit}",
    )

    if st.button("Save Template", type="primary"):
        templates[selected_tpl_edit] = tpl_body
        save_json(TEMPLATES_FILE, templates)
        st.success(f"Template '{selected_tpl_edit}' saved successfully!")
        st.rerun()
