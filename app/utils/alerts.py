from sqlalchemy.orm import Session
from app.models.transaction import Transaction, Alert
from datetime import datetime, timedelta

def generate_alerts_for_user(user_id: str, db: Session):
    """
    Analyze user's transactions and generate alerts based on spending behavior.
    """
    alerts = []

    # Get recent transactions (last 30 days)
    now = datetime.utcnow()
    last_month = now - timedelta(days=30)

    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.date >= last_month)
        .all()
    )

    if not transactions:
        return []

    # --- Analyze spending ---
    expenses = [t for t in transactions if t.type == "expense"]
    incomes = [t for t in transactions if t.type == "income"]

    total_expense = sum(t.amount for t in expenses)
    total_income = sum(t.amount for t in incomes)

    # --- Alert: Overspending ---
    if total_expense > (total_income * 0.8 if total_income > 0 else 1000):
        alerts.append(Alert(
            user_id=user_id,
            title="⚠️ High Spending Detected",
            message=f"You've spent KES {total_expense:.2f} in the last 30 days — that's quite high!",
            category="expense",
            level="warning",
        ))

    # --- Alert: Savings Milestone ---
    savings = total_income - total_expense
    if savings > 0 and savings > (total_income * 0.3):
        alerts.append(Alert(
            user_id=user_id,
            title="🎉 Savings Milestone!",
            message=f"Great job! You've saved KES {savings:.2f} in the past month.",
            category="goal",
            level="info",
        ))

    # --- Alert: Large Single Transaction ---
    for t in transactions:
        if t.amount > 5000:
            alerts.append(Alert(
                user_id=user_id,
                title="💸 Large Transaction",
                message=f"A transaction of KES {t.amount:.2f} was recorded ({t.category}).",
                category=t.type,
                level="info",
            ))

    # Save new alerts
    for alert in alerts:
        db.add(alert)
    db.commit()

    return alerts
