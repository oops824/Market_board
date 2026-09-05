var $=function(s){return document.querySelector(s)};
var CUR=null;
function esc(t){return String(t==null?'':t).replace(/[<>&]/g,function(c){
  return {'<':'&lt;','>':'&gt;','&':'&amp;'}[c]})}
function cls(c){if(!c)return 'na';return String(c).trim().charAt(0)==='-'?'dn':'up'}

function findItem(title,kw){
  if(!CUR)return null;
  for(var i=0;i<CUR.sections.length;i++){var s=CUR.sections[i];
    if(s.title.indexOf(title)<0)continue;
    for(var j=0;j<s.items.length;j++){
      if(s.items[j].name.indexOf(kw)>=0)return s.items[j]}}
  return null}

function kpi(){
  var picks=[['매크로','변동성 VIX','VIX'],['매크로','달러지수','달러'],
             ['매크로','HYG/TLT','위험선호'],['프리미엄','BTC','BTC 프리미엄']];
  var h='';
  for(var i=0;i<picks.length;i++){
    var it=findItem(picks[i][0],picks[i][1]);
    if(!it)continue;
    h+='<div><div class="k">'+picks[i][2]+'</div><div class="v">'+esc(it.value)+
       '</div><div class="c"><span class="badge '+cls(it.change)+'">'+
       (esc(it.change)||'-')+'</span></div></div>'}
  $('#kpi').innerHTML=h}

