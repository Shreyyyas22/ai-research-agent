from pydantic import ValidationError

from app.schemas.research import ResearchPlan


def main() -> None:
    valid_data = {
        "tasks": [
            {
                "question": "How does PostgreSQL handle transactions?",
                "search_queries": [
                    "PostgreSQL transactions",
                    "PostgreSQL ACID"
                ],
                "priority": 1,
            }
        ]
    }

    plan = ResearchPlan.model_validate(valid_data)

    print("VALID PLAN")
    print(plan)
    print()

    invalid_data = {
        "tasks": [
            {
                "question": "How does PostgreSQL handle transactions?",
                "search_queries": "PostgreSQL transactions",
                "priority": 10,
            }
        ]
    }

    try:
        ResearchPlan.model_validate(invalid_data)
    except ValidationError as exc:
        print("INVALID PLAN")
        print(exc)


if __name__ == "__main__":
    main()