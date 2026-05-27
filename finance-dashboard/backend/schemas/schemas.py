"""
backend/schemas/schemas.py

Pydantic v2 schemas used for API request/response validation.

Keeping schemas separate from ORM models is intentional:
- ORM models are SQLAlchemy objects tied to the DB layer.
- Schemas are pure data contracts for the HTTP layer.
- This lets both evolve independently and prevents accidental data leakage
  (e.g. we never accidentally serialize encrypted_access_token to the frontend).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Plaid Link
# ─────────────────────────────────────────────────────────────────────────────

class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: str


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_name: str


class ExchangeTokenResponse(BaseModel):
    institution_id: str
    institution_name: str
    message: str = "Institution linked successfully"


class SyncRequest(BaseModel):
    institution_id: str


class SyncResponse(BaseModel):
    institution_id: str
    added: int
    modified: int
    removed: int
    has_more: bool


# ─────────────────────────────────────────────────────────────────────────────
# Accounts
# ─────────────────────────────────────────────────────────────────────────────

class AccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str
    plaid_account_id: str
    name: str
    official_name: Optional[str] = None
    mask: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    current_balance: Optional[float] = None
    available_balance: Optional[float] = None
    iso_currency_code: Optional[str] = "USD"
    updated_at: datetime


class InstitutionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plaid_item_id: str
    institution_name: str
    created_at: datetime
    accounts: list[AccountSchema] = []
    last_sync: Optional[datetime] = None  # populated from SyncState


# ─────────────────────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────────────────────

class TransactionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    plaid_transaction_id: str
    merchant_name: Optional[str] = None
    name: str
    amount: float
    iso_currency_code: Optional[str] = "USD"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    date: str
    pending: bool
    created_at: datetime


class TransactionListResponse(BaseModel):
    transactions: list[TransactionSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

class MonthlySpending(BaseModel):
    month: str        # "YYYY-MM"
    total: float
    transaction_count: int


class CategoryBreakdown(BaseModel):
    category: str
    total: float
    transaction_count: int
    percentage: float


class TopMerchant(BaseModel):
    merchant_name: str
    total: float
    transaction_count: int


class SpendingByMonthResponse(BaseModel):
    data: list[MonthlySpending]


class CategoryBreakdownResponse(BaseModel):
    data: list[CategoryBreakdown]
    total_spending: float


class TopMerchantsResponse(BaseModel):
    data: list[TopMerchant]


# ─────────────────────────────────────────────────────────────────────────────
# Generic
# ─────────────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
