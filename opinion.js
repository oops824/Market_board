/* 종합 투자의견 (탭5) — scripts/opinion.py 가 하루 1회 만드는 opinion.json */
var OP=null;
var OP_PAL=['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
var OP_STN=['적극 축소','축소','중립','확대','적극 확대'];
var OP_ACT={'분할 매수':'up','비중 확대':'up','일부 차익실현':'dn','비중 축소':'dn','유지':'na','관망':'warn'};
var OP_COINS=['BTC','ETH','SOL','HYPE','LINK','ONDO','SUI','VIRTUAL'];

function opT(t){return esc(t==null?'':t)}
function opNum(v){return typeof v==='number'&&isFinite(v)}
function opPct(v){return opNum(v)?(v>=0?'+':'')+v.toFixed(1)+'%':'-'}
function opWhen(s){var m=String(s||'').match(/^\d{4}-(\d\d)-(\d\d)[T ](\d\d:\d\d)/);
  return m?(+m[1])+'/'+(+m[2])+' '+m[3]:String(s||'')}

/* 입장 5단계: 가운데(중립)에서 확대는 오른쪽(빨강), 축소는 왼쪽(파랑)으로 채움 */
function opMeter(v){
  var k=OP_STN.indexOf(v),h='';
  for(var i=0;i<5;i++){
    var on=k===2?i===2:k>2?(i>2&&i<=k):(k>=0&&i<2&&i>=k);
    h+='<i class="'+(on?(k>2?'up':k<2?'dn':'na'):'')+'"></i>'}
  return '<div class="mtr">'+h+'</div>'}
function opStance(st){
  return '<div class="stn">'+[['주식','stocks'],['코인','crypto'],['현금','cash']].map(function(x){
    var v=(st||{})[x[1]]||'-',k=OP_STN.indexOf(v);
    return '<div><div class="k">'+x[0]+'</div><div class="v '+(k>2?'tu':k>=0&&k<2?'td':'')+'">'+
      opT(v)+'</div>'+opMeter(v)+'</div>'}).join('')+'</div>'}

function opHero(o){
  return '<div class="pick op-hero"><div class="pk-tag">오늘의 종합의견</div>'+
    '<div class="op-hl">'+opT(o.headline)+'</div>'+
    '<div class="op-sm">'+opT(o.summary)+'</div>'+opStance(o.stance)+
    '<div class="tags"><span class="tag na">투자 시계 '+opT(o.horizon)+'</span>'+
    '<span class="tag na">전체 확신 '+opT(o.confidence)+'</span></div></div>'}

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
  return '<div class="etf"><div class="eh"><b>모델 포트폴리오</b><span class="dim">내가 지금 새로 짠다면</span></div>'+
    '<div class="alb">'+bar+'</div>'+rows+'</div>'}

function opCf(c){return c?'<span class="cf">확신 '+opT(c)+'</span>':''}
function opPicks(list,lab,cl){
  if(!list||!list.length)return '';
  return '<div class="oph"><span class="tag '+cl+'">'+lab+'</span></div><ul class="opl">'+list.map(function(p){
    return '<li><div class="opr"><b>'+opT(p.name)+'</b>'+(p.ticker?'<span class="tk">'+opT(p.ticker)+'</span>':'')+
      opCf(p.confidence)+'</div><div class="opw">'+opT(p.why)+'</div></li>'}).join('')+'</ul>'}
function opStocks(s,stance){
  if(!s)return '';
  return '<div class="etf"><div class="eh"><b>주식</b><span class="dim">'+opT(stance)+'</span></div>'+
    '<div class="brief">'+opT(s.view)+'</div>'+
    opPicks(s.overweight,'비중 확대','up')+opPicks(s.underweight,'비중 축소','dn')+
    opPicks(s.watch,'관심·대기','warn')+'</div>'}

function opCoins(cr,stance){
  if(!cr)return '';
  var cs=(cr.coins||[]).slice().sort(function(a,b){
    return OP_COINS.indexOf(a.sym)-OP_COINS.indexOf(b.sym)});
  return '<div class="etf"><div class="eh"><b>보유 코인 8종</b><span class="dim">'+opT(stance)+'</span></div>'+
    '<div class="brief">'+opT(cr.view)+'</div><ul class="opl">'+cs.map(function(c){
      return '<li><div class="opr"><b>'+opT(c.sym)+'</b><span class="tag '+(OP_ACT[c.action]||'na')+'">'+
        opT(c.action)+'</span>'+opCf(c.confidence)+'</div><div class="opw">'+opT(c.why)+'</div>'+
        (c.condition?'<div class="opc"><em>조건</em>'+opT(c.condition)+'</div>':'')+'</li>'}).join('')+
    '</ul></div>'}

