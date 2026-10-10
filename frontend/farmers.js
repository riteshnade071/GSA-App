/* Farmers section: public, no login. Needs API (defined in index.html). */
(function(){
  const root = document.getElementById("sec-farmers");
  if(!root) return;
  const esc = s => { const d=document.createElement("div"); d.textContent = s==null ? "" : s; return d.innerHTML; };
  const safe = u => /^https:\/\//i.test(u||"") ? u : "#";
  const F = {cat:"", scope:"", state:"", group:"", q:"", meta:null, timer:null};

  root.innerHTML = `
    <div class="card">
      <h2>🌾 Farmer schemes</h2>
      <div class="hint">Central and state government schemes for farmers, with eligibility, documents and official links. Every scheme shows when its official source was last checked.</div>
      <div class="fgrid">
        <div><label for="f_q">Search</label><input id="f_q" type="search" placeholder="e.g. solar pump, insurance, PM-KISAN" autocomplete="off"></div>
        <div><label for="f_state">Your state</label><select id="f_state"><option value="">All states</option></select></div>
        <div><label for="f_group">Who are you?</label><select id="f_group"><option value="">Any farmer</option></select></div>
      </div>
      <div class="chips" id="f_scope"></div>
      <div class="chips" id="f_cats"></div>
    </div>
    <div id="f_count" class="hint"></div>
    <div id="f_list" class="cards2"></div>
    <div class="note">Information here is compiled from official government sources and can change. Always confirm amounts, dates and eligibility on the official link before you apply.</div>`;

  const $ = id => document.getElementById(id);
  const chip = (label, on, fn) => { const b=document.createElement("button"); b.type="button"; b.className="chip"+(on?" on":""); b.textContent=label; b.onclick=fn; return b; };

  function drawChips(){
    const sc = $("f_scope"); sc.innerHTML="";
    [["","All schemes"],["central","🇮🇳 Central"],["state","📍 State"]].forEach(([v,l])=>sc.appendChild(chip(l,F.scope===v,()=>{F.scope=v;drawChips();load();})));
    const ct = $("f_cats"); ct.innerHTML="";
    ct.appendChild(chip("All categories",F.cat==="",()=>{F.cat="";drawChips();load();}));
    ((F.meta&&F.meta.categories)||[]).filter(c=>c.count>0).forEach(c=>ct.appendChild(chip(`${c.label} (${c.count})`,F.cat===c.id,()=>{F.cat=c.id;drawChips();load();})));
  }

  function card(s){
    const verified = s.verified;
    const trust = verified
      ? `<span class="tag ok">✔ Verified ${esc(s.last_verified)}</span>`
      : `<span class="tag pending">Official source checked ${esc(s.source_checked_on||"—")} · awaiting final review</span>`;
    const list = a => a && a.length ? `<ul>${a.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>` : "";
    return `<div class="opp">
      <span class="tag ${s.scope}">${s.scope==="state" ? "📍 "+esc(s.state) : "🇮🇳 Central (All India)"}</span><span class="tag cat">${esc(s.sub_category_label)}</span>
      <h3>${esc(s.name)}</h3>
      ${s.amount_text?`<p class="amt">💰 ${esc(s.amount_text)}</p>`:""}
      ${s.description?`<p>${esc(s.description)}</p>`:""}
      ${s.benefits?`<span class="lbl">Benefits</span><p>${esc(s.benefits)}</p>`:""}
      ${s.eligibility_text?`<span class="lbl">Who can apply</span><p>${esc(s.eligibility_text)}</p>`:""}
      ${s.required_documents.length?`<span class="lbl">Documents needed</span>${list(s.required_documents)}`:""}
      ${s.application_steps.length?`<details class="steps"><summary>How to apply — ${s.application_steps.length} steps</summary><ol>${s.application_steps.map(x=>`<li>${esc(x)}</li>`).join("")}</ol></details>`:""}
      <div class="src">Source: ${esc(s.source_organization||"—")}<br>${trust}</div>
      <a class="applybtn" href="${esc(safe(s.official_url))}" target="_blank" rel="noopener noreferrer">Official website → Apply / details</a>
    </div>`;
  }

  async function load(){
    const list = $("f_list"), count = $("f_count");
    const p = new URLSearchParams();
    if(F.state) p.set("state",F.state); if(F.cat) p.set("category",F.cat); if(F.group) p.set("group",F.group);
    if(F.scope) p.set("scope",F.scope); if(F.q) p.set("q",F.q);
    const my = ++load.n;
    count.textContent = "Loading schemes…";
    const wake = setTimeout(()=>{ if(my===load.n) count.textContent = "The server was asleep and is waking up. This can take 30–50 seconds, please wait…"; }, 6000);
    try{
      const res = await fetch(`${API}/farmers/schemes?${p}`); clearTimeout(wake);
      if(!res.ok) throw new Error("Could not load schemes");
      const items = await res.json(); if(my!==load.n) return;
      count.innerHTML = `<b>${items.length} scheme${items.length===1?"":"s"}</b> found`;
      list.innerHTML = items.length ? items.map(card).join("") : `<div class="empty" style="grid-column:1/-1">No scheme matches these filters yet. Try clearing a filter. More states are being added.</div>`;
    }catch(e){ clearTimeout(wake); if(my===load.n){ count.textContent=""; list.innerHTML = `<div class="empty" style="grid-column:1/-1">${esc(e.message)}. Please try again in a moment.</div>`; } }
  }
  load.n = 0;

  async function init(){
    try{
      F.meta = await (await fetch(`${API}/farmers/meta`)).json();
      $("f_state").innerHTML += (F.meta.states||[]).map(s=>`<option>${esc(s)}</option>`).join("");
      $("f_group").innerHTML += (F.meta.eligibility_groups||[]).filter(g=>g.id!=="any_farmer").map(g=>`<option value="${esc(g.id)}">${esc(g.label)}</option>`).join("");
    }catch{}
    drawChips(); load();
  }
  $("f_state").onchange = e => { F.state=e.target.value; load(); };
  $("f_group").onchange = e => { F.group=e.target.value; load(); };
  $("f_q").oninput = e => { clearTimeout(F.timer); F.timer=setTimeout(()=>{F.q=e.target.value.trim();load();},350); };
  window.farmersInit = (function(){ let done=false; return ()=>{ if(!done){ done=true; init(); } }; })();
})();
