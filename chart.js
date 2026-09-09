function spark(pts,color,unit){
  if(!pts||pts.length<2)return '<div class="s">데이터 적립 중 ('+
    (pts?pts.length:0)+'일)</div>';
  var W=320,H=95,i,vs=[];
  for(i=0;i<pts.length;i++){vs.push(pts[i].v)}
  var lo=Math.min.apply(null,vs),hi=Math.max.apply(null,vs);
  var last=vs[vs.length-1],li=vs.indexOf(lo),hidx=vs.indexOf(hi);
  var mn=lo,mx=hi;
  if(mx===mn){mx=mx+Math.abs(mx||1)*0.1;mn=mn-Math.abs(mn||1)*0.1}
  var pad=(mx-mn)*0.22;mn=mn-pad;mx=mx+pad;
  var span=(mx-mn)||1;
  function X(k){return 34+k*(W-42)/(pts.length-1)}
  function Y(v){return H-14-(v-mn)/span*(H-30)}
  function fm(v){var a=Math.abs(v);
    return a>=1000?v.toFixed(0):a>=10?v.toFixed(2):v.toFixed(3)}
  var d='';
  for(i=0;i<pts.length;i++){d+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(pts[i].v).toFixed(1)+' '}
  var z='';
  for(i=0;i<=4;i++){
    var gv=mn+span*i/4,gy=Y(gv);
    z+='<line x1="34" y1="'+gy.toFixed(1)+'" x2="'+(W-6)+'" y2="'+gy.toFixed(1)+
       '" stroke="#232a35" stroke-width="1"/>'+
       '<text x="2" y="'+(gy+3).toFixed(1)+'" fill="#4a5361" font-size="8">'+
       fm(gv)+'</text>'}
  if(mn<0&&mx>0){z+='<line x1="34" y1="'+Y(0).toFixed(1)+'" x2="'+(W-6)+
    '" y2="'+Y(0).toFixed(1)+'" stroke="#5a6577" stroke-dasharray="3 3"/>'}
  function mark(idx,val,col,dy){
    var x=X(idx),tx=x<60?x:(x>W-60?x-52:x-24);
    return '<circle cx="'+x.toFixed(1)+'" cy="'+Y(val).toFixed(1)+'" r="2.6" fill="'+col+
      '" opacity=".85"/><text x="'+tx.toFixed(1)+'" y="'+(Y(val)+dy).toFixed(1)+
      '" fill="'+col+'" font-size="9.5">'+fm(val)+unit+'</text>'}
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">'+z+
    '<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2"/>'+
    mark(hidx,hi,'#ff8080',-6)+mark(li,lo,'#6aa8ff',13)+
    '<circle cx="'+X(pts.length-1).toFixed(1)+'" cy="'+Y(last).toFixed(1)+
    '" r="3.4" fill="'+color+'"/>'+
    '<text x="34" y="'+(H-2)+'" fill="#5d6675" font-size="9">'+
    String(pts[0].d).slice(5)+'</text>'+
    '<text x="'+(W-46)+'" y="'+(H-2)+'" fill="#5d6675" font-size="9">'+
    String(pts[pts.length-1].d).slice(5)+'</text>'+
    '<text x="2" y="11" fill="'+color+'" font-size="11" font-weight="600">'+
    fm(last)+unit+'</text></svg>'}
function drawTrends(h){
  if(!h||!h.length)return '<p class="err">기록이 아직 없습니다.</p>';
  var x='',i,j,n;
  var defs=[['tnx','10년 국채금리','#ff9f43','%'],
            ['irx','3개월 국채금리','#feca57','%'],
            ['dxy','달러지수 DXY','#48dbfb',''],
            ['vix','변동성 VIX','#ff6b6b',''],
            ['risk','위험선호 HYG/TLT','#1dd1a1',''],
            ['breadth','시장 폭 RSP/SPY','#a29bfe',''],
            ['smh','반도체 주도력 SMH/SPY','#00d2d3',''],
            ['btc_prem','BTC 코인베이스 프리미엄','#f7931a','%'],
            ['eth_prem','ETH 코인베이스 프리미엄','#7c9cff','%']];
  for(i=0;i<defs.length;i++){
    var k=defs[i][0],p=[];
    for(j=0;j<h.length;j++){
      if(typeof h[j][k]==='number')p.push({d:h[j].date,v:h[j][k]})}
    x+='<div class="chart"><div class="t">'+defs[i][1]+
       '</div><div class="s">'+(defs[i][0].indexOf('prem')>=0?
       '양수=미국 매수 우위':'일별 추이')+'</div>'+
       spark(p,defs[i][2],defs[i][3])+'</div>'}
  var cnt={};
  for(j=0;j<h.length;j++){var o=h[j].defi||{};
    for(n in o){if(o.hasOwnProperty(n))cnt[n]=(cnt[n]||0)+1}}
  var names=[];
  for(n in cnt){if(cnt.hasOwnProperty(n))names.push(n)}
  names.sort(function(a,b){return cnt[b]-cnt[a]});
  var top=names.slice(0,3),cols=['#4ade80','#38bdf8','#f472b6'];
  for(i=0;i<top.length;i++){
    var p2=[];
    for(j=0;j<h.length;j++){
      if(h[j].defi&&typeof h[j].defi[top[i]]==='number')
        p2.push({d:h[j].date,v:h[j].defi[top[i]]})}
    x+='<div class="chart"><div class="t">'+esc(top[i])+
       '</div><div class="s">24시간 프로토콜 수익 (M$)</div>'+
       spark(p2,cols[i],'')+'</div>'}
  return x||'<p class="err">그릴 데이터가 없습니다.</p>'}

function trends(){
  fetch('history/trend.json?t='+Date.now())
  .then(function(r){if(!r.ok)throw new Error('파일 없음');return r.json()})
  .then(function(h){
    try{$('#p2').innerHTML=drawTrends(h)}
    catch(e){$('#p2').innerHTML='<p class="err">그래프 오류: '+e.message+'</p>'}})
  .catch(function(e){$('#p2').innerHTML='<p class="err">불러오기 실패: '+
    (e&&e.message?e.message:'알 수 없음')+'</p>'})}

trends();
