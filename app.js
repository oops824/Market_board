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
// 섹터 표는 미국주식 탭, COT 포지셔닝은 기관 탭으로 나눠 그린다
function tables(){
  var sec=function(k){return CUR.sections.filter(function(s){return s.title.indexOf(k)===0})};
  $('#app').innerHTML=secTables(CUR.sections.filter(function(s){
    return !hiddenSec(s.title)&&s.title.indexOf('섹터')!==0&&s.title.indexOf('CFTC')!==0}),2);
  var st=sec('섹터'),ct=sec('CFTC');
  $('#st-sec').innerHTML=st.length?'<div class="hd">섹터 ETF · 대장주</div>'+LEGEND+secTables(st,st.length):'';
  $('#cot').innerHTML=ct.length?'<div class="hd">CFTC 선물 포지셔닝<small>레버리지펀드 vs 자산운용사</small></div>'+
    secTables(ct,ct.length):''}
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

/* ---------- 미국 경제지표 발표 · 시장 반응 · 물가 기여도 ---------- */
function ePct(v,d){return typeof v==='number'?(v>0?'+':'')+v.toFixed(d==null?1:d)+'%':'-'}
function eMonth(p){var m=String(p||'').match(/^(\d{4})-(\d{2})/);return m?m[1]+'년 '+(+m[2])+'월':''}
function eQuarter(p){var m=String(p||'').match(/^(\d{4})-(\d{2})/);return m?m[1]+'년 '+Math.ceil(+m[2]/3)+'분기':''}
function eKv(k,v,s){return '<div class="kv"><div class="k">'+k+'</div><div class="v">'+v+'</div>'+
  (s?'<div class="s">'+s+'</div>':'')+'</div>'}
function eBars(list,mx){
  if(!list||!list.length)return '';
  mx=mx||Math.max.apply(null,list.map(function(x){return Math.abs(x.pp)}))||1;var h='';
  list.forEach(function(x){var w=Math.abs(x.pp)/mx*50,pos=x.pp>=0;
    h+='<div class="cbr"><span class="cn2">'+esc(x.name)+'<i>비중 '+x.w+'%'+
      (typeof x.mom==='number'?' · 전월비 '+ePct(x.mom,2):'')+'</i></span>'+
      '<span class="ctr"><b class="'+(pos?'up':'dn')+'" style="'+(pos?'left:50%':'right:50%')+';width:'+w.toFixed(1)+'%"></b></span>'+
      '<span class="cv '+(Math.abs(x.pp)<0.005?'':pos?'tu':'td')+'">'+(x.pp>0?'+':'')+x.pp.toFixed(2)+'%p</span></div>'});
  return h}
function eTrend(tr,key,unit){
  if(!tr||tr.length<3)return '';
  var v=tr.map(function(x){return x[key]}).filter(function(x){return typeof x==='number'});
  if(v.length<3)return '';
  var W=300,H=44,lo=Math.min.apply(null,v),hi=Math.max.apply(null,v),sp=(hi-lo)||1,d='';
  v.forEach(function(y,i){d+=(i?'L':'M')+(i*W/(v.length-1)).toFixed(1)+' '+(H-4-(y-lo)/sp*(H-8)).toFixed(1)});
  return '<div class="etr"><svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none"><path d="'+d+
    '" fill="none" stroke="var(--acc)" stroke-width="1.8" vector-effect="non-scaling-stroke"/></svg>'+
    '<span>'+esc(String(tr[0].d).slice(2,7))+' '+v[0].toFixed(1)+unit+' → '+esc(String(tr[tr.length-1].d).slice(2,7))+' '+
    v[v.length-1].toFixed(1)+unit+'</span></div>'}
