import os
from datetime import datetime

from resource_translate import AbortTranslation, Translator, attr

import shopify
from db import Session

from . import session
from .db import Customer


class Person(Translator):
    constants = {"tags": os.getenv("SHOP_TAG", "shopify")}
    mapping = {
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
        "phone": "phone",
        "billing_address": {
            "address1": "default_address.address1",
            "address2": "default_address.address2",
            "city": "default_address.city",
            "state": "default_address.province",
            "zip": "default_address.zip",
            "country_code": "default_address.country_code",
        },
    }


class Donation(Translator):
    constants = {"tracking_code_slug": os.getenv("SHOP_TRACKING_CODE", "shopify")}

    @session
    def __init__(self, resource, from_map=False, **kwargs):
        self.trxs = [
            trx
            for trx in shopify.Transaction.find(
                order_id=resource.id,
                in_shop_currency=True,
                fields="amount,processed_at,gateway,kind,status,test",
                limit=100,
            )
            if not trx.test
            and trx.kind in {"sale", "capture", "refund"}
            and trx.status == "success"
        ]

        super().__init__(resource, from_map, **kwargs)

    @attr
    def succeeded_at(self):
        if datetime.fromisoformat(self.trxs[0].processed_at).year < int(
            os.getenv("SHOP_FROM_YEAR", -1)
        ):
            raise AbortTranslation

        return self.trxs[0].processed_at

    @attr
    def donor_id(self):
        try:
            self.customer_metafield = self.resource.customer.metafields(
                namespace="nationbuilder", key="id"
            )[0]

            return self.customer_metafield.value
        except AttributeError:
            if not self.resource.email:
                raise

            with Session() as db:
                self.customer = db.query(Customer).get(self.resource.email)

            return self.customer.id

    @attr
    def amount_in_cents(self):
        return round(
            sum(
                (-1 if trx.kind == "refund" else 1) * float(trx.amount)
                for trx in self.trxs
            )
            * 100
        )

    @attr
    def payment_type_name(self):
        return (
            "Credit Card"
            if self.trxs[0].gateway
            in {
                type.strip()
                for type in os.getenv(
                    "SHOP_CC_TYPES", "stripe, shopify_payments"
                ).split(",")
            }
            else "Other"
        )


class UpdatedDonation(Donation):
    constants = {}
    succeeded_at = donor_id = payment_type_name = None
