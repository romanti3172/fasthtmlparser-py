Results of `python bench/bench.py` (2026-11-17, AMD Ryzen 7 3800X, Windows 10, selectolax 1.0.2, lxml 6.1.3, parsel 1.12.1, beautifulsoup4 4.15.0).

Python 3.14.10, Windows, AMD64 Family 23 Model 113 Stepping 0, AuthenticAMD

| page | fasthtmlparser | selectolax (lexbor) | lxml | parsel (lxml) | BeautifulSoup (lxml) | BeautifulSoup (html.parser) |
|---|---:|---:|---:|---:|---:|---:|
| quotes, 11 KB | 18 μs | 96 μs | 502 μs | 511 μs | 4,293 μs | 5,168 μs |
| laptops, 38 KB | 52 μs | 337 μs | 1,519 μs | 1,575 μs | 11,225 μs | 15,080 μs |
| books, 51 KB | 65 μs | 413 μs | 1,413 μs | 1,499 μs | 16,476 μs | 17,183 μs |
| books x10, 510 KB | 624 μs | 3,838 μs | 14,825 μs | 14,530 μs | 13,614 μs | 179,453 μs |
| books without </li> </p> | 59 μs | 211 μs | 1,402 μs | 1,614 μs | 13,614 μs | 17,203 μs |

| scrape 20 books | time |
|---|---:|
| fasthtmlparser find | 150 μs |
| fasthtmlparser CSS | 127 μs |
| fasthtmlparser XPath | 230 μs |
| selectolax CSS | 554 μs |
| lxml XPath | 2,720 μs |
| parsel CSS | 2,454 μs |
| BeautifulSoup (lxml) CSS | 17,615 μs |

| scrape 10 quotes | time |
|---|---:|
| fasthtmlparser find | 74 μs |
| selectolax CSS | 247 μs |
| parsel CSS | 1,015 μs |
| BeautifulSoup (lxml) CSS | 5,744 μs |
