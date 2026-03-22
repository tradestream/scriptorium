"""Metadata enrichment from multiple book databases.

Providers (in priority order):
  1. Hardcover   — high-quality curated data, GraphQL API (requires key)
  2. Amazon PAAPI — product data + covers, requires Associates key
  3. Google Books — broad coverage, good for ISBN lookup (optional key)
  4. Open Library — open, no key required, good fallback
  5. ISBNDB       — ISBN-focused, large database (requires key)
  6. ComicVine    — comics/graphic novels only (requires key)
  7. CrossRef     — academic/DOI data, open
  8. StoryGraph   — content warnings + genre tags, no key required

The `enrich()` method tries providers in order and returns the first
sufficient result. Providers without a configured API key are skipped
automatically.

Cover image retrieval is separate from metadata; each provider exposes
a `cover_url` field in the normalized result when available.
"""

from __future__ import annotations

import json as _json
import logging
import re
import urllib.parse
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── DB-backed key overrides ────────────────────────────────────────────────────
# Populated at startup and updated when admin saves enrichment keys via the UI.
# Values here shadow the corresponding env-var settings.
_key_overrides: dict[str, str | None] = {}


def apply_enrichment_key_overrides(overrides: dict[str, str | None]) -> None:
    """Update the in-memory key overrides. Call at startup and after API saves."""
    _key_overrides.update(overrides)


def _get_key(env_attr: str) -> str | None:
    """Return the effective key: DB override if set, otherwise env var."""
    db_val = _key_overrides.get(env_attr)
    return db_val if db_val else getattr(settings, env_attr, None)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _first(*values) -> Optional[str]:
    """Return the first truthy string value."""
    for v in values:
        if v and isinstance(v, str):
            return v.strip()
    return None


def _list_of_strings(val) -> list[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val if x]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def _date_str(val) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    # Normalize to YYYY, YYYY-MM, or YYYY-MM-DD
    return s[:10] if len(s) >= 10 else s


# ── Provider base ──────────────────────────────────────────────────────────────

class Provider:
    name: str = "base"

    def is_available(self) -> bool:
        return True

    async def search(
        self,
        title: str,
        authors: list[str],
        isbn: Optional[str],
        is_comic: bool = False,
    ) -> Optional[dict]:
        raise NotImplementedError


# ── Google Books ───────────────────────────────────────────────────────────────

class GoogleBooksProvider(Provider):
    name = "google_books"
    BASE = "https://www.googleapis.com/books/v1/volumes"

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if is_comic:
            return None  # Google Books is weak for comics
        if isbn:
            q = f"isbn:{isbn}"
        else:
            q = f'intitle:"{title}"'
            if authors:
                q += f' inauthor:"{authors[0]}"'
        params: dict = {"q": q, "maxResults": 1, "printType": "books"}
        if _get_key("GOOGLE_BOOKS_API_KEY"):
            params["key"] = _get_key("GOOGLE_BOOKS_API_KEY")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(self.BASE, params=params)
                r.raise_for_status()
                data = r.json()
                items = data.get("items", [])
                if not items:
                    return None
                item = items[0]
                result = self._normalize(item.get("volumeInfo", {}))
                if result and item.get("id"):
                    result["google_id"] = item["id"]
                return result
        except Exception as exc:
            logger.warning("Google Books error: %s", exc)
            return None

    def _normalize(self, info: dict) -> dict:
        result: dict = {}
        if t := info.get("title"):
            result["title"] = t
        if s := info.get("subtitle"):
            result["subtitle"] = s
        if a := info.get("authors"):
            result["authors"] = a
        if d := info.get("description"):
            result["description"] = d
        if c := info.get("categories"):
            result["tags"] = c
        if p := info.get("publishedDate"):
            result["published_date"] = _date_str(p)
        if lang := info.get("language"):
            result["language"] = lang
        if pc := info.get("pageCount"):
            result["page_count"] = pc
        for iid in info.get("industryIdentifiers", []):
            if iid.get("type") in ("ISBN_13", "ISBN_10") and "isbn" not in result:
                result["isbn"] = iid["identifier"]
        if pub := info.get("publisher"):
            result["publisher"] = pub
        imgs = info.get("imageLinks", {})
        if cover := imgs.get("thumbnail") or imgs.get("smallThumbnail"):
            result["cover_url"] = cover.replace("http://", "https://")
        return result


# ── Open Library ───────────────────────────────────────────────────────────────

