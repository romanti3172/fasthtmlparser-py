import gc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import fasthtmlparser as fh

PAGE = """<html><body>
<div id="main" class="Card big">
  <h1>Title &amp; more</h1>
  <ul><li class="item"><a href="/p/1?a=1&amp;b=2" title="One">one</a><li class="item last">two</ul>
  <p>Contact: <a href="mailto:me@example.com">mail</a> <a href="tel:+1-555">call</a></p>
  <my-widget data-x="5">custom</my-widget>
  <!-- a comment -->
</div></body></html>"""


@pytest.fixture
def doc():
    return fh.parse(PAGE, url="https://example.com/catalog/")


def test_document(doc):
    assert doc.url == "https://example.com/catalog/"
    assert doc.source == PAGE
    assert len(doc) == len(list(doc))
    assert doc[0].name == "html" and doc[-1].name == "!--"
    with pytest.raises(IndexError):
        doc[len(doc)]
    assert repr(doc).startswith("<Document")
    assert fh.Document("<p>x</p>")[0].text == "x"


def test_find(doc):
    div = doc.find("div", id="main")
    assert div.has_class("card") and div.matches("DIV", class_="big")
    assert [li.text for li in div.find_all("li", class_="item")] == ["one", "two"]
    assert doc.find("a", attr=("title", "One")).text == "one"
    assert doc.find("h1", text="Title & more") is not None
    assert doc.find("h1", text_starts_with="Title") is not None
    assert doc.find("my-widget").attr("data-x") == "5"
    assert doc.find("li", class_="last").find_previous_sibling("li").text == "one"
    assert doc.find("a").find_parent("div").attr("id") == "main"
    assert doc.find("h1").find_next("li").text == "one"
    assert doc.find("nothing") is None and doc.find_all("nothing") == []
    assert doc.find(id="main", class_=None) is not None  # None criteria are left out
    with pytest.raises(TypeError, match="klass"):
        doc.find("a", klass="x")
    with pytest.raises(TypeError):
        doc.find("a", attr="title")


def test_reading(doc):
    a = doc.css_first("li a")
    assert a.attrs == {"href": "/p/1?a=1&b=2", "title": "One"}
    assert a.attr_raw("href") == "/p/1?a=1&amp;b=2"
    assert a.href == "https://example.com/p/1?a=1&b=2"
    assert a.href_from("https://other.org/x/") == "https://other.org/p/1?a=1&b=2"
    assert a.source == 'a href="/p/1?a=1&amp;b=2" title="One"'
    assert doc.find("h1").body == "Title &amp; more"
    assert doc.find("h1").outer_html == "<h1>Title &amp; more</h1>"
    links = doc.css("p a")
    assert (links[0].mailto, links[1].tel) == ("me@example.com", "+1-555")
    assert doc.find("ul").text_line_breaks == "one\ntwo"
    assert doc.find("ul").children == doc.css("ul > li")
    assert doc.find("h1").next_sibling.name == "ul"
    start, end = doc.find("h1").pos
    assert PAGE.encode()[start:end + 1] == b"<h1>Title &amp; more</h1>"


def test_css_and_xpath(doc):
    assert doc.css("li:last-child")[0].text == "two"
    ul = doc.find("ul")
    assert [n.text for n in ul.css("> li")] == ["one", "two"]
    assert ul.css_first("a").text == "one"
    assert doc.find("li").css_matches("ul > li.item")
    assert doc.xpath_value("count(//li)") == "2"
    assert doc.xpath_values("//a/@href")[1:] == ["mailto:me@example.com", "tel:+1-555"]
    assert doc.xpath_first("//li[2]").text == "two"
    assert ul.xpath_values("li") == ["one", "two"]
    assert ul.xpath_value("string(li[1])") == "one"
    assert doc.xpath_value("//nothing") == ""
    assert doc.xpath_values("//comment()") == [" a comment "]


def test_compiled_queries(doc):
    q = fh.XPathQuery("//li")
    assert q.expression == "//li" and q.is_node_set
    assert q.values(doc) == ["one", "two"] and q.value(doc.find("ul")) == "one"
    assert fh.XPathQuery("//nothing").value(doc) is None
    c = fh.CssQuery("li.item")
    assert c.selector == "li.item" and len(c.all(doc)) == 2 and c.first(doc.find("ul")).text == "one"
    assert c.matches(doc.find("li"))
    with pytest.raises(TypeError):
        c.all("not a document")


def test_errors(doc):
    with pytest.raises(fh.CssSelectorError):
        doc.css("a[")
    with pytest.raises(fh.CssSelectorError):
        fh.CssQuery("::before")
    with pytest.raises(fh.XPathError):
        doc.xpath("//a[")
    with pytest.raises(fh.XPathError, match="xpath_value"):
        doc.xpath("count(//a)")
    with pytest.raises(fh.XPathError):
        doc.xpath_value("sum(1)")  # fails when it runs
    assert issubclass(fh.CssSelectorError, ValueError) and issubclass(fh.XPathError, ValueError)
    with pytest.raises(TypeError):
        fh.parse(123)


def test_nodes_keep_the_document_alive():
    node = fh.parse("<div><b>kept</b></div>").find("b")
    gc.collect()
    assert node.text == "kept" and node.parent.name == "div"


def test_equality_and_hash(doc):
    assert doc.find("ul") == doc.css_first("ul") and doc.find("ul") != doc.find("div")
    assert len({doc.find("ul"), doc.css_first("ul"), doc.find("div")}) == 2
    assert doc.find("ul") != fh.parse(PAGE).find("ul")  # another document


def test_bytes_and_helpers():
    assert fh.parse("<p>café</p>".encode()).find("p").text == "café"
    assert fh.parse(b"<p>\xff</p>").find("p").text == "�"
    assert fh.decode_html("&lt;&copy;&#x41;") == "<©A"
    assert fh.html_to_text("<p>a <b>b</b></p><script>x</script>") == "a b"
    assert fh.html_to_text_line_breaks("<p>a</p><p>b</p>") == "a\n\nb"


def test_threads():
    page = (Path(__file__).parent.parent / "testdata" / "books" / "index.html").read_text(encoding="utf-8")

    def titles(_):
        return [a.attr("title") for a in fh.parse(page).css("article.product_pod h3 a")]

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(titles, range(64)))
    assert all(r == results[0] for r in results) and len(results[0]) == 20
