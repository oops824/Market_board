function spark(pts,color,unit){
  if(!pts||pts.length<2)return '<div class="s">데이터 적립 중 ('+
    (pts?pts.length:0)+'일)</div>';
  var W=320,H=105,i,vs=[];
  for(i=0;i<pts.length;i++){vs.push(pts[i].v)}
  var lo=Math.min.apply(null,vs),hi=Math.max.apply(null,vs);
  var last=vs[vs.length-1],li=vs.indexOf(lo),hidx=vs.indexOf(hi);
  var mn=lo,mx=hi;
  if(mx===mn){mx=mx+Math.abs(mx||1)*0.1;mn=mn-Math.abs(mn||1)*0.1}
  var pad=(mx-mn)*0.25;mn=mn-pad;mx=mx+pad;
  var span=(mx-mn)||1;
  function fm(v){var a=Math.abs(v);
    return a>=1000?v.toFixed(0):(a>=10?v.toFixed(2):v.toFixed(3))}
  function X(k){return 40+k*(W-48)/(pts.length-1)}
  function Y(v){return H-16-(v-mn)/span*(H-32)}
  var z='';
  for(i=0;i<=4;i++){
    var gv=mn+span*i/4,gy=Y(gv);
    z+='<line x1="40" y1="'+gy.toFixed(1)+'" x2="'+(W-6)+'" y2="'+gy.toFixed(1)+
       '" stroke="#252b35" stroke-width="1"/>'+
       '<text x="2" y="'+(gy+3).toFixed(1)+'" fill="#7f8898" font-size="8.5">'+
       fm(gv)+'</text>'}
  if(mn<0&&mx>0){z+='<line x1="40" y1="'+Y(0).toFixed(1)+'" x2="'+(W-6)+
    '" y2="'+Y(0).toFixed(1)+'" stroke="#7f8898" stroke-dasharray="3 3"/>'}
  var d='';
  for(i=0;i<pts.length;i++){d+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(pts[i].v).toFixed(1)+' '}
  function mark(idx,val,col,dy){
    var x=X(idx),tx=x-22;
    if(tx<42)tx=42;
    if(tx>W-46)tx=W-46;
    return '<circle cx="'+x.toFixed(1)+'" cy="'+Y(val).toFixed(1)+'" r="2.6" fill="'+col+
      '"/><text x="'+tx.toFixed(1)+'" y="'+(Y(val)+dy).toFixed(1)+'" fill="'+col+
      '" font-size="9.5" font-weight="600">'+fm(val)+unit+'</text>'}
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">'+z+
    '<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2"/>'+
    mark(hidx,hi,'#ff5c6c',-7)+mark(li,lo,'#4d9dff',14)+
    '<circle cx="'+X(pts.length-1).toFixed(1)+'" cy="'+Y(last).toFixed(1)+
    '" r="3.4" fill="'+color+'"/>'+
    '<text x="40" y="'+(H-3)+'" fill="#7f8898" font-size="9.5">'+
    String(pts[0].d).slice(5)+'</text>'+
    '<text x="'+(W-48)+'" y="'+(H-3)+'" fill="#7f8898" font-size="9.5">'+
    String(pts[pts.length-1].d).slice(5)+'</text>'+
    '<text x="2" y="10" fill="'+color+'" font-size="11" font-weight="600">'+
    fm(last)+unit+'</text></svg>'}
// 추이 그래프는 카테고리별 탭에 나눠 배치: 지표(금리·달러·변동성·위험선호), 미국주식(시장 폭·반도체 주도력), 가상자산(프리미엄·디파이)
var TR_DEFS={
  macro:[['tnx','10년 국채금리','#ff9f43','%'],['irx','3개월 국채금리','#feca57','%'],['dxy','달러지수 DXY','#48dbfb',''],
         ['vix','변동성 VIX','#ff6b6b',''],['risk','위험선호 HYG/TLT','#1dd1a1','']],
  stock:[['breadth','시장 폭 RSP/SPY','#a29bfe',''],['smh','반도체 주도력 SMH/SPY','#00d2d3','']],
  crypto:[['btc_prem','BTC 코인베이스 프리미엄','#f7931a','%'],['eth_prem','ETH 코인베이스 프리미엄','#7c9cff','%']]};
function trCharts(h,defs){
  var x='';
  defs.forEach(function(d){
    var p=[];h.forEach(function(r){if(typeof r[d[0]]==='number')p.push({d:r.date,v:r[d[0]]})});
    x+='<div class="chart"><div class="t">'+d[1]+'</div><div class="s">'+(d[0].indexOf('prem')>=0?
       '양수=미국 매수 우위 · 일별':'일별 추이')+'</div>'+spark(p,d[2],d[3])+'</div>'});
  return x}
function defiCharts(h){
  var cnt={},n,x='';
  h.forEach(function(r){var o=r.defi||{};for(n in o)if(o.hasOwnProperty(n))cnt[n]=(cnt[n]||0)+1});
  var top=Object.keys(cnt).sort(function(a,b){return cnt[b]-cnt[a]}).slice(0,3),cols=['#4ade80','#38bdf8','#f472b6'];
  top.forEach(function(k,i){
    var p=[];h.forEach(function(r){if(r.defi&&typeof r.defi[k]==='number')p.push({d:r.date,v:r.defi[k]})});
    x+='<div class="chart"><div class="t">'+esc(k)+'</div><div class="s">24시간 프로토콜 수익 (M$)</div>'+
       spark(p,cols[i],'')+'</div>'});
  return x}
function drawTrends(h){
  if(!h||!h.length)return;
  var hd=function(t){return '<div class="hd">'+t+'<small>일별 기록</small></div>'};
  $('#tr-macro').innerHTML=hd('매크로 추이')+trCharts(h,TR_DEFS.macro);
  $('#tr-stock').innerHTML=hd('미국 주식 추이')+trCharts(h,TR_DEFS.stock);
  $('#tr-crypto').innerHTML=hd('가상자산 추이')+trCharts(h,TR_DEFS.crypto)+defiCharts(h)}

function trends(){
  fetch('history/trend.json?t='+Date.now())
  .then(function(r){if(!r.ok)throw new Error('파일 없음');return r.json()})
  .then(function(h){
    try{drawTrends(h)}catch(e){$('#tr-macro').innerHTML='<p class="err">그래프 오류: '+e.message+'</p>'}})
  .catch(function(){})}

trends();
