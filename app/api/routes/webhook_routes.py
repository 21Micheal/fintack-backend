from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.services.plaid_service import handle_plaid_webhook
import logging

router = APIRouter(prefix="/api/webhook", tags=["Plaid Webhook"])

logger = logging.getLogger(__name__)


@router.post("/plaid")
async def plaid_webhook(request: Request):
    """
    Official endpoint that receives webhook events from Plaid.
    """
    try:
        webhook_data = await request.json()
        logger.info(f"📩 Incoming Plaid Webhook: {webhook_data}")

        response = await handle_plaid_webhook(webhook_data)
        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error handling Plaid webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ✅ TEST ENDPOINT — Simulate a Plaid Webhook manually
@router.post("/plaid/test")
async def test_plaid_webhook():
    """
    Simulate a Plaid webhook for local testing.
    Example: POST /api/webhook/plaid/test
    """
    mock_webhook = {
        "webhook_type": "TRANSACTIONS",
        "webhook_code": "TRANSACTIONS_UPDATED",
        "item_id": "test_item_id_123",
        "new_transactions": 3,
        "removed_transactions": [],
        "environment": "sandbox"
    }

    logger.info("🚀 Simulating Plaid webhook locally...")
    response = await handle_plaid_webhook(mock_webhook)
    return JSONResponse(content={
        "message": "Simulated Plaid webhook processed successfully.",
        "mock_data": mock_webhook,
        "result": response
    })
