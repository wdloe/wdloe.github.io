const form = document.querySelector('.filters');
if (form) {
  form.hidden = false;
  const search = document.querySelector('#publication-search');
  const type = document.querySelector('#publication-type');
  const year = document.querySelector('#publication-year');
  const publications = [...document.querySelectorAll('.publication')];
  const update = () => {
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const item of publications) {
      const matches = (!type.value || item.dataset.category === type.value)
        && (!year.value || item.dataset.year === year.value)
        && item.textContent.toLocaleLowerCase().includes(query);
      item.hidden = !matches;
      if (matches) count++;
    }
    document.querySelector('#result-count').textContent = `${count} publication${count === 1 ? '' : 's'}`;
    document.querySelector('#empty-results').hidden = count !== 0;
  };
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  form.addEventListener('reset', () => setTimeout(update, 0));
}
