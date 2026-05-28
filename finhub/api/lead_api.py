import frappe
import json
from frappe import _
from frappe.utils import now_datetime


def log_lead_activity(lead_name, activity_type, description=None, old_value=None, new_value=None, performed_by=None):
    """
    Create activity log entry for lead
    """
    try:
        if not performed_by:
            performed_by = frappe.session.user or "Administrator"
        
        log_entry = frappe.get_doc({
            "doctype": "Lead Activity Log",
            "lead": lead_name,
            "activity_type": activity_type,
            "description": description,
            "old_value": old_value,
            "new_value": new_value,
            "performed_by": performed_by
        })
        log_entry.insert(ignore_permissions=True)
        frappe.db.commit()
        return True
    except Exception as e:
        frappe.log_error(f"Activity log failed: {str(e)}", "Lead Activity Log")
        return False


def round_robin_by_role(role_name):
    """Round robin assignment for users with specific role"""
    users = frappe.get_all(
        "Has Role",
        filters={"role": role_name, "parenttype": "User"},
        pluck="parent"
    )
    
    if not users:
        return None
    
    enabled_users = []
    for user in users:
        if frappe.db.get_value("User", user, "enabled"):
            enabled_users.append(user)
    
    if not enabled_users:
        return None
    
    cache_key = f"round_robin_role_{role_name}"
    last_user = frappe.cache().get_value(cache_key)
    
    if not last_user or last_user not in enabled_users:
        next_user = enabled_users[0]
    else:
        current_index = enabled_users.index(last_user)
        next_index = (current_index + 1) % len(enabled_users)
        next_user = enabled_users[next_index]
    
    frappe.cache().set_value(cache_key, next_user)
    return next_user


def get_least_busy_user_by_role(role_name):
    """Get user with fewest leads today from a specific role"""
    from frappe.utils import nowdate
    
    users = frappe.get_all(
        "Has Role",
        filters={"role": role_name, "parenttype": "User"},
        pluck="parent"
    )
    
    if not users:
        return None
    
    today = nowdate()
    user_loads = []
    
    for user in users:
        if frappe.db.get_value("User", user, "enabled"):
            lead_count = frappe.db.count(
                "FinHub Lead",
                filters={
                    "assigned_to": user,
                    "creation": ["between", [today, frappe.utils.add_days(today, 1)]]
                }
            )
            user_loads.append({"user": user, "count": lead_count})
    
    if not user_loads:
        return None
    
    user_loads.sort(key=lambda x: x["count"])
    return user_loads[0]["user"]


def get_default_active_user():
    """Get any active user as default"""
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        pluck="name",
        limit=1
    )
    return users[0] if users else "Administrator"


def get_user_by_role(role_name):
    """Get first user with specific role"""
    return frappe.db.get_value(
        "Has Role",
        {"role": role_name, "parenttype": "User"},
        "parent"
    )


def get_assignment_user(region=None, vertical=None, source=None, priority=None, email=None, company=None):
    """
    Dynamic Assignment Engine
    Reads rules from FinHub Assignment Rule
    """
    try:
        rules = frappe.get_all(
            "FinHub Assignment Rule",
            filters={"is_active": 1},
            fields=["name", "region", "vertical", "priority", "assign_to"],
            order_by="priority desc, creation asc"
        )

        for rule in rules:
            # Match Region
            if rule.region and region:
                if str(rule.region).strip().lower() != str(region).strip().lower():
                    continue

            # Match Vertical
            if rule.vertical and vertical:
                if str(rule.vertical).strip().lower() != str(vertical).strip().lower():
                    continue

            # Match Priority
            if rule.priority and priority:
                if str(rule.priority).strip().lower() != str(priority).strip().lower():
                    continue

            # User Validation
            if rule.assign_to:
                is_enabled = frappe.db.get_value("User", rule.assign_to, "enabled")
                if is_enabled:
                    return rule.assign_to

        # FALLBACK USER
        return get_default_active_user()

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Dynamic Assignment Engine Failed")
        return get_default_active_user()


def send_lead_notification(lead):
    """Send email notification to assigned user"""
    if not lead.assigned_to:
        return
    
    try:
        user = frappe.get_doc("User", lead.assigned_to)
        if not user.email:
            return
        
        frappe.sendmail(
            recipients=[user.email],
            subject=f"New Lead Assigned: {lead.lead_name}",
            message=f"""
            <h3>New Lead Assigned to You</h3>
            <p><strong>Lead Name:</strong> {lead.lead_name}</p>
            <p><strong>Email:</strong> {lead.email}</p>
            <p><strong>Phone:</strong> {lead.phone or 'N/A'}</p>
            <p><strong>Priority:</strong> {lead.priority}</p>
            <p><strong>Source:</strong> {lead.source}</p>
            <br>
            <p><a href="{frappe.utils.get_url_to_form('FinHub Lead', lead.name)}">Click here to view lead</a></p>
            """
        )
        
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"New lead assigned: {lead.lead_name}",
            "for_user": lead.assigned_to,
            "type": "Alert",
            "document_type": "FinHub Lead",
            "document_name": lead.name
        }).insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        # Log activity for notification
        log_lead_activity(
            lead.name,
            "Email Sent",
            f"Notification sent to {user.email} for lead assignment",
            performed_by="System"
        )
        
    except Exception as e:
        frappe.log_error(f"Notification failed: {str(e)}", "Lead Notification")


