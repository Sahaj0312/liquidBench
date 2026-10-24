class QuickView {
  constructor() {
    document.querySelectorAll('.quick-view-trigger').forEach((el) => {
      el.addEventListener('click', () => this.open(el.dataset.productHandle));
    });
  }
  open(handle) {
    const modal = document.querySelector('.quick-view-modal');
    if (modal) modal.hidden = false;
  }
}
new QuickView();
