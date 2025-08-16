import streamlit as st
import sqlite3
import menu
import os

DB_FILE = "master_questions.db"

def get_papers_with_progress(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            p.paper_id, p.title, p.type, p.instructions, p.total_questions,
            IFNULL(up.answered_count, 0), IFNULL(up.score, 0), IFNULL(up.completed, 0)
        FROM papers p
        LEFT JOIN user_progress up
        ON p.paper_id = up.paper_id AND up.user_id = ?
        ORDER BY p.type, p.paper_id
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def all_mocks_completed(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM papers p
        LEFT JOIN user_progress up
        ON p.paper_id = up.paper_id AND up.user_id = ?
        WHERE p.type = 'mock' AND IFNULL(up.completed, 0) = 1
    """, (user_id,))
    completed_mocks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM papers WHERE type = 'mock'")
    total_mocks = cursor.fetchone()[0]
    conn.close()
    return completed_mocks == total_mocks and total_mocks > 0

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.switch_page("pages/1_Login.py")

st.set_page_config(page_title="Dashboard", layout="wide")
st.session_state.current_page = os.path.basename(__file__)
menu.top_menu()

col1, col2 = st.columns([3, 1])  # Left (title) takes more space, right (logout) less

with col1:
    st.title(f"📊 Welcome, {st.session_state.user_name}")

with col2:
    st.markdown("<div style='text-align: right; padding-top: 28px;'>", unsafe_allow_html=True)
    if st.button("🚪 Logout", key="logout_top"):
        st.session_state.clear()
        st.switch_page("pages/1_Login.py")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

papers = get_papers_with_progress(st.session_state.user_id)
mocks_done = all_mocks_completed(st.session_state.user_id)

mock_papers = [p for p in papers if p[2] == "mock"]
practice_papers = [p for p in papers if p[2] == "practice"]

# MOCK PAPERS
st.subheader("📚 Mock Papers")
cols = st.columns(2)
for idx, paper in enumerate(mock_papers):
    a=idx
    with cols[idx % 2]:
        pid, title, ptype, inst, total_q, ans_count, score, completed = paper
        completion_pct = int((ans_count / total_q) * 100) if total_q > 0 else 0
        st.markdown(f"### {title.capitalize()}-{a+1}")
        st.progress(completion_pct / 100)
        st.caption(f"**{total_q} Questions** — {completion_pct}% Completed")
        with st.expander("📖 Instructions"):
            st.write(inst or "No instructions provided.")
        if st.button("▶ Start Test", key=f"start_{pid}"):
            st.session_state.selected_paper = pid
            st.session_state.mode = "Mock Exam"
            st.switch_page("pages/3_Test.py")

# PRACTICE PAPERS
st.subheader("🛠 Practice Papers")
cols = st.columns(2)
for idx, paper in enumerate(practice_papers):
    b=idx
    with cols[idx % 2]:
        pid, title, ptype, inst, total_q, ans_count, score, completed = paper
        completion_pct = int((ans_count / total_q) * 100) if total_q > 0 else 0
        st.markdown(f"### {title.capitalize()}-{b+1}")
        st.progress(completion_pct / 100)
        st.caption(f"**{total_q} Questions** — {completion_pct}% Completed")
        with st.expander("📖 Instructions"):
            st.write(inst or "No instructions provided.")
        if not mocks_done:
            st.button("🔒 Locked", key=f"locked_{pid}", disabled=True)
        else:
            if st.button("▶ Start Test", key=f"start_{pid}"):
                st.session_state.selected_paper = pid
                st.session_state.mode = "Practice Mode"
                st.switch_page("pages/3_Test.py")
