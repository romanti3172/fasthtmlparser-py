//! Python bindings of fasthtmlparser (the Rust port of z3l.FastHtmlParser).
//!
//! A Python `Document` holds the parsed page in an `Arc`; a `Node` holds the same `Arc` and the tag index, so nodes
//! stay valid as long as any of them is alive, and no Python object is borrowed while Rust code runs.

use std::collections::HashMap;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::{Arc, LazyLock, Mutex};

use fasthtmlparser as fh;
use pyo3::create_exception;
use pyo3::exceptions::{PyIndexError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyString};

create_exception!(
    fasthtmlparser,
    CssSelectorError,
    PyValueError,
    "An invalid CSS selector."
);
create_exception!(
    fasthtmlparser,
    XPathError,
    PyValueError,
    "An invalid XPath expression, or one that cannot be evaluated."
);

// ----- query caches: the string methods compile a query once -----

type Cache<Q> = LazyLock<Mutex<HashMap<String, Arc<Q>>>>;

static CSS_CACHE: Cache<fh::CssQuery> = LazyLock::new(Default::default);
static XPATH_CACHE: Cache<fh::XPathQuery> = LazyLock::new(Default::default);

fn cached<Q, E: std::fmt::Display>(
    cache: &Mutex<HashMap<String, Arc<Q>>>,
    key: &str,
    compile: impl FnOnce(&str) -> Result<Q, E>,
) -> Result<Arc<Q>, String> {
    if let Some(q) = cache.lock().unwrap_or_else(|e| e.into_inner()).get(key) {
        return Ok(q.clone());
    }
    let q = Arc::new(compile(key).map_err(|e| e.to_string())?);
    let mut c = cache.lock().unwrap_or_else(|e| e.into_inner());
    if c.len() >= 1024 {
        c.clear(); // dynamically built queries must not grow the cache forever
    }
    c.insert(key.to_string(), q.clone());
    Ok(q)
}

fn css(selector: &str) -> PyResult<Arc<fh::CssQuery>> {
    cached(&CSS_CACHE, selector, fh::CssQuery::compile).map_err(CssSelectorError::new_err)
}

fn xpath(expression: &str) -> PyResult<Arc<fh::XPathQuery>> {
    cached(&XPATH_CACHE, expression, fh::XPathQuery::compile).map_err(XPathError::new_err)
}

/// Runs an XPath evaluation; the few expressions that fail at run time (sum() of a string) panic in Rust.
fn evaluate<T>(f: impl FnOnce() -> T) -> PyResult<T> {
    catch_unwind(AssertUnwindSafe(f)).map_err(|e| {
        let message = e
            .downcast_ref::<String>()
            .cloned()
            .or_else(|| e.downcast_ref::<&str>().map(|s| s.to_string()))
            .unwrap_or_else(|| "the XPath expression cannot be evaluated".into());
        XPathError::new_err(message)
    })
}

fn nodes_of(doc: &Arc<fh::Document>, nodes: Vec<fh::Node<'_>>) -> Vec<Node> {
    nodes
        .into_iter()
        .map(|n| Node {
            doc: doc.clone(),
            index: n.index() as u32,
        })
        .collect()
}

fn node_of(doc: &Arc<fh::Document>, node: Option<fh::Node<'_>>) -> Option<Node> {
    node.map(|n| Node {
        doc: doc.clone(),
        index: n.index() as u32,
    })
}

// ----- search criteria (keyword arguments) -----

/// The criteria of find(), find_all(), matches() and the like, as owned strings a Query can borrow.
struct Criteria {
    name: Option<String>,
    class: Option<String>,
    id: Option<String>,
    attr: Option<(String, String)>,
    text: Option<String>,
    id_starts_with: Option<String>,
    text_starts_with: Option<String>,
    body: Option<String>,
    body_starts_with: Option<String>,
    source: Option<String>,
}

