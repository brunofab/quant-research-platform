from quant_research.data.sec import SECClient


ALPHABET_CIK = "1652044"


def main() -> None:
    with SECClient() as sec:
        submissions = sec.get_submissions(ALPHABET_CIK)
        facts = sec.get_company_facts(ALPHABET_CIK)

    print("Company:")
    print(submissions["name"])

    print("\nTickers:")
    print(submissions.get("tickers"))

    print("\nExchanges:")
    print(submissions.get("exchanges"))

    print("\nRecent filing forms:")
    print(submissions["filings"]["recent"]["form"][:10])

    print("\nCompany Facts Entity:")
    print(facts["entityName"])

    print("\nNumber of US-GAAP concepts:")
    print(len(facts["facts"].get("us-gaap", {})))


if __name__ == "__main__":
    main()
