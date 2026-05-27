"""
backend/routes/analytics_routes.py

GET /analytics/spending_by_month   — monthly spending totals
GET /analytics/category_breakdown  — pie-chart data
GET /analytics/top_merchants       — ranked merchants by spend
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models.models import Transaction
from backend.schemas.schemas import (
    CategoryBreakdown,
    CategoryBreakdownResponse,
    MonthlySpending,
    SpendingByMonthResponse,
    TopMerchant,
    TopMerchantsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])

_DEFAULT_CATEGORY = "Uncategorized"


def _build_date_filter(query, start_date: Optional[str], end_date: Optional[str]):
    """Apply optional date range filter to a query."""
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    return query


@router.get("/spending_by_month", response_model=SpendingByMonthResponse)
def spending_by_month(
    months: int = Query(12, ge=1, le=60, description="Number of months to return"),
    account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Aggregate spending by calendar month.

    Uses SQLite's strftime to extract YYYY-MM from the ISO date string.
    Only includes non-pending, positive-amount (outflow) transactions.
    """
    query = (
        db.query(
            func.strftime("%Y-%m", Transaction.date).label("month"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .filter(
            Transaction.pending == False,  # noqa: E712
            Transaction.amount > 0,        # outflows only
        )
        .group_by(func.strftime("%Y-%m", Transaction.date))
        .order_by(func.strftime("%Y-%m", Transaction.date).desc())
        .limit(months)
    )

    if account_id:
        query = query.filter(Transaction.account_id == account_id)

    rows = query.all()

    # Return in ascending date order for charting
    data = [
        MonthlySpending(
            month=row.month,
            total=round(row.total, 2),
            transaction_count=row.transaction_count,
        )
        for row in reversed(rows)
    ]

    return SpendingByMonthResponse(data=data)


@router.get("/category_breakdown", response_model=CategoryBreakdownResponse)
def category_breakdown(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Sum spending by Plaid category for the given date range.

    NULL categories are grouped as 'Uncategorized'.
    Percentages are calculated from total non-pending outflow spend.
    """
    base = (
        db.query(Transaction)
        .filter(
            Transaction.pending == False,  # noqa: E712
            Transaction.amount > 0,
        )
    )
    base = _build_date_filter(base, start_date, end_date)
    if account_id:
        base = base.filter(Transaction.account_id == account_id)

    rows = (
        base.with_entities(
            func.coalesce(Transaction.category, _DEFAULT_CATEGORY).label("category"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .group_by(func.coalesce(Transaction.category, _DEFAULT_CATEGORY))
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    total_spending = sum(r.total for r in rows)

    data = [
        CategoryBreakdown(
            category=row.category,
            total=round(row.total, 2),
            transaction_count=row.transaction_count,
            percentage=round((row.total / total_spending * 100) if total_spending else 0, 1),
        )
        for row in rows
    ]

    return CategoryBreakdownResponse(
        data=data,
        total_spending=round(total_spending, 2),
    )


@router.get("/top_merchants", response_model=TopMerchantsResponse)
def top_merchants(
    limit: int = Query(10, ge=1, le=50),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    account_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return top merchants by total spend.

    Transactions with no merchant_name are grouped under their name field.
    Only non-pending outflows are counted.
    """
    base = (
        db.query(Transaction)
        .filter(
            Transaction.pending == False,  # noqa: E712
            Transaction.amount > 0,
        )
    )
    base = _build_date_filter(base, start_date, end_date)
    if account_id:
        base = base.filter(Transaction.account_id == account_id)

    rows = (
        base.with_entities(
            func.coalesce(Transaction.merchant_name, Transaction.name).label("merchant_name"),
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .group_by(func.coalesce(Transaction.merchant_name, Transaction.name))
        .order_by(func.sum(Transaction.amount).desc())
        .limit(limit)
        .all()
    )

    data = [
        TopMerchant(
            merchant_name=row.merchant_name,
            total=round(row.total, 2),
            transaction_count=row.transaction_count,
        )
        for row in rows
    ]

    return TopMerchantsResponse(data=data)


@router.get("/accounts_summary")
def accounts_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Per-account spending totals — used by the dashboard spending-by-card widget.
    """
    from backend.models.models import Account

    query = (
        db.query(
            Transaction.account_id,
            Account.name.label("account_name"),
            Account.mask,
            Account.subtype,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .join(Account, Account.id == Transaction.account_id)
        .filter(
            Transaction.pending == False,  # noqa: E712
            Transaction.amount > 0,
        )
    )
    query = _build_date_filter(query, start_date, end_date)
    rows = query.group_by(Transaction.account_id).order_by(func.sum(Transaction.amount).desc()).all()

    return {
        "data": [
            {
                "account_id": r.account_id,
                "account_name": r.account_name,
                "mask": r.mask,
                "subtype": r.subtype,
                "total": round(r.total, 2),
                "transaction_count": r.transaction_count,
            }
            for r in rows
        ]
    }
