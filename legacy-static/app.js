const S={file:null,stage:"idle"};
const NAV=[["notices","Notices"],["reconciliation","Reconciliation"],["evidence","Evidence"],["replies","Replies"]];
const $=s=>document.querySelector(s);
const esc=t=>String(t).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const D='<span class="mono" style="color:var(--mut)">–</span>';

/* components */
const PageHeader=(crumb,t,s,a="")=>`<div class="crumb lbl">${crumb}</div><div class="ph"><div><h1>${t}</h1><p class="sub">${s}</p></div><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">${a}</div></div>`;
const UploadBtn=c=>`<button class="btn ${c||"t"}" onclick="openUpload()">Upload notice</button>`;
const EmptyState=(t,d,a="")=>`<div class="empty"><b>${t}</b><p>${d}</p>${a}</div>`;
const StatusBadge=(l,k="")=>`<span class="badge ${k}">${l}</span>`;
const DeadlineBadge=d=>StatusBadge(d||"No deadline",d?"warn":"");
const MetadataRow=(k,v)=>`<div class="mr"><span>${k}</span>${v??D}</div>`;
const Card=(t,body,act="")=>`<section class="card"><div class="ch"><h2>${t}</h2>${act}</div>${body}</section>`;
const Tabs=l=>`<div class="tabs" role="group" aria-label="Filter">${l.map((x,i)=>`<button aria-pressed="${i==0}" disabled>${x} <span class="mono" style="color:var(--mut)">0</span></button>`).join("")}</div>`;
const DataTable=(cols,emptyT,emptyD,emptyA="")=>`<div class="tw"><table><thead><tr>${cols.map(c=>`<th class="${/value|diff|amount|source/i.test(c)?"r":""}">${c}</th>`).join("")}</tr></thead><tbody><tr><td colspan="${cols.length}">${EmptyState(emptyT,emptyD,emptyA)}</td></tr></tbody></table></div>`;
const ReviewBanner=()=>`<div class="banner" role="note"><b>Review required before submission.</b><span style="color:var(--mut)">NoticePilot does not submit responses to the GST portal.</span></div>`;
const DocumentPreview=(t="No document loaded",d="The uploaded notice will be shown here.")=>`<div class="viewer"><div class="page" style="display:grid;place-items:center;text-align:center;color:var(--mut)"><div><b class="ser" style="font-size:18px;color:var(--pri)">${t}</b><br>${d}</div></div></div>`;
const STAGES=["Upload","Read document","Extract fields","Reconcile","Check evidence","Prepare review"];
const Timeline=()=>{const st=S.stage;return `<ol class="tl">${STAGES.map((n,i)=>{let k="",note="Not connected";
 if(i==0){if(st=="processing"){k="run";note="Receiving file"}else if(st=="done"){k="done";note="File received"}else note=S.file?"Ready":"Waiting for a file"}
 return `<li><span class="dot ${k}"></span><div><b>${n}</b><small>${note}</small></div></li>`}).join("")}</ol>`};
function toast(m){const t=$("#toast");t.textContent=m;t.hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>t.hidden=true,2400)}

