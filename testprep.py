import sqlite3
import streamlit as st
import random

DB_FILE = "nism_questions.db"

# ==== DB HELPER ====
def get_all_questions():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, question, option_a, option_b, option_c, option_d, correct_option, explanation
        FROM questions
        WHERE question IS NOT NULL AND correct_option IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==== QUIZ UI ====
st.set_page_config(page_title="NISM Quiz", layout="centered")
st.title("📚 NISM Practice Quiz")

if "score" not in st.session_state:
    st.session_state.score = 0
if "questions" not in st.session_state:
    st.session_state.questions = random.sample(get_all_questions(), 10)  # 10 random Qs
    st.session_state.current_q = 0
    st.session_state.answers = {}

questions = st.session_state.questions
current_q_idx = st.session_state.current_q

if current_q_idx < len(questions):
    q_id, q_text, a, b, c, d, correct_opt, explanation = questions[current_q_idx]

    st.subheader(f"Q{current_q_idx+1}. {q_text}")
    options_map = {"A": a, "B": b, "C": c, "D": d}

    selected = st.radio(
        "Choose your answer:",
        list(options_map.keys()),
        format_func=lambda x: f"{x}. {options_map[x]}" if options_map[x] else x
    )

    if st.button("Submit Answer"):
        is_correct = selected == correct_opt
        st.session_state.answers[q_id] = {
            "question": q_text,
            "selected": selected,
            "selected_text": options_map[selected],
            "correct": correct_opt,
            "correct_text": options_map[correct_opt],
            "is_correct": is_correct,
            "explanation": explanation
        }
        if is_correct:
            st.success("✅ Correct!")
            st.session_state.score += 1
        else:
            st.error(f"❌ Wrong! Correct answer: {correct_opt}. {options_map[correct_opt]}")
        if explanation:
            st.info(f"**Explanation:** {explanation}")

        st.session_state.current_q += 1
        st.rerun()

else:
    st.success(f"🎉 Quiz completed! Your score: {st.session_state.score}/{len(questions)}")

    st.markdown("## 📜 Detailed Summary")
    for idx, (q_id, data) in enumerate(st.session_state.answers.items(), start=1):
        st.markdown(f"**Q{idx}. {data['question']}**")
        st.write(f"Your Answer: {data['selected']} - {data['selected_text']}")
        st.write(f"Correct Answer: {data['correct']} - {data['correct_text']}")
        st.write(f"Explanation: {data['explanation']}")
        st.markdown("---")

    if st.button("Restart Quiz"):
        st.session_state.score = 0
        st.session_state.questions = random.sample(get_all_questions(), 10)
        st.session_state.current_q = 0
        st.session_state.answers = {}
        st.rerun()
