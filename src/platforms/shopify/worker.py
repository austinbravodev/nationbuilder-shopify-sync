from db import Session

from celery import Task, chain

from .db import Error


class BaseTask(Task):
    rate_limit = "24/m"
    time_limit = 30
    autoretry_for = (Exception,)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if retval and isinstance(retval, list):
            chain(retval).delay()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        with Session() as db:
            with db.begin():
                db.add(
                    Error(
                        **(
                            (
                                {"id": args[0], "resource_type": "customer"}
                                if args
                                else {
                                    "id": kwargs["order_id"],
                                    "resource_type": "order",
                                }
                            )
                            if "create_person" in self.name
                            else {"id": args[0], "resource_type": "order"}
                        )
                    )
                )
