import frappe
from frappe import _


@frappe.whitelist()
def bulk_hard_delete_companies(companies):

    if isinstance(companies, str):
        companies = frappe.parse_json(companies)

    results = []

    for company in companies:
        results.append(hard_delete_company(company))

    return {
        "success": True,
        "results": results
    }


@frappe.whitelist()
def hard_delete_company(company):

    try:

        frappe.only_for("System Manager")

        if not frappe.db.exists("Company", company):

            return {
                "success": False,
                "message": _("Company does not exist")
            }

        # ==========================================================
        # STEP 1: REMOVE REPOST ITEM VALUATION BLOCKERS
        # ==========================================================

        remove_repost_item_valuation_entries(company)

        # ==========================================================
        # STEP 2: FORCE CANCEL SUBMITTED DOCS
        # ==========================================================

        cancel_doctypes = [

            "Sales Invoice",
            "Purchase Invoice",
            "Payment Entry",
            "Journal Entry",
            "Stock Entry",
            "Delivery Note",
            "Purchase Receipt",
            "Sales Order",
            "Purchase Order",
            "Repost Item Valuation"
        ]

        for dt in cancel_doctypes:

            try:

                if not frappe.db.exists("DocType", dt):
                    continue

                meta = frappe.get_meta(dt)

                if not meta.has_field("company"):
                    continue

                docs = frappe.get_all(
                    dt,
                    filters={
                        "company": company
                    },
                    fields=["name", "docstatus"]
                )

                for d in docs:

                    try:

                        if d.docstatus == 1:

                            doc = frappe.get_doc(dt, d.name)

                            doc.flags.ignore_permissions = True
                            doc.flags.ignore_validate = True
                            doc.flags.ignore_links = True
                            doc.flags.ignore_mandatory = True
                            doc.flags.ignore_version = True

                            doc.cancel()

                            frappe.db.commit()

                    except Exception:
                        pass

            except Exception:
                pass

        # ==========================================================
        # STEP 3: DELETE LOW LEVEL TRANSACTION TABLES
        # ==========================================================

        transaction_tables = [

            # ACCOUNTING
            "GL Entry",
            "Payment Ledger Entry",

            # STOCK
            "Stock Ledger Entry",
            "Bin",
            "Serial No",
            "Batch",

            # REPOST
            "Repost Item Valuation",

            # SALES
            "Sales Invoice Item",
            "Sales Taxes and Charges",

            # PURCHASE
            "Purchase Invoice Item",
            "Purchase Taxes and Charges",

            # STOCK
            "Stock Entry Detail",

            # JOURNAL
            "Journal Entry Account",

            # PAYMENT
            "Payment Entry Reference"
        ]

        for dt in transaction_tables:

            force_delete_doctype_by_company(dt, company)

        # ==========================================================
        # STEP 4: DELETE MAIN DOCS
        # ==========================================================

        main_doctypes = [

            "Sales Invoice",
            "Purchase Invoice",
            "Payment Entry",
            "Journal Entry",
            "Stock Entry",
            "Delivery Note",
            "Purchase Receipt",
            "Sales Order",
            "Purchase Order",
            "Warehouse",
            "Account"
        ]

        for dt in main_doctypes:

            force_delete_doctype_by_company(
                dt,
                company,
                nested=True
            )

        # ==========================================================
        # STEP 5: DELETE OTHER COMPANY LINKED DOCS
        # ==========================================================

        delete_all_company_linked_docs(company)

        # ==========================================================
        # STEP 6: DELETE COMPANY
        # ==========================================================

        frappe.db.sql(
            """
            DELETE FROM `tabCompany`
            WHERE name=%s
            """,
            company
        )

        frappe.db.commit()

        return {
            "success": True,
            "message": _("Company permanently deleted")
        }

    except Exception:

        frappe.db.rollback()

        frappe.log_error(
            title="Hard Delete Company Failed",
            message=frappe.get_traceback()
        )

        return {
            "success": False,
            "message": frappe.get_traceback()
        }


def remove_repost_item_valuation_entries(company):

    try:

        if frappe.db.exists("DocType", "Repost Item Valuation"):

            frappe.db.sql(
                """
                DELETE FROM `tabRepost Item Valuation`
                WHERE company=%s
                """,
                company
            )

            frappe.db.commit()

    except Exception:

        frappe.log_error(
            title="Failed removing Repost Item Valuation",
            message=frappe.get_traceback()
        )


def force_delete_doctype_by_company(
    doctype,
    company,
    nested=False
):

    try:

        if not frappe.db.exists("DocType", doctype):
            return

        meta = frappe.get_meta(doctype)

        company_field = None

        for field in meta.fields:

            if (
                field.fieldtype == "Link"
                and field.options == "Company"
            ):
                company_field = field.fieldname
                break

        if not company_field:
            return

        order_by = "creation desc"

        if nested:
            order_by = "lft desc"

        names = frappe.get_all(
            doctype,
            filters={
                company_field: company
            },
            order_by=order_by,
            pluck="name"
        )

        for name in names:

            try:

                frappe.db.sql(
                    f"""
                    DELETE FROM `tab{doctype}`
                    WHERE name=%s
                    """,
                    name
                )

            except Exception:
                pass

        frappe.db.commit()

    except Exception:

        frappe.log_error(
            title=f"Failed deleting {doctype}",
            message=frappe.get_traceback()
        )


def delete_all_company_linked_docs(company):

    doctypes = frappe.get_all(
        "DocType",
        filters={
            "issingle": 0
        },
        pluck="name"
    )

    excluded = [
        "Company",
        "Account",
        "Warehouse"
    ]

    for dt in doctypes:

        if dt in excluded:
            continue

        try:

            meta = frappe.get_meta(dt)

            company_fields = []

            for field in meta.fields:

                if (
                    field.fieldtype == "Link"
                    and field.options == "Company"
                ):
                    company_fields.append(field.fieldname)

            if not company_fields:
                continue

            for fieldname in company_fields:

                try:

                    frappe.db.sql(
                        f"""
                        DELETE FROM `tab{dt}`
                        WHERE `{fieldname}`=%s
                        """,
                        company
                    )

                except Exception:
                    pass

            frappe.db.commit()

        except Exception:
            pass