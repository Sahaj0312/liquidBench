class QuantityInput extends HTMLElement {
  connectedCallback() {
    this.input = this.querySelector('input');
    this.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      b.name === 'plus' ? this.input.stepUp() : this.input.stepDown();
    }));
  }
}
customElements.define('quantity-input', QuantityInput);
