class SearchForm extends HTMLElement {
  connectedCallback() {
    this.input = this.querySelector('input[type="search"]');
    this.querySelector('.search-form__reset')?.addEventListener('click', () => this.input.focus());
  }
}
customElements.define('search-form', SearchForm);