impl Criteria {
    fn query(&self) -> fh::Query<'_> {
        let mut q = match &self.name {
            Some(n) => fh::by_name(n),
            None => fh::any(),
        };
        if let Some(v) = &self.class {
            q = q.class(v);
        }
        if let Some(v) = &self.id {
            q = q.id(v);
        }
        if let Some((n, v)) = &self.attr {
            q = q.attr(n, v);
        }
        if let Some(v) = &self.text {
            q = q.text(v);
        }
        if let Some(v) = &self.id_starts_with {
            q = q.id_starts_with(v);
        }
        if let Some(v) = &self.text_starts_with {
            q = q.text_starts_with(v);
        }
        if let Some(v) = &self.body {
            q = q.body(v);
        }
        if let Some(v) = &self.body_starts_with {
            q = q.body_starts_with(v);
        }
        if let Some(v) = &self.source {
            q = q.source(v);
        }
        q
    }
}

const CRITERIA: &str =
    "class_, id, attr, text, id_starts_with, text_starts_with, body, body_starts_with, source";

/// The search criteria from the name and the keyword arguments; an unknown keyword is a TypeError.
fn criteria(name: Option<String>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Criteria> {
    let mut c = Criteria {
        name,
        class: None,
        id: None,
        attr: None,
        text: None,
        id_starts_with: None,
        text_starts_with: None,
        body: None,
        body_starts_with: None,
        source: None,
    };
    let Some(kwargs) = kwargs else { return Ok(c) };
    for (key, value) in kwargs.iter() {
        let key: String = key.extract()?;
        if value.is_none() {
            continue;
        }
        if key == "attr" {
            c.attr = Some(
                value
                    .extract()
                    .map_err(|_| PyTypeError::new_err("attr= takes a (name, value) tuple"))?,
            );
            continue;
        }
        let v: String = value
            .extract()
            .map_err(|_| PyTypeError::new_err(format!("{key}= takes a str")))?;
        let slot = match key.as_str() {
            "class_" => &mut c.class,
            "id" => &mut c.id,
            "text" => &mut c.text,
            "id_starts_with" => &mut c.id_starts_with,
            "text_starts_with" => &mut c.text_starts_with,
            "body" => &mut c.body,
            "body_starts_with" => &mut c.body_starts_with,
            "source" => &mut c.source,
            _ => {
                return Err(PyTypeError::new_err(format!(
                    "unexpected keyword argument '{key}' (the criteria are {CRITERIA})"
                )))
            }
        };
        *slot = Some(v);
    }
    Ok(c)
}

// ----- Document -----

/// A parsed HTML or XML page: a flat list of tags in document order.
#[pyclass(frozen, module = "fasthtmlparser")]
struct Document {
    doc: Arc<fh::Document>,
}

/// Parses an HTML or XML page. Bytes are read as UTF-8 (invalid sequences become U+FFFD). With url, relative
/// links (Node.href, Node.src) are resolved against it.
#[pyfunction]
#[pyo3(signature = (html, url = None))]
fn parse(py: Python<'_>, html: &Bound<'_, PyAny>, url: Option<&str>) -> PyResult<Document> {
    let source: String = if let Ok(s) = html.cast::<PyString>() {
        s.to_str()?.to_owned()
    } else if let Ok(b) = html.cast::<PyBytes>() {
        String::from_utf8_lossy(b.as_bytes()).into_owned()
    } else {
        return Err(PyTypeError::new_err("parse() takes a str or bytes"));
    };
    let url = url.map(str::to_owned);
    // the page is parsed without the GIL: other threads run meanwhile
    let doc = py.detach(move || match url {
        Some(u) => fh::Document::parse_with_url(source, &u),
        None => fh::Document::parse(source),
    });
    Ok(Document { doc: Arc::new(doc) })
}

#[pymethods]
impl Document {
    #[new]
    #[pyo3(signature = (html, url = None))]
    fn new(py: Python<'_>, html: &Bound<'_, PyAny>, url: Option<&str>) -> PyResult<Document> {
        parse(py, html, url)
    }

    /// The page URL given to parse(), or "".
    #[getter]
    fn url(&self) -> &str {
        self.doc.url()
    }

    /// The page source.
    #[getter]
    fn source(&self) -> &str {
        self.doc.source()
    }

    fn __len__(&self) -> usize {
        self.doc.len()
    }

    fn __getitem__(&self, index: isize) -> PyResult<Node> {
        let len = self.doc.len() as isize;
        let i = if index < 0 { index + len } else { index };
        if i < 0 || i >= len {
            return Err(PyIndexError::new_err("tag index out of range"));
        }
        Ok(Node {
            doc: self.doc.clone(),
            index: i as u32,
        })
    }

    fn __iter__(&self) -> NodeIterator {
        NodeIterator {
            doc: self.doc.clone(),
            next: 0,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "<Document url={:?} tags={}>",
            self.doc.url(),
            self.doc.len()
        )
    }

    /// The first tag that matches: by name (any name, case-insensitive) and the keyword criteria; or None.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(node_of(&self.doc, self.doc.find(c.query())))
    }

    /// All tags that match, in document order.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find_all(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Vec<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(nodes_of(&self.doc, self.doc.find_all(c.query())))
    }

    /// The tags that match the CSS selector (querySelectorAll).
    fn css(&self, selector: &str) -> PyResult<Vec<Node>> {
        Ok(nodes_of(&self.doc, css(selector)?.all(&self.doc)))
    }

    /// The first tag that matches the CSS selector (querySelector), or None.
    fn css_first(&self, selector: &str) -> PyResult<Option<Node>> {
        Ok(node_of(&self.doc, css(selector)?.first(&self.doc)))
    }

    /// The tags the XPath expression selects.
    fn xpath(&self, expression: &str) -> PyResult<Vec<Node>> {
        let q = xpath(expression)?;
        check_node_set(&q)?;
        evaluate(|| nodes_of(&self.doc, q.nodes(&self.doc)))
    }

    /// The first tag the XPath expression selects, or None.
    fn xpath_first(&self, expression: &str) -> PyResult<Option<Node>> {
        Ok(self.xpath(expression)?.into_iter().next())
    }

    /// The values the XPath expression selects: decoded attributes, text(), visible text of tags, or the result
    /// of count(), sum(), string(), ...
    fn xpath_values(&self, expression: &str) -> PyResult<Vec<String>> {
        let q = xpath(expression)?;
        evaluate(|| q.values(&self.doc))
    }

    /// The first value the XPath expression selects, or "".
    fn xpath_value(&self, expression: &str) -> PyResult<String> {
        let q = xpath(expression)?;
        evaluate(|| q.value(&self.doc).unwrap_or_default())
    }
}

