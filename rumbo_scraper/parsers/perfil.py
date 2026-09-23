"""Reading the institutional profile a university publishes on its home page.

Every one of the fifteen sites keeps the same things in the same place: the
links to its social networks in the footer, its telephone and its mail address
beside them, and the year it was founded in the sentence that introduces it.
Those are the columns of ``universidades`` that no career page ever fills, so
they are read once per university and not once per career.

This lives apart from any one adapter because the footer of a site is the one
part that fifteen different content managers still build the same way.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from rumbo_scraper.normalizers.text import clean_text, comparison_key
from rumbo_scraper.normalizers.url import is_official_url

# The networks the contract has a column for, and the host that identifies each.
NETWORKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("instagram", ("instagram.com",)),
    ("facebook", ("facebook.com",)),
    ("linkedin", ("linkedin.com",)),
    ("twitter", ("twitter.com", "x.com")),
    ("youtube", ("youtube.com", "youtu.be")),
    ("tiktok", ("tiktok.com",)),
)

# A link to the network of a faculty, a career or a campus is not the account
# of the university; the ones that matter sit in the footer, unqualified.
_NOT_AN_ACCOUNT = re.compile(
    r"(?i)/(share|sharer|intent|login|signup|help|legal|privacy|policies|"
    # A video, a playlist or a post is something the university published,
    # not the account that published it.
    r"watch|playlist|embed|shorts|posts?|photo|video|reel|status|p|tr|pixel)\b"
    r"|/hashtag/|[?&]u=|[?&]url=|[?&]v=|^https?://(analytics|px|pixel)\."
)


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup


def social_accounts(html: str, page_url: str) -> dict[str, str]:
    """Read the account of the university on each network it links to.

    A page carries several links to the same network: the account in the
    footer and the buttons that share the page on it. The share buttons carry
    the address they would share, so they are the ones with a query string,
    and they are left out.
    """
    accounts: dict[str, str] = {}
    for anchor in _soup(html).find_all("a", href=True):
        url = urljoin(page_url, clean_text(anchor["href"]))
        host = (urlparse(url).netloc or "").lower().lstrip("www.")
        if _NOT_AN_ACCOUNT.search(url):
            continue
        for field, hosts in NETWORKS:
            if field in accounts or not any(host.endswith(h) for h in hosts):
                continue
            path = urlparse(url).path.strip("/")
            if not path:
                # The bare host is a link to the network, not to an account.
                continue
            accounts[field] = url.split("?")[0]
    return accounts


# A telephone written for a person to read, with or without the country code.
_PHONE = re.compile(r"(?:\+?54)?\s*(?:\(?0?(\d{2,4})\)?)?[\s.-]*(\d{3,4}[\s.-]?\d{4})")
_INSTITUTIONAL_MAIL = re.compile(
    r"(?i)^(info|informes|contacto|admisiones|ingreso|consultas|comunicacion|"
    r"institucional|secretaria|alumnos|estudiantes)"
)


def contact(html: str, domain: str) -> dict[str, str | None]:
    """Read the mail address and the telephone the site publishes for itself.

    A site lists many mail addresses; the one that answers for the university
    is the one it names for information or admissions, so that is the one
    taken and, failing it, the first address of its own domain.
    """
    soup = _soup(html)
    mails: list[str] = []
    phones: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = clean_text(anchor["href"])
        low = href.lower()
        if low.startswith("mailto:"):
            value = clean_text(href[7:].split("?")[0])
            if "@" in value and value not in mails:
                mails.append(value)
        elif low.startswith("tel:"):
            value = clean_text(href[4:])
            if value and value not in phones:
                phones.append(value)
    own = [mail for mail in mails
           if mail.lower().split("@")[-1].endswith(domain.lower())]
    # Only an address the university named for information or admissions is
    # its contact. The first address of the domain is as likely to be the one
    # that receives job applications, and publishing that is worse than none.
    preferred = next(
        (mail for mail in own if _INSTITUTIONAL_MAIL.match(mail.split("@")[0])), None)
    area, number = _split_phone(phones[0]) if phones else (None, None)
    return {"mail_contacto": preferred, "telefono_area": area,
            "telefono_numero": number}


# 0800 and 0810 are national numbers: they have no area code, and splitting
# one as if it had turns 0810-122-1222 into area 81.
_NATIONAL = re.compile(r"^(800|810|600)")
# The area code is read only where the site itself separated it: in brackets,
# after the country code, or as a group that opens with a zero. Argentina's
# areas run from two to four digits and its subscriber numbers from six to
# eight, so a bare string of digits does not say where one ends and the other
# begins -- and a wrong split is a telephone that does not ring.
_AREA_IN_BRACKETS = re.compile(r"\(\s*0?(\d{2,4})\s*\)")
_AREA_AFTER_COUNTRY = re.compile(r"^\s*\+\s*54\s+0?(\d{2,4})[\s.-]")
_AREA_WITH_ZERO = re.compile(r"^\s*0(\d{2,4})[\s.-]")


def _split_phone(value: str) -> tuple[str | None, str | None]:
    """Split a published telephone into its area code and its number."""
    text = clean_text(value)
    digits = re.sub(r"\D", "", text)
    digits = re.sub(r"^54", "", digits) if text.lstrip().startswith("+") else digits
    digits = digits.lstrip("0")
    if len(digits) < 6:
        return None, None
    if _NATIONAL.match(digits):
        return None, digits
    for pattern in (_AREA_IN_BRACKETS, _AREA_AFTER_COUNTRY, _AREA_WITH_ZERO):
        match = pattern.search(text)
        if match and digits.startswith(match.group(1)):
            area = match.group(1)
            return area, digits[len(area):] or None
    # Buenos Aires is the one area a bare number still gives away, because
    # eleven plus eight digits is the only ten-digit shape in the country.
    if len(digits) == 10 and digits.startswith("11"):
        return "11", digits[2:]
    return None, digits


# The year of foundation is deliberately not read here. A page says "desde
# 2008" about a campus, a programme or an award as readily as about the
# university, and the sentence around it is the only thing that tells them
# apart; a wrong year is worse than an empty one.


def read_profile(pages: dict[str, str], domain: str) -> dict[str, Any]:
    """Read every institutional field the pages of a university publish.

    More than one page is read because a site keeps its networks in the footer
    of one page and its contact on another; whichever states a field first is
    the one that fills it.
    """
    profile: dict[str, Any] = {}
    for url, html in pages.items():
        if not html:
            continue
        if not is_official_url(url, domain, require_https=False):
            continue
        for field, value in social_accounts(html, url).items():
            profile.setdefault(field, value)
        for field, value in contact(html, domain).items():
            if value and field not in profile:
                profile[field] = value
    return profile
