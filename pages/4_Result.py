# pages/4_Result.py

import streamlit as st
import menu
import sqlite3

DB_FILE = "master_questions.db"

st.set_page_config(page_title="Test Results", layout="wide")
st.session_state.current_page = "4_Result.py"
menu.top_menu()

if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.switch_page("pages/1_Login.py")

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

# === Check if we have a valid test result to show ===
if "selected_paper" not in st.session_state:
    st.error("❌ No test result available.")
    if st.button("🏠 Go to Dashboard", type="primary"):
        st.switch_page("pages/2_Dashboard.py")
    st.stop()

PAPER_ID = st.session_state.selected_paper
USER_ID = st.session_state.user_id

# === Fetch Results ===
def get_user_results(user_id, paper_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            q.id, q.question, q.option_a, q.option_b, q.option_c, q.option_d,
            q.correct_option, q.explanation,
            ua.selected_option
        FROM questions q
        LEFT JOIN user_answers ua ON q.id = ua.question_id AND ua.user_id = ?
        WHERE q.paper_id = ?
        ORDER BY q.id
    """, (user_id, paper_id))
    rows = cursor.fetchall()
    conn.close()
    return rows

results = get_user_results(USER_ID, PAPER_ID)

if not results:
    st.error("❌ No answer data found.")
    if st.button("Back to Dashboard", type="secondary"):
        st.switch_page("pages/2_Dashboard.py")
    st.stop()

# === Calculate Score ===
total = len(results)
correct = sum(1 for r in results if r[8] == r[6])
percentage = (correct / total) * 100

st.title("📜 Your Test Results")
st.markdown(f"### 🎯 Score: {correct}/{total} ({percentage:.1f}%)")
st.markdown("---")

# === Show Each Question ===
option_cols = {"A": 2, "B": 3, "C": 4, "D": 5}

for idx, row in enumerate(results):
    q_id, question, a, b, c, d, correct, explanation, selected = row
    status = "✅" if selected == correct else "❌"
    bg_color = "lightgreen" if selected == correct else "lightpink" if selected else "lightgrey"

    with st.expander(f"{status} Q{idx+1}: {question}", expanded=False):
        st.markdown(f"**Your Answer:** `{selected or 'Not answered'}`")
        st.markdown(f"**Correct Answer:** `{correct}`")

        st.markdown("**Options:**")
        for opt in "ABCD":
            txt = row[option_cols[opt]]
            if not txt:
                continue
            if opt == correct:
                st.markdown(f"- **{opt}. {txt}** ✅")
            elif opt == selected:
                st.markdown(f"- ~~{opt}. {txt}~~ ❌")
            else:
                st.markdown(f"- {opt}. {txt}")

        if explanation:
            st.info(f"📘 **Explanation:**\n\n{explanation}")

st.markdown("---")

# === Navigation Buttons ===
col1, col2 = st.columns(2)
with col1:
    if st.button("🔁 Retake Same Test", use_container_width=True):
        st.session_state.mode = "Practice Mode"  # or keep original
        st.switch_page("pages/3_Test.py")

with col2:
    if st.button("🏠 Back to Dashboard", use_container_width=True):
        # Optional: clear test state
        for key in ["selected_paper", "mode"]:
            st.session_state.pop(key, None)
        st.switch_page("pages/2_Dashboard.py")