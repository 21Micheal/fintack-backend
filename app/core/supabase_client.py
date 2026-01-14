# app/supabase_client.py (create this file if it doesn't exist)
from supabase import create_client, Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# ✅ Create Supabase client with SERVICE ROLE KEY for admin operations
def get_supabase_admin() -> Client:
    """
    Returns a Supabase client with admin privileges.
    Use this for admin operations like updating user metadata.
    """
    try:
        supabase_admin: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY  # ⚠️ This is the SERVICE ROLE KEY, not anon key
        )
        return supabase_admin
    except Exception as e:
        logger.error(f"❌ Failed to create Supabase admin client: {e}")
        raise

# 🔓 Create regular Supabase client with anon key (for non-admin operations)
def get_supabase_client() -> Client:
    """
    Returns a regular Supabase client for non-admin operations.
    """
    try:
        supabase_client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY
        )
        return supabase_client
    except Exception as e:
        logger.error(f"❌ Failed to create Supabase client: {e}")
        raise