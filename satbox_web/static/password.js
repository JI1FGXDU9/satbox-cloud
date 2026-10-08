document.querySelectorAll('.password-toggle').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.getAttribute('aria-controls'));
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(visible));
    const label = document.documentElement.lang === 'en' ? (visible ? 'Hide password' : 'Show password') : (visible ? 'パスワードを非表示' : 'パスワードを表示');
    button.setAttribute('aria-label', label);
    button.title = label;
    button.querySelector('.eye-slash').toggleAttribute('hidden', !visible);
  });
});
