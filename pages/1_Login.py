import streamlit as st
import menu
import os

st.set_page_config(page_title="Login", layout="centered")
st.session_state.current_page = os.path.basename(__file__)
menu.top_menu()

st.title("🔑 Login to NISM Test Series")
st.markdown("---")

username = st.text_input("Enter your name", "")
login_btn = st.button("Login", key="login_page_btn")

if login_btn:
    if username.strip():
        st.session_state.logged_in = True
        st.session_state.user_name = username.strip()
        st.session_state.user_id = 1  # static for now
        st.switch_page("pages/2_Dashboard.py")
    else:
        st.warning("⚠ Please enter your name to proceed.")
