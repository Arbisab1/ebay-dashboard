import base64
import json
import os
from urllib.parse import parse_qs, unquote, urlparse
import requests
import streamlit as st

# --- SECRETS MANAGEMENT ---
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

AUTH_URL = (
    f"https://auth.ebay.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={RUNAME}&"
    "scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.marketing.readonly%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.marketing%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.inventory.readonly%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.inventory%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.account.readonly%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.account%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.fulfillment.readonly%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.fulfillment%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.analytics.readonly%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.finances%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.payment.dispute%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.identity.readonly%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.reputation%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.reputation.readonly%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.notification.subscription%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.notification.subscription.readonly%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.stores%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.stores.readonly%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fscope%2Fsell.edelivery%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.vero%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fsell.inventory.mapping%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.message%20https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.feedback%20"
    "https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope%2Fcommerce.shipping"
)

st.set_page_config(
    page_title="eBay Multi-Store Automation Hub",
    layout="wide",
    page_icon="🛍️",
)


def load_stores():
    if os.path.exists(STORES_FILE):
        try:
            with open(STORES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_stores(data):
    with open(STORES_FILE, "w") as f:
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


def get_orders(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    res = requests.get(
        "https://api.ebay.com/sell/fulfillment/v1/order?limit=10",
        headers=headers,
    )
    if res.status_code == 200:
        return res.json().get("orders", [])
    return []


st.title("🛍️ eBay Multi-Store Manager & Bot Dashboard")

with st.sidebar:
    st.header("➕ Link New eBay Store")
    st.markdown(f"[🔗 **Click to Connect eBay Store**]({AUTH_URL})")
    st.caption("Authorization ke baad browser URL paste karein:")
    redirect_input = st.text_input("Redirected URL / Code:")
    store_alias = st.text_input("Store Name / Label (e.g. asafulfilldeals):")

    if st.button("Save & Link Store"):
        if redirect_input and store_alias:
            final_code = clean_auth_code(redirect_input)
            status, token_data = exchange_code_for_tokens(final_code)

            if status == 200 and "access_token" in token_data:
                stores = load_stores()
                stores[store_alias] = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token", ""),
                }
                save_stores(stores)
                st.success(f"Store '{store_alias}' kamyabi say connect ho gaya!")
                st.rerun()
            else:
                err_msg = token_data.get(
                    "error_description",
                    token_data.get("error", "Unknown error"),
                )
                st.error(f"Failed ({status}): {err_msg}")
        else:
            st.warning("Store name aur URL dono fields lazmi hain.")

stores = load_stores()
if not stores:
    st.info("Filhal koi store link nahi hai. Sidebar say store connect karein.")
else:
    tabs = st.tabs(list(stores.keys()))
    for idx, (name, tokens) in enumerate(stores.items()):
        with tabs[idx]:
            st.subheader(f"📊 Dashboard - {name}")
            if st.button(f"🔄 Sync Orders ({name})", key=f"sync_{name}"):
                orders = get_orders(tokens["access_token"])
                st.session_state[f"orders_{name}"] = orders
                st.metric("Total Live Orders", len(orders))

            orders = st.session_state.get(f"orders_{name}", [])
            if orders:
                st.write("### Recent Orders")
                table_data = [
                    {
                        "Order ID": o.get("orderId"),
                        "Buyer": o.get("buyer", {}).get("username"),
                        "Status": o.get("orderFulfillmentStatus"),
                    }
                    for o in orders
                ]
                st.table(table_data)
