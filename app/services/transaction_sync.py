# # app/services/transaction_sync.py
# from datetime import datetime, timedelta
# from sqlalchemy.orm import Session
# from app.models.transaction import Transaction
# from app.services.plaid_client import get_transactions

# def sync_transactions(db: Session, access_token: str, user_id: str):
#     # Fetch transactions from the last 30 days
#     end_date = datetime.now().date()
#     start_date = end_date - timedelta(days=30)

#     plaid_response = get_transactions(access_token, str(start_date), str(end_date))
#     transactions = plaid_response["transactions"]

#     new_records = []
#     for txn in transactions:
#         # Skip if transaction already exists
#         exists = db.query(Transaction).filter(
#             Transaction.account_id == txn["account_id"],
#             Transaction.date == txn["date"],
#             Transaction.amount == txn["amount"]
#         ).first()
#         if exists:
#             continue

#         record = Transaction(
#             user_id=user_id,
#             account_id=txn["account_id"],
#             name=txn["name"],
#             amount=txn["amount"],
#             date=txn["date"],
#             category=" > ".join(txn["category"]) if txn.get("category") else None,
#             merchant_name=txn.get("merchant_name"),
#             iso_currency_code=txn.get("iso_currency_code"),
#             pending=txn.get("pending"),
#         )
#         db.add(record)
#         new_records.append(record)

#     db.commit()
#     return {"synced": len(new_records), "new_transactions": [t.name for t in new_records]}
