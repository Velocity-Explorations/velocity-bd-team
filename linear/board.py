"""The Pursuits project of Velocity's Operations team on Linear: open an issue, move it, comment on it.

    board = LinearBoard(LinearClient())
    issue = board.open(title, body, due, priority, assignee_email)   # {"id", "identifier", "url"}, or None
    board.move(issue["id"], "In Progress")
    board.comment(issue["id"], "Marked Submitted ...")

The team, the project and its states are looked up once per board, by the team's key, the project's name and each
state's name; a person by their email, once each. A failed call returns None or False and is logged by the client.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)

TEAM_KEY = "OPS"
PROJECT = "Pursuits"
OPENED_IN = "Backlog"

TEAM = """query Team($key: String!) {
  teams(filter: {key: {eq: $key}}) { nodes { id states { nodes { id name } } } }
}"""
FIND_PROJECT = """query Project($name: String!) {
  projects(filter: {name: {eq: $name}}) { nodes { id teams { nodes { key } } } }
}"""
USER = """query User($email: String!) {
  users(filter: {email: {eq: $email}}) { nodes { id } }
}"""
OPEN = """mutation Open($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { id identifier url } }
}"""
MOVE = """mutation Move($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) { success }
}"""
COMMENT = """mutation Comment($input: CommentCreateInput!) {
  commentCreate(input: $input) { success }
}"""


class Client(Protocol):
    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any] | None: ...


def _nodes(data: dict[str, Any] | None, field: str) -> list[dict[str, Any]]:
    return list(((data or {}).get(field) or {}).get("nodes") or [])


class LinearBoard:
    def __init__(self, client: Client, team_key: str = TEAM_KEY, project: str = PROJECT) -> None:
        self.client = client
        self.team_key = team_key
        self.project = project
        self._ids: dict[str, Any] | None = None
        self._people: dict[str, str | None] = {}

    def _lookup(self) -> dict[str, Any] | None:
        """The team's id and states, and the project's id; looked up again only after a failure."""
        if self._ids is None:
            teams = _nodes(self.client.query(TEAM, {"key": self.team_key}), "teams")
            projects = _nodes(self.client.query(FIND_PROJECT, {"name": self.project}), "projects")
            project = next((p for p in projects
                            if any(t.get("key") == self.team_key for t in _nodes(p, "teams"))), None)
            if not teams or project is None:
                log.warning("Linear: no %s project in team %s", self.project, self.team_key)
                return None
            self._ids = {"team": teams[0]["id"], "project": project["id"],
                         "states": {s["name"]: s["id"] for s in _nodes(teams[0], "states")}}
        return self._ids

    def _person(self, email: str) -> str | None:
        if email not in self._people:
            found = _nodes(self.client.query(USER, {"email": email}), "users")
            self._people[email] = found[0]["id"] if found else None
        return self._people[email]

    def open(self, title: str, body: str, due: str | None, priority: int, assignee_email: str | None) -> dict[str, str] | None:
        ids = self._lookup()
        if ids is None or OPENED_IN not in ids["states"]:
            return None
        fields: dict[str, Any] = {"teamId": ids["team"], "projectId": ids["project"], "stateId": ids["states"][OPENED_IN],
                                  "title": title, "description": body, "priority": priority}
        if due:
            fields["dueDate"] = due
        assignee = self._person(assignee_email) if assignee_email else None
        if assignee:
            fields["assigneeId"] = assignee
        created = (self.client.query(OPEN, {"input": fields}) or {}).get("issueCreate") or {}
        issue = created.get("issue")
        if not created.get("success") or not issue:
            return None
        return {key: str(issue[key]) for key in ("id", "identifier", "url")}

    def move(self, issue_id: str, state: str) -> bool:
        state_id = ((self._lookup() or {}).get("states") or {}).get(state)
        if not state_id:
            log.warning("Linear: team %s has no state %s", self.team_key, state)
            return False
        updated = (self.client.query(MOVE, {"id": issue_id, "input": {"stateId": state_id}}) or {}).get("issueUpdate") or {}
        return bool(updated.get("success"))

    def comment(self, issue_id: str, body: str) -> bool:
        created = (self.client.query(COMMENT, {"input": {"issueId": issue_id, "body": body}}) or {}).get("commentCreate") or {}
        return bool(created.get("success"))
