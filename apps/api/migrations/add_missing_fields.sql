-- Migration to add missing fields for complete feature implementation

-- Add missing fields to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20),
ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS locale VARCHAR(10),
ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

-- Add missing fields to sessions table
ALTER TABLE sessions 
ADD COLUMN IF NOT EXISTS revoked BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Create indexes for new fields
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
CREATE INDEX IF NOT EXISTS idx_users_phone_number ON users(phone_number);
CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON sessions(revoked);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at);

-- Update existing records to have default values
UPDATE users SET is_admin = FALSE WHERE is_admin IS NULL;
UPDATE sessions SET revoked = FALSE WHERE revoked IS NULL;
UPDATE sessions SET last_activity_at = last_active_at WHERE last_activity_at IS NULL;