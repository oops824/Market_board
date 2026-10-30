/* 종합 투자의견 (탭5) — scripts/opinion.py 가 하루 두 번(10시·22시) 만드는 opinion.json
   단기(1~4주)는 매번 갱신, 중장기(3~12개월)는 분명한 근거가 있을 때만 바뀜.
   본문의 ==핵심== 표시는 형광 강조로 보여 줌(생성 단계에서 영역별 15% 이내로 제한) */
var OP=null,OP_H='s';
try{OP_H=localStorage.getItem('opH')==='l'?'l':'s'}catch(e){}
var OP_PAL=['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
var OP_STN=['적극 축소','축소','중립','확대','적극 확대'];
var OP_ACT={'분할 매수':'up','비중 확대':'up','일부 차익실현':'dn','비중 축소':'dn','유지':'na','관망':'warn'};
var OP_ROLE={'핵심 보유':'acc','보유':'na','비중 확대':'up','비중 축소':'dn','정리':'dn'};

function opT(t){return esc(t==null?'':t).replace(/==(.+?)==/g,'<mark class="hl">$1</mark>')}
/* 개조식 여러 줄('- '로 시작)은 글머리표 목록으로, 한 줄이면 그대로 */
function opB(t){
  var ls=String(t==null?'':t).split(/\n+/).map(function(x){return x.trim()}).filter(Boolean);
  if(ls.length<2&&!/^[-•]\s/.test(ls[0]||''))return opT(t);
  return '<ul class="bl">'+ls.map(function(x){return '<li>'+opT(x.replace(/^[-•]\s*/,''))+'</li>'}).join('')+'</ul>'}
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
    (ck&&ck.note?'<span>'+opMD(ck.date)+' 점검: '+opB(ck.note)+'</span>':
      lg.change_note?'<span>'+opB(lg.change_note)+'</span>':'')+'</div>'}
function opHero(o){
  var row=function(lab,sub,st){st=st||{};
    return '<div class="rl">'+lab+'<small>'+sub+'</small></div>'+opCell(st.stocks)+opCell(st.crypto)+opCell(st.cash)};
  return '<div class="pick op-hero"><div class="pk-tag">오늘의 종합의견</div>'+
    '<div class="op-hl">'+opT(o.headline)+'</div><div class="op-sm">'+opB(o.summary)+'</div>'+
    '<div class="stg"><div></div><div class="h">주식</div><div class="h">코인</div><div class="h">현금</div>'+
    row('단기','1~4주',o.short.stance)+row('중장기','3~12개월',o.long.stance)+'</div></div>'}

/* 내 코인 포트폴리오: 현재 비중(막대)과 중장기 목표 비중(세로선), 단기 행동·중장기 역할 */
function opPortCoin(o){
  var pf=OP.portfolio;if(!pf||!pf.rows)return '';
  var rows=pf.rows.slice();
  (pf.unknown||[]).forEach(function(x){rows.push({sym:x,w:null,pnl:null})});
  rows.push({sym:'현금',cash:true,w:pf.cash,t:o.long.crypto_cash_pct});
  return opPortCard('내 코인 포트폴리오',pf.asof,rows,(o.short.coins||[]).concat(o.short.holdings||[]),
    (o.long.coins||[]).concat(o.long.holdings||[]),pf.cash_sym||'USDT')}
/* 레버리지 배율: 거래소 설정(x)과 실효 배율(lev, 추가 증거금 반영)이 다르면 함께 */
function opLev(r){var x=r.x||r.lev;return x+'배'+(r.x&&Math.abs(r.x-r.lev)>=0.3?'(실효 '+r.lev.toFixed(1)+'배)':'')}
function opCLev(){var m={};((OP.portfolio||{}).rows||[]).forEach(function(r){if(r.lev)m[r.sym]=1});return m}
function opPortStock(o){
  var st=(OP.portfolio||{}).stocks;if(!st||!st.rows)return '';
  var rows=st.rows.slice();
  if(opNum(st.cash)&&st.cash>0)rows.push({sym:'현금',cash:true,w:st.cash});
  return opPortCard('내 미국 주식 포트폴리오',st.asof,rows,o.short.holdings,o.long.holdings,st.cash_note?'USDT':'USD')}
