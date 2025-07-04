-- Create the roles table first since it's referenced by system_users
CREATE TABLE roles (
    id CHAR(32) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    permissions JSON DEFAULT '{}',
    is_active BOOLEAN DEFAULT 1,
    level INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_id CHAR(32) NULL
);

-- Create the system_users table
CREATE TABLE system_users (
    id CHAR(32) PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    email VARCHAR(254) UNIQUE NOT NULL,
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    user_type VARCHAR(20) DEFAULT 'STAFF',
    status VARCHAR(20) DEFAULT 'PENDING',
    is_staff BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    is_superuser BOOLEAN DEFAULT 0,
    must_change_password BOOLEAN DEFAULT 1,
    password_changed_at TIMESTAMP NULL,
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP NULL,
    locked_until TIMESTAMP NULL,
    email_verified BOOLEAN DEFAULT 0,
    two_factor_enabled BOOLEAN DEFAULT 0,
    two_factor_secret VARCHAR(32),
    phone VARCHAR(20),
    department VARCHAR(100),
    profile_picture TEXT,
    user_timezone VARCHAR(50) DEFAULT 'UTC',
    language VARCHAR(10) DEFAULT 'en',
    last_login TIMESTAMP NULL,
    last_login_ip VARCHAR(45) NULL,
    last_active TIMESTAMP NULL,
    login_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    metadata JSON DEFAULT '{}',
    role_id CHAR(32),
    created_by_id CHAR(32),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_id) REFERENCES system_users(id) ON DELETE SET NULL
);

-- Create the login_attempts table
CREATE TABLE login_attempts (
    id CHAR(32) PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    location_data JSON NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    was_successful BOOLEAN DEFAULT 0,
    failure_reason VARCHAR(200),
    risk_score FLOAT NULL,
    user_id CHAR(32) NULL,
    FOREIGN KEY (user_id) REFERENCES system_users(id) ON DELETE CASCADE
);

-- Create the audit_logs table
CREATE TABLE audit_logs (
    id CHAR(32) PRIMARY KEY,
    action VARCHAR(20) NOT NULL,
    model VARCHAR(100) NOT NULL,
    record_id VARCHAR(100) NULL,
    changes JSON NULL,
    ip_address VARCHAR(45) NULL,
    user_agent TEXT,
    endpoint VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    additional_data JSON NULL,
    status VARCHAR(50) DEFAULT 'success',
    duration FLOAT NULL,
    user_id CHAR(32) NULL,
    FOREIGN KEY (user_id) REFERENCES system_users(id) ON DELETE SET NULL
);

-- Create indexes
CREATE INDEX idx_system_users_email ON system_users(email);
CREATE INDEX idx_system_users_status ON system_users(status);
CREATE INDEX idx_audit_logs_timestamp_action ON audit_logs(timestamp, action);
CREATE INDEX idx_audit_logs_user_timestamp ON audit_logs(user_id, timestamp);
CREATE INDEX idx_login_attempts_timestamp ON login_attempts(timestamp);
CREATE INDEX idx_login_attempts_email ON login_attempts(email);