// Student portal: match score, gap analysis, study map and learning roadmap.
let lastRoadmap = null;
const slug = s => "step-" + s.toLowerCase().replace(/[^a-z0-9]+/g, "-");

$("#hours").addEventListener("input", e => { $("#hours-val").textContent = e.target.value; });

$("#load-sample").addEventListener("click", async () => {
  const f = $("#student-form");
  f.resume_text.value = await loadSample("resume");
  f.jd_text.value = await loadSample("jd");
});

$("#student-form").addEventListener("submit", async e => {
  e.preventDefault();
  showError("");
  setBusy(true);
  try {
    const data = await postForm("/api/student/analyze", e.target);
    render(data);
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
  }
});

function render(data) {
  const { match, gaps, roadmap } = data;
  $("#results").hidden = false;
  $("#ring-score").innerHTML = ring(match.score);
  $("#ring-coverage").innerHTML = ring(gaps.coverage);
  const nReq = gaps.missing.filter(m => m.priority === "required").length;
  $("#score-text").innerHTML = `
    <h3>${verdict(match.score)}</h3>
    <p>You cover <b>${gaps.coverage}%</b> of the skills this job description asks for
       (${gaps.matched.length} matched, ${gaps.missing.length} missing${nReq ? `, ${nReq} of them required` : ""}).</p>
    <p class="muted small">Document cosine ${match.document_cosine} · requirement alignment ${match.alignment_cosine} ·
       model: ${match.backend === "sbert" ? "SBERT all-MiniLM-L6-v2" : "TF-IDF fallback"}</p>`;

  $("#matched").innerHTML = gaps.matched.length
    ? gaps.matched.map(m => chip(m.skill, "good", m.via ? `via ${m.via}` : "")).join("")
    : `<span class="empty">No JD skills found on your resume yet.</span>`;
  $("#missing").innerHTML = gaps.missing.length
    ? gaps.missing.map(m => chip(m.skill, `bad ${m.priority}`, m.alternative_to ? `or ${m.alternative_to}` : m.priority)).join("")
    : `<span class="empty">Nothing missing — great fit!</span>`;
  $("#partial-wrap").hidden = !gaps.partial.length;
  $("#partial").innerHTML = gaps.partial.map(p =>
    `<div class="evidence"><b>${esc(p.skill)}</b> — “${esc(p.evidence)}”</div>`).join("");
  $("#unbacked-wrap").hidden = !gaps.unbacked.length;
  $("#unbacked").innerHTML = gaps.unbacked.map(s => chip(s, "warn")).join("");
  $("#suggestions").innerHTML = gaps.suggestions.map(t => `<li>${esc(t)}</li>`).join("");
  $("#weakest").innerHTML = match.weakest_requirements.map(w => `
    <div class="weak-item"><b>JD:</b> ${esc(w.jd_line)}<br>
    <span class="muted small">Closest resume line: ${w.closest_resume_line ? "“" + esc(w.closest_resume_line) + "”" : "none"} (sim ${w.similarity})</span></div>`).join("");

  renderRoadmap(roadmap);
  $("#results").scrollIntoView({ behavior: "smooth" });
}

