/* 관심 코인 종합 대시보드 (탭3) */
var CR=null;
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

function newsList(arr){
  var x='<ul class="news">';
  for(var j=0;j<arr.length;j++){var n=arr[j];
    if(!/^https?:\/\//.test(n.url))continue;
    x+='<li><a href="'+escA(n.url)+'" target="_blank" rel="noopener noreferrer"'+
      (n.orig?' title="'+escA(n.orig)+'"':'')+'>'+escA(n.title)+'</a><div class="s">'+
      escA(n.src)+(n.ts?' · '+escA(n.ts):'')+(n.lang==='en'?(n.orig?' · 영문 번역':' · EN'):'')+
      '</div></li>'}
  return x+'</ul>'}

function pickCard(p,past){
  if(!p)return '';
  var ch=nz(p.now)&&nz(p.price)?(p.now/p.price-1)*100:null,x='';
  x+='<div class="pk-h"><div><span class="pk-tag">오늘의 주목 코인 · '+escA(p.date.slice(5))+
    '</span><div class="pk-n"><b>'+escA(p.sym)+'</b> '+escA(p.name)+
    ' <span class="cn">#'+escA(p.rank)+'</span></div>'+
    (p.headline?'<div class="pk-hl">'+escA(p.headline)+'</div>':'')+'</div>'+
    '<div class="cp">'+fp(nz(p.now)?p.now:p.price)+(nz(p.ch24)?' '+bd(p.ch24):'')+'</div></div>';
  x+='<div class="grid">'+kv('7일 (소개 시점)',bd(p.ch7))+kv('30일 (소개 시점)',bd(p.ch30))+
    kv('시가총액',fbig(p.mcap))+kv('소개 이후',nz(ch)?bd(ch):'-',fp(p.price)+' → '+fp(p.now))+'</div>';
  if(p.cats&&p.cats.length)x+='<div class="cats">'+p.cats.map(function(c){
    return '<span>'+escA(c)+'</span>'}).join('')+'</div>';
  if(p.intro)x+='<div class="sec">어떤 코인인가</div><div class="brief">'+escA(p.intro)+'</div>';
  if(p.institutions)x+='<div class="sec">월가·기관 관심 근거</div><div class="brief">'+
    escA(p.institutions)+'</div>';
  if(p.evidence&&p.evidence.length)x+='<div class="sec">근거 기사</div>'+newsList(p.evidence);
  if(p.risks)x+='<div class="sec">유의할 점</div><div class="brief">'+escA(p.risks)+'</div>';
  if(past&&past.length){
    var t='<table class="mini"><tr><td>소개일</td><td>코인</td><td>소개 이후</td></tr>';
    for(var i=0;i<past.length&&i<10;i++){var q=past[i];
      t+='<tr><td>'+escA(q.date.slice(5))+'</td><td>'+escA(q.sym)+'</td><td>'+
        (nz(q.since)?bd(q.since):'-')+'</td></tr>'}
    x+='<div class="sec">지난 소개</div>'+t+'</table>'}
  x+='<p class="note">시총 상위 250위 중 모멘텀 상위 후보에서, 최근 30일 기사로 ETF·자산운용사·은행 등 '+
    '기관 관여가 확인된 코인을 매일 1개 선정합니다. 투자 권유가 아닙니다.</p>';
  return '<div class="pick">'+x+'</div>'}

function coinCard(c){
  var m=c.market||{},hl=c.hl||{},ok=c.okx||{},op=c.options,px=m.price,x='';
  // 헤더
  var sum='<summary><div class="ch"><b>'+escA(c.sym)+'</b> <span class="cn">'+
    escA(c.name)+(m.rank?' · #'+m.rank:'')+'</span></div><div class="cp">'+fp(px)+
    ' '+bd(m.ch24)+'</div></summary>';
  // 가격
  x+=sparkline(m.spark,(m.ch7||0)>=0);
  x+='<div class="grid">'+kv('7일',bd(m.ch7))+kv('30일',bd(m.ch30))+
    kv('원화',fkrw(m.krw))+kv('시가총액',fbig(m.mcap))+kv('24h 거래량',fbig(m.vol))+
    kv('ATH 대비',fpc(m.athPct,1),fp(m.ath))+'</div>';
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
  x+='<div class="sec">최신 뉴스</div>'+
    (c.news&&c.news.length?newsList(c.news):'<p class="note">최근 3일 뉴스 없음</p>');
  return '<details class="coin">'+sum+'<div class="body">'+x+'</div></details>'}

function renderCrypto(){
  var i,up=0,dn=0,sum=0,n=0,fs=0,fn=0;
  for(i=0;i<CR.coins.length;i++){var m=CR.coins[i].market||{},hl=CR.coins[i].hl||{};
    if(nz(m.ch24)){sum+=m.ch24;n++;if(m.ch24>=0)up++;else dn++}
    if(nz(hl.fundingApr)){fs+=hl.fundingApr;fn++}}
  var top='<div class="kpi ckpi">'+
    '<div><div class="k">공포·탐욕 지수</div><div class="v">'+(CR.fng?CR.fng.value:'-')+
    '</div><div class="c">'+(CR.fng?escA(FNG_KO[CR.fng.label]||CR.fng.label)+(nz(CR.fng.week)?' · 1주전 '+
      CR.fng.week:''):'')+'</div></div>'+
    '<div><div class="k">8종 평균 24시간</div><div class="v">'+(n?fpc(sum/n):'-')+
    '</div><div class="c">상승 '+up+' · 하락 '+dn+'</div></div>'+
    '<div><div class="k">평균 펀딩비 (연환산)</div><div class="v">'+(fn?fpc(fs/fn,1):'-')+
    '</div><div class="c">하이퍼리퀴드 기준</div></div>'+
    '<div><div class="k">비트코인</div><div class="v">'+fp((CR.coins[0].market||{}).price)+
    '</div><div class="c">'+bd((CR.coins[0].market||{}).ch24)+'</div></div></div>';
  var ov=CR.overall?'<div class="sum"><b>관심 코인 종합</b>'+escA(CR.overall)+'</div>':'';
  var cards='';
  for(i=0;i<CR.coins.length;i++)cards+=coinCard(CR.coins[i]);
  var err=CR.errors&&CR.errors.length?'<p class="note">일부 수집 실패 '+CR.errors.length+
    '건: '+escA(CR.errors.slice(0,4).join(' / '))+'</p>':'';
  $('#p3').innerHTML='<div class="cbar"><span id="cupd">'+escA(CR.updated||'')+
    (CR.live?' · 시세 '+CR.live+' 갱신':'')+'</span><button id="clive">시세 새로고침</button></div>'+
    top+pickCard(CR.pick,CR.pastPicks)+ov+cards+err;
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
