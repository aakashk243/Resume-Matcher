# Resume ↔ Job Description Matcher — with Skill-Gap Learning Roadmap

23CSE473 Neural Networks and Deep Learning · Ketha Aakash (CH.SC.U4CSE23222) · Vasanthakumar S (CH.SC.U4CSE23257)

A Flask web app with two portals on one engine:

| Portal | What it gives |
|---|---|
| **Student** | Semantic match score, skill coverage, matched/missing skills (required vs preferred), a **study map** (prerequisite graph), and a **week-by-week learning roadmap** with free and paid online courses, mini projects, milestones and a capstone |
| **Employer** | Ranks many resumes against one JD, splits overlapping skills into *well-supported* (backed by experience or project text) and *list-only*, and suggests interview questions for the list-only ones |

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # open http://127.0.0.1:5000
```

The first run downloads the SBERT model **all-MiniLM-L6-v2** (~90 MB) from Hugging Face. If that isn't possible (no internet, or sentence-transformers not installed), the app falls back to a TF-IDF encoder automatically. The badge in the top-right corner shows which model is in use. To force the fallback, set `MATCHER_BACKEND=tfidf`.

Click **Load sample** on either portal to try it with the included sample resume and JD.

```bash
python -m pytest -q     # 9 tests
python evaluate.py      # SBERT vs TF-IDF on synonym-heavy pairs
```

## Pipeline (matches slide 8)

```
Resume + JD ─► pdf_parser ─► preprocessing ─► skill_extractor ─► SBERT (Siamese) ─► similarity score
                                                                        │
                        Student:  gap_analysis ─► roadmap (study map + courses)
                        Employer: consistency_check ─► interview probes
```

| Module | Role |
|---|---|
| `matcher/pdf_parser.py` | PDF (pdfplumber, with pypdf as fallback), DOCX and TXT to text |
| `matcher/preprocessing.py` | Cleans text, splits the resume into sections (Experience, Projects, Skills, …), splits the JD into required and preferred parts, and chunks text into sentences |
| `matcher/skill_extractor.py` | spaCy `PhraseMatcher` over `data/skills_taxonomy.json` (84 skills, 231 aliases, e.g. *ML* → Machine Learning, *k8s* → Kubernetes). Short names such as C, R, Go and REST are matched case-sensitively |
| `matcher/embedder.py` | SBERT bi-encoder: the same shared-weight MiniLM encodes each document independently, and the two are compared with cosine similarity. Includes the TF-IDF fallback |
| `matcher/similarity.py` | Score = 50% whole-document cosine + 50% requirement alignment (each JD line is matched to its best resume line), mapped to 0–100. Also reports the weakest-covered JD lines |
| `matcher/gap_analysis.py` | Matched, missing and *related-evidence* skills (SBERT finds a skill that is described but not named). Handles "PyTorch **or** TensorFlow" alternatives. Computes weighted coverage and flags skills that are listed but never demonstrated |
| `matcher/roadmap.py` | **Learning roadmap / study map** (see below) |
| `matcher/consistency_check.py` | Employer view: well-supported vs list-only skills, with interview questions |
| `app.py` | Flask REST API and pages |

## Learning roadmap: how it works

1. **Targets.** Each missing JD skill is weighted by importance: required = 1.0, preferred = 0.6, plus 0.1 for each extra mention in the JD (up to +0.3).
2. **Prerequisite expansion.** `data/learning_resources.json` stores a prerequisite graph (Deep Learning ← Machine Learning ← Python/NumPy/Statistics/Linear Algebra, Kubernetes ← Docker ← Linux, …). Prerequisites the student lacks are added as *foundation* steps. Ones the student already has are shown as "you already know".
3. **Ordering.** Depth is the longest prerequisite chain, and it decides the phase, so a skill is never scheduled before what it builds on. Nice-to-have skills go into a final phase.
4. **Effort estimate.** Each skill has base hours. If the student already knows a skill in the same category, the estimate drops by 25% (transfer). Total hours divided by the weekly study budget gives week ranges and a target date.
5. **Resources for every step:**
   - Curated courses, free ones first: Kaggle Learn, Coursera, fast.ai, Stanford CS231n/CS224n, Hugging Face, AWS Skill Builder, Microsoft Learn, official docs, and others. A **free-only** toggle is available.
   - Search links for Coursera, Udemy, edX, YouTube and NPTEL lectures.
   - A roadmap.sh link where one exists.
   - A mini project and checkable milestones.
6. **Capstone.** One project that combines the top three gaps with skills the student already has.
7. **Export.** Download the plan as Markdown, or use Print to save a PDF.

The **study map** is an SVG graph with one column per phase and arrows from each skill to what it unlocks. Click a node to jump to that step.

### Adding skills or courses
- Add the skill and its aliases to `data/skills_taxonomy.json`.
- Add `level`, `hours`, `prerequisites`, `courses`, `project` and `roadmap_sh` to `data/learning_resources.json`.

## API

| Method | Endpoint | Body |
|---|---|---|
| POST | `/api/student/analyze` | form: `resume_file` or `resume_text`, `jd_file` or `jd_text`, `hours_per_week`, `free_only` |
| POST | `/api/employer/analyze` | form: `jd_file` or `jd_text`, `resume_files` (multiple) and/or `resume_text` |
| POST | `/api/roadmap/markdown` | JSON roadmap, returns a `.md` download |
| GET | `/api/health` | shows which backend is active (`sbert` / `tfidf`) |

## Notes and limitations
- Score calibration for SBERT maps cosine 0.15 to 0 and 0.75 to 100. These values were set by hand for MiniLM on professional text; tune them in `embedder.py`.
- The consistency check is a **screening signal, not a lie detector**.
- Course links point to official or long-standing pages, but providers do move pages. The search links always work as a backup.
- Future scope: fine-tune SBERT on labelled resume–JD pairs (conSultantBERT-style), add accounts and saved history, and expand the taxonomy.
