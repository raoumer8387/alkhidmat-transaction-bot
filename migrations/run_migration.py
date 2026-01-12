#!/usr/bin/env python3
"""
PostgreSQL Migration Runner
Executes the bank_transactions table migration script.

Compatible with:
- Railway PostgreSQL
- Heroku PostgreSQL
- Local PostgreSQL
- AWS RDS PostgreSQL

Usage:
    python migrations/run_migration.py

Environment Variables:
    DATABASE_URL - PostgreSQL connection string
        Format: postgresql://user:password@host:port/database
        Example: postgresql://postgres:password@localhost:5432/alkhidmat
    
    Or individual variables:
    - DB_HOST (default: localhost)
    - DB_PORT (default: 5432)
    - DB_NAME (default: alkhidmat)
    - DB_USER (default: postgres)
    - DB_PASSWORD (required)
"""

import os
import sys
from pathlib import Path
import logging

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ Error: psycopg2 is not installed.")
    print("   Install it with: pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional, continue without it
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_database_connection():
    """
    Get PostgreSQL database connection from environment variables.
    
    Supports:
    - DATABASE_URL (Railway, Heroku format)
    - Individual DB_* environment variables
    
    Returns:
        psycopg2.connection: Database connection object
        
    Raises:
        ValueError: If required environment variables are missing
        psycopg2.Error: If connection fails
    """
    # Try DATABASE_URL first (used by Railway, Heroku, etc.)
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        logger.info("Using DATABASE_URL for database connection")
        # Handle postgres:// URLs (some platforms use this instead of postgresql://)
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            logger.info("Converted postgres:// to postgresql://")
        
        try:
            conn = psycopg2.connect(database_url)
            logger.info("✅ Successfully connected to database using DATABASE_URL")
            return conn
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to connect using DATABASE_URL: {e}")
            raise
    
    # Fallback to individual environment variables
    logger.info("DATABASE_URL not found, using individual environment variables")
    
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "alkhidmat")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    
    if not db_password:
        error_msg = (
            "❌ Database connection requires either:\n"
            "   - DATABASE_URL environment variable, or\n"
            "   - DB_PASSWORD environment variable (with optional DB_HOST, DB_PORT, DB_NAME, DB_USER)"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        logger.info(f"Connecting to PostgreSQL at {db_host}:{db_port}/{db_name} as {db_user}")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        logger.info("✅ Successfully connected to database")
        return conn
    except psycopg2.Error as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        raise


def read_sql_file(file_path: Path) -> str:
    """
    Read SQL migration file.
    
    Args:
        file_path: Path to the SQL file
        
    Returns:
        str: Contents of the SQL file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If the file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Migration file not found: {file_path}")
    
    logger.info(f"Reading migration file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        logger.info(f"✅ Successfully read migration file ({len(sql_content)} characters)")
        return sql_content
    except IOError as e:
        logger.error(f"❌ Failed to read migration file: {e}")
        raise


def execute_migration(sql_content: str, conn) -> bool:
    """
    Execute SQL migration content.
    
    Args:
        sql_content: SQL migration script content
        conn: Database connection object
        
    Returns:
        bool: True if migration succeeded, False otherwise
    """
    try:
        # Set isolation level to autocommit for DDL statements
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info("Executing migration SQL...")
        
        # Execute the migration SQL
        cursor.execute(sql_content)
        
        logger.info("✅ Migration SQL executed successfully")
        
        # Verify table was created
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'bank_transactions'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            logger.info("✅ Verified: bank_transactions table exists")
            
            # Check columns
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'bank_transactions'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            logger.info(f"✅ Table has {len(columns)} columns")
            
            # Check indexes
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'bank_transactions';
            """)
            indexes = cursor.fetchall()
            logger.info(f"✅ Found {len(indexes)} indexes")
            
            # Check triggers
            cursor.execute("""
                SELECT trigger_name 
                FROM information_schema.triggers 
                WHERE event_object_table = 'bank_transactions';
            """)
            triggers = cursor.fetchall()
            logger.info(f"✅ Found {len(triggers)} triggers")
        else:
            logger.warning("⚠️  Warning: bank_transactions table not found after migration")
        
        cursor.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Database error during migration: {e}")
        logger.error(f"   Error code: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        logger.error(f"   Error message: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during migration: {e}")
        logger.exception("Full traceback:")
        return False


def main():
    """Main function to run the migration."""
    logger.info("=" * 60)
    logger.info("PostgreSQL Migration Runner")
    logger.info("=" * 60)
    
    # Get migration file path
    script_dir = Path(__file__).parent
    migration_file = script_dir / "create_bank_transactions_postgresql.sql"
    
    if not migration_file.exists():
        logger.error(f"❌ Migration file not found: {migration_file}")
        logger.error("   Please ensure the migration file exists in the migrations directory")
        sys.exit(1)
    
    logger.info(f"📄 Migration file: {migration_file.absolute()}")
    
    # Read SQL file
    try:
        sql_content = read_sql_file(migration_file)
    except Exception as e:
        logger.error(f"❌ Failed to read migration file: {e}")
        sys.exit(1)
    
    # Get database connection
    try:
        conn = get_database_connection()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except psycopg2.Error as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error connecting to database: {e}")
        sys.exit(1)
    
    # Execute migration
    try:
        success = execute_migration(sql_content, conn)
        
        if success:
            logger.info("=" * 60)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("=" * 60)
            logger.error("❌ Migration failed!")
            logger.error("=" * 60)
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Unexpected error during migration execution: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    main()

