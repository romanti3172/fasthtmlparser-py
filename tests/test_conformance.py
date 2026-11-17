"""Conformance with z3l.FastHtmlParser (.NET) through the Python package: the expected output in
testdata/conformance comes from the .NET version for the same pages (see the Rust crate), so this checks the
bindings as well as the parser."""

import hashlib
import json
from pathlib import Path

import pytest

import fasthtmlparser as fh

DATA = Path(__file__).parent.parent / "testdata" / "conformance"
PAGE_URL = "https://Example.com:443/catalog/page-1.html?sort=asc#top"
PAGES = sorted(p.stem for p in (DATA / "input").glob("*.html"))
# the .NET result depends on the order of an unstable sort there (see the Rust crate)
KNOWN_DIFFERENCES = {("snip039", "//div/node()")}


def index(n):
    return -1 if n is None else n.index


@pytest.mark.parametrize("page", PAGES)
def test_tags(page):
    source = (DATA / "input" / f"{page}.html").read_bytes()
    expected = json.loads((DATA / "expected" / f"{page}.json").read_text(encoding="utf-8"))
    doc = fh.parse(source, url=PAGE_URL)
    assert len(doc) == len(expected)
    for n, e in zip(doc, expected):
        start, end = n.pos
        got = {
            "name": n.name, "parent": index(n.parent), "depth": n.depth, "start": start, "end": end,
            "text": n.text, "textLineBreaks": n.text_line_breaks, "source": n.source,
            "next": index(n.next), "previous": index(n.previous),
            "nextSibling": index(n.next_sibling), "previousSibling": index(n.previous_sibling),
            "children": ",".join(str(c.index) for c in n.children),
            "href": n.href, "src": n.src, "mailto": n.mailto, "tel": n.tel, "textAfter": n.text_after,
        }
        want = {k: e[k] for k in got}
        assert got == want, f"[{n.index}]"
        for attr, value in e["attrs"].items():
            assert n.attr(attr) == value, f"[{n.index}] @{attr}"


def test_compile():
    expected = json.loads((DATA / "expected" / "queries" / "compile.json").read_text(encoding="utf-8"))
    for kind, compile_, error in (("xpath", fh.XPathQuery, fh.XPathError), ("css", fh.CssQuery, fh.CssSelectorError)):
        for query, want in expected[kind].items():
            try:
                compile_(query)
                got = "ok"
            except error:
                got = "error"
            assert got == want, f"{kind} {query!r}"


def result(values):
    """[count, hash] of the values, or "throws" when the evaluation fails (.NET throws)."""
    try:
        v = values()
    except fh.XPathError:
        return "throws"
    return [str(len(v)), hashlib.sha256("\x01".join(v).encode()).hexdigest()[:16]]


def indexes(nodes):
    return [str(n.index) for n in nodes]


@pytest.mark.parametrize("page", [p for p in PAGES])
def test_queries(page):
    expected = json.loads((DATA / "expected" / "queries" / f"{page}.json").read_text(encoding="utf-8"))
    doc = fh.parse((DATA / "input" / f"{page}.html").read_bytes())
    scopes = [doc[s] for s in expected["scopes"]]
    problems = []

    def check(what, want, got):
        if got != want and len(problems) < 10:
            problems.append(f"{what}\n  python: {str(got)[:300]}\n  .net:   {str(want)[:300]}")

    for x, want in expected["xpath"].items():
        if (page, x) in KNOWN_DIFFERENCES:
            continue
        q = fh.XPathQuery(x)
        check(f"XPath tags {x}", want["tags"], result(lambda: indexes(q.nodes(doc))))
        check(f"XPath values {x}", want["values"], result(lambda: q.values(doc)))
        check(f"XPath value {x}", want["value"], result(lambda: [v if (v := q.value(doc)) is not None else "<null>"]))
        check(f"XPath scoped {x}", want["scoped"],
              [result(lambda: indexes(q.nodes(s)) + ["|"] + q.values(s)) for s in scopes])

    for c, want in expected["css"].items():
        q = fh.CssQuery(c)
        check(f"CSS all {c}", want["all"], result(lambda: indexes(q.all(doc))))
        check(f"CSS first {c}", want["first"], result(lambda: [str(f.index) if (f := q.first(doc)) else "<null>"]))
        check(f"CSS matches {c}", want["matches"], result(lambda: indexes([n for n in doc if q.matches(n)])))
        check(f"CSS scoped {c}", want["scoped"], [result(lambda: indexes(q.all(s))) for s in scopes])

    assert not problems, "\n".join(problems)
