"""
backend/routes/transaction_routes.py

GET /transactions         — paginated, filterable transaction list
GET /transactions/{id}    — single transaction detail
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models.models import Account, Transaction
from backend.schemas.schemas import TransactionListResponse, TransactionSchema, TransactionUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("date"),
    sort_dir: str = Query("desc"),
    search: Optional[str] = None,
    account_id: Optional[str] = None,
    pending: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    # 1. Start with a base query that joins the Account table and filters for active ones
    query = db.query(Transaction).join(Account).filter(Account.is_active == True)

    # 2. Re-apply your existing optional filters on top of the active base query
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
        
    if pending is not None:
        query = query.filter(Transaction.pending == pending)
        
    if search:
        query = query.filter(
            (Transaction.merchant_name.ilike(f"%{search}%")) |
            (Transaction.name.ilike(f"%{search}%")) |
            (Transaction.category.ilike(f"%{search}%"))
        )

    # 3. Handle sorting and pagination execution (keep your existing logic below)
    total = query.count()
    
    # Apply sorting dynamically
    sort_attr = getattr(Transaction, sort_by, Transaction.date)
    if sort_dir == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())
        
    # Paginate
    transactions = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size

    return {
        "transactions": [TransactionSchema.model_validate(t) for t in transactions],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/{transaction_id}", response_model=TransactionSchema)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
):
    """Return a single transaction by internal ID."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id!r} not found",
        )
    return TransactionSchema.model_validate(txn)

@router.patch("/{transaction_id}", response_model=TransactionSchema)
def update_transaction_category(
    transaction_id: str,
    update_data: TransactionUpdate,
    db: Session = Depends(get_db),
):
    """Manually override a transaction's category."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id!r} not found",
        )
    
    txn.category = update_data.category
    db.commit()
    db.refresh(txn)
    
    return TransactionSchema.model_validate(txn)