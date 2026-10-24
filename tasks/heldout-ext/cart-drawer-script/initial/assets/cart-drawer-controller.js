class CartDrawer extends HTMLElement {
  connectedCallback() {
    this.setAttribute('role', 'dialog');
  }
}
customElements.define('cart-drawer', CartDrawer);
