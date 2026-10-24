class PredictiveSearch extends HTMLElement {
  connectedCallback() {
    this.input = this.querySelector('input[type="search"]');
    this.results = this.querySelector('[data-predictive-search]');
    this.input.addEventListener('input', () => this.onChange());
  }
  onChange() {
    const term = this.input.value.trim();
    if (!term) { this.results.innerHTML = ''; return; }
    fetch(`/search/suggest?q=${encodeURIComponent(term)}&section_id=predictive-search`)
      .then((r) => r.text())
      .then((html) => { this.results.innerHTML = html; });
  }
}
customElements.define('predictive-search', PredictiveSearch);
