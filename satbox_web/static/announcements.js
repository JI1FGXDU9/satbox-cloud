(() => {
  const english=window.satboxLanguage?.language==='en';
  const status = document.getElementById('speech-status');
  function notice(text) { status.hidden = false; status.textContent = text; }
  if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
    notice('このブラウザーは音声アナウンスに対応していません。'); return;
  }
  const engine = window.speechSynthesis;
  const letterNames = {
    A:'エー', B:'ビー', C:'シー', D:'ディー', E:'イー', F:'エフ',
    G:'ジー', H:'エイチ', I:'アイ', J:'ジェー', K:'ケー', L:'エル',
    M:'エム', N:'エヌ', O:'オー', P:'ピー', Q:'キュー', R:'アール',
    S:'エス', T:'ティー', U:'ユー', V:'ブイ', W:'ダブリュー',
    X:'エックス', Y:'ワイ', Z:'ゼット'
  };
  function numberReading(value) {
    const units = ['', 'いち', 'に', 'さん', 'よん', 'ご', 'ろく', 'なな', 'はち', 'きゅう'];
    let number = Number(value), text = '';
    if (number === 0) return 'ゼロ';
    const thousands = Math.floor(number / 1000);
    if (thousands) text += ({1:'せん',3:'さんぜん',8:'はっせん'})[thousands] || units[thousands]+'せん';
    number %= 1000;
    const hundreds = Math.floor(number / 100);
    if (hundreds) text += ({1:'ひゃく',3:'さんびゃく',6:'ろっぴゃく',8:'はっぴゃく'})[hundreds] || units[hundreds]+'ひゃく';
    number %= 100;
    const tens = Math.floor(number / 10);
    if (tens) text += (tens === 1 ? '' : units[tens])+'じゅう';
    return text+units[number % 10];
  }
  function satelliteReading(name) {
    if(english)return String(name).replace(/-/g, ' ');
    const match = String(name).match(/^([A-Z]+)(?:[- ]?(\d{1,4}))?$/);
    if (!match) return name;
    return Array.from(match[1], letter => letterNames[letter]).join('') +
      (match[2] === undefined ? '' : '、'+numberReading(match[2]));
  }
  const {userId, leadMinutes} = window.satboxSpeech;
  const storageKey = 'satbox-speech-' + userId;
  const started = performance.now();
  const now = () => window.satboxClock.serverTime + performance.now() - started;
  let previous = now() - 3000;
  let history = [];
  try { history = JSON.parse(sessionStorage.getItem(storageKey) || '[]'); } catch {}
  if (!Array.isArray(history)) history = [];
  history = history.filter(e => e && Number.isFinite(e.aos) && Math.abs(e.aos-now()) < 172800000);
  function save() { try { sessionStorage.setItem(storageKey, JSON.stringify(history)); } catch {} }
  let voices = [];
  const loadVoices = () => { voices = engine.getVoices(); };
  loadVoices(); engine.addEventListener('voiceschanged',loadVoices);
  const utterances = new Set();
  let blocked = null;
  function speak(text, deadline) {
    const message = new SpeechSynthesisUtterance(text);
    message.lang = english?'en-US':'ja-JP'; message.rate = 1; message.pitch = 1; message.volume = 1;
    const japanese = voices.filter(v => v.lang?.toLowerCase().startsWith(english?'en':'ja'));
    message.voice = japanese.find(v => v.name.includes('Haruka')) || japanese[0] || null;
    utterances.add(message);
    message.onend = () => { utterances.delete(message); };
    message.onstart = () => { status.hidden = true; blocked = null; };
    message.onerror = event => {
      utterances.delete(message);
      if (event.error === 'not-allowed') {
        blocked = {text,deadline};
        notice('音声がブラウザーに制限されました。ページ内をクリック／タップすると再試行します。');
      } else notice('音声アナウンスを再生できませんでした：' + (event.error || '不明'));
    };
    // Queue overlapping satellites instead of cancelling the preceding speech.
    engine.speak(message);
  }
  document.addEventListener('click', () => {
    if (!blocked) return;
    const retry = blocked; blocked = null;
    if (now()-retry.deadline <= 30000) speak(retry.text,retry.deadline);
  });
  function tick() {
    const current = now();
    const events = [];
    document.querySelectorAll('.pass-row').forEach(row => {
      const checkbox = row.querySelector('.satellite-toggle');
      if (!checkbox.checked || checkbox.disabled) return;
      const counter = row.querySelector('.countdown');
      const aos = Number(counter.dataset.aosMs), los = Number(counter.dataset.losMs);
      if (current >= los) return;
      const name = checkbox.dataset.satellite;
      const spokenName = satelliteReading(name);
      if (leadMinutes > 0 && row.dataset.preAllowed === '1') {
        const remainingSeconds = Math.max(0, leadMinutes*60-30);
        const minutes = Math.floor(remainingSeconds/60), seconds = remainingSeconds%60;
        const remainingText = (minutes ? minutes+'分' : '')+(seconds ? seconds+'秒' : '');
        events.push({name,aos,kind:'advance',at:Number(row.dataset.announcementMs),
          text:english?`${spokenName}. AOS in ${minutes} minutes ${seconds} seconds. Maximum elevation ${Math.round(Number(row.dataset.maxel))} degrees.`:`${spokenName}、AOSまで${remainingText}。最大仰角${Math.round(Number(row.dataset.maxel))}度です。`});
      }
      if (row.dataset.risingAllowed === '1') events.push({name,aos,kind:'rising',at:aos,text:english?`Satellite ${spokenName} rising`:`サテライト ${spokenName} ライジング`});
    });
    events.sort((a,b) => a.at-b.at);
    for (const event of events) {
      // No catch-up burst after tab suspension or opening an old pass.
      if (!(previous < event.at && event.at <= current && current-event.at <= 3000)) continue;
      if (history.some(e => e.name === event.name && e.kind === event.kind && Math.abs(e.aos-event.aos) < 120000)) continue;
      history.push({name:event.name,kind:event.kind,aos:event.aos}); save();
      speak(event.text,event.at);
    }
    previous = current;
  }
  tick(); setInterval(tick,1000);
})();
