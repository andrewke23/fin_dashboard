"""
backend/routes/plaid_routes.py

Three Plaid-specific endpoints:

POST /plaid/create_link_token   — frontend calls this to open Plaid Link
POST /plaid/exchange_public_token — called with public_token from Link
POST /plaid/sync_transactions   — trigger a sync for a linked institution
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from plaid.exceptions import ApiException
from plaid.model.country_code import CountryCode
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models.models import Institution, SyncState
from backend.plaid.client import get_plaid_client
from backend.schemas.schemas import (
    ExchangeTokenRequest,
    ExchangeTokenResponse,
    LinkTokenResponse,
    SyncRequest,
    SyncResponse,
)
from backend.services.sync_service import sync_accounts, sync_transactions
from backend.utils.encryption import encrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plaid", tags=["plaid"])


@router.post("/create_link_token", response_model=LinkTokenResponse)
def create_link_token():
    """
    Generate a short-lived Plaid Link token.

    The frontend passes this token to the Plaid Link JS component to open the
    institution-selection / credential-entry flow.  The token expires in 30min.
    """
    client = get_plaid_client()

    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id="local-user"),
        client_name="Finance Dashboard",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )

    try:
        response = client.link_token_create(request)
    except ApiException as exc:
        logger.error("link_token_create failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Plaid error: {exc.body}",
        )

    return LinkTokenResponse(
        link_token=response.link_token,
        expiration=str(response.expiration),
    )


@router.post("/exchange_public_token", response_model=ExchangeTokenResponse)
def exchange_public_token(
    body: ExchangeTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange the short-lived public_token from Plaid Link for a permanent
    access_token.  The access token is encrypted before being stored in SQLite.

    On success, immediately syncs accounts (balances) so the UI can display
    them right away.
    """
    client = get_plaid_client()

    try:
        exchange_response = client.item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=body.public_token)
        )
    except ApiException as exc:
        logger.error("item_public_token_exchange failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Plaid error: {exc.body}",
        )

    access_token: str = exchange_response.access_token
    item_id: str = exchange_response.item_id

    # Check if this institution is already linked (re-link scenario)
    existing = (
        db.query(Institution)
        .filter(Institution.plaid_item_id == item_id)
        .first()
    )

    if existing:
        # Update the token (user may have re-linked after expiry)
        existing.encrypted_access_token = encrypt_token(access_token)
        db.commit()
        institution = existing
    else:
        institution = Institution(
            plaid_item_id=item_id,
            institution_name=body.institution_name,
            encrypted_access_token=encrypt_token(access_token),
        )
        db.add(institution)
        db.commit()
        db.refresh(institution)

    # Sync accounts immediately so balances are available
    try:
        sync_accounts(db, institution)
        db.commit()
    except Exception as exc:
        logger.warning("Initial account sync failed: %s", exc)
        # Don't fail the whole exchange — accounts can sync later

    return ExchangeTokenResponse(
        institution_id=institution.id,
        institution_name=institution.institution_name,
    )


@router.post("/sync_transactions", response_model=SyncResponse)
def trigger_sync(
    body: SyncRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger a transaction sync for a specific institution.

    This runs synchronously in the request (acceptable for a local single-user
    app).  For large backlogs, the first sync may take several seconds.
    """
    institution = (
        db.query(Institution)
        .filter(Institution.id == body.institution_id)
        .first()
    )
    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution not found",
        )

    # Refresh account balances before pulling transactions
    try:
        sync_accounts(db, institution)
        db.commit()
    except Exception as exc:
        logger.warning("Account sync failed before transaction sync: %s", exc)

    try:
        result = sync_transactions(db, institution)
    except ApiException as exc:
        logger.error("sync_transactions failed for %s: %s", institution.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Plaid sync error: {exc.body}",
        )

    return SyncResponse(
        institution_id=institution.id,
        **result,
    )
