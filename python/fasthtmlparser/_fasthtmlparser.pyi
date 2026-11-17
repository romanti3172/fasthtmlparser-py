from collections.abc import Iterator
from typing import final

class CssSelectorError(ValueError):
    """An invalid CSS selector."""

class XPathError(ValueError):
    """An invalid XPath expression, or one that cannot be evaluated."""

def parse(html: str | bytes, url: str | None = None) -> Document:
    """Parses an HTML or XML page. Bytes are read as UTF-8 (invalid sequences become U+FFFD).

    With url, relative links (Node.href, Node.src) are resolved against it. The GIL is released while parsing.
    """

def decode_html(text: str) -> str:
    """Decodes the character references of a text (CR LF and a lone CR become LF)."""

def html_to_text(html: str) -> str:
    """The visible text of an HTML fragment: tags removed, whitespace collapsed, entities decoded."""

def html_to_text_line_breaks(html: str) -> str:
    """The text of an HTML fragment with the visible line structure kept."""

@final
class Document:
    """A parsed HTML or XML page: a flat list of tags in document order.

    `len(doc)`, `doc[i]` (negative indexes too) and iteration give the tags, comments included.
    """

    def __new__(cls, html: str | bytes, url: str | None = None) -> Document: ...
    @property
    def url(self) -> str:
        """The page URL given to parse(), or ""."""
    @property
    def source(self) -> str:
        """The page source."""
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> Node: ...
    def __iter__(self) -> Iterator[Node]: ...
    def find(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> Node | None:
        """The first tag that matches: by name (any name, case-insensitive) and the criteria; or None.

        class_: one of the space-separated classes (case-insensitive); attr: (name, decoded value);
        text: the visible text; body: the inner HTML; source: the opening tag without '<' and '>'.
        """
    def find_all(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> list[Node]:
        """All tags that match, in document order."""
    def css(self, selector: str) -> list[Node]:
        """The tags that match the CSS selector (querySelectorAll). Raises CssSelectorError on an invalid one."""
    def css_first(self, selector: str) -> Node | None:
        """The first tag that matches the CSS selector (querySelector), or None."""
    def xpath(self, expression: str) -> list[Node]:
        """The tags the XPath 1.0 expression selects. Raises XPathError on an invalid expression or one that
        gives a number, string or boolean (use xpath_value)."""
    def xpath_first(self, expression: str) -> Node | None:
        """The first tag the XPath expression selects, or None."""
    def xpath_values(self, expression: str) -> list[str]:
        """The values the XPath expression selects: decoded attributes, text(), visible text of tags, or the
        result of count(), sum(), string(), ..."""
    def xpath_value(self, expression: str) -> str:
        """The first value the XPath expression selects, or ""."""

@final
class Node:
    """One tag of a document. Positions are byte offsets into the UTF-8 source.

    Nodes compare equal when they are the same tag of the same document, and are hashable.
    """

    @property
    def name(self) -> str:
        """The lower-case tag name ("div", "!--" for comments, "custom-tag", ...)."""
    @property
    def index(self) -> int:
        """The position of the tag in the document."""
    @property
    def depth(self) -> int:
        """The nesting depth: 0 for top-level tags."""
    @property
    def pos(self) -> tuple[int, int]:
        """The byte offsets of the opening '<' and of the last '>' in the UTF-8 source."""
    @property
    def text(self) -> str:
        """The visible text: tags, comments, script and style removed, entities decoded, whitespace collapsed."""
    @property
    def text_line_breaks(self) -> str:
        """The text with the visible line structure kept: <br> and block elements give new lines, p and
        headings paragraphs."""
    @property
    def body(self) -> str:
        """The inner HTML (trimmed); "" for tags that are not closed."""
    @property
    def outer_html(self) -> str:
        """The source of the whole element; "" for tags that are not closed."""
    @property
    def source(self) -> str:
        """The opening tag without '<' and '>': the name and the attributes."""
    @property
    def attrs(self) -> dict[str, str]:
        """The attributes as a dict of decoded values, names in lower case (the first of a repeated name wins)."""
    def attr(self, name: str) -> str:
        """The decoded value of the first attribute with the name (case-insensitive); "" when it is missing."""
    def attr_raw(self, name: str) -> str:
        """The value of the attribute as written in the source."""
    def has_class(self, class_: str) -> bool:
        """Whether one of the space-separated classes equals class_ (case-insensitive)."""
    @property
    def href(self) -> str:
        """The link a browser follows: href decoded and made absolute against the page URL. An empty or missing
        href gives the page URL."""
    @property
    def src(self) -> str:
        """src decoded and made absolute against the page URL."""
    def href_from(self, base_url: str) -> str:
        """href resolved against base_url instead of the page URL."""
    def src_from(self, base_url: str) -> str:
        """src resolved against base_url instead of the page URL."""
    @property
    def mailto(self) -> str:
        """The address of a mailto: link, or ""."""
    @property
    def tel(self) -> str:
        """The number of a tel: link, or ""."""
    @property
    def text_after(self) -> str:
        """The source text right after the tag up to the next '<'."""
    @property
    def parent(self) -> Node | None:
        """The enclosing tag, or None."""
    @property
    def children(self) -> list[Node]:
        """The direct children."""
    @property
    def has_children(self) -> bool:
        """Whether another tag starts inside this one."""
    @property
    def next(self) -> Node | None:
        """The tag that follows in document order (the first child, if there is one), or None."""
    @property
    def previous(self) -> Node | None:
        """The tag before this one in document order, or None."""
    @property
    def next_sibling(self) -> Node | None:
        """The next tag at the same level inside the same parent, or None."""
    @property
    def previous_sibling(self) -> Node | None:
        """The previous tag at the same level inside the same parent, or None."""
    def find(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> Node | None:
        """The first tag inside this one that matches, or None."""
    def find_all(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> list[Node]:
        """All tags inside this one that match."""
    def matches(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> bool:
        """Whether this tag matches."""
    def find_parent(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> Node | None:
        """The nearest enclosing tag that matches, or None."""
    def find_next(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> Node | None:
        """The first tag after the end of this one that matches (tags inside it are skipped), or None."""
    def find_next_sibling(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> Node | None:
        """The next sibling that matches, or None."""
    def find_previous_sibling(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> Node | None:
        """The nearest previous sibling that matches, or None."""
    def text_after_until(
        self,
        name: str | None = None,
        *,
        class_: str | None = None,
        id: str | None = None,
        attr: tuple[str, str] | None = None,
        text: str | None = None,
        id_starts_with: str | None = None,
        text_starts_with: str | None = None,
        body: str | None = None,
        body_starts_with: str | None = None,
        source: str | None = None,
    ) -> str:
        """The source between the end of this tag and the next tag that matches; "" when there is none."""
    def css(self, selector: str) -> list[Node]:
        """The tags inside this one that match the CSS selector; it may start with '>' for the children."""
    def css_first(self, selector: str) -> Node | None:
        """The first tag inside this one that matches the CSS selector, or None."""
    def css_matches(self, selector: str) -> bool:
        """Whether this tag matches the CSS selector (element.matches())."""
    def xpath(self, expression: str) -> list[Node]:
        """The tags the XPath expression selects, relative paths starting at this tag."""
    def xpath_first(self, expression: str) -> Node | None:
        """The first tag the XPath expression selects from this tag, or None."""
    def xpath_values(self, expression: str) -> list[str]:
        """The values the XPath expression selects from this tag."""
    def xpath_value(self, expression: str) -> str:
        """The first value the XPath expression selects from this tag, or ""."""
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

@final
class CssQuery:
    """A compiled CSS selector: compile once, use on any number of pages and threads."""

    def __new__(cls, selector: str) -> CssQuery: ...
    @property
    def selector(self) -> str: ...
    def all(self, target: Document | Node, /) -> list[Node]:
        """The matching tags in a document, or inside a node."""
    def first(self, target: Document | Node, /) -> Node | None:
        """The first matching tag in a document, or inside a node, or None."""
    def matches(self, node: Node, /) -> bool:
        """Whether the tag matches (element.matches())."""

@final
class XPathQuery:
    """A compiled XPath 1.0 expression: compile once, use on any number of pages and threads."""

    def __new__(cls, expression: str) -> XPathQuery: ...
    @property
    def expression(self) -> str: ...
    @property
    def is_node_set(self) -> bool:
        """Whether the expression gives tags (a node-set), not a number, string or boolean."""
    def nodes(self, target: Document | Node, /) -> list[Node]:
        """The selected tags, evaluated on a document or from a node."""
    def values(self, target: Document | Node, /) -> list[str]:
        """The values of the selected nodes, or the result of the expression as one value."""
    def value(self, target: Document | Node, /) -> str | None:
        """The value of the first selected node, or the result of the expression; None when it selects nothing."""
