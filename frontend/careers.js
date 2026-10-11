/* Career Guidance section: public, no login. Needs API (defined in index.html). */
(function(){
  const root = document.getElementById("sec-careers");
  if(!root) return;
  const esc = s => { const d=document.createElement("div"); d.textContent = s==null ? "" : s; return d.innerHTML; };
  const safe = u => /^https:\/\//i.test(u||"") ? u : "#";
  const $ = id => document.getElementById(id);
  let Q = null, META = null, ans = {interests:[], skills:[]}, tab = "find";

  root.innerHTML = `
    <div class="card">
      <h2>🧭 Career guidance</h2>
      <div class="hint">Not sure what to do after your current course? Answer a few questions, or explore options stage by stage.</div>
      <div class="chips" style="margin-top:0">
        <button class="chip on" id="c_tab_find" type="button">🎯 Find my path</button>
        <button class="chip" id="c_tab_stage" type="button">📚 Explore by stage</button>
        <button class="chip" id="c_tab_abroad" type="button">✈️ Study abroad</button>
      </div>
    </div>
    <div id="c_body"></div>
    <div class="note" id="c_disc"></div>`;

  const wakeHint = el => { const t=setTimeout(()=>{ el.innerHTML = `<div class="empty">The server was asleep and is waking up. This can take 30–50 seconds, please wait…</div>`; },6000); return ()=>clearTimeout(t); };
  async function getJSON(path, opts){
    const res = await fetch(API+path, opts); if(!res.ok) throw new Error("Could not load. Please try again."); return res.json();
  }
  function setTab(t){
    tab = t;
    for(const k of ["find","stage","abroad"]) $("c_tab_"+k).classList.toggle("on", k===t);
    if(t==="find") drawForm(); else if(t==="stage") drawStages(); else drawAbroad();
  }
  $("c_tab_find").onclick = ()=>setTab("find");
  $("c_tab_stage").onclick = ()=>setTab("stage");
  $("c_tab_abroad").onclick = ()=>setTab("abroad");

  /* ---------- questionnaire ---------- */
  function drawForm(){
    const body = $("c_body");
    if(!Q){ body.innerHTML = `<div class="empty">Loading questions…</div>`; const stop = wakeHint(body);
      getJSON("/careers/questionnaire").then(q=>{stop(); Q=q; if(tab==="find") drawForm();}).catch(e=>{stop(); body.innerHTML=`<div class="empty">${esc(e.message)}</div>`;}); return; }
    const STATES = (typeof window.__hubStates!=="undefined" ? window.__hubStates : []);
    body.innerHTML = `<div class="card"><div class="hint">${esc(Q.intro)}</div>` + Q.questions.map(q=>{
      if(q.hide_if && q.hide_if.stage && q.hide_if.stage.includes(ans.stage)) return "";
      if(q.type==="state") return `<div class="q"><label class="qt" for="q_state">${esc(q.label)}</label><select id="q_state"><option value="">Skip</option>${STATES.map(s=>`<option ${ans.state===s?"selected":""}>${esc(s)}</option>`).join("")}</select></div>`;
      const multi = q.type==="multi";
      return `<div class="q"><span class="qt">${esc(q.label)}${q.required?" *":""}</span><div class="opts">` +
        q.options.map(o=>{ const on = multi ? (ans[q.id]||[]).includes(o.value) : ans[q.id]===o.value;
          return `<button type="button" class="chip${on?" on":""}" data-q="${q.id}" data-v="${esc(o.value)}" data-m="${multi?1:0}" data-max="${q.max||0}">${esc(o.label)}</button>`; }).join("") + `</div></div>`;
    }).join("") + `<div class="row"><button class="btn" id="q_go" type="button">Show my career options</button><span class="msg" id="q_msg"></span></div></div><div id="c_results"></div>`;
    body.querySelectorAll(".opts .chip").forEach(b=>b.onclick=()=>{
      const id=b.dataset.q, v=b.dataset.v;
      if(b.dataset.m==="1"){ const a=ans[id]||(ans[id]=[]), i=a.indexOf(v); if(i>=0) a.splice(i,1); else if(!+b.dataset.max || a.length<+b.dataset.max) a.push(v); }
      else { ans[id] = ans[id]===v ? undefined : v; }
      const y = window.scrollY; drawForm(); window.scrollTo(0,y);
    });
    const st=$("q_state"); if(st) st.onchange=e=>{ ans.state=e.target.value||undefined; };
    $("q_go").onclick = recommend;
  }
  async function recommend(){
    const msg=$("q_msg"); msg.className="msg";
    if(!ans.stage || !ans.budget){ msg.className="msg err"; msg.textContent="Please answer the questions marked * (your education and budget)."; return; }
    const out = $("c_results"); out.innerHTML = `<div class="empty">Finding options for you…</div>`; const stop = wakeHint(out); msg.textContent="";
    try{
      const d = await getJSON("/careers/recommend",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({stage:ans.stage,stream:ans.stream||null,interests:ans.interests||[],skills:ans.skills||[],budget:ans.budget,goal:ans.goal||null,state:ans.state||null})});
      stop();
      out.innerHTML = `<h2 style="margin:6px 0 10px">Your top options</h2><div class="cards2">${d.recommendations.map((r,i)=>pathCard(r,true,i===0)).join("")||`<div class="empty">No matching options found.</div>`}</div>`;
      out.scrollIntoView({behavior:"smooth",block:"start"});
    }catch(e){ stop(); out.innerHTML=`<div class="empty">${esc(e.message)}</div>`; }
  }

  /* ---------- path card ---------- */
  const ul = a => a && a.length ? `<ul>${a.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>` : "";
  const links = a => a && a.length ? `<div class="linklist">${a.map(l=>`<a class="lnk" href="${esc(safe(l.url))}" target="_blank" rel="noopener noreferrer">${esc(l.label)} ↗</a>`).join("")}</div>` : "";
  function pathCard(p, rec, first){
    const exams = (p.entrance_exams||[]).map(e => e.url ? `<li><a class="lnk" href="${esc(safe(e.url))}" target="_blank" rel="noopener noreferrer">${esc(e.name)} ↗</a></li>` : `<li>${esc(e.name)}</li>`).join("");
    const sch = (p.scholarships||[]).map(s=>`<li><a class="lnk" href="${esc(safe(s.official_url))}" target="_blank" rel="noopener noreferrer">${esc(s.name)} ↗</a>${s.amount_text?` — ${esc(s.amount_text)}`:""}</li>`).join("");
    const app = (p.app_links||[]).map(a=>`<li><a class="lnk" href="#${esc(a.section)}" onclick="hubGo('${esc(a.section)}');return false;">${esc(a.label)} →</a></li>`).join("");
    return `<div class="opp">
      ${rec?`<span class="fit ${p.fit==="Strong fit"?"strong":""}">${esc(p.fit)}</span>`:""}<span class="tag cat" style="margin-left:0">${esc(p.type_label)}</span>
      <h3>${esc(p.title)}</h3><p>${esc(p.summary)}</p>
      ${rec&&p.why&&p.why.length?`<p class="why">✅ ${p.why.map(esc).join(" · ")}</p>`:""}
      ${rec&&p.cautions&&p.cautions.length?`<p class="stale">⚠️ ${p.cautions.map(esc).join(" ")}</p>`:""}
      <details class="steps" ${first?"open":""}><summary>Qualifications, exams, opportunities and next steps</summary>
        <span class="lbl">Qualification needed</span><p>${esc(p.qualification)}</p>
        ${p.courses&&p.courses.length?`<span class="lbl">Courses and options</span>${ul(p.courses)}`:""}
        ${exams?`<span class="lbl">Entrance exams and admission</span><ul>${exams}</ul>`:""}
        ${p.opportunities&&p.opportunities.length?`<span class="lbl">Career opportunities</span>${ul(p.opportunities)}`:""}
        <span class="lbl">Fees</span><p>${esc(p.fees_note||"")}</p>
        <span class="lbl">Your next steps</span><ol>${(p.next_steps||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ol>
        ${sch||app?`<span class="lbl">Scholarships and related schemes</span><ul>${sch}${app}<li><a class="lnk" href="#scholarships" onclick="hubGo('scholarships');return false;">See scholarships matched to you on OpportunityHub →</a></li></ul>`:`<span class="lbl">Scholarships</span><ul><li><a class="lnk" href="#scholarships" onclick="hubGo('scholarships');return false;">See scholarships on OpportunityHub →</a></li></ul>`}
        <span class="lbl">Official websites</span>${links(p.official_links)}
      </details></div>`;
  }

  /* ---------- explore by stage ---------- */
  async function drawStages(stageId){
    const body = $("c_body");
    if(!META){ body.innerHTML=`<div class="empty">Loading…</div>`; const stop=wakeHint(body);
      try{ META = await getJSON("/careers/meta"); stop(); }catch(e){ stop(); body.innerHTML=`<div class="empty">${esc(e.message)}</div>`; return; } }
    $("c_disc").textContent = META.disclaimer;
    body.innerHTML = `<div class="card"><span class="qt" style="font-weight:700;font-size:14px">Choose where you are</span><div class="chips">${META.stages.map(s=>`<button type="button" class="chip${stageId===s.id?" on":""}" data-s="${esc(s.id)}">${esc(s.title)}</button>`).join("")}</div></div><div id="c_stage"></div>`;
    body.querySelectorAll("[data-s]").forEach(b=>b.onclick=()=>drawStages(b.dataset.s));
    if(!stageId) return;
    const out=$("c_stage"); out.innerHTML=`<div class="empty">Loading…</div>`;
    try{
      const g = await getJSON(`/careers/guide/${encodeURIComponent(stageId)}`);
      const byType = {}; g.paths.forEach(p=>(byType[p.type_label]=byType[p.type_label]||[]).push(p));
      out.innerHTML = `<div class="card"><h2>${esc(g.title)}</h2><p style="font-size:13.5px">${esc(g.summary)}</p><ul class="kp">${g.key_points.map(k=>`<li>${esc(k)}</li>`).join("")}</ul></div>` +
        Object.entries(byType).map(([t,ps])=>`<h3 style="margin:14px 0 8px;font-size:15px">${esc(t)}</h3><div class="cards2">${ps.map(p=>`<div class="opp"><h3>${esc(p.title)}</h3><p>${esc(p.summary)}</p><button type="button" class="btn btn-ghost" style="width:100%" data-p="${esc(p.id)}">View details</button><div data-d="${esc(p.id)}"></div></div>`).join("")}</div>`).join("");
      out.querySelectorAll("[data-p]").forEach(b=>b.onclick=async()=>{
        const slot=out.querySelector(`[data-d="${b.dataset.p}"]`);
        if(slot.innerHTML){ slot.innerHTML=""; b.textContent="View details"; return; }
        b.textContent="Loading…";
        try{ const p = await getJSON(`/careers/paths/${encodeURIComponent(b.dataset.p)}${ans.state?`?state=${encodeURIComponent(ans.state)}`:""}`);
          slot.innerHTML = pathCard(p,false,true).replace(/^<div class="opp">/,'<div style="margin-top:10px">'); b.textContent="Hide details";
        }catch(e){ b.textContent="Try again"; }
      });
    }catch(e){ out.innerHTML=`<div class="empty">${esc(e.message)}</div>`; }
  }

  /* ---------- study abroad ---------- */
  async function drawAbroad(){
    const body=$("c_body"); body.innerHTML=`<div class="empty">Loading…</div>`; const stop=wakeHint(body);
    try{
      if(!META) META = await getJSON("/careers/meta");
      const list = await getJSON("/careers/paths?type=study_abroad"); stop();
      $("c_disc").textContent = META.disclaimer;
      body.innerHTML = `<div class="card"><h2>Study abroad pathways</h2><div class="hint">Use official country portals and the universities' own websites. Costs and visa rules change often.</div><ul class="kp">${META.study_abroad_checklist.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div><div class="cards2">${list.map(p=>`<div class="opp"><h3>${esc(p.title)}</h3><p>${esc(p.summary)}</p><button type="button" class="btn btn-ghost" style="width:100%" data-p="${esc(p.id)}">View details</button><div data-d="${esc(p.id)}"></div></div>`).join("")}</div>`;
      body.querySelectorAll("[data-p]").forEach(b=>b.onclick=async()=>{
        const slot=body.querySelector(`[data-d="${b.dataset.p}"]`);
        if(slot.innerHTML){ slot.innerHTML=""; b.textContent="View details"; return; }
        try{ const p = await getJSON(`/careers/paths/${encodeURIComponent(b.dataset.p)}`); slot.innerHTML = pathCard(p,false,true).replace(/^<div class="opp">/,'<div style="margin-top:10px">'); b.textContent="Hide details"; }catch{ b.textContent="Try again"; }
      });
    }catch(e){ stop(); body.innerHTML=`<div class="empty">${esc(e.message)}</div>`; }
  }

  window.careersInit = (function(){ let done=false; return ()=>{ if(!done){ done=true; getJSON("/careers/meta").then(m=>{META=m;$("c_disc").textContent=m.disclaimer;}).catch(()=>{}); setTab("find"); } }; })();
})();
