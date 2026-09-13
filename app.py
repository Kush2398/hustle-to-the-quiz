from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os
import random
import time
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hustle-to-the-quiz-change-this-key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

ADMIN_ID = os.environ.get("QUIZ_ADMIN_ID", "admin")
ADMIN_PASSWORD = os.environ.get("QUIZ_ADMIN_PASSWORD", "admin123")

SYMBOLS = ["◆", "●", "▲", "■"]
LETTERS = ["A", "B", "C", "D"]


def get_db():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    db = get_db()
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enrollment TEXT NOT NULL UNIQUE,
            college TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            option_1 TEXT NOT NULL,
            option_2 TEXT NOT NULL,
            option_3 TEXT NOT NULL,
            option_4 TEXT NOT NULL,
            correct_option INTEGER NOT NULL CHECK(correct_option BETWEEN 1 AND 4),
            difficulty TEXT NOT NULL DEFAULT 'Medium',
            time_limit INTEGER NOT NULL DEFAULT 20,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_option INTEGER NOT NULL CHECK(selected_option BETWEEN 1 AND 4),
            is_correct INTEGER NOT NULL DEFAULT 0,
            points INTEGER NOT NULL DEFAULT 0,
            answered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, question_id),
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quiz_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            active INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            current_position INTEGER NOT NULL DEFAULT 0,
            started_at REAL,
            question_started_at REAL,
            question_ids TEXT DEFAULT ''
        );
    """)

    # Upgrade databases created by older versions.
    cols = {row["name"] for row in db.execute("PRAGMA table_info(quiz_state)").fetchall()}
    if "completed" not in cols:
        db.execute("ALTER TABLE quiz_state ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")

    row = db.execute("SELECT id FROM quiz_state WHERE id = 1").fetchone()
    if not row:
        db.execute("""
            INSERT INTO quiz_state
            (id, active, completed, current_position, started_at, question_started_at, question_ids)
            VALUES (1, 0, 0, 0, NULL, NULL, '')
        """)

    db.commit()
    db.close()


init_db()


def json_error(message, status=400):
    return jsonify({"success": False, "message": message}), status


def json_ok(**kwargs):
    return jsonify({"success": True, **kwargs})


def is_api_request():
    return request.path.startswith("/api/")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            if is_api_request():
                return json_error("Admin session expired. Please log in again.", 401)
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "student":
            if is_api_request():
                return json_error("Student session expired. Please log in again.", 401)
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def get_quiz_state(db):
    return db.execute("SELECT * FROM quiz_state WHERE id = 1").fetchone()


def get_question_ids(state):
    raw = state["question_ids"] or ""
    ids = []
    for item in raw.split(","):
        try:
            ids.append(int(item))
        except (ValueError, TypeError):
            pass
    return ids


def get_current_question(db, state=None):
    state = state or get_quiz_state(db)
    ids = get_question_ids(state)
    if not state["active"] or not ids:
        return None
    position = state["current_position"]
    if position < 0 or position >= len(ids):
        return None
    return db.execute("SELECT * FROM questions WHERE id = ?", (ids[position],)).fetchone()


def public_question(question):
    if not question:
        return None
    return {
        "id": question["id"],
        "question": question["question"],
        "options": [question["option_1"], question["option_2"], question["option_3"], question["option_4"]],
        "difficulty": question["difficulty"],
        "time_limit": question["time_limit"],
        "symbols": SYMBOLS,
        "letters": LETTERS,
    }


def leaderboard_rows(db):
    return db.execute("""
        SELECT
            s.id, s.name, s.enrollment, s.college,
            COALESCE(SUM(a.points), 0) AS score,
            COALESCE(SUM(a.is_correct), 0) AS correct,
            COUNT(a.id) AS answered
        FROM students s
        LEFT JOIN answers a ON a.student_id = s.id
        GROUP BY s.id
        ORDER BY score DESC, correct DESC, s.name COLLATE NOCASE ASC, s.id ASC
    """).fetchall()


def build_results(rows):
    results = []
    for rank, row in enumerate(rows, start=1):
        item = dict(row)
        item["rank"] = rank
        results.append(item)
    return results


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/login")
def login():
    data = request.get_json(silent=True) or request.form
    name = str(data.get("name", "")).strip()
    enrollment = str(data.get("enrollment", "")).strip()
    college = str(data.get("college", "")).strip()

    if not name or not enrollment:
        return json_error("Please enter all required details.")

    if name == ADMIN_ID and enrollment == ADMIN_PASSWORD:
        session.clear()
        session["role"] = "admin"
        session["admin_id"] = name
        return json_ok(role="admin", redirect="/admin", message="Admin login successful.")

    if not college:
        return json_error("Please enter your college name.")

    db = get_db()
    try:
        student = db.execute("SELECT id FROM students WHERE enrollment = ?", (enrollment,)).fetchone()
        if student:
            student_id = student["id"]
            db.execute("UPDATE students SET name = ?, college = ? WHERE id = ?", (name, college, student_id))
        else:
            cur = db.execute("INSERT INTO students (name, enrollment, college) VALUES (?, ?, ?)", (name, enrollment, college))
            student_id = cur.lastrowid
        db.commit()
        db.close()

        session.clear()
        session["role"] = "student"
        session["student_id"] = student_id
        session["student_name"] = name
        session["student_enrollment"] = enrollment
        session["student_college"] = college
        return json_ok(role="student", redirect="/quiz", message="Registration successful.")
    except sqlite3.IntegrityError:
        db.rollback(); db.close()
        return json_error("This enrollment number is already in use.")
    except Exception:
        db.rollback(); db.close()
        app.logger.exception("Login error")
        return json_error("Unable to complete login.", 500)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# -------------------- ADMIN PAGES --------------------

@app.get("/admin")
@admin_required
def admin():
    db = get_db()
    question_count = db.execute("SELECT COUNT(*) AS count FROM questions").fetchone()["count"]
    student_count = db.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    state = get_quiz_state(db)
    current = get_current_question(db, state)
    db.close()
    ids = get_question_ids(state)
    return render_template("admin.html", question_count=question_count, student_count=student_count,
                           quiz_active=bool(state["active"]), quiz_completed=bool(state["completed"]),
                           current_position=state["current_position"], total_quiz_questions=len(ids),
                           current_question_number=state["current_position"] + 1 if current else 0)


@app.get("/questions")
@admin_required
def questions_page(): return render_template("questions.html")

@app.get("/participants")
@admin_required
def participants_page(): return render_template("participants.html")

@app.get("/quiz-control")
@admin_required
def quiz_control_page(): return render_template("quiz_control.html")

@app.get("/results")
@admin_required
def results_page(): return render_template("results.html")


# -------------------- QUESTIONS API --------------------

@app.get("/api/questions")
@admin_required
def api_questions():
    db = get_db(); rows = db.execute("SELECT id, question, option_1, option_2, option_3, option_4, correct_option, difficulty, time_limit, created_at FROM questions ORDER BY id ASC").fetchall(); db.close()
    return json_ok(questions=[dict(r) for r in rows])


def validate_question(data):
    question = str(data.get("question", "")).strip()
    options = [str(data.get(f"option_{i}", "")).strip() for i in range(1, 5)]
    difficulty = str(data.get("difficulty", "Medium")).strip()
    try:
        correct = int(data.get("correct_option")); time_limit = int(data.get("time_limit", 20))
    except (TypeError, ValueError):
        raise ValueError("Correct answer and time limit must be valid numbers.")
    if not question or any(not o for o in options): raise ValueError("Question and all four options are required.")
    if correct not in range(1, 5): raise ValueError("Correct answer must be option 1, 2, 3 or 4.")
    if difficulty not in {"Easy", "Medium", "Hard"}: raise ValueError("Difficulty must be Easy, Medium or Hard.")
    if not 5 <= time_limit <= 300: raise ValueError("Time limit must be between 5 and 300 seconds.")
    return question, options, correct, difficulty, time_limit


@app.post("/api/questions")
@admin_required
def api_add_question():
    try: question, options, correct, difficulty, time_limit = validate_question(request.get_json(silent=True) or {})
    except ValueError as e: return json_error(str(e))
    db = get_db(); cur = db.execute("INSERT INTO questions (question, option_1, option_2, option_3, option_4, correct_option, difficulty, time_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (question, *options, correct, difficulty, time_limit)); db.commit(); qid = cur.lastrowid; db.close()
    return json_ok(question_id=qid, message="Question added successfully.")


@app.put("/api/questions/<int:question_id>")
@admin_required
def api_update_question(question_id):
    try: question, options, correct, difficulty, time_limit = validate_question(request.get_json(silent=True) or {})
    except ValueError as e: return json_error(str(e))
    db = get_db(); exists = db.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
    if not exists: db.close(); return json_error("Question not found.", 404)
    if get_quiz_state(db)["active"]: db.close(); return json_error("Stop the quiz before editing questions.")
    db.execute("UPDATE questions SET question=?, option_1=?, option_2=?, option_3=?, option_4=?, correct_option=?, difficulty=?, time_limit=? WHERE id=?", (question, *options, correct, difficulty, time_limit, question_id)); db.commit(); db.close()
    return json_ok(message="Question updated successfully.")


@app.delete("/api/questions/<int:question_id>")
@admin_required
def api_delete_question(question_id):
    db = get_db(); state = get_quiz_state(db)
    if state["active"]: db.close(); return json_error("Stop the quiz before deleting questions.")
    exists = db.execute("SELECT id FROM questions WHERE id=?", (question_id,)).fetchone()
    if not exists: db.close(); return json_error("Question not found.", 404)
    db.execute("DELETE FROM questions WHERE id=?", (question_id,)); db.commit(); db.close()
    return json_ok(message="Question deleted successfully.")


@app.post("/api/questions/bulk")
@admin_required
def api_bulk_questions():
    data = request.get_json(silent=True) or {}; questions = data.get("questions")
    if not isinstance(questions, list) or not questions: return json_error("Provide a non-empty questions list.")
    db = get_db(); added = 0; errors = []
    for index, item in enumerate(questions, 1):
        try:
            q, opts, correct, difficulty, tl = validate_question(item)
            db.execute("INSERT INTO questions (question, option_1, option_2, option_3, option_4, correct_option, difficulty, time_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (q, *opts, correct, difficulty, tl)); added += 1
        except Exception as e: errors.append(f"Question {index}: {e}")
    db.commit(); db.close()
    return json_ok(added=added, errors=errors, message=f"{added} question(s) added successfully.")


# -------------------- PARTICIPANTS API --------------------

@app.get("/api/participants")
@admin_required
def api_participants():
    db = get_db(); rows = db.execute("""
        SELECT s.id, s.name, s.enrollment, s.college, s.created_at,
               COALESCE(SUM(a.points), 0) AS score, COUNT(a.id) AS answered
        FROM students s LEFT JOIN answers a ON a.student_id=s.id
        GROUP BY s.id ORDER BY s.id ASC
    """).fetchall(); db.close()
    return json_ok(participants=[dict(r) for r in rows])


@app.put("/api/participants/<int:student_id>")
@admin_required
def api_update_participant(student_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip(); enrollment = str(data.get("enrollment", "")).strip(); college = str(data.get("college", "")).strip()
    if not name or not enrollment or not college: return json_error("Name, enrollment and college are required.")
    if len(name) > 100 or len(enrollment) > 100 or len(college) > 150: return json_error("One or more fields are too long.")
    db = get_db(); exists = db.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone()
    if not exists: db.close(); return json_error("Participant not found.", 404)
    duplicate = db.execute("SELECT id FROM students WHERE enrollment=? AND id<>?", (enrollment, student_id)).fetchone()
    if duplicate: db.close(); return json_error("That enrollment number is already registered.")
    db.execute("UPDATE students SET name=?, enrollment=?, college=? WHERE id=?", (name, enrollment, college, student_id)); db.commit(); db.close()
    return json_ok(message="Participant updated successfully.")


@app.delete("/api/participants/<int:student_id>")
@admin_required
def api_delete_participant(student_id):
    db = get_db(); exists = db.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone()
    if not exists: db.close(); return json_error("Participant not found.", 404)
    if get_quiz_state(db)["active"]: db.close(); return json_error("Stop the quiz before deleting a participant.")
    db.execute("DELETE FROM students WHERE id=?", (student_id,)); db.commit(); db.close()
    return json_ok(message="Participant deleted successfully.")


# -------------------- QUIZ API --------------------

@app.get("/api/quiz/state")
def api_quiz_state():
    db = get_db(); state = get_quiz_state(db); current = get_current_question(db, state); ids = get_question_ids(state)
    payload = {
        "active": bool(state["active"]), "completed": bool(state["completed"]),
        "position": state["current_position"], "total": len(ids),
        "current_number": state["current_position"] + 1 if current else 0,
        "question_started_at": state["question_started_at"], "current_question": public_question(current)
    }
    db.close(); return json_ok(**payload)


@app.post("/api/quiz/start")
@admin_required
def api_quiz_start():
    db = get_db(); ids = [r["id"] for r in db.execute("SELECT id FROM questions ORDER BY id").fetchall()]
    if not ids: db.close(); return json_error("Add at least one question before starting the quiz.")
    random.shuffle(ids); now = time.time()
    db.execute("DELETE FROM answers")
    db.execute("UPDATE quiz_state SET active=1, completed=0, current_position=0, started_at=?, question_started_at=?, question_ids=? WHERE id=1", (now, now, ",".join(map(str, ids))))
    db.commit(); db.close()
    return json_ok(message="Quiz started.", total=len(ids), current_number=1)


@app.post("/api/quiz/next")
@admin_required
def api_quiz_next():
    db = get_db(); state = get_quiz_state(db)
    if not state["active"]: db.close(); return json_error("Quiz is not active.")
    ids = get_question_ids(state); next_position = state["current_position"] + 1
    if next_position >= len(ids):
        db.execute("UPDATE quiz_state SET active=0, completed=1, question_started_at=NULL WHERE id=1")
        db.commit(); db.close()
        return json_ok(finished=True, completed=True, message="Quiz finished. Final results are now visible to everyone.")
    now = time.time()
    db.execute("UPDATE quiz_state SET current_position=?, question_started_at=? WHERE id=1", (next_position, now)); db.commit()
    current = get_current_question(db); db.close()
    return json_ok(finished=False, completed=False, position=next_position, current_number=next_position+1, total=len(ids), current_question=public_question(current))


@app.post("/api/quiz/stop")
@admin_required
def api_quiz_stop():
    db = get_db(); db.execute("UPDATE quiz_state SET active=0, completed=0, question_started_at=NULL WHERE id=1"); db.commit(); db.close()
    return json_ok(message="Quiz stopped. Final results remain hidden until all questions are completed.")


# -------------------- STUDENT PAGES/API --------------------

@app.get("/quiz")
@student_required
def student_quiz():
    return render_template("quiz.html", student_name=session.get("student_name", "Student"))


@app.get("/quiz-board")
def quiz_board():
    return render_template("quiz_board.html")


@app.post("/api/quiz/answer")
@student_required
def api_quiz_answer():
    data = request.get_json(silent=True) or {}
    try: question_id = int(data.get("question_id")); selected_option = int(data.get("selected_option"))
    except (TypeError, ValueError): return json_error("Invalid answer data.")
    if selected_option not in range(1, 5): return json_error("Invalid option.")
    db = get_db(); state = get_quiz_state(db)
    if not state["active"]: db.close(); return json_error("The quiz is not currently active.")
    current = get_current_question(db, state)
    if not current or current["id"] != question_id: db.close(); return json_error("This question is no longer active.")
    student_id = session.get("student_id")
    existing = db.execute("SELECT id FROM answers WHERE student_id=? AND question_id=?", (student_id, question_id)).fetchone()
    if existing: db.close(); return json_error("You have already answered this question.")
    correct = int(selected_option == current["correct_option"]); points = correct
    db.execute("INSERT INTO answers (student_id, question_id, selected_option, is_correct, points) VALUES (?, ?, ?, ?, ?)", (student_id, question_id, selected_option, correct, points)); db.commit()
    score = db.execute("SELECT COALESCE(SUM(points),0) AS score FROM answers WHERE student_id=?", (student_id,)).fetchone()["score"]
    db.close(); return json_ok(correct=bool(correct), points=points, score=score)


@app.get("/api/my-score")
@student_required
def api_my_score():
    db = get_db(); student_id = session["student_id"]
    row = db.execute("SELECT COALESCE(SUM(points),0) AS score, COUNT(*) AS answered FROM answers WHERE student_id=?", (student_id,)).fetchone(); db.close()
    return json_ok(score=row["score"], answered=row["answered"])


# -------------------- RESULTS --------------------

@app.get("/api/final-results")
def api_final_results():
    db = get_db(); state = get_quiz_state(db)
    if not state["completed"]:
        db.close(); return json_error("Final results are not available yet.", 403)
    rows = leaderboard_rows(db); total = len(get_question_ids(state)); db.close()
    return json_ok(results=build_results(rows), total_questions=total)


@app.get("/api/results")
@admin_required
def api_results():
    db = get_db(); state = get_quiz_state(db); rows = leaderboard_rows(db); total = len(get_question_ids(state)); completed = bool(state["completed"]); db.close()
    return json_ok(results=build_results(rows), total_questions=total, completed=completed, active=bool(state["active"]))


@app.errorhandler(404)
def not_found(error):
    if is_api_request(): return json_error("Endpoint not found.", 404)
    return "Page not found.", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
