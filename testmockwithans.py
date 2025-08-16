import sqlite3
import streamlit as st
import random
import time
import datetime
import json
import os

DB_FILE = "nism_questions.db"

# ==== DB HELPERS ====
def get_all_questions():
    if not os.path.exists(DB_FILE):
        st.error(f"❌ Database file not found: {DB_FILE}")
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question, option_a, option_b, option_c, option_d, correct_option, explanation
            FROM questions
            WHERE question IS NOT NULL AND TRIM(question) != ''
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        st.error(f"❌ Error reading DB: {e}")
        return []

# ==== PAGE CONFIG ====
st.set_page_config(page_title="NISM Mock Test", layout="wide", initial_sidebar_state="expanded")

# ==== SESSION STATE INIT ====
if "started" not in st.session_state:
    st.session_state.started = False
if "mode" not in st.session_state:
    st.session_state.mode = "Mock Exam"
if "questions" not in st.session_state:
    st.session_state.questions = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "marked" not in st.session_state:
    st.session_state.marked = {}
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "exam_duration" not in st.session_state:
    st.session_state.exam_duration = 20 * 60
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "show_only_marked" not in st.session_state:
    st.session_state.show_only_marked = False

# ==== LANDING PAGE ====
if not st.session_state.started:
    st.markdown("<h1 style='text-align: center; color: #007BFF;'>📝 NISM Certification Mock Exam</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #555;'>Simulate real exam conditions with timer, review, and explanations.</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### 📚 Instructions")
    st.markdown("""
    - You have **20 minutes** to answer the questions.
    - You can **mark questions for review** and revisit them before submission.
    - **Mock Exam**: No feedback until you submit.
    - **Practice Mode**: See feedback instantly after each save.
    """)

    st.session_state.mode = st.radio(
        "Select Mode:",
        ["Mock Exam", "Practice Mode"],
        help="Mock Exam hides feedback until submission. Practice Mode shows feedback instantly."
    )

    if st.button("🚀 Start Exam", use_container_width=True):
        all_qs = get_all_questions()
        if not all_qs:
            st.error("❌ No questions found in the database.")
            st.stop()
        #st.session_state.questions = random.sample(all_qs, min(20, len(all_qs)))
        st.session_state.questions = all_qs  # use all questions from DB

        st.session_state.start_time = time.time()
        st.session_state.started = True
        st.rerun()

