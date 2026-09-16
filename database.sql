CREATE DATABASE IF NOT EXISTS hustle_to_the_quiz_5
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hustle_to_the_quiz_5;

SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS answers;
DROP TABLE IF EXISTS event_scores;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS quiz_state;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS events;
SET FOREIGN_KEY_CHECKS=1;

CREATE TABLE events (
 id INT AUTO_INCREMENT PRIMARY KEY,
 event_key VARCHAR(100) NOT NULL UNIQUE,
 event_name VARCHAR(150) NOT NULL,
 description TEXT,
 event_order INT NOT NULL,
 status ENUM('LOCKED','LIVE','COMPLETED') NOT NULL DEFAULT 'LOCKED',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT INTO events(event_key,event_name,description,event_order) VALUES
('logo_riddle','GUESS THE LOGO','Logo riddles and brand clues.',1),
('encryption_decryption','CRACK THE CODE','Encryption & decryption challenges.',2),
('guess_output','GUESS THE OUTPUT','Predict the output of code.',3),
('solve_error','SOLVE THE ERROR','Find the error and choose the fix.',4),
('final_quiz','FINAL QUIZ','The ultimate technology quiz.',5);

CREATE TABLE students (
 id INT AUTO_INCREMENT PRIMARY KEY,
 name VARCHAR(150) NOT NULL,
 enrollment VARCHAR(100) NOT NULL UNIQUE,
 college VARCHAR(255) NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE questions (
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
) ENGINE=InnoDB;

CREATE TABLE answers (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 student_id INT NOT NULL,
 event_id INT NOT NULL,
 question_id INT NOT NULL,
 selected_option TINYINT NOT NULL,
 is_correct TINYINT NOT NULL DEFAULT 0,
 points INT NOT NULL DEFAULT 0,
 answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_student_event_question(student_id,event_id,question_id),
 FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
 FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
 FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE event_scores (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 student_id INT NOT NULL,
 event_id INT NOT NULL,
 score INT NOT NULL DEFAULT 0,
 total_questions INT NOT NULL DEFAULT 0,
 correct_answers INT NOT NULL DEFAULT 0,
 wrong_answers INT NOT NULL DEFAULT 0,
 completed TINYINT NOT NULL DEFAULT 0,
 completed_at TIMESTAMP NULL,
 UNIQUE KEY uq_student_event(student_id,event_id),
 FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
 FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE quiz_state (
 id TINYINT PRIMARY KEY,
 active TINYINT NOT NULL DEFAULT 0,
 current_event_id INT NULL,
 current_position INT NOT NULL DEFAULT 0,
 current_question_id INT NULL,
 started_at DOUBLE NULL,
 question_started_at DOUBLE NULL,
 question_ids TEXT NULL,
 status ENUM('IDLE','LIVE','STOPPED','COMPLETED') NOT NULL DEFAULT 'IDLE',
 results_visible TINYINT NOT NULL DEFAULT 0,
 FOREIGN KEY(current_event_id) REFERENCES events(id) ON DELETE SET NULL,
 FOREIGN KEY(current_question_id) REFERENCES questions(id) ON DELETE SET NULL
) ENGINE=InnoDB;

INSERT INTO quiz_state(id,active,current_event_id,current_position,current_question_id,
started_at,question_started_at,question_ids,status,results_visible)
VALUES(1,0,NULL,0,NULL,NULL,NULL,'','IDLE',0);
