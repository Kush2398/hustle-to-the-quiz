from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import os, random, time, json
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

ADMIN_ID = os.environ.get("QUIZ_ADMIN_ID", "admin")
ADMIN_PASSWORD = os.environ.get("QUIZ_ADMIN_PASSWORD", "admin123")

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Kush230908.")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "hustle_to_the_quiz_5")

EVENTS = [
    ("logo_riddle", "GUESS THE LOGO", "Logo riddles and brand clues.", 1),
    ("encryption_decryption", "CRACK THE CODE", "Encryption & decryption challenges.", 2),
    ("guess_output", "GUESS THE OUTPUT", "Predict the output of code.", 3),
    ("solve_error", "SOLVE THE ERROR", "Find the error and choose the fix.", 4),
    ("final_quiz", "FINAL QUIZ", "The ultimate technology quiz.", 5),
]
SYMBOLS = ["◆", "●", "▲", "■"]

def connect_server():
    return pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                           password=MYSQL_PASSWORD, charset="utf8mb4",
                           cursorclass=DictCursor, autocommit=True)

def db():
    return pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                           password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
                           charset="utf8mb4", cursorclass=DictCursor,
                           autocommit=False)

def init_db():
    c = connect_server()
    try:
        with c.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    finally:
        c.close()
    c = db()
    try:
        with c.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS events(
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_key VARCHAR(100) NOT NULL UNIQUE,
                event_name VARCHAR(150) NOT NULL,
                description TEXT NULL,
                event_order INT NOT NULL,
                status ENUM('LOCKED','LIVE','COMPLETED') NOT NULL DEFAULT 'LOCKED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB""")
            cur.execute("""CREATE TABLE IF NOT EXISTS students(
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                enrollment VARCHAR(100) NOT NULL UNIQUE,
                college VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB""")
            cur.execute("""CREATE TABLE IF NOT EXISTS questions(
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id INT NOT NULL,
                question TEXT NOT NULL,
                option_1 TEXT NOT NULL, option_2 TEXT NOT NULL,
                option_3 TEXT NOT NULL, option_4 TEXT NOT NULL,
                correct_option TINYINT NOT NULL,
                difficulty ENUM('Easy','Medium','Hard') NOT NULL DEFAULT 'Medium',
                time_limit INT NOT NULL DEFAULT 20,
                question_order INT NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
                INDEX idx_questions_event(event_id)
            ) ENGINE=InnoDB""")
            cur.execute("""CREATE TABLE IF NOT EXISTS answers(
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL, event_id INT NOT NULL, question_id INT NOT NULL,
                selected_option TINYINT NOT NULL, is_correct TINYINT NOT NULL DEFAULT 0,
                points INT NOT NULL DEFAULT 0, answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_student_event_question(student_id,event_id,question_id),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            ) ENGINE=InnoDB""")
            cur.execute("""CREATE TABLE IF NOT EXISTS quiz_state(
                id TINYINT PRIMARY KEY,
                active TINYINT NOT NULL DEFAULT 0,
                current_event_id INT NULL,
                current_position INT NOT NULL DEFAULT 0,
                current_question_id INT NULL,
                started_at DOUBLE NULL, question_started_at DOUBLE NULL,
                question_ids TEXT NULL,
                status ENUM('IDLE','LIVE','STOPPED','COMPLETED') NOT NULL DEFAULT 'IDLE',
                results_visible TINYINT NOT NULL DEFAULT 0,
                FOREIGN KEY(current_event_id) REFERENCES events(id) ON DELETE SET NULL,
                FOREIGN KEY(current_question_id) REFERENCES questions(id) ON DELETE SET NULL
            ) ENGINE=InnoDB""")
            cur.execute("""CREATE TABLE IF NOT EXISTS event_scores(
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL, event_id INT NOT NULL,
                score INT NOT NULL DEFAULT 0, total_questions INT NOT NULL DEFAULT 0,
                correct_answers INT NOT NULL DEFAULT 0, wrong_answers INT NOT NULL DEFAULT 0,
                completed TINYINT NOT NULL DEFAULT 0, completed_at TIMESTAMP NULL,
                UNIQUE KEY uq_student_event(student_id,event_id),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            ) ENGINE=InnoDB""")
            for key,name,desc,order in EVENTS:
                cur.execute("""INSERT INTO events(event_key,event_name,description,event_order)
                               VALUES(%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE event_name=VALUES(event_name),
                               description=VALUES(description),event_order=VALUES(event_order)""",
                            (key,name,desc,order))
            cur.execute("SELECT id FROM quiz_state WHERE id=1")
            if not cur.fetchone():
                cur.execute("""INSERT INTO quiz_state(id,active,current_event_id,current_position,current_question_id,
                    started_at,question_started_at,question_ids,status,results_visible)
                    VALUES(1,0,NULL,0,NULL,NULL,NULL,'','IDLE',0)""")
        c.commit()
    finally:
        c.close()

init_db()

def ok(**x): return jsonify(success=True, **x)
def err(msg, code=400): return jsonify(success=False, message=msg), code
def api(): return request.path.startswith("/api/")

def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if session.get("role")!="admin":
            return err("Admin session expired. Please log in again.",401) if api() else redirect(url_for("index"))
        return f(*a,**k)
    return w

def student_required(f):
    @wraps(f)
    def w(*a,**k):
        if session.get("role")!="student":
            return err("Student session expired. Please log in again.",401) if api() else redirect(url_for("index"))
        return f(*a,**k)
    return w

def state(cur):
    cur.execute("""SELECT qs.*, e.event_key, e.event_name FROM quiz_state qs
                   LEFT JOIN events e ON e.id=qs.current_event_id WHERE qs.id=1""")
    return cur.fetchone()

def ids(s):
    try: return [int(x) for x in (s.get("question_ids") or "").split(",") if x.strip()]
    except: return []

def current_question(cur, s):
    qids=ids(s)
    if not s or not s["active"] or not qids: return None
    pos=int(s["current_position"])
    if pos<0 or pos>=len(qids): return None
    cur.execute("SELECT * FROM questions WHERE id=%s",(qids[pos],))
    return cur.fetchone()

def public_q(q):
    if not q:return None
    return {"id":q["id"],"question":q["question"],
            "options":[q["option_1"],q["option_2"],q["option_3"],q["option_4"]],
            "difficulty":q["difficulty"],"time_limit":q["time_limit"],"symbols":SYMBOLS}

def leaderboard(cur, event_id=None):
    if event_id:
        cur.execute("""SELECT s.id,s.name,s.enrollment,s.college,
                    COALESCE(SUM(a.points),0) score,
                    COALESCE(SUM(a.is_correct),0) correct,COUNT(a.id) answered
                    FROM students s LEFT JOIN answers a
                    ON a.student_id=s.id AND a.event_id=%s
                    GROUP BY s.id,s.name,s.enrollment,s.college
                    ORDER BY score DESC,correct DESC,s.name ASC,s.enrollment ASC""",(event_id,))
    else:
        cur.execute("""SELECT s.id,s.name,s.enrollment,s.college,
                    COALESCE(SUM(a.points),0) score,
                    COALESCE(SUM(a.is_correct),0) correct,COUNT(a.id) answered
                    FROM students s LEFT JOIN answers a ON a.student_id=s.id
                    GROUP BY s.id,s.name,s.enrollment,s.college
                    ORDER BY score DESC,correct DESC,s.name ASC,s.enrollment ASC""")
    rows=cur.fetchall()
    for i,r in enumerate(rows,1): r["rank"]=i
    return rows

@app.get("/")
def index(): return render_template("index.html")

@app.post("/login")
def login():
    data=request.get_json(silent=True) or request.form
    name=str(data.get("name","")).strip()
    enrollment=str(data.get("enrollment","")).strip()
    college=str(data.get("college","")).strip()
    if not name or not enrollment: return err("Please enter your name and enrollment/password.")
    if name==ADMIN_ID and enrollment==ADMIN_PASSWORD:
        session.clear(); session.update(role="admin",admin_id=name)
        return ok(role="admin",redirect="/admin")
    if not college:return err("Please enter your college name.")
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE enrollment=%s",(enrollment,))
            r=cur.fetchone()
            if r:
                sid=r["id"];cur.execute("UPDATE students SET name=%s,college=%s WHERE id=%s",(name,college,sid))
            else:
                cur.execute("INSERT INTO students(name,enrollment,college) VALUES(%s,%s,%s)",(name,enrollment,college));sid=cur.lastrowid
        c.commit()
        session.clear();session.update(role="student",student_id=sid,student_name=name,student_enrollment=enrollment)
        return ok(role="student",redirect="/dashboard")
    finally:c.close()

@app.get("/logout")
def logout():session.clear();return redirect(url_for("index"))

@app.get("/dashboard")
@student_required
def dashboard():return render_template("dashboard.html",student_name=session.get("student_name","Student"))

@app.get("/quiz")
@student_required
def quiz():return render_template("quiz.html",student_name=session.get("student_name","Student"))

@app.get("/leaderboard")
@student_required
def leaderboard_page():return render_template("leaderboard.html")

@app.get("/quiz-board")
def board():return render_template("quiz_board.html")

@app.get("/admin")
@admin_required
def admin_page():
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM students");sc=cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) n FROM questions");qc=cur.fetchone()["n"]
            cur.execute("SELECT * FROM events ORDER BY event_order");events=cur.fetchall()
            s=state(cur)
        return render_template("admin.html",students=sc,questions=qc,events=events,state=s)
    finally:c.close()

