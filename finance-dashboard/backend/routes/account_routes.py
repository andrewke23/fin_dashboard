"""
backend/routes/account_routes.py

GET /accounts                — list all institutions with their accounts
GET /accounts/{id}           — single account detail
DELETE /accounts/{id}        — unlink an institution
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models.models import Account, Institution, SyncState, Transaction
from backend.schemas.schemas import AccountSchema, InstitutionSchema
from backend.schemas.schemas import RewardRulesUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[InstitutionSchema])
def list_institutions(db: Session = Depends(get_db)):
    """
    Return all linked institutions with their child accounts.
    Also attaches last_sync from SyncState.
    """
    institutions = db.query(Institution).order_by(Institution.institution_name).all()
    result = []

    for inst in institutions:
        sync_state = (
            db.query(SyncState)
            .filter(SyncState.institution_id == inst.id)
            .first()
        )
        schema = InstitutionSchema.model_validate(inst)
        schema.last_sync = sync_state.last_sync if sync_state else None
        result.append(schema)

    return result


@router.get("/{account_id}", response_model=AccountSchema)
def get_account(account_id: str, db: Session = Depends(get_db)):
    acct = db.query(Account).filter(Account.id == account_id).first()
    if not acct:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id!r} not found",
        )
    return AccountSchema.model_validate(acct)


@router.delete("/institutions/{institution_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_institution(institution_id: str, db: Session = Depends(get_db)):
    """
    Remove an institution and all associated accounts, transactions, and sync state.
    Cascade deletes are defined on the ORM relationships.
    """
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution {institution_id!r} not found",
        )
    db.delete(institution)
    db.commit()

@router.patch("/{account_id}/toggle", response_model=AccountSchema)
def toggle_account_active(account_id: str, db: Session = Depends(get_db)):
    acct = db.query(Account).filter(Account.id == account_id).first()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    
    acct.is_active = not acct.is_active
    db.commit()
    db.refresh(acct)
    return AccountSchema.model_validate(acct)

@router.patch("/{account_id}/rules", response_model=AccountSchema)
def update_account_rules(
    account_id: str,
    update_data: RewardRulesUpdate,
    db: Session = Depends(get_db)
):
    """Update time-based point multiplier rules and retroactively apply them."""
    acct = db.query(Account).filter(Account.id == account_id).first()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # 1. Save the new array of rulesets to the Account
    # We use model_dump() to convert the Pydantic objects into standard dictionaries for JSON saving
    acct.reward_rules = [rule.model_dump() for rule in update_data.reward_rules]
    
    # 2. Sort rules newest to oldest
    sorted_rules = sorted(acct.reward_rules, key=lambda x: x.get("effective_date", "1970-01-01"), reverse=True)

    # 3. Retroactively recalculate all historical transactions
    transactions = db.query(Transaction).filter(Transaction.account_id == account_id).all()
    
    for txn in transactions:
        if txn.amount > 0:
            txn_date_str = txn.date.isoformat() if hasattr(txn.date, 'isoformat') else str(txn.date)
            
            # Find the active rule for this specific transaction's date
            active_rule = sorted_rules[-1] if sorted_rules else {"base": 1.0, "categories": {}}
            for rule in sorted_rules:
                if rule.get("effective_date", "1970-01-01") <= txn_date_str:
                    active_rule = rule
                    break
                    
            base_multiplier = active_rule.get("base", 1.0)
            category_multipliers = active_rule.get("categories", {})
            
            cat_str = txn.category if txn.category else "UNCATEGORIZED"
            multiplier = category_multipliers.get(cat_str, base_multiplier)
            
            txn.points_earned = int(txn.amount * multiplier)
        else:
            txn.points_earned = 0

    # 4. Commit all recalculations instantly
    db.commit()
    db.refresh(acct)
    
    return AccountSchema.model_validate(acct)