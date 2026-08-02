from __future__ import annotations

import argparse
import hashlib
import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

REQUIRED_TABLES = (
    "alembic_version",
    "companies",
    "filings",
    "financial_facts",
    "fiscal_periods",
    "normalized_financials",
    "normalized_financial_sources",
    "pipeline_runs",
)

SAFE_TEST_DATABASE_PREFIX = (
    "quant_research_restore_test"
)


def format_command(
    command: Sequence[str],
) -> str:
    """Format a command for diagnostic output."""

    return shlex.join(command)


def run_command(
    *,
    command: Sequence[str],
    working_directory: Path,
    label: str,
    input_path: Path | None = None,
) -> str:
    """Run one command and return decoded stdout."""

    if input_path is None:
        result = subprocess.run(
            list(command),
            cwd=working_directory,
            capture_output=True,
            check=False,
            timeout=7200,
        )
    else:
        with input_path.open("rb") as input_file:
            result = subprocess.run(
                list(command),
                cwd=working_directory,
                stdin=input_file,
                capture_output=True,
                check=False,
                timeout=7200,
            )

    stdout = result.stdout.decode(
        "utf-8",
        errors="replace",
    ).strip()

    stderr = result.stderr.decode(
        "utf-8",
        errors="replace",
    ).strip()

    if result.returncode != 0:
        message = (
            f"{label} failed with exit code "
            f"{result.returncode}.\n"
            f"Command: {format_command(command)}"
        )

        if stderr:
            message += (
                "\nRecent error output:\n"
                f"{stderr[-6000:]}"
            )

        raise RuntimeError(message)

    return stdout