class OpenLibraryProvider(Provider):
    name = "open_library"

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                if isbn:
                    r = await client.get(f"https://openlibrary.org/isbn/{isbn}.json")
                    if r.status_code == 404:
                        return None
                    r.raise_for_status()
                    return await self._normalize_book(r.json(), client)
                else:
                    q = title
                    if authors:
                        q += f" {authors[0]}"
                    r = await client.get(
                        "https://openlibrary.org/search.json",
                        params={"q": q, "limit": 1,
                                "fields": "key,title,author_name,subject,first_publish_year,isbn,language,cover_i"},
                    )
                    r.raise_for_status()
                    docs = r.json().get("docs", [])
                    return self._normalize_search(docs[0]) if docs else None
        except Exception as exc:
            logger.warning("Open Library error: %s", exc)
            return None

    async def _normalize_book(self, data: dict, client: httpx.AsyncClient) -> dict:
        result: dict = {}
        if t := data.get("title"):
            result["title"] = t
        if d := data.get("description"):
            result["description"] = d if isinstance(d, str) else d.get("value", "")
        if subj := data.get("subjects"):
            result["tags"] = _list_of_strings(subj)[:10]
        if pub := data.get("publish_date"):
            result["published_date"] = _date_str(pub)
        covers = data.get("covers", [])
        if covers:
            result["cover_url"] = f"https://covers.openlibrary.org/b/id/{covers[0]}-L.jpg"
        # Fetch author names
        if author_refs := data.get("authors"):
            names = []
            for ref in author_refs[:3]:
                key = ref.get("key") or (ref if isinstance(ref, str) else None)
                if key:
                    try:
                        ar = await client.get(f"https://openlibrary.org{key}.json", timeout=5.0)
                        if ar.status_code == 200:
                            names.append(ar.json().get("name", ""))
                    except Exception:
                        pass
            if names:
                result["authors"] = [n for n in names if n]
        return result

    def _normalize_search(self, doc: dict) -> dict:
        result: dict = {}
        if t := doc.get("title"):
            result["title"] = t
        if a := doc.get("author_name"):
            result["authors"] = _list_of_strings(a)
        if s := doc.get("subject"):
            result["tags"] = _list_of_strings(s)[:10]
        if y := doc.get("first_publish_year"):
            result["published_date"] = str(y)
        if isbns := doc.get("isbn"):
            result["isbn"] = isbns[0] if isinstance(isbns, list) else isbns
        if langs := doc.get("language"):
            result["language"] = langs[0] if isinstance(langs, list) else langs
        if cid := doc.get("cover_i"):
            result["cover_url"] = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"
        return result


# ── Hardcover ──────────────────────────────────────────────────────────────────

class HardcoverProvider(Provider):
    name = "hardcover"
    GQL = "https://api.hardcover.app/v1/graphql"

    def is_available(self) -> bool:
        return bool(_get_key("HARDCOVER_API_KEY"))

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if not self.is_available():
            return None
        # Use ISBN search when available, else title+author
        if isbn:
            query = """
            query($isbn: String!) {
              books(where: {_or: [{isbn_10: {_eq: $isbn}}, {isbn_13: {_eq: $isbn}}]}, limit: 1) {
                id title description language
                contributions { author { name } }
                book_tags { tag { tag } }
                release_date
                image { url }
                isbn_10 isbn_13
              }
            }"""
            variables: dict = {"isbn": isbn}
        else:
            query = """
            query($q: String!) {
              search(query: $q, query_type: "Book", per_page: 1) {
                results
              }
            }"""
            variables = {"q": f"{title} {authors[0]}" if authors else title}
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r = await client.post(
                    self.GQL,
                    json={"query": query, "variables": variables},
                    headers={
                        "Authorization": f"Bearer {_get_key('HARDCOVER_API_KEY')}",
                        "Content-Type": "application/json",
                    },
                )
                r.raise_for_status()
                data = r.json()
                if "errors" in data:
                    logger.warning("Hardcover GraphQL errors: %s", data["errors"])
                    return None
                if isbn:
                    books = data.get("data", {}).get("books", [])
                    return self._normalize(books[0]) if books else None
                else:
                    # Search API returns `results` as a JSON array string or object
                    raw = data.get("data", {}).get("search", {}).get("results")
                    if not raw:
                        return None
                    import json as _json
                    results = _json.loads(raw) if isinstance(raw, str) else raw
                    hits = results.get("hits", [])
                    if not hits:
                        return None
                    return self._normalize(hits[0].get("document", {}))
        except Exception as exc:
            logger.warning("Hardcover error: %s", exc)
            return None

    def _normalize(self, book: dict) -> dict:
        result: dict = {}
        if t := book.get("title"):
            result["title"] = t
        if d := book.get("description"):
            result["description"] = d
        if lang := book.get("language"):
            result["language"] = lang
        if rd := book.get("release_date"):
            result["published_date"] = _date_str(rd)
        # Authors via contributions
        contribs = book.get("contributions") or book.get("authors") or []
        names = []
        for c in contribs:
            if isinstance(c, dict):
                author = c.get("author") or c
                if n := author.get("name"):
                    names.append(n)
            elif isinstance(c, str):
                names.append(c)
        if names:
            result["authors"] = names
        # Tags
        tags = []
        for bt in book.get("book_tags") or book.get("tags") or []:
            if isinstance(bt, dict):
                tag_obj = bt.get("tag") or bt
                if t := tag_obj.get("tag") or tag_obj.get("name"):
                    tags.append(t)
            elif isinstance(bt, str):
                tags.append(bt)
        if tags:
            result["tags"] = tags
        # ISBN
        for key in ("isbn_13", "isbn_10"):
            if v := book.get(key):
                result.setdefault("isbn", v)
        # Cover
        if img := book.get("image"):
            if url := (img.get("url") if isinstance(img, dict) else img):
                result["cover_url"] = url
        return result


