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
from backend.schemas.schemas import TransactionListResponse, TransactionSchema

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    # ── Filters ──────────────────────────────────────────────────
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    category: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    merchant: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Full-text search on name/merchant"),
    pending: Optional[bool] = Query(None),
    # ── Pagination ────────────────────────────────────────────────
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    # ── Sorting ───────────────────────────────────────────────────
    sort_by: str = Query("date", pattern="^(date|amount|merchant_name|name|category)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """
    Returns a paginated list of transactions with optional filters.

    All filters are ANDed together.
    Search performs a case-insensitive LIKE on both name and merchant_name.
    """
    query = db.query(Transaction)

    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    if category:
        query = query.filter(Transaction.category.ilike(f"%{category}%"))
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    if merchant:
        query = query.filter(Transaction.merchant_name.ilike(f"%{merchant}%"))
    if pending is not None:
        query = query.filter(Transaction.pending == pending)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Transaction.name.ilike(pattern),
                Transaction.merchant_name.ilike(pattern),
            )
        )

    # Total count before pagination
    total = query.count()

    # Sorting
    sort_col = getattr(Transaction, sort_by)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Pagination
    offset = (page - 1) * page_size
    transactions = query.offset(offset).limit(page_size).all()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return TransactionListResponse(
        transactions=[TransactionSchema.model_validate(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


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
