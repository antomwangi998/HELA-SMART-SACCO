# database.py - HELA SMART SACCO v3.0
# Thread-safe SQLite database manager with WAL mode and connection pooling

import os
import uuid
import sqlite3
import hashlib
import base64
import threading
import datetime
import json
from typing import Optional, List

from kivy.logger import Logger


class TransactionContext:
    """Context manager for atomic database transactions."""

    def __init__(self, db_manager):
        self.db = db_manager
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = self.db._get_connection()
        self.cursor = self.conn.cursor()
        self.cursor.execute("BEGIN IMMEDIATE")
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


class AdvancedDatabaseManager:
    """Thread-safe SQLite with WAL mode, optional encryption, and connection pooling."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path=None, crypto_manager=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path=None, crypto_manager=None):
        if self._initialized:
            return

        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), 'data', 'hela_sacco_v3.db'
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.crypto = crypto_manager
        self._local = threading.local()
        self._write_lock = threading.Lock()

        # Connection pool
        self._connection_pool = []
        self._pool_lock = threading.Lock()
        self._max_pool_size = 5

        self._init_database()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local or pooled connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            return self._local.conn

        with self._pool_lock:
            if self._connection_pool:
                conn = self._connection_pool.pop()
                self._local.conn = conn
                return conn

        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=memory")
        conn.execute("PRAGMA mmap_size=30000000000")
        conn.row_factory = sqlite3.Row
        self._local.conn = conn
        return conn

    def _return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        with self._pool_lock:
            if len(self._connection_pool) < self._max_pool_size:
                self._connection_pool.append(conn)
            else:
                conn.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a write query with thread safety."""
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

    def execute_many(self, query: str, params_list: List[tuple]):
        """Execute a batch write query with thread safety."""
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as a dict (so .get() works everywhere)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    def fetch_all(self, query: str, params: tuple = ()) -> List[dict]:
        """Fetch all matching rows as dicts (so .get() works everywhere)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

    def transaction(self) -> TransactionContext:
        """Return a context manager for an atomic transaction."""
        return TransactionContext(self)

    def log_change(self, table: str, record_id: str, operation: str,
                   old_data: dict = None, new_data: dict = None,
                   user_id: str = None, device_id: str = None, priority: int = 5):
        """Log a change for offline synchronisation."""
        old_str = json.dumps(old_data) if old_data else None
        new_str = json.dumps(new_data) if new_data else None
        self.execute('''
            INSERT INTO change_log
            (table_name, record_id, operation, old_data, new_data, changed_by, device_id, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (table, record_id, operation, old_str, new_str, user_id, device_id, priority))

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_database(self):
        """Initialise the full database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.executescript('''
            PRAGMA foreign_keys = ON;
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                iterations INTEGER NOT NULL DEFAULT 600000,
                role TEXT NOT NULL,
                full_name TEXT,
                email TEXT,
                email_encrypted TEXT,
                phone TEXT,
                phone_encrypted TEXT,
                id_number TEXT,
                id_number_encrypted TEXT,
                branch_id TEXT,
                department TEXT,
                employee_id TEXT,
                is_active INTEGER DEFAULT 1,
                is_locked INTEGER DEFAULT 0,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                last_login TIMESTAMP,
                last_activity TIMESTAMP,
                password_changed_at TIMESTAMP,
                password_expires_at TIMESTAMP,
                device_binding TEXT,
                two_factor_enabled INTEGER DEFAULT 0,
                two_factor_secret_encrypted TEXT,
                two_factor_backup_codes TEXT,
                biometric_enabled INTEGER DEFAULT 0,
                biometric_template_encrypted BLOB,
                security_questions TEXT,
                login_history TEXT,
                session_token TEXT,
                session_expires TIMESTAMP,
                permissions_override TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'synced',
                metadata TEXT,
                member_id TEXT
            );

            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                location TEXT,
                latitude REAL,
                longitude REAL,
                address TEXT,
                city TEXT,
                county TEXT,
                postal_code TEXT,
                phone TEXT,
                email TEXT,
                manager_id TEXT,
                assistant_manager_id TEXT,
                opening_hours TEXT,
                is_active INTEGER DEFAULT 1,
                is_head_office INTEGER DEFAULT 0,
                parent_branch_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'synced'
            );

            CREATE TABLE IF NOT EXISTS member_groups (
                id TEXT PRIMARY KEY,
                group_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                group_type TEXT DEFAULT 'chama',
                registration_number TEXT,
                registration_date DATE,
                meeting_day TEXT,
                meeting_time TEXT,
                meeting_location TEXT,
                meeting_frequency TEXT DEFAULT 'weekly',
                chairperson_id TEXT,
                treasurer_id TEXT,
                secretary_id TEXT,
                total_members INTEGER DEFAULT 0,
                total_savings REAL DEFAULT 0,
                total_loans_given REAL DEFAULT 0,
                status TEXT DEFAULT 'active',
                rules_text TEXT,
                constitution_file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS group_members (
                id TEXT PRIMARY KEY,
                group_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_date DATE DEFAULT CURRENT_DATE,
                shares_owned INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                left_date DATE,
                left_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (group_id) REFERENCES member_groups(id),
                FOREIGN KEY (member_id) REFERENCES members(id)
            );

            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                member_no TEXT UNIQUE NOT NULL,
                branch_id TEXT,
                group_id TEXT,
                referrer_id TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                other_names TEXT,
                full_name_search TEXT,
                id_number TEXT,
                id_number_encrypted TEXT,
                passport_number TEXT,
                passport_number_encrypted TEXT,
                date_of_birth DATE,
                gender TEXT,
                marital_status TEXT,
                nationality TEXT DEFAULT 'Kenyan',
                phone TEXT,
                phone_encrypted TEXT,
                phone2 TEXT,
                phone2_encrypted TEXT,
                email TEXT,
                email_encrypted TEXT,
                address TEXT,
                address_encrypted TEXT,
                city TEXT,
                county TEXT,
                constituency TEXT,
                ward TEXT,
                postal_code TEXT,
                gps_coordinates TEXT,
                occupation TEXT,
                employer TEXT,
                employer_id TEXT,
                department TEXT,
                job_title TEXT,
                employment_type TEXT,
                employment_start_date DATE,
                monthly_income REAL,
                annual_income REAL,
                other_income_sources TEXT,
                bank_account_number TEXT,
                bank_name TEXT,
                bank_branch TEXT,
                mpesa_number TEXT,
                kyc_status TEXT DEFAULT 'pending',
                kyc_score INTEGER DEFAULT 0,
                kyc_verified_by TEXT,
                kyc_verified_at TIMESTAMP,
                risk_score INTEGER DEFAULT 0,
                risk_category TEXT DEFAULT 'low',
                pep_status INTEGER DEFAULT 0,
                aml_flags TEXT,
                sanctions_check_status TEXT DEFAULT 'clear',
                sanctions_check_date TIMESTAMP,
                credit_bureau_check_status TEXT DEFAULT 'pending',
                credit_bureau_score INTEGER,
                is_active INTEGER DEFAULT 1,
                is_dormant INTEGER DEFAULT 0,
                dormant_since TIMESTAMP,
                dormancy_reason TEXT,
                membership_date DATE DEFAULT CURRENT_DATE,
                membership_fee_paid INTEGER DEFAULT 0,
                membership_fee_amount REAL DEFAULT 0,
                annual_subscription_due DATE,
                next_of_kin_name TEXT,
                next_of_kin_relationship TEXT,
                next_of_kin_phone TEXT,
                next_of_kin_address TEXT,
                profile_photo_path TEXT,
                signature_image_path TEXT,
                id_document_front_path TEXT,
                id_document_back_path TEXT,
                consent_signed INTEGER DEFAULT 0,
                consent_date TIMESTAMP,
                marketing_consent INTEGER DEFAULT 0,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                notes TEXT,
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (group_id) REFERENCES member_groups(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (referrer_id) REFERENCES members(id)
            );

            CREATE TABLE IF NOT EXISTS beneficiaries (
                id TEXT PRIMARY KEY,
                member_id TEXT NOT NULL,
                full_name TEXT NOT NULL,
                relationship TEXT,
                phone TEXT,
                phone_encrypted TEXT,
                email TEXT,
                email_encrypted TEXT,
                id_number TEXT,
                id_number_encrypted TEXT,
                date_of_birth DATE,
                address TEXT,
                percentage INTEGER DEFAULT 100,
                is_primary INTEGER DEFAULT 0,
                is_nominee INTEGER DEFAULT 0,
                is_guardian INTEGER DEFAULT 0,
                guardian_for_member_id TEXT,
                bank_account_number TEXT,
                bank_name TEXT,
                payout_status TEXT DEFAULT 'pending',
                payout_amount REAL,
                payout_date TIMESTAMP,
                documents_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (member_id) REFERENCES members(id)
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                document_name TEXT,
                file_path TEXT,
                file_size INTEGER,
                mime_type TEXT,
                checksum TEXT,
                encryption_key_id TEXT,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expiry_date DATE,
                is_verified INTEGER DEFAULT 0,
                verified_by TEXT,
                verified_at TIMESTAMP,
                verification_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                product_code TEXT UNIQUE NOT NULL,
                product_name TEXT NOT NULL,
                product_type TEXT NOT NULL,
                description TEXT,
                detailed_description TEXT,
                currency TEXT DEFAULT 'KES',
                min_balance_minor INTEGER DEFAULT 0,
                max_balance_minor INTEGER,
                min_opening_balance_minor INTEGER DEFAULT 0,
                interest_rate REAL DEFAULT 0,
                interest_rate_min REAL,
                interest_rate_max REAL,
                interest_calculation_method TEXT DEFAULT 'daily_balance',
                interest_posting_frequency TEXT DEFAULT 'monthly',
                interest_accrual_method TEXT DEFAULT 'simple',
                fees TEXT,
                charges TEXT,
                penalties TEXT,
                withdrawal_restrictions TEXT,
                deposit_restrictions TEXT,
                target_market TEXT,
                eligibility_criteria TEXT,
                required_documents TEXT,
                cooling_off_period_days INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_public INTEGER DEFAULT 1,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'synced'
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                account_no TEXT UNIQUE NOT NULL,
                member_id TEXT NOT NULL,
                branch_id TEXT,
                product_id TEXT,
                account_type TEXT NOT NULL,
                account_subtype TEXT,
                currency TEXT DEFAULT 'KES',
                status TEXT DEFAULT 'active',
                balance_minor INTEGER DEFAULT 0,
                available_balance_minor INTEGER DEFAULT 0,
                blocked_amount_minor INTEGER DEFAULT 0,
                uncleared_funds_minor INTEGER DEFAULT 0,
                overdraft_limit_minor INTEGER DEFAULT 0,
                overdraft_used_minor INTEGER DEFAULT 0,
                interest_rate REAL DEFAULT 0,
                interest_accrued_minor INTEGER DEFAULT 0,
                interest_posted_minor INTEGER DEFAULT 0,
                last_interest_posting_date DATE,
                opening_date DATE DEFAULT CURRENT_DATE,
                closing_date DATE,
                closing_reason TEXT,
                dormant_date DATE,
                last_transaction_date TIMESTAMP,
                last_deposit_date DATE,
                last_withdrawal_date DATE,
                statement_frequency TEXT DEFAULT 'monthly',
                statement_delivery_method TEXT DEFAULT 'email',
                sms_alert_enabled INTEGER DEFAULT 1,
                email_alert_enabled INTEGER DEFAULT 1,
                passbook_issued INTEGER DEFAULT 0,
                passbook_number TEXT,
                cheque_book_enabled INTEGER DEFAULT 0,
                cheque_book_number TEXT,
                atm_card_enabled INTEGER DEFAULT 0,
                atm_card_number TEXT,
                mobile_banking_enabled INTEGER DEFAULT 0,
                internet_banking_enabled INTEGER DEFAULT 0,
                standing_orders_count INTEGER DEFAULT 0,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS account_signatories (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                signatory_type TEXT DEFAULT 'signatory',
                signature_image_path TEXT,
                signature_verified INTEGER DEFAULT 0,
                signing_limit_minor INTEGER,
                is_active INTEGER DEFAULT 1,
                added_date DATE DEFAULT CURRENT_DATE,
                removed_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (member_id) REFERENCES members(id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                transaction_ref TEXT UNIQUE NOT NULL,
                batch_ref TEXT,
                account_id TEXT,
                counterparty_account_id TEXT,
                transaction_type TEXT NOT NULL,
                amount_minor INTEGER NOT NULL,
                currency TEXT DEFAULT 'KES',
                exchange_rate REAL DEFAULT 1.0,
                amount_in_kes_minor INTEGER,
                description TEXT,
                narrative TEXT,
                reference_number TEXT,
                related_transaction_id TEXT,
                loan_id TEXT,
                teller_id TEXT,
                branch_id TEXT,
                device_id TEXT,
                channel TEXT DEFAULT 'branch',
                idempotency_key TEXT,
                gps_coordinates TEXT,
                ip_address TEXT,
                prev_hash TEXT,
                tx_hash TEXT NOT NULL,
                merkle_root TEXT,
                signature TEXT,
                posted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                value_date DATE DEFAULT CURRENT_DATE,
                transaction_date DATE DEFAULT CURRENT_DATE,
                is_reversed INTEGER DEFAULT 0,
                reversed_by TEXT,
                reversal_reason TEXT,
                reversal_date TIMESTAMP,
                reversal_approved_by TEXT,
                is_flagged INTEGER DEFAULT 0,
                flag_reason TEXT,
                is_suspicious INTEGER DEFAULT 0,
                suspicious_reason TEXT,
                aml_review_status TEXT DEFAULT 'clear',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (teller_id) REFERENCES users(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (loan_id) REFERENCES loans(id)
            );

            CREATE TABLE IF NOT EXISTS transaction_tags (
                id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                category TEXT,
                confidence_score REAL,
                tagged_by TEXT,
                tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            );

            CREATE TABLE IF NOT EXISTS standing_orders (
                id TEXT PRIMARY KEY,
                order_name TEXT,
                from_account_id TEXT NOT NULL,
                to_account_id TEXT,
                to_external_account TEXT,
                beneficiary_name TEXT,
                amount_minor INTEGER NOT NULL,
                currency TEXT DEFAULT 'KES',
                frequency TEXT NOT NULL,
                start_date DATE,
                end_date DATE,
                next_execution_date DATE,
                last_execution_date DATE,
                execution_count INTEGER DEFAULT 0,
                max_executions INTEGER,
                status TEXT DEFAULT 'active',
                failure_count INTEGER DEFAULT 0,
                last_failure_reason TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (from_account_id) REFERENCES accounts(id),
                FOREIGN KEY (to_account_id) REFERENCES accounts(id)
            );

            CREATE TABLE IF NOT EXISTS loans (
                id TEXT PRIMARY KEY,
                loan_no TEXT UNIQUE NOT NULL,
                member_id TEXT NOT NULL,
                group_id TEXT,
                product_id TEXT,
                branch_id TEXT,
                loan_purpose TEXT,
                purpose_category TEXT,
                principal_amount_minor INTEGER NOT NULL,
                approved_amount_minor INTEGER,
                disbursed_amount_minor INTEGER,
                interest_rate REAL NOT NULL,
                interest_method TEXT DEFAULT 'flat',
                interest_amount_minor INTEGER DEFAULT 0,
                term_months INTEGER NOT NULL,
                grace_period_days INTEGER DEFAULT 0,
                application_date DATE DEFAULT CURRENT_DATE,
                appraisal_date TIMESTAMP,
                appraisal_score INTEGER,
                appraisal_notes TEXT,
                appraised_by TEXT,
                committee_date TIMESTAMP,
                committee_decision TEXT,
                committee_notes TEXT,
                committee_members TEXT,
                approved_date TIMESTAMP,
                approved_by TEXT,
                approval_conditions TEXT,
                disbursement_date DATE,
                disbursed_by TEXT,
                first_payment_date DATE,
                maturity_date DATE,
                status TEXT DEFAULT 'pending',
                sub_status TEXT,
                outstanding_principal_minor INTEGER DEFAULT 0,
                outstanding_interest_minor INTEGER DEFAULT 0,
                outstanding_penalties_minor INTEGER DEFAULT 0,
                outstanding_fees_minor INTEGER DEFAULT 0,
                total_repaid_minor INTEGER DEFAULT 0,
                next_payment_date DATE,
                next_payment_amount_minor INTEGER,
                days_in_arrears INTEGER DEFAULT 0,
                par_status TEXT DEFAULT 'current',
                provision_percentage REAL DEFAULT 0,
                provision_amount_minor INTEGER DEFAULT 0,
                is_rescheduled INTEGER DEFAULT 0,
                rescheduled_from_loan_id TEXT,
                reschedule_count INTEGER DEFAULT 0,
                is_restructured INTEGER DEFAULT 0,
                restructure_date TIMESTAMP,
                restructure_reason TEXT,
                moratorium_months INTEGER DEFAULT 0,
                collateral_value_minor INTEGER DEFAULT 0,
                guarantors_count INTEGER DEFAULT 0,
                credit_score_at_application INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (group_id) REFERENCES member_groups(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (approved_by) REFERENCES users(id),
                FOREIGN KEY (disbursed_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS loan_schedule (
                id TEXT PRIMARY KEY,
                loan_id TEXT NOT NULL,
                installment_no INTEGER NOT NULL,
                due_date DATE NOT NULL,
                principal_amount_minor INTEGER NOT NULL,
                interest_amount_minor INTEGER NOT NULL,
                fee_amount_minor INTEGER DEFAULT 0,
                total_amount_minor INTEGER NOT NULL,
                paid_amount_minor INTEGER DEFAULT 0,
                paid_date DATE,
                payment_ref TEXT,
                status TEXT DEFAULT 'pending',
                days_overdue INTEGER DEFAULT 0,
                penalty_accrued_minor INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (loan_id) REFERENCES loans(id)
            );

            CREATE TABLE IF NOT EXISTS guarantors (
                id TEXT PRIMARY KEY,
                loan_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                guarantee_amount_minor INTEGER NOT NULL,
                guarantee_type TEXT DEFAULT 'secured',
                is_active INTEGER DEFAULT 1,
                released_date DATE,
                released_by TEXT,
                release_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (loan_id) REFERENCES loans(id),
                FOREIGN KEY (member_id) REFERENCES members(id)
            );

            CREATE TABLE IF NOT EXISTS collateral (
                id TEXT PRIMARY KEY,
                loan_id TEXT,
                member_id TEXT,
                collateral_type TEXT NOT NULL,
                description TEXT,
                registration_number TEXT,
                serial_number TEXT,
                make_model TEXT,
                year_of_manufacture INTEGER,
                condition TEXT,
                location TEXT,
                ownership_type TEXT,
                owner_name TEXT,
                owner_id_number TEXT,
                estimated_value_minor INTEGER,
                forced_sale_value_minor INTEGER,
                valuation_date DATE,
                valuer_name TEXT,
                valuer_license_number TEXT,
                insurance_required INTEGER DEFAULT 0,
                insurance_company TEXT,
                insurance_policy_no TEXT,
                insurance_coverage_minor INTEGER,
                insurance_expiry DATE,
                insurance_premium_minor INTEGER,
                document_path TEXT,
                photos_paths TEXT,
                release_date DATE,
                release_reason TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS charges (
                id TEXT PRIMARY KEY,
                charge_code TEXT UNIQUE NOT NULL,
                charge_name TEXT NOT NULL,
                charge_type TEXT NOT NULL,
                description TEXT,
                amount_minor INTEGER,
                percentage REAL,
                minimum_amount_minor INTEGER,
                maximum_amount_minor INTEGER,
                applicable_products TEXT,
                applicable_transaction_types TEXT,
                is_mandatory INTEGER DEFAULT 1,
                is_taxable INTEGER DEFAULT 0,
                tax_rate REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                effective_from DATE,
                effective_to DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'synced'
            );

            CREATE TABLE IF NOT EXISTS charge_applications (
                id TEXT PRIMARY KEY,
                charge_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                amount_minor INTEGER NOT NULL,
                tax_amount_minor INTEGER DEFAULT 0,
                total_amount_minor INTEGER NOT NULL,
                waived_amount_minor INTEGER DEFAULT 0,
                waived_by TEXT,
                waiver_reason TEXT,
                waiver_approved_by TEXT,
                applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (charge_id) REFERENCES charges(id)
            );

            CREATE TABLE IF NOT EXISTS teller_cashbook (
                id TEXT PRIMARY KEY,
                teller_id TEXT NOT NULL,
                branch_id TEXT,
                date DATE DEFAULT CURRENT_DATE,
                currency TEXT DEFAULT 'KES',
                opening_balance_minor INTEGER DEFAULT 0,
                closing_balance_minor INTEGER,
                cash_received_minor INTEGER DEFAULT 0,
                cash_paid_minor INTEGER DEFAULT 0,
                cheques_received_minor INTEGER DEFAULT 0,
                cheques_paid_minor INTEGER DEFAULT 0,
                transfers_in_minor INTEGER DEFAULT 0,
                transfers_out_minor INTEGER DEFAULT 0,
                expected_balance_minor INTEGER,
                actual_balance_minor INTEGER,
                discrepancy_minor INTEGER DEFAULT 0,
                discrepancy_reason TEXT,
                is_balanced INTEGER DEFAULT 0,
                is_closed INTEGER DEFAULT 0,
                opened_at TIMESTAMP,
                closed_at TIMESTAMP,
                closed_by TEXT,
                supervisor_approved INTEGER DEFAULT 0,
                supervisor_id TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (teller_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS teller_transactions (
                id TEXT PRIMARY KEY,
                cashbook_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount_minor INTEGER NOT NULL,
                reference_no TEXT,
                related_transaction_id TEXT,
                customer_name TEXT,
                customer_id TEXT,
                notes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cashbook_id) REFERENCES teller_cashbook(id)
            );

            CREATE TABLE IF NOT EXISTS vault_movements (
                id TEXT PRIMARY KEY,
                branch_id TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                currency TEXT DEFAULT 'KES',
                amount_minor INTEGER NOT NULL,
                denomination_breakdown TEXT,
                from_teller_id TEXT,
                to_teller_id TEXT,
                from_vault INTEGER DEFAULT 0,
                to_vault INTEGER DEFAULT 0,
                reference_no TEXT,
                notes TEXT,
                recorded_by TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_by TEXT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );

            CREATE TABLE IF NOT EXISTS payroll_uploads (
                id TEXT PRIMARY KEY,
                employer_id TEXT,
                employer_name TEXT,
                upload_period TEXT,
                upload_date DATE DEFAULT CURRENT_DATE,
                file_name TEXT,
                file_path TEXT,
                file_hash TEXT,
                total_records INTEGER,
                total_amount_minor INTEGER,
                processed_records INTEGER DEFAULT 0,
                failed_records INTEGER DEFAULT 0,
                duplicate_records INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                processed_by TEXT,
                processed_at TIMESTAMP,
                error_log TEXT,
                uploaded_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS payroll_items (
                id TEXT PRIMARY KEY,
                upload_id TEXT NOT NULL,
                member_id TEXT,
                payroll_number TEXT,
                id_number TEXT,
                full_name TEXT,
                amount_minor INTEGER NOT NULL,
                deduction_type TEXT DEFAULT 'savings',
                reference_number TEXT,
                status TEXT DEFAULT 'pending',
                failure_reason TEXT,
                processed_at TIMESTAMP,
                transaction_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (upload_id) REFERENCES payroll_uploads(id),
                FOREIGN KEY (member_id) REFERENCES members(id)
            );

            CREATE TABLE IF NOT EXISTS distributions (
                id TEXT PRIMARY KEY,
                distribution_type TEXT NOT NULL,
                financial_year TEXT,
                period_start DATE,
                period_end DATE,
                total_amount_minor INTEGER NOT NULL,
                total_members INTEGER,
                distribution_date DATE,
                rate_percent REAL,
                withholding_tax_rate REAL DEFAULT 0,
                total_tax_minor INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                prepared_by TEXT,
                prepared_at TIMESTAMP,
                approved_by TEXT,
                approved_at TIMESTAMP,
                posted_by TEXT,
                posted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS distribution_items (
                id TEXT PRIMARY KEY,
                distribution_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                account_id TEXT,
                shares_held INTEGER,
                amount_per_share REAL,
                gross_amount_minor INTEGER NOT NULL,
                tax_amount_minor INTEGER DEFAULT 0,
                net_amount_minor INTEGER NOT NULL,
                is_paid INTEGER DEFAULT 0,
                paid_at TIMESTAMP,
                payment_method TEXT,
                payment_reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (distribution_id) REFERENCES distributions(id),
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount_minor INTEGER,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                current_level INTEGER DEFAULT 1,
                max_levels INTEGER DEFAULT 1,
                approved_by TEXT,
                approved_at TIMESTAMP,
                rejection_reason TEXT,
                notes TEXT,
                escalation_history TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (requested_by) REFERENCES users(id),
                FOREIGN KEY (approved_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                member_id TEXT,
                notification_type TEXT NOT NULL,
                category TEXT,
                priority TEXT DEFAULT 'normal',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                detailed_message TEXT,
                action_required INTEGER DEFAULT 0,
                action_type TEXT,
                action_screen TEXT,
                action_params TEXT,
                is_read INTEGER DEFAULT 0,
                read_at TIMESTAMP,
                expires_at TIMESTAMP,
                sent_via TEXT DEFAULT 'in_app',
                external_message_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notification_templates (
                id TEXT PRIMARY KEY,
                template_code TEXT UNIQUE NOT NULL,
                template_name TEXT NOT NULL,
                description TEXT,
                notification_type TEXT DEFAULT 'sms',
                subject_template TEXT,
                message_template TEXT NOT NULL,
                html_template TEXT,
                variables TEXT,
                required_variables TEXT,
                default_variables TEXT,
                is_active INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                session_id TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                operation TEXT,
                old_values TEXT,
                new_values TEXT,
                changes_summary TEXT,
                ip_address TEXT,
                device_id TEXT,
                user_agent TEXT,
                geolocation TEXT,
                risk_score INTEGER DEFAULT 0,
                hash TEXT NOT NULL,
                prev_hash TEXT,
                signature TEXT,
                blockchain_index INTEGER,
                merkle_root TEXT
            );

            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                record_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                old_data TEXT,
                new_data TEXT,
                changed_by TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                sync_attempts INTEGER DEFAULT 0,
                last_sync_attempt TIMESTAMP,
                sync_error TEXT,
                priority INTEGER DEFAULT 5
            );


            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                encrypted_value TEXT,
                is_encrypted INTEGER DEFAULT 0,
                data_type TEXT DEFAULT 'string',
                category TEXT DEFAULT 'general',
                description TEXT,
                is_editable INTEGER DEFAULT 1,
                requires_restart INTEGER DEFAULT 0,
                allowed_values TEXT,
                updated_by TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mobile_money_transactions (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                phone TEXT NOT NULL,
                amount_ksh REAL NOT NULL,
                charge_ksh REAL DEFAULT 0,
                reference TEXT UNIQUE,
                conversation_id TEXT,
                mpesa_transaction_id TEXT,
                status TEXT DEFAULT 'pending',
                raw_response TEXT,
                account_id TEXT,
                member_id TEXT,
                processed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS currencies (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                symbol TEXT,
                minor_unit INTEGER DEFAULT 2,
                country_code TEXT,
                is_active INTEGER DEFAULT 1,
                is_default INTEGER DEFAULT 0,
                exchange_rate REAL DEFAULT 1.0,
                exchange_rate_updated_at TIMESTAMP,
                exchange_rate_source TEXT,
                rounding_method TEXT DEFAULT 'standard'
            );

            CREATE TABLE IF NOT EXISTS chart_of_accounts (
                id TEXT PRIMARY KEY,
                account_code TEXT UNIQUE NOT NULL,
                account_name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                account_subtype TEXT,
                parent_id TEXT,
                level INTEGER DEFAULT 1,
                is_bank_account INTEGER DEFAULT 0,
                is_cash_account INTEGER DEFAULT 0,
                is_control_account INTEGER DEFAULT 0,
                control_account_for TEXT,
                opening_balance_minor INTEGER DEFAULT 0,
                current_balance_minor INTEGER DEFAULT 0,
                budget_amount_minor INTEGER,
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                FOREIGN KEY (parent_id) REFERENCES chart_of_accounts(id)
            );

            CREATE TABLE IF NOT EXISTS gl_entries (
                id TEXT PRIMARY KEY,
                entry_date DATE NOT NULL,
                period TEXT NOT NULL,
                account_id TEXT NOT NULL,
                transaction_id TEXT,
                debit_minor INTEGER DEFAULT 0,
                credit_minor INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'KES',
                exchange_rate REAL DEFAULT 1.0,
                narration TEXT,
                reference_no TEXT,
                is_reversing_entry INTEGER DEFAULT 0,
                reversed_entry_id TEXT,
                is_closing_entry INTEGER DEFAULT 0,
                is_adjustment INTEGER DEFAULT 0,
                approved_by TEXT,
                approved_at TIMESTAMP,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                device_id TEXT,
                sync_status TEXT DEFAULT 'pending',
                FOREIGN KEY (account_id) REFERENCES chart_of_accounts(id)
            );

            CREATE TABLE IF NOT EXISTS accounting_periods (
                id TEXT PRIMARY KEY,
                period_name TEXT NOT NULL,
                fiscal_year TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                is_current INTEGER DEFAULT 0,
                is_closed INTEGER DEFAULT 0,
                closed_by TEXT,
                closed_at TIMESTAMP,
                closing_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id TEXT PRIMARY KEY,
                budget_name TEXT NOT NULL,
                fiscal_year TEXT NOT NULL,
                department TEXT,
                total_budget_minor INTEGER NOT NULL,
                spent_minor INTEGER DEFAULT 0,
                remaining_minor INTEGER,
                status TEXT DEFAULT 'draft',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS qr_tokens (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                token_data TEXT NOT NULL,
                encrypted_payload TEXT,
                signature TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                used_at TIMESTAMP,
                used_by TEXT,
                is_revoked INTEGER DEFAULT 0,
                revoked_at TIMESTAMP,
                revoke_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS anomaly_flags (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                description TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detected_by TEXT,
                rule_id TEXT,
                confidence_score REAL,
                is_false_positive INTEGER DEFAULT 0,
                is_resolved INTEGER DEFAULT 0,
                resolved_by TEXT,
                resolved_at TIMESTAMP,
                resolution_notes TEXT,
                escalated_to TEXT,
                escalated_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ml_predictions (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                model_version TEXT,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                prediction_value REAL,
                confidence_score REAL,
                feature_importance TEXT,
                input_features TEXT,
                prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                actual_outcome TEXT,
                actual_outcome_date TIMESTAMP,
                model_accuracy REAL
            );

            CREATE TABLE IF NOT EXISTS chatbot_conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                member_id TEXT,
                session_id TEXT,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                intent_detected TEXT,
                entities_extracted TEXT,
                confidence_score REAL,
                context TEXT,
                follow_up_required INTEGER DEFAULT 0,
                human_handoff_required INTEGER DEFAULT 0,
                handed_off_to TEXT,
                satisfaction_rating INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                schedule TEXT NOT NULL,
                next_run_at TIMESTAMP,
                last_run_at TIMESTAMP,
                last_run_status TEXT,
                last_run_output TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_logs (
                id TEXT PRIMARY KEY,
                integration_name TEXT NOT NULL,
                endpoint TEXT,
                request_method TEXT,
                request_headers TEXT,
                request_body TEXT,
                response_status INTEGER,
                response_body TEXT,
                response_time_ms INTEGER,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Performance indexes
            CREATE INDEX IF NOT EXISTS idx_members_member_no ON members(member_no);
            CREATE INDEX IF NOT EXISTS idx_members_id_number ON members(id_number);
            CREATE INDEX IF NOT EXISTS idx_members_phone ON members(phone);
            CREATE INDEX IF NOT EXISTS idx_members_names ON members(full_name_search);
            CREATE INDEX IF NOT EXISTS idx_members_active ON members(is_active, is_dormant);
            CREATE INDEX IF NOT EXISTS idx_accounts_member ON accounts(member_id, status);
            CREATE INDEX IF NOT EXISTS idx_accounts_number ON accounts(account_no);
            CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id, posted_date);
            CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
            CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
            CREATE INDEX IF NOT EXISTS idx_loans_member ON loans(member_id, status);
            CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status, par_status);
            CREATE INDEX IF NOT EXISTS idx_loans_dates ON loans(application_date, disbursement_date);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_change_log_sync ON change_log(sync_status, priority);
            CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status, priority, requested_at);
            CREATE INDEX IF NOT EXISTS idx_teller_cashbook ON teller_cashbook(teller_id, date);
            CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, priority);
            CREATE INDEX IF NOT EXISTS idx_gl_entries ON gl_entries(account_id, period, entry_date);

            CREATE TABLE IF NOT EXISTS investments (
                id TEXT PRIMARY KEY,
                member_id TEXT NOT NULL REFERENCES members(id),
                account_id TEXT REFERENCES accounts(id),
                investment_type TEXT NOT NULL DEFAULT 'fixed_deposit',
                name TEXT,
                principal_minor INTEGER NOT NULL DEFAULT 0,
                interest_rate REAL NOT NULL DEFAULT 0,
                term_months INTEGER NOT NULL DEFAULT 12,
                start_date TEXT NOT NULL,
                maturity_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                interest_earned_minor INTEGER DEFAULT 0,
                payout_at_maturity INTEGER DEFAULT 1,
                auto_rollover INTEGER DEFAULT 0,
                notes TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_investments_member ON investments(member_id, status);
        ''')

        conn.commit()
        self._run_migrations(cursor, conn)
        self._seed_defaults(cursor)
        conn.commit()

    def _run_migrations(self, cursor, conn):
        """
        Apply schema migrations for existing databases.
        Uses ALTER TABLE ADD COLUMN which is safe to run repeatedly
        — SQLite ignores columns that already exist when wrapped in try/except.
        """
        migrations = [
            # users table additions
            ("ALTER TABLE users ADD COLUMN member_id TEXT", None),
            ("ALTER TABLE users ADD COLUMN full_name TEXT", None),
            ("ALTER TABLE users ADD COLUMN metadata TEXT", None),
            # members additions
            ("ALTER TABLE members ADD COLUMN is_active INTEGER DEFAULT 1", None),
            # accounts additions
            # accounts table — add columns that older installs may be missing
            ("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'active'", None),
            ("ALTER TABLE accounts ADD COLUMN account_type TEXT", None),
            ("ALTER TABLE accounts ADD COLUMN account_no TEXT", None),
            ("ALTER TABLE accounts ADD COLUMN available_balance_minor INTEGER DEFAULT 0", None),
            ("ALTER TABLE accounts ADD COLUMN balance_minor INTEGER DEFAULT 0", None),
            # loan_schedule table: ensure it exists (for fresh installs missing it)
            ("""CREATE TABLE IF NOT EXISTS loan_schedule (
                id TEXT PRIMARY KEY,
                loan_id TEXT NOT NULL,
                installment_no INTEGER NOT NULL DEFAULT 0,
                due_date DATE NOT NULL,
                principal_amount_minor INTEGER NOT NULL DEFAULT 0,
                interest_amount_minor INTEGER NOT NULL DEFAULT 0,
                fee_amount_minor INTEGER DEFAULT 0,
                total_amount_minor INTEGER NOT NULL DEFAULT 0,
                paid_amount_minor INTEGER DEFAULT 0,
                paid_date DATE,
                payment_ref TEXT,
                status TEXT DEFAULT 'pending',
                days_overdue INTEGER DEFAULT 0,
                penalty_accrued_minor INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (loan_id) REFERENCES loans(id)
            )""", None),
            # investments table (safe — CREATE TABLE IF NOT EXISTS)
            ("""CREATE TABLE IF NOT EXISTS investments (
                id TEXT PRIMARY KEY,
                member_id TEXT NOT NULL,
                account_id TEXT,
                investment_type TEXT NOT NULL DEFAULT 'fixed_deposit',
                name TEXT,
                principal_minor INTEGER NOT NULL DEFAULT 0,
                interest_rate REAL NOT NULL DEFAULT 0,
                term_months INTEGER NOT NULL DEFAULT 12,
                start_date TEXT NOT NULL,
                maturity_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                interest_earned_minor INTEGER DEFAULT 0,
                payout_at_maturity INTEGER DEFAULT 1,
                auto_rollover INTEGER DEFAULT 0,
                notes TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )""", None),
            # ── mobile_money_transactions: ensure table + all needed columns ──
            # The table may have been created with an old schema — add missing
            # columns safely (SQLite raises OperationalError if col exists,
            # which we catch and ignore).
            ("""CREATE TABLE IF NOT EXISTS mobile_money_transactions (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                phone TEXT NOT NULL,
                amount_ksh REAL NOT NULL,
                charge_ksh REAL DEFAULT 0,
                reference TEXT UNIQUE,
                conversation_id TEXT,
                mpesa_transaction_id TEXT,
                status TEXT DEFAULT 'pending',
                raw_response TEXT,
                account_id TEXT,
                member_id TEXT,
                processed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""", None),
            # Patch old schemas that may be missing columns
            ("ALTER TABLE mobile_money_transactions ADD COLUMN status TEXT DEFAULT 'pending'", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN charge_ksh REAL DEFAULT 0", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN conversation_id TEXT", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN mpesa_transaction_id TEXT", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN raw_response TEXT", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN account_id TEXT", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN member_id TEXT", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN processed_by TEXT", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", None),
            ("ALTER TABLE mobile_money_transactions ADD COLUMN reference TEXT", None),
            # Beneficiaries (saved phone numbers) — created here so it exists even if
            # the user hasn't done a transfer yet
            ("""CREATE TABLE IF NOT EXISTS beneficiaries (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                phone TEXT NOT NULL,
                name TEXT,
                use_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, phone)
            )""", None),
        ]
        for sql, params in migrations:
            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
            except Exception:
                pass  # Column already exists — safe to ignore
        conn.commit()

    def _seed_defaults(self, cursor):
        """Seed default data on first run."""

        # Currencies
        cursor.execute("SELECT COUNT(*) FROM currencies")
        if cursor.fetchone()[0] == 0:
            cursor.executemany('''
                INSERT OR IGNORE INTO currencies
                (code, name, symbol, minor_unit, is_default, country_code)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [
                ('KES', 'Kenyan Shilling', 'KSh', 2, 1, 'KE'),
                ('USD', 'US Dollar', '$', 2, 0, 'US'),
                ('EUR', 'Euro', '€', 2, 0, 'EU'),
                ('GBP', 'British Pound', '£', 2, 0, 'GB'),
                ('TZS', 'Tanzanian Shilling', 'TSh', 2, 0, 'TZ'),
                ('UGX', 'Ugandan Shilling', 'USh', 0, 0, 'UG'),
                ('RWF', 'Rwandan Franc', 'RF', 0, 0, 'RW'),
            ])

        # Default super admin
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'super_admin'")
        if cursor.fetchone()[0] == 0:
            admin_id = str(uuid.uuid4())
            salt = base64.b64encode(os.urandom(32)).decode()
            password_hash = base64.b64encode(hashlib.pbkdf2_hmac(
                'sha256', b'SuperAdmin@2024!', base64.b64decode(salt), 600000, 32
            )).decode()
            cursor.execute('''
                INSERT INTO users
                (id, username, password_hash, salt, iterations, role,
                 full_name, is_active, email, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                admin_id, 'superadmin', password_hash, salt, 600000,
                'super_admin', 'System Super Administrator', 1,
                'admin@helasmart.co.ke', '+254700000000',
                datetime.datetime.now().isoformat()
            ))

        # Default branch
        cursor.execute("SELECT COUNT(*) FROM branches")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO branches (id, code, name, is_active, is_head_office, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), 'HQ001', 'Head Office - Nairobi', 1, 1,
                datetime.datetime.now().isoformat()
            ))

        # Default products
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            products = [
                (str(uuid.uuid4()), 'SAV001', 'Hekima Savings', 'savings',
                 'Standard savings account with competitive interest', 0, 8.0, 10000),
                (str(uuid.uuid4()), 'SAV002', 'Elimu Education Savings', 'savings',
                 'Education savings with bonus interest', 0, 10.0, 5000),
                (str(uuid.uuid4()), 'SAV003', 'Biashara Business Savings', 'savings',
                 'For business owners and entrepreneurs', 50000, 7.5, 100000),
                (str(uuid.uuid4()), 'SAV004', 'Future Stars Junior', 'children_savings',
                 'Savings account for children under 18', 0, 9.0, 1000),
                (str(uuid.uuid4()), 'SAV005', 'Golden Years Retirement', 'retirement',
                 'Retirement savings with tax benefits', 0, 11.0, 50000),
                (str(uuid.uuid4()), 'LOA001', 'Biashara Loan', 'loan',
                 'Business development loan', 0, 14.0, 5000000),
                (str(uuid.uuid4()), 'LOA002', 'Elimu Education Loan', 'loan',
                 'School fees and education expenses', 0, 12.0, 2000000),
                (str(uuid.uuid4()), 'LOA003', 'Dharura Emergency Loan', 'loan',
                 'Quick emergency loan within 24 hours', 0, 15.0, 500000),
                (str(uuid.uuid4()), 'LOA004', 'Nyumba Housing Loan', 'loan',
                 'Home construction and improvement', 0, 13.0, 10000000),
                (str(uuid.uuid4()), 'LOA005', 'Kilimo Agricultural Loan', 'loan',
                 'For farmers and agricultural enterprises', 0, 12.5, 3000000),
                (str(uuid.uuid4()), 'LOA006', 'Asset Acquisition Loan', 'loan',
                 'Vehicle and equipment financing', 0, 14.5, 8000000),
                (str(uuid.uuid4()), 'SHA001', 'Share Capital', 'share_capital',
                 'Member share capital investment', 100000, 0.0, 100000),
                (str(uuid.uuid4()), 'FD001', 'Fixed Deposit 3M', 'fixed_deposit',
                 '3 months fixed deposit', 50000, 10.0, 10000000),
                (str(uuid.uuid4()), 'FD002', 'Fixed Deposit 6M', 'fixed_deposit',
                 '6 months fixed deposit', 50000, 12.0, 10000000),
                (str(uuid.uuid4()), 'FD003', 'Fixed Deposit 12M', 'fixed_deposit',
                 '12 months fixed deposit', 50000, 14.0, 10000000),
            ]
            for p in products:
                cursor.execute('''
                    INSERT INTO products
                    (id, product_code, product_name, product_type,
                     description, min_balance_minor, interest_rate, max_balance_minor)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', p)

        # Chart of accounts
        # parent_id is a FK to id (UUID), so we pre-build a code→UUID map
        cursor.execute("SELECT COUNT(*) FROM chart_of_accounts")
        if cursor.fetchone()[0] == 0:
            # (account_code, account_name, account_type, parent_code, level, is_bank, is_cash)
            coa_def = [
                ('1000', 'ASSETS',               'asset',     None,   1, 0, 0),
                ('1100', 'Current Assets',        'asset',     '1000', 2, 0, 0),
                ('1110', 'Cash and Bank',         'asset',     '1100', 3, 0, 0),
                ('1111', 'Cash on Hand',          'asset',     '1110', 4, 0, 1),
                ('1112', 'Bank Accounts',         'asset',     '1110', 4, 1, 0),
                ('1120', 'Member Loans',          'asset',     '1100', 3, 0, 0),
                ('1121', 'Performing Loans',      'asset',     '1120', 4, 0, 0),
                ('1122', 'Non-Performing Loans',  'asset',     '1120', 4, 0, 0),
                ('1130', 'Accounts Receivable',   'asset',     '1100', 3, 0, 0),
                ('2000', 'LIABILITIES',           'liability', None,   1, 0, 0),
                ('2100', 'Member Deposits',       'liability', '2000', 2, 0, 0),
                ('2101', 'Savings Deposits',      'liability', '2100', 3, 0, 0),
                ('2102', 'Fixed Deposits',        'liability', '2100', 3, 0, 0),
                ('2200', 'Interest Payable',      'liability', '2000', 2, 0, 0),
                ('2300', 'Accounts Payable',      'liability', '2000', 2, 0, 0),
                ('3000', 'EQUITY',                'equity',    None,   1, 0, 0),
                ('3100', 'Share Capital',         'equity',    '3000', 2, 0, 0),
                ('3200', 'Retained Earnings',     'equity',    '3000', 2, 0, 0),
                ('3300', 'General Reserves',      'equity',    '3000', 2, 0, 0),
                ('4000', 'INCOME',                'income',    None,   1, 0, 0),
                ('4100', 'Interest Income',       'income',    '4000', 2, 0, 0),
                ('4101', 'Loan Interest',         'income',    '4100', 3, 0, 0),
                ('4102', 'Investment Income',     'income',    '4100', 3, 0, 0),
                ('4200', 'Fee Income',            'income',    '4000', 2, 0, 0),
                ('4201', 'Account Fees',          'income',    '4200', 3, 0, 0),
                ('4202', 'Transaction Fees',      'income',    '4200', 3, 0, 0),
                ('5000', 'EXPENSES',              'expense',   None,   1, 0, 0),
                ('5100', 'Operating Expenses',    'expense',   '5000', 2, 0, 0),
                ('5101', 'Staff Costs',           'expense',   '5100', 3, 0, 0),
                ('5102', 'Rent and Utilities',    'expense',   '5100', 3, 0, 0),
                ('5103', 'Marketing',             'expense',   '5100', 3, 0, 0),
                ('5200', 'Financial Costs',       'expense',   '5000', 2, 0, 0),
                ('5201', 'Interest Expense',      'expense',   '5200', 3, 0, 0),
                ('5300', 'Loan Loss Provisions',  'expense',   '5000', 2, 0, 0),
            ]
            # Pre-generate UUIDs so parent_id references are correct
            code_to_uuid = {row[0]: str(uuid.uuid4()) for row in coa_def}
            for code, name, atype, parent_code, level, is_bank, is_cash in coa_def:
                parent_uuid = code_to_uuid.get(parent_code) if parent_code else None
                cursor.execute('''
                    INSERT INTO chart_of_accounts
                    (id, account_code, account_name, account_type,
                     parent_id, level, is_bank_account, is_cash_account)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (code_to_uuid[code], code, name, atype,
                        parent_uuid, level, is_bank, is_cash))

        # Notification templates
        cursor.execute("SELECT COUNT(*) FROM notification_templates")
        if cursor.fetchone()[0] == 0:
            templates = [
                ('WELCOME_SMS', 'Welcome SMS', 'sms',
                 'Welcome {{name}} to HELA SMART SACCO! Your member number is {{member_no}}. Dial *384# for services.'),
                ('DEPOSIT_CONFIRM', 'Deposit Confirmation', 'sms',
                 'Dear {{name}}, your deposit of KSh {{amount}} to account {{account_no}} has been received. New balance: KSh {{balance}}'),
                ('WITHDRAWAL_CONFIRM', 'Withdrawal Confirmation', 'sms',
                 'Dear {{name}}, KSh {{amount}} has been withdrawn from your account {{account_no}}. New balance: KSh {{balance}}'),
                ('LOAN_APPROVED', 'Loan Approval', 'sms',
                 'Congratulations {{name}}! Your loan {{loan_no}} of KSh {{amount}} has been approved.'),
                ('LOAN_DUE', 'Loan Payment Due', 'sms',
                 'Dear {{name}}, your loan installment of KSh {{amount}} is due on {{due_date}}.'),
                ('STATEMENT_READY', 'Statement Ready', 'email',
                 'Your {{period}} account statement is now available.'),
            ]
            for t in templates:
                cursor.execute('''
                    INSERT INTO notification_templates
                    (id, template_code, template_name, notification_type, message_template)
                    VALUES (?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), *t))

        # System settings
        settings = [
            ('system_name', 'HELA SMART SACCO', 'string', 'general', 'System Name'),
            ('system_version', '3.0.0', 'string', 'general', 'System Version'),
            ('currency_default', 'KES', 'string', 'financial', 'Default Currency'),
            ('currency_symbol', 'KSh', 'string', 'financial', 'Currency Symbol'),
            ('min_deposit_amount', '100', 'integer', 'financial', 'Minimum Deposit'),
            ('max_deposit_amount', '10000000', 'integer', 'financial', 'Maximum Deposit'),
            ('min_withdrawal_amount', '100', 'integer', 'financial', 'Minimum Withdrawal'),
            ('max_withdrawal_amount', '5000000', 'integer', 'financial', 'Maximum Withdrawal'),
            ('daily_withdrawal_limit', '1000000', 'integer', 'financial', 'Daily Withdrawal Limit'),
            ('teller_max_cash', '1000000', 'integer', 'financial', 'Maximum Teller Cash'),
            ('loan_max_amount', '10000000', 'integer', 'financial', 'Maximum Loan Amount'),
            ('loan_min_amount', '10000', 'integer', 'financial', 'Minimum Loan Amount'),
            ('interest_calculation_method', 'daily_balance', 'string', 'financial', 'Interest Calculation'),
            ('password_expiry_days', '90', 'integer', 'security', 'Password Expiry Days'),
            ('session_timeout_minutes', '30', 'integer', 'security', 'Session Timeout'),
            ('max_login_attempts', '5', 'integer', 'security', 'Max Login Attempts'),
            ('lockout_duration_minutes', '30', 'integer', 'security', 'Lockout Duration'),
            ('require_2fa_for_admin', '1', 'boolean', 'security', 'Require 2FA for Admin'),
            ('backup_encryption_enabled', '1', 'boolean', 'security', 'Encrypt Backups'),
            ('audit_retention_days', '2555', 'integer', 'security', 'Audit Log Retention'),
            ('theme_primary', 'forest', 'string', 'ui', 'Primary Theme'),
            ('theme_mode', 'light', 'string', 'ui', 'Theme Mode'),
            ('language_default', 'en', 'string', 'ui', 'Default Language'),
            ('date_format', 'DD/MM/YYYY', 'string', 'ui', 'Date Format'),
            ('time_format', '24h', 'string', 'ui', 'Time Format'),
            ('sms_enabled', '1', 'boolean', 'integration', 'SMS Enabled'),
            ('email_enabled', '1', 'boolean', 'integration', 'Email Enabled'),
            ('mobile_money_enabled', '1', 'boolean', 'integration', 'Mobile Money Enabled'),
            ('api_rate_limit', '1000', 'integer', 'integration', 'API Rate Limit'),
        ]
        for s in settings:
            cursor.execute('''
                INSERT OR IGNORE INTO system_settings
                (key, value, data_type, category, description)
                VALUES (?, ?, ?, ?, ?)
            ''', s)
