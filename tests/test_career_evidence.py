from pathlib import Path


def test_career_draft_discloses_missing_manual_baseline() -> None:
    draft = Path("docs/career/portfolio_and_interview_draft.md").read_text(
        encoding="utf-8"
    )
    assert "no se midió una ejecución manual comparable" in draft
    assert "477.81" in draft
    assert "231,123" in draft
    assert "6,924.9" in draft

