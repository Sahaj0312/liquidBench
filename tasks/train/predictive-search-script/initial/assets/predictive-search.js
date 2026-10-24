class PredictiveSearch extends HTMLElement {
  connectedCallback() {
    this.status = this.querySelector('.predictive-search__status');
  }
}
customElements.define('predictive-search', PredictiveSearch);