/* pages */
const strip=()=>`<div class="card strip">${[["Notice intake","Upload and read"],["Reconcile","Return data comparison"],["Evidence","Invoices and records"],["Reply","Review-ready draft"]].map(([n,d],i)=>`<div class="step ${i?"":"on"}"><span class="n">0${i+1}</span><div><b>${n}</b><small>${d}</small></div></div>`).join("")}</div>`;
const stat=(t,u,a,b)=>`<div class="card stat"><div class="lbl">${t}</div><div class="big">0<small>${u}</small></div><div class="row"><span>${a}</span><span class="mono">${b}</span></div></div>`;
const P={
dashboard:()=>PageHeader("Overview / Compliance deck","Dashboard","Review your GST notices and response workflow.",`<span class="badge">Active GSTIN: not set</span>`)+ReviewBanner()+strip()+
 `<div class="grid g4">${stat("Active notices","none open","No urgent items","–")}${stat("Deadlines","none tracked","Set from notice","–")}${stat("Under review","files","Nothing waiting","–")}${stat("Replies ready","drafts","Nothing drafted","–")}</div>`+
 `<div class="alert"><span class="t">Action required</span><h2 class="h2s">No notice needs action</h2><p class="sub">Upload a GST notice to begin your first review. Details will fill in after processing.</p>
 <div class="f">${["Notice amount","Tax period","Deadline","Issuing authority"].map(k=>`<div><div class="lbl">${k}</div><span class="ph-v"></span></div>`).join("")}</div></div>`+
 `<div class="grid g11">`+Card("Deadlines",EmptyState("No deadlines to track","Deadlines will appear after a notice is processed."))+Card("Recent activity",EmptyState("No activity yet","Your processing history will appear here."))+`</div>`+
 `<div style="height:16px"></div>`+Card("Recent notices",`<div class="ch" style="border-top:0"><span class="badge">0 files</span>${Tabs(["All","Action required","Draft ready","Resolved"])}</div>`+DataTable(["Notice ref","Type","Period","Difference","Status","Deadline"],"No notices yet","Upload a GST notice to begin.",UploadBtn("n"))+`<div class="foot-t"><span>Showing 0 of 0 notices</span><span>Total difference: <span class="mono">–</span></span></div>`),
notices:()=>PageHeader("Workspace / Notices","Notices","All notices received from the GST portal.",UploadBtn())+
 Card("Notice register",`<div class="ch" style="border-top:0">${Tabs(["All","Action required","Draft ready","Resolved"])}</div>`+DataTable(["Notice","Type","Tax period","Status","Deadline","Actions"],"No notices found","Upload a GST notice to start.",UploadBtn("n"))+`<div class="foot-t"><span>Showing 0 of 0 notices</span><a href="#/notices/detail" style="color:var(--sec)">Preview empty notice detail</a></div>`),
detail:()=>PageHeader("Notices / Detail","Notice details","Notice details will appear after processing.",`${StatusBadge("Not processed")} ${DeadlineBadge()}`)+ReviewBanner()+
 `<div class="grid g2"><div class="grid">`+Card("Notice header",`<div class="cb">${["Notice number","Notice type","Tax period","Issue date"].map(k=>MetadataRow(k)).join("")}</div>`)+
 Card("Mismatch summary",`<div class="cb">${["Notice amount","Amount in return A","Amount in return B","Difference"].map(k=>MetadataRow(k)).join("")}</div>`)+
 Card("Requested action",EmptyState("Not extracted","The action requested in the notice will appear after processing."))+
 `</div><div class="grid">`+Card("Deadline",`<div class="cb">${MetadataRow("Reply by")}${MetadataRow("Days remaining")}</div>`)+Card("Source document",`<div class="cb">${DocumentPreview()}</div>`)+Card("Processing status",`<div class="cb">${Timeline()}</div>`)+`</div></div>`,
reconciliation:()=>PageHeader("Workspace / Reconciliation","Reconciliation",`<span class="mono">Notice ref: –</span> &nbsp; <span class="mono">Period: –</span> &nbsp; <span class="mono">Total mismatch: –</span>`,
 `<button class="btn" disabled>Export Excel</button><button class="btn" disabled>Re-run rules check</button><button class="btn n" disabled>Match settings</button>`)+ReviewBanner()+
 `<section class="card"><div class="ch">${Tabs(["All","Matched","Mismatch","Needs evidence"])}<div class="srch" style="width:280px;height:30px"><input placeholder="Search by invoice no, GSTIN or ledger" aria-label="Search rows" disabled></div></div>`+
 DataTable(["#","Reference","Date","Description","Source A","Source B","Difference","Status","Linked evidence","Action"],"Reconciliation not available","Upload the required return data to begin reconciliation.")+
 `<div class="foot-t"><span>Records: 0 of 0 · Selected: none</span><span>Total A: <span class="mono">–</span> · Total B: <span class="mono">–</span> · Net variance: <span class="mono">–</span> · Unresolved: <span class="mono">–</span></span></div></section>`+
 `<div style="display:flex;justify-content:space-between;align-items:center;margin:20px 0 10px;flex-wrap:wrap;gap:8px"><span class="h2s">Discrepancy diagnostics and rule analysis</span><span style="display:flex;gap:8px"><button class="btn" disabled>Rule reference</button><button class="btn t" disabled>Draft reply clause</button></span></div>`+
 `<div class="grid g11">${Card("Rule analysis",EmptyState("No analysis","Select a finding after reconciliation to see the rule applied."))}${Card("Required evidence set",EmptyState("No evidence required yet","Required records will be listed per finding."),"")}</div>`,
evidence:()=>PageHeader("Workspace / Evidence","Evidence","Supporting records linked to reconciliation findings.")+
 Card("Evidence index",`<div class="ch" style="border-top:0">${Tabs(["All","Attached","Unlinked"])}</div>`+DataTable(["ID","Document","Finding","Source","Status"],"No evidence collected","Evidence will appear when processed records are linked to a finding.")+`<div class="foot-t"><span>0 records</span><span></span></div>`),
replies:()=>PageHeader("Workspace / Replies","Reply draft","Prepared from reconciled records once available.",`<button class="btn" disabled>Save draft</button><button class="btn t" disabled>Request review</button><button class="btn n" disabled>Export PDF</button>`)+ReviewBanner()+
 `<div class="grid g2"><section class="card"><div class="tool">${["B","I","U","•","1."].map(x=>`<button disabled aria-label="Format ${x}">${x}</button>`).join("")}<span class="badge" style="margin-left:auto">No draft</span></div>
 <div class="viewer" style="border:0;border-radius:0"><div class="page"><div style="text-align:center;margin-bottom:24px"><div class="lbl">Response document</div><b class="ser" style="font-size:22px;color:var(--pri)">No response draft</b><p class="sub">Complete a reconciliation before preparing a response.</p></div><div class="rule l"></div><div class="rule l"></div><div class="rule"></div></div></div>
 <div class="verify"><div class="lbl" style="margin-bottom:8px">Reviewer verification</div><label><input type="checkbox" disabled> A reviewer confirms the reconciliation and evidence here, once a draft exists.</label></div></section>
 <div class="grid" style="align-content:start">${Card("Referenced documents",EmptyState("No documents linked","Evidence attached to the draft will be listed here."),`<span class="badge">0 linked</span>`)}${Card("Reconciler check",`<div class="cb">${["Source A total","Source B total","Net differential"].map(k=>MetadataRow(k)).join("")}</div>`)}</div></div>`,
settings:()=>PageHeader("Workspace / Settings","Settings","Preferences for this workspace.")+
 `<section class="card">`+[["Profile","<input type='text' placeholder='Name' aria-label='Name'>"],["Language","<select aria-label='Language'><option>English</option><option>Hindi</option><option>Marathi</option></select>"],["Document preferences","<select aria-label='Export format'><option>PDF</option><option>DOCX</option></select>"],["Review preferences","<label><input type='checkbox' checked disabled> Require review before export</label>"],["Rule pack",`<span class="sub">Rule pack will be connected in the processing layer.</span>`]].map(([t,c])=>`<div class="set"><h2>${t}</h2><div>${c}</div></div>`).join("")+`</section>`
};

