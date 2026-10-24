document.addEventListener('DOMContentLoaded', function () {
  var reply = document.querySelector('.comment-labels__reply');
  if (reply) { reply.setAttribute('aria-live', 'polite'); }
});
