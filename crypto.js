/* 보유 코인 종합 대시보드 (탭3) */
var CR=null,HOLD_KEY='mb_holdings_v1';
var FNG_KO={'Extreme Fear':'극단적 공포','Fear':'공포','Neutral':'중립','Greed':'탐욕',
  'Extreme Greed':'극단적 탐욕'};
function escA(t){return String(t==null?'':t).replace(/[<>&"']/g,function(c){
  return {'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]})}
function nz(v){return typeof v==='number'&&isFinite(v)}
function fp(v){if(!nz(v))return '-';var a=Math.abs(v);
  return '$'+(a>=1000?v.toLocaleString('en-US',{maximumFractionDigits:0}):
    a>=1?v.toFixed(2):a>=0.01?v.toFixed(4):v.toPrecision(3))}
function fbig(v){if(!nz(v))return '-';var a=Math.abs(v);
  return a>=1e12?'$'+(v/1e12).toFixed(2)+'T':a>=1e9?'$'+(v/1e9).toFixed(2)+'B':
    a>=1e6?'$'+(v/1e6).toFixed(1)+'M':'$'+v.toLocaleString('en-US',{maximumFractionDigits:0})}
function fkrw(v){return nz(v)?'₩'+Math.round(v).toLocaleString('ko-KR'):'-'}
function fpc(v,d){return nz(v)?(v>=0?'+':'')+v.toFixed(d==null?2:d)+'%':'-'}
function bd(v,txt){return '<span class="badge '+(nz(v)?(v>=0?'up':'dn'):'na')+'">'+
  (txt||fpc(v))+'</span>'}

function loadHold(){try{return JSON.parse(localStorage.getItem(HOLD_KEY))||{}}catch(e){return {}}}
function saveHold(h){try{localStorage.setItem(HOLD_KEY,JSON.stringify(h))}catch(e){}}

/* 펀딩비 해석: 8시간 환산 % 기준 */
function fundTag(p8){
  if(!nz(p8))return '';
  if(p8>=0.05)return '<span class="badge up">롱 과열</span>';
  if(p8>=0.02)return '<span class="badge up">롱 우위</span>';
  if(p8<=-0.02)return '<span class="badge dn">숏 과열</span>';
  if(p8<0)return '<span class="badge dn">숏 우위</span>';
  return '<span class="badge na">중립</span>'}

function sparkline(arr,up){
  if(!arr||arr.length<2)return '';
  var W=300,H=46,lo=Math.min.apply(null,arr),hi=Math.max.apply(null,arr),sp=(hi-lo)||1,d='';
  for(var i=0;i<arr.length;i++){
    d+=(i?'L':'M')+(i*W/(arr.length-1)).toFixed(1)+' '+(H-3-(arr[i]-lo)/sp*(H-6)).toFixed(1)}
  return '<svg class="spk" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'+
    '<path d="'+d+'" fill="none" stroke="'+(up?'var(--up)':'var(--dn)')+
    '" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>'}

function kv(k,v,s){return '<div class="kv"><div class="k">'+k+'</div><div class="v">'+v+
  '</div>'+(s?'<div class="s">'+s+'</div>':'')+'</div>'}

function coinCard(c,h,total){
  var m=c.market||{},hl=c.hl||{},ok=c.okx||{},op=c.options,px=m.price,x='';
  var q=h&&nz(h.q)?h.q:0,val=q*(px||0),cost=h&&nz(h.avg)?h.avg*q:null;
  var pnl=cost?val-cost:null,pnlP=cost?(val/cost-1)*100:null;
  // 헤더
  var sum='<summary><div class="ch"><b>'+escA(c.sym)+'</b> <span class="cn">'+
    escA(c.name)+(m.rank?' · #'+m.rank:'')+'</span></div><div class="cp">'+fp(px)+
    ' '+bd(m.ch24)+'</div></summary>';
  // 가격
  x+=sparkline(m.spark,(m.ch7||0)>=0);
  x+='<div class="grid">'+kv('7일',bd(m.ch7))+kv('30일',bd(m.ch30))+
    kv('원화',fkrw(m.krw))+kv('시가총액',fbig(m.mcap))+kv('24h 거래량',fbig(m.vol))+
    kv('ATH 대비',fpc(m.athPct,1),fp(m.ath))+'</div>';
  // 보유
  if(q>0){
    x+='<div class="sec">내 보유</div><div class="grid">'+
      kv('수량',q.toLocaleString('en-US',{maximumFractionDigits:6}))+
      kv('평가액',fbig(val),total?(val/total*100).toFixed(1)+'% 비중':'')+
      kv('손익',pnl==null?'<span class="dim">평단 미입력</span>':bd(pnl,
        (pnl>=0?'+':'-')+fbig(Math.abs(pnl))),pnl==null?'':fpc(pnlP))+
      '</div>'}
  // 선물
  var hl8=nz(hl.funding)?hl.funding*800:null,ok8=nz(ok.funding)?ok.funding*100:null;
  x+='<div class="sec">선물 · 파생</div><div class="grid">'+
    kv('HL 펀딩 (8h환산)',nz(hl8)?fpc(hl8,4)+' '+fundTag(hl8):'-',
       nz(hl.fundingApr)?'연 '+fpc(hl.fundingApr,1):'')+
    kv('OKX 펀딩 (8h)',nz(ok8)?fpc(ok8,4)+' '+fundTag(ok8):'-',
       nz(ok.nextFunding)?'다음 예상 '+fpc(ok.nextFunding*100,4):'')+
    kv('미결제약정',fbig((hl.oiUsd||0)+(ok.oiUsd||0)||null),
       'HL '+fbig(hl.oiUsd)+' · OKX '+fbig(ok.oiUsd))+
    kv('롱/숏 계정비',nz(ok.lsRatio)?ok.lsRatio.toFixed(2):'-',
       nz(ok.lsRatio)?(ok.lsRatio>=1?'롱 계정 多':'숏 계정 多')+' · OKX':'')+
    kv('마크-오라클 괴리',fpc(hl.basis,3),'하이퍼리퀴드')+
    kv('HL 24h 거래대금',fbig(hl.vol24))+'</div>';
  // 옵션 / 맥스페인
  x+='<div class="sec">옵션 · 맥스페인</div>';
  if(op){
    var ref=px||op.underlying;
    function mpRow(t,e){if(!e)return '';var dist=ref?(e.maxPain/ref-1)*100:null;
      return kv(t+' ('+e.exp.slice(5)+', D-'+Math.max(0,Math.round(e.days))+')',
        fp(e.maxPain),'현재가 대비 '+fpc(dist,1)+(nz(e.pcr)?' · P/C '+e.pcr:''))}
    x+='<div class="grid">'+mpRow('최근월',op.nearest)+
      (op.major.exp!==op.nearest.exp?mpRow('주요 만기',op.major):'')+
      kv('전체 풋/콜 OI',nz(op.pcr)?op.pcr.toFixed(2):'-',
        nz(op.pcr)?(op.pcr>1?'풋 우세(헤지 수요)':'콜 우세'):'')+'</div>';
    if(op.expiries&&op.expiries.length>2){
      var t='<table class="mini"><tr><td>만기</td><td>맥스페인</td><td>P/C</td></tr>';
      for(var i=0;i<op.expiries.length;i++){var e=op.expiries[i];
        t+='<tr><td>'+e.exp.slice(5)+'</td><td>'+fp(e.maxPain)+'</td><td>'+
          (nz(e.pcr)?e.pcr:'-')+'</td></tr>'}
      x+=t+'</table>'}
    x+='<p class="note">Deribit 옵션 미결제약정 기준</p>'}
  else x+='<p class="note">상장된 옵션 시장(Deribit)이 없어 맥스페인 산출 불가</p>';
  // AI 브리핑
  if(c.brief)x+='<div class="sec">AI 브리핑</div><div class="brief">'+escA(c.brief)+'</div>';
  // 뉴스
  x+='<div class="sec">최신 뉴스</div>';
  if(c.news&&c.news.length){
    x+='<ul class="news">';
    for(var j=0;j<c.news.length;j++){var n=c.news[j];
      if(!/^https?:\/\//.test(n.url))continue;
      x+='<li><a href="'+escA(n.url)+'" target="_blank" rel="noopener noreferrer">'+
        escA(n.title)+'</a><div class="s">'+escA(n.src)+' · '+escA(n.ts)+
        (n.lang==='en'?' · EN':'')+'</div></li>'}
    x+='</ul>'}
  else x+='<p class="note">최근 3일 뉴스 없음</p>';
  return '<details class="coin">'+sum+'<div class="body">'+x+'</div></details>'}

function holdEditor(h){
  var r='';
  for(var i=0;i<CR.coins.length;i++){var c=CR.coins[i],v=h[c.sym]||{};
    r+='<tr><td class="n">'+escA(c.sym)+'</td><td><input inputmode="decimal" data-s="'+
      escA(c.sym)+'" data-k="q" value="'+(nz(v.q)?v.q:'')+'" placeholder="수량"></td>'+
      '<td><input inputmode="decimal" data-s="'+escA(c.sym)+'" data-k="avg" value="'+
      (nz(v.avg)?v.avg:'')+'" placeholder="평단 $"></td></tr>'}
  return '<details id="hed"><summary>보유 수량 · 평단 입력</summary><div class="body">'+
    '<p class="note">이 기기 브라우저에만 저장됩니다 (서버·깃허브로 전송되지 않음)</p>'+
    '<table class="hold">'+r+'</table></div></details>'}

function renderCrypto(){
  var h=loadHold(),total=0,cost=0,chg=0,i;
  for(i=0;i<CR.coins.length;i++){var c=CR.coins[i],m=c.market||{},v=h[c.sym];
    if(!v||!nz(v.q)||!nz(m.price))continue;
    var val=v.q*m.price;total+=val;
    if(nz(v.avg))cost+=v.q*v.avg;
    if(nz(m.ch24))chg+=val-val/(1+m.ch24/100)}
  var krwRate=null,b=CR.coins[0]&&CR.coins[0].market;
  if(b&&nz(b.krw)&&nz(b.price))krwRate=b.krw/b.price;
  var top='<div class="kpi ckpi">'+
    '<div><div class="k">내 평가액</div><div class="v">'+(total?fbig(total):'-')+
    '</div><div class="c">'+(krwRate&&total?fkrw(total*krwRate):'수량을 입력하세요')+'</div></div>'+
    '<div><div class="k">24시간 손익</div><div class="v">'+(total?(chg>=0?'+':'-')+
      fbig(Math.abs(chg)):'-')+'</div><div class="c">'+(total?bd(chg/(total-chg)*100):'')+
    '</div></div>'+
    '<div><div class="k">누적 손익</div><div class="v">'+(cost?(total>=cost?'+':'-')+
      fbig(Math.abs(total-cost)):'-')+'</div><div class="c">'+(cost?bd((total/cost-1)*100):
      '<span class="dim">평단 미입력</span>')+'</div></div>'+
    '<div><div class="k">공포·탐욕 지수</div><div class="v">'+(CR.fng?CR.fng.value:'-')+
    '</div><div class="c">'+(CR.fng?escA(FNG_KO[CR.fng.label]||CR.fng.label)+(nz(CR.fng.week)?' · 1주전 '+
      CR.fng.week:''):'')+'</div></div></div>';
  var alloc='';
  if(total){alloc='<div class="alloc">';
    var cols=['#f7931a','#7c9cff','#14f195','#50d2c1','#2a5ada','#b8a1ff','#4da2ff','#ff6fb5'];
    for(i=0;i<CR.coins.length;i++){var cc=CR.coins[i],hv=h[cc.sym],mm=cc.market||{};
      if(!hv||!nz(hv.q)||!nz(mm.price))continue;
      var w=hv.q*mm.price/total*100;
      alloc+='<span style="width:'+w.toFixed(2)+'%;background:'+cols[i%cols.length]+
        '" title="'+escA(cc.sym)+' '+w.toFixed(1)+'%"></span>'}
    alloc+='</div><div class="leg">';
    for(i=0;i<CR.coins.length;i++){var c2=CR.coins[i],h2=h[c2.sym],m2=c2.market||{};
      if(!h2||!nz(h2.q)||!nz(m2.price))continue;
      alloc+='<span><i style="background:'+cols[i%cols.length]+'"></i>'+escA(c2.sym)+' '+
        (h2.q*m2.price/total*100).toFixed(1)+'%</span>'}
    alloc+='</div>'}
  var ov=CR.overall?'<div class="sum"><b>보유 코인 종합</b>'+escA(CR.overall)+'</div>':'';
  var cards='';
  for(i=0;i<CR.coins.length;i++)cards+=coinCard(CR.coins[i],h[CR.coins[i].sym],total);
  var err=CR.errors&&CR.errors.length?'<p class="note">일부 수집 실패 '+CR.errors.length+
    '건: '+escA(CR.errors.slice(0,4).join(' / '))+'</p>':'';
  $('#p3').innerHTML='<div class="cbar"><span id="cupd">'+escA(CR.updated||'')+
    (CR.live?' · 시세 '+CR.live+' 갱신':'')+'</span><button id="clive">시세 새로고침</button></div>'+
    top+alloc+ov+holdEditor(h)+cards+err;
  var ins=document.querySelectorAll('#hed input');
  for(i=0;i<ins.length;i++)ins[i].onchange=function(){
    var hh=loadHold(),s=this.getAttribute('data-s'),k=this.getAttribute('data-k'),
      v=parseFloat(String(this.value).replace(/,/g,''));
    hh[s]=hh[s]||{};
    if(isFinite(v))hh[s][k]=v;else delete hh[s][k];
    saveHold(hh);renderCrypto();
    var d=document.getElementById('hed');if(d)d.open=true};
  $('#clive').onclick=liveRefresh}

/* 브라우저에서 바로 가격·펀딩비만 갱신 (뉴스·맥스페인은 정기 수집값 유지) */
function liveRefresh(){
  var btn=$('#clive');if(btn){btn.disabled=true;btn.textContent='불러오는 중...'}
  var ids=CR.coins.map(function(c){return c.cg}).join(',');
  var p1=fetch('https://api.coingecko.com/api/v3/simple/price?ids='+ids+
    '&vs_currencies=usd,krw&include_24hr_change=true').then(function(r){return r.json()})
    .then(function(j){CR.coins.forEach(function(c){var q=j[c.cg];if(!q)return;
      c.market=c.market||{};c.market.price=q.usd;c.market.krw=q.krw;
      if(nz(q.usd_24h_change))c.market.ch24=q.usd_24h_change})});
  var p2=fetch('https://api.hyperliquid.xyz/info',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'metaAndAssetCtxs'})})
    .then(function(r){return r.json()}).then(function(j){
      var map={};j[0].universe.forEach(function(u,i){map[u.name]=j[1][i]});
      CR.coins.forEach(function(c){var x=map[c.sym];if(!x)return;
        var px=+x.markPx,f=+x.funding,o=+x.oraclePx;
        c.hl=c.hl||{};c.hl.funding=f;c.hl.fundingApr=f*24*365*100;c.hl.mark=px;
        c.hl.oiUsd=(+x.openInterest)*px;c.hl.vol24=+x.dayNtlVlm;
        if(o)c.hl.basis=(px/o-1)*100})});
  Promise.all([p1.catch(function(){return 'x'}),p2.catch(function(){return 'x'})])
  .then(function(r){
    var ok=r.filter(function(v){return v!=='x'}).length;
    if(ok){var t=new Date();
      CR.live=('0'+t.getHours()).slice(-2)+':'+('0'+t.getMinutes()).slice(-2)}
    var open=[].map.call(document.querySelectorAll('details.coin'),function(d){return d.open});
    renderCrypto();
    [].forEach.call(document.querySelectorAll('details.coin'),function(d,i){d.open=!!open[i]});
    if(!ok){var b=$('#clive');if(b)b.textContent='실패 · 다시 시도'}})}

function loadCrypto(){
  fetch('crypto.json?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(function(d){CR=d;
    try{renderCrypto()}catch(e){$('#p3').innerHTML='<p class="err">표시 오류: '+escA(e.message)+'</p>'}})
  .catch(function(){$('#p3').innerHTML='<p class="err">crypto.json이 아직 없습니다.<br>'+
    'Actions에서 crypto-board 워크플로를 한 번 실행해 주세요.</p>'})}
loadCrypto();
