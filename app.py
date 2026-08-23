import base64
from datetime import datetime
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
TEMPLATES_FILE = "custom_templates.json"
LOGS_FILE = "message_logs.json"

AUTH_URL = (
    f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={RUNAME}&"
    "scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.fulfillment%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.message"
)

st.set_page_config(
    page_title="eBay All Orders Sync & Multi-Filter Bot",
    layout="wide",
    page_icon="📦",
)

# --- DEFAULT TEMPLATES ---
DEFAULT_TEMPLATES = {
    "Shipped Notification": (
        "Hi {buyer},\n\n"
        "Your Order #{order_id} has been dispatched via {carrier}!\n"
        "Tracking Number: {tracking_number}\n\n"
        "Thank you for shopping with us!"
    ),
    "Delivered Feedback": (
        "Hi {buyer},\n\n"
        "Your Order #{order_id} has been marked as delivered! "
        "If you are satisfied with the purchase, we would appreciate your positive feedback.\n\n"
        "Best regards!"
    ),
    "New Order Processing": (
        "Hi {buyer},\n\n"
        "Thanks for ordering (Order #{order_id})! "
        "We are getting your package prepared for shipment.\n\n"
        "Thank you!"
    ),
}


# --- PERSISTENCE HELPERS ---
def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)


# --- AUTH HELPERS ---
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


# --- FETCH ALL UNLIMITED ORDERS (AUTO PAGINATED) ---
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


# --- SEND MESSAGE VIA XML API ---
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


# --- DASHBOARD HEADER ---
st.title("📦 eBay Multi-Store All Orders & Status Filter Engine")

# --- SIDEBAR ---
with st.sidebar:
    st.header("➕ Connect eBay Account")
    st.markdown(f"[🔗 **Link eBay Store**]({AUTH_URL})")
    st.caption("Authorization URL paste karein:")
    redirect_input = st.text_input("Redirected URL / Code:")
    store_alias = st.text_input("Store Name (e.g. Account 1):")

    if st.button("Save Store"):
        if redirect_input and store_alias:
            final_code = clean_auth_code(redirect_input)
            status, token_data = exchange_code_for_tokens(final_code)

            if status == 200 and "access_token" in token_data:
                stores = load_json(STORES_FILE, {})
                stores[store_alias] = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token", ""),
                }
                save_json(STORES_FILE, stores)
                st.success(f"Store '{store_alias}' Connected!")
                st.rerun()
            else:
                st.error("Authentication Failed.")

stores = load_json(STORES_FILE, {})
templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if not stores:
    st.info("Sidebar say apna eBay account connect karein.")
