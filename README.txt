HUSTLE TO THE QUIZ - LEVEL 1

FINAL BEHAVIOR
1. Admin starts the quiz.
2. Students answer on their phones using only ◆ ● ▲ ■.
3. Students see their own running score during the quiz.
4. Admin can monitor all participants and scores.
5. Admin can edit or delete participants when the quiz is not running.
6. Admin clicks NEXT QUESTION after each question.
7. After NEXT QUESTION is pressed on the last question, the quiz becomes COMPLETED.
8. The final leaderboard automatically appears on the main Quiz Board and on every student phone.
9. No admin "show results" button is required.
10. If admin uses STOP before the last question, final results remain hidden.

IMPORTANT TESTING RULE
Do not log in as admin and student in the same browser profile. Flask sessions use a browser cookie. Use the admin laptop/browser for admin and separate phones/browsers for students.

RENDER
Build command:
pip install -r requirements.txt

Start command:
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120

DATABASE NOTE
This version uses SQLite. Render Free web-service storage is ephemeral, so use a persistent database for a real event if you need data to survive redeploys/restarts.
