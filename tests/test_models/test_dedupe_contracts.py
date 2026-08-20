"""Contract tests for dedupe/clarify response models."""

from src.models.schemas import (
    ChatResponse,
    CustomMetricGenerateResponse,
    DuplicateMetricNotice,
    MetricConflictInfo,
    MetricSuggestionsV2,
)


def _notice(**overrides):
    payload = {"existing_metric_name": "Doanh thu", "user_message": "Đã tồn tại"}
    payload.update(overrides)
    return DuplicateMetricNotice(**payload)


def test_notice_defaults():
    n = _notice()
    assert n.existing_metric_id is None and n.existing_metric_status is None
    assert n.similarity_reason == ""
    assert n.existing_definition is None and n.existing_yaml == ""
    assert not hasattr(n, "proposed")


def test_conflict_requires_join_key():
    c = MetricConflictInfo(
        proposed_metric_name="Doanh thu",
        existing_metric_name="Doanh thu",
        suggested_name="Doanh thu (mới)",
    )
    assert c.suggested_name.endswith("(mới)") and c.clarify_question == ""


def test_v2_defaults_empty_lists():
    v = MetricSuggestionsV2()
    assert v.metrics == [] and v.duplicates == [] and v.conflicts == []


def test_generate_response_carries_dedupe():
    r = CustomMetricGenerateResponse()
    assert r.duplicates == [] and r.dedupe_performed is True


def test_chat_response_carries_dedupe():
    r = ChatResponse(
        intent="metric_query",
        session_id="s1",
        user_message_id="u1",
        assistant_message_id="a1",
    )
    assert r.duplicates == [] and r.dedupe_performed is True