/* upload modal */
function openUpload(){if(S.stage=="done"){S.file=null;S.stage="idle"}drawModal()}
function closeModal(){$("#modal").innerHTML="";render()}
function drawModal(){
 const f=S.file,st=S.stage;let body;
 if(st=="done")body=`<div class="cb">${StatusBadge("File received","ok")}<p><b class="mono">${esc(f.name)}</b> was received. Extraction, reconciliation and evidence checks are not connected yet, so no fields were read.</p>${Timeline()}</div>`;
 else if(st=="processing")body=`<div class="cb">${Timeline()}</div>`;
 else body=`<div class="cb"><label class="drop" id="dz"><input id="fi" type="file" accept=".pdf,.txt,application/pdf,text/plain" hidden>${f?`<b class="mono">${esc(f.name)}</b><br><span class="sub">Ready for processing</span>`:`<b>Drop your file here or choose a file</b><br><span class="sub">PDF or TXT</span>`}</label></div>`;
 const act=st=="done"?`<button class="btn n" onclick="closeModal()">Close</button>`:st=="processing"?"":`<button class="btn" onclick="closeModal()">Cancel</button><button class="btn t" ${f?"":"disabled"} onclick="processFile()">Process notice</button>`;
 $("#modal").innerHTML=`<div class="modal" role="dialog" aria-modal="true" aria-label="Upload GST notice"><div class="md"><div class="ch"><div><h2 class="h2s">Upload GST notice</h2><span class="sub">Upload the notice you received from the GST portal.</span></div></div>${body}<div class="ch" style="border-top:1px solid var(--bd);border-bottom:0;justify-content:flex-end">${act}</div></div></div>`;
 const fi=$("#fi"),dz=$("#dz");if(fi){fi.onchange=()=>pick(fi.files[0]);dz.ondragover=e=>{e.preventDefault();dz.classList.add("h")};dz.ondragleave=()=>dz.classList.remove("h");dz.ondrop=e=>{e.preventDefault();pick(e.dataTransfer.files[0])}}
}
function pick(f){if(!f)return;if(!/\.(pdf|txt)$/i.test(f.name)){toast("Only PDF or TXT files are accepted");return}S.file=f;S.stage="ready";drawModal()}
function processFile(){S.stage="processing";drawModal();setTimeout(()=>{S.stage="done";drawModal();toast("File received")},1200)}
addEventListener("keydown",e=>{if(e.key=="Escape"&&$("#modal").innerHTML&&S.stage!="processing")closeModal()});

/* router */
function render(){
 const h=location.hash.replace(/^#\//,"")||"dashboard";
 const key=h=="notices/detail"?"detail":(P[h]?h:"dashboard");
 const cur=key=="detail"?"notices":key;
 $("#nav").innerHTML=NAV.map(([k,l])=>`<a href="#/${k}" ${k==cur?'aria-current="page"':""}>${l}</a>`).join("");
 $("#app").innerHTML=P[key]();
 document.title=(key=="detail"?"Notice details":key[0].toUpperCase()+key.slice(1))+" · NoticePilot";
 scrollTo(0,0);
}
addEventListener("hashchange",render);render();
