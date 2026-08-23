import base64
import json
import os
import requests
import streamlit as st

# --- CONFIGURATION ---
CLIENT_ID = "NawazIqb-eBayAuto-PRD-d254d2f41-10c98af7"
CLIENT_SECRET = "PRD-254d2f418365-a9a4-43a0-bc81-4af2"
RUNAME = "Nawaz_Iqbal-NawazIqb-eBayAu-pifoqzze"
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


# --- DATA STORAGE FUNCTIONS ---
def load_stores():
    if os.path.exists(STORES_FILE):
        with open(STORES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_stores(data):
    with open(STORES_FILE, "w") as f:
        json.dump(data, f, indent=4)


# --- TOKEN EXCHANGE & REFRESH ---
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
    return res.json()


def get_fresh_access_token(refresh_token):
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


# --- FETCH ORDERS ---
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


# --- UI HEADER ---
st.title("🛍️ eBay Multi-Store Manager & Bot Dashboard")

# --- SIDEBAR: CONNECT STORE ---
with st.sidebar:
    st.header("➕ Link New eBay Store")
    st.markdown(
        f'<a href="{AUTH_URL}" target="_blank"><button style="background-color:#0053a0;color:white;padding:10px;border-radius:6px;border:none;width:100%;cursor:pointer;font-weight:bold;">🔗 Click to Connect eBay Store</button></a>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.caption("Authorization kay baad URL bar ka pura link paste karein:")
    redirect_input = st.text_input("Redirected URL / Code:")
    store_alias = st.text_input("Store Name / Label (e.g. MyStore 1):")

    if st.button("Save & Link Store"):
        if redirect_input and store_alias:
            code = redirect_input
            if "code=" in redirect_input:
                code = (
                    redirect_input.split("code=")[1]
                    .split("&")[0]
                    .replace("%2F", "/")
                )

            token_data = exchange_code_for_tokens(code)
            if "access_token" in token_data:
                stores = load_stores()
                stores[store_alias] = {
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token", ""),
                }
                save_stores(stores)
                st.success(f"Store '{store_alias}' successfully connected!")
                st.rerun()
            else:
                st.error("Token exchange failed. URL dobara check karein.")
        else:
            st.warning("Store name aur URL dono fields lazmi hain.")

# --- MAIN DASHBOARD VIEW ---
stores = load_stores()

if not stores:
    st.info(
        "Filhal koi store link nahi hai. Sidebar say button press kar kay pehla store connect karein."
    )
else:
    tabs = st.tabs(list(stores.keys()))

    for idx, (name, tokens) in enumerate(stores.items()):
        with tabs[idx]:
            st.subheader(f"📊 Dashboard - {name}")

            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button(f"🔄 Sync Orders ({name})", key=f"sync_{name}"):
                    orders = get_orders(tokens["access_token"])
                    # If token expired, auto refresh
                    if not orders and tokens.get("refresh_token"):
                        new_acc = get_fresh_access_token(
                            tokens["refresh_token"]
                        )
                        if new_acc:
                            tokens["access_token"] = new_acc
                            stores[name]["access_token"] = new_acc
                            save_stores(stores)
                            orders = get_orders(new_acc)

                    st.session_state[f"orders_{name}"] = orders
                    st.metric("Total Live Orders", len(orders))

            with col2:
                st.subheader("✉️ Auto Messaging Settings")
                msg_template = st.text_area(
                    "Default Message Template:",
                    "Hi {buyer}, Thank you for your order! We are processing it.",
                    key=f"msg_{name}",
                )
                if st.button(f"Save Settings ({name})", key=f"save_{name}"):
                    st.success("Automated template saved!")

            # Order Table Display
            orders = st.session_state.get(f"orders_{name}", [])
            if orders:
                st.write("### Recent Orders")
                table_data = []
                for o in orders:
                    table_data.append(
                        {
                            "Order ID": o.get("orderId"),
                            "Buyer": o.get("buyer", {}).get("username"),
                            "Total": f"{o.get('pricingSummary', {}).get('total', {}).get('value')} {o.get('pricingSummary', {}).get('total', {}).get('currency')}",
                            "Status": o.get("orderFulfillmentStatus"),
                        }
                    )
                st.table(table_data)