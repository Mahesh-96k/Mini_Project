
CREATE TABLE IF NOT EXISTS hospitals (
    hospital_id VARCHAR(10) PRIMARY KEY,
    hospital_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL DEFAULT 'Karnataka',
    is_demo BOOLEAN NOT NULL DEFAULT TRUE,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('hospital', 'patient', 'authority')
        NOT NULL,
    hospital_id VARCHAR(10) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_users_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES hospitals(hospital_id)
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    global_pid VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL UNIQUE,
    date_of_birth DATE NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_patients_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS hospital_patient_links (
    link_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    hospital_id VARCHAR(10) NOT NULL,
    hpid VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_patient_hospital
        UNIQUE (patient_id, hospital_id),

    CONSTRAINT fk_hpl_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id),

    CONSTRAINT fk_hpl_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES hospitals(hospital_id)
);

CREATE TABLE IF NOT EXISTS medical_documents (
    document_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    hospital_id VARCHAR(10) NOT NULL,
    report_number VARCHAR(100) NOT NULL,
    document_type VARCHAR(100) NULL,
    report_date DATE NULL,
    stored_file_name VARCHAR(255) NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    uploaded_by BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_hospital_report
        UNIQUE (hospital_id, report_number),

    CONSTRAINT fk_docs_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id),

    CONSTRAINT fk_docs_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES hospitals(hospital_id),

    CONSTRAINT fk_docs_uploader
        FOREIGN KEY (uploaded_by)
        REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    analysis_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT UNSIGNED NOT NULL,
    extracted_data JSON NOT NULL,
    risk_score TINYINT UNSIGNED NOT NULL,
    risk_level ENUM('Low', 'Medium', 'High') NOT NULL,
    review_status VARCHAR(50) NOT NULL,
    findings JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_risk_score
        CHECK (risk_score <= 100),

    CONSTRAINT fk_analysis_document
        FOREIGN KEY (document_id)
        REFERENCES medical_documents(document_id)
);

CREATE TABLE IF NOT EXISTS verification_history (
    verification_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT UNSIGNED NULL,
    requested_by BIGINT UNSIGNED NOT NULL,
    result_status VARCHAR(50) NOT NULL,
    details JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_verification_document
        FOREIGN KEY (document_id)
        REFERENCES medical_documents(document_id),

    CONSTRAINT fk_verification_user
        FOREIGN KEY (requested_by)
        REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS access_requests (
    request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    hospital_id VARCHAR(10) NOT NULL,
    status ENUM(
        'pending',
        'approved',
        'rejected',
        'expired',
        'revoked'
    ) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    decided_at TIMESTAMP NULL,

    CONSTRAINT fk_requests_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id),

    CONSTRAINT fk_requests_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES hospitals(hospital_id)
);

CREATE TABLE IF NOT EXISTS hospital_id_counters (
    hospital_id VARCHAR(10) PRIMARY KEY,
    next_sequence BIGINT UNSIGNED NOT NULL DEFAULT 1,

    CONSTRAINT fk_counter_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES hospitals(hospital_id),

    CONSTRAINT chk_next_sequence
        CHECK (next_sequence >= 1)
);

