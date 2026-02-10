from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class Customer(Base):
    __tablename__ = "shopify_customers"

    email = Column(String, primary_key=True)
    id = Column(Integer, nullable=False)


class LastUpdate(Base):
    __tablename__ = "shopify_last_updates"

    id = Column(Integer, primary_key=True)
    datetime = Column(String, nullable=False)
    orders = relationship("Order", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "shopify_orders"

    id = Column(BigInteger, primary_key=True)
    last_update = Column(Integer, ForeignKey("shopify_last_updates.id"))


class Error(Base):
    __tablename__ = "shopify_errors"

    id = Column(BigInteger, primary_key=True)
    resource_type = Column(String, nullable=False)