@app.get("/participants")
@admin_required
def participants():return render_template("participants.html")

@app.get("/questions")
@admin_required
def questions_page():return render_template("questions.html")

@app.get("/quiz-control")
@admin_required
def control():return render_template("quiz_control.html")

@app.get("/results")
@admin_required
def results_page():return render_template("results.html")

@app.get("/api/health")
def health():
    try:
        c=db()
        with c.cursor() as cur:cur.execute("SELECT 1")
        c.close();return ok(database="connected")
    except Exception as e:return err("MySQL connection failed: "+str(e),500)

@app.get("/api/events")
def api_events():
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM events ORDER BY event_order")
            ev=cur.fetchall()
            s=state(cur)
            for e in ev:
                cur.execute("SELECT COUNT(*) n FROM questions WHERE event_id=%s",(e["id"],));e["question_count"]=cur.fetchone()["n"]
            return ok(events=ev,current_event_id=s["current_event_id"],active=bool(s["active"]),status=s["status"])
    finally:c.close()

@app.get("/api/questions")
@admin_required
def api_questions():
    event_id=request.args.get("event_id",type=int)
    c=db()
    try:
        with c.cursor() as cur:
            if event_id:
                cur.execute("""SELECT q.*,e.event_name FROM questions q JOIN events e ON e.id=q.event_id
                               WHERE q.event_id=%s ORDER BY q.question_order,q.id""",(event_id,))
            else:
                cur.execute("""SELECT q.*,e.event_name FROM questions q JOIN events e ON e.id=q.event_id
                               ORDER BY e.event_order,q.question_order,q.id""")
            return ok(questions=cur.fetchall())
    finally:c.close()