# ── ISBNDB ─────────────────────────────────────────────────────────────────────

class ISBNDBProvider(Provider):
    name = "isbndb"
    BASE = "https://api2.isbndb.com"

    def is_available(self) -> bool:
        return bool(_get_key("ISBNDB_API_KEY"))

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if not self.is_available():
            return None
        headers = {"Authorization": _get_key("ISBNDB_API_KEY")}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if isbn:
                    r = await client.get(f"{self.BASE}/book/{isbn}", headers=headers)
                    if r.status_code == 404:
                        return None
                    r.raise_for_status()
                    book = r.json().get("book", {})
                else:
                    q = f"{title} {authors[0]}" if authors else title
                    r = await client.get(
                        f"{self.BASE}/books/{q}",
                        params={"page": 1, "pageSize": 1},
                        headers=headers,
                    )
                    r.raise_for_status()
                    books = r.json().get("books", [])
                    book = books[0] if books else {}
                return self._normalize(book) if book else None
        except Exception as exc:
            logger.warning("ISBNDB error: %s", exc)
            return None

    def _normalize(self, book: dict) -> dict:
        result: dict = {}
        if t := book.get("title"):
            result["title"] = t
        if d := book.get("synopsis"):
            result["description"] = d
        if a := book.get("authors"):
            result["authors"] = _list_of_strings(a)
        if s := book.get("subjects"):
            result["tags"] = _list_of_strings(s)[:10]
        if p := book.get("date_published"):
            result["published_date"] = _date_str(p)
        if lang := book.get("language"):
            result["language"] = lang
        if pc := book.get("pages"):
            result["page_count"] = pc
        if pub := book.get("publisher"):
            result["publisher"] = pub
        for key in ("isbn13", "isbn"):
            if v := book.get(key):
                result.setdefault("isbn", v)
        if cover := book.get("image"):
            result["cover_url"] = cover
        return result


# ── ComicVine ──────────────────────────────────────────────────────────────────

class ComicVineProvider(Provider):
    name = "comicvine"
    BASE = "https://comicvine.gamespot.com/api"

    def is_available(self) -> bool:
        return bool(_get_key("COMICVINE_API_KEY"))

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if not self.is_available() or not is_comic:
            return None  # Only used for comics
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r = await client.get(
                    f"{self.BASE}/search/",
                    params={
                        "api_key": _get_key("COMICVINE_API_KEY"),
                        "query": title,
                        "resources": "volume",
                        "format": "json",
                        "limit": 1,
                        "field_list": "id,name,description,publisher,start_year,image,people",
                    },
                    headers={"User-Agent": "Scriptorium/1.0"},
                )
                r.raise_for_status()
                results = r.json().get("results", [])
                return self._normalize(results[0]) if results else None
        except Exception as exc:
            logger.warning("ComicVine error: %s", exc)
            return None

    def _normalize(self, vol: dict) -> dict:
        result: dict = {}
        if n := vol.get("name"):
            result["title"] = n
        # Strip HTML from description
        if d := vol.get("description"):
            import re
            result["description"] = re.sub(r"<[^>]+>", "", d).strip()
        if pub := (vol.get("publisher") or {}).get("name"):
            result["tags"] = [pub]
        if year := vol.get("start_year"):
            result["published_date"] = str(year)
        # Authors from people list
        people = vol.get("people") or []
        writers = [p["name"] for p in people if "Writer" in (p.get("role") or "")]
        if writers:
            result["authors"] = writers
        if img := (vol.get("image") or {}).get("original_url"):
            result["cover_url"] = img
        return result



# ── Amazon (cookie-based) ──────────────────────────────────────────────────────

_AMZ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
}


