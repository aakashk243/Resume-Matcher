"""Student portal: personalised learning roadmap (study map) to close the skill gap.

Algorithm
---------
1. Targets = missing JD skills, weighted by importance
   (required = 1.0, preferred = 0.6, +0.1 per extra JD mention, max +0.3).
2. Prerequisite expansion: walk the prerequisite graph in
   learning_resources.json; any prerequisite the student does not already
   have becomes a "foundation" node that inherits 90% of its dependant's weight.
3. Depth = longest prerequisite chain inside the plan. Depth levels become
   phases, so nothing is scheduled before the thing it builds on.
4. Effort: base hours per skill, reduced 25% when the student already knows a
   skill in the same category (transfer learning — "you know Flask, so
   Django is faster"). Weeks = hours / weekly study budget.
5. Each step gets curated courses (free first), auto-search links for
   Coursera / Udemy / YouTube / edX / NPTEL, a roadmap.sh link, a mini project
   and milestones; the plan ends with a capstone combining the top gaps.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from urllib.parse import quote_plus

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

PRIORITY_WEIGHT = {"required": 1.0, "preferred": 0.6}
FREE_COSTS = {"Free", "Free to audit"}
TRANSFER_DISCOUNT = 0.75
CORE_WEIGHT = 0.8  # below this a skill is treated as nice-to-have
PHASE_NAMES = ["Foundations", "Core Skills", "Applied Skills", "Advanced & Specialisation", "Mastery"]


def search_links(skill: str) -> list[dict]:
    q = quote_plus(skill)
    return [
        {"provider": "Coursera", "url": f"https://www.coursera.org/search?query={q}"},
        {"provider": "Udemy", "url": f"https://www.udemy.com/courses/search/?q={q}"},
        {"provider": "edX", "url": f"https://www.edx.org/search?q={q}"},
        {"provider": "YouTube", "url": f"https://www.youtube.com/results?search_query={q}+full+course"},
        {"provider": "NPTEL", "url": f"https://www.youtube.com/results?search_query=NPTEL+{q}"},
    ]


class RoadmapBuilder:
    def __init__(self, resources_path: str | None = None, category: dict | None = None):
        resources_path = resources_path or os.path.join(DATA_DIR, "learning_resources.json")
        with open(resources_path, encoding="utf-8") as fh:
            self.res: dict = json.load(fh)
        self.category = category or {}

    # ------------------------------------------------------------------
    def _info(self, skill: str) -> dict:
        return self.res.get(skill, {"level": "Intermediate", "hours": 20, "prerequisites": [],
                                    "roadmap_sh": None, "courses": [],
                                    "project": f"Build a small project that uses {skill}."})

    def build(self, missing: list[dict], known: set[str], hours_per_week: float = 10,
              free_only: bool = False, start: date | None = None) -> dict:
        hours_per_week = max(1.0, float(hours_per_week or 10))
        start = start or date.today()

        # 1. targets with importance
        weight: dict[str, float] = {}
        reason: dict[str, str] = {}
        needed_for: dict[str, set[str]] = {}
        optional = [m for m in missing if m.get("alternative_to")]
        missing = [m for m in missing if not m.get("alternative_to")]
        for m in missing:
            w = PRIORITY_WEIGHT.get(m.get("priority"), 0.6) + min(0.3, 0.1 * (m.get("mentions", 1) - 1))
            weight[m["skill"]] = round(w, 2)
            reason[m["skill"]] = f"{m.get('priority', 'required').capitalize()} in the job description"

        # 2. prerequisite expansion (DFS)
        known_used: set[str] = set()

        def expand(skill: str, w: float, stack: tuple = ()):
            for pre in self._info(skill)["prerequisites"]:
                if pre in stack:
                    continue
                if pre in known:
                    known_used.add(pre)
                    continue
                needed_for.setdefault(pre, set()).add(skill)
                if pre not in weight or weight[pre] < w * 0.9:
                    weight[pre] = round(w * 0.9, 2)
                reason.setdefault(pre, "Prerequisite")
                expand(pre, w * 0.9, stack + (skill,))

        for s in list(weight):
            expand(s, weight[s])
        targets = {m["skill"] for m in missing}
        nodes = set(weight)

        # 3. depth = longest prerequisite chain within the plan
        depth: dict[str, int] = {}

        def d(s: str, seen=()) -> int:
            if s in depth:
                return depth[s]
            pres = [p for p in self._info(s)["prerequisites"] if p in nodes and p not in seen]
            depth[s] = 0 if not pres else 1 + max(d(p, seen + (s,)) for p in pres)
            return depth[s]

        for s in nodes:
            d(s)

        # 4/5. build steps
        known_cats = {self.category.get(k) for k in known}
        steps = {}
        for s in nodes:
            info = self._info(s)
            hours = info["hours"]
            builds_on = sorted(p for p in info["prerequisites"] if p in known)
            same_cat = sorted(k for k in known if self.category.get(k) == self.category.get(s) and k != s)
            transfer = bool(same_cat) and self.category.get(s) is not None
            if transfer:
                hours = math.ceil(hours * TRANSFER_DISCOUNT)
            courses = info["courses"]
            if free_only:
                courses = [c for c in courses if c["cost"] in FREE_COSTS]
            courses = sorted(courses, key=lambda c: c["cost"] not in FREE_COSTS)
            why = reason[s]
            if s in needed_for:
                deps = ", ".join(sorted(needed_for[s]))
                why = f"{why} — needed before {deps}" if s in targets else f"Prerequisite for {deps}"
            steps[s] = {
                "skill": s,
                "category": self.category.get(s, "General"),
                "level": info["level"],
                "hours": hours,
                "base_hours": info["hours"],
                "weight": weight[s],
                "is_target": s in targets,
                "why": why,
                "builds_on": builds_on,
                "head_start": same_cat[:3] if transfer else [],
                "prerequisites": info["prerequisites"],
                "courses": courses,
                "search_links": search_links(s),
                "roadmap_sh": info.get("roadmap_sh"),
                "project": info["project"],
                "milestones": self._milestones(s, courses, info["project"]),
                "depth": depth[s],
            }

        # group into phases by depth, ordered by importance inside each phase
        phases = []
        week = 0
        # Core (required-chain) skills are phased by prerequisite depth;
        # nice-to-have skills and their prerequisites go into a final phase.
        core_depths = [st["depth"] for st in steps.values() if st["weight"] >= CORE_WEIGHT]
        extra_stage = (max(core_depths) + 1) if core_depths else 0
        for st in steps.values():
            st["stage"] = st["depth"] if st["weight"] >= CORE_WEIGHT else extra_stage
        for level in sorted({st["stage"] for st in steps.values()}):
            items = sorted((st for st in steps.values() if st["stage"] == level),
                           key=lambda st: (st["depth"], -st["weight"], st["hours"], st["skill"]))
            hours = sum(st["hours"] for st in items)
            weeks = max(1, math.ceil(hours / hours_per_week))
            # per-skill week windows inside the phase (sequential)
            cursor = week
            for st in items:
                w = st["hours"] / hours_per_week
                st["week_start"] = int(cursor) + 1
                cursor += w
                st["week_end"] = max(st["week_start"], math.ceil(cursor))
            if all(st["weight"] < CORE_WEIGHT for st in items):
                name = "Nice-to-Have Skills"
            elif level == 0:
                name = "Quick Wins & Core Gaps" if all(st["is_target"] for st in items) else "Foundations & Quick Wins"
            else:
                name = PHASE_NAMES[min(level, len(PHASE_NAMES) - 1)]
            phases.append({
                "index": len(phases) + 1,
                "name": name,
                "week_start": week + 1,
                "week_end": week + weeks,
                "hours": hours,
                "start_date": (start + timedelta(weeks=week)).isoformat(),
                "end_date": (start + timedelta(weeks=week + weeks) - timedelta(days=1)).isoformat(),
                "steps": items,
            })
            week += weeks

        total_hours = sum(st["hours"] for st in steps.values())
        top = sorted((s for s in steps.values() if s["is_target"]), key=lambda s: -s["weight"])[:3]
        capstone = None
        if top:
            names = [s["skill"] for s in top]
            capstone = {
                "title": "Capstone: prove it end-to-end",
                "skills": names,
                "description": (f"Build one portfolio project that combines {', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else names[0]}"
                                f"{' with what you already know (' + ', '.join(sorted(known_used)[:3]) + ')' if known_used else ''}. "
                                "Deploy it, write a README with architecture + results, and add it to the Projects section "
                                "of your resume with measurable outcomes."),
                "weeks": 2,
            }
            week += 2
        graph = self._graph(steps, known_used)
        return {
            "summary": {
                "skills_to_learn": len(steps),
                "targets": len(targets & nodes),
                "prerequisites_added": len(nodes - targets),
                "total_hours": total_hours,
                "hours_per_week": hours_per_week,
                "total_weeks": week,
                "start_date": start.isoformat(),
                "target_date": (start + timedelta(weeks=week)).isoformat(),
                "free_only": free_only,
                "known_prerequisites": sorted(known_used),
                "optional_alternatives": [{"skill": m["skill"], "alternative_to": m["alternative_to"]} for m in optional],
            },
            "phases": phases,
            "capstone": capstone,
            "graph": graph,
        }

    @staticmethod
    def _milestones(skill: str, courses: list, project: str) -> list[str]:
        ms = []
        if courses:
            ms.append(f"Complete: {courses[0]['title']}")
        ms.append(f"Build: {project}")
        ms.append(f"Push the code to GitHub and add a '{skill}' bullet with a measurable result to your resume")
        return ms

    def _graph(self, steps: dict, known_used: set[str]) -> dict:
        nodes = [{"id": k, "type": "known", "depth": -1} for k in sorted(known_used)]
        nodes += [{"id": s, "type": "target" if st["is_target"] else "prerequisite",
                   "depth": st["stage"]} for s, st in steps.items()]  # column = roadmap phase
        ids = {n["id"] for n in nodes}
        edges = []
        for s, st in steps.items():
            for p in st["prerequisites"]:
                if p in ids:
                    edges.append({"from": p, "to": s})
        return {"nodes": nodes, "edges": edges}


def roadmap_to_markdown(rm: dict, title: str = "My Learning Roadmap") -> str:
    s = rm["summary"]
    out = [f"# {title}", "",
           f"**{s['skills_to_learn']} skills · ~{s['total_hours']} hours · {s['total_weeks']} weeks "
           f"at {s['hours_per_week']:g} h/week** (target date {s['target_date']})", ""]
    for ph in rm["phases"]:
        out.append(f"## Phase {ph['index']}: {ph['name']} (weeks {ph['week_start']}–{ph['week_end']})")
        for st in ph["steps"]:
            out.append(f"### {st['skill']} — {st['level']}, ~{st['hours']} h  ")
            out.append(f"_{st['why']}_")
            for c in st["courses"]:
                out.append(f"- [{c['title']}]({c['url']}) — {c['provider']} ({c['cost']})")
            if st["roadmap_sh"]:
                out.append(f"- Roadmap: {st['roadmap_sh']}")
            out.append(f"- Project: {st['project']}")
            out += [f"- [ ] {m}" for m in st["milestones"]]
            out.append("")
    if rm.get("capstone"):
        out += [f"## {rm['capstone']['title']}", rm["capstone"]["description"], ""]
    return "\n".join(out)