fn check_node_set(q: &fh::XPathQuery) -> PyResult<()> {
    if q.is_node_set() {
        Ok(())
    } else {
        Err(XPathError::new_err(format!(
            "the XPath {:?} gives a number, string or boolean, not tags; use xpath_value()",
            q.as_str()
        )))
    }
}

#[pyclass(module = "fasthtmlparser")]
struct NodeIterator {
    doc: Arc<fh::Document>,
    next: usize,
}

#[pymethods]
impl NodeIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self) -> Option<Node> {
        if self.next >= self.doc.len() {
            return None;
        }
        self.next += 1;
        Some(Node {
            doc: self.doc.clone(),
            index: self.next as u32 - 1,
        })
    }
}

// ----- Node -----

/// One tag of a document. Positions are byte offsets into the UTF-8 source.
#[pyclass(frozen, module = "fasthtmlparser")]
struct Node {
    doc: Arc<fh::Document>,
    index: u32,
}

impl Node {
    fn node(&self) -> fh::Node<'_> {
        self.doc.node(self.index as usize)
    }

    fn wrap(&self, n: Option<fh::Node<'_>>) -> Option<Node> {
        node_of(&self.doc, n)
    }
}

#[pymethods]
impl Node {
    /// The lower-case tag name ("div", "!--" for comments, "custom-tag", ...).
    #[getter]
    fn name(&self) -> &str {
        self.node().name()
    }

    /// The position of the tag in the document.
    #[getter]
    fn index(&self) -> usize {
        self.index as usize
    }

    /// The nesting depth: 0 for top-level tags.
    #[getter]
    fn depth(&self) -> usize {
        self.node().depth()
    }

    /// The byte offsets of the opening '<' and of the last '>' in the UTF-8 source.
    #[getter]
    fn pos(&self) -> (usize, usize) {
        self.node().pos()
    }

    /// The visible text with entities decoded and whitespace collapsed.
    #[getter]
    fn text(&self) -> String {
        self.node().text().into_owned()
    }

    /// The text with the visible line structure kept: <br> and block elements give new lines, p and headings
    /// paragraphs.
    #[getter]
    fn text_line_breaks(&self) -> String {
        self.node().text_line_breaks()
    }

