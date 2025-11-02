import spacy
import random
import re
import uuid
from collections import Counter
import fitz
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any
import json
import sqlite3

import en_core_web_md

app = FastAPI(title="MCQ Generator API")

try:
    nlp = en_core_web_md.load()
except Exception as e:
    print(f"spacy not loaded: {e}")
    raise

def init_db():
    conn = sqlite3.connect('quiz_storage.db')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        quiz_id TEXT PRIMARY KEY,
        correct_answers TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

@app.post("/generate-quiz/")
async def generate_quiz(
    num_questions: int = Form(...),
    file: UploadFile = File(...)
):
    pdf_content = await file.read()
    
    text = extract_text_from_pdf(pdf_content)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF.")
        
    mcqs = generate_mcqs_advanced(text, num_questions)
    if not mcqs:
        raise HTTPException(status_code=404, detail="Could not generate MCQs from the provided text.")

    quiz_id = str(uuid.uuid4())
    correct_answers = {}
    questions_for_user = []
    
    for i, (question, options, correct_char) in enumerate(mcqs):
        questions_for_user.append({
            "id": i,
            "question": question,
            "options": options
        })
        correct_answers[str(i)] = correct_char

    try:
        conn = sqlite3.connect('quiz_storage.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO quizzes (quiz_id, correct_answers) VALUES (?, ?)",
            (quiz_id, json.dumps(correct_answers))
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    
    return {"quiz_id": quiz_id, "questions": questions_for_user}

@app.post("/submit-quiz/")
async def submit_quiz(
    quiz_id: str = Form(...),
    answers: str = Form(...) 
):
    correct_answers_json = None
    try:
        conn = sqlite3.connect('quiz_storage.db')
        cursor = conn.cursor()
        cursor.execute("SELECT correct_answers FROM quizzes WHERE quiz_id = ?", (quiz_id,))
        result = cursor.fetchone()
        if result:
            correct_answers_json = result[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()
    
    if not correct_answers_json:
        raise HTTPException(status_code=404, detail="Quiz ID not found or expired.")

    try:
        correct_answers = json.loads(correct_answers_json)
        user_answers = json.loads(answers)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid answers format.")

    score = 0
    total = len(correct_answers)
    results = {}

    for q_id, correct_ans_char in correct_answers.items():
        user_ans_char = user_answers.get(q_id)
        is_correct = (user_ans_char == correct_ans_char)
        if is_correct:
            score += 1
        
        results[q_id] = {
            "user_answer": user_ans_char,
            "correct_answer": correct_ans_char,
            "is_correct": is_correct
        }

    percentage = (score / total) * 100 if total > 0 else 0
    
    return {
        "score": score,
        "total": total,
        "percentage": round(percentage, 2),
        "results": results,
    }

def generate_mcqs_advanced(text, num_questions=5):
    if not text or not isinstance(text, str):
        return []
    doc = nlp(text)

    potential_distractors = [ent.text.lower() for ent in doc.ents if ent.label_ not in ['CARDINAL', 'DATE', 'QUANTITY']]
    nouns = [token.text.lower() for token in doc if token.pos_ == 'NOUN' and token.is_stop == False]
    potential_distractors.extend(list(set(nouns)))
    potential_distractors = list(set(potential_distractors))
 
    sentences = list(doc.sents)
     
    num_questions = min(num_questions, len(sentences))
     
    random.shuffle(sentences)
     
    sentences_to_try = sentences 
     
    mcqs = []

    for sent in sentences_to_try:
        if len(mcqs) == num_questions:
            break
        subject = None
         
        if sent.ents:
            valid_ents = [ent for ent in sent.ents if ent.label_ not in ['CARDINAL', 'DATE', 'QUANTITY']]
             
            if valid_ents:
                subject = random.choice(valid_ents)
        else:
            sent_nouns = [token for token in sent if token.pos_ == 'NOUN' and not token.is_stop]
            if sent_nouns:
                noun_counts = Counter(token.text for token in sent_nouns)
                subject_text = noun_counts.most_common(1)[0][0]
                subject = next((token for token in sent if token.text == subject_text), None)

        if not subject:
            continue
        question_stem = re.sub(r'\b' + re.escape(subject.text) + r'\b', "______", sent.text, count=1)

        if question_stem == sent.text:
            continue
             
        answer_choices = [subject.text]
         
        distractors = []
        subject_token = nlp(subject.text)[0] 
         
        sorted_distractors = sorted(
            potential_distractors,
            key=lambda x: subject_token.similarity(nlp(x)[0]) if x and nlp(x).has_vector else 0,
            reverse=True
        )

        for dist in sorted_distractors:
            if dist.lower() != subject.text.lower() and len(distractors) < 3:
                distractors.append(dist)
         
        remaining_distractors = [d for d in potential_distractors if d.lower() != subject.text.lower() and d not in distractors]
        while len(distractors) < 3 and remaining_distractors:
            distractors.append(random.choice(remaining_distractors))
            distractors = list(set(distractors))
            remaining_distractors = [d for d in remaining_distractors if d not in distractors]

        answer_choices.extend(distractors)
        random.shuffle(answer_choices)
         
        if len(answer_choices) < 2:
            continue

        correct_answer_char = chr(65 + answer_choices.index(subject.text))
        
        options_dict = {chr(65 + i): option for i, option in enumerate(answer_choices)}
        mcqs.append((question_stem, options_dict, correct_answer_char))

    return mcqs

def extract_text_from_pdf(file_stream) -> str:
    text = ""
    try:
        with fitz.open(stream=file_stream, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF processing error: {e}")
    return text