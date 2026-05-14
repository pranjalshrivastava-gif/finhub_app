# File:
# /home/pranjal/Desktop/finhub_local/erp_stack_v15/apps/finhub/finhub/api/testing_data.py

import frappe
from frappe import _
from frappe.utils import today


# =========================================================
# AUTO COMPANY NUMBER
# =========================================================

def get_next_company():

    companies = frappe.get_all(
        "Company",
        filters={
            "company_name": ["like", "Test Company %"]
        },
        pluck="company_name"
    )

    max_no = 0

    for company in companies:

        try:
            no = int(company.replace("Test Company ", ""))
            max_no = max(max_no, no)

        except Exception:
            pass

    next_no = max_no + 1

    return {
        "number": next_no,
        "company": f"Test Company {next_no}",
        "abbr": f"TC{next_no}"
    }


# =========================================================
# LOGGER
# =========================================================

def log(message):
    print(f"[OK] {message}")
    frappe.logger().info(message)


# =========================================================
# GENERIC GET OR CREATE
# =========================================================

def get_or_create(doctype, name, data):

    if frappe.db.exists(doctype, name):
        log(f"{doctype} Already Exists: {name}")
        return frappe.get_doc(doctype, name)

    doc = frappe.get_doc(data)

    doc.insert(ignore_permissions=True)

    frappe.db.commit()

    log(f"{doctype} Created: {doc.name}")

    return doc


# =========================================================
# ACCOUNT HELPERS
# =========================================================

def get_account(company, filters):

    filters["company"] = company

    return frappe.db.get_value(
        "Account",
        filters,
        "name"
    )


# =========================================================
# COMPANY
# =========================================================

def ensure_company(company, abbr):

    if frappe.db.exists("Company", company):
        log(f"Company Already Exists: {company}")
        return

    doc = frappe.get_doc({
        "doctype": "Company",
        "company_name": company,
        "abbr": abbr,
        "default_currency": "INR",
        "country": "India"
    })

    doc.insert(ignore_permissions=True)

    frappe.db.commit()

    log(f"Company Created: {company}")


# =========================================================
# CHART OF ACCOUNTS
# =========================================================

def ensure_chart_of_accounts(company):

    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts

    exists = frappe.db.exists(
        "Account",
        {
            "company": company,
            "is_group": 0
        }
    )

    if exists:
        log("Chart Of Accounts Already Exists")
        return

    create_charts(
        company=company,
        chart_template="Standard"
    )

    frappe.db.commit()

    log("Chart Of Accounts Created")


# =========================================================
# CONFIGURATION
# =========================================================

def ensure_configuration():

    # -----------------------------------------------------
    # ITEM GROUP
    # -----------------------------------------------------

    if not frappe.db.exists("Item Group", "Test Item Group"):

        frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": "Test Item Group",
            "parent_item_group": "All Item Groups"
        }).insert(ignore_permissions=True)

        frappe.db.commit()

        log("Item Group Created")

    # -----------------------------------------------------
    # UOM
    # -----------------------------------------------------

    if not frappe.db.exists("UOM", "Nos"):

        frappe.get_doc({
            "doctype": "UOM",
            "uom_name": "Nos"
        }).insert(ignore_permissions=True)

        frappe.db.commit()

        log("UOM Created")

    # -----------------------------------------------------
    # CUSTOMER GROUP
    # -----------------------------------------------------

    if not frappe.db.exists("Customer Group", "Commercial"):

        frappe.get_doc({
            "doctype": "Customer Group",
            "customer_group_name": "Commercial",
            "parent_customer_group": "All Customer Groups",
            "is_group": 0
        }).insert(ignore_permissions=True)

        frappe.db.commit()

        log("Customer Group Created")

    # -----------------------------------------------------
    # TERRITORY
    # -----------------------------------------------------

    if not frappe.db.exists("Territory", "All Territories"):

        frappe.get_doc({
            "doctype": "Territory",
            "territory_name": "All Territories",
            "is_group": 0
        }).insert(ignore_permissions=True)

        frappe.db.commit()

        log("Territory Created")


# =========================================================
# WAREHOUSE
# =========================================================

def ensure_warehouse(company, abbr):

    warehouse_name = f"Main Warehouse - {abbr}"

    if frappe.db.exists("Warehouse", warehouse_name):
        log(f"Warehouse Already Exists: {warehouse_name}")
        return warehouse_name

    warehouse = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": "Main Warehouse",
        "company": company
    })

    warehouse.insert(ignore_permissions=True)

    frappe.db.commit()

    log(f"Warehouse Created: {warehouse.name}")

    return warehouse.name


# =========================================================
# COMPANY ACCOUNT SETUP
# =========================================================

def setup_company_accounts(company, warehouse):

    receivable_account = get_account(
        company,
        {
            "account_type": "Receivable",
            "is_group": 0
        }
    )

    payable_account = get_account(
        company,
        {
            "account_type": "Payable",
            "is_group": 0
        }
    )

    stock_account = get_account(
        company,
        {
            "account_name": "Stock In Hand",
            "is_group": 0
        }
    )

    company_doc = frappe.get_doc("Company", company)

    company_doc.default_receivable_account = receivable_account
    company_doc.default_payable_account = payable_account
    company_doc.stock_received_but_not_billed = stock_account

    company_doc.save(ignore_permissions=True)

    warehouse_doc = frappe.get_doc("Warehouse", warehouse)

    warehouse_doc.account = stock_account

    warehouse_doc.save(ignore_permissions=True)

    frappe.db.commit()

    log("Company Accounts Configured")

    return {
        "receivable_account": receivable_account,
        "stock_account": stock_account
    }


# =========================================================
# CUSTOMER
# =========================================================