    /// The inner HTML (trimmed); "" for tags that are not closed.
    #[getter]
    fn body(&self) -> &str {
        self.node().body()
    }

    /// The source of the whole element; "" for tags that are not closed.
    #[getter]
    fn outer_html(&self) -> &str {
        self.node().outer_html()
    }

    /// The opening tag without '<' and '>': the name and the attributes.
    #[getter]
    fn source(&self) -> &str {
        self.node().source()
    }

    /// The attributes as a dict of decoded values, names in lower case (the first one of a repeated name wins).
    #[getter]
    fn attrs<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        let n = self.node();
        for (name, _) in n.attrs() {
            let key = name.to_lowercase();
            if !d.contains(&key)? {
                d.set_item(&key, n.attr(name).as_ref())?;
            }
        }
        Ok(d)
    }

    /// The decoded value of the first attribute with the name (case-insensitive); "" when it is missing or empty.
    fn attr(&self, name: &str) -> String {
        self.node().attr(name).into_owned()
    }

    /// The value of the attribute as written in the source.
    fn attr_raw(&self, name: &str) -> &str {
        self.node().attr_raw(name)
    }

    /// Whether one of the space-separated classes equals class_ (case-insensitive).
    fn has_class(&self, class_: &str) -> bool {
        self.node().has_class(class_)
    }

    /// The link a browser follows: href decoded and made absolute against the page URL.
    #[getter]
    fn href(&self) -> String {
        self.node().href()
    }

    /// src decoded and made absolute against the page URL.
    #[getter]
    fn src(&self) -> String {
        self.node().src()
    }

    /// href resolved against base_url instead of the page URL.
    fn href_from(&self, base_url: &str) -> String {
        self.node().href_from(base_url)
    }

    /// src resolved against base_url instead of the page URL.
    fn src_from(&self, base_url: &str) -> String {
        self.node().src_from(base_url)
    }

    /// The address of a mailto: link, or "".
    #[getter]
    fn mailto(&self) -> String {
        self.node().href_mail_to()
    }

    /// The number of a tel: link, or "".
    #[getter]
    fn tel(&self) -> String {
        self.node().href_telephone()
    }

    /// The source text right after the tag up to the next '<'.
    #[getter]
    fn text_after(&self) -> &str {
        self.node().text_after_tag_until_next_one()
    }

    // ----- navigation -----

    /// The enclosing tag, or None.
    #[getter]
    fn parent(&self) -> Option<Node> {
        self.wrap(self.node().parent())
    }

    /// The direct children.
    #[getter]
    fn children(&self) -> Vec<Node> {
        nodes_of(&self.doc, self.node().children())
    }

    /// Whether another tag starts inside this one.
    #[getter]
    fn has_children(&self) -> bool {
        self.node().has_children()
    }

    /// The tag that follows in document order (the first child, if there is one), or None.
    #[getter]
    fn next(&self) -> Option<Node> {
        self.wrap(self.node().next())
    }

    /// The tag before this one in document order, or None.
    #[getter]
    fn previous(&self) -> Option<Node> {
        self.wrap(self.node().previous())
    }

    /// The next tag at the same level inside the same parent, or None.
    #[getter]
    fn next_sibling(&self) -> Option<Node> {
        self.wrap(self.node().next_sibling())
    }

    /// The previous tag at the same level inside the same parent, or None.
    #[getter]
    fn previous_sibling(&self) -> Option<Node> {
        self.wrap(self.node().previous_sibling())
    }

    // ----- search -----

    /// The first tag inside this one that matches, or None.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(self.wrap(self.node().find(c.query())))
    }

    /// All tags inside this one that match.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find_all(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Vec<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(nodes_of(&self.doc, self.node().find_all(c.query())))
    }

    /// Whether this tag matches.
    #[pyo3(signature = (name = None, **kwargs))]
    fn matches(&self, name: Option<String>, kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<bool> {
        let c = criteria(name, kwargs)?;
        Ok(self.node().is(c.query()))
    }

    /// The nearest enclosing tag that matches, or None.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find_parent(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(self.wrap(self.node().parent_matching(c.query())))
    }

    /// The first tag after the end of this one that matches (tags inside it are skipped), or None.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find_next(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(self.wrap(self.node().next_matching(c.query())))
    }

    /// The next sibling that matches, or None.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find_next_sibling(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(self.wrap(self.node().next_sibling_matching(c.query())))
    }

    /// The nearest previous sibling that matches, or None.
    #[pyo3(signature = (name = None, **kwargs))]
    fn find_previous_sibling(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Option<Node>> {
        let c = criteria(name, kwargs)?;
        Ok(self.wrap(self.node().previous_sibling_matching(c.query())))
    }

    /// The source between the end of this tag and the next tag that matches; "" when there is none.
    #[pyo3(signature = (name = None, **kwargs))]
    fn text_after_until(
        &self,
        name: Option<String>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<String> {
        let c = criteria(name, kwargs)?;
        Ok(self.node().text_after_until(c.query()).to_string())
    }

    /// The tags inside this one that match the CSS selector.
    fn css(&self, selector: &str) -> PyResult<Vec<Node>> {
        Ok(nodes_of(&self.doc, css(selector)?.all_in(self.node())))
    }

    /// The first tag inside this one that matches the CSS selector, or None.
    fn css_first(&self, selector: &str) -> PyResult<Option<Node>> {
        Ok(self.wrap(css(selector)?.first_in(self.node())))
    }

    /// Whether this tag matches the CSS selector (element.matches()).
    fn css_matches(&self, selector: &str) -> PyResult<bool> {
        Ok(css(selector)?.matches(self.node()))
    }

    /// The tags the XPath expression selects, relative paths starting at this tag.
    fn xpath(&self, expression: &str) -> PyResult<Vec<Node>> {
        let q = xpath(expression)?;
        check_node_set(&q)?;
        evaluate(|| nodes_of(&self.doc, q.nodes_from(self.node())))
    }

    /// The first tag the XPath expression selects from this tag, or None.
    fn xpath_first(&self, expression: &str) -> PyResult<Option<Node>> {
        Ok(self.xpath(expression)?.into_iter().next())
    }

    /// The values the XPath expression selects from this tag.
    fn xpath_values(&self, expression: &str) -> PyResult<Vec<String>> {
        let q = xpath(expression)?;
        evaluate(|| q.values_from(self.node()))
    }

    /// The first value the XPath expression selects from this tag, or "".
    fn xpath_value(&self, expression: &str) -> PyResult<String> {
        let q = xpath(expression)?;
        evaluate(|| q.value_from(self.node()).unwrap_or_default())
    }

    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        match other.cast::<Node>() {
            Ok(o) => {
                let o = o.get();
                Arc::ptr_eq(&self.doc, &o.doc) && self.index == o.index
            }
            Err(_) => false,
        }
    }

    fn __hash__(&self) -> u64 {
        (Arc::as_ptr(&self.doc) as u64) ^ ((self.index as u64) << 1)
    }

    fn __repr__(&self) -> String {
        let source = self.node().source();
        let short: String = source.chars().take(80).collect();
        let more = if short.len() < source.len() {
            "..."
        } else {
            ""
        };
        format!("<Node {} <{short}{more}>>", self.index)
    }
}

