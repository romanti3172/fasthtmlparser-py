# fasthtmlparser

[![CI](https://github.com/romanti3172/fasthtmlparser-py/actions/workflows/ci.yml/badge.svg)](https://github.com/romanti3172/fasthtmlparser-py/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fasthtmlparser.svg)](https://pypi.org/project/fasthtmlparser/)

**Website:** [fasthtmlparser.com](https://fasthtmlparser.com): try the parser on any page, documentation and every language.

A fast HTML / XML parser for scraping, with **XPath 1.0** and **CSS selectors**: Python bindings of the
[Rust port](https://github.com/romanti3172/fasthtmlparser-rs) of
[z3l.FastHtmlParser](https://github.com/romanti3172/z3l.FastHtmlParser). It is built for extracting data, not for
building a DOM: a page becomes a flat list of tags that hold only positions in the source; text, attributes and
entities are read when you ask for them. Parsing is **5–7x faster than selectolax** and **20x faster than lxml**
(see below).

```
pip install fasthtmlparser
```

Python 3.10 or later. Wheels for Linux (glibc and musl), Windows and macOS, x86-64 and ARM64; no dependencies.

```python
import fasthtmlparser as fh

doc = fh.parse(html, url="https://books.toscrape.com/")  # str or bytes; url resolves relative links

# CSS selectors, as querySelectorAll / querySelector
for pod in doc.css("article.product_pod"):
    title = pod.css_first("h3 a").attr("title")
    price = pod.css_first("p.price_color").text
    link = pod.css_first("h3 a").href          # absolute URL
ul.css("> li")                                 # the children of ul

# XPath 1.0
doc.xpath("//div[@class='card']//span[@class='price']")   # tags
doc.xpath_values("//a[contains(@href, '/product/')]/@href")
doc.xpath_value("//dt[.='Price']/following-sibling::dd[1]")
doc.xpath_value("count(//table//tr)")          # "12"

# compile once, reuse on any number of pages and threads
TITLES = fh.XPathQuery("//article//h3/a/@title")
TITLES.values(doc)
PRICES = fh.CssQuery("p.price_color")
PRICES.all(doc)

# search by name (any name, case-insensitive) and criteria, as in BeautifulSoup
pod = doc.find("article", class_="product_pod")
pod.find("p", class_="price_color").text
doc.find_all("a", attr=("rel", "next"))
doc.find("dt", text="Price").find_next_sibling("dd").text
doc.find("my-widget", id_starts_with="w-")
# criteria: class_, id, attr=(name, value), text, id_starts_with, text_starts_with, body, body_starts_with, source

# reading a tag
tag.name, tag.depth, tag.index, tag.pos   # pos: byte offsets in the UTF-8 source
tag.text              # visible text, entities decoded, whitespace collapsed
tag.text_line_breaks  # <br> and block elements → new lines, <p> and headings → paragraphs
tag.attr("data-src")  # decoded value, "" when missing; attr_raw(): as written
tag.attrs             # {"href": "...", "class": "..."}
tag.href, tag.src     # absolute URLs; href_from(base) / src_from(base)
tag.mailto, tag.tel   # the address of a mailto: link, the number of a tel: link
tag.body, tag.outer_html, tag.source   # inner HTML, the whole element, the opening tag

# navigation
tag.parent, tag.children, tag.next_sibling, tag.previous_sibling, tag.next, tag.previous
tag.find_parent("table"), tag.find_next("h2"), tag.text_after_until("br")

# the whole document
len(doc), doc[0], doc[-1], list(doc)    # every tag, comments included
```

A missing tag is `None`, a missing value is `""`. An invalid selector raises `fh.CssSelectorError`, an invalid XPath
expression `fh.XPathError` (both are `ValueError`s); `xpath()` on an expression that gives a number or string raises
`XPathError` too (use `xpath_value`). The string methods compile and cache queries. A `Node` keeps its document alive,
nodes compare equal when they are the same tag, and are hashable. The GIL is released while a page is parsed, and
documents and compiled queries can be shared between threads. Type stubs are included.

CSS: type, `*`, `#id`, `.class`, attribute selectors with all operators and the `i` / `s` flags, the four combinators,
selector lists, `:first-child`, `:last-child`, `:only-child`, `:*-of-type`, `:nth-child(An+B [of S])` and its relatives,
`:not()`, `:is()`, `:where()`, `:has()`, `:empty`, `:root`, `:scope`, `:link`, `:checked`, `:disabled`, `:enabled`,
`:required`, `:optional`, `:contains("text")`. XPath: all axes except namespace, predicates, `|`, the operators and all
XPath 1.0 functions, plus `ends-with()`, `lower-case()`, `upper-case()`. HTML rules apply: names are case-insensitive,
the string-value of an element is its visible text, attribute values and text are decoded. HTML5 optional end tags
(`<li>`, `<p>`, `<td>`, `<option>` without end tags) give the same elements as in a browser; there is no full HTML5
tree construction (no implied `<tbody>` or `<html>`), and documents are read-only.

## Same results as the .NET version

`tests/test_conformance.py` runs the conformance data of the Rust crate through the Python package: on 117 pages
(fixtures, broken markup, cut-off pages, CR LF, 600-deep nesting, ...) every tag's name, position, text, text with line
breaks, attributes, navigation and links, and 569 XPath / CSS queries on the document and from three tags of each
page, must give exactly what z3l.FastHtmlParser (.NET) gives. So the bindings are checked as well as the parser.

## Benchmarks

`python bench/bench.py` (Python 3.14, AMD Ryzen 7 3800X, Windows; [`bench-results.md`](bench-results.md)). Every
library must extract the same records before anything is timed.

Parse a page:

| Page | fasthtmlparser | selectolax (lexbor) | lxml | parsel | BeautifulSoup (lxml) |
|---|---:|---:|---:|---:|---:|
| quotes, 11 KB | 19 μs | 95 μs | 495 μs | 499 μs | 4,368 μs |
| laptops, 38 KB | 53 μs | 306 μs | 1,379 μs | 1,420 μs | 12,192 μs |
| books, 51 KB | 65 μs | 424 μs | 1,547 μs | 1,616 μs | 15,273 μs |
| books x10, 510 KB | 652 μs | 3,531 μs | 13,873 μs | 14,886 μs | 15,083 μs\* |
| books without `</li>` `</p>` | 59 μs | 221 μs | 1,460 μs | 1,593 μs | 14,393 μs |

\* BeautifulSoup with lxml stops at the first `</html>`: it finds 20 of the 200 books on that page.

Scrape a page: parse and extract the records (books: 20 × title, price, rating; quotes: 10 × text, author, tags).

| Task | fasthtmlparser | selectolax | lxml / parsel | BeautifulSoup (lxml) |
|---|---:|---:|---:|---:|
| 20 books, CSS | 126 μs | 587 μs | parsel 2,543 μs | 19,006 μs |
| 20 books, XPath | 217 μs | | lxml 2,715 μs | |
| 20 books, `find` | 152 μs | | | |
| 10 quotes | 74 μs | 271 μs | parsel 1,030 μs | 5,984 μs |

## Build from source

Needs Rust 1.85+ and [maturin](https://www.maturin.rs/):

```
python -m venv .venv && .venv/Scripts/activate   # or . .venv/bin/activate
pip install maturin pytest
maturin develop --release
pytest
```

## Other languages

The same parser is available for:

| Language | Package | Source |
|---|---|---|
| C# (.NET 9 and 10) | [z3l.FastHtmlParser](https://www.nuget.org/packages/z3l.FastHtmlParser) on NuGet | [romanti3172/z3l.FastHtmlParser](https://github.com/romanti3172/z3l.FastHtmlParser) |
| Go | `github.com/romanti3172/fasthtmlparser` | [romanti3172/fasthtmlparser](https://github.com/romanti3172/fasthtmlparser) |
| Rust | [fasthtmlparser](https://crates.io/crates/fasthtmlparser) on crates.io | [romanti3172/fasthtmlparser-rs](https://github.com/romanti3172/fasthtmlparser-rs) |
| JavaScript / TypeScript | [z3l-fasthtmlparser](https://www.npmjs.com/package/z3l-fasthtmlparser) on npm | [romanti3172/fasthtmlparser-js](https://github.com/romanti3172/fasthtmlparser-js) |
| Python | [fasthtmlparser](https://pypi.org/project/fasthtmlparser/) on PyPI | [romanti3172/fasthtmlparser-py](https://github.com/romanti3172/fasthtmlparser-py) |

## License

Same terms as z3l.FastHtmlParser (see LICENSE.md): free for companies under USD 1M annual revenue and under 100
people, a commercial license above that. This is source-available, not an OSI open-source license.
