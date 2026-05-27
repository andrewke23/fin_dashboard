"""
backend/models/models.py

SQLAlchemy ORM models.  All tables live here so relationships are easy to follow.

Design decisions:
- String PKs (UUID) are used for Institution/Account/Transaction to make future
  exports / cross-device merges deterministic.
- plaid_*_id columns have unique constraints so we can safely upsert.
- raw_json on Transaction stores the full Plaid payload, giving us a migration
  path to any new Plaid fields without schema changes.
- SyncState stores the Plaid cursor per item — essential for incremental sync.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Institution
# ─────────────────────────────────────────────────────────────────────────────

class Institution(Base):
    """
    Represents a bank / financial institution connected via Plaid.
    One Institution = one Plaid Item (one set of credentials).
    """

    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plaid_item_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Encrypted Plaid access token — never store plaintext.
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="institution", cascade="all, delete-orphan"
    )
    sync_state: Mapped["SyncState | None"] = relationship(
        "SyncState", back_populates="institution", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Institution {self.institution_name!r} item={self.plaid_item_id!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Account
# ─────────────────────────────────────────────────────────────────────────────

class Account(Base):
    """
    A single bank account or credit card under an Institution.
    Balances are refreshed on every sync.
    """

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False
    )
    plaid_account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255))
    mask: Mapped[str | None] = mapped_column(String(10))       # last 4 digits
    type: Mapped[str | None] = mapped_column(String(50))       # depository | credit | …
    subtype: Mapped[str | None] = mapped_column(String(50))    # checking | savings | credit card | …
    current_balance: Mapped[float | None] = mapped_column(Float)
    available_balance: Mapped[float | None] = mapped_column(Float)
    iso_currency_code: Mapped[str | None] = mapped_column(String(10), default="USD")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    institution: Mapped["Institution"] = relationship("Institution", back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account {self.name!r} …{self.mask}>"


# ─────────────────────────────────────────────────────────────────────────────
# Transaction
# ─────────────────────────────────────────────────────────────────────────────

class Transaction(Base):
    """
    A single financial transaction.

    amount follows Plaid convention: positive = money leaving the account
    (purchases/outflows), negative = money entering (credits/refunds).
    """

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("plaid_transaction_id", name="uq_transaction_plaid_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    plaid_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Plaid's raw name
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    iso_currency_code: Mapped[str | None] = mapped_column(String(10), default="USD")
    # Plaid primary category (e.g. "Food and Drink")
    category: Mapped[str | None] = mapped_column(String(100))
    # Plaid detailed category (e.g. "Restaurants")
    subcategory: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[str] = mapped_column(String(10), nullable=False)   # ISO 8601 "YYYY-MM-DD"
    pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Store full Plaid payload for forward compatibility
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction {self.date} {self.merchant_name or self.name!r} ${self.amount}>"


# ─────────────────────────────────────────────────────────────────────────────
# SyncState
# ─────────────────────────────────────────────────────────────────────────────

class SyncState(Base):
    """
    Persists the Plaid transaction sync cursor for each Institution/Item.

    Plaid's /transactions/sync endpoint is cursor-based: each call returns
    new/modified/removed transactions since the last cursor.  We store the
    cursor here so incremental syncs only pull what's new.
    """

    __tablename__ = "sync_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    institution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("institutions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plaid_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    cursor: Mapped[str | None] = mapped_column(Text)       # None = no sync yet
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    institution: Mapped["Institution"] = relationship(
        "Institution", back_populates="sync_state"
    )

    def __repr__(self) -> str:
        return f"<SyncState item={self.plaid_item_id!r} last={self.last_sync}>"
