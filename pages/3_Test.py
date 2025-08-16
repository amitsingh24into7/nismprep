import streamlit as st
import menu
import sqlite3
import time
import os

DB_FILE = "master_questions.db"

# ===== PAGE CONFIG =====
st.set_page_config(page_title="NISM Test", layout="wide")
st.session_state.current_page = os.path.basename(__file__)
menu.top_menu()

# ===== SESSION CHECKS =====
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    if "selected_paper" in st.session_state:
        st.error("⚠ Session expired. Redirecting to login...")
        time.sleep(1)
        st.switch_page("pages/1_Login.py")
    else:
        st.switch_page("pages/1_Login.py")
    st.stop()

required_keys = ["user_id", "selected_paper", "mode"]
for key in required_keys:
    if key not in st.session_state:
        st.error("⚠ Invalid access. Please start from Dashboard.")
        if st.button("Go to Dashboard"):
            st.switch_page("pages/2_Dashboard.py")
        st.stop()

USER_ID = st.session_state.user_id
PAPER_ID = st.session_state.selected_paper
MODE = st.session_state.mode

# ===== DB HELPERS =====
def get_questions(paper_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question, option_a, option_b, option_c, option_d, correct_option, explanation
            FROM questions
            WHERE paper_id = ?
            ORDER BY id
        """, (paper_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        st.error(f"❌ Database error: {e}")
        st.stop()

def save_user_progress(user_id, paper_id, score, total_questions, answers, completed=1):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_progress (user_id, paper_id, answered_count, score, completed)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, paper_id)
            DO UPDATE SET answered_count = excluded.answered_count,
                          score = excluded.score,
                          completed = excluded.completed
        """, (user_id, paper_id, len(answers), score, completed))

        cursor.executemany("""
            INSERT OR REPLACE INTO user_answers (user_id, question_id, selected_option)
            VALUES (?, ?, ?)
        """, [
            (user_id, q_id, ans["selected"])
            for q_id, ans in answers.items()
        ])

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"❌ Failed to save progress: {e}")

# ===== SESSION STATE INIT =====
if "questions" not in st.session_state:
    st.session_state.questions = get_questions(PAPER_ID)
    st.rerun()

if "answers" not in st.session_state:
    st.session_state.answers = {}

if "marked" not in st.session_state:
    st.session_state.marked = {}

if "current_q" not in st.session_state:
    st.session_state.current_q = 0

if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()

if "submitted" not in st.session_state:
    st.session_state.submitted = False

questions = st.session_state.questions
n_questions = len(questions)

if n_questions == 0:
    st.error("❌ No questions found for this test.")
    st.stop()

# ===== SYNC QUERY PARAMS =====
current_q_idx = st.session_state.current_q

if "q" in st.query_params:
    try:
        q_index = int(st.query_params["q"])
        if 0 <= q_index < n_questions and st.session_state.current_q != q_index:
            st.session_state.current_q = q_index
            st.rerun()
    except Exception:
        pass

if st.query_params.get("q") != str(current_q_idx):
    st.query_params["q"] = str(current_q_idx)

# ===== TIMER =====
exam_duration = 20 * 60
time_left = max(0, exam_duration - (time.time() - st.session_state.start_time))
mins, secs = divmod(int(time_left), 60)

if time_left <= 0 and not st.session_state.submitted:
    st.session_state.submitted = True
    st.warning("⏰ Time's up! Submitting your test...")
    time.sleep(1)
    st.rerun()

# ===== SIDEBAR NAVIGATION =====
if MODE == "Mock Exam":
    st.sidebar.header("📋 Question Navigator")

    st.sidebar.markdown("""
    <small>
    ✅ = Saved  
    🔖 = Marked  
    Number = Pending
    </small>
    """, unsafe_allow_html=True)

    show_marked_only = st.sidebar.checkbox("📌 Show Only Marked Questions")

    question_indices = list(range(n_questions))
    if show_marked_only:
        question_indices = [
            i for i in question_indices
            if st.session_state.marked.get(questions[i][0], False)
        ]

    # Grid of navigator buttons
    cols_per_row = 5
    for i in range(0, len(question_indices), cols_per_row):
        cols = st.sidebar.columns(cols_per_row, gap="small")
        for j, q_idx in enumerate(question_indices[i:i + cols_per_row]):
            q_id = questions[q_idx][0]

            btn_label = "🔖" if st.session_state.marked.get(q_id, False) \
                else "✅" if q_id in st.session_state.answers \
                else str(q_idx + 1)

            if cols[j].button(btn_label, key=f"nav_{q_idx}", help=f"Q{q_idx+1}"):
                st.session_state.current_q = q_idx
                st.query_params["q"] = str(q_idx)
                st.rerun()

    # ✅ Clear All Marks Button
    def clear_all_marks():
        st.session_state.marked.clear()

    if st.sidebar.button("🧹 Clear All Marks", use_container_width=True):
        clear_all_marks()
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("✅ Submit Test", use_container_width=True):
        if any(st.session_state.marked.values()):
            st.sidebar.warning("⚠ Review marked questions.")
        elif len(st.session_state.answers) < n_questions:
            st.sidebar.warning("⚠ Answer all questions.")
        else:
            st.session_state.submitted = True
            st.rerun()

