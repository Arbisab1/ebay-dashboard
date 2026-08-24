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
    page_title="eBay Multi-Store Manager & Smart Bot",
    layout="wide",
    page_icon="⚡",
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


# --- DIRECT EBAY STATUS CHECK ---
def get_clean_order_status(o):
    # 1. Cancelled Check
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

    # 2. Check Line Items Delivery Status from eBay
    line_items = o.get("lineItems", [])
    plans = o.get("fulfillmentStartPlans", [])
    fulfillments = o.get("fulfillments", [])

    is_delivered_ebay = False
    has_tracking_ebay = False

    # Direct line items check
    for item in line_items:
        del_status = (
            item.get("deliveryInfo", {}).get("deliveryStatus", "").upper()
        )
        if del_status == "DELIVERED":
            is_delivered_ebay = True
        elif del_status in [
            "IN_TRANSIT",
            "OUT_FOR_DELIVERY",
            "SHIPPED",
            "DROPPED_OFF",
        ]:
            has_tracking_ebay = True

    # Direct fulfillments array check
    for f in fulfillments:
        if f.get("shipmentTrackingNumber") or f.get("trackingNumber"):
            has_tracking_ebay = True
        if f.get("deliveryStatus", "").upper() == "DELIVERED":
            is_delivered_ebay = True

    # Direct fulfillmentStartPlans check
    for plan in plans:
        ship_step = plan.get("shippingStep", {})
        if ship_step.get("shipmentTracking"):
            has_tracking_ebay = True
        if ship_step.get("actualDeliveryDate"):
            is_delivered_ebay = True

    # Order level fulfillment status check
    f_status = o.get("orderFulfillmentStatus", "NOT_STARTED")

    if is_delivered_ebay:
        return "DELIVERED", "📦 Delivered"
    elif has_tracking_ebay or f_status == "FULFILLED":
        return "SHIPPED", "🚚 Shipped"
    else:
        return "NEW", "🆕 New Order"


# --- DASHBOARD HEADER ---
st.title("⚡ eBay Multi-Store Manager & Smart Bot")

# --- SIDEBAR ---
stores = load_json(STORES_FILE, {})

with st.sidebar:
    st.header("➕ Link eBay Account")
    st.markdown(f"[🔗 **Link eBay Store**]({AUTH_URL})")
    st.caption("Authorization URL paste karein:")
    redirect_input = st.text_input("Redirected URL / Code:")
    store_alias = st.text_input("Store Name:")

    if st.button("Save Store"):
        if redirect_input and store_alias:
            final_code = clean_auth_code(redirect_input)
            status, token_data = exchange_code_for_tokens(final_code)

            if status == 200 and "access_token" in token_data:
                stores[store_alias] = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token", ""),
                }
                save_json(STORES_FILE, stores)
                st.success(f"Store '{store_alias}' Linked!")
                st.rerun()
            else:
                st.error("Authentication Failed.")
        else:
            st.warning("All fields are required.")

    if stores:
        st.divider()
        st.header("🗑️ Unlink / Delete Store")
        store_to_remove = st.selectbox(
            "Select Store to Delete:", list(stores.keys()), key="store_to_del"
        )
        if st.button(
            f"❌ Delete {store_to_remove}", type="secondary", key="del_btn"
        ):
            del stores[store_to_remove]
            save_json(STORES_FILE, stores)
            st.success(f"Store '{store_to_remove}' has been removed!")
            st.rerun()

templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if not stores:
    st.info(
        "Filhal koi store link nahi hai. Sidebar say apna store connect karein."
    )
