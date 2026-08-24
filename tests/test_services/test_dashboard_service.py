"""Tests for strict dashboard schemas and optimistic-concurrency persistence."""

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from src.models.db import (
    DashboardLayoutModel,
    OrganizationMemberModel,
    SemanticColumnModel,
    SemanticDatabaseModel,
    SemanticMetricModel,
    SemanticTableModel,
    UserModel,
)
from src.models.schemas import (
    DashboardLayout,
    DashboardLayoutResponse,
    DashboardSaveRequest,
    DashboardWidgetConfig,
)
from src.services import dashboard_service
from src.services.dashboard_service import (
    DashboardAuthorizationError,
    DashboardNotFoundError,
    DashboardValidationError,
    DashboardVersionConflictError,
    get_dashboard_layout,
    save_dashboard_layout,
)
from src.services.organization_service import create_organization

# ---------------------------------------------------------------------------
# Schema contract tests
# ---------------------------------------------------------------------------


def _widget_payload(**overrides):
    payload = {
        "id": "widget-1",
        "metric_id": 7,
        "dimension_col_id": 3,
        "date_filter_column_id": 5,
        "time_grain": "month",
        "chart_type": "line",
        "width": "half",
        "height": "normal",
        "custom_title": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("chart_type", ["kpi", "line", "area", "bar", "pie", "table"])
def test_widget_accepts_every_supported_chart_type(chart_type):
    overrides = {"chart_type": chart_type}
    if chart_type == "kpi":
        overrides.update({"dimension_col_id": None, "time_grain": None})
    elif chart_type in ("bar", "pie", "table"):
        overrides["time_grain"] = None
    widget = DashboardWidgetConfig(**_widget_payload(**overrides))
    assert widget.chart_type == chart_type


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chart_type", "scatter"),
        ("width", "quarter"),
        ("height", "huge"),
        ("time_grain", "decade"),
        ("metric_id", 0),
        ("metric_id", -3),
        ("dimension_col_id", -1),
        ("date_filter_column_id", 0),
    ],
)
def test_widget_rejects_invalid_literals_and_non_positive_ids(field, value):
    with pytest.raises(ValidationError):
        DashboardWidgetConfig(**_widget_payload(**{field: value}))


def test_kpi_requires_date_filter_column():
    payload = _widget_payload(
        chart_type="kpi",
        dimension_col_id=None,
        time_grain=None,
        date_filter_column_id=None,
    )
    with pytest.raises(ValidationError, match="date_filter_column_id"):
        DashboardWidgetConfig(**payload)


@pytest.mark.parametrize("kept_field", ["dimension_col_id", "time_grain"])
def test_kpi_rejects_dimension_and_time_grain(kept_field):
    payload = _widget_payload(chart_type="kpi", **{kept_field: None})
    with pytest.raises(ValidationError, match="KPI"):
        DashboardWidgetConfig(**payload)


@pytest.mark.parametrize("chart_type", ["line", "area"])
def test_time_series_charts_require_dimension_and_grain(chart_type):
    without_grain = _widget_payload(chart_type=chart_type, time_grain=None)
    without_dimension = _widget_payload(chart_type=chart_type, dimension_col_id=None)
    for payload in (without_grain, without_dimension):
        with pytest.raises(ValidationError):
            DashboardWidgetConfig(**payload)


@pytest.mark.parametrize("chart_type", ["bar", "pie", "table"])
def test_categorical_charts_require_dimension(chart_type):
    payload = _widget_payload(chart_type=chart_type, dimension_col_id=None)
    with pytest.raises(ValidationError):
        DashboardWidgetConfig(**payload)


def test_custom_title_blank_normalizes_to_none_and_length_is_capped():
    blank = DashboardWidgetConfig(**_widget_payload(custom_title="   "))
    assert blank.custom_title is None
    trimmed = DashboardWidgetConfig(**_widget_payload(custom_title="  Doanh thu  "))
    assert trimmed.custom_title == "Doanh thu"
    with pytest.raises(ValidationError):
        DashboardWidgetConfig(**_widget_payload(custom_title="x" * 201))


def test_layout_rejects_duplicate_widget_ids():
    widgets = [
        DashboardWidgetConfig(**_widget_payload(id="same")),
        DashboardWidgetConfig(**_widget_payload(id="same")),
    ]
    with pytest.raises(ValidationError, match="unique"):
        DashboardLayout(widgets=widgets)


