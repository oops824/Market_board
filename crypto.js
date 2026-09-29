/* 관심 코인 종합 대시보드 (탭3) */
var CR=null,MKT=null;  // MKT: data.json 중 코인 탭으로 옮긴 섹션(일 1회 갱신)
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

/* ---------- 가격 차트: 기간 선택, 최고·최저 표시, 터치 시 가격 ---------- */
var CH_P={},CH_D={};
function chSeries(c,p){
  var m=c.market||{};
  if(p==='7'){
    if(!m.spark||m.spark.length<2)return null;
    var end=m.sparkEnd||Date.now(),st=(m.sparkStepH||2)*3600e3,n=m.spark.length;
    return {ts:m.spark.map(function(_,i){return end-(n-1-i)*st}),v:m.spark.slice(),h:true,
      label:'최근 7일 · '+(m.sparkStepH||2)+'시간 간격'}}
  var d=c.daily;if(!d||!d.c||d.c.length<2)return null;
  var k=Math.min(+p,d.c.length);
  return {ts:d.t.slice(-k),v:d.c.slice(-k),h:false,
    label:'최근 '+k+'일 · 일 단위'}}
function fdt(t,h){var d=new Date(t),s=(d.getMonth()+1)+'/'+d.getDate();
  return h?s+' '+('0'+d.getHours()).slice(-2)+'시':s}
function priceChart(c){
  var p=CH_P[c.sym]||'7',s=chSeries(c,p),id='pc-'+c.sym,i;
  var btn='<div class="pbar">';
  ['7','30','90'].forEach(function(q){var ok=!!chSeries(c,q);
    btn+='<button class="pb'+(q===p?' on':'')+'" data-sym="'+escA(c.sym)+'" data-p="'+q+'"'+
      (ok?'':' disabled')+'>'+q+'일</button>'});
  btn+='</div>';
  if(!s)return '<div class="pcw" id="w'+id+'">'+btn+'<p class="note">차트 데이터 없음</p></div>';
  var v=s.v,n=v.length,lo=Math.min.apply(null,v),hi=Math.max.apply(null,v),
    li=v.indexOf(lo),hx=v.indexOf(hi),W=340,H=184,T=26,B=40,L=6,R=6,
    pad=(hi-lo)*0.06||hi*0.01,mn=lo-pad,mx=hi+pad;
  function X(k){return L+k*(W-L-R)/(n-1)}
  function Y(y){return T+(mx-y)/(mx-mn)*(H-T-B)}
  var up=v[n-1]>=v[0],col=up?'var(--up)':'var(--dn)',d='';
  for(i=0;i<n;i++)d+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(v[i]).toFixed(1);
  var area=d+'L'+X(n-1).toFixed(1)+' '+(H-B)+'L'+X(0).toFixed(1)+' '+(H-B)+'Z';
  function lab(k,val,txt,above,cl){
    var x=X(k),anc=x<70?'start':x>W-70?'end':'middle',y=above?Y(val)-9:Y(val)+17;
    return '<circle class="mk" cx="'+x.toFixed(1)+'" cy="'+Y(val).toFixed(1)+'" r="4" fill="'+cl+
      '" stroke="var(--card)" stroke-width="2"/><text x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+
      '" text-anchor="'+anc+'" class="pl" fill="'+cl+'">'+txt+'</text>'}
  CH_D[id]={ts:s.ts,v:v,h:s.h,X:X,Y:Y,W:W,H:H,T:T,B:B};
  var svg='<svg class="pc" id="'+id+'" viewBox="0 0 '+W+' '+H+'">'+
    '<defs><linearGradient id="g'+id+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="'+col+
    '" stop-opacity=".22"/><stop offset="1" stop-color="'+col+'" stop-opacity="0"/></linearGradient></defs>'+
    '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+(H-20)+'" y2="'+(H-20)+'" stroke="var(--line)"/>'+
    '<path d="'+area+'" fill="url(#g'+id+')"/>'+
    '<path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="2" stroke-linejoin="round"/>'+
    lab(hx,hi,'최고 '+fp(hi),true,'var(--up)')+lab(li,lo,'최저 '+fp(lo),false,'var(--dn)')+
    '<text x="'+L+'" y="'+(H-5)+'" class="pa">'+fdt(s.ts[0],s.h)+'</text>'+
    '<text x="'+(W/2)+'" y="'+(H-5)+'" class="pa" text-anchor="middle">'+fdt(s.ts[Math.floor((n-1)/2)],s.h)+'</text>'+
    '<text x="'+(W-R)+'" y="'+(H-5)+'" class="pa" text-anchor="end">'+fdt(s.ts[n-1],s.h)+'</text>'+
    '<g class="xh" style="display:none"><line y1="'+T+'" y2="'+(H-B)+'" stroke="var(--sub)" stroke-dasharray="3 3"/>'+
    '<circle r="4.5" fill="'+col+'" stroke="var(--txt)" stroke-width="1.5"/>'+
    '<rect rx="6" height="22" fill="var(--card2)" stroke="var(--line2)"/><text class="xt" fill="var(--txt)"></text></g>'+
    '<rect class="hit" x="0" y="0" width="'+W+'" height="'+H+'" fill="transparent"/></svg>';
  var ch=(v[n-1]/v[0]-1)*100;
  return '<div class="pcw" id="w'+id+'"><div class="phd"><span>'+escA(s.label)+'</span>'+btn+'</div>'+svg+
    '<div class="pst"><div><span>최고</span><b class="tu">'+fp(hi)+'</b><i>'+fdt(s.ts[hx],s.h)+'</i></div>'+
    '<div><span>최저</span><b class="td">'+fp(lo)+'</b><i>'+fdt(s.ts[li],s.h)+'</i></div>'+
    '<div><span>기간 등락</span><b class="'+(ch>=0?'tu':'td')+'">'+fpc(ch)+'</b><i>시작 '+fp(v[0])+'</i></div></div></div>'}
