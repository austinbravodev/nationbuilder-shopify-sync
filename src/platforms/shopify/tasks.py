from requests.exceptions import HTTPError
from resource_translate import AbortTranslation
import shopify

from db import Session
from nationbuilder_api import NationBuilderClient
from nationbuilder_api.resp_procs import payload_filter
from worker import queue

from . import session
from .db import Customer
from .resources import Donation, Person, UpdatedDonation
from .worker import BaseTask


@queue.task(base=BaseTask)
@session
def handle_order(order_id):
    tasks = []
    order = shopify.Order.find(order_id, fields="customer,email,id")

    try:
        if not order.customer.metafields(namespace="nationbuilder", key="id"):
            tasks.append(create_person.si(order.customer.id))
    except AttributeError:
        if not order.email:
            raise

        with Session() as db:
            if not db.query(Customer).get(order.email):
                tasks.append(create_person.si(order_id=order_id))

    tasks.append(
        update_donation.si(order_id)
        if order.metafields(namespace="nationbuilder", key="id")
        else create_donation.si(order_id)
    )

    return tasks


@queue.task(base=BaseTask)
@session
def create_person(customer_id=None, order_id=None):
    if customer_id:
        customer = shopify.Customer.find(
            customer_id,
            fields="default_address,email,id,first_name,last_name,phone",
        )
    elif order_id:
        customer = shopify.Order.find(order_id, fields="email")

        if not customer.email:
            raise AttributeError

    with NationBuilderClient() as nb:
        person_id = nb.people.update(
            Person(customer).repr, resp_proc=payload_filter("id")
        )

    if customer_id:
        customer.add_metafield(
            shopify.Metafield(
                {
                    "namespace": "nationbuilder",
                    "key": "id",
                    "value": person_id,
                    "value_type": "integer",
                }
            )
        )
    elif order_id:
        with Session() as db:
            with db.begin():
                db.add(Customer(email=customer.email, id=person_id))


@queue.task(base=BaseTask)
@session
def create_donation(order_id):
    order = shopify.Order.find(order_id, fields="customer,email,id")

    try:
        _donation = Donation(order)
    except AbortTranslation:
        return

    with NationBuilderClient() as nb:
        try:
            donation_id = nb.donations.add(
                _donation.repr, resp_proc=payload_filter("id")
            )
        except HTTPError as exc:
            if exc.response.status_code == 404:
                try:
                    _donation.customer_metafield.destroy()
                except AttributeError:
                    with Session() as db:
                        with db.begin():
                            db.delete(_donation.customer)

                return [handle_order.si(order_id)]
            raise

        try:
            order.add_metafield(
                shopify.Metafield(
                    {
                        "namespace": "nationbuilder",
                        "key": "id",
                        "value": donation_id,
                        "value_type": "integer",
                        "description": _donation.repr["amount_in_cents"],
                    }
                )
            )
        except Exception:
            nb.donations.remove(donation_id)
            raise


@queue.task(base=BaseTask)
@session
def update_donation(order_id):
    order = shopify.Order.find(order_id, fields="id")
    donation = UpdatedDonation(order).repr
    metafield = order.metafields(namespace="nationbuilder", key="id")[0]

    if int(metafield.description) != donation["amount_in_cents"]:
        try:
            with NationBuilderClient() as nb:
                nb.donations.update(metafield.value, donation)
        except HTTPError as exc:
            if exc.response.status_code != 404:
                raise

            metafield.destroy()
