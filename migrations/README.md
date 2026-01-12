# Database Migrations

This directory contains PostgreSQL migration scripts for the Transaction Bot application.

## Migration Files

- `001_create_bank_transactions_table.sql` - Creates the `bank_transactions` table with indexes and triggers

## Prerequisites

- PostgreSQL database (version 12 or higher recommended)
- Python 3.8+ (for Python migration runner)
- `psycopg2` package: `pip install psycopg2-binary`
- `python-dotenv` package: `pip install python-dotenv`

## Running Migrations

### Option 1: Using Python Script (Recommended)

1. Set up environment variables:
   ```bash
   # Option A: Use DATABASE_URL (Railway, Heroku format)
   export DATABASE_URL="postgresql://user:password@host:port/database"
   
   # Option B: Use individual variables
   export DB_HOST="localhost"
   export DB_PORT="5432"
   export DB_NAME="alkhidmat"
   export DB_USER="postgres"
   export DB_PASSWORD="your_password"
   ```

2. Run the migration script:
   ```bash
   python migrations/run_migration.py
   ```

### Option 2: Using psql Command Line

1. Connect to your PostgreSQL database:
   ```bash
   psql -h hostname -U username -d database_name
   ```

2. Run the migration file:
   ```sql
   \i migrations/001_create_bank_transactions_table.sql
   ```

   Or from command line:
   ```bash
   psql -h hostname -U username -d database_name -f migrations/001_create_bank_transactions_table.sql
   ```

### Option 3: Using Railway CLI

If deploying to Railway:

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```

2. Link your project:
   ```bash
   railway link
   ```

3. Run migration:
   ```bash
   railway run psql $DATABASE_URL -f migrations/001_create_bank_transactions_table.sql
   ```

### Option 4: Using pgAdmin or DBeaver

1. Open your database management tool (pgAdmin, DBeaver, etc.)
2. Connect to your PostgreSQL database
3. Open the SQL migration file
4. Execute the SQL script

## Table Schema

The `bank_transactions` table includes:

- **id** - Primary key (auto-incrementing)
- **booking_date** - Transaction booking date/time (VARCHAR)
- **value_date** - Transaction value date (VARCHAR)
- **doc_id** - Unique document ID from bank (VARCHAR)
- **stan** - System Trace Audit Number (VARCHAR)
- **description** - Transaction description (TEXT)
- **debit** - Debit amount (NUMERIC)
- **credit** - Credit amount (NUMERIC)
- **available_balance** - Available balance (NUMERIC)
- **gsheet_row** - Google Sheet row number (INTEGER, default: -1)
- **created_at** - Record creation timestamp (TIMESTAMP)
- **updated_at** - Record last update timestamp (TIMESTAMP)

## Indexes

The migration creates the following indexes for performance:

- `idx_bank_transactions_doc_id` - On `doc_id` column
- `idx_bank_transactions_value_date` - On `value_date` column
- `idx_bank_transactions_booking_date` - On `booking_date` column
- `idx_bank_transactions_credit` - Partial index on `credit` where credit > 0
- `idx_bank_transactions_gsheet_row` - On `gsheet_row` column

## Triggers

- `update_bank_transactions_updated_at` - Automatically updates `updated_at` timestamp on row updates

## Notes

- The migration uses `CREATE TABLE IF NOT EXISTS`, so it's safe to run multiple times
- Indexes use `CREATE INDEX IF NOT EXISTS` for idempotency
- The unique constraint on `doc_id` is commented out by default (uncomment if needed)
- All columns are nullable except `id` (which is auto-generated)

## Troubleshooting

### Connection Errors

If you get connection errors:
- Verify your `DATABASE_URL` or individual DB environment variables are correct
- Check that PostgreSQL is running and accessible
- Verify firewall rules allow connections from your IP

### Permission Errors

If you get permission errors:
- Ensure your database user has `CREATE TABLE` and `CREATE INDEX` permissions
- For Railway/Heroku, the provided database user should have all necessary permissions

### Duplicate Key Errors

If you get duplicate key errors when uncommenting the unique constraint:
- Check for existing duplicate `doc_id` values:
  ```sql
  SELECT doc_id, COUNT(*) 
  FROM bank_transactions 
  GROUP BY doc_id 
  HAVING COUNT(*) > 1;
  ```
- Clean up duplicates before adding the constraint

## Platform-Specific Notes

### Railway

Railway automatically provides a `DATABASE_URL` environment variable. Use:
```bash
railway run python migrations/run_migration.py
```

### Heroku

Heroku provides `DATABASE_URL` in config vars. Run:
```bash
heroku run python migrations/run_migration.py
```

### AWS RDS

Use individual environment variables or construct `DATABASE_URL`:
```bash
export DATABASE_URL="postgresql://user:password@rds-endpoint:5432/database"
python migrations/run_migration.py
```

### Local Development

For local PostgreSQL:
```bash
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="alkhidmat"
export DB_USER="postgres"
export DB_PASSWORD="your_password"
python migrations/run_migration.py
```


