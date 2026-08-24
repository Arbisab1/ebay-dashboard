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
    page_title="eBay Automation SaaS Portal",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded",
)

# --- MODERN SAAS CSS STYLING ---
st.markdown(
    """
<style>
    /* Metric Cards */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1E88E5;
    }
    div[data-testid="stMetric"] {
        background-color: rgba(30, 136, 229, 0.05);
        border: 1px solid rgba(30, 136, 229, 0.2);
        padding: 12px 18px;
        border-radius: 10px;
    }
    /* Expander Card Styling */
    .streamlit-expanderHeader {
        font-size: 1.05rem;
        font-weight: 600;
        border-radius: 8px;
    }
    /* Buttons */
    button[kind="primary"] {
        background: linear-gradient(90deg, #1E88E5, #1565C0);
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    /* Sidebar Navigation styling */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(255, 255, 255, 0.08);
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
users_db = load_json(USERS_FILE, DEFAULT_USERS)
templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.assigned_stores = []


# ==========================================================
# 1. LOGIN SCREEN
# ==========================================================
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1.8, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            """
        <div style="text-align: center; padding: 20px; background-color: rgba(30, 136, 229, 0.05); border: 1px solid rgba(30, 136, 229, 0.2); border-radius: 14px; margin-bottom: 20px;">
            <h2 style="margin: 0; color: #1E88E5;">⚡ eBay Automation Suite</h2>
            <p style="margin-top: 6px; color: gray; font-size: 0.95rem;">Multi-Tenant Order & Messaging Management Portal</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            uname = st.text_input("👤 Username")
            pword = st.text_input("🔑 Password", type="password")
            submit_btn = st.form_submit_button(
                "🚀 Sign In to Dashboard",
                use_container_width=True,
                type="primary",
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
                    st.success(f"Welcome back, {uname}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials provided.")
    st.stop()


# ==========================================================
# 2. LOGGED IN SAAS DASHBOARD WITH SIDEBAR NAVIGATION
# ==========================================================

# Determine user's stores
if st.session_state.role == "admin":
    accessible_stores = stores
else:
    accessible_stores = {
        k: v
        for k, v in stores.items()
        if k in st.session_state.assigned_stores
    }

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown("### ⚡ **eBay Automation Hub**")
    st.markdown(
        f"👤 User: **`{st.session_state.username}`** | Role: `{st.session_state.role.upper()}`"
    )

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.assigned_stores = []
        st.rerun()

    st.divider()
    st.markdown("### 📌 **Navigation Menu**")

    nav_options = [
        "📊 Orders & Messaging Hub",
        "➕ Connect & Manage Stores",
        "📝 Template Customizer",
    ]
    if st.session_state.role == "admin":
        nav_options.append("👥 User & Access Control")

    selected_page = st.radio("Go to Page:", nav_options, label_visibility="collapsed")
    st.divider()
    st.caption("🔒 End-to-End Encrypted eBay OAuth Engine")


# ==========================================================
# PAGE 1: ORDERS & MESSAGING HUB (MAIN WORKSPACE)
# ==========================================================
if selected_page == "📊 Orders & Messaging Hub":
    st.title("📊 Orders & Auto-Messaging Hub")
    st.caption("Select a store, sync real-time orders, and dispatch targeted personalized messages.")

    if not accessible_stores:
        st.warning(
            "⚠️ No stores are currently linked or assigned to your account. Go to **'Connect & Manage Stores'** to link one."
        )
    else:
        # Store Switcher
        active_store_name = st.selectbox(
            "🏬 Select Store Channel:", list(accessible_stores.keys())
        )
        tokens = accessible_stores[active_store_name]

        # Top Control Bar
        c_sync, c_spacer = st.columns([1.5, 3])
        with c_sync:
            if st.button(
                f"🔄 Sync Live Orders ({active_store_name})",
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
                    st.success(f"Successfully loaded {len(all_orders)} orders!")

        orders = st.session_state.get(f"orders_{active_store_name}", [])

        if orders:
            st.divider()

            # Filter and Template Controls
            col_filter, col_template = st.columns([2, 2])

            filter_options = [
                "🆕 Brand New Orders (Unfulfilled)",
                "🚚 Shipped Orders (In-Transit)",
                "📦 Delivered Orders",
                "❌ Cancelled Orders",
                "📋 All Orders",
            ]
            with col_filter:
                status_filter = st.selectbox("🎯 Target Filter Group:", filter_options)

            # Auto Select Matching Template
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
                    "💬 Active Message Template:",
                    list(templates.keys()),
                    index=default_tpl_index,
                )

            # Strict Separation Filter Logic
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

            # Quick Metric Banner
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Synced Orders", len(orders))
            m2.metric("Filtered Matches", len(display_orders))
            m3.metric("Selected Template", chosen_template)

            st.write("")

            # Bulk Send Button
            if st.button(
                f"🚀 Send '{chosen_template}' to All ({len(display_orders)}) Matched Customers",
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
                    f"✅ {sent_count}/{len(display_orders)} messages successfully dispatched!"
                )

            # Orders List
            st.divider()
            st.markdown("### 📋 Order Feed & Message Customizer")

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
                    f"Order #{order_id} | 👤 Buyer: {buyer} | {clean_badge} | {'✅ Sent' if is_sent else '⏳ Ready'}"
                ):
                    c_det, c_act = st.columns([1.5, 2])
                    with c_det:
                        st.write(f"**Item:** {item_title}")
                        st.write(f"**Item ID:** `{item_id}`")
                        st.write(f"**Carrier:** `{carrier_name}`")
                        st.write(f"**Tracking:** `{tracking_num}`")

                    with c_act:
                        user_msg_input = st.text_area(
                            f"Live Preview ({chosen_template}):",
                            value=formatted_preview,
                            height=110,
                            key=f"input_{order_id}_{chosen_template}_{status_filter}",
                        )

                        if st.button(
                            f"✉️ Send Message to {buyer}",
                            key=f"btn_send_{order_id}_{chosen_template}",
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
                                    st.error("Failed to send message.")


# ==========================================================
# PAGE 2: CONNECT & MANAGE STORES (DEDICATED PAGE)
# ==========================================================
elif selected_page == "➕ Connect & Manage Stores":
    st.title("➕ Connect & Manage eBay Stores")
    st.caption("Link new eBay production accounts via secure OAuth or remove existing connections.")

    c_link, c_manage = st.columns([1.2, 1])

    with c_link:
        st.markdown("### 🔗 Link New Account")
        st.info("Step 1: Click the authorization link below and sign in to eBay.")
        st.markdown(f"👉 [**Authorize with eBay (Click Here)**]({AUTH_URL})")
        st.write("")

        st.info("Step 2: Copy the redirected browser URL and paste it below:")
        redirect_input = st.text_input("Redirected URL / Authorization Code:")
        store_alias = st.text_input("Store Name / Label (e.g. MyStore UK):")

        if st.button("🔗 Complete Store Connection", type="primary"):
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
                    st.error("Authentication failed. Please check the URL/code and try again.")
            else:
                st.warning("All fields are mandatory.")

    with c_manage:
        st.markdown("### 🏬 Connected Stores")
        if not accessible_stores:
            st.info("No stores linked yet.")
        else:
            for s_name in list(accessible_stores.keys()):
                with st.container():
                    st.markdown(
                        f"""
                    <div style="padding: 12px 16px; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong style="font-size: 1.1rem;">🏪 {s_name}</strong><br>
                            <span style="color: #4CAF50; font-size: 0.85rem;">● Connected & Active</span>
                        </div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        f"🗑️ Delete / Unlink {s_name}", key=f"del_store_page_{s_name}"
                    ):
                        del stores[s_name]
                        save_json(STORES_FILE, stores)
                        st.success(f"Store '{s_name}' removed!")
                        st.rerun()


# ==========================================================
# PAGE 3: TEMPLATE CUSTOMIZER
# ==========================================================
elif selected_page == "📝 Template Customizer":
    st.title("📝 Message Templates & Variables")
    st.caption("Design dynamic automated messages using personalized tags.")

    st.markdown(
        """
    **Available Dynamic Tags:**
    * `{buyer}`: Automatically replaced with the customer's username.
    * `{order_id}`: Automatically replaced with the eBay order ID.
    * `{carrier}`: Automatically replaced with the shipping provider name.
    * `{tracking_number}`: Automatically replaced with the parcel tracking number.
    """
    )
    st.divider()

    selected_tpl_edit = st.selectbox(
        "Choose Template to Edit:", list(templates.keys())
    )
    tpl_body = st.text_area(
        "Template Content:",
        value=templates[selected_tpl_edit],
        height=180,
        key=f"editor_{selected_tpl_edit}",
    )

    if st.button("💾 Save Template Changes", type="primary"):
        templates[selected_tpl_edit] = tpl_body
        save_json(TEMPLATES_FILE, templates)
        st.success(f"Template '{selected_tpl_edit}' updated successfully!")
        st.rerun()


# ==========================================================
# PAGE 4: USER & ACCESS CONTROL (ADMIN ONLY)
# ==========================================================
elif (
    selected_page == "👥 User & Access Control"
    and st.session_state.role == "admin"
):
    st.title("👥 User & Client Access Management")
    st.caption("Create dedicated client logins and assign specific store access.")

    c_u1, c_u2 = st.columns([1.2, 1])

    with c_u1:
        st.markdown("### ➕ Create Client Login")
        new_uname = st.text_input("New Client Username:")
        new_pword = st.text_input("New Client Password:", type="password")
        store_choices = list(stores.keys())
        assigned_store = st.selectbox(
            "Assign Store to this Account:",
            store_choices if store_choices else ["No stores connected"],
        )

        if st.button("Create Client Account", type="primary"):
            if (
                new_uname
                and new_pword
                and assigned_store != "No stores connected"
            ):
                if new_uname in users_db:
                    st.error("Username already exists!")
                else:
                    users_db[new_uname] = {
                        "password": hash_pass(new_pword),
                        "role": "client",
                        "assigned_stores": [assigned_store],
                    }
                    save_json(USERS_FILE, users_db)
                    st.success(
                        f"Account created for '{new_uname}' with access to '{assigned_store}'!"
                    )
                    st.rerun()
            else:
                st.warning("Please fill all fields properly.")

    with c_u2:
        st.markdown("### 📋 Active User Accounts")
        for u, data in users_db.items():
            with st.container():
                st.markdown(
                    f"""
                <div style="padding: 10px 14px; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; margin-bottom: 8px;">
                    <strong>👤 {u}</strong> ({data['role'].upper()})<br>
                    <small style="color: gray;">Assigned: {data.get('assigned_stores')}</small>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                if u != "admin":
                    if st.button(f"🗑️ Delete User {u}", key=f"del_user_{u}"):
                        del users_db[u]
                        save_json(USERS_FILE, users_db)
                        st.success(f"User {u} removed!")
                        st.rerun()