def test_layout_caps_widgets_at_24():
    overflow = [DashboardWidgetConfig(**_widget_payload(id=f"w-{i}")) for i in range(25)]
    with pytest.raises(ValidationError):
        DashboardLayout(widgets=overflow)
    allowed = [DashboardWidgetConfig(**_widget_payload(id=f"w-{i}")) for i in range(24)]
    assert len(DashboardLayout(widgets=allowed).widgets) == 24


def test_save_request_requires_zero_or_positive_expected_version():
    request = DashboardSaveRequest(layout=DashboardLayout(), expected_version=0)
    assert request.expected_version == 0
    with pytest.raises(ValidationError):
        DashboardSaveRequest(layout=DashboardLayout(), expected_version=-1)


def test_layout_response_defaults_match_empty_singleton_shape():
    response = DashboardLayoutResponse(db_id=1)
    assert response.layout is None
    assert response.version == 0
    assert response.updated_at is None
    assert response.updated_by is None


# ---------------------------------------------------------------------------
# Service test fixtures
# ---------------------------------------------------------------------------


async def _create_user(async_session, user_id, username):
    async_session.add(
        UserModel(
            id=user_id,
            email=f"{username}@company.com",
            username=username,
            full_name=username.title(),
            hashed_password="hash",
            status="active",
        )
    )
    await async_session.commit()


async def _add_membership(async_session, org_id, user_id, role):
    async_session.add(OrganizationMemberModel(org_id=org_id, user_id=user_id, role=role))
    await async_session.commit()


async def _seed_semantic_database(async_session, org_id=None, created_by=1, display_name="Dash DB"):
    database = SemanticDatabaseModel(
        org_id=org_id,
        created_by=created_by,
        display_name=display_name,
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.flush()
    table = SemanticTableModel(db_id=database.id, table_name="orders", business_name="Don hang")
    async_session.add(table)
    await async_session.flush()
    date_col = SemanticColumnModel(
        table_id=table.id,
        column_name="order_date",
        data_type="date",
        business_name="Ngay dat",
        is_time_dimension=True,
    )
    region_col = SemanticColumnModel(
        table_id=table.id,
        column_name="region",
        data_type="varchar",
        business_name="Khu vuc",
    )
    async_session.add_all([date_col, region_col])
    metric = SemanticMetricModel(
        db_id=database.id,
        created_by=created_by,
        name="doanh_thu",
        description="Tong doanh thu",
        sql_template="SELECT amount FROM orders",
        status="approved",
    )
    async_session.add(metric)
    await async_session.commit()
    return database.id, metric.id, region_col.id, date_col.id


async def _seed_workspace_database(async_session, slug):
    organization = await create_organization(async_session, 1, "Acme", slug)
    db_id, metric_id, region_id, date_id = await _seed_semantic_database(async_session, org_id=organization.id)
    return organization, db_id, metric_id, region_id, date_id


def _line_layout(metric_id, dimension_col_id, date_filter_column_id):
    widget = DashboardWidgetConfig(
        id="widget-1",
        metric_id=metric_id,
        dimension_col_id=dimension_col_id,
        date_filter_column_id=date_filter_column_id,
        time_grain="month",
        chart_type="line",
        width="half",
        height="normal",
    )
    return DashboardLayout(widgets=[widget])


# ---------------------------------------------------------------------------
# Service behavior tests
# ---------------------------------------------------------------------------


async def test_get_dashboard_returns_empty_singleton_response(async_session):
    organization, db_id, *_ = await _seed_workspace_database(async_session, "acme-empty")

    response = await get_dashboard_layout(async_session, 1, db_id, org_id=organization.id)

    assert response == DashboardLayoutResponse(db_id=db_id)


async def test_create_layout_with_expected_version_zero_stores_version_one(async_session):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-create")
    request = DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0)

    saved = await save_dashboard_layout(async_session, 1, db_id, request, org_id=organization.id)

    assert saved.version == 1
    assert saved.updated_by == 1
    assert saved.updated_at is not None
    assert saved.layout.widgets[0].metric_id == metric_id
    row = await async_session.scalar(select(DashboardLayoutModel).where(DashboardLayoutModel.db_id == db_id))
    assert row is not None
    assert row.version == 1
    assert row.updated_by == 1


