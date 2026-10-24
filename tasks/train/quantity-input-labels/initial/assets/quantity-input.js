class QuantityInput extends HTMLElement {
  connectedCallback() {
    this.input = this.querySelector('input');
    this.querySelectorAll('button').forEach((button) =>
      button.addEventListener('click', (event) => {
        event.preventDefault();
        button.name === 'plus' ? this.input.stepUp() : this.input.stepDown();
        this.input.dispatchEvent(new Event('change', { bubbles: true }));
      })
    );
  }
}
customElements.define('quantity-input', QuantityInput);
