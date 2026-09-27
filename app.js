var $=function(s){return document.querySelector(s)};
var CUR=null;
function esc(t){return String(t==null?'':t).replace(/[<>&]/g,function(c){
  return {'<':'&lt;','>':'&gt;','&':'&amp;'}[c]})}
// 코인 탭으로 옮긴 섹션(COIN_SECS)과 삭제한 섹션: 지표 탭에서는 표시하지 않음
var COIN_SECS=['DeFiLlama','스테이블코인','코인베이스 프리미엄'],DROP_SECS=['하이퍼리퀴드'];
function hiddenSec(t){var l=COIN_SECS.concat(DROP_SECS);
  for(var i=0;i<l.length;i++)if(String(t).indexOf(l[i])>=0)return true;return false}
function tagsHtml(tags,n){
  if(!tags||!tags.length)return '';
  var h='';
  for(var i=0;i<tags.length&&i<(n||9);i++){var t=tags[i];
    h+='<span class="tag '+({up:'up',dn:'dn',warn:'warn'}[t.c]||'na')+'">'+esc(t.t)+'</span>'}
  return '<div class="tags">'+h+'</div>'}
var LEGEND='<div class="legend"><span><i style="background:var(--up)"></i>상승 신호</span>'+
  '<span><i style="background:var(--dn)"></i>하락 신호</span>'+
  '<span><i style="background:var(--warn)"></i>과열·주의</span></div>';
function cls(c){if(!c)return 'na';return String(c).trim().charAt(0)==='-'?'dn':'up'}

function findItem(title,kw){
  if(!CUR)return null;
  for(var i=0;i<CUR.sections.length;i++){var s=CUR.sections[i];
    if(s.title.indexOf(title)<0)continue;
    for(var j=0;j<s.items.length;j++){
      if(s.items[j].name.indexOf(kw)>=0)return s.items[j]}}
  return null}

function kpi(){
  var picks=[['매크로','변동성 VIX','VIX'],['매크로','달러지수','달러'],
             ['매크로','HYG/TLT','위험선호'],['매크로','10년 국채금리','10년 금리']];
  var h='';
  for(var i=0;i<picks.length;i++){
    var it=findItem(picks[i][0],picks[i][1]);
    if(!it)continue;
    h+='<div><div class="k">'+picks[i][2]+'</div><div class="v">'+esc(it.value)+
       '</div><div class="c"><span class="badge '+cls(it.change)+'">'+
       (esc(it.change)||'-')+'</span></div></div>'}
  $('#kpi').innerHTML=h}

function summary(){
  if(!CUR.summary){$('#sum').innerHTML='';return}
  var parts=CUR.summary.split(/\n(?=\[)/),h='';
  for(var i=0;i<parts.length;i++){
    var m=parts[i].match(/^\[(.+?)\]\s*([\s\S]*)$/);
    if(m){h+='<div class="sum"><b>'+esc(m[1])+'</b>'+
      esc(m[2].trim()).replace(/^- /gm,'· ')+'</div>'}
    else if(parts[i].trim()){h+='<div class="sum">'+esc(parts[i].trim())+'</div>'}}
  $('#sum').innerHTML=h}
function badges(it){
  if(it.badges&&it.badges.length){
    var s='';
    for(var i=0;i<it.badges.length;i++){
      s+='<br><span class="badge '+(it.badges[i].c||'na')+'">'+
         esc(it.badges[i].t)+'</span>'}
    return s}
  return it.change?'<br><span class="badge '+cls(it.change)+'">'+
         esc(it.change)+'</span>':''}
function tables(){
  $('#app').innerHTML=secTables(CUR.sections.filter(function(s){return !hiddenSec(s.title)}),2)}
function secTables(secs,nOpen){
  var h='';
  for(var i=0;i<secs.length;i++){
    var s=secs[i],rows='';
    for(var j=0;j<s.items.length;j++){
      var it=s.items[j],lead=it.name.indexOf('└')>=0;
      rows+='<tr class="'+(lead?'lead':'')+'"><td class="n">'+
        esc(it.name.replace('└','↳'))+tagsHtml(it.tags,3)+
        (it.comment?'<div class="sub">'+esc(it.comment)+'</div>':'')+
        '</td><td class="v">'+esc(it.value)+
        badges(it)+
        '</td></tr>'}
    h+='<details'+(i<nOpen?' open':'')+'><summary>'+esc(s.title)+'</summary><div class="body">'+
       (s.note?'<p class="note">'+esc(s.note)+'</p>':'')+
       (s.items.some(function(x){return x.tags&&x.tags.length})?LEGEND:'')+
       '<table>'+rows+'</table></div></details>'}
  return h}

function render(d){
  CUR=d;
  $('#meta').textContent='갱신 '+(d.updated||'-');
  try{kpi()}catch(e){}
  try{summary()}catch(e){}
  try{tables()}catch(e){$('#app').innerHTML='<p class="err">표시 오류: '+e.message+'</p>'}}

function load(p){
  fetch(p+'?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(render).catch(function(){
    $('#meta').textContent='';
    $('#app').innerHTML='<p class="err">data.json을 읽지 못했습니다.<br>'+
      '실행이 끝났는지, 1~2분 기다렸는지 확인해 주세요.</p>'})}
function tab(n){for(var i=1;i<=3;i++){$('#t'+i).className='tab'+(i===n?' on':'');
  $('#p'+i).className=i===n?'':'hide'}}
$('#t1').onclick=function(){tab(1)};
$('#t2').onclick=function(){tab(2)};
$('#t3').onclick=function(){tab(3)};

fetch('reports/list.json?t='+Date.now())
.then(function(r){return r.ok?r.json():Promise.reject()}).then(function(l){
  if(!l.length)return;
  var s=$('#arc');s.className='';
  var o='<option value="data.json">최신 리포트</option>';
  for(var i=0;i<l.length;i++){o+='<option value="reports/'+l[i]+'">'+
    l[i].replace('.json','')+'</option>'}
  s.innerHTML=o;
  s.onchange=function(){load(s.value)}}).catch(function(){});

load('data.json');