/* 계좌 카드: 현재 비중(막대)과 중장기 목표 비중(세로선), 단기 행동·중장기 역할 */
function opPortCard(title,asof,rows,shortL,longL,cashSub){
  var sa={},lr={};
  (shortL||[]).forEach(function(c){sa[c.sym]=c});
  (longL||[]).forEach(function(c){lr[c.sym]=c});
  rows.forEach(function(r){if(!r.cash)r.t=(lr[r.sym]||{}).target_pct});
  rows.forEach(function(r){r.cw=r.lev&&opNum(r.exp)?r.exp:r.w});   // 레버리지는 실제 노출 기준으로 비교
  var mx=Math.max.apply(null,rows.map(function(r){return Math.max(r.cw||0,r.t||0)}))||1;
  var h=rows.map(function(r){
    var s=sa[r.sym],l=lr[r.sym],d=opNum(r.cw)&&opNum(r.t)?r.t-r.cw:null;
    var arrow=d==null||Math.abs(d)<2?'':d>0?' <span class="tu">▲</span>':' <span class="td">▼</span>';
    return '<div class="pf-r"><div class="pf-1"><b>'+opT(r.sym)+(r.cash&&cashSub?' <span class="dim">'+cashSub+'</span>':'')+'</b>'+
      (opNum(r.pnl)?'<span class="badge '+(r.pnl>=0?'up':'dn')+'">'+opPct(r.pnl)+'</span>':
        r.cash?'':'<span class="dim">비중 미입력</span>')+(r.note?'<span class="dim">'+opT(r.note)+'</span>':'')+
      '<span class="pf-w">'+(opNum(r.cw)?r.cw.toFixed(1)+'%':'-')+' → '+(opNum(r.t)?r.t+'%':'-')+arrow+'</span></div>'+
      (r.lev?'<div class="tags"><span class="tag warn lv">'+opLev(r)+' 레버리지 롱 · 증거금 '+r.w.toFixed(1)+'% · 실제 노출 '+
        r.exp.toFixed(1)+'%'+(opNum(r.liq)?' · 청산가 '+(r.cur==='USD'?'$':'')+r.liq+(opNum(r.px)?' ('+((r.liq/r.px-1)*100).toFixed(1)+'%)':''):'')+
        '</span></div>':'')+
      '<div class="pf-bar">'+(opNum(r.cw)?'<i style="width:'+(r.cw/mx*100).toFixed(1)+'%"></i>':'')+
      (opNum(r.t)?'<u style="left:calc('+(r.t/mx*100).toFixed(1)+'% - 1px)"></u>':'')+'</div>'+
      (s||l?'<div class="tags">'+(s?'<span class="tag '+(OP_ACT[s.action]||'na')+'">단기 '+opT(s.action)+'</span>':'')+
        (l?'<span class="tag '+(OP_ROLE[l.role]||'na')+'">중장기 '+opT(l.role)+'</span>':'')+opOvChip(r.sym)+'</div>':'')+'</div>'}).join('');
  return '<div class="etf"><div class="eh"><b>'+title+'</b><span class="dim">'+opMD(asof)+
    ' 기준 · 시세 반영</span></div><div class="legend"><span><i style="background:var(--sub)"></i>현재 비중</span>'+
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
      opCf(p.confidence)+'</div><div class="opw">'+opT(p.why)+'</div>'+opEntry(p.entry)+'</li>'}).join('')+'</ul>'}
/* 진입가(정확한 값 또는 좁은 범위) */
function opEntry(e){return e?'<div class="opc ent"><em>진입가</em>'+opT(e)+'</div>':''}
function opList(t,list,cl){
  if(!list||!list.length)return '';
  return (t?'<div class="sec">'+t+'</div>':'')+'<ol class="opn '+cl+'">'+list.map(function(x){
    return '<li>'+opT(x)+'</li>'}).join('')+'</ol>'}
