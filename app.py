import base64
from datetime import datetime
import json
import os
from urllib.parse import parse_qs, unquote, urlparse
import requests
import streamlit as st

# --- SECRETS & CONFIGURATION ---
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
    page_title="eBay Multi-Store Automation & Smart Messaging Engine",
    layout="wide",
    page_icon="⚡",
)

# --- DEFAULT TEMPLATES ---
DEFAULT_TEMPLATES = {
    "New Order Confirmation": (
        "Hi {buyer},\n\n"
        "Thank you for your purchase (Order ID: {order_id})! "
        "We are getting your item packed and will dispatch it shortly.\n\n"
        "Best regards,\nCustomer Support"
    ),
    "Shipped (With Tracking)": (
        "Hi {buyer},\n\n"
        "Great news! Your Order #{order_id} has been dispatched via {carrier}.\n"
        "Your Tracking Number: {tracking_number}\n\n"
        "Thank you for shopping with us!"
    ),
    "Delivered / Feedback Request": (
        "Hi {buyer},\n\n"
        "Your package for Order #{order_id} should now be delivered! "
        "We hope you loved the product. If you have a moment, please leave us positive feedback on eBay.\n\n"
        "Best regards!"
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


# --- EBAY API CALLS ---
def fetch_orders(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    res = requests.get(
        "https://api.ebay.com/sell/fulfillment/v1/order?limit=50",
        headers=headers,
    )
    if res.status_code == 200:
        return res.json().get("orders", [])
    return []


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
st.title("⚡ eBay Smart Automation & Rules Engine")

# --- SIDEBAR: CONNECT STORE ---
with st.sidebar:
    st.header("➕ Link New eBay Store")
    st.markdown(f"[🔗 **Click to Connect eBay Store**]({AUTH_URL})")
    st.caption("Authorization kay baad browser URL paste karein:")
    redirect_input = st.text_input("Redirected URL / Code:")
    store_alias = st.text_input("Store Name (e.g. Store 1):")

    if st.button("Save & Link Store"):
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
                st.success(f"Store '{store_alias}' linked!")
                st.rerun()
            else:
                err_msg = token_data.get(
                    "error_description",
                    token_data.get("error", "Unknown error"),
                )
                st.error(f"Failed: {err_msg}")
        else:
            st.warning("All fields are required.")

stores = load_json(STORES_FILE, {})
templates = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
logs = load_json(LOGS_FILE, {})

if not stores:
    st.info("Filhal koi store link nahi hai. Sidebar say store connect karein.")
else:
    # Top Tab Navigation: Stores vs Global Template Manager
    main_tabs = st.tabs(["🏬 Store Channels", "📝 Customize Templates"])

    # ---------------- TAB 2: TEMPLATES MANAGER ----------------
    with main_tabs[1]:
        st.subheader("📝 Customize & Create Message Templates")
        st.write(
            "Use variables: `{buyer}`, `{order_id}`, `{tracking_number}`, `{carrier}`"
        )

        selected_tpl_name = st.selectbox(
            "Select Template to Edit:", list(templates.keys())
        )
        tpl_content = st.text_area(
            "Template Body:",
            value=templates.get(selected_tpl_name, ""),
            height=160,
        )

        col_t1, col_t2 = st.columns([1, 4])
        with col_t1:
            if st.button("💾 Save Template"):
                templates[selected_tpl_name] = tpl_content
                save_json(TEMPLATES_FILE, templates)
                st.success(f"'{selected_tpl_name}' saved!")

        st.divider()
        st.write("**Create New Custom Template:**")
        new_tpl_name = st.text_input("New Template Name:")
        new_tpl_body = st.text_area(
            "New Template Content:", height=100, key="new_tpl_body"
        )
        if st.button("➕ Add Template"):
            if new_tpl_name and new_tpl_body:
                templates[new_tpl_name] = new_tpl_body
                save_json(TEMPLATES_FILE, templates)
                st.success("New template added!")
                st.rerun()

    # ---------------- TAB 1: STORE CHANNELS & RULES ----------------
    with main_tabs[0]:
        store_tabs = st.tabs(list(stores.keys()))

        for idx, (name, tokens) in enumerate(stores.items()):
            with store_tabs[idx]:
                st.subheader(f"🏪 Channel: {name}")

                # Sync Orders
                if st.button(
                    f"🔄 Fetch Latest Orders ({name})", key=f"sync_{name}"
                ):
                    orders = fetch_orders(tokens["access_token"])
                    st.session_state[f"orders_{name}"] = orders
                    st.success(f"{len(orders)} Orders Loaded!")

                orders = st.session_state.get(f"orders_{name}", [])

                if orders:
                    st.divider()
                    st.markdown("### 🎯 Automation Filter & Targeted Trigger")

                    col_filter, col_template = st.columns([2, 2])

                    with col_filter:
                        filter_rule = st.selectbox(
                            "Select Target Customer Group:",
                            [
                                "All Orders",
                                "Only Shipped / Dispatched (With Tracking)",
                                "Only Unfulfilled / Processing (New Orders)",
                                "Only Delivered Orders",
                            ],
                            key=f"rule_{name}",
                        )

                    with col_template:
                        active_template_key = st.selectbox(
                            "Choose Template to Send:",
                            list(templates.keys()),
                            key=f"active_tpl_{name}",
                        )

                    # Filter Orders Based on Rule
                    filtered_orders = []
                    for o in orders:
                        fulfill_status = o.get(
                            "orderFulfillmentStatus", "NOT_STARTED"
                        )
                        shipment_info = o.get("fulfillmentStartPlans", [])
                        has_tracking = any(
                            plan.get("shippingStep", {}).get("shipmentTracking")
                            for plan in shipment_info
                        )

                        if filter_rule == "All Orders":
                            filtered_orders.append(o)
                        elif (
                            filter_rule
                            == "Only Shipped / Dispatched (With Tracking)"
                            and (fulfill_status == "FULFILLED" or has_tracking)
                        ):
                            filtered_orders.append(o)
                        elif (
                            filter_rule
                            == "Only Unfulfilled / Processing (New Orders)"
                            and fulfill_status in ["NOT_STARTED", "IN_PROGRESS"]
                        ):
                            filtered_orders.append(o)
                        elif (
                            filter_rule == "Only Delivered Orders"
                            and fulfill_status == "FULFILLED"
                        ):
                            filtered_orders.append(o)

                    st.info(
                        f"📊 **{len(filtered_orders)}** out of {len(orders)} orders matched the filter: `{filter_rule}`"
                    )

                    # Bulk Trigger
                    if st.button(
                        f"🚀 Trigger Automation for ({len(filtered_orders)}) Matched Customers",
                        key=f"trigger_{name}",
                    ):
                        sent_count = 0
                        chosen_template = templates[active_template_key]

                        for o in filtered_orders:
                            order_id = o.get("orderId", "")
                            buyer = o.get("buyer", {}).get("username", "")
                            line_items = o.get("lineItems", [])
                            item_id = (
                                line_items[0].get("legacyItemId")
                                if line_items
                                else None
                            )

                            # Extract Tracking
                            tracking_num = "Pending"
                            carrier_name = "Courier"
                            fulfill_plans = o.get("fulfillmentStartPlans", [])
                            if fulfill_plans:
                                track_step = fulfill_plans[0].get(
                                    "shippingStep", {}
                                )
                                tracking_num = track_step.get(
                                    "shipmentTracking", {}
                                ).get("trackingNumber", "Uploaded on eBay")
                                carrier_name = track_step.get(
                                    "shippingCarrierCode", "Shipping Partner"
                                )

                            msg_body = chosen_template.format(
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
                                    logs[f"{order_id}_{active_template_key}"] = {
                                        "buyer": buyer,
                                        "status": "Sent",
                                        "time": datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                        "template": active_template_key,
                                    }

                        save_json(LOGS_FILE, logs)
                        st.success(
                            f"✅ {sent_count}/{len(filtered_orders)} messages successfully dispatched!"
                        )

                    st.divider()
                    st.markdown("### 📦 Matched Customer List & Direct Preview")

                    for o in filtered_orders:
                        order_id = o.get("orderId", "")
                        buyer = o.get("buyer", {}).get("username", "Unknown")
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
                        f_status = o.get(
                            "orderFulfillmentStatus", "NOT_STARTED"
                        )

                        log_key = f"{order_id}_{active_template_key}"
                        is_sent = log_key in logs

                        with st.expander(
                            f"Order #{order_id} | Buyer: {buyer} | Fulfillment: {f_status} | Status: {'✅ Sent' if is_sent else '⏳ Ready'}"
                        ):
                            st.write(f"**Product:** {item_title}")
                            st.write(f"**Item ID:** `{item_id}`")

                            # Live Preview Box
                            preview_text = templates[
                                active_template_key
                            ].format(
                                buyer=buyer,
                                order_id=order_id,
                                tracking_number="TRACK12345",
                                carrier="USPS / Royal Mail",
                            )
                            custom_txt = st.text_area(
                                "Live Message Preview / Edit for this Customer:",
                                value=preview_text,
                                key=f"prev_{order_id}_{name}",
                            )

                            if st.button(
                                f"✉️ Send Directly to {buyer}",
                                key=f"single_send_{order_id}",
                            ):
                                if item_id != "N/A":
                                    success = send_ebay_message(
                                        tokens["access_token"],
                                        item_id,
                                        buyer,
                                        custom_txt,
                                    )
                                    if success:
                                        logs[log_key] = {
                                            "buyer": buyer,
                                            "status": "Sent",
                                            "time": datetime.now().strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            ),
                                            "template": "Manual Preview",
                                        }
                                        save_json(LOGS_FILE, logs)
                                        st.success(f"Message sent to {buyer}!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to send message.")
