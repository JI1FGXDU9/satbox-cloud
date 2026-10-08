(() => {
  let language = 'ja';
  try { language = localStorage.getItem('satbox-language') === 'en' ? 'en' : 'ja'; } catch {}
  document.documentElement.lang = language;
  document.querySelectorAll('[data-ja][data-en]').forEach(el => { el.textContent = el.dataset[language]; });
  if (language !== 'en') return;
  const navigation={ 'Pass一覧':'Pass list','QTH設定':'QTH settings','衛星選択':'Satellite selection','通知予定':'Scheduled alerts','通知設定':'Alert settings','通知端末登録':'Notification devices','管理画面':'Administration','退会':'Delete account','ログアウト':'Log out' };
  document.querySelectorAll('nav a, nav button').forEach(el=>{const text=navigation[el.textContent.trim()];if(text)el.textContent=text;});
  document.querySelectorAll('.password-toggle').forEach(button => {
    const label = button.getAttribute('aria-pressed') === 'true' ? 'Hide password' : 'Show password';
    button.setAttribute('aria-label', label); button.title = label;
  });
  const messages = {
    '有効なメールアドレスを入力してください。': 'Enter a valid email address.',
    'ログインIDは英数字・_・.・-・/で3～64文字にしてください。': 'Login ID must contain 3–64 letters, digits, or _ . - /.',
    'パスワードは8～128文字にしてください。': 'Password must contain 8–128 characters.',
    '確認用パスワードが一致しません。': 'The passwords do not match.',
    'このログインIDは使用済みです。': 'This login ID is already in use.',
    'コールサインは英数字・/・-で2～32文字にしてください。': 'Callsign must contain 2–32 letters, digits, / or -.',
    '緯度・経度・高度を数値で入力してください。': 'Enter numbers for latitude, longitude, and altitude.',
    '緯度・経度・高度は有限の数値にしてください。': 'Latitude, longitude, and altitude must be finite numbers.',
    '緯度は-90～90度、経度は-180～180度です。': 'Latitude must be between −90 and 90°, and longitude between −180 and 180°.',
    '高度は-500～10000 mで指定してください。': 'Altitude must be between −500 and 10,000 m.',
    '有効なタイムゾーン地域名を指定してください。例: Asia/Manila': 'Enter a valid time zone region, such as Asia/Manila.',
    'グリッドロケーターは4・6・8文字で指定してください。例: PJ18WF': 'Grid locator must contain 4, 6, or 8 characters, such as PJ18WF.',
    'グリッドロケーターが緯度・経度と一致しません。空欄にすると自動計算します。': 'The grid locator does not match your coordinates. Leave it blank to calculate it automatically.',
    '予測範囲は24時間または48時間です。': 'Prediction period must be 24 or 48 hours.'
  };
  const error = document.getElementById('register-error');
  if (error) error.textContent = messages[error.textContent.trim()] || error.textContent;
})();
