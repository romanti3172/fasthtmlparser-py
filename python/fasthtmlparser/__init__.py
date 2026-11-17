"""Fast HTML / XML parser for scraping with XPath 1.0 and CSS selectors.

A Python package over the Rust port of z3l.FastHtmlParser: a page becomes a flat list of tags that hold only
positions in the source; text, attributes and entities are read when they are asked for.

    >>> import fasthtmlparser as fh
    >>> doc = fh.parse('<ul><li class="a">one<li>two</ul>')
    >>> [li.text for li in doc.css("li")]
    ['one', 'two']
    >>> doc.xpath_value("count(//li)")
    '2'
"""

from ._fasthtmlparser import (
    CssQuery,
    CssSelectorError,
    Document,
    Node,
    XPathError,
    XPathQuery,
    decode_html,
    html_to_text,
    html_to_text_line_breaks,
    parse,
)

__all__ = [
    "CssQuery",
    "CssSelectorError",
    "Document",
    "Node",
    "XPathError",
    "XPathQuery",
    "decode_html",
    "html_to_text",
    "html_to_text_line_breaks",
    "parse",
]
