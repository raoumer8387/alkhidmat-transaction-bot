-- PostgreSQL Migration Script for bank_transactions table
-- Compatible with Railway PostgreSQL and other PostgreSQL platforms
-- Matches SQLite schema and adds updated_at column with auto-update trigger

-- Create bank_transactions table matching SQLite schema
CREATE TABLE IF NOT EXISTS bank_transactions (
    id SERIAL PRIMARY KEY,
    booking_date TEXT,
    value_date TEXT,
    doc_id TEXT,
    description TEXT,
    debit REAL,
    credit REAL,
    available_balance REAL,
    gsheet_row INTEGER,
    stan TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_bank_transactions_doc_id ON bank_transactions(doc_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_value_date ON bank_transactions(value_date);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_booking_date ON bank_transactions(booking_date);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_credit ON bank_transactions(credit) WHERE credit IS NOT NULL AND credit > 0;
CREATE INDEX IF NOT EXISTS idx_bank_transactions_gsheet_row ON bank_transactions(gsheet_row);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_stan ON bank_transactions(stan) WHERE stan IS NOT NULL;

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_bank_transactions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at on row updates
DROP TRIGGER IF EXISTS trigger_bank_transactions_updated_at ON bank_transactions;
CREATE TRIGGER trigger_bank_transactions_updated_at
    BEFORE UPDATE ON bank_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_bank_transactions_updated_at();

