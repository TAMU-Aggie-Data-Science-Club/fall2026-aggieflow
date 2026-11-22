"""course_tools: exact lookups for one course.

Course tools take the course the same way, a code like 'CSCE 121'. Data comes
from the catalog and anex.us collectors, and live from RateMyProfessors
(see agent/data.py).
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
    easiest professor'. The easiest professor has the HIGHEST average GPA. `course` is a code like 'MATH 151'.
    For 'who should I take' or 'best professor', also call
    get_professor_ratings for the top 3 professors by GPA."""
    return data.grades(course)


@tool
def get_professor_grades(course: str, professor: str) -> list[Passage]:
    """Get one professor's grade history in one course from anex.us, semester
    by semester since 2023. `course` is a code like 'CHEM 107'; `professor` is
    a last name like 'Martinez'. To compare professors, use get_course_grades.
    If the name isn't found it may be misspelled: call get_course_grades to see
    the exact names of the course's professors. For 'is X good for this course'
    or 'is X a tough grader', also call get_professor_ratings."""
    return data.professor_grades(course, professor)


@tool
def get_professor_ratings(professor: str) -> list[Passage]:
    """Get what students say about a Texas A&M professor on RateMyProfessors:
    overall quality, difficulty, percent who would take them again, and their
    newest reviews (each with the course it was for). Use for 'is this
    professor good', 'how do they teach', 'would people take them again', and
    for choosing between professors. `professor` is a name like 'Leyk'
    or 'Teresa Leyk'; several professors may match, so check the department.
    When the question names a course, also call get_professor_grades (one
    professor) or get_course_grades (choosing one), unless it only asks how
    they teach."""
    return data.professor_ratings(professor)


TOOLS = [get_course, get_course_grades, get_professor_grades, get_professor_ratings]