function opList(t,list,cl){
  if(!list||!list.length)return '';
  return '<div class="sec">'+t+'</div><ol class="opn '+cl+'">'+list.map(function(x){
    return '<li>'+opT(x)+'</li>'}).join('')+'</ol>'}

/* 지난 의견: 당시 가격 대비 지금, 매수·확대는 상승이면 적중, 축소·차익실현은 하락이면 적중 */
function opTrack(tr){
  var h='<div class="etf"><div class="eh"><b>지난 의견 성과</b><span class="dim">의견 당시 가격 → 지금</span></div>';
  if(!tr||!tr.length)return h+'<p class="note" style="margin:0">첫 의견입니다. 다음 의견부터 이전 의견의 '+
    '매수·축소 판단이 실제로 맞았는지 여기서 확인할 수 있습니다.</p></div>';
  var n=0,w=0,rows='';
  tr.forEach(function(r){
    var chips=(r.calls||[]).filter(function(c){return c.hit!=null}).map(function(c){n++;if(c.hit)w++;
      return '<span class="tag '+(c.chg>0?'up':c.chg<0?'dn':'na')+'">'+opT(c.name)+' '+opT(c.action)+' '+
        opPct(c.chg)+' '+(c.hit?'✓':'×')+'</span>'}).join('');
    var st=r.stance||{};
    var dm=String(r.date||'').match(/-(\d\d)-(\d\d)$/);
    rows+='<li><div class="opr"><b>'+(dm?(+dm[1])+'/'+(+dm[2]):opT(r.date))+'</b>'+
      '<span class="dim">주식 '+opT(st.stocks||'-')+' · 코인 '+opT(st.crypto||'-')+' · 현금 '+opT(st.cash||'-')+'</span></div>'+
      '<div class="opw">'+opT(r.headline)+'</div>'+(chips?'<div class="tags">'+chips+'</div>':'')+'</li>'});
  return h+(n?'<div class="ops">방향 적중 <b>'+w+'/'+n+'</b> <span class="dim">('+Math.round(w*100/n)+'%) · '+
    '매수·확대는 오르면, 축소·차익실현은 내리면 적중</span></div>':'')+
    '<ul class="opl">'+rows+'</ul></div>'}

function opCard(t,inner){
  return inner?'<div class="etf"><div class="eh"><b>'+t+'</b></div>'+inner+'</div>':''}

function renderOP(){
  var o=OP.opinion||{},st=o.stance||{},asof=OP.asof||{},
    age=(Date.now()-Date.parse(OP.generated||''))/36e5;
  var bar='<div class="cbar"><span>'+opT(opWhen(OP.generated))+' 작성 · 하루 1회</span>'+
    '<span>지표 '+opT(opWhen(asof['지표']))+' 기준</span></div>';
  var stale=age>36?'<p class="note" style="color:var(--warn)">최근 생성에 실패해 '+Math.floor(age/24)+
    '일 전 의견을 표시하고 있습니다.</p>':'';
  $('#p5').innerHTML=bar+stale+opHero(o)+
    opCard('지금 할 일',opList('바로 실행',o.actions_now,'')+opList('기다릴 신호',o.wait_for,'op-q'))+
    opAlloc(o.allocation)+opStocks(o.stocks,st.stocks)+opCoins(o.crypto,st.crypto)+
    opCard('리스크 점검',opList('주요 리스크',o.risks,'op-w')+opList('이 의견을 바꿀 신호',o.change_mind,'op-q'))+
    opTrack(OP.track)+
    '<p class="note">매일 아침 지표 갱신 직후 대시보드 전체 데이터(매크로·경제지표·섹터·COT·코인 파생·ETF 흐름·'+
    '도미넌스·13F)를 근거로 작성합니다. 가정: 한국 거주 개인투자자 · 투자 시계 1~3개월 · 중간 이상 위험 감수 · '+
    '관심 코인 8종 보유. 데이터 기준: 지표 '+opT(asof['지표']||'-')+', 코인 '+opT(asof['코인']||'-')+
    ', 기관 13F '+opT(asof['기관']||'-')+' 공시.'+(OP.model?' 작성 모델 '+opT(OP.model)+'.':'')+'</p>'}

function loadOP(){
  fetch('opinion.json?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(function(d){OP=d;
    try{renderOP()}catch(e){$('#p5').innerHTML='<p class="err">표시 오류: '+opT(e.message)+'</p>'}})
  .catch(function(){
    $('#p5').innerHTML='<p class="err">opinion.json이 아직 없습니다.<br>'+
      'Actions에서 market-board 워크플로를 한 번 실행하면 만들어집니다.</p>';
    if($('#t5').className.indexOf('on')>=0)tab(1)})}
loadOP();