// ----- compiled queries -----

/// A target of a compiled query: a Document or a Node.
enum Target {
    Doc(Arc<fh::Document>),
    Node(Arc<fh::Document>, u32),
}

fn target(obj: &Bound<'_, PyAny>) -> PyResult<Target> {
    if let Ok(d) = obj.cast::<Document>() {
        return Ok(Target::Doc(d.get().doc.clone()));
    }
    if let Ok(n) = obj.cast::<Node>() {
        let n = n.get();
        return Ok(Target::Node(n.doc.clone(), n.index));
    }
    Err(PyTypeError::new_err("expected a Document or a Node"))
}

/// A compiled CSS selector: compile once, use on any number of pages and threads.
#[pyclass(frozen, module = "fasthtmlparser")]
struct CssQuery {
    q: Arc<fh::CssQuery>,
}

#[pymethods]
impl CssQuery {
    #[new]
    fn new(selector: &str) -> PyResult<CssQuery> {
        let q = fh::CssQuery::compile(selector)
            .map_err(|e| CssSelectorError::new_err(e.to_string()))?;
        Ok(CssQuery { q: Arc::new(q) })
    }

    /// The selector source.
    #[getter]
    fn selector(&self) -> &str {
        self.q.as_str()
    }

    /// The matching tags in a document, or inside a node.
    fn all(&self, target_: &Bound<'_, PyAny>) -> PyResult<Vec<Node>> {
        Ok(match target(target_)? {
            Target::Doc(d) => nodes_of(&d, self.q.all(&d)),
            Target::Node(d, i) => nodes_of(&d, self.q.all_in(d.node(i as usize))),
        })
    }

