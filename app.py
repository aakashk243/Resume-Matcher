"""Flask backend — two portals (Student / Employer), one matching engine."""
from __future__ import annotations

import logging
import os

from flask import Flask, Response, jsonify, render_template, request

from matcher.embedder import get_embedder
from matcher.pdf_parser import ParseError, extract_text
from matcher.pipeline import analyze_employer, analyze_student
from matcher.roadmap import roadmap_to_markdown

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB per request
MAX_BATCH = 25


def _text_from(field_file: str, field_text: str) -> str:
    """Prefer an uploaded file; fall back to pasted text."""
    f = request.files.get(field_file)
    if f and f.filename:
        return extract_text(f.filename, f.read())
    return request.form.get(field_text, "")


# ----------------------------------------------------------------- pages
@app.get("/")
def home():
    return render_template("index.html")


@app.get("/student")
def student():
    return render_template("student.html")


@app.get("/employer")
def employer():
    return render_template("employer.html")


# ------------------------------------------------------------------- API
@app.get("/api/health")
def health():
    emb = get_embedder()
    return jsonify(status="ok", backend=emb.backend)


@app.get("/api/sample/<name>")
def sample(name: str):
    allowed = {"resume": "sample_resume.txt", "resume2": "sample_resume_2.txt", "jd": "sample_jd.txt"}
    if name not in allowed:
        return jsonify(error="unknown sample"), 404
    with open(os.path.join(BASE, "samples", allowed[name]), encoding="utf-8") as fh:
        return jsonify(text=fh.read())


@app.post("/api/student/analyze")
def api_student():
    try:
        resume = _text_from("resume_file", "resume_text")
        jd = _text_from("jd_file", "jd_text")
        hours = float(request.form.get("hours_per_week", 10) or 10)
        free_only = request.form.get("free_only") in {"1", "true", "on"}
        return jsonify(analyze_student(resume, jd, hours, free_only))
    except (ParseError, ValueError) as exc:
        return jsonify(error=str(exc)), 400


@app.post("/api/employer/analyze")
def api_employer():
    try:
        jd = _text_from("jd_file", "jd_text")
        candidates = []
        for f in request.files.getlist("resume_files")[:MAX_BATCH]:
            if f and f.filename:
                candidates.append((f.filename, extract_text(f.filename, f.read())))
        pasted = request.form.get("resume_text", "").strip()
        if pasted:
            candidates.append(("Pasted resume", pasted))
        if not candidates:
            raise ValueError("Upload at least one resume (or paste one).")
        results = []
        for name, text in candidates:
            try:
                res = analyze_employer(text, jd)
                res["name"] = name
            except ValueError as exc:
                res = {"name": name, "error": str(exc)}
            results.append(res)
        results.sort(key=lambda r: -(r.get("match", {}).get("score", -1)))
        return jsonify(candidates=results)
    except (ParseError, ValueError) as exc:
        return jsonify(error=str(exc)), 400


@app.post("/api/roadmap/markdown")
def api_roadmap_md():
    data = request.get_json(silent=True) or {}
    if "phases" not in data:
        return jsonify(error="roadmap missing"), 400
    md = roadmap_to_markdown(data, data.get("title", "My Learning Roadmap"))
    return Response(md, mimetype="text/markdown",
                    headers={"Content-Disposition": "attachment; filename=learning_roadmap.md"})


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="File too large (limit 10 MB)."), 413


if __name__ == "__main__":
    get_embedder()  # load the model once at start-up
    app.run(debug=False, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
