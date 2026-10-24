document.querySelectorAll('form.search').forEach(function (form) {
  form.addEventListener('reset', function () {
    form.querySelector('.search__input').focus();
  });
});
