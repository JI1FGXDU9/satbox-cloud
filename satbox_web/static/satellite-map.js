(() => {
'use strict';
const settings=window.satboxMap;
const started=performance.now();
let targetName='',targetActive=false,selectedPass=null;
if(!window.L){document.getElementById('map-status').textContent='地図ライブラリを読み込めません。ページを再読み込みしてください。';return;}
const storageKey='satbox-map-'+settings.userId;
let saved={},busy=false,restoredSelection=false;
try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'{}');}catch(e){}

function label(name){const el=document.createElement('span');el.textContent=name;return el;}
// Start with a wide fixed view centred on the observer.
// 観測地点を中心とした広域表示を初期倍率にする。
const map=L.map('satellite-map',{
 dragging:false,scrollWheelZoom:false,touchZoom:false,doubleClickZoom:false,
 boxZoom:false,keyboard:false,zoomControl:false
}).setView([settings.observerLat,settings.observerLon],3);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
 // OSM requires a Referer. Override the page's same-origin policy for tiles only.
 referrerPolicy:'strict-origin-when-cross-origin',
 maxZoom:18,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const observer=L.circleMarker([settings.observerLat,settings.observerLon],{radius:9,color:'#0066cc',weight:3,fillColor:'#3399ff',fillOpacity:1}).addTo(map);
observer.bindTooltip('観測地点',{permanent:false});
const satIcon=L.divIcon({className:'',html:'<div class="sat-icon">&#128752;</div>',iconSize:[34,34],iconAnchor:[17,17]});
const satellite=L.marker([0,0],{icon:satIcon}).addTo(map);
const footprint=L.circle([0,0],{radius:0,color:'#1683ff',weight:3,fillColor:'#1683ff',fillOpacity:.22}).addTo(map);
const direction=L.polyline([],{color:'red',weight:4,dashArray:'9 8'}).addTo(map);
let lastPoint=null,lastHeading=null;

const Gauge=L.Control.extend({
 options:{position:'bottomleft'},
 onAdd:function(){
  const d=L.DomUtil.create('div','map-gauges');
  d.innerHTML='<div><svg width="94" height="94" viewBox="0 0 94 94"><circle cx="47" cy="47" r="38" fill="none" stroke="#111" stroke-width="1.5"/><text x="47" y="9" text-anchor="middle">N</text><text x="88" y="51" text-anchor="middle">E</text><text x="47" y="93" text-anchor="middle">S</text><text x="6" y="51" text-anchor="middle">W</text><line id="azNeedle" x1="47" y1="47" x2="47" y2="17" stroke="red" stroke-width="3"/></svg><div class="gauge-label" id="azText">Az --°</div></div>'+
  '<div><svg width="116" height="68" viewBox="0 0 116 68"><path d="M10 58 A48 48 0 0 1 106 58" fill="none" stroke="#111" stroke-width="1.5"/><line x1="10" y1="58" x2="106" y2="58" stroke="#111"/><text x="8" y="68">0°</text><text x="52" y="10">90°</text><text x="94" y="68">180°</text><line id="elNeedle" x1="58" y1="58" x2="14" y2="58" stroke="#00c832" stroke-width="4"/></svg><div class="gauge-label" id="elText">El --°</div></div>';
  L.DomEvent.disableClickPropagation(d);return d;
 }
});
map.addControl(new Gauge());

