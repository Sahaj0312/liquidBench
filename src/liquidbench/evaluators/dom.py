"""Small HTML fragment checker for explicitly constrained task markup."""

from html.parser import HTMLParser


class FragmentParser(HTMLParser):
    def __init__(self, allowed_tags):
        super().__init__(convert_charrefs=True)
        self.allowed_tags = set(allowed_tags)
        self.root = {"tag": "root", "attrs": [], "children": [], "text": ""}
        self.stack = [self.root]
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed_tags:
            self.invalid = True
        if len({name for name, _ in attrs}) != len(attrs):
            self.invalid = True
        attrs = [
            (
                name,
                " ".join(sorted(set(value.split()))) if name == "class" and value else value or "",
            )
            for name, value in attrs
        ]
        node = {"tag": tag, "attrs": sorted(attrs), "children": [], "text": ""}
        self.stack[-1]["children"].append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1]["tag"] != tag:
            self.invalid = True
        else:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.invalid = True

    def handle_data(self, data):
        self.stack[-1]["text"] += data

    def handle_decl(self, decl):
        self.invalid = True

    def parse_html_declaration(self, index):
        # Newer Python versions treat some invalid declarations as comments.
        # Reject declarations consistently, without rejecting ordinary comments.
        if not self.rawdata.startswith("<!--", index):
            self.invalid = True
        return super().parse_html_declaration(index)


def fragment(html, allowed_tags):
    parser = FragmentParser(allowed_tags)
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError):
        return None
    if parser.invalid or len(parser.stack) != 1 or parser.root["text"].strip():
        return None
    return parser.root["children"]


def element(tag, text="", attrs=None, children=None):
    return {
        "tag": tag,
        "attrs": sorted((attrs or {}).items()),
        "text": text,
        "children": children or [],
    }