function summary(){
  if(!CUR.summary){$('#sum').innerHTML='';return}
  var parts=CUR.summary.split(/\n(?=\[)/),h='';
  for(var i=0;i<parts.length;i++){
    var m=parts[i].match(/^\[(.+?)\]\s*([\s\S]*)$/);
    if(m){h+='<div class="sum"><b>'+esc(m[1])+'</b>'+
      esc(m[2].trim()).replace(/^- /gm,'· ')+'</div>'}
    else if(parts[i].trim()){h+='<div class="sum">'+esc(parts[i].trim())+'</div>'}}
  $('#sum').innerHTML=h}

function tables(){
  var h='';
  for(var i=0;i<CUR.sections.length;i++){
    var s=CUR.sections[i],rows='';
    for(var j=0;j<s.items.length;j++){
      var it=s.items[j],lead=it.name.indexOf('└')>=0;
      rows+='<tr class="'+(lead?'lead':'')+'"><td class="n">'+
        esc(it.name.replace('└','↳'))+
        (it.comment?'<div class="sub">'+esc(it.comment)+'</div>':'')+
        '</td><td class="v">'+esc(it.value)+
        (it.change?'<br><span class="badge '+cls(it.change)+'">'+esc(it.change)+'</span>':'')+
        '</td></tr>'}
    h+='<details'+(i<2?' open':'')+'><summary>'+esc(s.title)+'</summary><div class="body">'+
       (s.note?'<p class="note">'+esc(s.note)+'</p>':'')+
       '<table>'+rows+'</table></div></details>'}
  $('#app').innerHTML=h}

function render(d){
  CUR=d;
  $('#meta').textContent='갱신 '+(d.updated||'-');
  try{kpi()}catch(e){}
  try{summary()}catch(e){}
  try{tables()}catch(e){$('#app').innerHTML='<p class="err">표시 오류: '+e.message+'</p>'}}

function load(p){
  fetch(p+'?t='+Date.now()).then(function(r){if(!r.ok)throw 0;return r.json()})
  .then(render).catch(function(){
    $('#meta').textContent='';
    $('#app').innerHTML='<p class="err">data.json을 읽지 못했습니다.<br>'+
      '실행이 끝났는지, 1~2분 기다렸는지 확인해 주세요.</p>'})}
$('#t1').onclick=function(){$('#t1').className='tab on';$('#t2').className='tab';
  $('#p1').className='';$('#p2').className='hide'};
$('#t2').onclick=function(){$('#t2').className='tab on';$('#t1').className='tab';
  $('#p2').className='';$('#p1').className='hide'};

fetch('reports/list.json?t='+Date.now())
.then(function(r){return r.ok?r.json():Promise.reject()}).then(function(l){
  if(!l.length)return;
  var s=$('#arc');s.className='';
  var o='<option value="data.json">최신 리포트</option>';
  for(var i=0;i<l.length;i++){o+='<option value="reports/'+l[i]+'">'+
    l[i].replace('.json','')+'</option>'}
  s.innerHTML=o;
  s.onchange=function(){load(s.value)}}).catch(function(){});

load('data.json');
function spark(pts,color,unit){
  if(pts.length<2)return '<div class="s">데이터 적립 중 ('+pts.length+'일). '+
    '2일 이상 쌓이면 그래프가 나타납니다.</div>';
  var W=320,H=95,vs=pts.map(function(p){return p.v});
  var mn=Math.min.apply(null,vs),mx=Math.max.apply(null,vs);
  if(mx===mn){mx+=1;mn-=1}
  var pad=(mx-mn)*0.18;mn-=pad;mx+=pad;
  var X=function(i){return 34+i*(W-42)/(pts.length-1)};
  var Y=function(v){return H-14-(v-mn)/(mx-mn)*(H-30)};
  var d='';
  for(var i=0;i<pts.length;i++){d+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(pts[i].v).toFixed(1)+' '}
  var z=(mn<0&&mx>0)?'<line x1="34" y1="'+Y(0).toFixed(1)+'" x2="'+(W-6)+'" y2="'+
    Y(0).toFixed(1)+'" stroke="#39424f" stroke-dasharray="3 3"/>':'';
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">'+z+
    '<path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2"'+
    ' stroke-linejoin="round" stroke-linecap="round"/>'+
    '<circle cx="'+X(pts.length-1).toFixed(1)+'" cy="'+Y(vs[vs.length-1]).toFixed(1)+
    '" r="3.2" fill="'+color+'"/>'+
    '<text x="2" y="11" fill="#5d6675" font-size="9">'+mx.toFixed(2)+unit+'</text>'+
    '<text x="2" y="'+(H-16)+'" fill="#5d6675" font-size="9">'+mn.toFixed(2)+unit+'</text>'+
    '<text x="34" y="'+(H-2)+'" fill="#5d6675" font-size="9">'+pts[0].d.slice(5)+'</text>'+
    '<text x="'+(W-46)+'" y="'+(H-2)+'" fill="#5d6675" font-size="9">'+
    pts[pts.length-1].d.slice(5)+'</text></svg>'}

function trends(){
  fetch('history/trend.json?t='+Date.now())
  .then(function(r){return r.ok?r.json():Promise.reject()})
  .then(function(h){
    if(!h.length){$('#p2').innerHTML='<p class="err">기록이 아직 없습니다.</p>';return}
    var x='',defs=[['btc_prem','BTC 코인베이스 프리미엄','#f7931a','%'],
                   ['eth_prem','ETH 코인베이스 프리미엄','#7c9cff','%']];
    for(var i=0;i<defs.length;i++){
      var k=defs[i][0],p=[];
      for(var j=0;j<h.length;j++){if(typeof h[j][k]==='number')p.push({d:h[j].date,v:h[j][k]})}
      x+='<div class="chart"><div class="t">'+defs[i][1]+
         '</div><div class="s">양수=미국 매수 우위</div>'+spark(p,defs[i][2],defs[i][3])+'</div>'}
    var cnt={};
    for(var j=0;j<h.length;j++){var o=h[j].defi||{};
      for(var n in o){cnt[n]=(cnt[n]||0)+1}}
    var top=Object.keys(cnt).sort(function(a,b){return cnt[b]-cnt[a]}).slice(0,3);
    var cols=['#4ade80','#38bdf8','#f472b6'];
    for(var i=0;i<top.length;i++){
      var p=[];
      for(var j=0;j<h.length;j++){
        if(h[j].defi&&typeof h[j].defi[top[i]]==='number')
          p.push({d:h[j].date,v:h[j].defi[top[i]]})}
      x+='<div class="chart"><div class="t">'+esc(top[i])+
         '</div><div class="s">24시간 프로토콜 수익 (M$)</div>'+spark(p,cols[i],'')+'</div>'}
    $('#p2').innerHTML=x})
  .catch(function(){$('#p2').innerHTML='<p class="err">history/trend.json이 없습니다.<br>'+
    'macro.py의 기록 코드가 들어갔는지 확인해 주세요.</p>'})}

trends();
