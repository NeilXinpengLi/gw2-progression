"""Alembic migrations for GW2 Progression."""

from logging.config import fileConfig

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — represents the current database schema
meta = MetaData()

# Core tables
price_snapshots = Table(
    "price_snapshots", meta,
    Column("id", Integer, primary_key=True),
    Column("item_id", Integer, nullable=False),
    Column("buy_unit_price", Integer, nullable=False),
    Column("buy_quantity", Integer, nullable=False),
    Column("sell_unit_price", Integer, nullable=False),
    Column("sell_quantity", Integer, nullable=False),
    Column("fetched_at", String, nullable=False),
)

account_snapshots = Table(
    "account_snapshots", meta,
    Column("id", Integer, primary_key=True),
    Column("account_name", String, nullable=False),
    Column("api_key_hash", String),
    Column("total_value_buy", Integer),
    Column("total_value_sell", Integer),
    Column("wallet_value", Integer),
    Column("created_at", String),
)

# Add more tables as needed — for the initial migration, we capture the full schema
# by connecting to the database

# Reflect the existing DB schema for autogenerate

_engine = create_engine(config.get_main_option("sqlalchemy.url"))
_meta = MetaData()
try:
    _meta.reflect(bind=_engine)
except Exception:
    pass
target_metadata = _meta

def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = _engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
