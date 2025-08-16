import sqlite3
import streamlit as st
import os

DB_FILE = "master_questions.db"  # Change to your master DB file
USER_ID = 1  # For now static, later can be login-based


# ===== DB HELPERS =====
def get_papers_with_progress():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.paper_id,
            p.title,
            p.type,
            p.instructions,
            p.total_questions,
            IFNULL(up.answered_count, 0) AS answered_count,
            IFNULL(up.score, 0) AS score,
            IFNULL(up.completed, 0) AS completed
        FROM papers p
        LEFT JOIN user_progress up
        ON p.paper_id = up.paper_id AND up.user_id = ?
        ORDER BY p.type, p.paper_id
    """, (USER_ID,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def all_mocks_completed():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM papers p
        LEFT JOIN user_progress up
        ON p.paper_id = up.paper_id AND up.user_id = ?
        WHERE p.type = 'mock' AND IFNULL(up.completed, 0) = 1
    """, (USER_ID,))
    completed_mocks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM papers WHERE type = 'mock'")
    total_mocks = cursor.fetchone()[0]
    conn.close()

    return completed_mocks == total_mocks and total_mocks > 0


# ===== STREAMLIT PAGE CONFIG =====
st.set_page_config(page_title="NISM — Online Test Series (v1.0)", layout="wide")
st.title("📝 NISM — Online Test Series (v1.0)")
st.markdown("---")


# ===== FETCH DATA =====
papers = get_papers_with_progress()
mocks_done = all_mocks_completed()

# ===== RENDER DASHBOARD =====
mock_papers = [p for p in papers if p[2] == "mock"]
practice_papers = [p for p in papers if p[2] == "practice"]

# --- MOCK PAPERS SECTION ---
st.subheader("📚 Mock Papers")
cols = st.columns(2)

for idx, paper in enumerate(mock_papers):
    with cols[idx % 2]:
        paper_id, title, ptype, instructions, total_q, ans_count, score, completed = paper
        completion_pct = int((ans_count / total_q) * 100) if total_q > 0 else 0

        with st.container():
            st.markdown(f"### {title}- {paper_id}")
            st.progress(completion_pct / 100)
            st.caption(f"**{total_q} Questions** — {completion_pct}% Completed")
            with st.expander("📖 Instructions"):
                st.write(instructions or "No instructions provided.")

            if st.button("▶ Start Test", key=f"start_{paper_id}"):
                st.session_state.selected_paper = paper_id
                st.session_state.started = True
                st.session_state.mode = "Mock Exam"
                st.rerun()

# --- PRACTICE PAPERS SECTION ---
st.subheader("🛠 Practice Papers")
cols = st.columns(2)

for idx, paper in enumerate(practice_papers):
    with cols[idx % 2]:
        paper_id, title, ptype, instructions, total_q, ans_count, score, completed = paper
        completion_pct = int((ans_count / total_q) * 100) if total_q > 0 else 0
        a=idx

        with st.container():
            st.markdown(f"### {title}- {a+1}")
            st.progress(completion_pct / 100)
            st.caption(f"**{total_q} Questions** — {completion_pct}% Completed")
            with st.expander("📖 Instructions"):
                st.write(instructions or "No instructions provided.")

            if not mocks_done:
                st.button("🔒 Locked", key=f"locked_{paper_id}", disabled=True)
            else:
                if st.button("▶ Start Test", key=f"start_{paper_id}"):
                    st.session_state.selected_paper = paper_id
                    st.session_state.started = True
                    st.session_state.mode = "Practice Mode"
                    st.rerun()


# ===== FOOTER =====
st.markdown("---")
st.caption("💡 Complete all mock papers to unlock practice papers.")
