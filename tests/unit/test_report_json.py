from app.schemas.research import (
    Evidence,
    ResearchReport,
    Source,
    SynthesizedClaim,
)


def make_report() -> ResearchReport:
    source = Source(
        title="Example Source",
        url="https://example.com",
    )

    evidence = Evidence(
        source=source,
        claim="Example claim.",
        excerpt="Example supporting evidence.",
    )

    return ResearchReport(
        title="Example Research Report",
        executive_summary="Example summary.",
        key_findings=[
            SynthesizedClaim(
                claim="Example finding.",
                citation_ids=[1],
            )
        ],
        detailed_analysis="Example detailed analysis.",
        trade_offs=["Example trade-off."],
        evidence=[evidence],
        limitations=["Example limitation."],
        conclusion="Example conclusion.",
        sources=[source],
    )


def test_report_can_be_serialized_to_dict():
    report = make_report()

    data = report.model_dump()

    assert isinstance(data, dict)
    assert data["title"] == "Example Research Report"
    assert len(data["key_findings"]) == 1
    assert data["key_findings"][0]["citation_ids"] == [1]
    assert len(data["sources"]) == 1


def test_report_can_be_serialized_to_json():
    report = make_report()

    json_data = report.model_dump_json()

    assert isinstance(json_data, str)
    assert "Example Research Report" in json_data
    assert "Example finding." in json_data


def test_report_json_round_trip():
    report = make_report()

    json_data = report.model_dump_json()
    restored = ResearchReport.model_validate_json(json_data)

    assert restored == report