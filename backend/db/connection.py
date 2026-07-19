import contextlib
from typing import Any, Generator

from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from backend.config import settings
from backend.logging import logger


class DatabaseManager:
    _pool = None
    _init_attempted = False  # Guard: only attempt pool init once per process

    @classmethod
    def initialize(cls):
        """
        Initializes the PostgreSQL database connection pool.
        Only attempted once; if it fails the pool stays None (offline mode).
        """
        if cls._init_attempted:
            return
        cls._init_attempted = True
        try:
            logger.info(
                "Initializing database connection pool",
                extra={
                    "host": settings.database.host,
                    "port": settings.database.port,
                    "dbname": settings.database.dbname,
                    "user": settings.database.user,
                },
            )
            cls._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                host=settings.database.host,
                port=settings.database.port,
                dbname=settings.database.dbname,
                user=settings.database.user,
                password=settings.database.password,
                connect_timeout=3,
            )
        except Exception:
            logger.critical(
                "Failed to initialize database connection pool — running in offline mode",
                exc_info=True,
            )
            cls._pool = None  # Stay None; callers degrade to offline fallbacks

    @classmethod
    def get_connection(cls):
        """
        Retrieves a connection from the pool.
        """
        cls.initialize()
        if cls._pool is None:
            from psycopg2 import OperationalError

            raise OperationalError("Database pool unavailable — offline mode active")
        return cls._pool.getconn()

    @classmethod
    def put_connection(cls, conn):
        """
        Returns a connection back to the pool.
        """
        if cls._pool:
            cls._pool.putconn(conn)

    @classmethod
    def close_all(cls):
        """
        Closes all connections in the pool.
        """
        if cls._pool:
            logger.info("Closing all database connections in the pool")
            cls._pool.closeall()
            cls._pool = None


@contextlib.contextmanager
def get_db_cursor() -> Generator[Any, None, None]:
    """
    Context manager to safely yield a database connection cursor.
    Auto-commits transactions or rolls them back in case of failures.
    """
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Database transaction failed; rolled back", exc_info=True)
        raise e
    finally:
        cursor.close()
        DatabaseManager.put_connection(conn)
