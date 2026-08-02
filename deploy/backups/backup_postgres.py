from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path


def format_command(
    command: Sequence[str],
) -> str:
    """Format a command for readable error output."""

    return " ".join(command)


def command_error(
    label: str,
    command: Sequence[str],
    return_code: int,
    stderr: bytes,
) -> RuntimeError:
    """Build a useful subprocess error."""

    decoded_stderr = stderr.decode(
        "utf-8",
        errors="replace",
    ).strip()

    message = (
        f"{label} failed with exit code "
        f"{return_code}.\n"
        f"Command: {format_command(command)}"
    )

    if decoded_stderr:
        message += (
            "\nRecent error output:\n"
            f"{decoded_stderr[-4000:]}"
        )

    return RuntimeError(message)


def create_database_dump(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    database_user: str,
    database_name: str,
    output_path: Path,
) -> None:
    """Create one PostgreSQL custom-format dump."""

    command = [
        docker_binary,
        "compose",
        "exec",
        "-T",
        compose_service,
        "pg_dump",
        "-U",
        database_user,
        "-d",
        database_name,
        "--format=custom",
        "--no-owner",
        "--no-acl",
    ]

    with output_path.open("wb") as output_file:
        result = subprocess.run(
            command,
            cwd=project_directory,
            stdout=output_file,
            stderr=subprocess.PIPE,
            check=False,
            timeout=7200,
        )

        output_file.flush()
        os.fsync(output_file.fileno())

    if result.returncode != 0:
        raise command_error(
            label="PostgreSQL dump",
            command=command,
            return_code=result.returncode,
            stderr=result.stderr,
        )

    if output_path.stat().st_size == 0:
        raise RuntimeError(
            "PostgreSQL created an empty dump file."
        )


def verify_database_dump(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    dump_path: Path,
) -> None:
    """Verify that pg_restore can read the archive."""

    command = [
        docker_binary,
        "compose",
        "exec",
        "-T",
        compose_service,
        "pg_restore",
        "--list",
    ]

    with dump_path.open("rb") as input_file:
        result = subprocess.run(
            command,
            cwd=project_directory,
            stdin=input_file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=600,
        )

    if result.returncode != 0:
        raise command_error(
            label="PostgreSQL archive verification",
            command=command,
            return_code=result.returncode,
            stderr=result.stderr,
        )


def sha256_digest(
    path: Path,
) -> str:
    """Calculate a SHA-256 digest without loading the file at once."""

    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        while chunk := input_file.read(
            1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_checksum(
    dump_path: Path,
) -> Path:
    """Write a sha256sum-compatible sidecar file."""

    checksum_path = dump_path.with_suffix(
        dump_path.suffix + ".sha256"
    )

    temporary_path = checksum_path.with_suffix(
        checksum_path.suffix + ".partial"
    )

    digest = sha256_digest(dump_path)

    temporary_path.write_text(
        f"{digest}  {dump_path.name}\n",
        encoding="utf-8",
    )

    with temporary_path.open("rb") as input_file:
        os.fsync(input_file.fileno())

    temporary_path.replace(checksum_path)

    return checksum_path


def enforce_retention(
    *,
    backup_directory: Path,
    filename_prefix: str,
    retention_count: int,
) -> list[Path]:
    """Keep only the newest requested number of dumps."""

    dump_files = sorted(
        backup_directory.glob(
            f"{filename_prefix}_*.dump"
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    removed: list[Path] = []

    for dump_path in dump_files[
        retention_count:
    ]:
        checksum_path = dump_path.with_suffix(
            dump_path.suffix + ".sha256"
        )

        dump_path.unlink(missing_ok=True)
        checksum_path.unlink(missing_ok=True)

        removed.append(dump_path)

    return removed


def build_parser() -> argparse.ArgumentParser:
    """Build the backup command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Create and verify a retained PostgreSQL "
            "backup for the Quant Research Platform."
        )
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--backup-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--database",
        required=True,
    )

    parser.add_argument(
        "--database-user",
        required=True,
    )

    parser.add_argument(
        "--compose-service",
        default="db",
    )

    parser.add_argument(
        "--retention-count",
        type=int,
        default=14,
    )

    parser.add_argument(
        "--filename-prefix",
        default="quant_research",
    )

    parser.add_argument(
        "--docker-binary",
        default="/usr/bin/docker",
    )

    return parser


def main() -> int:
    """Create, verify and retain a database backup."""

    arguments = build_parser().parse_args()

    project_directory = (
        arguments.project_dir.expanduser().resolve()
    )

    backup_directory = (
        arguments.backup_dir.expanduser().resolve()
    )

    if not project_directory.is_dir():
        raise RuntimeError(
            "Project directory does not exist: "
            f"{project_directory}"
        )

    if arguments.retention_count < 1:
        raise RuntimeError(
            "retention-count must be at least 1."
        )

    backup_directory.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )

    timestamp = datetime.now(
        UTC
    ).strftime("%Y%m%dT%H%M%SZ")

    filename = (
        f"{arguments.filename_prefix}_"
        f"{timestamp}.dump"
    )

    final_dump_path = (
        backup_directory / filename
    )

    partial_dump_path = final_dump_path.with_suffix(
        final_dump_path.suffix + ".partial"
    )

    partial_dump_path.unlink(missing_ok=True)

    print(
        "Creating PostgreSQL backup:"
        f"\n  Database: {arguments.database}"
        f"\n  Destination: {final_dump_path}"
    )

    try:
        create_database_dump(
            docker_binary=arguments.docker_binary,
            project_directory=project_directory,
            compose_service=arguments.compose_service,
            database_user=arguments.database_user,
            database_name=arguments.database,
            output_path=partial_dump_path,
        )

        verify_database_dump(
            docker_binary=arguments.docker_binary,
            project_directory=project_directory,
            compose_service=arguments.compose_service,
            dump_path=partial_dump_path,
        )

        partial_dump_path.replace(
            final_dump_path
        )

        checksum_path = write_checksum(
            final_dump_path
        )

        removed_backups = enforce_retention(
            backup_directory=backup_directory,
            filename_prefix=(
                arguments.filename_prefix
            ),
            retention_count=(
                arguments.retention_count
            ),
        )

    except BaseException:
        partial_dump_path.unlink(
            missing_ok=True
        )
        raise

    size_megabytes = (
        final_dump_path.stat().st_size
        / 1024
        / 1024
    )

    print()
    print("Backup completed successfully.")
    print(f"Archive: {final_dump_path}")
    print(f"Checksum: {checksum_path}")
    print(f"Size: {size_megabytes:.2f} MiB")
    print("Archive verification: passed")
    print(
        "Retention limit: "
        f"{arguments.retention_count}"
    )
    print(
        "Older backups removed: "
        f"{len(removed_backups)}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
