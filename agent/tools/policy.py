"""policy_tools: keyword search over one collected source each.

Each tool searches exactly one source, so the model picks by topic and no
passage can be found by two tools. Course pages from the catalog are left out
of search_degree_plans; get_course finds those.
"""

from langchain_core.tools import tool

from agent import data
from agent.state import Passage


@tool
def search_student_rules(query: str) -> list[Passage]:
    """Search the Texas A&M Student Rules: Q-drops, excused absences and
    make-up work, grading and grade notations, final exams, academic standing,
    student conduct and campus behavior rules (animals in buildings, skateboards).
    Not for dates or deadlines, including the Q-drop deadline, or for graduation
    ceremonies (use search_registrar)."""
    return data.search("student-rules", query)


@tool
def search_registrar(query: str) -> list[Passage]:
    """Search the Registrar's pages: registration, the academic calendar and
    deadlines (add/drop, Q-drop, withdrawal, finals), transcripts, enrollment
    verification, graduation, commencement ceremonies (tickets, guests, Reed
    Arena) and diplomas, residency and records. Not for the rules themselves, like how many Q-drops
    you get (use search_student_rules)."""
    return data.search("registrar", query)


@tool
def search_tech_help(query: str) -> list[Passage]:
    """Search Technology Services (IT) help: Wi-Fi and VPN, NetID and accounts,
    email, software for students, printing (AggiePrint) and open access labs,
    IT security and policy."""
    return data.search("oal", query)


@tool
def search_degree_plans(query: str) -> list[Passage]:
    """Search the Texas A&M catalog for degree plans and program requirements,
    majors, minors and certificates, the core curriculum, the International and
    Cultural Diversity (ICD) and Cultural Discourse (CD) lists and which courses
    count for them, and catalog-wide academic policies. Not for one course's description or prerequisites
    (use get_course)."""
    return data.search("catalog", query)


@tool
def search_transportation(query: str) -> list[Passage]:
    """Search Transportation Services: parking permits, lots and garages,
    night, break and visitor parking, citations and appeals, accessible
    parking, AggieSpirit bus service and how to ride, gameday parking and
    shuttles, bikes, scooters and EV charging. Not for live bus arrival times
    or open garage spaces right now (we don't have them), or for the Student
    Rules' conduct and appeals panels (use search_student_rules)."""
    return data.search("transportation", query)


TOOLS = [search_student_rules, search_registrar, search_tech_help, search_degree_plans,
         search_transportation]