    /// The first matching tag in a document, or inside a node, or None.
    fn first(&self, target_: &Bound<'_, PyAny>) -> PyResult<Option<Node>> {
        Ok(match target(target_)? {
            Target::Doc(d) => node_of(&d, self.q.first(&d)),
            Target::Node(d, i) => node_of(&d, self.q.first_in(d.node(i as usize))),
        })
    }

    /// Whether the tag matches (element.matches()).
    fn matches(&self, node: &Bound<'_, Node>) -> bool {
        self.q.matches(node.get().node())
    }

    fn __repr__(&self) -> String {
        format!("CssQuery({:?})", self.q.as_str())
    }
}

/// A compiled XPath 1.0 expression: compile once, use on any number of pages and threads.
#[pyclass(frozen, module = "fasthtmlparser")]
struct XPathQuery {
    q: Arc<fh::XPathQuery>,
}

#[pymethods]
impl XPathQuery {
    #[new]
    fn new(expression: &str) -> PyResult<XPathQuery> {
        let q =
            fh::XPathQuery::compile(expression).map_err(|e| XPathError::new_err(e.to_string()))?;
        Ok(XPathQuery { q: Arc::new(q) })
    }

    /// The expression source.
    #[getter]
    fn expression(&self) -> &str {
        self.q.as_str()
    }

    /// Whether the expression gives tags (a node-set), not a number, string or boolean.
    #[getter]
    fn is_node_set(&self) -> bool {
        self.q.is_node_set()
    }

    /// The selected tags, evaluated on a document or from a node.
    fn nodes(&self, target_: &Bound<'_, PyAny>) -> PyResult<Vec<Node>> {
        check_node_set(&self.q)?;
        match target(target_)? {
            Target::Doc(d) => evaluate(|| nodes_of(&d, self.q.nodes(&d))),
            Target::Node(d, i) => evaluate(|| nodes_of(&d, self.q.nodes_from(d.node(i as usize)))),
        }
    }

    /// The values of the selected nodes, or the result of the expression as one value.
    fn values(&self, target_: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
        match target(target_)? {
            Target::Doc(d) => evaluate(|| self.q.values(&d)),
            Target::Node(d, i) => evaluate(|| self.q.values_from(d.node(i as usize))),
        }
    }

    /// The value of the first selected node, or the result of the expression; None when it selects nothing.
    fn value(&self, target_: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
        match target(target_)? {
            Target::Doc(d) => evaluate(|| self.q.value(&d)),
            Target::Node(d, i) => evaluate(|| self.q.value_from(d.node(i as usize))),
        }
    }

    fn __repr__(&self) -> String {
        format!("XPathQuery({:?})", self.q.as_str())
    }
}

// ----- functions -----

/// Decodes the character references of a text (CR LF and a lone CR become LF).
#[pyfunction]
fn decode_html(text: &str) -> String {
    fh::decode_html(text).into_owned()
}

/// The visible text of an HTML fragment.
#[pyfunction]
fn html_to_text(html: &str) -> String {
    fh::html_to_text(html)
}

/// The text of an HTML fragment with the visible line structure kept.
#[pyfunction]
fn html_to_text_line_breaks(html: &str) -> String {
    fh::html_to_text_line_breaks(html)
}

#[pymodule]
fn _fasthtmlparser(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(decode_html, m)?)?;
    m.add_function(wrap_pyfunction!(html_to_text, m)?)?;
    m.add_function(wrap_pyfunction!(html_to_text_line_breaks, m)?)?;
    m.add_class::<Document>()?;
    m.add_class::<Node>()?;
    m.add_class::<CssQuery>()?;
    m.add_class::<XPathQuery>()?;
    m.add("CssSelectorError", py.get_type::<CssSelectorError>())?;
    m.add("XPathError", py.get_type::<XPathError>())?;
    Ok(())
}
