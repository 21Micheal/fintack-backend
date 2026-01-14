import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.api_client import Configuration, ApiClient
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.products import Products

from app.models.transaction import Transaction
from app.db.session import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

# -------------------------------
# 🧩 Initialize Plaid client
# -------------------------------
def get_plaid_client() -> plaid_api.PlaidApi:
    """
    Initialize and return a configured Plaid API client.
    """
    env_map = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }

    base_url = env_map.get(settings.PLAID_ENV.lower(), "https://sandbox.plaid.com")

    configuration = Configuration(
        host=base_url,
        api_key={
            "clientId": settings.PLAID_CLIENT_ID,
            "secret": settings.PLAID_SECRET,
        },
    )

    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


# -------------------------------
# 🔔 Handle Webhooks
# -------------------------------
async def handle_plaid_webhook(webhook_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Handles incoming Plaid webhook events.
    """
    webhook_type = webhook_data.get("webhook_type")
    webhook_code = webhook_data.get("webhook_code")

    logger.info(f"Received Plaid webhook: {webhook_type} - {webhook_code}")
    print(f"🔔 Received Plaid Webhook: {webhook_type} - {webhook_code}")

    # Transaction-related webhooks
    if webhook_type == "TRANSACTIONS":
        if webhook_code in ["DEFAULT_UPDATE", "INITIAL_UPDATE"]:
            logger.info("Plaid: New transaction update received.")
            await process_transaction_update(webhook_data)
        elif webhook_code == "TRANSACTIONS_REMOVED":
            logger.info("Plaid: Transactions removed event received.")
            # TODO: Implement transaction removal logic here
        else:
            logger.warning(f"Unhandled transactions webhook code: {webhook_code}")

    elif webhook_type == "ITEM":
        logger.info("Plaid: ITEM webhook received.")
        # TODO: Handle ITEM webhook types (e.g., ITEM_LOGIN_REQUIRED)

    else:
        logger.warning(f"Unhandled Plaid webhook type: {webhook_type}")

    return {"status": "success"}


# -------------------------------
# 💾 Process Transaction Updates
# -------------------------------
async def process_transaction_update(payload: Dict[str, Any]):
    """
    Called when Plaid sends a new transaction update.
    Stores added transactions in the database.
    """
    added = payload.get("added", [])
    if not added:
        logger.info("No new transactions found in webhook payload.")
        return

    db: Session = SessionLocal()
    try:
        for tx in added:
            txn = Transaction(
                name=tx.get("name"),
                amount=tx.get("amount"),
                date=tx.get("date"),
                category=tx.get("category", [None])[0],
                account_id=tx.get("account_id"),
            )
            db.add(txn)
        db.commit()
        logger.info(f"Added {len(added)} new transactions from Plaid webhook.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing transactions: {e}")
    finally:
        db.close()

async def fetch_accounts_from_plaid(access_token: str):
    """
    Fetch all accounts linked to the user's Plaid item.
    """
    client = get_plaid_client()
    request = AccountsGetRequest(access_token=access_token)

    try:
        response = client.accounts_get(request)
        accounts = response["accounts"]
        logger.info(f"✅ Fetched {len(accounts)} accounts from Plaid.")
        return accounts
    except Exception as e:
        logger.error(f"Error fetching Plaid accounts: {e}")
        raise

async def fetch_transactions_from_plaid(access_token: str, start_date: str = None, end_date: str = None):
    """
    Fetch transactions for a given access token.
    """
    client = get_plaid_client()

    # Default: last 30 days
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.now().date().isoformat()

    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date,
        end_date=end_date,
        options=TransactionsGetRequestOptions(count=100)
    )

    try:
        response = client.transactions_get(request)
        transactions = response["transactions"]
        logger.info(f"✅ Fetched {len(transactions)} transactions from Plaid.")
        return transactions
    except Exception as e:
        logger.error(f"Error fetching Plaid transactions: {e}")
        raise