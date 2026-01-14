# app/core/advisor_context_manager.py
from app.models.transaction import AdvisorContext
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def update_advisor_context(db, user_id, alert_summary=None, ai_summary=None):
    try:
        context = db.query(AdvisorContext).filter_by(user_id=user_id).first()

        if context:
            if alert_summary:
                context.alert_summary = alert_summary
            if ai_summary:
                context.ai_summary = ai_summary
            context.updated_at = datetime.utcnow()
            logger.info(f"Updated existing advisor context for user {user_id}")
        else:
            context = AdvisorContext(
                user_id=user_id,
                alert_summary=alert_summary,
                ai_summary=ai_summary,
                last_profile_snapshot=None,
            )
            db.add(context)
            logger.info(f"Created new advisor context for user {user_id}")

        db.commit()
        db.refresh(context)
        return context
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating advisor context: {str(e)}")
        # Don't raise the error - we want the main flow to continue
        return None