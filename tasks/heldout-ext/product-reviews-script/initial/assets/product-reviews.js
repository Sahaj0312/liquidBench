document.querySelectorAll('.review-card').forEach((card) => {
  card.addEventListener('click', () => card.classList.toggle('review-card--expanded'));
});
