# Question-MCQs-Generator

# AI-Powered MCQ Generator API

##  Project Overview

This project is a **FastAPI** application that automatically generates Multiple Choice Questions (MCQs) from any given PDF document.

It serves as an "EdTech" (Educational Technology) tool that helps educators, students, and content creators quickly build quizzes from study materials (like textbook chapters, articles, or research papers).

The API provides two main endpoints:
1.  `/generate-quiz/`: Accepts a PDF file and a number of questions. It returns a unique `quiz_id` and a list of questions with their options.
2.  `/submit-quiz/`: Accepts the `quiz_id` and the user's answers, checks them against the stored correct answers, and returns a final score and detailed results.

##  Core Logic & Methodology

This system uses a sophisticated NLP pipeline to generate high-quality, relevant questions and distractors.

1.  **API Layer (FastAPI):**
    * The API is built using **FastAPI**, handling file uploads (`UploadFile`), form data (`Form`), and JSON responses.

2.  **Text Extraction (PyMuPDF):**
    * The `/generate-quiz/` endpoint receives a `.pdf` file.
    * The `fitz (PyMuPDF)` library is used to open the PDF stream and extract raw text content from all pages.

3.  **NLP Core (spaCy):**
    * The extracted text is processed using **spaCy** (specifically the `en_core_web_md` model, which includes word vectors).
    * **Answer Selection:** The code iterates through sentences and identifies potential answers by looking for:
        1.  **Named Entities** (like  `PERSON`, `ORG`), ignoring non-relevant ones (like `CARDINAL`).
        2.  If no entities are found, it falls back to finding the **most common Noun** in the sentence.
    * **Question Stem Generation:** The selected answer (e.g., "The Milky Way") is replaced with "______" in the original sentence using **Regex (`re`)** to create the question.

4.  **Intelligent Distractor Generation:**
    * This is the core feature. Instead of random words, the API generates plausible distractors:
    * A "bank" of all nouns and valid entities from the *entire text* is created.
    * Using `spacy`'s built-in **word vector similarity** (`token.similarity()`), this bank is sorted based on semantic similarity to the correct answer.
    * The top 3 most similar (but not identical) words are chosen as distractors.
    * If not enough similar words are found, it fills the remaining slots randomly from the bank.

5.  **Stateless Quiz & Scoring (UUID & SQLite):**
    * When a quiz is generated, a unique **`quiz_id`** (using `uuid`) is created.
    * A **`sqlite3`** database (`quiz_storage.db`) stores this `quiz_id` mapped to a JSON object of the **correct answers** only.
    * The API remains "stateless," as it doesn't need to hold the quiz in memory.
    * When the user submits to `/submit-quiz/`, the API retrieves the correct answers from the DB using the `quiz_id` and calculates the score.

##  Technologies & Libraries Used

* **Python**
* **Web Framework:** FastAPI
* **NLP:** spaCy (`en_core_web_md`)
* **PDF Extraction:** PyMuPDF (`fitz`)
* **Database:** `sqlite3` (for stateless quiz handling)
* **Utilities:** `re` (Regex), `random`, `uuid`, `json`, `collections.Counter`

##  How to Run

1.  **Clone the repository:**
    ```bash
    git clone [YOUR_REPO_LINK]
    cd [YOUR_REPO_NAME]
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install the required libraries:**
    *Create a `requirements.txt` file first!*
    ```bash
    pip install fastapi "uvicorn[standard]" spacy PyMuPDF en_core_web_md
    python -m spacy download en_core_web_md
    pip freeze > requirements.txt
    ```

4.  **Run the API server:**
    ```bash
    uvicorn main:app --reload
    ```

5.  **Access the API:**
    * The API will be live at `http://127.0.0.1:8000`.
    * You can access the interactive documentation (provided by FastAPI) at `http://127.0.0.1:8000/docs` to test the endpoints.
