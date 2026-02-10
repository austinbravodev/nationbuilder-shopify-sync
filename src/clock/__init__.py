if __name__ == "__main__":
    import os

    from apscheduler.schedulers.blocking import BlockingScheduler

    sched = BlockingScheduler()
    # sched.add_job("platforms.shopify.jobs:sync", "interval", minutes=int(os.getenv("SHOP_POLL_INT", 15)))
    sched.start()