function opCard(t,inner,sub){
  return inner?'<div class="etf"><div class="eh"><b>'+t+'</b>'+(sub?'<span class="dim">'+sub+'</span>':'')+'</div>'+
    inner+'</div>':''}

/* 과대낙폭(역발상) 점검: 점수 칩 + 저가 매수 조건 상자 */
var OP_OV={'항복 구간':'up','과대낙폭':'acc','조정 중':'na','과대낙폭 아님':'na'};
function opOv(sym){return (OP.oversold||{})[sym]}
function opDip(sym,dip){
  var v=opOv(sym);
  if(!dip&&!v)return '';
  return '<div class="opc dip"><em>저가 매수</em>'+opT(dip||'-')+
    (v?'<div class="dsig"><span class="tag '+(OP_OV[v.label]||'na')+'">역발상 점검 '+v.score+' · '+opT(v.label)+'</span>'+
      (v.sig&&v.sig.length?'<span>'+opT(v.sig.join(' · '))+'</span>':'')+'</div>':'')+'</div>'}
function opOvChip(sym){var v=opOv(sym);
  return v&&v.score>=40?'<span class="tag '+(OP_OV[v.label]||'na')+'">'+opT(v.label)+' '+v.score+'</span>':''}

function opCoinList(o,isShort){
  var ps=OP.prev_short,pw={};
  ((OP.portfolio||{}).rows||[]).forEach(function(r){pw[r.sym]=r.w});
  return '<ul class="opl">'+((isShort?o.short:o.long).coins||[]).map(function(c){
    var was=isShort&&ps&&ps.coins?ps.coins[c.sym]:null,k=isShort?c.action:c.role;
    return '<li><div class="opr"><b>'+opT(c.sym)+'</b><span class="tag '+((isShort?OP_ACT:OP_ROLE)[k]||'na')+'">'+opT(k)+'</span>'+
      (was&&was!==c.action?'<span class="chgd">'+opMD(ps.date)+' '+opT(was)+'에서 변경</span>':'')+
      (isShort?opCf(c.confidence):'<span class="cf">목표 '+c.target_pct+'%'+(opNum(pw[c.sym])?' · 현재 '+pw[c.sym].toFixed(1)+'%':'')+'</span>')+
      '</div><div class="opw">'+opT(c.why)+'</div>'+(isShort&&c.condition?'<div class="opc"><em>조건</em>'+opT(c.condition)+'</div>':'')+
      (isShort?opDip(c.sym,c.dip):'')+'</li>'}).join('')+'</ul>'}
/* 관심 종목(보유 외): 그룹별로 단기 행동 + 중장기 역할 */
var OP_Q={lead:['주도','up'],improve:['돌아서는 중','acc'],weaken:['약화','warn'],lag:['소외','dn']};
var OP_QD={lead:'3개월·20일 모두 시장 상회',improve:'3개월은 열세였지만 최근 20일 우위',
  weaken:'3개월 우위였지만 최근 20일 열세',lag:'3개월·20일 모두 시장 하회'};
var OP_V={'비중 확대':'up','관심':'acc','중립':'na','비중 축소':'dn'};
var OP_F={early:['조기 신호','acc'],hot:['과열·추격 주의','warn']};
function opFlag(r){var f=r&&OP_F[r.flag];return f?'<span class="tag '+f[1]+'">'+f[0]+'</span>':''}
function opRot(){var m={};((OP.rotation||{}).items||[]).forEach(function(r){m[r.etf]=r});return m}
function opSgn(v){return (v>=0?'+':'')+v.toFixed(1)+'%p'}
/* 역할이 최근 7일 안에 바뀐 관심 종목 표시 */
function opRoleChg(w){
  if(!w.role_from||!w.role_since||w.role_from===w.role)return '';
  var n=opDays(w.role_since);if(n==null||n>7)return '';
  return '<span class="chgd">'+opMD(w.role_since)+' '+opT(w.role_from)+'→'+opT(w.role)+'</span>'}