else:
    main_tabs = st.tabs(["🏬 Store Channels & Filter", "📝 Customize Templates"])

    # --- TAB 2: TEMPLATES ---
    with main_tabs[1]:
        st.subheader("📝 Customize Templates")
        selected_tpl = st.selectbox(
            "Select Template:", list(templates.keys()), key="tpl_edit_select"
        )
        tpl_body = st.text_area(
            "Template Text (use {buyer}, {order_id}, {tracking_number}, {carrier}):",
            value=templates[selected_tpl],
            height=150,
        )
        if st.button("💾 Save Template"):
            templates[selected_tpl] = tpl_body
            save_json(TEMPLATES_FILE, templates)
            st.success("Template Saved!")

    # --- TAB 1: ALL ORDERS & STATUS FILTERING ---
    with main_tabs[0]:
        store_tabs = st.tabs(list(stores.keys()))

        for idx, (name, tokens) in enumerate(stores.items()):
            with store_tabs[idx]:
                st.subheader(f"🏪 Active Store: {name}")

                # Button to sync EVERYTHING
                if st.button(
                    f"🔄 Sync ALL Orders from eBay ({name})",
                    key=f"sync_all_{name}",
                ):
                    with st.spinner("Syncing entire store order history..."):
                        all_orders = fetch_all_ebay_orders(
                            tokens["access_token"]
                        )
                        if not all_orders and tokens.get("refresh_token"):
                            new_t = get_fresh_token(tokens["refresh_token"])
                            if new_t:
                                stores[name]["access_token"] = new_t
                                save_json(STORES_FILE, stores)
                                all_orders = fetch_all_ebay_orders(new_t)

                        st.session_state[f"orders_{name}"] = all_orders
                        st.success(
                            f"Total {len(all_orders)} Orders fetched from eBay!"
                        )

                orders = st.session_state.get(f"orders_{name}", [])

                if orders:
                    st.divider()
                    st.markdown("### 🔍 Live Order Filter")

                    col_filter, col_template = st.columns([2, 2])

                    with col_filter:
                        status_filter = st.selectbox(
                            "Select Order Status to Display:",
                            [
                                "All Orders",
                                "Shipped (Dispatched / With Tracking)",
                                "Delivered Orders",
                                "Processing / Unfulfilled (New Orders)",
                            ],
                            key=f"filter_{name}",
                        )

                    with col_template:
                        chosen_template = st.selectbox(
                            "Choose Message Template:",
                            list(templates.keys()),
                            key=f"tpl_pick_{name}",
                        )

                    # Dynamic Filter Logic
                    display_orders = []
                    for o in orders:
                        f_status = o.get(
                            "orderFulfillmentStatus", "NOT_STARTED"
                        )
                        plans = o.get("fulfillmentStartPlans", [])
                        has_tracking = any(
                            p.get("shippingStep", {}).get("shipmentTracking")
                            for p in plans
                        )

                        if status_filter == "All Orders":
                            display_orders.append(o)
                        elif status_filter == "Shipped (Dispatched / With Tracking)":
                            if f_status == "FULFILLED" or has_tracking:
                                display_orders.append(o)
                        elif status_filter == "Delivered Orders":
                            if f_status == "FULFILLED":
                                display_orders.append(o)
                        elif (
                            status_filter
                            == "Processing / Unfulfilled (New Orders)"
                        ):
                            if f_status in ["NOT_STARTED", "IN_PROGRESS"]:
                                display_orders.append(o)

                    st.info(
                        f"Showing **{len(display_orders)}** orders matching `{status_filter}` (out of {len(orders)} total orders)."
                    )

                    # Bulk Action on Filtered View
                    if st.button(
                        f"🚀 Send Message to All ({len(display_orders)}) Filtered Orders",
                        key=f"bulk_send_{name}",
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

                            # Extract Tracking
                            tracking_num = "Uploaded on eBay"
                            carrier_name = "Standard Courier"
                            fulfill_plans = o.get("fulfillmentStartPlans", [])
                            if fulfill_plans:
                                track_step = fulfill_plans[0].get(
                                    "shippingStep", {}
                                )
                                tracking_num = track_step.get(
                                    "shipmentTracking", {}
                                ).get("trackingNumber", "Uploaded on eBay")
                                carrier_name = track_step.get(
                                    "shippingCarrierCode", "Standard Courier"
                                )

                            msg_body = templates[chosen_template].format(
                                buyer=buyer,
                                order_id=order_id,
                                tracking_number=tracking_num,
                                carrier=carrier_name,
                            )

                            if item_id:
                                success = send_ebay_message(
                                    tokens["access_token"],
                                    item_id,
                                    buyer,
                                    msg_body,
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
                            progress_bar.progress(
                                (i + 1) / len(display_orders)
                            )

                        save_json(LOGS_FILE, logs)
                        st.success(
                            f"✅ {sent_count}/{len(display_orders)} customer messages sent successfully!"
                        )

                    # List / Table View of Filtered Orders
                    st.divider()
                    st.markdown("### 📋 Filtered Orders List")

                    for o in display_orders:
                        order_id = o.get("orderId", "")
                        buyer = o.get("buyer", {}).get("username", "Buyer")
                        line_items = o.get("lineItems", [])
                        item_title = (
                            line_items[0].get("title", "Item")
                            if line_items
                            else ""
                        )
                        item_id = (
                            line_items[0].get("legacyItemId", "N/A")
                            if line_items
                            else "N/A"
                        )
                        f_stat = o.get("orderFulfillmentStatus", "NOT_STARTED")
                        is_logged = f"{order_id}_{chosen_template}" in logs

                        with st.expander(
                            f"Order #{order_id} | {buyer} | Status: {f_stat} | {'✅ Sent' if is_logged else '⏳ Ready'}"
                        ):
                            st.write(f"**Item:** {item_title}")
                            st.write(f"**Item ID:** `{item_id}`")

                            single_msg = templates[chosen_template].format(
                                buyer=buyer,
                                order_id=order_id,
                                tracking_number="Uploaded on eBay",
                                carrier="Courier",
                            )

                            custom_txt = st.text_area(
                                "Message Content:",
                                value=single_msg,
                                key=f"txt_{order_id}_{name}",
                            )

                            if st.button(
                                f"✉️ Send to {buyer}",
                                key=f"btn_single_{order_id}",
                            ):
                                if item_id != "N/A":
                                    success = send_ebay_message(
                                        tokens["access_token"],
                                        item_id,
                                        buyer,
                                        custom_txt,
                                    )
                                    if success:
                                        logs[
                                            f"{order_id}_{chosen_template}"
                                        ] = {
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