# ==== MAIN TEST ====
else:
    questions = st.session_state.questions
    n_questions = len(questions)
    current_q_idx = st.session_state.current_q

    # Timer
    time_left = max(0, st.session_state.exam_duration - (time.time() - st.session_state.start_time))
    mins, secs = divmod(int(time_left), 60)
    if time_left <= 0 and not st.session_state.submitted:
        st.session_state.submitted = True
        st.warning("⏰ Time's up! Your exam has been auto-submitted.")

    # ===== STATUS BAR =====
    answered_count = len(st.session_state.answers)
    marked_count = sum(1 for v in st.session_state.marked.values() if v)
    st.markdown(f"""
    **Mode:** {st.session_state.mode} |
    **Question:** {current_q_idx+1}/{n_questions} |
    **Answered:** {answered_count} |
    **Marked:** {marked_count} |
    ⏳ **Time Left:** {mins:02d}:{secs:02d}
    """)
    st.markdown("---")

    # ===== SIDEBAR NAVIGATION =====
    st.sidebar.header("📋 Exam Navigator")
    st.session_state.show_only_marked = st.sidebar.checkbox("> Show only Marked Questions", value=st.session_state.show_only_marked)

    cols = st.sidebar.columns(5)
    for i, q in enumerate(questions):
        q_id = q[0]
        badge = "✅" if q_id in st.session_state.answers else "🔖" if st.session_state.marked.get(q_id) else "○"
        col = cols[i % 5]
        if col.button(badge, key=f"nav_{i}"):
            st.session_state.current_q = i
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("✅ Submit Exam", use_container_width=True) and not st.session_state.submitted:
        st.session_state.submitted = True
        st.rerun()
    if st.sidebar.button("🔄 Restart Exam", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # ==== SHOW QUESTIONS ====
    if not st.session_state.submitted:
        # Filter marked questions if selected
        if st.session_state.show_only_marked:
            marked_indices = [i for i, q in enumerate(questions) if st.session_state.marked.get(q[0])]
            if marked_indices:
                if current_q_idx not in marked_indices:
                    st.session_state.current_q = marked_indices[0]
                    current_q_idx = st.session_state.current_q
            else:
                st.info("🔖 You haven't marked any questions for review yet.")
                st.stop()

        q_id, q_text, a, b, c, d, correct_opt, explanation = questions[current_q_idx]
        options_map = {"A": a, "B": b, "C": c, "D": d}
        opt_keys = [k for k, v in options_map.items() if v and str(v).strip() != ""]

        radio_key = f"sel_{q_id}"
        saved = st.session_state.answers.get(q_id)
        if radio_key not in st.session_state and saved:
            st.session_state[radio_key] = saved["selected"]

        st.subheader(f"Q{current_q_idx+1}. {q_text}")
        selected = st.radio(
            "Choose your answer:",
            opt_keys,
            index=opt_keys.index(st.session_state.get(radio_key, opt_keys[0])) if st.session_state.get(radio_key) in opt_keys else 0,
            format_func=lambda x: f"{x}. {options_map[x]}",
            key=radio_key
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("💾 Save Answer"):
                if selected:
                    st.session_state.answers[q_id] = {
                        "selected": selected,
                        "selected_text": options_map[selected],
                        "correct": correct_opt,
                        "correct_text": options_map.get(correct_opt, ""),
                        "explanation": explanation
                    }
                    if st.session_state.mode == "Practice Mode":
                        if selected == correct_opt:
                            st.success("✅ Correct!")
                        else:
                            st.error(f"❌ Incorrect. Correct: {correct_opt} — {options_map[correct_opt]}")
                        if explanation:
                            st.info(f"📘 {explanation}")
                else:
                    st.warning("Select an option first.")

        with col2:
            if st.button("💾 Save & Next"):
                if selected:
                    st.session_state.answers[q_id] = {
                        "selected": selected,
                        "selected_text": options_map[selected],
                        "correct": correct_opt,
                        "correct_text": options_map.get(correct_opt, ""),
                        "explanation": explanation
                    }
                    if st.session_state.mode == "Practice Mode":
                        if selected == correct_opt:
                            st.success("✅ Correct!")
                        else:
                            st.error(f"❌ Incorrect. Correct: {correct_opt} — {options_map[correct_opt]}")
                        if explanation:
                            st.info(f"📘 {explanation}")
                    if current_q_idx < n_questions - 1:
                        st.session_state.current_q += 1
                        st.rerun()
                else:
                    st.warning("Select an option first.")

        with col3:
            if st.button("⬅ Previous") and current_q_idx > 0:
                st.session_state.current_q -= 1
                st.rerun()

        with col4:
            if st.button("Next ➡") and current_q_idx < n_questions - 1:
                st.session_state.current_q += 1
                st.rerun()

        mark_key = f"mark_{q_id}"
        if mark_key not in st.session_state:
            st.session_state[mark_key] = st.session_state.marked.get(q_id, False)
        st.session_state.marked[q_id] = st.checkbox("🔖 Mark for Review", key=mark_key)

    # ==== RESULTS ====
    else:
        st.markdown("## 📊 Exam Results")
        score = sum(1 for q in questions if st.session_state.answers.get(q[0], {}).get("selected") == q[6])
        st.markdown(f"🎯 Final Score: {score}/{n_questions} ({(score/n_questions)*100:.1f}%)")