def create_auto_ticket(lead, data):
    """Auto-create ticket based on lead data"""
    should_create = False
    ticket_reason = ""
    
    if data.get("signup_type") == "sandbox":
        should_create = True
        ticket_reason = "Sandbox setup required"
    elif data.get("priority") == "High":
        should_create = True
        ticket_reason = "High priority lead needs immediate attention"
    elif data.get("source") == "Tenant Registration":
        should_create = True
        ticket_reason = "New tenant registration - setup assistance needed"
    
    if not should_create:
        return None
    
    ticket = frappe.get_doc({
        "doctype": "FinHub Ticket",
        "subject": f"{ticket_reason} - {lead.lead_name}",
        "ticket_type": "Support",
        "lead_reference": lead.name,
        "assigned_to": lead.assigned_to,
        "priority": "High" if data.get("priority") == "High" else "Medium",
        "description": f"""
        <h4>Auto-generated Ticket</h4>
        <p><strong>Lead:</strong> {lead.lead_name}</p>
        <p><strong>Email:</strong> {lead.email}</p>
        <p><strong>Reason:</strong> {ticket_reason}</p>
        <hr>
        <pre>{json.dumps(data, indent=2, default=str)[:500]}</pre>
        """
    })
    ticket.insert(ignore_permissions=True)
    frappe.db.commit()
    
    # Log activity for ticket creation
    log_lead_activity(
        lead.name,
        "Task Created",
        f"Auto-created ticket {ticket.name}: {ticket_reason}",
        performed_by="System"
    )
    
    return ticket


def build_response(success=True, message="", data=None):
    """Standard API response"""
    return {
        "success": success,
        "message": message,
        "data": data or {}
    }


@frappe.whitelist(allow_guest=True)
def create_lead_from_event(*args, **kwargs):
    """
    Dynamic Lead Creation API/Webhook
    Supports: JSON body, Form data, Webhook payloads
    """
    try:
        data = frappe.local.form_dict or {}
        
        # Handle direct function calls with arguments
        if kwargs:
            data.update(kwargs)
        if args and len(args) > 0 and isinstance(args[0], dict):
            data.update(args[0])
        
        # Raw JSON Body
        if frappe.request and frappe.request.data:
            try:
                json_data = json.loads(frappe.request.data)
                data.update(json_data)
            except Exception:
                pass
        
        if isinstance(data, str):
            data = json.loads(data)
        
        email = (data.get("email") or "").strip().lower()
        if not email:
            return build_response(success=False, message=_("Email is required"))
        
        lead_name = data.get("lead_name") or data.get("name") or email.split("@")[0]
        
        existing_lead = frappe.db.exists("FinHub Lead", {"email": email})
        if existing_lead:
            return build_response(success=False, message=_("Lead already exists"), data={"lead_id": existing_lead})
        
        source = data.get("source") or "API"
        priority = data.get("priority") or "Medium"
        status = data.get("status") or "New"
        
        # Get and validate region
        region = data.get("region")
        if region:
            # Get the actual Branch document
            branch_doc = frappe.db.get_value("Branch", {"name": region}, "name")
            if not branch_doc:
                # Try case-insensitive search
                branch_doc = frappe.db.get_value("Branch", {"name": ["like", region]}, "name")
            if not branch_doc:
                available_branches = frappe.get_all("Branch", pluck="name", limit=5)
                return build_response(
                    success=False, 
                    message=f"Could not find Region: {region}. Available branches: {', '.join(available_branches) if available_branches else 'No branches found'}"
                )
            region = branch_doc  # Use the actual document name
        
        # Get and validate vertical
        vertical = data.get("vertical")
        if vertical:
            # Get the actual Business Vertical document
            vertical_doc = frappe.db.get_value("Business Vertical", {"name": vertical}, "name")
            if not vertical_doc:
                # Try case-insensitive search
                vertical_doc = frappe.db.get_value("Business Vertical", {"name": ["like", vertical]}, "name")
            if not vertical_doc:
                available_verticals = frappe.get_all("Business Vertical", pluck="name", limit=5)
                return build_response(
                    success=False, 
                    message=f"Could not find Vertical: {vertical}. Available verticals: {', '.join(available_verticals) if available_verticals else 'No verticals found'}"
                )
            vertical = vertical_doc  # Use the actual document name
        
        # Get assigned user
        assigned_to = get_assignment_user(
            region=region,
            vertical=vertical,
            source=source,
            priority=priority,
            email=email,
            company=data.get("company")
        )
        
        reserved_fields = [
            "lead_name", "name", "email", "phone", "source",
            "event_type", "region", "vertical", "priority",
            "status", "company", "notes"
        ]
        
        custom_payload = {}
        for key, value in data.items():
            if key not in reserved_fields:
                custom_payload[key] = value
        
        # Create lead document
        lead = frappe.get_doc({
            "doctype": "FinHub Lead",
            "lead_name": lead_name,
            "email": email,
            "phone": data.get("phone"),
            "company": data.get("company"),
            "source": source,
            "event_type": data.get("event_type"),
            "status": status,
            "priority": priority,
            "assigned_to": assigned_to,
            "region": region,
            "vertical": vertical,
            "notes": data.get("notes"),
            "created_via": "API/Webhook",
            "custom_fields": json.dumps(custom_payload, indent=4, default=str)
        })
        
        # Insert with ignore_links to bypass doctype validation
        lead.flags.ignore_links = True
        lead.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # LOG ACTIVITY: Lead Created
        log_lead_activity(
            lead.name,
            "Note Added",
            f"Lead created via {source} with priority {priority}",
            performed_by="API/Webhook"
        )
        
        # LOG ACTIVITY: Assignment (if assigned)
        if assigned_to:
            log_lead_activity(
                lead.name,
                "Assignment",
                f"Lead assigned to {assigned_to}",
                new_value=assigned_to,
                performed_by="System"
            )
        
        # Auto-create ticket if needed
        ticket = create_auto_ticket(lead, data)
        
        # Send notification to assigned user
        send_lead_notification(lead)
        
        response_data = {
            "lead_id": lead.name,
            "assigned_to": assigned_to
        }
        
        if ticket:
            response_data["ticket_id"] = ticket.name
        
        # Create Automation Event Log
        try:
            event_log = frappe.get_doc({
                "doctype": "FinHub Automation Event Log",
                "event_type": data.get("event_type") or "lead_created",
                "source": source,
                "status": "Success",
                "request_payload": json.dumps(data, indent=4, default=str),
                "response_payload": json.dumps(response_data, indent=4, default=str),
                "reference_doctype": "FinHub Lead",
                "reference_name": lead.name,
                "processing_time": 0.0,
                "created_by": frappe.session.user
            })
            event_log.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            pass
        
        return build_response(
            success=True,
            message=_("Lead created successfully"),
            data=response_data
        )
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "FinHub Lead API Error")
        return build_response(success=False, message=f"Internal server error: {str(e)}")