/* 섹터 로테이션: SPY 대비 상대강도 4분면 + 오늘의 섹터 판단 */
function opRotation(o){
  var R=OP.rotation;if(!R||!R.items||!R.items.length)return '';
  var view={};(o.sectors||[]).forEach(function(x){view[x.etf]=x});
  var mx=Math.max.apply(null,R.items.map(function(r){return Math.abs(r.rs20)}))||1;
  var h=['lead','improve','weaken','lag'].map(function(q){
    var items=R.items.filter(function(r){return r.q===q});
    if(!items.length)return '';
    return '<div class="rq"><div class="rq-h"><span class="tag '+OP_Q[q][1]+'">'+OP_Q[q][0]+'</span><span class="dim">'+
      OP_QD[q]+'</span></div>'+items.map(function(r){var v=view[r.etf],w=Math.abs(r.rs20)/mx*50,pos=r.rs20>=0;
        return '<div class="rr"><div class="rr-1"><b>'+opT(r.name)+'</b><span class="tk">'+opT(r.etf)+'</span>'+opFlag(r)+
          (v?'<span class="tag '+(OP_V[v.view]||'na')+'">'+opT(v.view)+'</span>':'')+
          '<span class="rr-v">'+(opNum(r.rs10)?'<span class="dim">10일 '+opSgn(r.rs10)+'</span> ':'')+
          '<span class="'+(pos?'tu':'td')+'">20일 '+opSgn(r.rs20)+'</span> <span class="dim">3개월 '+opSgn(r.rs63)+
          '</span></span></div><span class="ctr"><b class="'+(pos?'up':'dn')+'" style="'+(pos?'left:50%':'right:50%')+
          ';width:'+w.toFixed(1)+'%"></b></span>'+(v&&v.why?'<div class="opw">'+opT(v.why)+'</div>':'')+'</div>'}).join('')+'</div>'}).join('');
  return '<div class="etf"><div class="eh"><b>섹터 로테이션</b><span class="dim">SPY 대비 초과수익 · '+opMD(R.asof)+'</span></div>'+
    '<p class="note" style="margin:0 0 4px">20일(확인)과 3개월(추세) 상대강도로 나눴습니다. \'돌아서는 중\'은 그동안 시장에 뒤졌지만 '+
    '최근 20일은 시장을 이기는 섹터로, 다음 주도 섹터 후보입니다. \'조기 신호\'는 20일은 아직 뒤지지만 최근 10일 시장을 이기고 '+
    '상대강도가 오르는 섹터(소량·조건부), \'과열·추격 주의\'는 20일에 시장보다 8%p 이상 올랐는데 힘이 멈춘 섹터(눌림에서만)입니다. '+
    '칩은 오늘의 섹터 판단입니다.</p>'+h+'</div>'}

/* 관심 종목(보유 외): 그룹별 접이식, 섹터 그룹은 상대강도 순. 매수 의견·최근 역할 변경이 있는 그룹은 펼침 */
function opWatch(o,filter){
  var meta=OP.watch_meta||{},groups={},order=[],rot=opRot();
  (o.watch||[]).forEach(function(w){
    var m=meta[w.sym]||{},g=m.group||'기타';
    if(filter&&!filter(g))return;
    if(!groups[g]){groups[g]=[];order.push(g)}
    groups[g].push(w)});
  if(!order.length)return '';
  var etfOf=function(g){var m=meta[groups[g][0].sym]||{};return m.etf||null};
  var rank=function(g){if(g==='하이퍼스케일러')return 1e9;var r=rot[etfOf(g)];return r?r.rs20:-1e9};
  order.sort(function(a,b){return rank(b)-rank(a)});
  return order.map(function(g){
    var ws=groups[g],r=/대장주$/.test(g)?rot[etfOf(g)]:null;   // 섹터 그룹에만 상대강도 칩
    var buys=ws.filter(function(w){return w.action==='분할 매수'||w.action==='비중 확대'}).length;
    var good=ws.filter(function(w){return w.role==='핵심 보유'||w.role==='비중 확대'||w.role==='보유'}).length;
    var chg=ws.some(function(w){return !!opRoleChg(w)});
    return '<details class="ws"'+(buys||chg?' open':'')+'><summary><span class="tag acc">'+opT(g)+'</span>'+
      (r?'<span class="tag '+OP_Q[r.q][1]+'">'+OP_Q[r.q][0]+'</span>'+opFlag(r):'')+
      '<span class="ws-n">'+(buys?'매수 '+buys+' · ':'')+'담을 만함 '+good+'/'+ws.length+'</span></summary><ul class="opl">'+
      ws.map(function(w){var m=meta[w.sym]||{};
        return '<li><div class="opr"><b>'+opT(w.sym)+'</b><span class="tk">'+opT(m.name||'')+'</span>'+opRoleChg(w)+
          '<span class="cf"><span class="tag '+(OP_ACT[w.action]||'na')+'">단기 '+opT(w.action)+'</span> '+
          '<span class="tag '+(OP_ROLE[w.role]||'na')+'">중장기 '+opT(w.role)+'</span></span></div>'+
          '<div class="opw">'+opT(w.why)+'</div>'+opEntry(w.entry)+'</li>'}).join('')+'</ul></details>'}).join('')}

