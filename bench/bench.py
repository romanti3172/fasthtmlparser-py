"""Benchmarks of fasthtmlparser against selectolax (lexbor), lxml, parsel and BeautifulSoup on the same pages as
the .NET, Go and Rust benchmarks. Every library must extract the same records first.

    python bench/bench.py            # the table
    python bench/bench.py --check    # the records only
"""

import platform
import statistics
import sys
import timeit
from pathlib import Path

import lxml.html
import parsel
from bs4 import BeautifulSoup
from selectolax.lexbor import LexborHTMLParser

import fasthtmlparser as fh

DATA = Path(__file__).parent.parent / "testdata"
quotes = (DATA / "quotes" / "page1.html").read_text(encoding="utf-8")
laptops = (DATA / "webscraper" / "laptops.html").read_text(encoding="utf-8")
books = (DATA / "books" / "index.html").read_text(encoding="utf-8")
PAGES = [
    ("quotes, 11 KB", quotes),
    ("laptops, 38 KB", laptops),
    ("books, 51 KB", books),
    ("books x10, 510 KB", books * 10),
    ("books without </li> </p>", books.replace("</li>", "").replace("</p>", "")),
]


def last_word(s):
    return s.rsplit(" ", 1)[-1]


# ----- books: 20 x (title, price, rating) -----

def books_fh_find(page):
    return [
        (pod.find("h3").find("a").attr("title"), pod.find("p", class_="price_color").text,
         last_word(pod.find("p", class_="star-rating").attr("class")))
        for pod in fh.parse(page).find_all("article", class_="product_pod")
    ]


PODS, TITLE, PRICE, RATING = (fh.CssQuery(s) for s in ("article.product_pod", "h3 a", "p.price_color", "p.star-rating"))


def books_fh_css(page):
    return [
        (TITLE.first(pod).attr("title"), PRICE.first(pod).text, last_word(RATING.first(pod).attr("class")))
        for pod in PODS.all(fh.parse(page))
    ]


XPODS, XTITLE, XPRICE, XRATING = (fh.XPathQuery(x) for x in (
    "//article[contains(concat(' ', @class, ' '), ' product_pod ')]", ".//h3/a/@title",
    ".//p[contains(concat(' ', @class, ' '), ' price_color ')]",
    ".//p[contains(concat(' ', @class, ' '), ' star-rating ')]/@class"))


def books_fh_xpath(page):
    return [
        (XTITLE.value(pod), XPRICE.value(pod), last_word(XRATING.value(pod)))
        for pod in XPODS.nodes(fh.parse(page))
    ]


def books_selectolax(page):
    return [
        (pod.css_first("h3 a").attributes["title"], pod.css_first("p.price_color").text(strip=True),
         last_word(pod.css_first("p.star-rating").attributes["class"]))
        for pod in LexborHTMLParser(page).css("article.product_pod")
    ]


def books_lxml_xpath(page):
    return [
        (pod.xpath(".//h3/a/@title")[0],
         pod.xpath("string(.//p[contains(concat(' ', @class, ' '), ' price_color ')])").strip(),
         last_word(pod.xpath(".//p[contains(concat(' ', @class, ' '), ' star-rating ')]/@class")[0]))
        for pod in lxml.html.fromstring(page).xpath("//article[contains(concat(' ', @class, ' '), ' product_pod ')]")
    ]


def books_parsel(page):
    return [
        (pod.css("h3 a::attr(title)").get(), pod.css("p.price_color::text").get().strip(),
         last_word(pod.css("p.star-rating::attr(class)").get()))
        for pod in parsel.Selector(text=page).css("article.product_pod")
    ]


def books_bs4(page, parser):
    return [
        (pod.select_one("h3 a")["title"], pod.select_one("p.price_color").get_text(strip=True),
         pod.select_one("p.star-rating")["class"][-1])
        for pod in BeautifulSoup(page, parser).select("article.product_pod")
    ]


# ----- quotes: 10 x (text, author, tags) -----

def quotes_fh(page):
    return [
        (q.find("span", class_="text").text, q.find("small", class_="author").text,
         ",".join(a.text for a in q.find_all("a", class_="tag")))
        for q in fh.parse(page).find_all("div", class_="quote")
    ]


def quotes_selectolax(page):
    return [
        (q.css_first("span.text").text(strip=True), q.css_first("small.author").text(strip=True),
         ",".join(a.text(strip=True) for a in q.css("a.tag")))
        for q in LexborHTMLParser(page).css("div.quote")
    ]


def quotes_parsel(page):
    return [
        (q.css("span.text::text").get(), q.css("small.author::text").get(), ",".join(q.css("a.tag::text").getall()))
        for q in parsel.Selector(text=page).css("div.quote")
    ]


def quotes_bs4(page):
    return [
        (q.select_one("span.text").get_text(strip=True), q.select_one("small.author").get_text(strip=True),
         ",".join(a.get_text(strip=True) for a in q.select("a.tag")))
        for q in BeautifulSoup(page, "lxml").select("div.quote")
    ]


PARSERS = [
    ("fasthtmlparser", fh.parse),
    ("selectolax (lexbor)", LexborHTMLParser),
    ("lxml", lxml.html.fromstring),
    ("parsel (lxml)", lambda p: parsel.Selector(text=p)),
    ("BeautifulSoup (lxml)", lambda p: BeautifulSoup(p, "lxml")),
    ("BeautifulSoup (html.parser)", lambda p: BeautifulSoup(p, "html.parser")),
]

BOOKS = [
    ("fasthtmlparser find", books_fh_find),
    ("fasthtmlparser CSS", books_fh_css),
    ("fasthtmlparser XPath", books_fh_xpath),
    ("selectolax CSS", books_selectolax),
    ("lxml XPath", books_lxml_xpath),
    ("parsel CSS", books_parsel),
    ("BeautifulSoup (lxml) CSS", lambda p: books_bs4(p, "lxml")),
]

QUOTES = [
    ("fasthtmlparser find", quotes_fh),
    ("selectolax CSS", quotes_selectolax),
    ("parsel CSS", quotes_parsel),
    ("BeautifulSoup (lxml) CSS", quotes_bs4),
]


def check():
    expected = books_fh_find(books)
    assert len(expected) == 20, expected
    for name, f in BOOKS:
        assert f(books) == expected, name
    expected_quotes = quotes_fh(quotes)
    assert len(expected_quotes) == 10
    for name, f in QUOTES:
        assert f(quotes) == expected_quotes, name
    print(expected[0], expected_quotes[0][1])


def measure(f, arg):
    """The median time per call of five rounds, in microseconds."""
    timer = timeit.Timer(lambda: f(arg))
    number, _ = timer.autorange()
    return statistics.median(timer.repeat(5, number)) / number * 1e6


def main():
    check()
    if "--check" in sys.argv:
        return
    print(f"\nPython {platform.python_version()}, {platform.system()}, {platform.processor()}\n")
    print("| page | " + " | ".join(n for n, _ in PARSERS) + " |")
    print("|---|" + "---:|" * len(PARSERS))
    for page_name, page in PAGES:
        cells = [f"{measure(p, page):,.0f} μs" for _, p in PARSERS]
        print(f"| {page_name} | " + " | ".join(cells) + " |")
    for title, tasks, page in (("20 books", BOOKS, books), ("10 quotes", QUOTES, quotes)):
        print(f"\n| scrape {title} | time |\n|---|---:|")
        for name, f in tasks:
            print(f"| {name} | {measure(f, page):,.0f} μs |")


if __name__ == "__main__":
    main()
