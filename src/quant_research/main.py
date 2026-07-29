from quant_research.database.connection import check_database_connection


def main() -> None:
    database, user = check_database_connection()

    print(f"Connected successfully to database '{database}' as user '{user}'.")


if __name__ == "__main__":
    main()