def validate_q(d):
    q=str(d.get("question","")).strip()
    opts=[str(d.get(f"option_{i}","")).strip() for i in range(1,5)]
    try:eid=int(d.get("event_id"));co=int(d.get("correct_option"));tl=int(d.get("time_limit",20))
    except:raise ValueError("Event, correct option and time limit are required.")
    diff=str(d.get("difficulty","Medium"))
    if not q or any(not x for x in opts):raise ValueError("Question and all four options are required.")
    if co not in (1,2,3,4):raise ValueError("Correct option must be 1-4.")
    if diff not in ("Easy","Medium","Hard"):raise ValueError("Invalid difficulty.")
    if tl<5 or tl>300:raise ValueError("Time limit must be 5-300 seconds.")
    return eid,q,opts,co,diff,tl

@app.post("/api/questions")
@admin_required
def add_q():
    try:eid,q,o,co,diff,tl=validate_q(request.get_json(silent=True) or {})
    except ValueError as e:return err(str(e))
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM events WHERE id=%s",(eid,))
            if not cur.fetchone():return err("Event not found.")
            cur.execute("SELECT COALESCE(MAX(question_order),0)+1 n FROM questions WHERE event_id=%s",(eid,))
            order=cur.fetchone()["n"]
            cur.execute("""INSERT INTO questions(event_id,question,option_1,option_2,option_3,option_4,
                correct_option,difficulty,time_limit,question_order) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (eid,q,*o,co,diff,tl,order))
        c.commit();return ok(message="Question added.",question_id=cur.lastrowid)
    finally:c.close()

@app.put("/api/questions/<int:qid>")
@admin_required
def update_q(qid):
    try:eid,q,o,co,diff,tl=validate_q(request.get_json(silent=True) or {})
    except ValueError as e:return err(str(e))
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("""UPDATE questions SET event_id=%s,question=%s,option_1=%s,option_2=%s,
                option_3=%s,option_4=%s,correct_option=%s,difficulty=%s,time_limit=%s WHERE id=%s""",
                (eid,q,*o,co,diff,tl,qid))
        c.commit();return ok(message="Question updated.")
    finally:c.close()

@app.delete("/api/questions/<int:qid>")
@admin_required
def delete_q(qid):
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur)
            if s["active"]:return err("Stop the active event before deleting questions.")
            cur.execute("DELETE FROM questions WHERE id=%s",(qid,))
        c.commit();return ok(message="Question deleted.")
    finally:c.close()

@app.post("/api/questions/bulk")
@admin_required
def bulk_q():
    data=request.get_json(silent=True) or {};items=data.get("questions")
    if not isinstance(items,list) or not items:return err("Provide a non-empty questions array.")
    c=db();added=0;errors=[]
    try:
        with c.cursor() as cur:
            for i,d in enumerate(items,1):
                try:
                    eid,q,o,co,diff,tl=validate_q(d)
                    cur.execute("SELECT id FROM events WHERE id=%s",(eid,))
                    if not cur.fetchone():raise ValueError("Event not found.")
                    cur.execute("SELECT COALESCE(MAX(question_order),0)+1 n FROM questions WHERE event_id=%s",(eid,))
                    order=cur.fetchone()["n"]
                    cur.execute("""INSERT INTO questions(event_id,question,option_1,option_2,option_3,option_4,
                        correct_option,difficulty,time_limit,question_order) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (eid,q,*o,co,diff,tl,order));added+=1
                except Exception as e:errors.append(f"Question {i}: {e}")
        c.commit();return ok(added=added,errors=errors)
    finally:c.close()