/* 종합 탭은 결론 → 할 일 → 근거 → 큰 그림 순서로 읽히게 배치 */
function opToday(o){var sh=o.short;
  return opCard('오늘의 할 일',opList('바로 실행 · 우선순위 순',sh.actions_now,'')+opList('기다릴 신호',sh.wait_for,'op-q'),
    '근거는 아래에')}
function opWhy(o){var sh=o.short;
  return opCard('단기 시각','<div class="brief">'+opB(sh.view)+'</div>','확신 '+opT(sh.confidence))+
    (o.forward?opCard('앞으로의 시나리오','<div class="brief">'+opB(o.forward)+'</div>','기본·낙관·비관 · 지정학'):'')+
    opCard('단기 리스크',opList('',sh.risks,'op-w'))}
function opLong(o){
  var lg=o.long;
  var log=(OP.long_log||[]).map(function(x){
    return '<li><div class="opr"><b>'+opMD(x.date)+'</b><span class="tag '+(x.status==='변경'?'warn':'na')+'">'+
      opT(x.status)+'</span></div><div class="opw">'+opB(x.note)+'</div></li>'}).join('');
  return opCard('중장기 전략','<div class="brief">'+opB(lg.thesis)+'</div>'+opLongStatus(o),'확신 '+opT(lg.confidence))+
    opAlloc(lg.allocation)+
    opCard('리스크 점검',opList('주요 리스크',lg.risks,'op-w')+opList('이 의견을 바꿀 신호',lg.change_mind,'op-q'))+
    (log?opCard('중장기 의견 변경 이력','<ul class="opl">'+log+'</ul>'):'')}
/* 미국주식 탭 본문 */
function opStock(o,isShort){
  var sh=o.short,lg=o.long,cl=opCLev(),nf=function(l){return (l||[]).filter(function(c){return !cl[c.sym]})};
  return (isShort?opCard('보유 주식 단기 대응',opHold(nf(sh.holdings),true)):
      opCard('보유 주식 중장기',opHold(nf(lg.holdings),false),'주식 계좌 목표 비중'+(lg.holdings_new_pct?' · 신규 편입 '+lg.holdings_new_pct+'%':'')))+
    opCard('관심 종목 의견',opWatch(o,function(g){return g.indexOf('13F')<0}),'하이퍼스케일러 · 17개 섹터 대장주 · 상대강도 순')+
    (isShort?opCard('새로 볼 종목 · 피할 종목',opPicks(sh.stocks_buy,'매수','up')+opPicks(sh.stocks_avoid,'회피','dn')):
      opCard('중장기 테마',opPicks(lg.stocks_overweight,'비중 확대','up')+opPicks(lg.stocks_underweight,'비중 축소','dn')))}
/* 가상자산 탭 본문 */
function opCoin(o,isShort){
  var cl=opCLev(),fl=function(l){return (l||[]).filter(function(c){return cl[c.sym]})};
  var fut=opHold(fl((isShort?o.short:o.long).holdings),isShort);
  return (fut?opCard('코인 선물 포지션',fut,isShort?'손절·축소 조건':'코인 계좌 기준 실제 노출 목표'):'')+
    (isShort?opCard('코인 단기 대응',opCoinList(o,true)):
    opCard('코인 중장기',opCoinList(o,false),'코인 계좌 목표 · 현금 '+opT(o.long.crypto_cash_pct)+'%'))}

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