# ===== STATUS BAR =====
answered_count = len(st.session_state.answers)
marked_count = sum(1 for v in st.session_state.marked.values() if v)
st.markdown(f"""
**Mode:** {MODE} |
**Q:** {current_q_idx+1}/{n_questions} |
**Ans:** {answered_count} |
**Marked:** {marked_count} |
⏳ **Time:** {mins:02d}:{secs:02d}
""")
st.markdown("---")

# ===== RENDER QUESTION =====
if not st.session_state.submitted:
    q_id, q_text, a, b, c, d, correct_opt, explanation = questions[current_q_idx]
    options_map = {"A": a, "B": b, "C": c, "D": d}
    opt_keys = [k for k, v in options_map.items() if v and str(v).strip()]

    if not opt_keys:
        st.error("❌ No valid options.")
        st.stop()

    radio_key = f"sel_{q_id}"
    if q_id in st.session_state.answers:
        st.session_state[radio_key] = st.session_state.answers[q_id]["selected"]

    st.subheader(f"Q{current_q_idx+1}. {q_text}")
    selected = st.radio(
        "Choose your answer:",
        opt_keys,
        format_func=lambda x: f"**{x}.** {options_map[x]}",
        key=radio_key
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("💾 Save Answer", key=f"save_{q_id}"):
            if selected:
                st.session_state.answers[q_id] = {
                    "selected": selected,
                    "selected_text": options_map[selected],
                    "correct": correct_opt,
                    "correct_text": options_map.get(correct_opt, ""),
                    "explanation": explanation
                }
                st.toast("✅ Answer saved!", icon="💾")
                st.rerun()
            else:
                st.warning("⚠ Select an option first.")

    with col2:
        if st.button("💾 Save & Next", key=f"save_next_{q_id}"):
            if selected:
                st.session_state.answers[q_id] = {
                    "selected": selected,
                    "selected_text": options_map[selected],
                    "correct": correct_opt,
                    "correct_text": options_map.get(correct_opt, ""),
                    "explanation": explanation
                }
                if current_q_idx < n_questions - 1:
                    st.session_state.current_q += 1
                    st.query_params["q"] = str(st.session_state.current_q)
                st.rerun()
            else:
                st.warning("⚠ Select an option first.")

    with col3:
        if st.button("⬅ Previous", key=f"prev_{q_id}") and current_q_idx > 0:
            st.session_state.current_q -= 1
            st.query_params["q"] = str(st.session_state.current_q)
            st.rerun()

    with col4:
        if st.button("Next ➡", key=f"next_{q_id}") and current_q_idx < n_questions - 1:
            st.session_state.current_q += 1
            st.query_params["q"] = str(st.session_state.current_q)
            st.rerun()

    # ✅ Mark for Review (Fixed: No st.rerun() in callback)
    def on_mark_change():
        st.session_state.marked[q_id] = st.session_state[mark_key]

    mark_key = f"mark_{q_id}"
    current_marked = st.session_state.marked.get(q_id, False)

    st.checkbox(
        "🔖 Mark for Review",
        value=current_marked,
        key=mark_key,
        on_change=on_mark_change
    )

# ===== AFTER SUBMISSION =====
else:
    st.markdown("## 📊 Test Submitted!")
    score = sum(1 for q in questions if st.session_state.answers.get(q[0], {}).get("selected") == q[6])
    percentage = (score / n_questions) * 100
    st.markdown(f"### 🎯 Score: {score}/{n_questions} ({percentage:.1f}%)")

    if "results_saved" not in st.session_state:
        save_user_progress(USER_ID, PAPER_ID, score, n_questions, st.session_state.answers)
        st.session_state.results_saved = True
        st.toast("✅ Results saved!", icon="📈")

    # Cleanup
    for key in ["questions", "answers", "marked", "current_q", "start_time", "submitted"]:
        st.session_state.pop(key, None)

    st.link_button("📄 View Detailed Results", "pages/4_Result.py", type="primary")