async def test_update_layout_increments_version_and_sets_updater(async_session):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-update")
    await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0),
        org_id=organization.id,
    )
    await _create_user(async_session, 2, "editor")
    await _add_membership(async_session, organization.id, 2, "data_lead")

    updated = await save_dashboard_layout(
        async_session,
        2,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=1),
        org_id=organization.id,
    )

    assert updated.version == 2
    assert updated.updated_by == 2
    row = await async_session.scalar(select(DashboardLayoutModel).where(DashboardLayoutModel.db_id == db_id))
    assert row.version == 2


async def test_stale_expected_version_raises_conflict_with_current_version(async_session):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-conflict")
    layout = _line_layout(metric_id, region_id, date_id)
    await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=layout, expected_version=0),
        org_id=organization.id,
    )

    with pytest.raises(DashboardVersionConflictError) as stale_create:
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=layout, expected_version=0),
            org_id=organization.id,
        )
    assert stale_create.value.current_version == 1

    with pytest.raises(DashboardVersionConflictError) as stale_update:
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=layout, expected_version=5),
            org_id=organization.id,
        )
    assert stale_update.value.current_version == 1


async def test_insert_race_maps_integrity_error_to_current_version(async_session, monkeypatch):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-race")
    request = DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0)
    await save_dashboard_layout(async_session, 1, db_id, request, org_id=organization.id)

    original_select = dashboard_service._select_singleton
    forced_first = {"pending": True}

    async def _hide_then_reveal(db, target_db_id):
        if forced_first["pending"]:
            forced_first["pending"] = False
            return None
        return await original_select(db, target_db_id)

    monkeypatch.setattr(dashboard_service, "_select_singleton", _hide_then_reveal)

    with pytest.raises(DashboardVersionConflictError) as raced:
        await save_dashboard_layout(async_session, 1, db_id, request, org_id=organization.id)

    assert raced.value.current_version == 1


@pytest.mark.parametrize("role", ["admin", "data_lead", "member"])
async def test_every_workspace_role_can_read_and_mutate_shared_dashboard(async_session, role):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, f"acme-{role}")
    await _create_user(async_session, 2, f"{role}-user")
    await _add_membership(async_session, organization.id, 2, role)
    await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0),
        org_id=organization.id,
    )

    seen = await get_dashboard_layout(async_session, 2, db_id, org_id=organization.id)
    assert seen.version == 1

    updated = await save_dashboard_layout(
        async_session,
        2,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=1),
        org_id=organization.id,
    )
    assert updated.version == 2
    assert updated.updated_by == 2


async def test_foreign_workspace_database_is_masked_as_not_found(async_session):
    _, db_id, *_ = await _seed_workspace_database(async_session, "acme-masked")
    foreign_org = await create_organization(async_session, 1, "Other", "other-org")
    await _create_user(async_session, 2, "outsider")
    await _add_membership(async_session, foreign_org.id, 2, "member")

    with pytest.raises(DashboardNotFoundError):
        await get_dashboard_layout(async_session, 2, db_id, org_id=foreign_org.id)
    with pytest.raises(DashboardNotFoundError):
        await save_dashboard_layout(
            async_session,
            2,
            db_id,
            DashboardSaveRequest(layout=DashboardLayout(), expected_version=0),
            org_id=foreign_org.id,
        )


async def test_non_member_of_owning_workspace_is_denied(async_session):
    organization, db_id, *_ = await _seed_workspace_database(async_session, "acme-denied")
    await _create_user(async_session, 2, "ghost")

    with pytest.raises(DashboardAuthorizationError):
        await get_dashboard_layout(async_session, 2, db_id, org_id=organization.id)
    with pytest.raises(DashboardAuthorizationError):
        await save_dashboard_layout(
            async_session,
            2,
            db_id,
            DashboardSaveRequest(layout=DashboardLayout(), expected_version=0),
            org_id=organization.id,
        )


