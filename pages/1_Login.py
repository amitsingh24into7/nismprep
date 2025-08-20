# pages/1_Login.py
import streamlit as st
from db.db_connection import get_db_connection, verify_password
import menu
import os
from datetime import datetime

st.set_page_config(page_title="Login", layout="centered")
st.session_state.current_page = os.path.basename(__file__)
menu.top_menu()

st.title("🔑 Login to NISM Test Series")
st.markdown("---")

username = st.text_input("Email")
password = st.text_input("Password", type="password")
login_btn = st.button("Login")

if login_btn:
    if not username or not password:
        st.warning("Please fill all fields")
    else:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    APP_SLUG = os.getenv("APP_SLUG", "nism-test")
                    cur.execute("""
                            SELECT password_hash, valid_until, is_active
                            FROM users
                            WHERE username = %s AND app_slug = %s
                        """, (username, APP_SLUG))
                    row = cur.fetchone()

            if not row:
                st.error("❌ User not found")
            else:
                password_hash, valid_until, is_active = row

                if not is_active:
                    st.error("❌ Account is inactive")
                elif valid_until < datetime.now().date():
                    st.error("❌ Subscription expired on " + str(valid_until))
                elif verify_password(password, password_hash):
                    st.session_state.logged_in = True
                    st.session_state.user_name = username
                    st.session_state.user_id = username  # or fetch ID
                    st.session_state.current_page = "1_Login.py"
                    st.success("✅ Logged in!")
                    st.switch_page("pages/2_Dashboard.py")
                else:
                    st.error("❌ Incorrect password")
        except Exception as e:
            st.error(f"❌ System error: {e}")