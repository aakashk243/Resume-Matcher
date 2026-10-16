"""Run with:  python -m pytest -q"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matcher.gap_analysis import jd_skill_priorities  # noqa: E402
from matcher.pdf_parser import extract_text_from_path  # noqa: E402
from matcher.pipeline import analyze_employer, analyze_student  # noqa: E402
from matcher.preprocessing import split_jd_requirements, split_sections  # noqa: E402
from matcher.roadmap import RoadmapBuilder, roadmap_to_markdown  # noqa: E402
from matcher.skill_extractor import SkillExtractor  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESUME = open(os.path.join(HERE, "samples", "sample_resume.txt"), encoding="utf-8").read()
RESUME2 = open(os.path.join(HERE, "samples", "sample_resume_2.txt"), encoding="utf-8").read()
JD = open(os.path.join(HERE, "samples", "sample_jd.txt"), encoding="utf-8").read()
EXT = SkillExtractor()


def test_synonyms_are_normalised():
    found = EXT.extract_set("Worked on ML and NLP using sklearn, k8s and React.js")
    assert {"Machine Learning", "Natural Language Processing", "Scikit-learn", "Kubernetes", "React"} <= found


def test_ambiguous_short_names():
    assert "C" not in EXT.extract_set("Skilled in C++ and C#")
    assert "C" in EXT.extract_set("Languages: C, Python")
    assert "Go" not in EXT.extract_set("I want to go to the office")
    assert "R" not in EXT.extract_set("r and d")


def test_sections_detected():
    secs = split_sections(RESUME)
    assert {"skills", "experience", "projects", "education"} <= set(secs)


def test_jd_required_vs_preferred():
    parts = split_jd_requirements(JD)
    assert "Kubernetes" in parts["preferred"]
    pri = jd_skill_priorities(JD, EXT)
    assert pri["Python"]["priority"] == "required"
    assert pri["Kubernetes"]["priority"] == "preferred"
    assert "TensorFlow" in pri["PyTorch"]["alternatives"]


def test_student_analysis_and_roadmap():
    out = analyze_student(RESUME, JD, hours_per_week=10)
    gaps, rm = out["gaps"], out["roadmap"]
    missing = {m["skill"] for m in gaps["missing"]}
    assert "Deep Learning" in missing and "Python" not in missing
    assert 0 <= out["match"]["score"] <= 100
    order = [s["skill"] for ph in rm["phases"] for s in ph["steps"]]
    # prerequisites always come before the skills they unlock
    assert order.index("Deep Learning") < order.index("PyTorch")
    assert order.index("Natural Language Processing") < order.index("Large Language Models")
    # every step has at least one course or search link
    assert all(s["courses"] or s["search_links"] for ph in rm["phases"] for s in ph["steps"])
    assert "# My Learning Roadmap" in roadmap_to_markdown(rm)


def test_free_only_filter():
    rm = RoadmapBuilder(category=EXT.category).build(
        [{"skill": "Deep Learning", "priority": "required"}], known={"Python"}, free_only=True)
    costs = {c["cost"] for ph in rm["phases"] for s in ph["steps"] for c in s["courses"]}
    assert costs <= {"Free", "Free to audit"}


def test_prerequisite_expansion():
    rm = RoadmapBuilder(category=EXT.category).build(
        [{"skill": "Kubernetes", "priority": "required"}], known=set())
    skills = [s["skill"] for ph in rm["phases"] for s in ph["steps"]]
    assert skills.index("Linux") < skills.index("Docker") < skills.index("Kubernetes")


def test_employer_ranking_signal():
    strong = analyze_employer(RESUME2, JD)
    weak = analyze_employer(RESUME, JD)
    assert strong["match"]["score"] > weak["match"]["score"]
    listed = {s["skill"] for s in strong["consistency"]["list_only"]}
    assert "Kubernetes" in listed  # only in the skills list, never in experience


def test_pdf_parsing():
    path = os.path.join(HERE, "samples", "sample_resume.pdf")
    if os.path.exists(path):
        assert "Python" in extract_text_from_path(path)