else:
    main_tabs = st.tabs(["🏬 Orders & Smart Filters", "📝 Customize Templates"])

    # --- TAB 2: TEMPLATES MANAGER ---
    with main_tabs[1]:
        st.subheader("📝 Customize Message Templates")
        selected_tpl_edit = st.selectbox(
            "Select Template to Edit:",
            list(templates.keys()),
            key="tpl_edit_select",
        )
        tpl_body = st.text_area(
            "Template Content:",
            value=templates[selected_tpl_edit],
            height=150,
            key=f"editor_{selected_tpl_edit}",
        )
        if st.button("💾 Save Template"):
            templates[selected_tpl_edit] = tpl_body
            save_json(TEMPLATES_FILE, templates)
            st.success("Template Saved Successfully!")
            st.rerun()

    # --- TAB 1: STORE ORDERS & SMART MESSAGING ---
    with main_tabs[0]:
        store_tabs = st.tabs(list(stores.keys()))

        for idx, (name, tokens) in enumerate(stores.items()):
            with store_tabs[idx]:
                col_title, col_del = st.columns([3, 1])
                with col_title:
                    st.subheader(f"🏪 Active Store: {name}")
                with col_del:
                    if st.button(
                        f"🗑️ Remove {name}",
                        key=f"del_tab_{name}",
                        help="Unlink this store",
                    ):
                        del stores[name]
                        save_json(STORES_FILE, stores)
                        st.success(f"Store '{name}' unlinked!")
                        st.rerun()

                if st.button(
                    f"🔄 Sync ALL Orders from eBay ({name})",
                    key=f"sync_all_{name}",
                ):
                    with st.spinner("Fetching orders from eBay..."):
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
                        st.success(f"Loaded {len(all_orders)} Orders!")

                orders = st.session_state.get(f"orders_{name}", [])

                if orders:
                    st.divider()
                    st.markdown("### 🎯 Order Filter & Smart Auto-Template")

                    col_filter, col_template = st.columns([2, 2])

                    filter_options = [
                        "🆕 Brand New Orders (Unfulfilled)",
                        "🚚 Shipped Orders",
                        "📦 Delivered Orders",
                        "❌ Cancelled Orders",
                        "📋 All Orders",
                    ]
                    with col_filter:
                        status_filter = st.selectbox(
                            "Select Target Order Status:",
                            filter_options,
                            key=f"filter_{name}",
                        )

                    # Auto Select Matching Template
                    target_tpl_name = "Brand New Order Welcome"
                    if "Shipped" in status_filter:
                        target_tpl_name = "Shipped Notification"
                    elif "Delivered" in status_filter:
                        target_tpl_name = "Delivered Feedback"
                    elif "Cancelled" in status_filter:
                        target_tpl_name = "Order Cancellation Notice"

                    default_tpl_index = get_template_index(
                        templates, target_tpl_name
                    )

                    with col_template:
                        chosen_template = st.selectbox(
                            "Select Message Template:",
                            list(templates.keys()),
                            index=default_tpl_index,
                            key=f"tpl_select_{name}",
                        )

                    # Strict Separation Filter Logic directly mapped to eBay status
                    display_orders = []
                    for o in orders:
                        order_type, _ = get_clean_order_status(o)

                        if status_filter == "📋 All Orders":
                            display_orders.append(o)
                        elif status_filter == "❌ Cancelled Orders":
                            if order_type == "CANCELLED":
                                display_orders.append(o)
                        elif (
                            status_filter
                            == "🆕 Brand New Orders (Unfulfilled)"
                        ):
                            if order_type == "NEW":
                                display_orders.append(o)
                        elif status_filter == "🚚 Shipped Orders":
                            if order_type == "SHIPPED":
                                display_orders.append(o)
                        elif status_filter == "📦 Delivered Orders":
                            if order_type == "DELIVERED":
                                display_orders.append(o)

                    st.info(
                        f"📊 Selected: **`{status_filter}`** | Template: **`{chosen_template}`** | Orders Found: **{len(display_orders)}**"
                    )

                    if st.button(
                        f"🚀 Send '{chosen_template}' to All ({len(display_orders)}) Orders",
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

                            # Extract tracking details
                            tracking_num = "Uploaded on eBay"
                            carrier_name = "Standard Courier"
                            fulfillments = o.get("fulfillments", [])
                            if fulfillments:
                                tracking_num = (
                                    fulfillments[0].get(
                                        "shipmentTrackingNumber"
                                    )
                                    or tracking_num
                                )
                                carrier_name = (
                                    fulfillments[0].get("shippingCarrierCode")
                                    or carrier_name
                                )
                            else:
                                plans = o.get("fulfillmentStartPlans", [])
                                if plans:
                                    step = plans[0].get("shippingStep", {})
                                    tracking_num = step.get(
                                        "shipmentTracking", {}
                                    ).get("trackingNumber", tracking_num)
                                    carrier_name = step.get(
                                        "shippingCarrierCode", carrier_name
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
                            f"✅ {sent_count}/{len(display_orders)} messages dispatched!"
                        )

                    st.divider()
                    st.markdown("### 📦 Orders Preview & Individual Control")

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

                        _, clean_badge = get_clean_order_status(o)

                        # Extract tracking for preview
                        tracking_num = "Uploaded on eBay"
                        carrier_name = "Courier"
                        fulfillments = o.get("fulfillments", [])
                        if fulfillments:
                            tracking_num = (
                                fulfillments[0].get("shipmentTrackingNumber")
                                or tracking_num
                            )
                            carrier_name = (
                                fulfillments[0].get("shippingCarrierCode")
                                or carrier_name
                            )
                        else:
                            plans = o.get("fulfillmentStartPlans", [])
                            if plans:
                                step = plans[0].get("shippingStep", {})
                                tracking_num = step.get(
                                    "shipmentTracking", {}
                                ).get("trackingNumber", tracking_num)
                                carrier_name = step.get(
                                    "shippingCarrierCode", carrier_name
                                )

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
                            st.write(f"**Item:** {item_title}")
                            st.write(f"**Item ID:** `{item_id}`")

                            user_msg_input = st.text_area(
                                f"Message Preview ({chosen_template}):",
                                value=formatted_preview,
                                height=120,
                                key=f"input_{order_id}_{chosen_template}_{status_filter}",
                            )

                            if st.button(
                                f"✉️ Send to {buyer}",
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