function chMove(e){
  var svg=e.target.closest&&e.target.closest('svg.pc');if(!svg)return;
  var o=CH_D[svg.id];if(!o)return;
  var r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*o.W,n=o.v.length;
  var k=Math.max(0,Math.min(n-1,Math.round((x-o.X(0))/(o.X(n-1)-o.X(0))*(n-1))));
  var g=svg.querySelector('.xh'),px=o.X(k),py=o.Y(o.v[k]);g.style.display='';svg.classList.add('hov');
  var ln=g.querySelector('line');ln.setAttribute('x1',px);ln.setAttribute('x2',px);
  var cc=g.querySelector('circle');cc.setAttribute('cx',px);cc.setAttribute('cy',py);
  var t=g.querySelector('text'),rc=g.querySelector('rect');
  t.textContent=fdt(o.ts[k],o.h)+'  '+(o.fmt||fp)(o.v[k]);
  var tw=t.textContent.length*6.4+14,tx=Math.max(2,Math.min(o.W-tw-2,px-tw/2));
  rc.setAttribute('x',tx);rc.setAttribute('y',2);rc.setAttribute('width',tw);
  t.setAttribute('x',tx+7);t.setAttribute('y',17)}
document.addEventListener('pointermove',chMove);
document.addEventListener('pointerdown',chMove);
document.addEventListener('pointerout',function(e){
  var svg=e.target.closest&&e.target.closest('svg.pc');
  if(svg&&e.pointerType==='mouse'){var g=svg.querySelector('.xh');if(g)g.style.display='none';svg.classList.remove('hov')}});
