"""course_tools: exact lookups for one course.

Every tool takes the course the same way, a code like 'CSCE 121'. Data comes
from the catalog and anex.us collectors (see agent/data.py).
"""

from langchain_core.tools import tool

from agent import data
from agent.state import Passage


@tool
def get_course(course: str) -> list[Passage]:
    """Get one course's catalog entry: title, credit hours, description and
    prerequisites. `course` is a code like 'CSCE 121'. Not for grades (use
    get_course_grades) or degree requirements (use search_degree_plans)."""
    return data.course(course)


@tool
def get_course_grades(course: str) -> list[Passage]:
    """Get a course's past grade distribution from anex.us across all
    professors: average GPA, percent A's, Q-drop rate, and professors ranked
    by average GPA since 2023. Use for 'is this class hard' or 'who's the
    easiest professor'. `course` is a code like 'MATH 151'."""
    return data.grades(course)


@tool
def get_professor_grades(course: str, professor: str) -> list[Passage]:
    """Get one professor's grade history in one course from anex.us, semester
    by semester since 2023. `course` is a code like 'CHEM 107'; `professor` is
    a last name like 'Martinez'. To compare professors, use get_course_grades."""
    return data.professor_grades(course, professor)


TOOLS = [get_course, get_course_grades, get_professor_grades]