// ---------------------------------------------------------------- roadmap
function renderRoadmap(rm) {
  lastRoadmap = rm;
  const s = rm.summary;
  const hasSteps = rm.phases.length > 0;
  $("#roadmap").hidden = !hasSteps;
  if (!hasSteps) return;
  const target = new Date(s.target_date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  $("#roadmap-sub").textContent = `Ordered by prerequisites and JD priority, at ${s.hours_per_week} h/week` +
    (s.free_only ? " · free courses only" : "") + ".";
  $("#roadmap-stats").innerHTML = [
    [s.skills_to_learn, "skills to learn"],
    [s.prerequisites_added, "prerequisites added"],
    [`~${s.total_hours} h`, "total study time"],
    [`${s.total_weeks} wks`, "incl. capstone"],
    [target, "job-ready target"],
  ].map(([b, t]) => `<div class="stat"><b>${esc(b)}</b><span>${esc(t)}</span></div>`).join("");

  $("#study-map").innerHTML = studyMap(rm.graph);
  $("#study-map").querySelectorAll(".node").forEach(n => n.addEventListener("click", () => {
    const el = document.getElementById(slug(n.dataset.id));
    if (!el) return;
    el.closest("details").open = true;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("highlight");
    setTimeout(() => el.classList.remove("highlight"), 1600);
  }));

  $("#phases").innerHTML = rm.phases.map(ph => `
    <details class="phase card" data-n="${ph.index}" open>
      <summary>
        <span class="phase-title">Phase ${ph.index}: ${esc(ph.name)}</span>
        <span class="phase-meta">Weeks ${ph.week_start}–${ph.week_end} · ~${ph.hours} h · ${ph.steps.length} skill${ph.steps.length > 1 ? "s" : ""}</span>
      </summary>
      ${ph.steps.map(stepCard).join("")}
    </details>`).join("");

  const cap = rm.capstone;
  $("#capstone").innerHTML = cap ? `
    <div class="card capstone">
      <h3>🏁 ${esc(cap.title)} <span class="badge info">~${cap.weeks} weeks</span></h3>
      <p>${esc(cap.description)}</p>
      <div class="chips">${cap.skills.map(k => chip(k, "")).join("")}</div>
    </div>` : "";
  const opt = s.optional_alternatives || [];
  $("#optional").innerHTML = opt.length ? `<p class="muted small">Optional: ${opt.map(o =>
    `<b>${esc(o.skill)}</b> is listed as an alternative to ${esc(o.alternative_to)}, so it was left out of the plan.`).join(" ")}</p>` : "";
}

function stepCard(st) {
  const tags = [
    `<span class="badge ${st.is_target ? "info" : ""}">${st.is_target ? "JD skill" : "Prerequisite"}</span>`,
    `<span class="badge">${esc(st.level)}</span>`,
    `<span class="badge">~${st.hours} h · wk ${st.week_start}${st.week_end > st.week_start ? "–" + st.week_end : ""}</span>`,
  ].join("");
  const head = st.head_start.length || st.builds_on.length
    ? `<div class="headstart">Head start: you already know ${esc([...new Set([...st.builds_on, ...st.head_start])].join(", "))}` +
      (st.hours < st.base_hours ? ` — estimate reduced from ${st.base_hours} h.` : ".") + `</div>` : "";
  const courses = st.courses.length ? `<ul class="courses">${st.courses.map(c => `
      <li><span><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a>
        <span class="provider"> · ${esc(c.provider)} · ${esc(c.type)}</span></span>
        <span class="badge ${c.cost === "Paid" ? "warn" : "good"}">${esc(c.cost)}</span></li>`).join("")}</ul>`
    : `<p class="muted small">No curated free course — try the search links below.</p>`;
  const more = `<div class="more">More courses:
      ${st.search_links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.provider)}</a>`).join(" · ")}
      ${st.roadmap_sh ? ` · <a href="${esc(st.roadmap_sh)}" target="_blank" rel="noopener">roadmap.sh</a>` : ""}</div>`;
  return `<div class="step" id="${slug(st.skill)}">
    <div class="step-head"><h4>${esc(st.skill)}</h4><div class="step-tags">${tags}</div></div>
    <div class="why">${esc(st.why)}</div>
    ${head}${courses}${more}
    <div class="project"><b>Mini project:</b> ${esc(st.project)}</div>
    <ul class="milestones">${st.milestones.map(m => `<li><label><input type="checkbox"><span>${esc(m)}</span></label></li>`).join("")}</ul>
  </div>`;
}

const SHORT = { "Natural Language Processing": "NLP", "Large Language Models": "LLMs", "Data Structures and Algorithms": "DSA",
  "Object-Oriented Programming": "OOP", "Reinforcement Learning": "Reinforcement L.", "Feature Engineering": "Feature Eng." };

// Layered dependency graph: columns = learning order, arrows = "unlocks".
function studyMap(graph) {
  const W = 150, H = 34, GX = 46, GY = 14, TOP = 30, PAD = 8;
  const cols = {};
  graph.nodes.forEach(n => (cols[n.depth] = cols[n.depth] || []).push(n));
  const depths = Object.keys(cols).map(Number).sort((a, b) => a - b);
  const parents = {};
  graph.edges.forEach(e => (parents[e.to] = parents[e.to] || []).push(e.from));
  const pos = {};
  depths.forEach((d, ci) => {
    const col = cols[d];
    // order by average position of parents to reduce edge crossings
    col.sort((a, b) => {
      const avg = n => { const p = (parents[n.id] || []).filter(x => pos[x]); return p.length ? p.reduce((s, x) => s + pos[x].y, 0) / p.length : 1e6; };
      return avg(a) - avg(b) || a.id.localeCompare(b.id);
    });
    col.forEach((n, ri) => { pos[n.id] = { x: PAD + ci * (W + GX), y: TOP + ri * (H + GY) }; });
  });
  const width = PAD * 2 + depths.length * W + (depths.length - 1) * GX;
  const height = TOP + Math.max(...depths.map(d => cols[d].length)) * (H + GY);
  const labels = depths.map((d, ci) =>
    `<text class="col-label" x="${PAD + ci * (W + GX) + W / 2}" y="16" text-anchor="middle">${d < 0 ? "You already know" : "Phase " + (depths.filter(x => x >= 0).indexOf(d) + 1)}</text>`).join("");
  const edges = graph.edges.filter(e => pos[e.from] && pos[e.to]).map(e => {
    const a = pos[e.from], b = pos[e.to];
    const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x - 6, y2 = b.y + H / 2, mx = (x1 + x2) / 2;
    return `<path class="edge" marker-end="url(#arrow)" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"/>`;
  }).join("");
  const nodes = graph.nodes.map(n => {
    const p = pos[n.id];
    const short = SHORT[n.id] || n.id;
    const label = short.length > 20 ? short.slice(0, 18) + "…" : short;
    return `<g class="node ${n.type}" data-id="${esc(n.id)}" transform="translate(${p.x},${p.y})">
      <title>${esc(n.id)}</title><rect width="${W}" height="${H}" rx="8"/>
      <text x="${W / 2}" y="${H / 2}" text-anchor="middle" dominant-baseline="central">${esc(label)}</text></g>`;
  }).join("");
  return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Skill dependency study map">
    <defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"/></marker></defs>
    ${labels}${edges}${nodes}</svg>`;
}

// ---------------------------------------------------------------- export
$("#dl-md").addEventListener("click", async () => {
  if (!lastRoadmap) return;
  const res = await fetch("/api/roadmap/markdown", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lastRoadmap),
  });
  const blob = await res.blob();
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "learning_roadmap.md" });
  a.click();
  URL.revokeObjectURL(a.href);
});
$("#print").addEventListener("click", () => window.print());
