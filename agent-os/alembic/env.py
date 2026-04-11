from alembic import context
from agent_os.db.connection import Base
from agent_os.config import Settings

config = context.config
config.set_main_option("sqlalchemy.url", Settings().database.url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

    import asyncio

    async def run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    def do_run_migrations(connection) -> None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
