from __future__ import annotations

import argparse
import os
import smtplib
import socket
import ssl
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

DEFAULT_SERVICE_UNIT = (
    "quant-research-refresh.service"
)


def load_environment_file(
    path: Path,
) -> None:
    """Load a simple KEY=VALUE environment file."""

    for line_number, raw_line in enumerate(
        path.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if not separator:
            raise ValueError(
                f"Invalid environment entry at "
                f"{path}:{line_number}."
            )

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def required_environment(
    name: str,
) -> str:
    """Return a required environment variable."""

    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Required environment variable "
            f"{name} is missing."
        )

    return value


def command_output(
    command: Sequence[str],
) -> str:
    """Run a diagnostic command without raising."""

    result = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    output = "\n".join(
        part.strip()
        for part in (
            result.stdout,
            result.stderr,
        )
        if part.strip()
    )

    if not output:
        output = (
            f"Command returned exit code "
            f"{result.returncode} without output."
        )

    return output


def service_status(
    service_unit: str,
) -> str:
    """Return relevant systemd service properties."""

    return command_output(
        [
            "/usr/bin/systemctl",
            "show",
            service_unit,
            "--no-pager",
            "--property=Result",
            "--property=ExecMainCode",
            "--property=ExecMainStatus",
            "--property=ActiveEnterTimestamp",
            "--property=InactiveEnterTimestamp",
        ]
    )


def service_journal(
    service_unit: str,
) -> str:
    """Return the most recent service journal lines."""

    return command_output(
        [
            "/usr/bin/journalctl",
            "-u",
            service_unit,
            "-n",
            "120",
            "--no-pager",
            "--output=short-iso",
        ]
    )


def parse_recipients(
    value: str,
) -> list[str]:
    """Parse comma-separated email recipients."""

    recipients = [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]

    if not recipients:
        raise RuntimeError(
            "ALERT_EMAIL_TO contains no recipients."
        )

    return recipients


def send_email(
    subject: str,
    body: str,
) -> None:
    """Send an SMTP email."""

    smtp_host = os.environ.get(
        "SMTP_HOST",
        "smtp.gmail.com",
    )

    smtp_port = int(
        os.environ.get(
            "SMTP_PORT",
            "465",
        )
    )

    smtp_username = required_environment(
        "SMTP_USERNAME"
    )
    smtp_password = required_environment(
        "SMTP_PASSWORD"
    )

    sender = os.environ.get(
        "ALERT_EMAIL_FROM",
        smtp_username,
    ).strip()

    recipients = parse_recipients(
        required_environment(
            "ALERT_EMAIL_TO"
        )
    )

    timeout = float(
        os.environ.get(
            "SMTP_TIMEOUT_SECONDS",
            "20",
        )
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    context = ssl.create_default_context()

    if smtp_port == 465:
        with smtplib.SMTP_SSL(
            smtp_host,
            smtp_port,
            timeout=timeout,
            context=context,
        ) as smtp:
            smtp.login(
                smtp_username,
                smtp_password,
            )
            smtp.send_message(message)

        return

    with smtplib.SMTP(
        smtp_host,
        smtp_port,
        timeout=timeout,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(
            smtp_username,
            smtp_password,
        )
        smtp.send_message(message)


def service_label(
    service_unit: str,
) -> str:
    """Return a readable component label."""

    labels = {
        "quant-research-refresh.service": (
            "Data refresh"
        ),
        "quant-research-backup.service": (
            "PostgreSQL backup and restore validation"
        ),
    }

    return labels.get(
        service_unit,
        service_unit,
    )


def build_failure_message(
    service_unit: str,
) -> tuple[str, str]:
    """Build the production alert email."""

    hostname = socket.gethostname()

    subject_prefix = os.environ.get(
        "ALERT_SUBJECT_PREFIX",
        "[Quant Research]",
    ).strip()

    component = service_label(
        service_unit
    )

    subject = (
        f"{subject_prefix} {component} failed "
        f"on {hostname}"
    )

    timestamp = datetime.now(
        UTC
    ).isoformat()

    body = f"""Quant Research Platform failure detected.

Component: {component}
Host: {hostname}
Service: {service_unit}
Detected at: {timestamp}

SYSTEMD STATUS
--------------
{service_status(service_unit)}

RECENT JOURNAL
--------------
{service_journal(service_unit)}

Suggested checks
----------------
1. systemctl status {service_unit}
2. journalctl -u {service_unit} -n 200 --no-pager
3. docker compose ps
4. Check the newest backup and checksum files
5. Check whether the temporary restore database remains
"""

    return subject, body


def build_test_message() -> tuple[str, str]:
    """Build a harmless test notification."""

    hostname = socket.gethostname()

    subject_prefix = os.environ.get(
        "ALERT_SUBJECT_PREFIX",
        "[Quant Research]",
    ).strip()

    subject = (
        f"{subject_prefix} Test notification "
        f"from {hostname}"
    )

    body = f"""This is a test notification from the
Quant Research Platform.

Host: {hostname}
Sent at: {
    datetime.now(UTC).isoformat()
}

SMTP notification delivery is working.
"""

    return subject, body


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Send a Quant Research Platform "
            "failure notification."
        )
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a harmless test message.",
    )

    parser.add_argument(
        "--env-file",
        type=Path,
        help=(
            "Optional environment file used for "
            "manual testing."
        ),
    )

    parser.add_argument(
        "--service-unit",
        default=DEFAULT_SERVICE_UNIT,
        help="systemd unit whose status is included.",
    )

    return parser


def main() -> int:
    """Send the requested notification."""

    arguments = build_parser().parse_args()

    if arguments.env_file is not None:
        load_environment_file(
            arguments.env_file
        )

    if arguments.test:
        subject, body = build_test_message()
    else:
        subject, body = build_failure_message(
            arguments.service_unit
        )

    send_email(
        subject=subject,
        body=body,
    )

    print(
        f"Notification email sent: {subject}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
