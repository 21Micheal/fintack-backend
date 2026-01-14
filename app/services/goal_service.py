from sqlalchemy.orm import Session
from uuid import UUID
from core.goal_crud import get_goals_by_user, update_goal_progress
from api.routes.transaction_routes import get_mpesa_transactions as get_transactions_by_user  # Assuming you have this

def auto_update_goal_progress(db: Session, user_id: UUID):
    """Automatically update goal progress based on user's available savings"""
    
    # Get user's current financial position
    transactions = get_transactions_by_user(db, user_id)
    
    # Calculate available savings (income - expenses)
    income = sum(t.amount for t in transactions if t.type == "income")
    expenses = sum(t.amount for t in transactions if t.type == "expense")
    available_savings = income - expenses
    
    if available_savings <= 0:
        return {"message": "No available savings to allocate to goals"}
    
    # Get active goals
    goals = get_goals_by_user(db, user_id)
    active_goals = [g for g in goals if g.is_active]
    
    if not active_goals:
        return {"message": "No active goals to update"}
    
    # Simple allocation: distribute available savings proportionally to goal targets
    total_target = sum(g.target_amount for g in active_goals)
    
    updates = []
    remaining_savings = available_savings
    
    for goal in active_goals:
        if remaining_savings <= 0:
            break
            
        # Calculate proportional allocation
        goal_share = (goal.target_amount / total_target) * available_savings
        actual_allocation = min(goal_share, goal.target_amount - goal.current_amount, remaining_savings)
        
        if actual_allocation > 0:
            updated_goal = update_goal_progress(db, goal.id, user_id, actual_allocation)
            remaining_savings -= actual_allocation
            updates.append({
                "goal_id": goal.id,
                "goal_name": goal.name,
                "amount_added": actual_allocation,
                "new_total": updated_goal.current_amount
            })
    
    return {
        "message": "Goal progress updated automatically",
        "total_allocated": available_savings - remaining_savings,
        "remaining_savings": remaining_savings,
        "updates": updates
    }