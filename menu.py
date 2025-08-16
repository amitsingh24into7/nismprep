import streamlit as st
import os

def top_menu():
    # Menu items: label → file path
    menu_items = {
        "Home": "Home.py",
        "Login": "pages/1_Login.py",
        "Dashboard": "pages/2_Dashboard.py",
        "Test": "pages/3_Test.py",
        "Result": "pages/4_Result.py"
    }

    # Top horizontal menu
    cols = st.columns(len(menu_items))
    for i, (label, path) in enumerate(menu_items.items()):
        if cols[i].button(label, key=f"menu_{label}"):
            st.switch_page(path)

    # Hide default Streamlit multipage sidebar navigation
    current_page = st.session_state.get("current_page", os.path.basename(__file__))

    if not current_page.endswith("3_Test.py"):
        # Hide sidebar completely for non-test pages
        st.markdown(
            """
            <style>
                section[data-testid="stSidebar"] {display: none !important;}
                div[data-testid="stSidebarNav"] {display: none !important;}
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        # Hide default page nav but keep sidebar visible for question nav
        st.markdown(
            """
            <style>
                div[data-testid="stSidebarNav"] {display: none !important;}
            </style>
            """,
            unsafe_allow_html=True
        )
