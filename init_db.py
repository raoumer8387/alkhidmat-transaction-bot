#!/usr/bin/env python3
"""
Quick database initialization script.
Initializes all database tables using db.initialize_schema().

Usage:
    python init_db.py

Environment Variables:
    DATABASE_URL - PostgreSQL connection string (Railway format)
    Or individual DB_* variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import db
except ImportError:
    print("❌ Error: Could not import db module")
    print("   Make sure you're running this from the project root directory")
    sys.exit(1)


def main():
    """Initialize database schema."""
    print("=" * 60)
    print("Database Initialization Script")
    print("=" * 60)
    
    # Check if DATABASE_URL is set
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"✅ Found DATABASE_URL")
        # Mask password in output
        if "@" in database_url:
            masked_url = database_url.split("@")[0].split(":")[0] + ":***@" + "@".join(database_url.split("@")[1:])
            print(f"   Connection: {masked_url}")
    else:
        print("⚠️  DATABASE_URL not found, using individual DB_* variables")
        db_host = os.getenv("DB_HOST", "localhost")
        db_name = os.getenv("DB_NAME", "alkhidmat")
        db_user = os.getenv("DB_USER", "postgres")
        print(f"   Host: {db_host}")
        print(f"   Database: {db_name}")
        print(f"   User: {db_user}")
    
    print("\nInitializing database schema...")
    
    try:
        db.initialize_schema()
        print("\n" + "=" * 60)
        print("✅ Database schema initialized successfully!")
        print("=" * 60)
        print("\nTables created:")
        print("  - sync_metadata")
        print("  - bank_transactions")
        print("  - verification_results")
        print("  - screenshots")
        print("\nAll indexes and constraints have been set up.")
        sys.exit(0)
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ Error initializing database schema")
        print("=" * 60)
        print(f"\nError: {str(e)}")
        print("\nTroubleshooting:")
        print("  1. Check that DATABASE_URL or DB_* variables are set correctly")
        print("  2. Verify database is running and accessible")
        print("  3. Ensure database user has CREATE TABLE permissions")
        print("  4. Check database connection logs for more details")
        sys.exit(1)


if __name__ == "__main__":
    main()