function econ(){
  var E=CUR.econ;if(!E||!E.items||!E.items.length){$('#econ').innerHTML='';return}
  var h='<div class="hd">미국 경제지표 발표 · 시장 반응<small>'+esc(E.src||'')+'</small></div>';
  E.items.forEach(function(it){
    var q=it.key==='gdp'?eQuarter(it.period):eMonth(it.period),x='';
    x+='<div class="eh"><b>'+esc(it.title)+'</b><span class="cn">'+esc(q)+' 기준'+
      (it.release?' · '+esc(it.release.slice(5).replace('-','/'))+' 발표':'')+'</span></div>';
    if(it.head){
      x+='<div class="grid">'+eKv(esc(it.head.name)+' 전년비',ePct(it.head.yoy),'전월비 '+ePct(it.head.mom,2)+
          ' · 직전 '+ePct(it.head.yoy_prev))+
        eKv(esc(it.core.name)+' 전년비',ePct(it.core.yoy),'전월비 '+ePct(it.core.mom,2)+
          ' · 직전 '+ePct(it.core.yoy_prev))+'</div>'}
    else if(it.key==='unemp'){
      x+='<div class="grid">'+eKv('실업률',it.value.toFixed(1)+'%','직전 '+it.prev.toFixed(1)+'% ('+
        (it.chg>0?'+':'')+it.chg.toFixed(1)+'%p)')+'</div>'}
    else if(it.key==='gdp'){
      x+='<div class="grid">'+eKv('성장률(연율)',ePct(it.value),'직전 분기 '+ePct(it.prev))+'</div>'}
    if(it.consensus)x+='<p class="note" style="margin:8px 0 0">시장 예상: '+esc(it.consensus)+'</p>';
    if(it.market&&it.market.length){
      x+='<div class="sec">발표일 시장 반응</div><div class="tags">'+it.market.map(function(m){
        var t=m.kind==='bp'?(m.v>0?'+':'')+m.v.toFixed(1)+'bp':ePct(m.v,2);
        return '<span class="tag '+(m.v>0?'up':m.v<0?'dn':'na')+'">'+esc(m.name)+' '+t+'</span>'}).join('')+'</div>'}
    if(it.contrib&&it.contrib.length){
      x+='<div class="sec">항목별 기여도 <span class="dim">헤드라인 전월비에 대한 약 %p</span></div>'+eBars(it.contrib)}
    if(it.detail&&it.detail.length){
      // 같은 축척(위 기여도 최댓값 기준)으로 그려 크기 비교가 왜곡되지 않게
      var mx=Math.max.apply(null,(it.contrib||[]).concat(it.detail).map(function(y){return Math.abs(y.pp)}));
      x+='<div class="sec">세부 항목 <span class="dim">위 항목에 포함 · 같은 축척</span></div>'+eBars(it.detail,mx)}
    if(it.ai)x+='<div class="sec">해석</div><div class="brief"><b class="ai">✦</b> '+esc(it.ai)+'</div>';
    x+=it.head?eTrend(it.trend,'yoy','%'):eTrend(it.trend,'v','%');
    h+='<details class="etf econ"'+(it.key==='cpi'?' open':'')+'><summary>'+esc(it.title)+
      '<span class="cn">'+esc(q)+(it.head?' · '+ePct(it.head.yoy):it.value!=null?' · '+it.value.toFixed(1)+'%':'')+
      '</span></summary><div class="body">'+x+'</div></details>'});
  h+='<p class="note">기여도는 항목 비중(상대 중요도 근사치) × 전월비로 계산한 추정치입니다. 발표일 시장 반응은 전 거래일 종가 대비 발표일 종가.</p>';
  $('#econ').innerHTML=h}

function render(d){
  CUR=d;
  $('#meta').textContent='갱신 '+(d.updated||'-');
  try{kpi()}catch(e){}
  try{summary()}catch(e){}
  try{econ()}catch(e){$('#econ').innerHTML='<p class="err">경제지표 표시 오류: '+e.message+'</p>'}
  try{tables()}catch(e){$('#app').innerHTML='<p class="err">표시 오류: '+e.message+'</p>'}}

function load(p){
  fetch(p+'?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(render).catch(function(){
    $('#meta').textContent='';
    $('#app').innerHTML='<p class="err">data.json을 읽지 못했습니다.<br>'+
      '실행이 끝났는지, 1~2분 기다렸는지 확인해 주세요.</p>'})}
function tab(n){for(var i=1;i<=5;i++){$('#t'+i).className='tab'+(i===n?' on':'');
  $('#p'+i).className=i===n?'':'hide'}}
$('#t1').onclick=function(){tab(1)};
$('#t2').onclick=function(){tab(2)};
$('#t3').onclick=function(){tab(3)};
$('#t4').onclick=function(){tab(4)};
$('#t5').onclick=function(){tab(5)};

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
