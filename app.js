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