@app.get("/api/participants")
@admin_required
def api_participants():
    c=db()
    try:
        with c.cursor() as cur:
            rows=leaderboard(cur)
            return ok(participants=rows)
    finally:c.close()

@app.put("/api/participants/<int:sid>")
@admin_required
def edit_participant(sid):
    d=request.get_json(silent=True) or {}
    n=str(d.get("name","")).strip();en=str(d.get("enrollment","")).strip();col=str(d.get("college","")).strip()
    if not n or not en or not col:return err("Name, enrollment and college are required.")
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE enrollment=%s AND id<>%s",(en,sid))
            if cur.fetchone():return err("Enrollment already belongs to another participant.")
            cur.execute("UPDATE students SET name=%s,enrollment=%s,college=%s WHERE id=%s",(n,en,col,sid))
        c.commit();return ok(message="Participant updated.")
    except pymysql.err.IntegrityError:
        c.rollback();return err("Enrollment must be unique.")
    finally:c.close()

@app.delete("/api/participants/<int:sid>")
@admin_required
def delete_participant(sid):
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur)
            if s["active"]:return err("Stop the active event before deleting participants.")
            cur.execute("DELETE FROM students WHERE id=%s",(sid,))
        c.commit();return ok(message="Participant deleted.")
    finally:c.close()

@app.post("/api/quiz/start")
@admin_required
def start_event():
    d=request.get_json(silent=True) or {}
    try:eid=int(d.get("event_id"))
    except:return err("Choose an event.")
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE id=%s",(eid,));ev=cur.fetchone()
            if not ev:return err("Event not found.")
            cur.execute("SELECT id FROM questions WHERE event_id=%s ORDER BY question_order,id",(eid,))
            qids=[x["id"] for x in cur.fetchall()]
            if not qids:return err("Add questions to this event first.")
            cur.execute("UPDATE events SET status='LOCKED' WHERE status='LIVE'")
            cur.execute("UPDATE events SET status='LIVE' WHERE id=%s",(eid,))
            cur.execute("DELETE FROM answers WHERE event_id=%s",(eid,))
            now=time.time();random.shuffle(qids)
            cur.execute("""UPDATE quiz_state SET active=1,current_event_id=%s,current_position=0,
                current_question_id=%s,started_at=%s,question_started_at=%s,question_ids=%s,
                status='LIVE',results_visible=0 WHERE id=1""",
                (eid,qids[0],now,now,",".join(map(str,qids))))
        c.commit();return ok(message="Event started.",event=ev,total=len(qids))
    finally:c.close()

@app.post("/api/quiz/next")
@admin_required
def next_q():
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur)
            if not s["active"]:return err("No event is active.")
            qids=ids(s);n=int(s["current_position"])+1
            if n>=len(qids):
                cur.execute("UPDATE events SET status='COMPLETED' WHERE id=%s",(s["current_event_id"],))
                cur.execute("""UPDATE quiz_state SET active=0,current_question_id=NULL,
                    status='COMPLETED',results_visible=1,question_started_at=NULL WHERE id=1""")
                c.commit();return ok(finished=True,message="Event completed. Leaderboard is visible everywhere.")
            now=time.time()
            cur.execute("UPDATE quiz_state SET current_position=%s,current_question_id=%s,question_started_at=%s WHERE id=1",
                        (n,qids[n],now))
        c.commit();return ok(finished=False,current_number=n+1,total=len(qids))
    finally:c.close()