def ensure_customer(customer_name):

    if frappe.db.exists("Customer", customer_name):
        log(f"Customer Already Exists: {customer_name}")
        return

    doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_group": "Commercial",
        "territory": "All Territories"
    })

    doc.insert(ignore_permissions=True)

    frappe.db.commit()

    log(f"Customer Created: {customer_name}")


# =========================================================
# SUPPLIER
# =========================================================

def ensure_supplier(supplier_name):

    if frappe.db.exists("Supplier", supplier_name):
        log(f"Supplier Already Exists: {supplier_name}")
        return

    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": supplier_name,
        "supplier_group": "All Supplier Groups"
    })

    doc.insert(ignore_permissions=True)

    frappe.db.commit()

    log(f"Supplier Created: {supplier_name}")


# =========================================================
# ITEM
# =========================================================

def ensure_item(item_code):

    if frappe.db.exists("Item", item_code):
        log(f"Item Already Exists: {item_code}")
        return

    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "item_group": "Test Item Group",
        "stock_uom": "Nos",
        "is_stock_item": 1
    })

    item.insert(ignore_permissions=True)

    frappe.db.commit()

    log(f"Item Created: {item.name}")


# =========================================================
# PURCHASE INVOICE
# =========================================================

def create_purchase_invoice(
    company,
    supplier,
    item_code,
    warehouse
):

    doc = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "company": company,
        "supplier": supplier,
        "posting_date": today(),
        "update_stock": 1,
        "set_warehouse": warehouse,
        "items": [
            {
                "item_code": item_code,
                "qty": 5,
                "rate": 100,
                "warehouse": warehouse
            }
        ]
    })

    doc.insert(ignore_permissions=True)

    doc.submit()

    frappe.db.commit()

    log(f"Purchase Invoice Created: {doc.name}")

    return doc.name


# =========================================================
# SALES INVOICE
# =========================================================

def create_sales_invoice(
    company,
    customer,
    item_code,
    warehouse
):

    doc = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": company,
        "customer": customer,
        "posting_date": today(),
        "update_stock": 1,
        "set_warehouse": warehouse,
        "items": [
            {
                "item_code": item_code,
                "qty": 2,
                "rate": 150,
                "warehouse": warehouse
            }
        ]
    })

    doc.insert(ignore_permissions=True)

    doc.submit()

    frappe.db.commit()

    log(f"Sales Invoice Created: {doc.name}")

    return doc.name


# =========================================================
# JOURNAL ENTRY
# =========================================================

def create_journal_entry(company):

    asset_account = get_account(
        company,
        {
            "root_type": "Asset",
            "is_group": 0
        }
    )

    equity_account = get_account(
        company,
        {
            "root_type": "Equity",
            "is_group": 0
        }
    )

    doc = frappe.get_doc({
        "doctype": "Journal Entry",
        "company": company,
        "posting_date": today(),
        "voucher_type": "Journal Entry",
        "accounts": [
            {
                "account": asset_account,
                "debit_in_account_currency": 1000
            },
            {
                "account": equity_account,
                "credit_in_account_currency": 1000
            }
        ]
    })

    doc.insert(ignore_permissions=True)

    doc.submit()

    frappe.db.commit()

    log(f"Journal Entry Created: {doc.name}")

    return doc.name


# =========================================================
# PAYMENT ENTRY
# =========================================================

def create_payment_entry(
    company,
    customer,
    receivable_account
):

    asset_account = get_account(
        company,
        {
            "root_type": "Asset",
            "is_group": 0
        }
    )

    doc = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "company": company,
        "party_type": "Customer",
        "party": customer,
        "posting_date": today(),
        "paid_from": receivable_account,
        "paid_to": asset_account,
        "paid_amount": 500,
        "received_amount": 500
    })

    doc.insert(ignore_permissions=True)

    doc.submit()

    frappe.db.commit()

    log(f"Payment Entry Created: {doc.name}")

    return doc.name


# =========================================================
# MAIN API
# =========================================================

@frappe.whitelist()
def create_testing_entries():

    try:

        company_data = get_next_company()

        company = company_data["company"]
        abbr = company_data["abbr"]

        customer = f"Test Customer {company_data['number']}"
        supplier = f"Test Supplier {company_data['number']}"
        item_code = f"Test Item {company_data['number']}"

        log(f"STARTING TEST DATA FOR: {company}")

        ensure_company(company, abbr)

        ensure_chart_of_accounts(company)

        ensure_configuration()

        warehouse = ensure_warehouse(company, abbr)

        account_data = setup_company_accounts(
            company,
            warehouse
        )

        ensure_customer(customer)

        ensure_supplier(supplier)

        ensure_item(item_code)

        purchase_invoice = create_purchase_invoice(
            company,
            supplier,
            item_code,
            warehouse
        )

        sales_invoice = create_sales_invoice(
            company,
            customer,
            item_code,
            warehouse
        )

        journal_entry = create_journal_entry(company)

        payment_entry = create_payment_entry(
            company,
            customer,
            account_data["receivable_account"]
        )

        frappe.db.commit()

        log("ALL TEST ENTRIES CREATED SUCCESSFULLY")

        return {
            "success": True,
            "company": company,
            "message": _("Testing Entries Created Successfully"),
            "data": {
                "purchase_invoice": purchase_invoice,
                "sales_invoice": sales_invoice,
                "journal_entry": journal_entry,
                "payment_entry": payment_entry
            }
        }

    except Exception:

        frappe.db.rollback()

        frappe.log_error(
            title="Testing Entry Creation Failed",
            message=frappe.get_traceback()
        )

        return {
            "success": False,
            "message": frappe.get_traceback()
        }