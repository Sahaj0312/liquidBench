document.addEventListener('click', function (event) {
  if (event.target.closest('.lightbox__close')) {
    event.target.closest('.lightbox').hidden = true;
  }
});
