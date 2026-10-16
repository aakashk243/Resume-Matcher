// Employer portal: rank resumes and show the consistency signal per candidate.
let candidates = [];

$("#load-sample").addEventListener("click", async () => {
  const f = $("#employer-form");
  f.jd_text.value = await loadSample("jd");
  f.resume_text.value = await loadSample("resume2");
});

$("#employer-form").addEventListener("submit", async e => {
  e.preventDefault();
  showError("");
  setBusy(true);
  try {
    const data = await postForm("/api/employer/analyze", e.target);
    candidates = data.candidates;
    renderTable();
    if (candidates.length) showDetail(0);
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
  }
});

const bar = v => `<span class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%"></i></span>${v.toFixed(0)}%`;

function renderTable() {
  $("#results").hidden = false;
  $("#rank-body").innerHTML = candidates.map((c, i) => c.error
    ? `<tr data-i="${i}"><td>–</td><td>${esc(c.name)}</td><td colspan="3" class="muted">${esc(c.error)}</td></tr>`
    : `<tr data-i="${i}"><td>${i + 1}</td><td>${esc(c.name)}</td><td>${bar(c.match.score)}</td>
         <td>${bar(c.coverage)}</td><td>${bar(c.consistency.support_ratio)}</td></tr>`).join("");
  $("#rank-body").querySelectorAll("tr").forEach(tr => tr.addEventListener("click", () => showDetail(+tr.dataset.i)));
}

function showDetail(i) {
  const c = candidates[i];
  $("#rank-body").querySelectorAll("tr").forEach(tr => tr.classList.toggle("sel", +tr.dataset.i === i));
  if (!c || c.error) { $("#detail").innerHTML = ""; return; }
  const k = c.consistency;
  $("#detail").innerHTML = `
    <div class="card score-row">
      <div class="ring-wrap">${ring(c.match.score)}<span>Semantic match</span></div>
      <div class="ring-wrap">${ring(k.support_ratio)}<span>Backed by experience</span></div>
      <div class="score-text">
        <h3>${esc(c.name)} — ${verdict(c.match.score)}</h3>
        <p><b>${k.support_ratio}%</b> of overlapping skills are backed by experience/project text.
           Covers ${c.coverage}% of JD skills.</p>
        <p class="note">Not a lie-detector: ${esc(k.note)}</p>
      </div>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>Well-supported skills</h3>
        <div class="chips">${k.well_supported.map(s => chip(s.skill, "good", s.sections.filter(x => x !== "skills").join(", "))).join("") || '<span class="empty">None</span>'}</div>
        <h4>Missing from resume</h4>
        <div class="chips">${k.missing.map(s => chip(s.skill, `bad ${s.priority}`, s.priority)).join("") || '<span class="empty">None</span>'}</div>
      </div>
      <div class="card">
        <h3>List-only skills — worth probing</h3>
        ${k.list_only.map(s => `<div class="probe"><b>${esc(s.skill)}</b> <span class="badge">${esc(s.priority)}</span>
            <p>Ask: ${esc(s.question)}</p></div>`).join("") || '<span class="empty">Every overlapping skill is backed by experience.</span>'}
      </div>
    </div>`;
}
