#!/usr/bin/env python3

import argparse
import html
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


class SessionExportError(RuntimeError):
    """Raised when a session cannot be exported or converted."""


INTERNAL_FIELDS = {
    "info",
    "tokens",
    "cost",
    "metadata",
    "reasoningEncryptedContent",
    "messageID",
    "sessionID",
    "type",
    "time",
}
NON_CONSTRUCTIVE_PART_TYPES = {"step-start", "step-finish", "tool", "reasoning"}


def is_non_constructive_part(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    part_type = value.get("type")
    return part_type in NON_CONSTRUCTIVE_PART_TYPES


def clean_value(value: Any, *, is_part: bool = False) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            if key in INTERNAL_FIELDS or (is_part and key == "id"):
                continue

            if key == "parts" and isinstance(child, list):
                cleaned_parts = []
                for part in child:
                    if is_non_constructive_part(part):
                        continue
                    cleaned_part = clean_value(part, is_part=True)
                    if cleaned_part != {}:
                        cleaned_parts.append(cleaned_part)
                if cleaned_parts:
                    cleaned[key] = cleaned_parts
            else:
                cleaned_child = clean_value(child)
                if cleaned_child != {}:
                    cleaned[key] = cleaned_child
        return cleaned

    if isinstance(value, list):
        return [
            cleaned_child
            for child in value
            if (cleaned_child := clean_value(child)) != {}
        ]

    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export an OpenCode session to a JSON or RTF document, "
            "optionally cleaned."
        ),
    )
    parser.add_argument(
        "session_id",
        nargs="?",
        help="OpenCode session ID, such as ses_... (optional)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path (default: <session-id>.<format>)",
    )
    parser.add_argument(
        "--format",
        choices=("rtf", "json"),
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Ask OpenCode to redact sensitive transcript and file data",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove internal fields, reasoning, and non-constructive parts locally",
    )
    return parser.parse_args()


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise SessionExportError(f"Required command not found: {command}")


