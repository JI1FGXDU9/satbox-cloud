(() => {
  const {serverTime, timezoneName} = window.satboxClock;
  const started = performance.now();
  const clockFormat = new Intl.DateTimeFormat('ja-JP', {timeZone: timezoneName, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'});
  const gmtFormat = new Intl.DateTimeFormat('ja-JP', {timeZone:'UTC',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const modeKey='satbox-time-mode';
  let mode='local';try{mode=localStorage.getItem(modeKey)==='gmt'?'gmt':'local';}catch(e){}
  function showTimes(){
    const format=new Intl.DateTimeFormat('ja-JP',{timeZone:mode==='gmt'?'UTC':timezoneName,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
    document.querySelectorAll('.pass-time').forEach(el=>{el.textContent=format.format(new Date(el.dateTime));});
    document.querySelectorAll('.time-mode').forEach(el=>{el.setAttribute('aria-current',String(el.dataset.mode===mode));});
    document.querySelectorAll('[data-time-kind]').forEach(el=>{el.textContent=el.dataset.timeKind+(window.satboxLanguage?.language==='en'?' time':'タイム')+' ('+(mode==='gmt'?'GMT':'LOCAL')+')';});
  }
  document.querySelectorAll('.time-mode').forEach(el=>el.addEventListener('click',event=>{event.preventDefault();mode=el.dataset.mode;try{localStorage.setItem(modeKey,mode);}catch(e){}showTimes();}));
  showTimes();
  function tick() {
    const nowMs = serverTime + performance.now() - started;
    let count = 0;
    document.querySelectorAll('.countdown').forEach(el => {
      const aos = Number(el.dataset.aosMs), los = Number(el.dataset.losMs);
      const row = el.closest('tr');
      row.hidden = nowMs >= los;
      const active = aos <= nowMs && nowMs < los;
      row.classList.toggle('pass-active', active);
      if (row.hidden) return;
      count++;
      const remaining = Math.max(0, Math.ceil(((active ? los : aos) - nowMs) / 1000));
      const hours = Math.floor(remaining / 3600);
      const minutes = Math.floor(remaining % 3600 / 60);
      const seconds = remaining % 60;
      const time = [hours, minutes, seconds].map(n => String(n).padStart(2, '0')).join(':');
      el.textContent = (active ? 'LOSまで ' : '') + time;
    });
    document.getElementById('clock').textContent = clockFormat.format(new Date(nowMs));
    document.getElementById('gmt-clock').textContent = gmtFormat.format(new Date(nowMs));
    document.getElementById('pass-count').textContent = count + '件';
  }
  function refresh() {
    // Finish an announcement before replacing the document.
    if (window.speechSynthesis?.speaking || window.speechSynthesis?.pending) {
      setTimeout(refresh, 1000); return;
    }
    location.reload();
  }
  tick(); setInterval(tick, 1000); setTimeout(refresh, 60000);
})();
