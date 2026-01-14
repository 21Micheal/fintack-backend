# app/core/profile_engine.py
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from app.models.transaction import Transaction, FinancialProfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def update_financial_profile(db: Session, user_id: str) -> FinancialProfile:
    try:
        # Get current month in YYYY-MM format
        current_month = datetime.utcnow().strftime("%Y-%m")
        current_year = datetime.utcnow().year
        current_month_num = datetime.utcnow().month
        
        logger.info(f"Updating financial profile for user {user_id}, month {current_month}")

        # Calculate totals for the current month
        income_result = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == "income",
            extract('year', Transaction.date) == current_year,
            extract('month', Transaction.date) == current_month_num
        ).scalar()

        expense_result = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract('year', Transaction.date) == current_year,
            extract('month', Transaction.date) == current_month_num
        ).scalar()

        total_income = float(income_result or 0)
        total_expenses = float(expense_result or 0)
        savings = total_income - total_expenses

        logger.info(f"Totals - Income: {total_income}, Expenses: {total_expenses}, Savings: {savings}")

        # Find top spending category for current month
        top_category_result = db.query(
            Transaction.category, 
            func.sum(Transaction.amount).label("total")
        ).filter(
            Transaction.user_id == user_id, 
            Transaction.type == "expense",
            extract('year', Transaction.date) == current_year,
            extract('month', Transaction.date) == current_month_num,
            Transaction.category.isnot(None)  # Exclude null categories
        ).group_by(
            Transaction.category
        ).order_by(
            func.sum(Transaction.amount).desc()
        ).first()

        top_category = top_category_result[0] if top_category_result and top_category_result[0] else "General"
        logger.info(f"Top category: {top_category}")

        # Check if profile exists for this month
        profile = db.query(FinancialProfile).filter(
            FinancialProfile.user_id == user_id, 
            FinancialProfile.month == current_month
        ).first()

        if profile:
            # Update existing profile
            profile.total_income = total_income
            profile.total_expenses = total_expenses
            profile.savings = savings
            profile.top_category = top_category
            profile.updated_at = datetime.utcnow()
            logger.info("Updated existing financial profile")
        else:
            # Create new profile
            profile = FinancialProfile(
                user_id=user_id,
                month=current_month,
                total_income=total_income,
                total_expenses=total_expenses,
                savings=savings,
                top_category=top_category,
            )
            db.add(profile)
            logger.info("Created new financial profile")

        db.commit()
        db.refresh(profile)
        
        # Verify profile was created successfully
        if not profile:
            logger.error("Failed to create financial profile - profile is None")
            raise ValueError("Failed to create financial profile")
            
        logger.info(f"Financial profile created/updated successfully: {profile.id}")
        return profile

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating financial profile for user {user_id}: {str(e)}")
        # Create a default profile to prevent None returns
        default_profile = FinancialProfile(
            user_id=user_id,
            month=current_month,
            total_income=0.0,
            total_expenses=0.0,
            savings=0.0,
            top_category="None",
        )
        db.add(default_profile)
        db.commit()
        db.refresh(default_profile)
        logger.info("Created default financial profile due to error")
        return default_profile