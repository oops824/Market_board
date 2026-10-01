/* 종합 투자의견 (탭5) — scripts/opinion.py 가 하루 1회 만드는 opinion.json
   단기(1~4주)는 매일 갱신, 중장기(3~12개월)는 분명한 근거가 있을 때만 바뀜 */
var OP=null,OP_H='s';
try{OP_H=localStorage.getItem('opH')==='l'?'l':'s'}catch(e){}
var OP_PAL=['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
var OP_STN=['적극 축소','축소','중립','확대','적극 확대'];
var OP_ACT={'분할 매수':'up','비중 확대':'up','일부 차익실현':'dn','비중 축소':'dn','유지':'na','관망':'warn'};
var OP_ROLE={'핵심 보유':'acc','보유':'na','비중 확대':'up','비중 축소':'dn','정리':'dn'};

function opT(t){return esc(t==null?'':t)}
function opNum(v){return typeof v==='number'&&isFinite(v)}
function opPct(v){return opNum(v)?(v>=0?'+':'')+v.toFixed(1)+'%':'-'}
function opWhen(s){var m=String(s||'').match(/^\d{4}-(\d\d)-(\d\d)[T ](\d\d:\d\d)/);
  return m?(+m[1])+'/'+(+m[2])+' '+m[3]:String(s||'')}
function opMD(d){var m=String(d||'').match(/^\d{4}-(\d\d)-(\d\d)/);return m?(+m[1])+'/'+(+m[2]):String(d||'')}
function opDays(d){var t=Date.parse(String(d||'')+'T00:00:00+09:00');
  return isFinite(t)?Math.floor((Date.now()-t)/864e5)+1:null}

/* 입장 5단계: 가운데(중립)에서 확대는 오른쪽(빨강), 축소는 왼쪽(파랑)으로 채움 */
function opMeter(v){
  var k=OP_STN.indexOf(v),h='';
  for(var i=0;i<5;i++){
    var on=k===2?i===2:k>2?(i>2&&i<=k):(k>=0&&i<2&&i>=k);
    h+='<i class="'+(on?(k>2?'up':k<2?'dn':'na'):'')+'"></i>'}
  return '<div class="mtr">'+h+'</div>'}
function opCell(v){var k=OP_STN.indexOf(v);
  return '<div class="stc"><b class="'+(k>2?'tu':k>=0&&k<2?'td':'')+'">'+opT(v||'-')+'</b>'+opMeter(v)+'</div>'}

function opLongStatus(o){
  var n=opDays(OP.long_since),ck=OP.long_check,lg=o.long;
  return '<div class="lst"><b>중장기</b>'+opMD(OP.long_since)+' 수립'+(n>1?' · '+n+'일째 유지':'')+
    (ck&&ck.note?'<span>'+opMD(ck.date)+' 점검: '+opT(ck.note)+'</span>':
      lg.change_note?'<span>'+opT(lg.change_note)+'</span>':'')+'</div>'}
function opHero(o){
  var row=function(lab,sub,st){st=st||{};
    return '<div class="rl">'+lab+'<small>'+sub+'</small></div>'+opCell(st.stocks)+opCell(st.crypto)+opCell(st.cash)};
  return '<div class="pick op-hero"><div class="pk-tag">오늘의 종합의견</div>'+
    '<div class="op-hl">'+opT(o.headline)+'</div><div class="op-sm">'+opT(o.summary)+'</div>'+
    (o.forward?'<div class="op-fw"><b>앞으로의 시나리오</b>'+opT(o.forward)+'</div>':'')+
    '<div class="stg"><div></div><div class="h">주식</div><div class="h">코인</div><div class="h">현금</div>'+
    row('단기','1~4주',o.short.stance)+row('중장기','3~12개월',o.long.stance)+'</div>'+opLongStatus(o)+'</div>'}

/* 내 코인 포트폴리오: 현재 비중(막대)과 중장기 목표 비중(세로선), 단기 행동·중장기 역할 */
function opPort(o){
  var pf=OP.portfolio;if(!pf||!pf.rows)return '';
  var sa={},lr={};
  (o.short.coins||[]).forEach(function(c){sa[c.sym]=c});
  (o.long.coins||[]).forEach(function(c){lr[c.sym]=c});
  var rows=pf.rows.slice();
  (pf.unknown||[]).forEach(function(s){rows.push({sym:s,w:null,pnl:null})});
  rows.push({sym:'현금',cash:true,w:pf.cash});
  rows.forEach(function(r){r.t=r.cash?o.long.crypto_cash_pct:(lr[r.sym]||{}).target_pct});
  var mx=Math.max.apply(null,rows.map(function(r){return Math.max(r.w||0,r.t||0)}))||1;
  var h=rows.map(function(r){
    var s=sa[r.sym],l=lr[r.sym],d=opNum(r.w)&&opNum(r.t)?r.t-r.w:null;
    var arrow=d==null||Math.abs(d)<2?'':d>0?' <span class="tu">▲</span>':' <span class="td">▼</span>';
    return '<div class="pf-r"><div class="pf-1"><b>'+opT(r.sym)+(r.cash?' <span class="dim">USDT</span>':'')+'</b>'+
      (opNum(r.pnl)?'<span class="badge '+(r.pnl>=0?'up':'dn')+'">'+opPct(r.pnl)+'</span>':
        r.cash?'':'<span class="dim">비중 미입력</span>')+(r.note?'<span class="dim">'+opT(r.note)+'</span>':'')+
      '<span class="pf-w">'+(opNum(r.w)?r.w.toFixed(1)+'%':'-')+' → '+(opNum(r.t)?r.t+'%':'-')+arrow+'</span></div>'+
      '<div class="pf-bar">'+(opNum(r.w)?'<i style="width:'+(r.w/mx*100).toFixed(1)+'%"></i>':'')+
      (opNum(r.t)?'<u style="left:calc('+(r.t/mx*100).toFixed(1)+'% - 1px)"></u>':'')+'</div>'+
      (s||l?'<div class="tags">'+(s?'<span class="tag '+(OP_ACT[s.action]||'na')+'">단기 '+opT(s.action)+'</span>':'')+
        (l?'<span class="tag '+(OP_ROLE[l.role]||'na')+'">중장기 '+opT(l.role)+'</span>':'')+'</div>':'')+'</div>'}).join('');
  return '<div class="etf"><div class="eh"><b>내 코인 포트폴리오</b><span class="dim">'+opMD(pf.asof)+
    ' 기준 · 이후 시세 반영</span></div><div class="legend"><span><i style="background:var(--sub)"></i>현재 비중</span>'+
    '<span><i class="tk2"></i>중장기 목표 비중</span><span>수익률은 평단 대비</span></div>'+h+'</div>'}

/* 모델 포트폴리오: 누적 막대(2px 간격) + 색 견본·이름·비중 목록 */
function opAlloc(al){
  var a=(al||[]).filter(function(x){return x.pct>0});
  if(!a.length)return '';
  if(a.length>8){var rest=a.slice(7).reduce(function(s,x){return s+x.pct},0);
    a=a.slice(0,7).concat([{asset:'기타',pct:rest,why:''}])}
  var bar='',rows='';
  a.forEach(function(x,i){var c=OP_PAL[i];
    bar+='<i style="flex:'+x.pct+' 0 0;background:'+c+'"></i>';
    rows+='<div class="alr"><i style="background:'+c+'"></i><b>'+opT(x.asset)+'</b><span>'+x.pct+'%</span>'+
      (x.why?'<p>'+opT(x.why)+'</p>':'')+'</div>'});
  return '<div class="etf"><div class="eh"><b>전체 자산 목표 배분</b><span class="dim">주식·코인·현금</span></div>'+
    '<div class="alb">'+bar+'</div>'+rows+'</div>'}

function opCf(c){return c?'<span class="cf">확신 '+opT(c)+'</span>':''}
function opPicks(list,lab,cl){
  if(!list||!list.length)return '';
  return '<div class="oph"><span class="tag '+cl+'">'+lab+'</span></div><ul class="opl">'+list.map(function(p){
    return '<li><div class="opr"><b>'+opT(p.name)+'</b>'+(p.ticker?'<span class="tk">'+opT(p.ticker)+'</span>':'')+
      opCf(p.confidence)+'</div><div class="opw">'+opT(p.why)+'</div></li>'}).join('')+'</ul>'}
function opList(t,list,cl){
  if(!list||!list.length)return '';
  return (t?'<div class="sec">'+t+'</div>':'')+'<ol class="opn '+cl+'">'+list.map(function(x){
    return '<li>'+opT(x)+'</li>'}).join('')+'</ol>'}
function opCard(t,inner,sub){
  return inner?'<div class="etf"><div class="eh"><b>'+t+'</b>'+(sub?'<span class="dim">'+sub+'</span>':'')+'</div>'+
    inner+'</div>':''}

function opShort(o){
  var sh=o.short,ps=OP.prev_short;
  var coins=(sh.coins||[]).map(function(c){
    var was=ps&&ps.coins?ps.coins[c.sym]:null;
    return '<li><div class="opr"><b>'+opT(c.sym)+'</b><span class="tag '+(OP_ACT[c.action]||'na')+'">'+opT(c.action)+'</span>'+
      (was&&was!==c.action?'<span class="chgd">'+opMD(ps.date)+' '+opT(was)+'에서 변경</span>':'')+opCf(c.confidence)+'</div>'+
      '<div class="opw">'+opT(c.why)+'</div>'+(c.condition?'<div class="opc"><em>조건</em>'+opT(c.condition)+'</div>':'')+'</li>'}).join('');
  return opCard('단기 시각','<div class="brief">'+opT(sh.view)+'</div>','확신 '+opT(sh.confidence))+
    opCard('지금 할 일',opList('바로 실행',sh.actions_now,'')+opList('기다릴 신호',sh.wait_for,'op-q'))+
    opCard('코인 단기 대응','<ul class="opl">'+coins+'</ul>')+
    opCard('주식 단기',opPicks(sh.stocks_buy,'매수','up')+opPicks(sh.stocks_avoid,'회피','dn'))+
    opCard('단기 리스크',opList('',sh.risks,'op-w'))}

function opLong(o){
  var lg=o.long,pw={};
  ((OP.portfolio||{}).rows||[]).forEach(function(r){pw[r.sym]=r.w});
  var coins=(lg.coins||[]).map(function(c){
    return '<li><div class="opr"><b>'+opT(c.sym)+'</b><span class="tag '+(OP_ROLE[c.role]||'na')+'">'+opT(c.role)+'</span>'+
      '<span class="cf">목표 '+c.target_pct+'%'+(opNum(pw[c.sym])?' · 현재 '+pw[c.sym].toFixed(1)+'%':'')+'</span></div>'+
      '<div class="opw">'+opT(c.why)+'</div></li>'}).join('');
  var log=(OP.long_log||[]).map(function(x){
    return '<li><div class="opr"><b>'+opMD(x.date)+'</b><span class="tag '+(x.status==='변경'?'warn':'na')+'">'+
      opT(x.status)+'</span></div><div class="opw">'+opT(x.note)+'</div></li>'}).join('');
  return opCard('중장기 전략','<div class="brief">'+opT(lg.thesis)+'</div>','확신 '+opT(lg.confidence))+
    opAlloc(lg.allocation)+
    opCard('코인 중장기','<ul class="opl">'+coins+'</ul>','코인 계좌 목표 · 현금 '+opT(lg.crypto_cash_pct)+'%')+
    opCard('주식 중장기',opPicks(lg.stocks_overweight,'비중 확대','up')+opPicks(lg.stocks_underweight,'비중 축소','dn'))+
    opCard('리스크 점검',opList('주요 리스크',lg.risks,'op-w')+opList('이 의견을 바꿀 신호',lg.change_mind,'op-q'))+
    (log?opCard('중장기 의견 변경 이력','<ul class="opl">'+log+'</ul>'):'')}

/* 지난 단기 의견: 당시 가격 대비 지금, 매수·확대는 상승이면 적중, 축소·차익실현·회피는 하락이면 적중 */
function opTrack(tr){
  var h='<div class="etf"><div class="eh"><b>지난 단기 의견 성과</b><span class="dim">의견 당시 가격 → 지금</span></div>';
  if(!tr||!tr.length)return h+'<p class="note" style="margin:0">첫 의견입니다. 다음 의견부터 이전 의견의 '+
    '매수·축소 판단이 실제로 맞았는지 여기서 확인할 수 있습니다.</p></div>';
  var n=0,w=0,rows='';
  tr.forEach(function(r){
    var chips=(r.calls||[]).filter(function(c){return c.hit!=null}).map(function(c){n++;if(c.hit)w++;
      return '<span class="tag '+(c.chg>0?'up':c.chg<0?'dn':'na')+'">'+opT(c.name)+' '+opT(c.action)+' '+
        opPct(c.chg)+' '+(c.hit?'✓':'×')+'</span>'}).join('');
    var st=r.stance||{};
    rows+='<li><div class="opr"><b>'+opMD(r.date)+'</b>'+
      '<span class="dim">주식 '+opT(st.stocks||'-')+' · 코인 '+opT(st.crypto||'-')+' · 현금 '+opT(st.cash||'-')+'</span></div>'+
      '<div class="opw">'+opT(r.headline)+'</div>'+(chips?'<div class="tags">'+chips+'</div>':'')+'</li>'});
  return h+(n?'<div class="ops">방향 적중 <b>'+w+'/'+n+'</b> <span class="dim">('+Math.round(w*100/n)+'%) · '+
    '매수·확대는 오르면, 축소·차익실현·회피는 내리면 적중</span></div>':'')+'<ul class="opl">'+rows+'</ul></div>'}

/* 웹 검색으로 모은 최근 뉴스·전문가 전망 (접힘) */
function opOutlook(){
  if(!OP.outlook)return '';
  var src=(OP.sources||[]).map(function(x){
    return '<li><a href="'+escA(x.url)+'" target="_blank" rel="noopener">'+opT(x.title)+'</a></li>'}).join('');
  return '<details class="etf econ"><summary>뉴스·전문가 전망<span class="cn">출처 '+(OP.sources||[]).length+
    '곳</span></summary><div class="body"><div class="brief op-ol">'+opT(OP.outlook)+'</div>'+
    (src?'<div class="sec">출처</div><ul class="news op-src">'+src+'</ul>':'')+'</div></details>'}

function opBody(){return OP_H==='l'?opLong(OP.opinion):opShort(OP.opinion)}
function renderOP(){
  var o=OP.opinion||{},asof=OP.asof||{},age=(Date.now()-Date.parse(OP.generated||''))/36e5;
  if(!o.short||!o.long){$('#p5').innerHTML='<p class="err">단기·중장기 의견을 준비하고 있습니다.</p>';return}
  var bar='<div class="cbar"><span>'+opT(opWhen(OP.generated))+' 작성 · 매일 아침</span>'+
    (asof['지표']?'<span>지표 '+opT(opWhen(asof['지표']))+' 기준</span>':'')+'</div>';
  var stale=age>36?'<p class="note" style="color:var(--warn)">최근 생성에 실패해 '+Math.floor(age/24)+
    '일 전 의견을 표시하고 있습니다.</p>':'';
  var seg='<div class="seg">'+[['s','단기','1~4주'],['l','중장기','3~12개월']].map(function(x){
    return '<button data-h="'+x[0]+'"'+(OP_H===x[0]?' class="on"':'')+'>'+x[1]+'<small>'+x[2]+'</small></button>'}).join('')+'</div>';
  $('#p5').innerHTML=bar+stale+opHero(o)+opOutlook()+opPort(o)+seg+'<div id="opb">'+opBody()+'</div>'+opTrack(OP.track)+
    '<p class="note">위험 성향 10점 중 7.5~8점(공격적) 기준. 대시보드 데이터에 웹 검색한 최근 뉴스·전문가 전망을 더해 판단합니다. 단기 의견은 매일 아침 지표 갱신 직후 새로 쓰고, 중장기 의견은 매크로 체제 전환처럼 분명한 근거가 있을 때만 '+
    '바꿉니다. 포트폴리오는 '+opT(opMD((OP.portfolio||{}).asof))+' 사진 기준 비중·평단·수익률(수량·금액은 저장하지 않음)에 '+
    '이후 가격 변동을 반영한 추정치입니다. 데이터 기준: 지표 '+opT(asof['지표']||'-')+', 코인 '+opT(asof['코인']||'-')+
    ', 기관 13F '+opT(asof['기관']||'-')+' 공시.'+(OP.model?' 작성 모델 '+opT(OP.model)+'.':'')+'</p>';
  [].forEach.call(document.querySelectorAll('#p5 .seg button'),function(b){b.onclick=function(){
    OP_H=this.getAttribute('data-h');try{localStorage.setItem('opH',OP_H)}catch(e){}
    [].forEach.call(document.querySelectorAll('#p5 .seg button'),function(x){
      x.className=x.getAttribute('data-h')===OP_H?'on':''});
    $('#opb').innerHTML=opBody()}})}

function loadOP(){
  fetch('opinion.json?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(function(d){OP=d;
    try{renderOP()}catch(e){$('#p5').innerHTML='<p class="err">표시 오류: '+opT(e.message)+'</p>'}})
  .catch(function(){
    $('#p5').innerHTML='<p class="err">opinion.json이 아직 없습니다.<br>'+
      'Actions에서 market-board 워크플로를 한 번 실행하면 만들어집니다.</p>';
    if($('#t5').className.indexOf('on')>=0)tab(1)})}
loadOP();
