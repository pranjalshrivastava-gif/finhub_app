import frappe
import hashlib
import hmac
import json
from frappe import _
from frappe.utils import cstr
import time

# ============================================
# API KEY MANAGEMENT
# ============================================

class APIAuth:
    """Handle API authentication"""
    
    @staticmethod
    def validate_api_key(api_key, api_secret):
        """Validate API key and secret"""
        user = frappe.db.get_value(
            "User",
            {"api_key": api_key, "enabled": 1},
            ["name", "api_secret"],
            as_dict=True
        )
        
        if not user:
            return False, "Invalid API key"
        
        if user.api_secret != api_secret:
            return False, "Invalid API secret"
        
        return True, user.name
    
    @staticmethod
    def generate_api_keys(user_email):
        """Generate new API keys for a user"""
        from frappe.core.doctype.user.user import generate_keys
        
        user = frappe.get_doc("User", user_email)
        api_key, api_secret = generate_keys(user.name)
        user.api_key = api_key
        user.api_secret = api_secret
        user.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "api_key": api_key,
            "api_secret": api_secret
        }
    
    @staticmethod
    def revoke_api_keys(user_email):
        """Revoke API keys for a user"""
        user = frappe.get_doc("User", user_email)
        user.api_key = ""
        user.api_secret = ""
        user.save(ignore_permissions=True)
        frappe.db.commit()
        return True


def require_api_auth():
    """Decorator for API authentication"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get API credentials from headers
            auth_header = frappe.get_request_header("Authorization", "")
            
            if not auth_header.startswith("Bearer "):
                frappe.local.response["http_status_code"] = 401
                return {
                    "success": False,
                    "error": "Missing or invalid authorization header. Use: Bearer API_KEY:API_SECRET"
                }
            
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            parts = token.split(":")
            
            if len(parts) != 2:
                frappe.local.response["http_status_code"] = 401
                return {"success": False, "error": "Invalid token format. Use: API_KEY:API_SECRET"}
            
            api_key, api_secret = parts
            
            # Validate
            is_valid, user = APIAuth.validate_api_key(api_key, api_secret)
            
            if not is_valid:
                frappe.local.response["http_status_code"] = 401
                return {"success": False, "error": user}
            
            # Set current user
            frappe.set_user(user)
            kwargs["current_user"] = user
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================
# API KEY MANAGEMENT ENDPOINTS
# ============================================

@frappe.whitelist()
def get_api_keys():
    """Get current user's API keys"""
    user = frappe.session.user
    user_doc = frappe.get_doc("User", user)
    
    return {
        "success": True,
        "data": {
            "api_key": user_doc.api_key if user_doc.api_key else "Not generated",
            "has_secret": bool(user_doc.api_secret)
        }
    }


@frappe.whitelist()
def generate_api_keys():
    """Generate new API keys for current user"""
    user = frappe.session.user
    keys = APIAuth.generate_api_keys(user)
    
    # Log the action
    log_api_event("API Keys Generated", user, {"action": "generate"})
    
    return {
        "success": True,
        "message": "API keys generated successfully. Save the secret key - it won't be shown again!",
        "data": keys
    }


@frappe.whitelist()
def revoke_api_keys():
    """Revoke current user's API keys"""
    user = frappe.session.user
    APIAuth.revoke_api_keys(user)
    
    # Log the action
    log_api_event("API Keys Revoked", user, {"action": "revoke"})
    
    return {
        "success": True,
        "message": "API keys revoked successfully"
    }