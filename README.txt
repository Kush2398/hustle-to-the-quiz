# HUSTLE TO THE QUIZ

GCET Diploma IT event platform for Level 1 — Guess the Logo / live symbol-answer quiz.

## Files

- app.py — Flask backend, SQLite database, login, question bank, quiz control, scoring and APIs.
- templates/index.html — single login page.
- templates/admin.html — admin dashboard.
- templates/questions.html — question management + bulk JSON import.
- templates/participants.html — participant list.
- templates/quiz_control.html — start/next/stop controls.
- templates/quiz_board.html — projector/smart-board display.
- templates/quiz.html — student phone interface.
- templates/results.html — leaderboard/results.
- database.db — created automatically when the app starts.

## Install

Open the project folder in the VS Code terminal:

    python -m pip install flask

## Run

    python app.py

Then open:

    http://127.0.0.1:5000/

## Default admin login

Name / Admin ID:
    admin

Enrollment No. / Password:
    admin123

For a real deployment, change these using environment variables:

    QUIZ_ADMIN_ID
    QUIZ_ADMIN_PASSWORD
    SECRET_KEY

## Quiz flow

1. Admin logs in.
2. Admin opens Question Management.
3. Add questions individually or use Bulk Add.
4. Admin opens Quiz Control and starts a new quiz.
5. Open /quiz-board on the projector/smart board.
6. Students log in from their phones and remain on /quiz.
7. The board displays the question and four option symbols:
   ◆  ●  ▲  ■
8. Students select the matching symbol on their phone.
9. Correct answer = +1.
10. Wrong answer = 0.
11. Admin presses NEXT QUESTION to move the board to the next question.
12. Results page shows the leaderboard.

## Bulk question JSON format

[
  {
    "question": "Which language is used to structure a web page?",
    "option_1": "HTML",
    "option_2": "Python",
    "option_3": "SQL",
    "option_4": "C",
    "correct_option": 1,
    "difficulty": "Easy",
    "time_limit": 20
  }
]

No questions are built into the application. The admin creates the question bank.
