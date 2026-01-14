from fastapi import APIRouter, HTTPException
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from app.config import settings
from datetime import datetime, timedelta
from app.schemas.plaid_schemas import (
    LinkTokenResponse,
    ExchangeTokenRequest,
    ExchangeTokenResponse,
)
from app.services.plaid_service import (
    fetch_accounts_from_plaid,
    fetch_transactions_from_plaid,
    get_plaid_client
)

# Initialize the router
router = APIRouter(prefix="/plaid", tags=["Plaid"])

@router.post("/link-token", response_model=LinkTokenResponse)
def create_link_token():
    """
    Create a Plaid Link token for the frontend to initialize Plaid Link.
    """
    client = get_plaid_client()

    try:
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id="user-12345"),  # TODO: replace with real user ID
            client_name="Finance Tracker",
            products=[Products("auth"), Products("transactions")],
            country_codes=[CountryCode("US")],
            language="en",
        )

        response = client.link_token_create(request)
        link_token = response["link_token"]

        return LinkTokenResponse(link_token=link_token)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Plaid link token creation failed: {e}")


@router.post("/exchange-token", response_model=ExchangeTokenResponse)
def exchange_public_token(data: ExchangeTokenRequest):
    """
    Exchange the public token from the frontend for a Plaid access token.
    """
    client = get_plaid_client()

    try:
        request = ItemPublicTokenExchangeRequest(public_token=data.public_token)
        response = client.item_public_token_exchange(request)
        access_token = response["access_token"]

        # TODO: Persist access_token in your DB, linked to the authenticated user
        return ExchangeTokenResponse(access_token=access_token)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

@router.post("/accounts")
def get_accounts(payload: ExchangeTokenResponse):
    """
    Fetch accounts linked to a Plaid access token.
    """
    client = get_plaid_client()

    try:
        request = AccountsGetRequest(access_token=payload.access_token)
        response = client.accounts_get(request)

        accounts = [
            {
                "name": acct.name,
                "mask": acct.mask,
                "official_name": acct.official_name,
                "type": acct.type,
                "subtype": acct.subtype,
                "balances": acct.balances.current,
                "available_balance": acct.balances.available,
            }
            for acct in response["accounts"]
        ]

        return {"accounts": accounts}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch accounts: {e}")

@router.post("/transactions")
def get_transactions(payload: ExchangeTokenResponse):
    """
    Fetch recent transactions from Plaid using an access token.
    """
    client = get_plaid_client()
    try:
        # Define date range: last 30 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        request = TransactionsGetRequest(
            access_token=payload.access_token,
            start_date=start_date,
            end_date=end_date
        )

        response = client.transactions_get(request)

        transactions = [
            {
                "name": tx.name,
                "amount": tx.amount,
                "date": tx.date,
                "account_id": tx.account_id,
                "category": tx.category[0] if tx.category else None,
                "merchant_name": tx.merchant_name,
            }
            for tx in response["transactions"]
        ]

        return {"transactions": transactions}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch transactions: {e}")