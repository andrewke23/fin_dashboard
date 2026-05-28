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
from backend.models.models import Transaction, Account
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


@router.get("/spending_by_month")
def get_spending_by_month(db: Session = Depends(get_db)):
    """Fetch total monthly outflow, ignoring deactivated accounts."""
    # We filter out credits (amount < 0) and only include transactions from active accounts
    results = (
        db.query(
            func.strftime("%Y-%m", Transaction.date).label("month"),
            func.sum(Transaction.amount).label("total")
        )
        .join(Account)
        .filter(Account.is_active == True)
        .filter(Transaction.amount > 0) 
        .group_by("month")
        .order_by("month")
        .all()
    )
    
    return {"data": [{"month": r.month, "total": float(r.total or 0)} for r in results]}


@router.get("/category_breakdown")
def get_category_breakdown(db: Session = Depends(get_db)):
    """Fetch spending grouped by category, ignoring deactivated accounts."""
    # Filter for debits/outflows from active accounts only
    results = (
        db.query(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count")
        )
        .join(Account)
        .filter(Account.is_active == True)
        .filter(Transaction.amount > 0)
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    
    total_spending = sum(float(r.total or 0) for r in results)
    
    data = []
    for r in results:
        cat_total = float(r.total or 0)
        percentage = (cat_total / total_spending * 100) if total_spending > 0 else 0
        data.append({
            "category": r.category or "UNCATEGORIZED",
            "total": cat_total,
            "transaction_count": r.count,
            "percentage": round(percentage, 2)
        })
        
    return {
        "data": data,
        "total_spending": total_spending
    }


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

@router.get("/points_by_card")
def get_points_by_card(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Fetch total credit card points earned per card with optional date filters."""
    # Explicitly join Account and Transaction to prevent 0-point bugs
    query = db.query(
        Account.name,
        Account.mask,
        func.sum(Transaction.points_earned).label("total_points")
    ).join(Transaction, Account.id == Transaction.account_id)
    
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
        
    results = query.filter(Account.is_active == True).group_by(Account.id).all()
                   
    data = []
    for r in results:
        # Only include cards that actually earned points in this time window
        if r.total_points and r.total_points > 0:
            card_name = f"{r.name} (..{r.mask})" if r.mask else r.name
            data.append({"card": card_name, "points": int(r.total_points)})
            
    # Sort the highest earning cards to the top
    data.sort(key=lambda x: x["points"], reverse=True)
    
    return {"data": data}