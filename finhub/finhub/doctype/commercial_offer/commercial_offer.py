import frappe
from frappe.model.document import Document
from frappe.utils import flt, today
from frappe import _

from erpnext.setup.utils import get_exchange_rate


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

    def get_conversion_rate(self):

        company_currency = "INR"

        target_currency = self.currency or "INR"

        if company_currency == target_currency:
            return 1.0

        exchange_rate = get_exchange_rate(
            company_currency,
            target_currency,
            transaction_date=today()
        )

        if not exchange_rate:

            frappe.throw(
                _(
                    "Currency Exchange missing for {0} to {1}"
                ).format(
                    company_currency,
                    target_currency
                )
            )

        return flt(exchange_rate)

    def apply_pricing_rules(self):

        if not self.get("items"):
            return

        conversion_rate = self.get_conversion_rate()

        self.conversion_rate = conversion_rate

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

            # ALWAYS USE HIDDEN INR VALUE
            base_rate_inr = flt(item.base_rate_inr)

            if not base_rate_inr:

                item.base_rate = 0
                item.rate = 0
                item.amount = 0

                continue

            final_rate_inr = base_rate_inr

            for rule in pricing_rules:

                rule_match = True

                # Vertical Match
                if (
                    rule.vertical
                    and rule.vertical != self.vertical
                ):
                    rule_match = False

                # Country Match
                if (
                    rule.country
                    and rule.country != self.country
                ):
                    rule_match = False

                # Qty Match
                if (
                    rule.minimum_qty
                    and qty < flt(rule.minimum_qty)
                ):
                    rule_match = False

                if not rule_match:
                    continue

                # Apply Markup
                if flt(rule.markup_percentage):

                    final_rate_inr += (
                        final_rate_inr
                        * flt(rule.markup_percentage)
                        / 100
                    )

                # Apply Discount
                if flt(rule.discount_percentage):

                    final_rate_inr -= (
                        final_rate_inr
                        * flt(rule.discount_percentage)
                        / 100
                    )

            # Convert Base Rate
            converted_base_rate = (
                base_rate_inr * conversion_rate
            )

            # Convert Final Rate
            converted_rate = (
                final_rate_inr * conversion_rate
            )

            item.base_rate = converted_base_rate

            item.rate = converted_rate

            item.amount = qty * converted_rate

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
            "conversion_rate": self.conversion_rate,
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

            # Replace with actual DocuSign Integration
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