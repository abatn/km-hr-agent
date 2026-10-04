"""
SphinxATS - Referenz-Code (GitHub: MANISH-K-07/SphinxATS)
==========================================================
Quelle: https://github.com/MANISH-K-07/SphinxATS
Autor: Manish Krishna Kandrakota et al.
Paper: DOI 10.1109/ICSSAS68835.2026.11559449 (IEEE ICSSAS 2026)
Lizenz: Keine angegeben (Capstone Project)

ACHTUNG: Dies ist eine LOKALE REFERENZ für unser Projekt.
Der Code ist NICHT Teil des KM-HR-Agenten.
Gespeichert: 17.09.2026
"""

import re
import os
import pdfplumber
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import numpy as np

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

job_description = ""

# ----------------------------------
# Master Technical Skills Dataset
# ----------------------------------
TECH_SKILLS = [
    "python", "java", "c++", "c programming", "sql",
    "machine learning", "deep learning",
    "data science", "data analysis",
    "flask", "django", "react", "angular",
    "node", "nodejs", "javascript",
    "html", "css", "bootstrap",
    "tensorflow", "pytorch", "keras",
    "aws", "azure", "gcp",
    "docker", "kubernetes",
    "mongodb", "mysql", "postgresql",
    "git", "linux", "pandas", "numpy",
    "opencv", "nlp", "power bi", "tableau"
]

MIN_SKILL_THRESHOLD = 0.2

# ----------------------------------
# SPECIALIZATION GROUPS
# ----------------------------------
SPECIALIZATION_SKILLS = {
    "Data Science": [
        "python", "machine learning", "deep learning",
        "data science", "data analysis",
        "tensorflow", "pytorch", "keras",
        "pandas", "numpy", "nlp"
    ],
    "Backend": [
        "java", "python", "node", "nodejs",
        "flask", "django", "sql",
        "mongodb", "mysql", "postgresql"
    ],
    "Frontend": [
        "react", "angular",
        "html", "css", "javascript",
        "bootstrap"
    ],
    "Cloud/DevOps": [
        "aws", "azure", "gcp",
        "docker", "kubernetes",
        "linux", "git"
    ]
}


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "role" not in session or session["role"] != role:
                return render_template("403.html"), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def extract_skills_from_jd(jd_text):
    jd_text = jd_text.lower()
    extracted = []
    for skill in TECH_SKILLS:
        if skill in jd_text:
            extracted.append(skill)
    return extracted


def get_resume_vector(text):
    vector = []
    for specialization, skills in SPECIALIZATION_SKILLS.items():
        count = 0
        for skill in skills:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text):
                count += 1
        vector.append(count)
    return vector


@app.route("/rank")
@role_required("hr")
def rank_resumes():
    global job_description
    if job_description == "":
        return render_template("message.html", message="Please submit a Job Description first.")

    resumes = []
    resume_names = []
    vectors = []

    jd_exp_match = re.search(r'(\d+)\s+years', job_description.lower())
    jd_exp = int(jd_exp_match.group(1)) if jd_exp_match else 1

    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith(".pdf"):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            text = ""
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            text = text.lower()
            resumes.append(text)
            resume_names.append(filename)

            required_skills = extract_skills_from_jd(job_description)
            matched_skills = []
            for skill in required_skills:
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, text):
                    matched_skills.append(skill)
            skill_score = (
                len(matched_skills) / len(required_skills)
                if required_skills else 0
            )

            if skill_score >= MIN_SKILL_THRESHOLD:
                vector = get_resume_vector(text)
                vectors.append(vector)
            else:
                vectors.append([-1])

    if not resumes:
        return render_template("message.html", message="No resumes uploaded.")

    # TF-IDF Similarity
    documents = [job_description.lower()] + resumes
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(documents)
    similarity_scores = cosine_similarity(
        tfidf_matrix[0:1], tfidf_matrix[1:]
    ).flatten()

    required_skills = extract_skills_from_jd(job_description)
    ranked = []

    for i, resume_text in enumerate(resumes):
        matched_skills = []
        for skill in required_skills:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, resume_text):
                matched_skills.append(skill)
        skill_score = (
            len(matched_skills) / len(required_skills)
            if required_skills else 0
        )

        resume_exp_match = re.search(r'(\d+)\s+years', resume_text)
        if resume_exp_match:
            resume_exp = int(resume_exp_match.group(1))
            exp_score = 1 if resume_exp >= jd_exp else resume_exp / jd_exp
        else:
            exp_score = 0.5

        # ============================================================
        # GEWICHTE (DIESE ZEILE IST DIE QUELLE FÜR UNSERE REFERENZ):
        #   0.6 × Similarity + 0.3 × Skills + 0.1 × Experience
        # ============================================================
        final_score = (
            (0.6 * similarity_scores[i]) +
            (0.3 * skill_score) +
            (0.1 * exp_score)
        )

        ranked.append({
            "name": resume_names[i],
            "final_score": round(final_score, 3),
            "skill_score": round(skill_score, 3),
            "exp_score": round(exp_score, 3),
            "matched_skills": matched_skills,
        })

    ranked = sorted(ranked, key=lambda x: x["final_score"], reverse=True)
    return render_template("results.html", ranked=ranked)


if __name__ == "__main__":
    app.run()
