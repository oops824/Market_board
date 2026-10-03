/* 기관 포트폴리오 13F 대시보드 (탭4) */
var TF=null,TF_CAT='all';
function escT(t){return String(t==null?'':t).replace(/[<>&"']/g,function(c){
  return {'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]})}
function tnum(v){return typeof v==='number'&&isFinite(v)}
function tbig(v){if(!tnum(v))return '-';var a=Math.abs(v);
  return a>=1e12?'$'+(v/1e12).toFixed(2)+'T':a>=1e9?'$'+(v/1e9).toFixed(1)+'B':
    a>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+v.toLocaleString('en-US',{maximumFractionDigits:0})}
function tpc(v){return tnum(v)?(v>=0?'+':'')+v.toFixed(0)+'%':'-'}
function tpc1(v){return tnum(v)?(v>=0?'+':'')+v.toFixed(1)+'%':'-'}
function tmd(p){var m=String(p||'').match(/^\d{4}-(\d{2})-(\d{2})/);return m?(+m[1])+'/'+(+m[2]):''}
/* 종목 이름 옆 티커·신호 칩, 값 옆 기준일 대비 현재 등락 */
function tfName(r){return escT(r.name)+(r.ticker?' <span class="tk">'+escT(r.ticker)+'</span>':'')}
function tfSince(r,period){
  if(!tnum(r.chg_since))return '';
  return '<br><span class="badge '+(r.chg_since>=0?'up':'dn')+'" title="'+escT(tmd(period))+' 종가 '+
    escT(r.px_period)+' → 현재 '+escT(r.px_now)+'">'+escT(tmd(period))+' 이후 '+tpc1(r.chg_since)+'</span>'}
function tq(p){if(!p)return '-';var m=String(p).match(/^(\d{4})-(\d{2})/);
  if(!m)return p;return m[1]+' Q'+Math.ceil(+m[2]/3)}
function tdate(s){if(!s)return '';var d=new Date(s);
  return isNaN(d)?'':(d.getMonth()+1)+'/'+d.getDate()}

/* 인물 발언: AI 요지 + 기사 목록 (영문은 번역 제목, 원문은 툴팁) */
function tfNewsList(arr){
  if(!arr||!arr.length)return '<p class="note">최근 30일 관련 기사 없음</p>';
  var h='';
  for(var k=0;k<arr.length;k++){var a=arr[k];
    if(!/^https?:\/\//.test(a.url||''))continue;
    h+='<li><a href="'+escT(newsHref(a))+'" target="_blank" rel="noopener noreferrer"'+
      (a.orig?' title="'+escT(a.orig)+'"':'')+'>'+escT(a.title)+'</a><div class="s">'+
      escT(a.source||'')+(tdate(a.published)?' · '+tdate(a.published):'')+
      (a.lang==='en'?(a.orig?' · 영문 번역':' · EN'):'')+'</div>'+koBlock(a)+'</li>'}
  return '<ul class="news">'+h+'</ul>'}
function tfPerson(name){
  var v=(TF.views||{})[name]||'',arr=(TF.news||[]).filter(function(a){return a.person===name});
  return (v?'<div class="brief tfview"><b class="ai">✦</b> '+escT(v)+'</div>':'')+tfNewsList(arr)}

/* 카테고리 필터 — 운용사 카드와 하단 뉴스에 함께 적용 */
function tfBar(){
  var cats=TF.categories||{},ks=['all'],h='';
  for(var k in cats)if(cats.hasOwnProperty(k))ks.push(k);
  for(var i=0;i<ks.length;i++){var k=ks[i];
    h+='<button class="pb'+(k===TF_CAT?' on':'')+'" data-tcat="'+escT(k)+'">'+
       escT(k==='all'?'전체':cats[k])+'</button>'}
  return '<div class="pbar tfbar">'+h+'</div>'}
function tfPass(c){return TF_CAT==='all'||c===TF_CAT}

/* 공통 매매: 2인 이상이 같은 분기에 함께 사고 판 종목 */
function tfConsensus(){
  var c=TF.consensus||{},b=c.bought||[],s=c.sold||[];
  if(!b.length&&!s.length)return '';
  function rows(l,cl){
    if(!l.length)return '<p class="note">해당 없음</p>';
    var h='';
    for(var i=0;i<l.length&&i<8;i++){var r=l[i];
      h+='<tr><td class="n">'+tfName(r)+tagsHtml(r.tags,3)+
         '<div class="sub">'+escT(r.managers.join(' · '))+'</div></td>'+
         '<td class="v"><span class="badge '+cl+'">'+r.count+'곳</span>'+
         tfSince(r,TF.latest_period)+'</td></tr>'}
    return '<table>'+h+'</table>'}
  return '<details open><summary>공통 매매 종목</summary><div class="body">'+
    '<p class="note">두 곳 이상이 같은 분기에 함께 움직인 종목입니다. '+
    '국민연금과 멀티전략·퀀트 펀드(보유 종목 수천 개)는 성격이 달라 집계에서 제외했습니다.</p>'+
    '<div class="sec">함께 사들인 종목</div>'+rows(b,'up')+
    '<div class="sec">함께 정리한 종목</div>'+rows(s,'dn')+
    '</div></details>'}

/* 운용사 카드 */
function tfRows(list,kind,period){
  if(!list||!list.length)return '<p class="note">해당 없음</p>';
  var h='';
  for(var i=0;i<list.length&&i<8;i++){
    var r=list[i],right,sub=[];
    if(r.putcall)sub.push(r.putcall==='Put'?'풋옵션':'콜옵션');
    if(kind==='sold'){right=tbig(r.value_prev)}
    else{
      right=tbig(r.value);
      if(tnum(r.weight))sub.push('비중 '+r.weight.toFixed(1)+'%')}
    h+='<tr><td class="n">'+tfName(r)+tagsHtml(r.tags,3)+
       (sub.length?'<div class="sub">'+escT(sub.join(' · '))+'</div>':'')+
       '</td><td class="v">'+right+tfSince(r,period)+
       (tnum(r.shares_chg_pct)&&(kind==='add'||kind==='trim')
         ? '<br><span class="badge '+(r.shares_chg_pct>=0?'up':'dn')+'">'+
           tpc(r.shares_chg_pct)+'</span>' : '')+
       '</td></tr>'}
  return '<table>'+h+'</table>'}

function tfManager(m){
  if(m.error){
    return '<details class="coin"><summary><div class="cr1"><div class="ch">'+
      '<b>'+escT(m.name)+'</b></div></div>'+
      '<div class="cr3"><span>수집 실패 · '+escT(m.error)+'</span></div>'+
      '</summary></details>'}
  var stale=m.stale?'<span class="badge warn">공시 중단</span>':'';
  var head='<div class="cr1"><div class="ch"><b>'+escT(m.name)+'</b></div>'+
    '<div class="cp">'+tbig(m.total_value)+'</div></div>'+
    '<div class="cr2"><div class="cn">'+escT(tq(m.period))+' 기준 · '+
    (m.position_count||0)+'종목'+'</div>'+
    (stale?'<div>'+stale+'</div>':'')+'</div>'+
    '<div class="cr3"><span>신규 '+(m.new_buys||[]).length+
    ' · 청산 '+(m.sold_out||[]).length+
    ' · 확대 '+(m.added||[]).length+
    ' · 축소 '+(m.trimmed||[]).length+'</span></div>'+
    ((TF.views||{})[m.name]?'<div class="tfv"><b class="ai">✦</b><span>'+
      escT(TF.views[m.name])+'</span></div>':'');
  var body='<div class="sec" style="margin-top:0">최근 발언·인터뷰</div>'+tfPerson(m.name)+
    '<div class="sec">상위 보유</div>'+tfRows(m.top,'top',m.period)+
    '<div class="sec">신규 편입</div>'+tfRows(m.new_buys,'new',m.period)+
    '<div class="sec">전량 청산</div>'+tfRows(m.sold_out,'sold',m.period)+
    '<div class="sec">비중 확대 <span class="dim">주식수 +10% 이상</span></div>'+
      tfRows(m.added,'add',m.period)+
    '<div class="sec">비중 축소 <span class="dim">주식수 -10% 이상</span></div>'+
      tfRows(m.trimmed,'trim',m.period)+
    '<p class="note">'+(m.stale?'공시가 오래되어 현재가 비교를 생략했습니다. ':
      '「'+escT(tmd(m.period))+' 이후」는 공시 기준일 종가 대비 현재가 등락입니다. ')+'신규·청산·확대·축소는 직전 분기('+escT(tq(m.period_prev))+') 대비. '+
    'SEC 공시일 '+escT(m.filed||'-')+'.</p>';
  return '<details class="coin"><summary>'+head+'</summary>'+
    '<div class="body">'+body+'</div></details>'}

/* 하단: 13F 카드가 없는 인물(정책 인사, 제출 중단자)의 발언·인터뷰 */
function tfNews(){
  var mg={};(TF.managers||[]).forEach(function(m){mg[m.name]=1});
  var l=(TF.news||[]).filter(function(a){return !mg[a.person]&&tfPass(a.category)});
  var order=[],seen={};
  l.forEach(function(a){if(!seen[a.person]){seen[a.person]=1;order.push(a)}});
  if(!order.length)return '';
  var h='<div class="hd">기타 인물 발언·인터뷰<small>최근 30일</small></div>';
  for(var j=0;j<order.length;j++){var p=order[j].person;
    h+='<details class="coin"><summary><div class="cr1"><div class="ch"><b>'+escT(p)+
       '</b><span class="cn">'+escT(order[j].category_label||'')+'</span></div></div>'+
       ((TF.views||{})[p]?'<div class="tfv"><b class="ai">✦</b><span>'+escT(TF.views[p])+
       '</span></div>':'')+'</summary><div class="body">'+tfPerson(p)+'</div></details>'}
  return h}

function renderTF(){
  var ms=(TF.managers||[]).filter(function(m){return tfPass(m.category)});
  var cards='';
  for(var i=0;i<ms.length;i++)cards+=tfManager(ms[i]);


  var bar='<div class="cbar"><span>'+escT(tq(TF.latest_period))+' 공시 기준</span>'+
    '<span>뉴스 '+escT(tdate(TF.news_updated_at)||'-')+'</span></div>';

  $('#tf').innerHTML=bar+tfBar()+(typeof LEGEND==='string'?LEGEND:'')+
    (TF_CAT==='all'?tfConsensus():'')+
    (cards?'<div class="hd">운용사별 포트폴리오</div>'+cards:'')+
    tfNews()+
    '<p class="note">'+escT(TF.note||'')+'</p>';

  var bs=document.querySelectorAll('#p4 .tfbar .pb');
  for(var j=0;j<bs.length;j++){
    bs[j].onclick=function(){TF_CAT=this.getAttribute('data-tcat');renderTF()}}}

function loadTF(){
  fetch('thirteenf.json?t='+Date.now())
  .then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(function(d){TF=d;
    try{renderTF()}
    catch(e){$('#tf').innerHTML='<p class="err">표시 오류: '+escT(e.message)+'</p>'}})
  .catch(function(){$('#tf').innerHTML='<p class="err">thirteenf.json이 아직 없습니다.<br>'+
    'Actions에서 thirteenf 워크플로를 한 번 실행해 주세요.</p>'})}
loadTF();
