import streamlit as st
import menu
import os

st.set_page_config(page_title="NISM Test Series", layout="wide")
st.session_state.current_page = os.path.basename(__file__)
menu.top_menu()

st.title("🏠 Welcome to NISM Test Series")
st.markdown("---")
st.write("""
This is your preparation hub for NISM exams.
- Login to your account
- Take Mock & Practice Papers
- Track your progress
""")