document.addEventListener('click',function(e){
  // 코인 차트 기간 버튼만 (다른 탭의 .pb 버튼은 무시)
  var b=e.target.closest&&e.target.closest('button.pb[data-p][data-sym]');if(!b||!CR)return;
  var c=CR.coins.filter(function(x){return x.sym===b.getAttribute('data-sym')})[0];if(!c)return;
  e.preventDefault();CH_P[c.sym]=b.getAttribute('data-p');
  var w=document.getElementById('wpc-'+c.sym);if(w)w.outerHTML=priceChart(c)});

function kv(k,v,s){return '<div class="kv"><div class="k">'+k+'</div><div class="v">'+v+
  '</div>'+(s?'<div class="s">'+s+'</div>':'')+'</div>'}

/* 영문 기사: 한글 번역 요약(펼치기) + 구글 번역 전문 링크. 기관 탭에서도 사용 */
function koLink(n){
  return n.real&&/^https?:\/\//.test(n.real)?'<a class="kotr" href="https://translate.google.com/translate?sl=auto&tl=ko&hl=ko&u='+
    encodeURIComponent(n.real)+'" target="_blank" rel="noopener noreferrer">전문 번역 ↗</a>':''}
function koBlock(n){
  if(n.lang!=='en')return '';
  var tr=koLink(n);
  if(n.ko&&n.ko.sum){
    var q=(n.ko.quotes||[]).map(function(x){return '<blockquote>'+escA(x)+'</blockquote>'}).join('');
    return '<details class="ko"><summary>한글로 읽기</summary><div class="kob">'+escA(n.ko.sum)+q+
      (tr?'<div class="kol">'+tr+'</div>':'')+'</div></details>'}
  return tr?'<div class="kol">'+tr+'</div>':''}
