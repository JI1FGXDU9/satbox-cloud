(() => {
  const boxes = Array.from(document.querySelectorAll('.satellite-toggle'));
  const status = document.getElementById('selection-status');
  boxes.forEach(box => box.addEventListener('change', async () => {
    const name = box.dataset.satellite, enabled = box.checked;
    const previous = new Map(boxes.map(b => [b, b === box ? !enabled : b.checked]));
    boxes.forEach(b => {if (b.dataset.satellite === name) b.checked = enabled; b.disabled = true;});
    status.hidden = false; status.textContent = name + 'の通知設定を保存中…';
    try {
      const response = await fetch(window.satboxSelection.url, {method: 'POST', credentials: 'same-origin',
        body: new URLSearchParams({csrf_token: window.satboxSelection.csrfToken, satellite_name: name, enabled: enabled ? '1' : '0'})});
      if (response.redirected) throw new Error('ログインし直してから設定してください。');
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '保存に失敗しました。');
      const count = document.getElementById('notification-queue-count');
      if (count) count.textContent = String(result.queue_count);
      document.querySelectorAll('.pass-row').forEach(row => {
        const name = row.querySelector('.satellite-toggle').dataset.satellite;
        const aos = Number(row.querySelector('.countdown').dataset.aosMs);
        const planned = (result.planned_passes || []).some(p => p.name === name && Math.abs(p.aos_ms - aos) < 120000);
        row.querySelector('.notification-plan-status').textContent = planned ? '予定（未送信）' : '';
        const empty = row.querySelector('.notification-no-plan');
        if (empty) empty.hidden = planned;
      });
      const selected = new Set(result.enabled_satellites);
      boxes.forEach(b => {b.checked = selected.has(b.dataset.satellite);});
      status.textContent = name + 'の通知を' + (selected.has(name) ? 'ON' : 'OFF') + 'に保存しました。' +
        (result.queue_ready ? '通知予定 ' + result.queue_count + '件。' : '一部の衛星を計算できません。通知予定を確認してください。');
    } catch (error) {
      boxes.forEach(b => {b.checked = previous.get(b);});
      status.textContent = error.message + '一覧を開き直して保存状態を確認してください。';
    } finally {boxes.forEach(b => {b.disabled = false;});}
  }));
})();