@app.post("/api/quiz/stop")
@admin_required
def stop():
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur)
            if not s["started_at"]:return err("No event has been started.")
            if s["current_event_id"]:cur.execute("UPDATE events SET status='COMPLETED' WHERE id=%s",(s["current_event_id"],))
            cur.execute("""UPDATE quiz_state SET active=0,current_question_id=NULL,status='STOPPED',
                results_visible=1,question_started_at=NULL WHERE id=1""")
        c.commit();return ok(message="Event stopped. Leaderboard is now visible on every device.")
    finally:c.close()

@app.get("/api/quiz/state")
def quiz_state_api():
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur);q=current_question(cur,s);qids=ids(s)
            return ok(active=bool(s["active"]),status=s["status"],results_visible=bool(s["results_visible"]),
                      current_event_id=s["current_event_id"],event_name=s["event_name"],
                      position=s["current_position"],total=len(qids),
                      current_number=(s["current_position"]+1 if q else 0),
                      question_started_at=s["question_started_at"],
                      current_question=public_q(q))
    finally:c.close()

@app.post("/api/quiz/answer")
@student_required
def answer():
    d=request.get_json(silent=True) or {}
    try:qid=int(d.get("question_id"));sel=int(d.get("selected_option"))
    except:return err("Invalid answer.")
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur);q=current_question(cur,s)
            if not s["active"] or not q:return err("No question is active.")
            if q["id"]!=qid:return err("This question is no longer active.")
            cur.execute("SELECT id FROM answers WHERE student_id=%s AND event_id=%s AND question_id=%s",
                        (session["student_id"],s["current_event_id"],qid))
            if cur.fetchone():return err("You already answered this question.")
            correct=int(sel==q["correct_option"]);pts=correct
            cur.execute("""INSERT INTO answers(student_id,event_id,question_id,selected_option,is_correct,points)
                           VALUES(%s,%s,%s,%s,%s,%s)""",
                        (session["student_id"],s["current_event_id"],qid,sel,correct,pts))
            cur.execute("SELECT COALESCE(SUM(points),0) score FROM answers WHERE student_id=%s AND event_id=%s",
                        (session["student_id"],s["current_event_id"]))
            score=cur.fetchone()["score"]
        c.commit();return ok(correct=bool(correct),points=pts,score=score)
    finally:c.close()

@app.get("/api/my-score")
@student_required
def my_score():
    c=db()
    try:
        with c.cursor() as cur:
            cur.execute("""SELECT COALESCE(SUM(points),0) score,COUNT(*) answered
                           FROM answers WHERE student_id=%s""",(session["student_id"],))
            allr=cur.fetchone()
            cur.execute("""SELECT e.event_name,COALESCE(SUM(a.points),0) score
                           FROM events e LEFT JOIN answers a ON a.event_id=e.id AND a.student_id=%s
                           GROUP BY e.id,e.event_name,e.event_order ORDER BY e.event_order""",(session["student_id"],))
            return ok(score=allr["score"],answered=allr["answered"],events=cur.fetchall())
    finally:c.close()

@app.get("/api/leaderboard")
def api_leaderboard():
    event_id=request.args.get("event_id",type=int)
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur)
            rows=leaderboard(cur,event_id)
            total=0
            if event_id:
                cur.execute("SELECT COUNT(*) n FROM questions WHERE event_id=%s",(event_id,))
            elif s["current_event_id"]:
                cur.execute("SELECT COUNT(*) n FROM questions WHERE event_id=%s",(s["current_event_id"],))
            else:
                cur.execute("SELECT COUNT(*) n FROM questions")
            total=cur.fetchone()["n"]
            return ok(results=rows,total_questions=total,event_id=event_id or s["current_event_id"],
                      results_visible=bool(s["results_visible"]),status=s["status"])
    finally:c.close()

@app.get("/api/final-results")
def final_results():
    c=db()
    try:
        with c.cursor() as cur:
            s=state(cur)
            if not s["results_visible"]:return err("Results are not visible yet.",403)
            rows=leaderboard(cur,s["current_event_id"])
            cur.execute("SELECT event_name FROM events WHERE id=%s",(s["current_event_id"],))
            ev=cur.fetchone()
            return ok(results=rows,event_name=ev["event_name"] if ev else "RESULTS")
    finally:c.close()

@app.errorhandler(404)
def not_found(e):return err("Endpoint not found.",404) if api() else ("Page not found.",404)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)