function newsHref(n){return /^https?:\/\//.test(n.real||'')?n.real:n.url}

function newsList(arr){
  var x='<ul class="news">';
  for(var j=0;j<arr.length;j++){var n=arr[j];
    if(!/^https?:\/\//.test(n.url))continue;
    x+='<li><a href="'+escA(newsHref(n))+'" target="_blank" rel="noopener noreferrer"'+
      (n.orig?' title="'+escA(n.orig)+'"':'')+'>'+escA(n.title)+'</a><div class="s">'+
      escA(n.src)+(n.ts?' · '+escA(n.ts):'')+(n.lang==='en'?(n.orig?' · 영문 번역':' · EN'):'')+
      '</div>'+koBlock(n)+'</li>'}
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
  x+='<p class="note">시총 상위 250위 중 모멘텀 상위 후보에서, 최근 30일 기사 2건 이상으로 ETF·자산운용사·은행 등 '+
    '기관 관여가 확인된 코인을 매일 1개 선정합니다(해당 코인이 없는 날은 건너뜀). 투자 권유가 아닙니다.</p>';
  return '<div class="pick">'+x+'</div>'}

/* ---------- 현물 ETF 자금 흐름 (백만 달러) ---------- */
function fM(v){if(!nz(v))return '-';var a=Math.abs(v),sg=v>0?'+':v<0?'-':'';
  return sg+(a>=1000?'$'+(a/1000).toFixed(2)+'B':'$'+a.toFixed(1)+'M')}
function mdS(d){var m=String(d).match(/^\d{4}-(\d{2})-(\d{2})/);return m?(+m[1])+'/'+(+m[2]):d}
function etfBars(days){
  var n=days.length,W=340,H=150,L=4,R=4,T=20,B=34,i,x='';
  // 0선 위·아래 공간을 양수·음수 최대값 비율로 나눈다 (빈 공간 최소화)
  var pm=Math.max(0,Math.max.apply(null,days.map(function(d){return d.total}))),
      nm=Math.max(0,-Math.min.apply(null,days.map(function(d){return d.total}))),tot=(pm+nm)||1;
  var use=H-B-T-(pm&&nm?14:0),zero=T+use*pm/tot+(pm&&nm?7:0),k=use/tot;
  var cw=(W-L-R)/n,bw=Math.min(30,cw*0.56);
  for(i=0;i<n;i++){var d=days[i],v=d.total,h=Math.max(1.5,Math.abs(v)*k),
      cx=L+cw*i+cw/2,y=v>=0?zero-h:zero,col=v>0?'var(--up)':v<0?'var(--dn)':'var(--dim)';
    var by=Object.keys(d.by||{}).sort(function(a,b){return Math.abs(d.by[b])-Math.abs(d.by[a])}).slice(0,3)
      .map(function(k){return k+' '+fM(d.by[k])}).join(', ');
    x+='<g><title>'+escA(mdS(d.d)+' 순유입 '+fM(v)+(by?' ('+by+')':''))+'</title>'+
      '<rect x="'+(cx-bw/2).toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h.toFixed(1)+
      '" rx="3" fill="'+col+'"/>'+
      '<text x="'+cx.toFixed(1)+'" y="'+(v>=0?y-5:y+h+12).toFixed(1)+'" text-anchor="middle" class="bl" fill="'+col+'">'+
      escA(fM(v).replace('$','').replace('M',''))+'</text>'+
      '<text x="'+cx.toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" class="pa">'+escA(mdS(d.d))+'</text></g>'}
  return '<svg class="eb" viewBox="0 0 '+W+' '+H+'">'+
    '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+zero.toFixed(1)+'" y2="'+zero.toFixed(1)+'" stroke="var(--line2)"/>'+x+'</svg>'}
function etfCard(a,e){
  if(!e||!e.days||!e.days.length)return '';
  var l=e.last,st=e.streak||0,nm={BTC:'비트코인',ETH:'이더리움',SOL:'솔라나',HYPE:'하이퍼리퀴드',LINK:'체인링크'}[a]||a;
  var top=Object.keys(l.by||{}).sort(function(x,y){return Math.abs(l.by[y])-Math.abs(l.by[x])}).slice(0,4);
  return '<div class="etf"><div class="eh"><b>'+nm+' 현물 ETF</b><span class="cn">'+escA(mdS(l.d))+' 기준'+
    (e.stale?' · 갱신 지연':'')+'</span></div>'+
    '<div class="grid">'+kv('최근일 순유입','<span class="'+(l.total>0?'tu':l.total<0?'td':'')+'">'+fM(l.total)+'</span>',
      st?(Math.abs(st)+'일 연속 '+(st>0?'순유입':'순유출')):'')+
    kv('최근 5거래일 합계','<span class="'+(e.sum5>0?'tu':e.sum5<0?'td':'')+'">'+fM(e.sum5)+'</span>',
      '7거래일 '+fM(e.sum7))+'</div>'+
    '<div class="phd" style="margin-top:10px"><span>최근 '+e.days.length+'거래일 순유입 (백만 달러)</span></div>'+
    etfBars(e.days)+
    (top.length?'<div class="phd" style="margin:10px 0 0"><span>'+escA(mdS(l.d))+' ETF별 순유입 상위</span></div><div class="tags">'+top.map(function(k){var v=l.by[k];
      return '<span class="tag '+(v>=0?'up':'dn')+'">'+escA(k)+' '+escA(fM(v))+'</span>'}).join('')+'</div>':'')+
    '</div>'}

/* ---------- 비트코인 도미넌스 · TOTAL2 ---------- */
var DOM_P='90';
function lineChart(id,ts,v,fmt,col){
  var n=v.length,lo=Math.min.apply(null,v),hi=Math.max.apply(null,v),li=v.indexOf(lo),hx=v.indexOf(hi),
    W=340,H=170,T=26,B=36,L=6,R=6,pad=(hi-lo)*0.08||Math.abs(hi)*0.01||1,mn=lo-pad,mx=hi+pad,i,d='';
  function X(k){return L+k*(W-L-R)/Math.max(1,n-1)}
  function Y(y){return T+(mx-y)/(mx-mn)*(H-T-B)}
  for(i=0;i<n;i++)d+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(v[i]).toFixed(1);
  function lab(k,val,txt,above,cl){var x=X(k),anc=x<70?'start':x>W-70?'end':'middle';
    return '<circle class="mk" cx="'+x.toFixed(1)+'" cy="'+Y(val).toFixed(1)+'" r="3.5" fill="'+cl+
      '" stroke="var(--card)" stroke-width="2"/><text x="'+x.toFixed(1)+'" y="'+(above?Y(val)-8:Y(val)+16).toFixed(1)+
      '" text-anchor="'+anc+'" class="pl" fill="'+cl+'">'+txt+'</text>'}
  CH_D[id]={ts:ts,v:v,h:false,X:X,Y:Y,W:W,H:H,T:T,B:B,fmt:fmt};
  return '<svg class="pc" id="'+id+'" viewBox="0 0 '+W+' '+H+'">'+
    '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+(H-18)+'" y2="'+(H-18)+'" stroke="var(--line)"/>'+
    '<path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="2" stroke-linejoin="round"/>'+
    (n>1?lab(hx,hi,'최고 '+fmt(hi),true,'var(--up)')+lab(li,lo,'최저 '+fmt(lo),false,'var(--dn)'):'')+
    '<text x="'+L+'" y="'+(H-4)+'" class="pa">'+fdt(ts[0])+'</text>'+
    '<text x="'+(W-R)+'" y="'+(H-4)+'" class="pa" text-anchor="end">'+fdt(ts[n-1])+'</text>'+
    '<g class="xh" style="display:none"><line y1="'+T+'" y2="'+(H-B)+'" stroke="var(--sub)" stroke-dasharray="3 3"/>'+
    '<circle r="4.5" fill="'+col+'" stroke="var(--txt)" stroke-width="1.5"/>'+
    '<rect rx="6" height="22" fill="var(--card2)" stroke="var(--line2)"/><text class="xt" fill="var(--txt)"></text></g>'+
    '<rect class="hit" x="0" y="0" width="'+W+'" height="'+H+'" fill="transparent"/></svg>'}
function domCard(dm){
  if(!dm||!dm.t||!dm.t.length)return '';
  var k=Math.min(+DOM_P,dm.t.length),ts=dm.t.slice(-k).map(function(d){return Date.parse(d+'T00:00:00')});
  var dv=dm.dom.slice(-k),tv=dm.total2.slice(-k),n=dv.length;
  function fpct(x){return x.toFixed(2)+'%'}
  function fT(x){return x>=1000?'$'+(x/1000).toFixed(2)+'T':'$'+x.toFixed(0)+'B'}
  function chg(a,j){return a.length>j?a[a.length-1]-a[a.length-1-j]:null}
  function chgP(a,j){return a.length>j?(a[a.length-1]/a[a.length-1-j]-1)*100:null}
  var btn='<div class="pbar">'+['30','90'].map(function(q){return '<button class="pb dp'+(q===DOM_P?' on':'')+
    '" data-dp="'+q+'">'+q+'일</button>'}).join('')+'</div>';
  var few=dm.t.length<7?'<p class="note">'+escA(dm.src)+' 기준 · 기록 '+dm.t.length+'일째 (매일 쌓여 추이가 길어집니다)</p>':'';
  return '<div class="hd">비트코인 도미넌스 · TOTAL2<small>'+escA(dm.src||'')+'</small></div><div class="etf" id="domw">'+
    '<div class="phd"><span>최근 '+n+'일 · 일 단위</span>'+btn+'</div>'+
    '<div class="grid">'+kv('BTC 도미넌스',fpct(dv[n-1]),nz(chg(dv,7))?'7일 '+(chg(dv,7)>=0?'+':'')+chg(dv,7).toFixed(2)+'%p':'')+
    kv('TOTAL2 (BTC 제외 시총)',fT(tv[n-1]),nz(chgP(tv,7))?'7일 '+fpc(chgP(tv,7),1):'')+'</div>'+
    '<div class="sec">BTC 도미넌스</div>'+lineChart('dom-d',ts,dv,fpct,'#f7931a')+
    '<div class="sec">TOTAL2</div>'+lineChart('dom-t',ts,tv,fT,'var(--acc)')+
    '<p class="note">도미넌스 상승 = 자금이 비트코인으로 쏠림, TOTAL2 상승 = 알트코인 전반으로 자금 유입</p>'+few+'</div>'}
document.addEventListener('click',function(e){
  var b=e.target.closest&&e.target.closest('button.dp');if(!b||!CR)return;
  DOM_P=b.getAttribute('data-dp');var w=document.getElementById('domw');
  if(w){var t=document.createElement('div');t.innerHTML=domCard(CR.dom);
    w.previousSibling.remove();w.replaceWith.apply(w,[].slice.call(t.childNodes))}});

function coinCard(c){
  var m=c.market||{},hl=c.hl||{},ok=c.okx||{},op=c.options,px=m.price,x='';
  // 헤더: 이름·가격 / 핵심 신호·등락 / AI 한 줄
  var line=((c.brief||'').match(/^[\s\S]*?[.다요](?=\s|$)/)||[c.brief||''])[0];
  var sum='<summary><div class="cr1"><div class="ch"><b>'+escA(c.sym)+'</b><span class="cn">'+
    escA(c.name)+(m.rank?' · #'+m.rank:'')+'</span></div><div class="cp">'+fp(px)+'</div></div>'+
    '<div class="cr2">'+(tagsHtml(c.tags,3)||'<div></div>')+'<div class="chg '+
    (nz(m.ch24)?(m.ch24>=0?'tu':'td'):'')+'">'+fpc(m.ch24)+'</div></div>'+
    '<div class="cr3">'+(line?'<b class="ai">✦</b><span>'+escA(line)+'</span>':
      '<span>자세히 보기</span>')+'</div></summary>';
  if(c.tags&&c.tags.length)x+='<div class="sec" style="margin-top:0">핵심 신호</div>'+
    tagsHtml(c.tags)+'<div style="height:12px"></div>';
  // 가격
  x+=priceChart(c);
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
  var mk='',ef=CR.etf||{};
  var ea=['BTC','ETH','SOL','HYPE','LINK'].filter(function(a){return ef[a]});
  var etf=ea.length?'<div class="hd">현물 ETF 자금 흐름<small>'+escA(ef[ea[0]].src||'')+
    ' · 미국 거래일 기준</small></div>'+ea.map(function(a){return etfCard(a,ef[a])}).join(''):'';
  var dm=domCard(CR.dom);
  if(MKT&&MKT.secs.length)mk='<div class="hd">크립토 시장 지표<small>'+escA(MKT.updated)+'</small></div>'+
    secTables(MKT.secs,MKT.secs.length);  // 전부 펼침
  $('#p3').innerHTML='<div class="cbar"><span id="cupd">'+escA(CR.updated||'')+
    (CR.live?' · 시세 '+CR.live+' 갱신':'')+'</span><button id="clive">시세 새로고침</button></div>'+
    top+pickCard(CR.pick,CR.pastPicks)+ov+etf+dm+mk+'<div class="hd">관심 코인 8종<small>4시간마다 갱신</small></div>'+LEGEND+cards+err;
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
function loadMarket(){
  fetch('data.json?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(function(d){
    var order=['코인베이스 프리미엄','스테이블코인','DeFiLlama'],secs=[];
    order.forEach(function(k){(d.sections||[]).forEach(function(s){
      if(s.title.indexOf(k)>=0)secs.push(s)})});
    MKT={updated:d.updated||'',secs:secs};
    if(CR)try{renderCrypto()}catch(e){}}).catch(function(){})}
loadCrypto();loadMarket();
