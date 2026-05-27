from backend.routes.account_routes import router as accounts_router
from backend.routes.analytics_routes import router as analytics_router
from backend.routes.plaid_routes import router as plaid_router
from backend.routes.transaction_routes import router as transactions_router

__all__ = ["plaid_router", "transactions_router", "accounts_router", "analytics_router"]
