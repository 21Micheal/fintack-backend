# app/services/mpesa_service.py
import base64
import requests
from datetime import datetime
from app.config import settings
from app.models.transaction import Transaction
from app.db.session import SessionLocal

def get_access_token():
    """
    Generate M-Pesa access token using consumer key & secret
    """
    auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(auth_url, auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))
    response.raise_for_status()
    return response.json()["access_token"]

def stk_push(phone_number: str, amount: float, account_reference="FinanceTracker"):
    """
    Initiate STK push payment request
    """
    access_token = get_access_token()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        (settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": "Finance Tracker Deposit"
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(
        "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers=headers,
    )

    if response.status_code != 200:
        raise Exception(f"STK push failed: {response.text}")

    return response.json()


def save_mpesa_transaction(result: dict):
    """
    Store M-Pesa transaction in the database
    """
    with SessionLocal() as db:
        transaction = Transaction(
            name=result.get("FirstName", "M-Pesa User"),
            amount=result.get("Amount"),
            category="Payments",
            transaction_type="income",
            source="M-Pesa",
            date=datetime.utcnow(),
            description=result.get("TransactionDesc", "STK Payment"),
        )
        db.add(transaction)
        db.commit()
