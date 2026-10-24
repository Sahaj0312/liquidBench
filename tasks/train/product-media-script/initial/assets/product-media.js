class ProductMedia extends HTMLElement {
  connectedCallback() { this.querySelectorAll('.product-media__trigger').forEach((b) => b.addEventListener('click', () => this.open(b))); }
  open(button) { this.dispatchEvent(new CustomEvent('media:open', { detail: button })); }
}
customElements.define('product-media', ProductMedia);
