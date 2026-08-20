import pytest
from sqlalchemy import select

from src.models.db import (
    ChatMessageModel,
    LiveTargetDbModel,
    OrganizationMemberModel,
    SemanticDatabaseModel,
    UserModel,
)
from src.services.chat_service import (
    ChatAuthorizationError,
    create_chat_session,
    delete_chat_session,
    get_chat_session_with_messages,
    get_recent_chat_history,
    list_chat_sessions,
    save_chat_message,
    update_chat_session_title,
)
from src.services.organization_service import create_organization


async def _seed_live_database(async_session):
    """Seed an owned semantic database with a live source."""
    database = SemanticDatabaseModel(
        created_by=1,
        display_name="Chat DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.flush()
    async_session.add(
        LiveTargetDbModel(
            created_by=1,
            display_name="Chat source",
            dialect="sqlite",
            conn_url_enc="encrypted",
            schema_metadata={},
            semantic_db_id=database.id,
        )
    )
    await async_session.commit()
    return database.id


async def test_chat_service_persists_ordered_history_and_cascade(async_session):
    """Messages are ordered, title updates, and delete cascades to messages."""
    db_id = await _seed_live_database(async_session)
    session = await create_chat_session(async_session, 1, db_id)
    await save_chat_message(async_session, session.id, "user", "Xin chào")
    await save_chat_message(async_session, session.id, "assistant", "Xin chào bạn")

    assert await get_recent_chat_history(async_session, session.id) == [
        {"role": "user", "content": "Xin chào"},
        {"role": "assistant", "content": "Xin chào bạn"},
    ]
    renamed = await update_chat_session_title(async_session, session.id, 1, "  Cuộc trò chuyện  ")
    assert renamed is not None
    assert renamed.title == "Cuộc trò chuyện"
    detail = await get_chat_session_with_messages(async_session, session.id, 1)
    assert detail is not None
    assert [message.sequence_no for message in detail.messages] == [1, 2]

    assert await delete_chat_session(async_session, session.id, 1) is True
    remaining = await async_session.execute(select(ChatMessageModel).where(ChatMessageModel.session_id == session.id))
    assert remaining.scalars().all() == []


async def test_chat_service_enforces_database_ownership(async_session):
    """A user cannot create or list sessions for another user's database."""
    other = UserModel(
        id=2,
        email="other@company.com",
        username="other",
        full_name="Other",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    async_session.add(other)
    await async_session.commit()
    db_id = await _seed_live_database(async_session)

    try:
        await create_chat_session(async_session, 2, db_id)
    except ChatAuthorizationError:
        pass
    else:
        raise AssertionError("Expected database ownership check to reject another user")

    assert await list_chat_sessions(async_session, 1, db_id) == []


async def test_workspace_data_lead_can_use_data_chat(async_session):
    """Workspace Data Lead can use the data assistant."""
    organization = await create_organization(async_session, 1, "Acme", "acme")
    database = SemanticDatabaseModel(
        org_id=organization.id,
        created_by=1,
        display_name="Workspace Chat DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.flush()
    async_session.add(
        LiveTargetDbModel(
            created_by=1,
            display_name="Workspace Chat source",
            dialect="sqlite",
            conn_url_enc="encrypted",
            schema_metadata={},
            semantic_db_id=database.id,
        )
    )
    await async_session.commit()

    session = await create_chat_session(async_session, 1, database.id, org_id=organization.id)
    assert session.db_id == database.id


async def test_workspace_member_cannot_use_chat_without_live_data_permission(async_session):
    """A Workspace member still needs a live data source to start the assistant."""
    other = UserModel(
        id=2,
        email="member@company.com",
        username="member",
        full_name="Member",
        hashed_password="hash",
        role="analyst",
        status="active",
    )
    async_session.add(other)
    await async_session.commit()
    organization = await create_organization(async_session, 1, "Acme", "acme")
    async_session.add(OrganizationMemberModel(org_id=organization.id, user_id=2, role="member"))
    await async_session.commit()

    database = SemanticDatabaseModel(
        org_id=organization.id,
        created_by=1,
        display_name="Member Chat DB",
        db_type="sqlite",
        conn_url_enc="encrypted",
    )
    async_session.add(database)
    await async_session.commit()

    with pytest.raises(ChatAuthorizationError, match="only supported for live"):
        await create_chat_session(async_session, 2, database.id, org_id=organization.id)
