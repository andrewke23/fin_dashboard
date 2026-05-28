"""
backend/services/sync_service.py

Orchestrates the full Plaid sync lifecycle:

1. Fetch accounts/balances for an Institution.
2. Use the /transactions/sync cursor API to pull new, modified, and removed
   transactions incrementally.
3. Upsert everything into SQLite.
4. Persist the cursor so the next run only pulls deltas.

Design decisions:
- Cursor-based sync (not date-range): Plaid strongly recommends cursor sync for
  production use — it handles pending→posted transitions, removes, and backfills.
- All DB writes in a single transaction per sync page so a crash mid-page leaves
  the DB in a consistent state (old cursor, partial writes rolled back).
- We strip and normalise categories from Plaid's personal_finance_category object
  (v2 API) with a fallback to the legacy category array.
- amounts are stored as-is from Plaid (positive = debit, negative = credit).
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.exceptions import ApiException

from backend.models.models import Account, Institution, SyncState, Transaction
from backend.plaid.client import get_plaid_client
from backend.utils.encryption import decrypt_token

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_category(txn) -> tuple[str | None, str | None]:
    """
    Extract primary / detailed category from a Plaid Transaction object.

    Plaid v2 returns personal_finance_category (preferred).
    Older or sandbox responses may only have the legacy category list.
    """
    try:
        pfc = txn.personal_finance_category
        if pfc:
            return pfc.primary, pfc.detailed
    except AttributeError:
        pass

    # Fallback: legacy category list  ["Food and Drink", "Restaurants"]
    try:
        cats = txn.category or []
        primary = cats[0] if len(cats) > 0 else None
        detailed = cats[1] if len(cats) > 1 else None
        return primary, detailed
    except (AttributeError, IndexError):
        return None, None


def _upsert_transaction(db: Session, txn, account_id: str) -> str:
    """
    Insert or update a single transaction.  Returns "added" or "modified".
    """
    primary_cat, detailed_cat = _parse_category(txn)

    existing = (
        db.query(Transaction)
        .filter(Transaction.plaid_transaction_id == txn.transaction_id)
        .first()
    )

    if existing:
        existing.merchant_name = txn.merchant_name
        existing.name = txn.name
        existing.amount = txn.amount
        existing.category = primary_cat
        existing.subcategory = detailed_cat
        existing.date = str(txn.date)
        existing.pending = txn.pending
        existing.raw_json = json.dumps(txn.to_dict(), default=str)
        return "modified"
    else:
        db.add(
            Transaction(
                account_id=account_id,
                plaid_transaction_id=txn.transaction_id,
                merchant_name=txn.merchant_name,
                name=txn.name,
                amount=txn.amount,
                iso_currency_code=getattr(txn, "iso_currency_code", "USD"),
                category=primary_cat,
                subcategory=detailed_cat,
                date=str(txn.date),
                pending=txn.pending,
                raw_json=json.dumps(txn.to_dict(), default=str),
            )
        )
        return "added"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def sync_accounts(db: Session, institution: Institution) -> list[Account]:
    """
    Refresh account balances for an institution.
    Creates new Account rows and updates balances on existing ones.
    """
    client = get_plaid_client()
    access_token = decrypt_token(institution.encrypted_access_token)

    try:
        response = client.accounts_get(AccountsGetRequest(access_token=access_token))
    except ApiException as exc:
        logger.error("Plaid accounts_get failed for %s: %s", institution.institution_name, exc)
        raise

    plaid_accounts = response.accounts
    synced: list[Account] = []

    for pa in plaid_accounts:
        existing = (
            db.query(Account)
            .filter(Account.plaid_account_id == pa.account_id)
            .first()
        )
        if existing:
            existing.current_balance = pa.balances.current
            existing.available_balance = pa.balances.available
            existing.updated_at = datetime.now(timezone.utc)
            synced.append(existing)
        else:
            acct = Account(
                institution_id=institution.id,
                plaid_account_id=pa.account_id,
                name=pa.name,
                official_name=pa.official_name,
                mask=pa.mask,
                type=str(pa.type) if pa.type else None,
                subtype=str(pa.subtype) if pa.subtype else None,
                current_balance=pa.balances.current,
                available_balance=pa.balances.available,
                iso_currency_code=pa.balances.iso_currency_code or "USD",
            )
            db.add(acct)
            synced.append(acct)

    db.flush()  # assign IDs without committing
    return synced


def sync_transactions(db: Session, institution: Institution) -> dict:
    """
    Run a full cursor-based transaction sync for one institution.

    Returns a summary dict: {added, modified, removed, has_more}

    The function pages through ALL available data in one call (has_more loop)
    but commits after each page to avoid holding a huge transaction.  The
    cursor is written at the end of each page so a crash mid-run can resume.
    """
    client = get_plaid_client()
    access_token = decrypt_token(institution.encrypted_access_token)

    # Fetch or initialise SyncState
    sync_state = (
        db.query(SyncState)
        .filter(SyncState.institution_id == institution.id)
        .first()
    )
    if not sync_state:
        sync_state = SyncState(
            institution_id=institution.id,
            plaid_item_id=institution.plaid_item_id,
            cursor=None,
        )
        db.add(sync_state)
        db.flush()

    cursor = sync_state.cursor  # None triggers a full historical fetch

    # Build account_id lookup  plaid_account_id → our internal UUID
    accounts = (
        db.query(Account)
        .filter(Account.institution_id == institution.id)
        .all()
    )
    account_map = {a.plaid_account_id: a for a in accounts}

    totals = {"added": 0, "modified": 0, "removed": 0, "has_more": False}

    has_more = True
    while has_more:
        # Build request dynamically to avoid passing None to strictly typed Plaid models
        request_kwargs = {
            "access_token": access_token,
            "count": 500,
        }
        if cursor is not None:
            request_kwargs["cursor"] = cursor

        request = TransactionsSyncRequest(**request_kwargs)

        try:
            response = client.transactions_sync(request)
        except ApiException as exc:
            logger.error(
                "transactions_sync failed for %s: %s",
                institution.institution_name,
                exc,
            )
            raise

        for txn in response.added:
            account = account_map.get(txn.account_id)
            if account is None:
                continue
                
            # --- TIME-TRAVEL POINT CALCULATION ENGINE ---
            # 1. Extract rules array, fallback to default genesis rule
            rules_array = account.reward_rules or [{"effective_date": "1970-01-01", "base": 1.0, "categories": {}}]
            
            # 2. Sort rules newest to oldest (descending date)
            sorted_rules = sorted(rules_array, key=lambda x: x.get("effective_date", "1970-01-01"), reverse=True)
            
            # 3. Find the active rule for this specific transaction date
            txn_date_str = txn.date.isoformat() if hasattr(txn.date, 'isoformat') else str(txn.date)
            active_rule = sorted_rules[-1] # Fallback to oldest rule by default
            
            for rule in sorted_rules:
                # The moment we find a rule that started BEFORE or ON the transaction date, we lock it in
                if rule.get("effective_date", "1970-01-01") <= txn_date_str:
                    active_rule = rule
                    break

            base_multiplier = active_rule.get("base", 1.0)
            category_multipliers = active_rule.get("categories", {})

            # 4. Calculate points
            points = 0
            if txn.amount > 0:
                category_str = txn.personal_finance_category.primary if txn.personal_finance_category else "UNCATEGORIZED"
                multiplier = category_multipliers.get(category_str, base_multiplier)
                points = int(txn.amount * multiplier)
            # ----------------------------------------------

            # 5. Save to database
            db_txn = Transaction(
                id=txn.transaction_id,
                plaid_transaction_id=txn.transaction_id, # Keeping our fix from earlier!
                account_id=account.id, 
                amount=txn.amount,
                date=txn.date,
                name=txn.name,
                merchant_name=txn.merchant_name,
                pending=txn.pending,
                category=txn.personal_finance_category.primary if txn.personal_finance_category else None,
                points_earned=points # Save the time-travel calculated points!
            )
            db.add(db_txn)

        for txn in response.modified:
            acct_id = account_map.get(txn.account_id)
            if acct_id is None:
                continue
            op = _upsert_transaction(db, txn, acct_id)
            totals[op] += 1

        # ── Process removed ────────────────────────────────────────────────
        for removed in response.removed:
            txn_id = removed.transaction_id
            row = (
                db.query(Transaction)
                .filter(Transaction.plaid_transaction_id == txn_id)
                .first()
            )
            if row:
                db.delete(row)
                totals["removed"] += 1

        # ── Advance cursor and commit this page ────────────────────────────
        cursor = response.next_cursor
        has_more = response.has_more

        sync_state.cursor = cursor
        sync_state.last_sync = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Sync page done for %s — added=%d modified=%d removed=%d has_more=%s",
            institution.institution_name,
            totals["added"],
            totals["modified"],
            totals["removed"],
            has_more,
        )

    totals["has_more"] = False  # all pages consumed
    return totals