class AmazonProvider(Provider):
    """Fetch book metadata from Amazon using a session cookie.

    Set AMAZON_COOKIE in .env to the full cookie string copied from your browser
    (DevTools → Application → Cookies → copy all as header value).
    No API account required.
    """

    name = "amazon"
    BASE = "https://www.amazon.com"

    def is_available(self) -> bool:
        return bool(_get_key("AMAZON_COOKIE"))

    def _headers(self) -> dict:
        h = dict(_AMZ_HEADERS)
        h["Cookie"] = _get_key("AMAZON_COOKIE") or ""
        return h

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if not self.is_available():
            return None

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers=self._headers(),
            ) as client:
                # Step 1: find an ASIN via search
                asin = await self._find_asin(client, isbn, title, authors)
                if not asin:
                    return None

                # Step 2: fetch the product page
                r = await client.get(f"{self.BASE}/dp/{asin}")
                if r.status_code != 200:
                    return None
                return self._parse_product(r.text, asin)
        except Exception as exc:
            logger.warning("Amazon scraper error: %s", exc)
            return None

    async def _find_asin(
        self,
        client: httpx.AsyncClient,
        isbn: Optional[str],
        title: str,
        authors: list[str],
    ) -> Optional[str]:
        # ISBN search: Amazon redirects ISBN queries directly to the product page
        if isbn:
            r = await client.get(
                f"{self.BASE}/s",
                params={"k": isbn, "i": "stripbooks"},
            )
            if asin := self._extract_asin(r.text):
                return asin
            # Also try dp redirect which Amazon sometimes does for ISBNs
            r2 = await client.get(f"{self.BASE}/dp/{isbn}")
            if r2.status_code == 200 and "/dp/" in str(r2.url):
                m = re.search(r"/dp/([A-Z0-9]{10})", str(r2.url))
                if m:
                    return m.group(1)

        # Title + author search
        q = f"{title} {authors[0]}" if authors else title
        r = await client.get(
            f"{self.BASE}/s",
            params={"k": q, "i": "stripbooks"},
        )
        return self._extract_asin(r.text)

    def _extract_asin(self, html: str) -> Optional[str]:
        # Search results embed ASINs in data-asin attributes
        m = re.search(r'data-asin="([A-Z0-9]{10})"', html)
        return m.group(1) if m else None

    def _parse_product(self, html: str, asin: str) -> Optional[dict]:
        result: dict = {}

        # Prefer structured JSON-LD data embedded in the page
        ld_match = re.search(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if ld_match:
            try:
                ld = _json.loads(ld_match.group(1))
                # May be a list or a single object
                if isinstance(ld, list):
                    ld = next((x for x in ld if x.get("@type") == "Book"), ld[0] if ld else {})
                if ld.get("@type") == "Book":
                    if name := ld.get("name"):
                        result["title"] = name
                    author = ld.get("author") or ld.get("contributor")
                    if isinstance(author, dict):
                        author = [author]
                    if isinstance(author, list):
                        result["authors"] = [a.get("name") for a in author if a.get("name")]
                    if isbn := ld.get("isbn"):
                        result["isbn"] = isbn
                    if pub := ld.get("publisher"):
                        if isinstance(pub, dict):
                            result["publisher"] = pub.get("name", "")
                        elif isinstance(pub, str):
                            result["publisher"] = pub
                    if pd := ld.get("datePublished") or ld.get("copyrightYear"):
                        result["published_date"] = _date_str(str(pd))
                    if desc := ld.get("description"):
                        result["description"] = re.sub(r"<[^>]+>", "", desc).strip()
            except Exception:
                pass

        # Fall back to HTML scraping for any missing fields
        if not result.get("title"):
            m = re.search(r'id="productTitle"[^>]*>\s*(.*?)\s*</span>', html, re.DOTALL)
            if m:
                result["title"] = re.sub(r"\s+", " ", m.group(1)).strip()

        if not result.get("authors"):
            m = re.search(r'id="bylineInfo"[^>]*>(.*?)</span>', html, re.DOTALL)
            if m:
                names = re.findall(r'class="author[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', m.group(0))
                if names:
                    result["authors"] = [n.strip() for n in names]

        if not result.get("description"):
            m = re.search(r'id="bookDescription_feature_div"[^>]*>.*?<div[^>]*>(.*?)</div>', html, re.DOTALL)
            if m:
                result["description"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        # Hi-res cover via direct Amazon CDN URL — more reliable than HTML scraping.
        # Pattern discovered by calibre-amazon-hires-covers; works for any ASIN.
        result["cover_url"] = f"https://ec2.images-amazon.com/images/P/{asin}.01.MAIN._SCRM_.jpg"

        # Store ASIN for future lookups
        result["asin"] = asin

        return result if result.get("title") else None


# ── LibraryThing (CK — Common Knowledge) ───────────────────────────────────────

class LibraryThingProvider(Provider):
    """Fetch rich Common Knowledge data from LibraryThing.

    Retrieves characters, places, awards, original publication date, and
    original language via the ck.getWork REST endpoint.  ISBN-to-workcode
    resolution uses the multirecommendations API; title fallback uses
    thingTitle.

    Uses urllib.request instead of httpx — httpx is blocked by Cloudflare on
    many LibraryThing endpoints.
    """

    name = "librarything"

    def is_available(self) -> bool:
        return bool(_get_key("LIBRARYTHING_API_KEY"))

    # ── internal helpers ──────────────────────────────────────────────────────

    def _fetch(self, url: str) -> Optional[str]:
        """Synchronous URL fetch via urllib (bypasses CF managed challenge)."""
        import urllib.request as _urlreq
        req = _urlreq.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with _urlreq.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            logger.debug("LT fetch failed for %s: %s", url, exc)
            return None

    def _isbn_to_workcode(self, isbn: str, key: str) -> Optional[str]:
        """Return LT numeric work ID for an ISBN, or None."""
        import json as _j
        url = (
            f"https://www.librarything.com/api/multirecommendations.php"
            f"?isbns={urllib.parse.quote(isbn)}&apiKey={key}"
        )
        body = self._fetch(url)
        if not body:
            return None
        try:
            data = _j.loads(body)
            req_list = data.get("request") or []
            if req_list and isinstance(req_list, list):
                return str(req_list[0].get("work") or "").strip() or None
        except Exception:
            pass
        return None

    def _title_to_workcode(self, title: str, key: str) -> Optional[str]:
        """Return LT numeric work ID via title lookup, or None."""
        import xml.etree.ElementTree as ET
        url = (
            f"https://www.librarything.com/api/{key}/thingTitle/"
            f"{urllib.parse.quote(title)}"
        )
        body = self._fetch(url)
        if not body:
            return None
        try:
            root = ET.fromstring(body)
            # <link>https://www.librarything.com/work/2964</link>
            link_el = root.find(".//link")
            if link_el is not None and link_el.text:
                m = re.search(r"/work/(\d+)", link_el.text)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return None

    def _ck_data(self, workcode: str, key: str) -> dict:
        """Fetch CK XML for a workcode and parse into a normalised dict."""
        import xml.etree.ElementTree as ET
        url = (
            f"https://www.librarything.com/services/rest/1.1/"
            f"?method=librarything.ck.getWork&id={workcode}&apikey={key}"
        )
        body = self._fetch(url)
        if not body:
            return {}
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            logger.debug("LT CK XML parse error: %s", exc)
            return {}

        def _facts(field_name: str) -> list[str]:
            """Extract <fact> text values for a named <field>."""
            for field_el in root.iter("field"):
                if field_el.get("name") == field_name:
                    return [
                        f.text.strip()
                        for f in field_el.iter("fact")
                        if f.text and f.text.strip()
                    ]
            return []

        result: dict = {}

        if desc_facts := _facts("description"):
            result["description"] = desc_facts[0]

        if chars := _facts("characternames"):
            result["characters"] = chars

        if places := _facts("placesmentioned"):
            result["places"] = places

        if awards := _facts("awards"):
            result["awards"] = awards

        if orig_date := _facts("originalpublicationdate"):
            # e.g. "1925-04-10" or "1925"
            raw = orig_date[0][:10]
            result["original_publication_date"] = raw
            year_m = re.match(r"(\d{4})", raw)
            if year_m:
                result["original_publication_year"] = int(year_m.group(1))

        if orig_lang := _facts("originallanguage"):
            result["original_language"] = orig_lang[0]

        return result

    # ── public interface ──────────────────────────────────────────────────────

    async def search(
        self,
        title: str,
        authors: list[str],
        isbn: Optional[str],
        is_comic: bool = False,
    ) -> Optional[dict]:
        if not self.is_available():
            return None
        key = _get_key("LIBRARYTHING_API_KEY")

        import asyncio
        loop = asyncio.get_running_loop()

        # Resolve workcode (ISBN preferred, title fallback)
        workcode: Optional[str] = None
        if isbn:
            workcode = await loop.run_in_executor(
                None, self._isbn_to_workcode, isbn, key
            )
        if not workcode and title:
            workcode = await loop.run_in_executor(
                None, self._title_to_workcode, title, key
            )
        if not workcode:
            logger.debug("LT: could not resolve workcode for '%s' isbn=%s", title, isbn)
            return None

        result = await loop.run_in_executor(None, self._ck_data, workcode, key)
        if not result:
            return None
        logger.debug("LT: enriched work %s → %s", workcode, list(result.keys()))
        return result


# ── CrossRef ───────────────────────────────────────────────────────────────────

class CrossRefProvider(Provider):
    """Metadata from CrossRef — best for academic books, monographs, and any
    work with a DOI.  No API key required; uses the public REST API.

    Coverage is excellent for university press / academic publisher titles and
    near-zero for mainstream fiction, so this sits at the end of the chain as
    a fallback for scholarly content.
    """

    name = "crossref"
    BASE = "https://api.crossref.org/works"
    HEADERS = {"User-Agent": "Scriptorium/1.0 (mailto:admin@scriptorium.local)"}

    async def search(
        self,
        title: str,
        authors: list[str],
        isbn: Optional[str],
        is_comic: bool = False,
    ) -> Optional[dict]:
        if is_comic:
            return None
        try:
            async with httpx.AsyncClient(timeout=12.0, headers=self.HEADERS) as client:
                # ISBN search via query filter (CrossRef indexes many ISBNs)
                if isbn:
                    r = await client.get(
                        self.BASE,
                        params={
                            "filter": f"isbn:{isbn}",
                            "rows": 1,
                            "select": "title,author,publisher,issued,published-print,container-title,DOI,type",
                        },
                    )
                    r.raise_for_status()
                    items = r.json().get("message", {}).get("items", [])
                    if items:
                        return self._normalize(items[0])

                # Title + author query
                params: dict = {
                    "query.title": title,
                    "rows": 3,
                    "select": "title,author,publisher,issued,published-print,container-title,DOI,type",
                }
                if authors:
                    params["query.author"] = authors[0]
                r = await client.get(self.BASE, params=params)
                r.raise_for_status()
                items = r.json().get("message", {}).get("items", [])
                # Prefer book/monograph types over journal articles
                book_types = {"book", "monograph", "book-chapter", "edited-book", "reference-book"}
                for item in items:
                    if item.get("type", "") in book_types:
                        return self._normalize(item)
                # Fallback: first result regardless of type
                return self._normalize(items[0]) if items else None
        except Exception as exc:
            logger.warning("CrossRef error: %s", exc)
            return None

    def _normalize(self, item: dict) -> dict:
        result: dict = {}

        titles = item.get("title") or []
        if titles:
            result["title"] = titles[0]

        # Authors: [{given, family}, ...]
        authors = []
        for a in item.get("author") or []:
            given = a.get("given", "")
            family = a.get("family", "")
            name = f"{given} {family}".strip() if given else family
            if name:
                authors.append(name)
        if authors:
            result["authors"] = authors

        if pub := item.get("publisher"):
            result["publisher"] = pub

        # Series: container-title is the journal/series name
        ct = item.get("container-title") or []
        if ct:
            result["series"] = [ct[0]]

        # Publication date — prefer issued, fall back to published-print
        for date_key in ("issued", "published-print"):
            parts = (item.get(date_key) or {}).get("date-parts", [[]])
            if parts and parts[0]:
                year = parts[0][0]
                if year:
                    result["published_date"] = str(year)
                    break

        if doi := item.get("DOI"):
            result["doi"] = doi

        return result if result.get("title") else None


# ── StoryGraph provider ─────────────────────────────────────────────────────────

class StoryGraphProvider(Provider):
    """Fetches content warnings, genre tags, and ratings from The StoryGraph.

    Uses the unofficial `storygraph-api` library. No API key required.
    Returns content_warnings (dict with graphic/moderate/minor lists), tags,
    description, and average_rating.
    """

    name = "storygraph"

    def is_available(self) -> bool:
        try:
            import storygraph_api  # noqa: F401
            return True
        except ImportError:
            return False

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if not self.is_available() or is_comic:
            return None
        try:
            import asyncio
            import json as _j
            from storygraph_api import Book as SGBook
            sg = SGBook()
            query = f"{title} {authors[0]}" if authors else title

            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(None, sg.search, query)
            results = _j.loads(raw_results) if isinstance(raw_results, str) else raw_results
            if not results:
                return None

            sg_id = results[0].get("book_id")
            if not sg_id:
                return None

            raw_info = await loop.run_in_executor(None, sg.book_info, sg_id)
            info = _j.loads(raw_info) if isinstance(raw_info, str) else raw_info
            if not info:
                return None

            result: dict = {"title": info.get("title", title)}
            if desc := info.get("description"):
                result["description"] = desc
            if rating := info.get("average_rating"):
                result["average_rating"] = rating
            if tags := info.get("tags"):
                result["tags"] = tags if isinstance(tags, list) else list(tags)
            if warnings := info.get("warnings"):
                result["content_warnings"] = warnings
            return result if (result.get("content_warnings") or result.get("tags")) else None
        except Exception as exc:
            logger.debug("StoryGraph fetch failed: %s", exc)
            return None


# ── Goodreads scraper ──────────────────────────────────────────────────────────

class GoodreadsProvider(Provider):
    """Scrapes Goodreads for ratings, awards, descriptions, and metadata.

    No API key needed — uses HTML scraping like Booklore's GoodReadsParser.
    """

    name = "goodreads"
    BASE_SEARCH = "https://www.goodreads.com/search?q="
    BASE_BOOK = "https://www.goodreads.com/book/show/"

    def is_available(self) -> bool:
        return True  # No key required

    async def search(self, title: str, authors: list[str], isbn: Optional[str], is_comic: bool = False) -> Optional[dict]:
        if is_comic:
            return None
        try:
            # Search by ISBN first, then title+author
            query = isbn if isbn else f"{title} {authors[0]}" if authors else title
            search_url = self.BASE_SEARCH + urllib.parse.quote_plus(query)

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(search_url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                })
                if r.status_code != 200:
                    return None

                # Extract first result's book ID
                gr_id = self._extract_book_id(r.text)
                if not gr_id:
                    return None

                # Fetch the book page
                book_r = await client.get(f"{self.BASE_BOOK}{gr_id}", headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                })
                if book_r.status_code != 200:
                    return None

                return self._parse_book_page(book_r.text, gr_id)

        except Exception as exc:
            logger.debug("Goodreads fetch failed: %s", exc)
            return None

    def _extract_book_id(self, html: str) -> Optional[str]:
        """Extract the first book ID from search results."""
        # Search results have links like /book/show/12345
        m = re.search(r'/book/show/(\d+)', html)
        return m.group(1) if m else None

    def _parse_book_page(self, html: str, gr_id: str) -> Optional[dict]:
        """Parse a Goodreads book page for metadata."""
        result: dict = {"goodreads_id": gr_id}

        # Try JSON-LD first
        ld_match = re.search(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if ld_match:
            try:
                ld = _json.loads(ld_match.group(1))
                if isinstance(ld, list):
                    ld = next((x for x in ld if x.get("@type") == "Book"), ld[0] if ld else {})
                if ld.get("name"):
                    result["title"] = ld["name"]
                if ld.get("author"):
                    authors = ld["author"]
                    if isinstance(authors, dict):
                        authors = [authors]
                    if isinstance(authors, list):
                        result["authors"] = [a.get("name") for a in authors if a.get("name")]
                if ld.get("isbn"):
                    result["isbn"] = ld["isbn"]
                if ld.get("numberOfPages"):
                    try:
                        result["page_count"] = int(ld["numberOfPages"])
                    except (ValueError, TypeError):
                        pass
                if ld.get("inLanguage"):
                    result["language"] = ld["inLanguage"]
                if ld.get("aggregateRating"):
                    ar = ld["aggregateRating"]
                    try:
                        result["goodreads_rating"] = float(ar.get("ratingValue", 0))
                        result["goodreads_rating_count"] = int(ar.get("ratingCount", 0))
                    except (ValueError, TypeError):
                        pass
            except Exception:
                pass

        # Fallback: scrape rating from HTML
        if "goodreads_rating" not in result:
            m = re.search(r'class="RatingStatistics__rating">(\d+\.\d+)</span>', html)
            if m:
                try:
                    result["goodreads_rating"] = float(m.group(1))
                except ValueError:
                    pass

        # Extract description
        if "description" not in result:
            m = re.search(
                r'<div[^>]*class="[^"]*DetailsLayoutRightParagraph[^"]*"[^>]*>\s*<span[^>]*>(.*?)</span>',
                html, re.DOTALL,
            )
            if m:
                desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if desc:
                    result["description"] = desc

        # Extract genres/categories
        genre_matches = re.findall(r'class="BookPageMetadataSection__genreButton"[^>]*><span[^>]*>([^<]+)</span>', html)
        if genre_matches:
            result["tags"] = [g.strip() for g in genre_matches[:10]]

        # Extract awards
        award_matches = re.findall(r'class="AwardCard[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?<span[^>]*>(\d{4})?</span>', html, re.DOTALL)
        if award_matches:
            awards = []
            for name, year in award_matches[:10]:
                award = {"name": name.strip()}
                if year:
                    award["year"] = int(year)
                awards.append(award)
            result["awards"] = awards

        # Cover URL
        cover_match = re.search(r'class="BookCover__image"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.DOTALL)
        if not cover_match:
            cover_match = re.search(r'id="coverImage"[^>]+src="([^"]+)"', html)
        if cover_match:
            cover_url = cover_match.group(1)
            # Upgrade to large size
            cover_url = re.sub(r'\._S[XY]\d+_', '._SX600_', cover_url)
            result["cover_url"] = cover_url

        return result if result.get("title") or result.get("goodreads_rating") else None


# ── Enrichment service ─────────────────────────────────────────────────────────

COMIC_EXTENSIONS = {".cbr", ".cbz", ".cb7", ".cbt"}


class MetadataEnrichmentService:
    """Tries multiple metadata providers in priority order.

    Priority for books:   Hardcover → Amazon → Google Books → Open Library → ISBNDB → LibraryThing → CrossRef → StoryGraph
    Priority for comics:  ComicVine → Open Library
    """

    def __init__(self):
        self._book_providers: list[Provider] = [
            HardcoverProvider(),
            GoodreadsProvider(),
            AmazonProvider(),
            GoogleBooksProvider(),
            OpenLibraryProvider(),
            ISBNDBProvider(),
            LibraryThingProvider(),
            CrossRefProvider(),
            StoryGraphProvider(),
        ]
        self._comic_providers: list[Provider] = [
            ComicVineProvider(),
            OpenLibraryProvider(),
        ]

    async def enrich(
        self,
        title: str,
        authors: list[str],
        isbn: Optional[str] = None,
        file_extension: Optional[str] = None,
    ) -> Optional[dict]:
        """Try all configured providers in order, return first sufficient result.

        Merges results across providers so later providers fill in missing fields
        from an earlier partial result.
        """
        is_comic = (file_extension or "").lower() in COMIC_EXTENSIONS
        providers = self._comic_providers if is_comic else self._book_providers

        merged: dict = {}
        for provider in providers:
            if not provider.is_available():
                continue
            try:
                result = await provider.search(title, authors, isbn, is_comic=is_comic)
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider.name, exc)
                continue

            if not result:
                continue

            # Merge: earlier (higher-priority) values win for most fields,
            # but we fill in any gaps from subsequent providers.
            for key, val in result.items():
                if key not in merged and val:
                    merged[key] = val

            # If we have all the key fields, stop searching.
            if all(merged.get(k) for k in ("title", "authors", "description")):
                break

        return merged if merged else None

    async def enrich_stream(
        self,
        title: str,
        authors: list[str],
        isbn: Optional[str] = None,
        file_extension: Optional[str] = None,
    ):
        """Yield (provider_name, result_or_None) for each provider tried.

        Used by SSE endpoints to stream per-provider results to the frontend.
        """
        is_comic = (file_extension or "").lower() in COMIC_EXTENSIONS
        providers = self._comic_providers if is_comic else self._book_providers

        for provider in providers:
            if not provider.is_available():
                yield provider.name, None, "skipped"
                continue
            try:
                result = await provider.search(title, authors, isbn, is_comic=is_comic)
                yield provider.name, result, "ok"
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider.name, exc)
                yield provider.name, None, "error"

    async def search_all_providers(
        self,
        title: str,
        authors: list[str],
        isbn: Optional[str] = None,
        file_extension: Optional[str] = None,
    ) -> list[dict]:
        """Query all providers and return a list of results with provider names.

        Used by the metadata proposal UI to show side-by-side comparisons.
        """
        is_comic = (file_extension or "").lower() in COMIC_EXTENSIONS
        providers = self._comic_providers if is_comic else self._book_providers
        results = []
        for provider in providers:
            if not provider.is_available():
                continue
            try:
                result = await provider.search(title, authors, isbn, is_comic=is_comic)
                if result:
                    result["_provider"] = provider.name
                    results.append(result)
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider.name, exc)
        return results

    async def search_provider(
        self,
        provider_name: str,
        title: str,
        authors: list[str],
        isbn: Optional[str] = None,
    ) -> Optional[dict]:
        """Search a specific provider by name."""
        all_providers = self._book_providers + self._comic_providers
        for p in all_providers:
            if p.name == provider_name:
                return await p.search(title, authors, isbn)
        raise ValueError(f"Unknown provider: {provider_name}")

    def available_providers(self) -> list[dict]:
        """Return list of providers with their availability status."""
        comic_names = {p.name for p in self._comic_providers}
        book_names = {p.name for p in self._book_providers}
        seen: set[str] = set()
        result = []
        for p in self._book_providers + self._comic_providers:
            if p.name not in seen:
                seen.add(p.name)
                result.append({
                    "name": p.name,
                    "available": p.is_available(),
                    # True if it's *only* for comics (not in the book chain)
                    "for_comics": p.name in comic_names and p.name not in book_names,
                })
        return result


enrichment_service = MetadataEnrichmentService()
