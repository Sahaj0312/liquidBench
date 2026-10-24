class PredictiveSearch extends HTMLElement {
  connectedCallback() {
    this.results = this.querySelector('.predictive-search__results');
  }
}

if (!customElements.get('predictive-search')) {
  customElements.define('predictive-search', PredictiveSearch);
}
