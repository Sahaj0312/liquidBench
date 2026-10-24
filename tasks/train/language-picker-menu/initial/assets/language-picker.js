document.querySelectorAll('.language-picker a').forEach(function (link) {
  link.addEventListener('click', function () {
    document.documentElement.setAttribute('data-switching-locale', 'true');
  });
});
