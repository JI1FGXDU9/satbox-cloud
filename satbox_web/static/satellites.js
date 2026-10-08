(() => {
  const available = document.getElementById('available-satellites');
  const selected = document.getElementById('selected-satellites');
  const search = document.getElementById('satellite-search');
  const count = document.getElementById('selected-count');
  function update() {
    const query = search.value.trim().toLocaleLowerCase();
    Array.from(available.options).forEach(o => {o.hidden = !o.value.toLocaleLowerCase().includes(query);});
    count.textContent = String(selected.options.length);
  }
  document.querySelectorAll('[data-move]').forEach(button => button.addEventListener('click', () => {
    const action = button.dataset.move;
    const adding = action.endsWith('add');
    const source = adding ? available : selected, target = adding ? selected : available;
    const options = Array.from(action.startsWith('all-') ? source.options : source.selectedOptions);
    options.forEach(option => {option.selected = false; option.hidden = false; target.add(option);});
    if (!adding) Array.from(available.options).sort((a,b)=>a.value.localeCompare(b.value)).forEach(o=>available.add(o));
    update();
  }));
  search.addEventListener('input',update);
  document.getElementById('satellite-selection-form').addEventListener('submit', () => {
    Array.from(selected.options).forEach(option => {option.selected = true;});
  });
  update();
})();
