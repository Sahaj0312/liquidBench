document.querySelectorAll('.search-form').forEach(function (form) {
  var input = form.querySelector('input[type=search]');
  form.addEventListener('reset', function () { setTimeout(function () { input.focus(); }, 0); });
});
