from sqlalchemy.orm import Session
from app.models.bank_models import BankItem, BankAccount, BankTransaction
import uuid
from datetime import datetime

def create_bank_item(db: Session, user_id: str, access_token: str, institution_name: str = None):
    item = BankItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        access_token=access_token,
        institution_name=institution_name,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def create_bank_accounts(db: Session, bank_item_id: str, accounts_data: list):
    accounts = []
    for acc in accounts_data:
        account = BankAccount(
            id=acc.get("account_id", str(uuid.uuid4())),
            bank_item_id=bank_item_id,
            name=acc.get("name"),
            type=acc.get("type"),
            subtype=acc.get("subtype"),
            mask=acc.get("mask"),
            current_balance=acc.get("balances", {}).get("current"),
            available_balance=acc.get("balances", {}).get("available"),
            iso_currency_code=acc.get("balances", {}).get("iso_currency_code"),
        )
        db.add(account)
        accounts.append(account)
    db.commit()
    return accounts


def create_transactions(db: Session, bank_item_id: str, transactions_data: list):
    transactions = []
    for tx in transactions_data:
        transaction = BankTransaction(
            id=tx.get("transaction_id", str(uuid.uuid4())),
            bank_item_id=bank_item_id,
            account_id=tx.get("account_id"),
            name=tx.get("name"),
            amount=tx.get("amount"),
            date=datetime.strptime(tx.get("date"), "%Y-%m-%d").date(),
            category=", ".join(tx.get("category", [])) if tx.get("category") else None,
            pending=str(tx.get("pending")),
            iso_currency_code=tx.get("iso_currency_code"),
        )
        db.add(transaction)
        transactions.append(transaction)
    db.commit()
    return transactions


def get_transactions_by_user(db: Session, user_id: str):
    return (
        db.query(BankTransaction)
        .join(BankItem)
        .filter(BankItem.user_id == user_id)
        .order_by(BankTransaction.date.desc())
        .all()
    )
