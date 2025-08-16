import streamlit as st

st.set_page_config(page_title="NISM — Online Test Series", layout="wide")

# Redirect to login if not logged in
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.switch_page("pages/1_Login.py")
else:
    st.switch_page("pages/2_Dashboard.py")
