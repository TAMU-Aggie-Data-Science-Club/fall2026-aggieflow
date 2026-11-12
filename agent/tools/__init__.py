"""Tool groups. Each group runs in its own graph node.

To add a tool: write it in the right group's file and add it to that file's
TOOLS list. To add a group: make a new file and add it to GROUPS.
"""

from agent.tools import campus, courses, policy

GROUPS = {
    "policy_tools": policy.TOOLS,
    "course_tools": courses.TOOLS,
    "campus_tools": campus.TOOLS,
}

ALL_TOOLS = [t for tools in GROUPS.values() for t in tools]
GROUP_OF = {t.name: group for group, tools in GROUPS.items() for t in tools}