async def test_personal_database_is_creator_only(async_session):
    db_id, metric_id, region_id, date_id = await _seed_semantic_database(async_session)
    await _create_user(async_session, 2, "stranger")

    saved = await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0),
    )
    assert saved.version == 1

    with pytest.raises(DashboardNotFoundError):
        await get_dashboard_layout(async_session, 2, db_id)
    with pytest.raises(DashboardNotFoundError):
        await save_dashboard_layout(
            async_session,
            2,
            db_id,
            DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=1),
        )


async def test_personal_database_with_org_header_stays_creator_only(async_session):
    db_id, metric_id, region_id, date_id = await _seed_semantic_database(async_session)
    organization = await create_organization(async_session, 1, "Acme", "acme-personal-header")
    await _create_user(async_session, 2, "colleague")
    await _add_membership(async_session, organization.id, 2, "member")

    saved = await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0),
        org_id=organization.id,
    )
    seen = await get_dashboard_layout(async_session, 1, db_id, org_id=organization.id)

    assert saved.version == 1
    assert seen.version == 1

    with pytest.raises(DashboardNotFoundError):
        await get_dashboard_layout(async_session, 2, db_id, org_id=organization.id)
    with pytest.raises(DashboardNotFoundError):
        await save_dashboard_layout(
            async_session,
            2,
            db_id,
            DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=1),
            org_id=organization.id,
        )


async def test_workspace_database_without_header_uses_membership_fallback(async_session):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-fallback")
    await _create_user(async_session, 2, "teammate")
    await _add_membership(async_session, organization.id, 2, "member")

    owner_saved = await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0),
    )
    teammate_seen = await get_dashboard_layout(async_session, 2, db_id)
    teammate_saved = await save_dashboard_layout(
        async_session,
        2,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=1),
    )

    assert owner_saved.version == 1
    assert teammate_seen.version == 1
    assert teammate_saved.version == 2
    assert teammate_saved.updated_by == 2


async def test_missing_metric_reference_is_rejected(async_session):
    organization, db_id, _, region_id, date_id = await _seed_workspace_database(async_session, "acme-missing")
    layout = _line_layout(99999, region_id, date_id)

    with pytest.raises(DashboardValidationError, match="99999"):
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=layout, expected_version=0),
            org_id=organization.id,
        )


async def test_cross_database_references_are_rejected(async_session):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-cross")
    other_db_id, other_metric_id, other_region_id, other_date_id = await _seed_semantic_database(
        async_session, org_id=organization.id, display_name="Other DB"
    )
    del other_db_id

    with pytest.raises(DashboardValidationError):
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=_line_layout(other_metric_id, region_id, date_id), expected_version=0),
            org_id=organization.id,
        )
    with pytest.raises(DashboardValidationError):
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=_line_layout(metric_id, other_region_id, date_id), expected_version=0),
            org_id=organization.id,
        )
    with pytest.raises(DashboardValidationError):
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=_line_layout(metric_id, region_id, other_date_id), expected_version=0),
            org_id=organization.id,
        )


async def test_non_approved_metric_is_rejected(async_session):
    organization, db_id, metric_id, region_id, date_id = await _seed_workspace_database(async_session, "acme-draft")
    metric = await async_session.get(SemanticMetricModel, metric_id)
    metric.status = "draft"
    await async_session.commit()
    layout = _line_layout(metric_id, region_id, date_id)

    with pytest.raises(DashboardValidationError):
        await save_dashboard_layout(
            async_session,
            1,
            db_id,
            DashboardSaveRequest(layout=layout, expected_version=0),
            org_id=organization.id,
        )


async def test_sql_dump_database_persists_layout_without_query_execution(async_session, monkeypatch):
    async def _forbid(*args, **kwargs):
        raise AssertionError("Dashboard layout persistence must not execute queries")

    monkeypatch.setattr("src.services.query_execution.execute_compiled_query", _forbid)
    monkeypatch.setattr("src.services.query_compiler.SemanticQueryCompiler.compile", _forbid)

    db_id, metric_id, region_id, date_id = await _seed_semantic_database(async_session)

    saved = await save_dashboard_layout(
        async_session,
        1,
        db_id,
        DashboardSaveRequest(layout=_line_layout(metric_id, region_id, date_id), expected_version=0),
    )
    loaded = await get_dashboard_layout(async_session, 1, db_id)

    assert saved.version == 1
    assert loaded.version == 1
    assert loaded.layout.widgets[0].metric_id == metric_id
