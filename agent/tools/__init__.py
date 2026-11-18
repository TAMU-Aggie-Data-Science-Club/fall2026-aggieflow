"""Tool groups. Each group runs in its own graph node.

Each tool does one job, and every passage is reachable through exactly one tool.
To add a tool: write it in the right group's file and add it to that file's
TOOLS list. To add a group: make a new file and add it to GROUPS.
"""

from agent.tools import courses, policy

GROUPS = {
    "policy_tools": policy.TOOLS,
    "course_tools": courses.TOOLS,
}

ALL_TOOLS = [t for tools in GROUPS.values() for t in tools]
GROUP_OF = {t.name: group for group, tools in GROUPS.items() for t in tools}