@frappe.whitelist()
def update_lead_status(lead_id, new_status, notes=None):
    """
    Update lead status and log the change
    """
    try:
        lead = frappe.get_doc("FinHub Lead", lead_id)
        old_status = lead.status
        
        if old_status == new_status:
            return {"success": False, "message": "Status is already " + new_status}
        
        # Update status
        lead.status = new_status
        if notes:
            lead.notes = (lead.notes or "") + f"\n{notes}"
        lead.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Log the status change
        log_lead_activity(
            lead.name,
            "Status Change",
            f"Status changed from {old_status} to {new_status}",
            old_value=old_status,
            new_value=new_status,
            performed_by=frappe.session.user
        )
        
        return {
            "success": True,
            "message": f"Lead status updated to {new_status}",
            "data": {"lead_id": lead.name, "old_status": old_status, "new_status": new_status}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def add_lead_note(lead_id, note):
    """
    Add note to lead and log activity
    """
    try:
        lead = frappe.get_doc("FinHub Lead", lead_id)
        lead.notes = (lead.notes or "") + f"\n{note}"
        lead.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Log the note
        log_lead_activity(
            lead.name,
            "Note Added",
            note,
            performed_by=frappe.session.user
        )
        
        return {"success": True, "message": "Note added successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_lead_activities(lead_id, limit=20):
    """
    Get all activities for a lead
    """
    try:
        activities = frappe.get_list(
            "Lead Activity Log",
            filters={"lead": lead_id},
            fields=["activity_type", "description", "old_value", "new_value", "performed_by", "creation"],
            order_by="creation desc",
            limit=limit
        )
        return {"success": True, "data": activities, "count": len(activities)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_leads(filters=None):
    """Get leads list"""
    try:
        if filters and isinstance(filters, str):
            filters = json.loads(filters)
        
        leads = frappe.get_list(
            "FinHub Lead", 
            filters=filters or {},
            fields=["name", "lead_name", "email", "source", "status", "priority", "assigned_to"],
            order_by="creation desc",
            ignore_permissions=True
        )
        return {"success": True, "data": leads, "count": len(leads)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_assignment_stats():
    """Get assignment statistics for dashboard"""
    try:
        from frappe.utils import nowdate
        today = nowdate()
        
        stats = {
            "total_leads": frappe.db.count("FinHub Lead"),
            "assigned_leads": frappe.db.count("FinHub Lead", filters={"assigned_to": ["!=", ""]}),
            "unassigned_leads": frappe.db.count("FinHub Lead", filters={"assigned_to": ["is", "not set"]}),
            "leads_today": frappe.db.count("FinHub Lead", filters={"creation": [">=", today]}),
        }
        
        if stats["total_leads"] > 0:
            stats["assignment_rate"] = round((stats["assigned_leads"] / stats["total_leads"]) * 100, 2)
        else:
            stats["assignment_rate"] = 0
        
        return {"success": True, "data": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}