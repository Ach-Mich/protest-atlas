(function(){
var TITLES={about:["About","À propos","Über uns"],methodology:["Methodology","Méthodologie","Methodik"],legal:["Legal notice","Mentions légales","Impressum"],privacy:["Privacy","Confidentialité","Datenschutz"]};
var page=(location.pathname.split("/").pop()||"").replace(".html","");
var info={};
function show(){var L=I18N.lang;
  document.querySelectorAll("#doc [data-l]").forEach(function(d){d.hidden=d.dataset.l!==L});
  var i=["en","fr","de"].indexOf(L),t=TITLES[page];if(t)document.title=t[i]+" · Protest Atlas";
  document.documentElement.lang=L;
  var sw=document.getElementById("sw");if(sw)sw.innerHTML=I18N.switchHTML();
  I18N.run(document.body);fill()}
function fill(){
  document.querySelectorAll("[data-info]").forEach(function(el){var k=el.dataset.info,v=(info[k]||"").trim();
    if(v){el.textContent=v;el.classList.remove("tbc");if(k==="email"&&/@/.test(v)){var a=document.createElement("a");a.href="mailto:"+v;a.textContent=v;el.textContent="";el.appendChild(a)}}
    else if(k==="registration"||k==="dataLicence"){el.hidden=true}
    else{el.textContent="[to be completed]";el.classList.add("tbc")}});
  var miss=!(info.operator||"").trim();document.querySelectorAll("[data-todo]").forEach(function(d){d.hidden=!miss||d.closest("[data-l]").dataset.l!==I18N.lang})}
window.addEventListener("pa-lang",show);
fetch("site-info.json",{cache:"no-store"}).then(function(r){return r.ok?r.json():{}}).catch(function(){return {}}).then(function(j){info=j||{};show()});
})();
