"""Library hours and Tech Bar equipment from LibCal, fetched live (see the note below)."""

import re
import threading
import time
from collections import Counter

from agent.data import _WORD
from agent.grades import _anex_module
from agent.state import Passage


# --- LibCal: library hours and Tech Bar equipment, fetched live (#121) ---------
# The University Libraries run their hours and their Tech Bar equipment lending on
# Springshare LibCal (tamu.libcal.com), which serves both as public JSON with no
# key or login. The hours page on library.tamu.edu draws its tables from the same
# feed with JavaScript, so that page's HTML has no times in it
# (deliverable2/libraries-kaushalp55.md). Hours change for holidays and breaks, so
# they're cached for an hour; the equipment catalog for a day. Same pacing as anex.

LIBCAL = "https://tamu.libcal.com"
LIBCAL_HOURS_URL = f"{LIBCAL}/api_hours_grid.php"
LIBCAL_EQUIPMENT_URL = f"{LIBCAL}/process_equip_cat.php"
LIBRARY_HOURS_PAGE = "https://library.tamu.edu/about/hours.html"  # what students open to check
LIBCAL_HOURS_WIDGET = 150  # the Libraries' hours calendar (LibCal's `iid`)
LIBCAL_HOURS_WEEKS = 2  # LibCal's week starts on Monday; two weeks lets Sunday answer "tomorrow"
LIBCAL_TIMEOUT_SECONDS = 10
LIBCAL_HOURS_CACHE_SECONDS = 60 * 60
LIBCAL_EQUIPMENT_CACHE_SECONDS = 24 * 60 * 60
LIBCAL_GAP_SECONDS = 1.0
LIBCAL_PER_PAGE = 100  # items per equipment request; the biggest category has about 50
LIBCAL_MAX_PAGES = 5
CAMPUS_TZ = "America/Chicago"

# Extra names students use for LibCal hours locations (lid -> words), on top of the words
# in each location's own name.
LIBRARY_ALIASES = {
    1644: {"evans", "main", "sterling"},
    1645: {"evans", "annex", "sterling"},
    3516: {"wcl", "west"},
    1647: {"msl", "medical"},
    3517: {"cushing"},
    3521: {"psel"},
    23383: {"williams", "galveston"},
    11483: {"askus", "chat", "ask"},
}
_LOCATION_NOISE = {"library", "libraries", "the", "hours", "hour", "tamu", "texas", "a", "m",
                   "open", "is", "at", "of", "s", "campus"}

# The two Tech Bars (LibCal equipment location ids). Category ids differ per Tech Bar,
# so each category maps location id -> category id. From tamu.libcal.com/equipment,
# checked Nov 22, 2026; a category missing from a Tech Bar isn't lent there.
TECH_BARS = {20326: "Tech Bar at Evans Library Annex", 20467: "Tech Bar at West Campus Library"}
TECH_BAR_ALIASES = {20326: {"evans", "annex", "sterling", "main"}, 20467: {"west", "wcl"}}
EQUIPMENT_CATEGORIES = {
    "Assistive tech": {20326: 42965, 20467: 49521},
    "Astronomy": {20326: 43020},
    "Audio equipment": {20326: 42970, 20467: 43824},
    "Calculators": {20326: 42841, 20467: 43366},
    "Chargers, cables and adaptors": {20326: 42931, 20467: 43369},
    "Chromebooks": {20326: 42969, 20467: 43370},
    "Computer accessories": {20326: 42986, 20467: 43367},
    "Gadgets and tools": {20326: 42984},
    "Photography accessories": {20326: 42971, 20467: 43372},
    "Cameras": {20326: 42913, 20467: 43368},
    "Projectors": {20326: 42862, 20467: 43371},
    "Video equipment": {20326: 42968, 20467: 43783},
}
# Words a student might use -> category. Anything else is searched by item name (like 'TI-84').
EQUIPMENT_WORDS = {
    "assistive": "Assistive tech", "astronomy": "Astronomy", "telescope": "Astronomy",
    "binocular": "Astronomy", "audio": "Audio equipment", "microphone": "Audio equipment",
    "mic": "Audio equipment", "headphone": "Audio equipment", "speaker": "Audio equipment",
    "recorder": "Audio equipment", "calculator": "Calculators", "charger": "Chargers, cables and adaptors",
    "cable": "Chargers, cables and adaptors", "adapter": "Chargers, cables and adaptors",
    "adaptor": "Chargers, cables and adaptors", "cord": "Chargers, cables and adaptors",
    "chromebook": "Chromebooks", "laptop": "Chromebooks", "accessory": "Computer accessories",
    "mouse": "Computer accessories", "keyboard": "Computer accessories", "webcam": "Computer accessories",
    "accessories": "Computer accessories",
    "gadget": "Gadgets and tools", "tool": "Gadgets and tools", "camera": "Cameras",
    "tripod": "Photography accessories", "lens": "Photography accessories",
    "projector": "Projectors", "video": "Video equipment", "camcorder": "Video equipment",
}

