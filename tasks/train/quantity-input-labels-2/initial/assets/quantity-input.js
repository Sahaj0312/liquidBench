document.querySelectorAll('.quantity').forEach(function (el) {
  var input = el.querySelector('.quantity__input');
  el.addEventListener('click', function (e) {
    var btn = e.target.closest('.quantity__button');
    if (!btn) return;
    var v = parseInt(input.value, 10) || 1;
    input.value = btn.name === 'plus' ? v + 1 : Math.max(1, v - 1);
  });
});