def find_latest_dump(
    *,
    backup_directory: Path,
    filename_prefix: str,
) -> Path:
    """Return the newest matching database dump."""

    dumps = sorted(
        backup_directory.glob(
            f"{filename_prefix}_*.dump"
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    if not dumps:
        raise RuntimeError(
            "No PostgreSQL backup dumps were found "
            f"in {backup_directory}."
        )

    return dumps[0]


def sha256_digest(
    path: Path,
) -> str:
    """Calculate a file's SHA-256 digest."""

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
    """Validate the dump against its sidecar checksum."""

    checksum_path = dump_path.with_suffix(
        dump_path.suffix + ".sha256"
    )

    if not checksum_path.is_file():
        raise RuntimeError(
            "Checksum file is missing: "
            f"{checksum_path}"
        )

    checksum_line = checksum_path.read_text(
        encoding="utf-8"
    ).strip()

    parts = checksum_line.split(
        maxsplit=1
    )

    if len(parts) != 2:
        raise RuntimeError(
            "Checksum file has an invalid format: "
            f"{checksum_path}"
        )

    expected_digest = parts[0].lower()

    referenced_filename = (
        parts[1]
        .strip()
        .lstrip("*")
    )

    if referenced_filename != dump_path.name:
        raise RuntimeError(
            "Checksum references a different file. "
            f"Expected {dump_path.name}, found "
            f"{referenced_filename}."
        )

    actual_digest = sha256_digest(
        dump_path
    ).lower()

    if actual_digest != expected_digest:
        raise RuntimeError(
            "Backup checksum verification failed. "
            f"Expected {expected_digest}, found "
            f"{actual_digest}."
        )

    return checksum_path


def docker_compose_command(
    *,
    docker_binary: str,
    compose_service: str,
    arguments: Sequence[str],
) -> list[str]:
    """Build a non-interactive docker compose command."""

    return [
        docker_binary,
        "compose",
        "exec",
        "-T",
        compose_service,
        *arguments,
    ]


def drop_test_database(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    database_user: str,
    test_database: str,
) -> None:
    """Drop the temporary database if it exists."""

    command = docker_compose_command(
        docker_binary=docker_binary,
        compose_service=compose_service,
        arguments=[
            "dropdb",
            "-U",
            database_user,
            "--if-exists",
            "--force",
            test_database,
        ],
    )

    run_command(
        command=command,
        working_directory=project_directory,
        label="Dropping temporary database",
    )


def create_test_database(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    database_user: str,
    test_database: str,
) -> None:
    """Create an empty temporary restore database."""

    command = docker_compose_command(
        docker_binary=docker_binary,
        compose_service=compose_service,
        arguments=[
            "createdb",
            "-U",
            database_user,
            "--owner",
            database_user,
            "--template",
            "template0",
            test_database,
        ],
    )

    run_command(
        command=command,
        working_directory=project_directory,
        label="Creating temporary database",
    )


def restore_database(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    database_user: str,
    test_database: str,
    dump_path: Path,
) -> None:
    """Restore the dump into the temporary database."""

    command = docker_compose_command(
        docker_binary=docker_binary,
        compose_service=compose_service,
        arguments=[
            "pg_restore",
            "-U",
            database_user,
            "-d",
            test_database,
            "--exit-on-error",
            "--no-owner",
            "--no-acl",
        ],
    )

    run_command(
        command=command,
        working_directory=project_directory,
        label="Restoring PostgreSQL backup",
        input_path=dump_path,
    )


def query_database(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    database_user: str,
    database_name: str,
    sql: str,
) -> str:
    """Run one strict SQL query against a database."""

    command = docker_compose_command(
        docker_binary=docker_binary,
        compose_service=compose_service,
        arguments=[
            "psql",
            "-U",
            database_user,
            "-d",
            database_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-A",
            "-t",
            "-F",
            "|",
            "-c",
            sql,
        ],
    )

    return run_command(
        command=command,
        working_directory=project_directory,
        label="Restore validation query",
    )


def validate_restored_database(
    *,
    docker_binary: str,
    project_directory: Path,
    compose_service: str,
    database_user: str,
    test_database: str,
) -> tuple[str, dict[str, int]]:
    """Validate schema revision and central row counts."""

    count_statements = [
        (
            f"SELECT '{table_name}', "
            f"COUNT(*)::bigint "
            f"FROM {table_name}"
        )
        for table_name in REQUIRED_TABLES
    ]

    count_sql = (
        "\nUNION ALL\n".join(
            count_statements
        )
        + "\nORDER BY 1;"
    )

    output = query_database(
        docker_binary=docker_binary,
        project_directory=project_directory,
        compose_service=compose_service,
        database_user=database_user,
        database_name=test_database,
        sql=count_sql,
    )

    counts: dict[str, int] = {}

    for line in output.splitlines():
        name, separator, raw_count = (
            line.partition("|")
        )

        if not separator:
            raise RuntimeError(
                "Unexpected validation output: "
                f"{line}"
            )

        counts[name.strip()] = int(
            raw_count.strip()
        )

    missing_tables = [
        table_name
        for table_name in REQUIRED_TABLES
        if table_name not in counts
    ]

    if missing_tables:
        raise RuntimeError(
            "Restored database is missing validation "
            "results for: "
            + ", ".join(missing_tables)
        )

    empty_tables = [
        table_name
        for table_name in REQUIRED_TABLES
        if counts[table_name] < 1
    ]

    if empty_tables:
        raise RuntimeError(
            "Required restored tables are empty: "
            + ", ".join(empty_tables)
        )

    revision_output = query_database(
        docker_binary=docker_binary,
        project_directory=project_directory,
        compose_service=compose_service,
        database_user=database_user,
        database_name=test_database,
        sql=(
            "SELECT version_num "
            "FROM alembic_version;"
        ),
    )

    revisions = [
        line.strip()
        for line in revision_output.splitlines()
        if line.strip()
    ]

    if len(revisions) != 1:
        raise RuntimeError(
            "Expected exactly one Alembic revision, "
            f"found {len(revisions)}."
        )

    unvalidated_constraints_output = (
        query_database(
            docker_binary=docker_binary,
            project_directory=(
                project_directory
            ),
            compose_service=compose_service,
            database_user=database_user,
            database_name=test_database,
            sql=(
                "SELECT COUNT(*) "
                "FROM pg_constraint "
                "WHERE contype IN ('f', 'c') "
                "AND NOT convalidated;"
            ),
        )
    )

    unvalidated_constraints = int(
        unvalidated_constraints_output.strip()
    )

    if unvalidated_constraints != 0:
        raise RuntimeError(
            "The restored database contains "
            f"{unvalidated_constraints} "
            "unvalidated constraints."
        )

    return revisions[0], counts


def validate_database_name(
    *,
    production_database: str,
    test_database: str,
) -> None:
    """Protect the production database from mistakes."""

    if test_database == production_database:
        raise RuntimeError(
            "The test database must not equal the "
            "production database."
        )

    if not test_database.startswith(
        SAFE_TEST_DATABASE_PREFIX
    ):
        raise RuntimeError(
            "Unsafe test database name. It must start "
            f"with {SAFE_TEST_DATABASE_PREFIX!r}."
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Restore and validate the newest Quant "
            "Research PostgreSQL backup."
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
        "--production-database",
        required=True,
    )

    parser.add_argument(
        "--test-database",
        default="quant_research_restore_test",
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
        "--filename-prefix",
        default="quant_research",
    )

    parser.add_argument(
        "--docker-binary",
        default="/usr/bin/docker",
    )

    return parser


def main() -> int:
    """Restore, validate and remove a temporary database."""

    arguments = build_parser().parse_args()

    project_directory = (
        arguments.project_dir
        .expanduser()
        .resolve()
    )

    backup_directory = (
        arguments.backup_dir
        .expanduser()
        .resolve()
    )

    if not project_directory.is_dir():
        raise RuntimeError(
            "Project directory does not exist: "
            f"{project_directory}"
        )

    if not backup_directory.is_dir():
        raise RuntimeError(
            "Backup directory does not exist: "
            f"{backup_directory}"
        )

    validate_database_name(
        production_database=(
            arguments.production_database
        ),
        test_database=(
            arguments.test_database
        ),
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

    print("PostgreSQL restore test")
    print(f"Archive: {dump_path}")
    print(f"Checksum: {checksum_path}")
    print("Checksum verification: passed")
    print(
        "Temporary database: "
        f"{arguments.test_database}"
    )
    print()

    drop_test_database(
        docker_binary=arguments.docker_binary,
        project_directory=project_directory,
        compose_service=(
            arguments.compose_service
        ),
        database_user=(
            arguments.database_user
        ),
        test_database=(
            arguments.test_database
        ),
    )

    database_created = False

    try:
        create_test_database(
            docker_binary=(
                arguments.docker_binary
            ),
            project_directory=(
                project_directory
            ),
            compose_service=(
                arguments.compose_service
            ),
            database_user=(
                arguments.database_user
            ),
            test_database=(
                arguments.test_database
            ),
        )

        database_created = True

        print(
            "Temporary database created."
        )

        restore_database(
            docker_binary=(
                arguments.docker_binary
            ),
            project_directory=(
                project_directory
            ),
            compose_service=(
                arguments.compose_service
            ),
            database_user=(
                arguments.database_user
            ),
            test_database=(
                arguments.test_database
            ),
            dump_path=dump_path,
        )

        print("Database restore completed.")

        revision, counts = (
            validate_restored_database(
                docker_binary=(
                    arguments.docker_binary
                ),
                project_directory=(
                    project_directory
                ),
                compose_service=(
                    arguments.compose_service
                ),
                database_user=(
                    arguments.database_user
                ),
                test_database=(
                    arguments.test_database
                ),
            )
        )

        print("Database validation passed.")
        print(f"Alembic revision: {revision}")
        print()

        for table_name in REQUIRED_TABLES:
            print(
                f"{table_name}: "
                f"{counts[table_name]:,} rows"
            )

    finally:
        if database_created:
            drop_test_database(
                docker_binary=(
                    arguments.docker_binary
                ),
                project_directory=(
                    project_directory
                ),
                compose_service=(
                    arguments.compose_service
                ),
                database_user=(
                    arguments.database_user
                ),
                test_database=(
                    arguments.test_database
                ),
            )

            print()
            print(
                "Temporary database removed."
            )

    print()
    print(
        "Restore test completed successfully."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