_libcal_lock = threading.Lock()
_libcal_cache: dict[tuple, tuple[float, object, str]] = {}  # key -> (time, data, fetched_at)
_libcal_last_request = 0.0
_TAG = re.compile(r"<[^>]+>")


def _fetch_libcal(url: str, params: dict) -> dict:
    """GET one LibCal JSON endpoint. Tests replace this."""
    import requests

    global _libcal_last_request
    wait = LIBCAL_GAP_SECONDS - (time.monotonic() - _libcal_last_request)
    if wait > 0:
        time.sleep(wait)
    _libcal_last_request = time.monotonic()
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": _anex_module().USER_AGENT},
                            timeout=LIBCAL_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as err:
        raise RuntimeError(f"the Libraries' LibCal didn't answer ({type(err).__name__}); try again later") from err


def _libcal_cached(key: tuple, seconds: int, load):
    """(data, fetched_at) for a cache key, calling load() at most once per `seconds`."""
    with _libcal_lock:
        hit = _libcal_cache.get(key)
        if hit and time.monotonic() - hit[0] < seconds:
            return hit[1], hit[2]
        fetched_at = _anex_module().now_utc()
        value = load()
        _libcal_cache[key] = (time.monotonic(), value, fetched_at)
        return value, fetched_at


def campus_today():
    """Today's date in College Station. Tests replace this."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(CAMPUS_TZ)).date()


def _plain_hours(rendered: str) -> str:
    """'7am - 12am' -> '7am - midnight', so closing at 12am isn't read as morning."""
    text = re.sub(r"\b12am\b", "midnight", rendered)
    return re.sub(r"\b12pm\b", "noon", text)


def _pick(found: list[tuple[int, object]], asked: str, what: str, names: list[str]):
    """The best-scoring matches, or LookupError naming what exists."""
    best = max((score for score, _ in found), default=0)
    if best == 0:
        raise LookupError(f"no {what} matches {asked!r}. Try one of: {', '.join(names)}.")
    return [item for score, item in found if score == best]


def library_hours(location: str | None = None) -> list[Passage]:
    """This week's and next week's hours for one library location, live from LibCal.
    Without a location, every library (not the services inside them) that has hours set.
    'Evans' matches both Evans Library and the Evans Annex, which share a building."""

    def load():
        raw = _fetch_libcal(LIBCAL_HOURS_URL, {"iid": LIBCAL_HOURS_WIDGET, "format": "json",
                                              "weeks": LIBCAL_HOURS_WEEKS, "systemTime": 0})
        try:
            return [{"lid": loc["lid"], "name": loc["name"], "category": loc.get("category"),
                     "days": [(d["date"], day, d.get("rendered") or "")
                              for week in loc["weeks"] for day, d in week.items()]}
                    for loc in raw["locations"]]
        except (KeyError, TypeError, AttributeError) as err:
            raise RuntimeError("LibCal changed its hours format; get_library_hours needs updating") from err

    locations, fetched_at = _libcal_cached(("hours",), LIBCAL_HOURS_CACHE_SECONDS, load)
    has_hours = [loc for loc in locations if any(r for _, _, r in loc["days"])]
    if location:
        asked = set(_WORD.findall(location.lower())) - _LOCATION_NOISE
        scored = [(len(asked & (set(_WORD.findall(loc["name"].lower())) | LIBRARY_ALIASES.get(loc["lid"], set()))),
                   loc) for loc in locations]  # a match with no hours set says so, day by day
        chosen = _pick(scored, location, "library location",
                       sorted({loc["name"] for loc in has_hours if loc["category"] == "library"}))
    else:
        chosen = [loc for loc in has_hours if loc["category"] == "library"]

    today = campus_today()
    from datetime import date

    passages = []
    for loc in chosen:
        days = sorted(loc["days"])
        lines = []
        for iso, day, rendered in days:
            d = date.fromisoformat(iso)
            label = f"{day}, {d:%B} {d.day}" + (" (today)" if d == today else "")
            lines.append(f"{label}: {_plain_hours(rendered) if rendered else 'hours not posted'}")
        first, last = date.fromisoformat(days[0][0]), date.fromisoformat(days[-1][0])
        text = (f"{loc['name']} hours, {first:%B} {first.day} to {last:%B} {last.day}, {last.year}, "
                f"from the Libraries' hours calendar. Today is {today:%A, %B} {today.day}, {today.year}. "
                + "; ".join(lines) + ". Hours past midnight run into the next morning.")
        passages.append({
            "id": f"libraries:hours/{loc['lid']}:1:live",
            "source": "libraries",
            "title": f"{loc['name']} hours",
            "text": text,
            "source_url": LIBRARY_HOURS_PAGE,
            "fetched_at": fetched_at,
        })
    return passages


def _short(description: str, words: int = 20) -> str:
    """An item's HTML description as one short line of plain text."""
    import html

    text = " ".join(html.unescape(_TAG.sub(" ", description or "")).split())
    cut = text.split()
    return " ".join(cut[:words]) + ("..." if len(cut) > words else "")


