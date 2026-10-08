(() => {
  const form = document.getElementById('login-form');
  const status = document.getElementById('login-status');
  const button = form.querySelector('[type="submit"]');
  let busy = false;
  let language='ja';
  try { language=localStorage.getItem('satbox-language')==='en'?'en':'ja'; } catch {}
  const error=document.getElementById('login-error');
  const originalError=error?.textContent.trim();
  const errors={
    'ログインIDまたはパスワードが違います。':'Incorrect login ID or password.',
    'ログイン試行が多すぎます。15分後に再試行してください。':'Too many login attempts. Please try again in 15 minutes.',
    'ログイン画面の情報を更新しました。もう一度ログインしてください。ブラウザーを閉じる必要はありません。':'The login form has been refreshed. Please log in again. You do not need to close your browser.'
  };
  function applyLanguage(value){
    language=value;document.documentElement.lang=value;
    document.querySelectorAll('[data-ja][data-en]').forEach(el=>{el.textContent=el.dataset[value];});
    document.querySelectorAll('[data-aria-ja]').forEach(el=>{el.setAttribute('aria-label',value==='en'?el.dataset.ariaEn:el.dataset.ariaJa);});
    document.querySelectorAll('[data-language]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.language===value)));
    document.querySelectorAll('.password-toggle').forEach(el=>{const visible=el.getAttribute('aria-pressed')==='true';const text=value==='en'?(visible?'Hide password':'Show password'):(visible?'パスワードを非表示':'パスワードを表示');el.title=text;el.setAttribute('aria-label',text);});
    if(error)error.textContent=value==='en'?(errors[originalError]||originalError):originalError;
    if(!status.hidden)status.textContent=prepareError();
    try{localStorage.setItem('satbox-language',value);}catch{}
  }
  function prepareError(){return language==='en'?'Unable to prepare login. Check your connection and click Log in again.':'ログインの準備ができませんでした。通信状態を確認して、もう一度ログインを押してください。';}
  document.querySelectorAll('[data-language]').forEach(el=>el.addEventListener('click',()=>applyLanguage(el.dataset.language)));
  applyLanguage(language);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    busy = true; button.disabled = true; status.hidden = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(window.satboxLogin.tokenUrl, {
        credentials:'same-origin', cache:'no-store', signal:controller.signal
      });
      if (!response.ok || response.redirected) throw new Error('画面の更新に失敗しました。');
      const data = await response.json();
      if (typeof data.csrf_token !== 'string' || !data.csrf_token) throw new Error('画面の更新に失敗しました。');
      form.elements.csrf_token.value = data.csrf_token;
      // Native submit avoids re-entering this handler; passwords remain POST-only.
      HTMLFormElement.prototype.submit.call(form);
    } catch {
      status.hidden = false;
      status.textContent = prepareError();
      busy = false; button.disabled = false;
    } finally { clearTimeout(timeout); }
  });
  window.addEventListener('pageshow', () => { busy = false; button.disabled = false; });
})();
