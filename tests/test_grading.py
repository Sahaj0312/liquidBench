from liquidbench.grading import matches_card

PRODUCT = {"title": "A & B", "vendor": " Vendor ", "available": False}
VALID = (
    "<article class='product-card'><h2>A &amp; B</h2>\n"
    "<p class='vendor'>Vendor</p><span class='availability'>Sold out</span></article>"
)


def test_dom_accepts_quote_and_whitespace_variants():
    assert matches_card("\n" + VALID + "\n", PRODUCT)
    assert matches_card("<!-- ordinary comment -->" + VALID, PRODUCT)
    assert matches_card(VALID.replace("class='product-card'", "class=' product-card  '"), PRODUCT)


def test_injection_and_extra_attributes_rejected():
    assert not matches_card(VALID.replace("A &amp; B", "<script>A & B</script>"), PRODUCT)
    assert not matches_card(VALID.replace("<h2>", '<h2 onclick="alert(1)">'), PRODUCT)
    assert not matches_card(VALID + "<img src=x>", PRODUCT)


def test_required_fallback_and_vendor_omission():
    html = (
        '<article class="product-card"><h2>Untitled product</h2>'
        '<span class="availability">In stock</span></article>'
    )
    assert matches_card(html, {"title": None, "vendor": " \t ", "available": True})
    assert not matches_card(html, PRODUCT)


def test_malformed_or_duplicate_structure_rejected():
    assert not matches_card(VALID.replace("</h2>", "</p>"), PRODUCT)
    assert not matches_card(VALID + VALID, PRODUCT)
    assert not matches_card(VALID.replace("<h2>", '<h2 class="x" class="y">'), PRODUCT)


def test_malformed_declarations_and_bare_duplicate_attributes_do_not_crash():
    assert not matches_card("<![nonsense]>" + VALID, PRODUCT)
    assert not matches_card(
        VALID.replace("class='product-card'", "class class='product-card'"), PRODUCT
    )