def _equipment_items(lid: int, gid: int, query: str = "") -> list[dict]:
    """Every item in one Tech Bar category (gid 0 = all), following LibCal's pages."""

    def load():
        items, page = [], 1
        while page <= LIBCAL_MAX_PAGES:
            raw = _fetch_libcal(LIBCAL_EQUIPMENT_URL, {"lid": lid, "gid": gid, "perpage": LIBCAL_PER_PAGE,
                                                       "page": page, "q": query})
            try:
                found = [{"name": " ".join(r["NAME"].split()), "category": r["CATEGORY"],
                          "about": _short(r.get("DESCRIPTION", ""))} for r in raw["results"]]
                total = int(raw["total_results"])
            except (KeyError, TypeError, ValueError) as err:
                raise RuntimeError("LibCal changed its equipment format; list_library_equipment needs updating") from err
            items += found
            if not found or len(items) >= total:
                break
            page += 1
        return items

    return _libcal_cached(("equipment", lid, gid, query), LIBCAL_EQUIPMENT_CACHE_SECONDS, load)


def _equipment_text(what: str, items: list[dict]) -> str:
    """One line per item name, with how many copies the catalog lists."""
    copies = Counter(i["name"] for i in items)
    about = {}
    for i in items:
        about.setdefault(i["name"], i)
    lines = []
    for name in sorted(copies, key=str.lower):
        item = about[name]
        extra = [f"{copies[name]} listed"] if copies[name] > 1 else []
        if what == "search":
            extra.append(item["category"])
        if item["about"]:
            extra.append(item["about"])
        lines.append(f"- {name}" + (f" ({'; '.join(extra)})" if extra else ""))
    return "\n".join(lines)


def library_equipment(category: str, location: str | None = None) -> list[Passage]:
    """What the Tech Bars lend in one category, or items whose name matches (like 'TI-84'),
    live from LibCal. One passage per Tech Bar, linking the page where students reserve."""
    exact = [name for name in EQUIPMENT_CATEGORIES if name.lower() == " ".join(category.lower().split())]
    if exact:  # 'Photography accessories' is one category, not cameras plus computer accessories
        kinds = set(exact)
    else:
        words = set(_WORD.findall(category.lower()))
        words |= {w[:-1] for w in words if w.endswith("s") and len(w) > 3}  # calculators -> calculator
        kinds = {EQUIPMENT_WORDS[w] for w in words if w in EQUIPMENT_WORDS}

    bars = list(TECH_BARS)
    if location:
        asked = set(_WORD.findall(location.lower())) - _LOCATION_NOISE
        bars = _pick([(len(asked & TECH_BAR_ALIASES[lid]), lid) for lid in TECH_BARS], location,
                     "Tech Bar", list(TECH_BARS.values()))

    passages = []
    if len(kinds) == 1:  # a kind of device: list the whole category at each Tech Bar
        kind = kinds.pop()
        for lid in bars:
            gid = EQUIPMENT_CATEGORIES[kind].get(lid)
            if gid is None:
                continue
            items, fetched_at = _equipment_items(lid, gid)
            if not items:
                continue
            passages.append({
                "id": f"libraries:equipment/{lid}-{gid}:1:live",
                "source": "libraries",
                "title": f"{kind} at the {TECH_BARS[lid]}",
                "text": (f"{kind} you can borrow from the {TECH_BARS[lid]}, from its equipment catalog "
                         f"({len(items)} listed; this list doesn't show which are checked out right now). "
                         f"Reserving one needs a NetID login on the catalog page.\n"
                         + _equipment_text(kind, items)),
                "source_url": f"{LIBCAL}/equipment?lid={lid}&gid={gid}",
                "fetched_at": fetched_at,
            })
        if not passages:
            where = " or ".join(TECH_BARS[lid] for lid in bars)
            raise LookupError(f"the {where} doesn't lend {kind.lower()}.")
        return passages

    query = " ".join(category.split())
    for lid in bars:  # a model or brand: search item names across every category
        items, fetched_at = _equipment_items(lid, 0, query)
        if items:
            slug = "-".join(_WORD.findall(query.lower())) or "items"
            passages.append({
                "id": f"libraries:equipment/{lid}-search-{slug}:1:live",
                "source": "libraries",
                "title": f"Items matching '{query}' at the {TECH_BARS[lid]}",
                "text": (f"Items at the {TECH_BARS[lid]} whose name matches '{query}', from its equipment "
                         f"catalog ({len(items)} listed; this list doesn't show which are checked out right "
                         f"now). Reserving one needs a NetID login on the catalog page.\n"
                         + _equipment_text("search", items)),
                "source_url": f"{LIBCAL}/equipment?lid={lid}",
                "fetched_at": fetched_at,
            })
    if not passages:
        raise LookupError(
            f"nothing at the Tech Bars matches {category!r}. Kinds of equipment they lend: "
            f"{', '.join(EQUIPMENT_CATEGORIES)}. Try one of those, or a model name like 'TI-84'.")
    return passages
