function spark(pts,color,unit){
  if(!pts||pts.length<2)return '<div class="s">데이터 적립 중 ('+
    (pts?pts.length:0)+'일)</div>';
  var W=320,H=95,i,vs=[];
  for(i=0;i<pts.length;i++){vs.push(pts[i].v)}
  var mn=Math.min.apply(null,vs),mx=Math.max.apply(null,vs);
  if(mx===mn){mx=mx+Math.abs(mx||1)*0.1;mn=mn-Math.abs(mn||1)*0.1}
  var pad=(mx-mn)*0.18;mn=mn-pad;mx=mx+pad;
  var span=(mx-mn)||1;
  function X(k){return 34+k*(W-42)/(pts.length-1)}
  function Y(v){return H-14-(v-mn)/span*(H-30)}
  var d='';
  for(i=0;i<pts.length;i++){d+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(pts[i].v).toFixed(1)+' '}
  var z='';
  if(mn<0&&mx>0){z='<line x1="34" y1="'+Y(0).toFixed(1)+'" x2="'+(W-6)+
    '" y2="'+Y(0).toFixed(1)+'" stroke="#39424f" stroke-dasharray="3 3"/>'}
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">'+z+
    '<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2"/>'+
    '<circle cx="'+X(pts.length-1).toFixed(1)+'" cy="'+Y(vs[vs.length-1]).toFixed(1)+
    '" r="3.2" fill="'+color+'"/>'+
    '<text x="2" y="11" fill="#5d6675" font-size="9">'+mx.toFixed(2)+unit+'</text>'+
    '<text x="2" y="'+(H-16)+'" fill="#5d6675" font-size="9">'+mn.toFixed(2)+unit+'</text>'+
    '<text x="34" y="'+(H-2)+'" fill="#5d6675" font-size="9">'+
    String(pts[0].d).slice(5)+'</text>'+
    '<text x="'+(W-46)+'" y="'+(H-2)+'" fill="#5d6675" font-size="9">'+
    String(pts[pts.length-1].d).slice(5)+'</text></svg>'}
function drawTrends(h){
  if(!h||!h.length)return '<p class="err">기록이 아직 없습니다.</p>';
  var x='',i,j,n;
  var defs=[['btc_prem','BTC 코인베이스 프리미엄','#f7931a','%'],
            ['eth_prem','ETH 코인베이스 프리미엄','#7c9cff','%']];
  for(i=0;i<defs.length;i++){
    var k=defs[i][0],p=[];
    for(j=0;j<h.length;j++){
      if(typeof h[j][k]==='number')p.push({d:h[j].date,v:h[j][k]})}
    x+='<div class="chart"><div class="t">'+defs[i][1]+
       '</div><div class="s">양수=미국 매수 우위</div>'+
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
