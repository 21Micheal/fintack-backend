# app/services/plaid_connector.py

from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest, LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from app.config import settings

# Configure Plaid client properly
configuration = Configuration(
    host=settings.PLAID_ENV,  # e.g., "https://sandbox.plaid.com"
    api_key={
        "clientId": settings.PLAID_CLIENT_ID,
        "secret": settings.PLAID_SECRET,
    },
)

api_client = ApiClient(configuration)
plaid_client = plaid_api.PlaidApi(api_client)


def create_link_token(user_id: str):
    """
    Create a new link token for a given user.
    """
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Finance Tracker",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )

    response = plaid_client.link_token_create(request)
    return response.to_dict()


def exchange_public_token(public_token: str):
    """
    Exchange a public token for an access token.
    """
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = plaid_client.item_public_token_exchange(request)
    return response.to_dict()


def get_accounts(access_token: str):
    """
    Retrieve user accounts linked to Plaid.
    """
    request = AccountsGetRequest(access_token=access_token)
    response = plaid_client.accounts_get(request)
    return response.to_dict()


def get_transactions(access_token: str, start_date: str, end_date: str):
    """
    Retrieve transactions for the given access token and date range.
    """
    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date,
        end_date=end_date,
    )
    response = plaid_client.transactions_get(request)
    return response.to_dict()
