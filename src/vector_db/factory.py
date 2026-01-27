"""Factory for creating VectorDatabase instances based on configuration."""

from config import get_logger, get_vector_db_settings
from vector_db.base import VectorDatabase
from vector_db.mongodb import MongoDBVectorDatabase
from vector_db.sqlite import SQLiteVectorDatabase

logger = get_logger("vector_db.factory")


def create_vector_database() -> VectorDatabase:
    """
    Create a VectorDatabase instance based on configuration.

    Reads VECTOR_DB_TYPE from environment to determine which implementation to use:
    - "sqlite": Uses SQLiteVectorDatabase (sqlite-vec)
    - "mongodb": Uses MongoDBVectorDatabase (local MongoDB with embeddings)

    Returns:
        VectorDatabase instance

    Raises:
        ValueError: If unknown database type is configured
    """
    settings = get_vector_db_settings()
    db_type = settings.type.lower()

    if db_type == "sqlite":
        logger.info("Creating SQLite vector database")
        return SQLiteVectorDatabase(
            base_url=settings.sqlite_url,
            timeout=settings.timeout,
        )

    if db_type == "mongodb":
        logger.info("Creating MongoDB vector database")
        return MongoDBVectorDatabase(
            base_url=settings.mongodb_api_url,
            timeout=settings.timeout,
        )

    msg = f"Unknown database type: {db_type}. Use 'sqlite' or 'mongodb'."
    raise ValueError(msg)