function bearing(a,b){
 const r=Math.PI/180,p1=a.lat*r,p2=b.lat*r,dl=(b.lng-a.lng)*r;
 return (Math.atan2(Math.sin(dl)*Math.cos(p2),Math.cos(p1)*Math.sin(p2)-Math.sin(p1)*Math.cos(p2)*Math.cos(dl))*180/Math.PI+360)%360;
}
function destination(p,brng,km){
 const R=6371,r=Math.PI/180,d=km/R,b=brng*r,p1=p.lat*r,l1=p.lng*r;
 const p2=Math.asin(Math.sin(p1)*Math.cos(d)+Math.cos(p1)*Math.sin(d)*Math.cos(b));
 const l2=l1+Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(p1),Math.cos(d)-Math.sin(p1)*Math.sin(p2));
 return L.latLng(p2/r,((l2/r+540)%360)-180);
}
function updateGauges(az,el){
 document.getElementById('azNeedle').setAttribute('visibility','visible');
 document.getElementById('azNeedle').setAttribute('transform','rotate('+az+' 47 47)');
 const elNeedle=document.getElementById('elNeedle');
 if(!Number.isFinite(el)||el<0){
  elNeedle.setAttribute('visibility','hidden');
 }else{
  elNeedle.setAttribute('visibility','visible');
 }
 const angle=(180-Math.max(0,Math.min(180,el)))*Math.PI/180;
 elNeedle.setAttribute('x2',58+44*Math.cos(angle));
 elNeedle.setAttribute('y2',58-44*Math.sin(angle));
 document.getElementById('azText').textContent='Az '+az.toFixed(1)+'°';
 document.getElementById('elText').textContent='El '+el.toFixed(1)+'°';
}
function syncTarget(){
 const now=window.satboxClock.serverTime+performance.now()-started;
 const rows=[...document.querySelectorAll('.pass-row')].filter(row=>Number(row.querySelector('.countdown').dataset.losMs)>now);
 if(!restoredSelection){selectedPass=rows.find(row=>row.querySelector('.countdown').dataset.aosMs===saved.passAos&&row.querySelector('.satellite-toggle').dataset.satellite===saved.passName)||null;restoredSelection=true;}
 if(selectedPass&&!rows.includes(selectedPass)){selectedPass=null;save();}
 const row=selectedPass||rows[0];
 const name=row?.querySelector('.satellite-toggle').dataset.satellite||'';
 const active=!!row&&Number(row.querySelector('.countdown').dataset.aosMs)<=now;
 if(name!==targetName||active!==targetActive){clearSatellite();targetName=name;targetActive=active;}
 document.getElementById('map-satellite-name').textContent=targetName;

 if(!targetActive)document.getElementById('map-status').textContent=targetName?targetName+'：AOS待ち':'表示対象のPassはありません';
 if(row&&!targetActive){
  document.getElementById('elText').textContent='El 0.0°';
  const elNeedle=document.getElementById('elNeedle');
  elNeedle.setAttribute('visibility','visible');
  elNeedle.setAttribute('x2','14');
  elNeedle.setAttribute('y2','58');
  const aosAz=Number(row.querySelector('[data-aos-az]').dataset.aosAz);
  if(Number.isFinite(aosAz)){
   const needle=document.getElementById('azNeedle');
   needle.setAttribute('visibility','visible');
   needle.setAttribute('transform','rotate('+aosAz+' 47 47)');
   document.getElementById('azText').textContent='Az '+aosAz.toFixed(1)+'°（AOS方位）';
  }
 }
}
async function refresh(){
 syncTarget();
 if(busy || !targetName || !targetActive || document.hidden)return;
 busy=true;const requestedName=targetName;
 try{
  const res=await fetch(settings.url+'?name='+encodeURIComponent(targetName)+'&t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(15000)});
  if(!res.ok)throw new Error('HTTP '+res.status);
  const d=await res.json();
  syncTarget();
  if(requestedName!==targetName||!targetActive)return;
  const obs=L.latLng(d.observerLat,d.observerLon);
  observer.setLatLng(obs);
  // Set the map position only once. Satellite movement or selection
  // changes must not move or zoom the map automatically.
  // 地図位置は初回だけ設定し、衛星移動・切替では動かさない。

  if(!d.valid){clearSatellite();document.getElementById('map-status').textContent=d.error||'衛星位置を計算中...';return;}
  [satellite,footprint,direction].forEach(layer=>{if(!map.hasLayer(layer))layer.addTo(map);});
  const p=L.latLng(d.satLat,d.satLon);
  satellite.setLatLng(p);
  if(satellite.getTooltip())satellite.setTooltipContent(label(d.name));
  else satellite.bindTooltip(label(d.name),{permanent:true,direction:'right',offset:[15,0],className:'sat-label'});
  footprint.setLatLng(p).setRadius(d.footprintKm*1000);
  if(lastPoint&&lastPoint.distanceTo(p)>20)lastHeading=bearing(lastPoint,p);
  if(lastHeading!==null)direction.setLatLngs([p,destination(p,lastHeading,Math.max(350,d.altKm*.9))]);
  lastPoint=p;
  updateGauges(d.az,d.el);
  document.getElementById('map-status').textContent=d.name+' / Az '+d.az.toFixed(1)+'° / El '+d.el.toFixed(1)+'° / 高度 '+d.altKm.toFixed(0)+' km';
 }catch(e){if(requestedName===targetName){clearSatellite();document.getElementById('map-status').textContent='地図データを取得できません。再試行します。';}}
 finally{busy=false;if(requestedName!==targetName)refresh();}
}
setInterval(refresh,2000);

function clearSatellite(){
 [satellite,footprint,direction].forEach(layer=>map.removeLayer(layer));
 lastPoint=null;lastHeading=null;
 document.getElementById('azNeedle').setAttribute('visibility','hidden');
 document.getElementById('elNeedle').setAttribute('visibility','hidden');
 document.getElementById('azText').textContent='Az --°';
 document.getElementById('elText').textContent='El --°';
}
function save(){try{sessionStorage.setItem(storageKey,JSON.stringify({passName:selectedPass?.querySelector('.satellite-toggle').dataset.satellite,passAos:selectedPass?.querySelector('.countdown').dataset.aosMs}));}catch(e){}}
document.querySelectorAll('.satellite-toggle').forEach(input=>input.addEventListener('change',()=>{if(!input.checked)return;selectedPass=input.closest('.pass-row');syncTarget();save();refresh();}));
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
new ResizeObserver(()=>{
 map.invalidateSize({pan:false});
 map.setView([settings.observerLat,settings.observerLon],3,{animate:false});
}).observe(document.getElementById('satellite-map'));
clearSatellite();refresh();
})();