/* 보유 종목별 판단 (단기: 행동·조건, 중장기: 역할·목표 비중) */
function opHold(list,isShort){
  if(!list||!list.length)return '';
  var pw={};(((OP.portfolio||{}).stocks||{}).rows||[]).concat((OP.portfolio||{}).rows||[]).forEach(function(r){
    pw[r.sym]=r.lev&&opNum(r.exp)?r.exp:r.w});
  return '<ul class="opl">'+list.map(function(c){
    var k=isShort?c.action:c.role;
    return '<li><div class="opr"><b>'+opT(c.sym)+'</b><span class="tag '+((isShort?OP_ACT:OP_ROLE)[k]||'na')+'">'+opT(k)+'</span>'+
      (!isShort?'<span class="cf">목표 '+c.target_pct+'%'+(opNum(pw[c.sym])?' · 현재 '+pw[c.sym].toFixed(1)+'%':'')+'</span>':'')+
      '</div><div class="opw">'+opT(c.why)+'</div>'+(isShort&&c.condition?'<div class="opc"><em>조건</em>'+opT(c.condition)+'</div>':'')+
      (isShort?opDip(c.sym,c.dip):'')+'</li>'}).join('')+'</ul>'}

/* 웹 검색으로 모은 최근 뉴스·전문가 전망: 영역(##)별 접이식, 글머리표·굵게 표시, 출처는 접어 둠 */
function opMd(t){return opT(t).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')}
function opOutlook(){
  if(!OP.outlook)return '';
  var secs=[],cur=null;
  OP.outlook.split('\n').forEach(function(line){
    var m=line.match(/^#{1,4}\s*(.+)$/);
    if(m){cur={t:m[1].replace(/\*\*/g,''),items:[]};secs.push(cur);return}
    if(!line.trim()||/^\*\*기준일/.test(line.trim()))return;
    if(!cur){cur={t:'요약',items:[]};secs.push(cur)}
    var b=line.match(/^(\s*)[-*•]\s+(.*)$/);
    cur.items.push(b?{sub:b[1].length>=2,t:b[2]}:{p:true,t:line.trim()})});
  var body=secs.map(function(x,i){
    var lis=x.items.map(function(it){
      return it.p?'<p class="ol-p">'+opMd(it.t)+'</p>':'<li'+(it.sub?' class="sub"':'')+'>'+opMd(it.t)+'</li>'}).join('');
    return '<details class="ol-s"'+(i===0?' open':'')+'><summary>'+opT(x.t.replace(/^[①-⑩]\s*/,''))+
      '<span class="ol-n">'+(i+1)+'</span></summary><ul class="ol-l">'+lis+'</ul></details>'}).join('');
  var src=(OP.sources||[]).map(function(x){
    return '<li><a href="'+escA(x.url)+'" target="_blank" rel="noopener">'+opT(x.title)+'</a></li>'}).join('');
  return '<div class="etf op-news"><div class="eh"><b>뉴스·전문가 전망</b><span class="dim">'+opMD(OP.generated)+
    ' 웹 검색 · 출처 '+(OP.sources||[]).length+'곳</span></div>'+body+
    (src?'<details class="ko"><summary>출처 보기</summary><ul class="news op-src">'+src+'</ul></details>':'')+'</div>'}

/* FOMC 금리 확률: 회의별 인하·동결·인상 막대 (연방기금금리 선물 기반, CME FedWatch 방식) */
function opFed(){
  var fw=OP.fedwatch;if(!fw||!fw.meetings||!fw.meetings.length)return '';
  var rows=fw.meetings.map(function(m){
    var up=m.hike,dn=m.cut,d=opDays(m.date),big=function(v){return v>=1?' (50bp '+Math.round(v)+'%)':''},seg=function(v,c,l){
      return v>=1?'<i class="'+c+'" style="width:'+v.toFixed(1)+'%">'+(v>=14?l+' '+Math.round(v)+'%':'')+'</i>':''};
    return '<div class="fw-r"><div class="fw-h"><b>'+opMD(m.date)+' FOMC</b><span class="dim">'+(d!=null&&d<=0?(1-d)+'일 후 · ':'')+
      '선물 내재 금리 '+m.pre.toFixed(2)+'% → '+m.post.toFixed(2)+'%</span></div>'+
      '<div class="fw-b">'+seg(dn,'dn','인하')+seg(m.hold,'na','동결')+seg(up,'up','인상')+'</div>'+
      '<div class="fw-l"><span class="td">인하 '+dn.toFixed(1)+'%'+big(m.cut50||0)+'</span><span>동결 '+m.hold.toFixed(1)+'%</span>'+
      '<span class="tu">인상 '+up.toFixed(1)+'%'+big(m.hike50||0)+'</span><span class="dim">지금부터 누적 '+(m.cum_bp>=0?'+':'')+Math.round(m.cum_bp)+'bp</span></div></div>'}).join('');
  return '<div class="etf op-fed"><div class="eh"><b>FOMC 금리 확률</b><span class="dim">'+opMD(fw.asof)+
    ' · 연방기금금리 선물 기반(FedWatch 방식) · '+opT(fw.src)+'</span></div>'+rows+'</div>'}

/* 실적 발표: 최근 결과(EPS·주가 반응)와 다음 일정, 보유 종목 표시 */
function opEarn(){
  var E=OP.earnings;if(!E||!((E.recent||[]).length||(E.upcoming||[]).length))return '';
  var held={},lev={};(E.held||[]).forEach(function(s){held[s]=1});(E.lev||[]).forEach(function(s){lev[s]=1});
  var fl=function(s){return lev[s]?'<span class="tag warn">레버리지 보유</span>':held[s]?'<span class="tag na">보유</span>':''};
  var usd=function(v){return opNum(v)?(v<0?'-$'+(-v).toFixed(2):'$'+v.toFixed(2)):'-'};
  var rx=function(r){r=r||{};
    if(opNum(r.day1))return '<span class="'+(r.day1>=0?'tu':'td')+'">첫날 '+opPct(r.day1)+'</span>'+(r.days>1?' · 지금까지 '+opPct(r.since):'');
    if(opNum(r.ext))return '<span class="'+(r.ext>=0?'tu':'td')+'">'+opT(r.ext_lab)+' '+opPct(r.ext)+'</span>';
    return '주가 반응 수집 전'};
  var li=function(e,body){return '<li><div class="opr"><b>'+opT(e.sym)+'</b>'+fl(e.sym)+
    '<span class="cf">'+opMD(e.date)+' '+opT(e.when)+(e.guess?'(추정)':'')+'</span></div><div class="opw">'+body+'</div></li>'};
  var rec=(E.recent||[]).slice(0,8).map(function(e){
    return li(e,(opNum(e.eps)?'EPS '+usd(e.eps)+' vs 예상 '+usd(e.est):'EPS 예상 '+usd(e.est))+' · '+rx(e.react))}).join('');
  var up=(E.upcoming||[]).slice(0,8).map(function(e){return li(e,'EPS 예상 '+usd(e.est))}).join('');
  return opCard('실적 발표',(rec?'<div class="sec">최근 결과 · 발표 전 종가 대비</div><ul class="opl">'+rec+'</ul>':'')+
    (up?'<div class="sec">다음 2주 일정</div><ul class="opl">'+up+'</ul>':''),opMD(E.asof)+' · 미국 날짜')}

function opSeg(){return '<div class="seg">'+[['s','단기','1~4주'],['l','중장기','3~12개월']].map(function(x){
  return '<button data-h="'+x[0]+'"'+(OP_H===x[0]?' class="on"':'')+'>'+x[1]+'<small>'+x[2]+'</small></button>'}).join('')+'</div>'}
function opBodies(){
  var o=OP.opinion,s=OP_H!=='l',set=function(id,h){var e=$(id);if(e)e.innerHTML=h};
  set('#opb-st',opStock(o,s));set('#opb-cr',opCoin(o,s))}
function renderOP(){
  var o=OP.opinion||{},asof=OP.asof||{},age=(Date.now()-Date.parse(OP.generated||''))/36e5;
  if(!o.short||!o.long){$('#p5').innerHTML='<p class="err">단기·중장기 의견을 준비하고 있습니다.</p>';return}
  var bar='<div class="cbar"><span>'+opT(opWhen(OP.generated))+' 작성 · 매일 10시·22시</span>'+
    (asof['지표']?'<span>지표 '+opT(opWhen(asof['지표']))+' 기준</span>':'')+'</div>';
  var stale=age>30?'<p class="note" style="color:var(--warn)">최근 생성에 실패해 '+Math.floor(age/24)+
    '일 전 의견을 표시하고 있습니다.</p>':'';
  var hd=function(t,sub){return '<div class="hd">'+t+(sub?'<small>'+sub+'</small>':'')+'</div>'};
  $('#p5').innerHTML=bar+stale+opHero(o)+opToday(o)+
    hd('왜 이렇게 하나','단기 시각 · 시나리오 · 리스크 · 데이터')+opWhy(o)+opFed()+opEarn()+opOutlook()+
    hd('큰 그림 · 중장기 전략','3~12개월')+opLong(o)+opTrack(OP.track)+
    '<p class="note">위험 성향 10점 중 7.5~8점(공격적) 기준. 대시보드 데이터에 웹 검색한 최근 뉴스·전문가 전망을 더해 판단하고, '+
    '추세 신호와 함께 과대낙폭(역발상) 점검으로 저가 매수 기회도 따로 봅니다. '+
    '미국주식·가상자산·기관 탭에 영역별 의견이 있습니다. 단기 의견은 매일 10시·22시에 새로 쓰고, 중장기 의견은 매크로 체제 전환처럼 분명한 근거가 있을 때만 '+
    '바꿉니다. 형광 표시는 꼭 봐야 할 핵심(글자 수 15% 이내)입니다. 포트폴리오는 사진 기준 비중·평단·수익률(수량·금액은 저장하지 않음)에 이후 가격 변동을 반영한 추정치입니다. '+
    '데이터 기준: 지표 '+opT(asof['지표']||'-')+', 코인 '+opT(asof['코인']||'-')+', 기관 13F '+opT(asof['기관']||'-')+' 공시.'+
    (OP.model?' 작성 모델 '+opT(OP.model)+'.':'')+'</p>';
  $('#st-op').innerHTML=hd('미국 주식 의견',opWhen(OP.generated)+' · 종합의견 기준')+opPortStock(o)+opRotation(o)+opSeg()+'<div id="opb-st"></div>';
  $('#cr-op').innerHTML=hd('가상자산 의견',opWhen(OP.generated)+' · 종합의견 기준')+opPortCoin(o)+opSeg()+'<div id="opb-cr"></div>';
  var tw=opWatch(o,function(g){return g.indexOf('13F')>=0});
  $('#tf-op').innerHTML=tw?'<div class="etf"><div class="eh"><b>기관이 함께 사고판 종목, 내 의견</b><span class="dim">13F 공동 매수·정리</span></div>'+
    tw+'</div>':'';
  opBodies();
  [].forEach.call(document.querySelectorAll('.seg button'),function(b){b.onclick=function(){
    OP_H=this.getAttribute('data-h');try{localStorage.setItem('opH',OP_H)}catch(e){}
    [].forEach.call(document.querySelectorAll('.seg button'),function(x){
      x.className=x.getAttribute('data-h')===OP_H?'on':''});
    opBodies()}})}

function loadOP(){
  fetch('opinion.json?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(function(d){OP=d;
    try{renderOP()}catch(e){$('#p5').innerHTML='<p class="err">표시 오류: '+opT(e.message)+'</p>'}})
  .catch(function(){
    $('#p5').innerHTML='<p class="err">opinion.json이 아직 없습니다.<br>'+
      'Actions에서 market-board 워크플로를 한 번 실행하면 만들어집니다.</p>';
    if($('#t5').className.indexOf('on')>=0)tab(1)})}
loadOP();