def list_latest_sessions() -> None:
    result = subprocess.run(
        ["opencode", "session", "list", "--max-count", "10", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip()
        raise SessionExportError(detail or "Unable to list OpenCode sessions")

    if not result.stdout.strip():
        print("No OpenCode sessions found in this directory.")
        return

    try:
        sessions = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SessionExportError(f"OpenCode returned invalid session data: {error}") from error

    if not isinstance(sessions, list):
        raise SessionExportError("OpenCode returned an invalid session list")

    print("Latest OpenCode sessions:")
    for session in sessions:
        if not isinstance(session, dict):
            continue
        session_id = session.get("id", "unknown")
        title = session.get("title", "Untitled")
        print(f"{session_id}  {title}")


def export_session(session_id: str, sanitize: bool) -> dict[str, Any]:
    command = ["opencode", "export"]
    if sanitize:
        command.append("--sanitize")
    command.append(session_id)

    exported: object | None = None
    decode_error: json.JSONDecodeError | None = None
    for attempt in range(3):
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as export_file:
            result = subprocess.run(
                command,
                stdout=export_file,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                detail = result.stderr.strip()
                raise SessionExportError(detail or "OpenCode export failed")

            export_file.seek(0)
            try:
                exported = json.load(export_file)
                break
            except json.JSONDecodeError as error:
                decode_error = error
                if attempt < 2:
                    time.sleep(0.25)

    if exported is None:
        raise SessionExportError(
            f"OpenCode repeatedly returned invalid JSON: {decode_error}"
        )

    if not isinstance(exported, dict):
        raise SessionExportError("OpenCode export did not return a JSON object")
    return exported


def pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def render_part(part: object, cleanup: bool = False) -> str:
    if not isinstance(part, dict):
        return f"<pre>{html.escape(pretty_json(part))}</pre>"

    part_type = str(part.get("type", "unknown"))
    display_part = clean_value(part, is_part=True) if cleanup else part
    if display_part == {}:
        return ""

    if part_type == "text" or (
        cleanup and isinstance(display_part, dict) and "text" in display_part
    ):
        text = display_part.get("text", "") if isinstance(display_part, dict) else ""
        return f'<div class="text">{html.escape(str(text))}</div>'

    if part_type == "tool":
        tool = html.escape(str(part.get("tool", "unknown")))
        state_value = (
            display_part.get("state", {})
            if isinstance(display_part, dict)
            else {}
        )
        state = html.escape(pretty_json(state_value))
        return f"<h3>Tool: {tool}</h3><pre>{state}</pre>"

    payload_source = display_part if isinstance(display_part, dict) else part
    payload = {
        key: value for key, value in payload_source.items() if key not in {"type"}
    }
    return (
        f'<details open><summary>{html.escape(part_type)}</summary>'
        f"<pre>{html.escape(pretty_json(payload))}</pre></details>"
    )


def render_html(session: dict[str, Any], cleanup: bool = False) -> str:
    info = session.get("info", {})
    title = (
        info.get("title", info.get("id", "OpenCode session"))
        if isinstance(info, dict)
        else "OpenCode session"
    )
    sections: list[str] = []

    messages = session.get("messages", [])
    if not isinstance(messages, list):
        raise SessionExportError("OpenCode export has an invalid messages field")

    for message in messages:
        if not isinstance(message, dict):
            continue
        message_info = message.get("info", {})
        role = (
            message_info.get("role", "unknown")
            if isinstance(message_info, dict)
            else "unknown"
        )
        parts = message.get("parts", [])
        if isinstance(parts, list):
            rendered_parts = "".join(
                render_part(part, cleanup=cleanup)
                for part in parts
                if not (cleanup and is_non_constructive_part(part))
            )
        else:
            rendered_parts = ""
        sections.append(
            f'<section class="message {html.escape(str(role))}">'
            f"<h2>{html.escape(str(role).upper())}</h2>{rendered_parts}</section>"
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(str(title))}</title>
<style>
body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 40px; color: #202124; }}
h1 {{ border-bottom: 2px solid #d0d7de; padding-bottom: 12px; }}
h2 {{ color: #44546a; margin-top: 28px; }}
h3 {{ margin-bottom: 6px; }}
.message {{ border-left: 4px solid #d0d7de; margin: 24px 0; padding-left: 18px; }}
.user {{ border-left-color: #0969da; }}
.assistant {{ border-left-color: #1a7f37; }}
.text {{ white-space: pre-wrap; line-height: 1.45; }}
pre {{ background: #f6f8fa; border: 1px solid #d0d7de; padding: 12px; white-space: pre-wrap; }}
summary {{ font-weight: bold; margin: 10px 0 6px; }}
</style>
</head>
<body>
<h1>{html.escape(str(title))}</h1>
{''.join(sections)}
</body>
</html>
"""


def convert_to_rtf(document: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="opencode-session-") as temp_directory:
        html_path = Path(temp_directory) / "session.html"
        html_path.write_text(document, encoding="utf-8")
        result = subprocess.run(
            [
                "textutil",
                "-convert",
                "rtf",
                "-inputencoding",
                "UTF-8",
                "-output",
                str(output_path),
                str(html_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise SessionExportError(detail or "RTF conversion failed")


def write_json(session: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pretty_json(session) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        require_command("opencode")
        if args.session_id is None:
            list_latest_sessions()
            return 0

        if args.format == "rtf":
            require_command("textutil")
        session = export_session(args.session_id, args.sanitize)
    except (OSError, SessionExportError) as error:
        if args.session_id is not None:
            print(f"Session export failed: {error}", file=sys.stderr)
            try:
                list_latest_sessions()
            except (OSError, SessionExportError) as list_error:
                print(f"Unable to list sessions: {list_error}", file=sys.stderr)
                return 1
            return 2
        print(f"error: {error}", file=sys.stderr)
        return 1

    extension = "json" if args.format == "json" else "rtf"
    output_path = (
        args.output or Path(f"{args.session_id}.{extension}")
    ).expanduser().resolve()

    try:
        if args.format == "json":
            if args.cleanup:
                session = clean_value(session)
            write_json(session, output_path)
        else:
            convert_to_rtf(render_html(session, cleanup=args.cleanup), output_path)
    except (OSError, SessionExportError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
