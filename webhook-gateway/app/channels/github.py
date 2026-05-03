"""GitHub webhook channel adapter.

Normalizes GitHub webhook payloads for push, pull request, issue,
and comment events into mem-dog's NormalizedMessage format.

Reference: https://docs.github.com/en/webhooks/webhook-events-and-payloads
"""

from __future__ import annotations

from typing import Any

from .base import BaseChannelAdapter, NormalizedMessage


class GitHubAdapter(BaseChannelAdapter):
    """Adapter for GitHub webhook payloads."""

    @property
    def channel_type(self) -> str:
        return "github"

    async def normalize(self, payload: dict[str, Any]) -> NormalizedMessage:
        action = payload.get("action", "")
        repo = payload.get("repository", {})
        sender = payload.get("sender", {})
        repo_name = repo.get("full_name", repo.get("name", ""))
        sender_name = sender.get("login", "")

        text_parts = []
        event_type = ""
        message_id = ""
        attachments: list[dict[str, Any]] = []

        # Push event (commits)
        if "commits" in payload and "ref" in payload:
            event_type = "push"
            ref = payload.get("ref", "").replace("refs/heads/", "")
            commits = payload.get("commits", [])
            text_parts.append(f"Push to {repo_name}/{ref} by {sender_name}")
            text_parts.append(f"{len(commits)} commit(s):")
            for commit in commits[:10]:
                sha = commit.get("id", "")[:7]
                msg = commit.get("message", "").split("\n")[0]
                author = commit.get("author", {}).get("name", "")
                text_parts.append(f"  {sha} {msg} ({author})")
                # Track modified files
                files = commit.get("added", []) + commit.get("modified", []) + commit.get("removed", [])
                if files:
                    text_parts.append(f"    Files: {', '.join(files[:5])}")
            message_id = payload.get("after", "")

        # Pull request
        elif "pull_request" in payload:
            event_type = "pull_request"
            pr = payload.get("pull_request", {})
            pr_number = pr.get("number", "")
            title = pr.get("title", "")
            body = pr.get("body", "") or ""
            state = pr.get("state", "")
            merged = pr.get("merged", False)
            head = pr.get("head", {}).get("ref", "")
            base = pr.get("base", {}).get("ref", "")

            status = "merged" if merged else f"{action} ({state})"
            text_parts.append(f"PR #{pr_number} {status}: {title}")
            text_parts.append(f"Branch: {head} → {base}")
            if body:
                text_parts.append(f"\n{body[:500]}")
            message_id = str(pr.get("id", ""))

        # Issue
        elif "issue" in payload and "pull_request" not in payload.get("issue", {}):
            event_type = "issue"
            issue = payload.get("issue", {})
            number = issue.get("number", "")
            title = issue.get("title", "")
            body = issue.get("body", "") or ""
            state = issue.get("state", "")
            labels = [l.get("name", "") for l in issue.get("labels", []) if isinstance(l, dict)]

            text_parts.append(f"Issue #{number} {action}: {title}")
            if labels:
                text_parts.append(f"Labels: {', '.join(labels)}")
            if body and action == "opened":
                text_parts.append(f"\n{body[:500]}")
            message_id = str(issue.get("id", ""))

        # Issue/PR comment
        elif "comment" in payload:
            event_type = "comment"
            comment = payload.get("comment", {})
            comment_body = comment.get("body", "")
            issue = payload.get("issue", {})
            number = issue.get("number", "")
            title = issue.get("title", "")
            is_pr = "pull_request" in issue

            prefix = "PR" if is_pr else "Issue"
            text_parts.append(f"Comment on {prefix} #{number}: {title}")
            text_parts.append(f"By {sender_name}:")
            text_parts.append(comment_body[:1000])
            message_id = str(comment.get("id", ""))

        # Release
        elif "release" in payload:
            event_type = "release"
            release = payload.get("release", {})
            tag = release.get("tag_name", "")
            name = release.get("name", "")
            body = release.get("body", "") or ""

            text_parts.append(f"Release {action}: {name} ({tag})")
            if body:
                text_parts.append(f"\n{body[:500]}")
            message_id = str(release.get("id", ""))

        # Fallback
        else:
            event_type = action or "unknown"
            text_parts.append(f"GitHub event: {event_type} on {repo_name}")

        return NormalizedMessage(
            channel_type="github",
            channel_id=repo_name,
            peer_id=sender_name,
            message_id=message_id,
            user_id=str(sender.get("id", sender_name)),
            text="\n".join(text_parts),
            attachments=attachments,
            source_type="code",
            raw=payload,
            extra={
                "event_type": event_type,
                "action": action,
                "repo": repo_name,
                "sender": sender_name,
            },
        )
