import shopify
from db import engine, Session

from . import paginate, session
from .db import Base, LastUpdate, Order
from .tasks import handle_order


def init_db(datetime="2021-01-01T00:00:00-00:00"):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session() as db:
        with db.begin():
            db.add(LastUpdate(id=123456789, datetime=datetime))


@session
def sync():
    with Session() as db:
        with db.begin():
            last_update = db.query(LastUpdate).first()
            last_update_orders = {order.id for order in last_update.orders}

            for order in sorted(
                paginate(
                    shopify.Order,
                    updated_at_min=last_update.datetime,
                    status="any",
                    financial_status="paid,partially_paid,refunded,partially_refunded",
                    fields="id,test,updated_at",
                    limit=250,
                ),
                key=lambda order: order.updated_at,
            ):
                if not order.test and (
                    order.updated_at != last_update.datetime
                    or order.id not in last_update_orders
                ):
                    handle_order.delay(order.id)

                if order.updated_at != last_update.datetime:
                    last_update.datetime = order.updated_at
                    last_update.orders = [Order(id=order.id)]
                elif order.id not in {order.id for order in last_update.orders}:
                    last_update.orders.append(Order(id=order.id))
