import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import _

import requests
import json
import base64
import jwt
import time


class CommercialOffer(Document):

    def validate(self):

        self.apply_country_mapping()

        self.apply_pricing_rules()

        self.calculate_totals()

    def apply_country_mapping(self):

        if not self.country:
            return

        mapping = frappe.db.get_value(
            "Country Company Mapping",
            {
                "country": self.country,
                "is_active": 1
            },
            [
                "company",
                "branch",
                "default_currency",
                "sales_manager_email"
            ],
            as_dict=True
        )

        if not mapping:
            return

        self.company = mapping.company
        self.branch = mapping.branch
        self.currency = mapping.default_currency
        self.sales_manager_email = mapping.sales_manager_email

    def apply_pricing_rules(self):

        if not self.get("items"):
            return

        pricing_rules = frappe.get_all(
            "Pricing Rule Logic",
            filters={
                "is_active": 1
            },
            fields=[
                "name",
                "vertical",
                "country",
                "minimum_qty",
                "discount_percentage",
                "markup_percentage",
                "currency",
                "priority"
            ],
            order_by="priority asc"
        )

        for item in self.items:

            qty = flt(item.qty)

            # Prevent recursive pricing
            base_rate = flt(item.base_rate or item.rate)

            final_rate = base_rate

            for rule in pricing_rules:

                rule_match = True

                # Vertical Match
                if rule.vertical and rule.vertical != self.vertical:
                    rule_match = False

                # Country Match
                if rule.country and rule.country != self.country:
                    rule_match = False

                # Quantity Match
                if rule.minimum_qty and qty < flt(rule.minimum_qty):
                    rule_match = False

                if not rule_match:
                    continue

                # Apply Markup
                if flt(rule.markup_percentage):

                    markup_amount = (
                        final_rate * flt(rule.markup_percentage) / 100
                    )

                    final_rate += markup_amount

                # Apply Discount
                if flt(rule.discount_percentage):

                    discount_amount = (
                        final_rate * flt(rule.discount_percentage) / 100
                    )

                    final_rate -= discount_amount

                # Override Currency
                if rule.currency:
                    self.currency = rule.currency

            item.rate = final_rate
            item.amount = qty * final_rate

    def calculate_totals(self):

        total = 0.0

        if not self.get("items"):
            self.total_amount = 0.0
            return

        for item in self.items:

            qty = flt(item.qty)
            rate = flt(item.rate)

            item.amount = qty * rate

            total += item.amount

        self.total_amount = total

    @frappe.whitelist()
    def get_module_data(self, finhub_module):

        if not finhub_module:
            return {
                "base_price": 0.0
            }

        data = frappe.db.get_value(
            "Finhub Module",
            finhub_module,
            ["base_price"],
            as_dict=True
        )

        return data if data else {
            "base_price": 0.0
        }

    @frappe.whitelist()
    def calculate_client_side_totals(self):

        self.apply_country_mapping()

        self.apply_pricing_rules()

        self.calculate_totals()

        return {
            "total_amount": self.total_amount,
            "currency": self.currency,
            "company": self.company,
            "branch": self.branch,
            "sales_manager_email": self.sales_manager_email,
            "items": self.items
        }

    @frappe.whitelist()
    def send_to_docusign(self):

        try:

            if self.docusign_envelope_id:

                return {
                    "status": "error",
                    "message": _("Envelope already created")
                }

            # Placeholder Logic
            # Replace with actual DocuSign integration

            fake_envelope_id = f"ENV-{self.name}"

            self.db_set(
                "docusign_envelope_id",
                fake_envelope_id
            )

            self.db_set(
                "status",
                "Sent"
            )

            return {
                "status": "success",
                "envelope_id": fake_envelope_id
            }

        except Exception:

            frappe.log_error(
                frappe.get_traceback(),
                "Commercial Offer DocuSign Error"
            )

            return {
                "status": "error",
                "message": _("Failed to send envelope")
            }