"""library_tools: Texas A&M University Libraries (#121).

search_libraries searches the collected library pages. Hours and Tech Bar
equipment come live from the Libraries' LibCal (see agent/libcal.py), because
hours change for holidays and breaks and the library website draws them with
JavaScript. Booking a room or a device needs a NetID login, so answers link
the page where students do it instead.
"""

from langchain_core.tools import tool

from agent import data, libcal
from agent.state import Passage


@tool
def search_libraries(query: str) -> list[Passage]:
    """Search the University Libraries' pages: borrowing and loan periods, renewals,
    returns and book drops, overdue fines and lost or damaged items, Get It For Me,
    the Tech Bar's rules (how long you can keep a device, late fees, returning it to
    another library), study rooms and how to reserve them, spaces like the Game Room
    and Maker Zone, printing and scanning in the libraries, and the branch libraries.
    Not for opening hours (use get_library_hours) or which devices you can borrow
    (use list_library_equipment)."""
    return data.search("libraries", query)


@tool
def get_library_hours(location: str | None = None) -> list[Passage]:
    """Get a Texas A&M library's opening hours for this week and next, live from the
    Libraries' hours calendar, with today's date marked. `location` is a name like
    'Evans', 'Evans Annex', 'West Campus Library', 'Medical Sciences Library',
    'Cushing', 'Williams Library' (Galveston) or a service like 'Maker Zone' or
    'AskUs chat'; leave it out for every library. Hours change for holidays and
    breaks, so use this for any 'is it open', 'when does it close' or 'hours' question."""
    return libcal.library_hours(location)


@tool
def list_library_equipment(category: str, location: str | None = None) -> list[Passage]:
    """List the devices students can borrow from the Libraries' Tech Bars (Evans
    Library Annex and West Campus Library), live from their equipment catalog, with
    the page to reserve them. `category` is a kind of device like 'calculators',
    'chromebooks', 'laptops', 'cameras', 'chargers', 'projectors' or 'microphones',
    or a model like 'TI-84'. `location` is 'Evans Annex' or 'West Campus Library';
    leave it out for both. It can't tell whether one is free right now. Not for loan
    rules or late fees (use search_libraries)."""
    return libcal.library_equipment(category, location)


TOOLS = [search_libraries, get_library_hours, list_library_equipment]
