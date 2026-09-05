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
