from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

REQUIRED_ENVIRONMENT = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "RESTIC_REPOSITORY",
    "RESTIC_PASSWORD_FILE",
)


def require_environment() -> None:
    """Ensure that all Restic secrets are available."""

    missing = [
        name
        for name in REQUIRED_ENVIRONMENT
        if not os.environ.get(name, "").strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


def run_command(
    *,
    command: Sequence[str],
    label: str,
    timeout: int = 7200,
) -> None:
    """Run one Restic command and stream its result."""

    print()
    print(f"[{label}]")
    print(f"$ {shlex.join(command)}")

    result = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )

    if result.stdout.strip():
        print(result.stdout.rstrip())

    if result.stderr.strip():
        print(result.stderr.rstrip())

    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code "
            f"{result.returncode}."
        )


def find_latest_dump(
    backup_directory: Path,
    filename_prefix: str,
) -> Path:
    """Return the newest local PostgreSQL dump."""

    dumps = sorted(
        backup_directory.glob(
            f"{filename_prefix}_*.dump"
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    if not dumps:
        raise RuntimeError(
            "No PostgreSQL dumps found in "
            f"{backup_directory}."
        )

    return dumps[0]


def sha256_digest(
    path: Path,
) -> str:
    """Calculate a SHA-256 digest."""

    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        while chunk := input_file.read(
            1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def verify_checksum(
    dump_path: Path,
) -> Path:
    """Validate the local checksum before upload."""

    checksum_path = dump_path.with_suffix(
        dump_path.suffix + ".sha256"
    )

    if not checksum_path.is_file():
        raise RuntimeError(
            f"Missing checksum: {checksum_path}"
        )

    checksum_line = checksum_path.read_text(
        encoding="utf-8"
    ).strip()

    parts = checksum_line.split(maxsplit=1)

    if len(parts) != 2:
        raise RuntimeError(
            "Invalid checksum file format."
        )

    expected_digest = parts[0].lower()

    referenced_filename = (
        parts[1]
        .strip()
        .lstrip("*")
    )

    if referenced_filename != dump_path.name:
        raise RuntimeError(
            "Checksum references a different dump."
        )

    actual_digest = sha256_digest(
        dump_path
    ).lower()

    if actual_digest != expected_digest:
        raise RuntimeError(
            "Local dump checksum verification failed."
        )

    return checksum_path


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Upload the newest validated PostgreSQL "
            "dump to an encrypted Restic repository."
        )
    )

    parser.add_argument(
        "--backup-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--filename-prefix",
        default="quant_research",
    )

    parser.add_argument(
        "--restic-binary",
        default="/usr/bin/restic",
    )

    parser.add_argument(
        "--host",
        default="quant-research-vps",
    )

    parser.add_argument(
        "--keep-daily",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--keep-weekly",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--keep-monthly",
        type=int,
        default=12,
    )

    return parser


def main() -> int:
    """Upload, retain and verify the offsite backup."""

    arguments = build_parser().parse_args()

    require_environment()

    backup_directory = (
        arguments.backup_dir
        .expanduser()
        .resolve()
    )

    if not backup_directory.is_dir():
        raise RuntimeError(
            "Backup directory does not exist: "
            f"{backup_directory}"
        )

    dump_path = find_latest_dump(
        backup_directory=backup_directory,
        filename_prefix=(
            arguments.filename_prefix
        ),
    )

    checksum_path = verify_checksum(
        dump_path
    )

    print("Encrypted offsite PostgreSQL backup")
    print(f"Dump: {dump_path}")
    print(f"Checksum: {checksum_path}")
    print("Local checksum verification: passed")

    run_command(
        label="Restic backup",
        command=[
            arguments.restic_binary,
            "backup",
            "--host",
            arguments.host,
            "--tag",
            "postgresql",
            str(dump_path),
            str(checksum_path),
        ],
    )

    run_command(
        label="Restic retention and prune",
        command=[
            arguments.restic_binary,
            "forget",
            "--host",
            arguments.host,
            "--tag",
            "postgresql",
            "--keep-daily",
            str(arguments.keep_daily),
            "--keep-weekly",
            str(arguments.keep_weekly),
            "--keep-monthly",
            str(arguments.keep_monthly),
            "--prune",
        ],
    )

    run_command(
        label="Restic repository check",
        command=[
            arguments.restic_binary,
            "check",
        ],
    )

    print()
    print(
        "Encrypted offsite backup completed "
        "successfully."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
