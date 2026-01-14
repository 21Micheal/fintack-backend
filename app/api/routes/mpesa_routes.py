# # app/api/routes/mpesa_routes.py
# from fastapi import APIRouter, Request, Depends, HTTPException
# from sqlalchemy.orm import Session
# from datetime import datetime
# import logging

# from app.db.session import get_db
# from app.models.transaction import Transaction

# logger = logging.getLogger(__name__)

# router = APIRouter(tags=["M-Pesa"])

# @router.post("/mpesa/callback")
# async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
#     """
#     Safaricom sends payment confirmation data here.
#     """
#     try:
#         data = await request.json()
#         logger.info(f"💰 M-Pesa Callback Data: {data}")

#         # Extract transaction fields safely
#         trans_id = data.get("TransID")
#         trans_amount = float(data.get("TransAmount", 0))
#         trans_time = data.get("TransTime", datetime.utcnow().strftime("%Y%m%d%H%M%S"))
#         phone_number = data.get("MSISDN", "Unknown")
#         name = data.get("FirstName", "M-Pesa User")
#         trans_type = data.get("TransactionType", "Pay Bill")

#         # Convert M-Pesa timestamp to datetime
#         try:
#             timestamp = datetime.strptime(trans_time, "%Y%m%d%H%M%S")
#         except Exception:
#             timestamp = datetime.utcnow()

#         # Create a transaction record
#         new_txn = Transaction(
#             name=name,
#             amount=trans_amount,
#             date=timestamp.date(),
#             category="M-Pesa",
#             account_id=phone_number,
#             transaction_type=trans_type,
#             type="income",
#             source="mpesa",
#             description=f"M-Pesa {trans_type} (ID: {trans_id})"
#         )

#         db.add(new_txn)
#         db.commit()
#         db.refresh(new_txn)

#         logger.info(f"✅ Transaction saved successfully: {new_txn}")

#         return {"ResultCode": 0, "ResultDesc": "Transaction received successfully"}

#     except Exception as e:
#         logger.error(f"❌ Error handling M-Pesa callback: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post("/mpesa/validate")
# async def mpesa_validate(request: Request):
#     """
#     Safaricom calls this endpoint before completing a transaction.
#     For now, always accept it.
#     """
#     data = await request.json()
#     logger.info(f"🧾 Validation Request: {data}")
#     return {"ResultCode": 0, "ResultDesc": "Accepted"}

# @router.get("/mpesa/transactions")
# def get_mpesa_transactions():
#     db: Session = Depends(get_db)
#     try:
#         transactions = db.query(Transaction).filter(Transaction.category == "M-Pesa").order_by(Transaction.date.desc()).limit(20).all()
#         return [t.__dict__ for t in transactions]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching M-Pesa transactions: {e}")
