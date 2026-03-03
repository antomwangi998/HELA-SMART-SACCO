# services.py - Service layer (business logic)
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import datetime
import hashlib
import json
import random
import re
import sqlite3
import string
import time
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from database import AdvancedDatabaseManager
from crypto import AdvancedCryptoManager
from models import KYCStatus, LoanStatus, TransactionType
from permissions import PermissionManager


class BaseService:
    """Enhanced base service with comprehensive functionality"""

    def __init__(self, db: AdvancedDatabaseManager, crypto: AdvancedCryptoManager):
        self.db = db
        self.crypto = crypto
        self.current_user = None
        self.device_id = None
        self.branch_id = None

    def set_context(self, user_id: str, device_id: str, branch_id: str = None):
        self.current_user = user_id
        self.device_id = device_id
        self.branch_id = branch_id

    def check_permission(self, action: str, resource_id: str = None) -> bool:
        if not self.current_user:
            return False
        user = self.db.fetch_one(
            "SELECT role FROM users WHERE id = ?", (self.current_user,)
        )
        if not user:
            return False
        return PermissionManager.has_permission(user['role'], action, resource_id)

    def require_permission(self, action: str, resource_id: str = None):
        if not self.check_permission(action, resource_id):
            raise PermissionError(f"Permission denied: {action}")

    def log_audit(self, action: str, entity_type: str = None,
                  entity_id: str = None, operation: str = None,
                  old_vals: dict = None, new_vals: dict = None,
                  changes_summary: str = None):
        last = self.db.fetch_one(
            "SELECT hash, blockchain_index FROM audit_log ORDER BY timestamp DESC LIMIT 1"
        )
        prev_hash = last['hash'] if last else "0" * 64
        prev_index = (last['blockchain_index'] or 0) if last else 0

        audit_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'user_id': self.current_user,
            'action': action,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'operation': operation,
            'prev_hash': prev_hash,
        }
        tx_hash = hashlib.sha256(
            json.dumps(audit_data, sort_keys=True).encode()
        ).hexdigest()

        signature = None
        if self.crypto._private_key:
            try:
                signature = self.crypto.create_digital_signature(tx_hash)
            except Exception:
                pass

        self.db.execute('''
            INSERT INTO audit_log
            (id, user_id, action, entity_type, entity_id, operation,
             old_values, new_values, changes_summary, device_id,
             hash, prev_hash, signature, blockchain_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            self.current_user, action, entity_type, entity_id, operation,
            json.dumps(old_vals) if old_vals else None,
            json.dumps(new_vals) if new_vals else None,
            changes_summary, self.device_id,
            tx_hash, prev_hash, signature, prev_index + 1
        ))
        return tx_hash

    def encrypt_sensitive_fields(self, data: dict, fields: List[str]) -> dict:
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[f"{field}_encrypted"] = self.crypto.encrypt_field(str(result[field]))
        return result

    def decrypt_sensitive_fields(self, row: sqlite3.Row, fields: List[str]) -> dict:
        result = dict(row)
        for field in fields:
            enc_field = f"{field}_encrypted"
            if enc_field in result and result[enc_field]:
                result[field] = self.crypto.decrypt_field(result[enc_field])
        return result

    def _generate_account_no(self, account_type: str) -> str:
        prefix_map = {
            'SAVINGS': 'SAV', 'CURRENT': 'CUR', 'SHARE_CAPITAL': 'SHA',
            'LOAN': 'LOA', 'FIXED_DEPOSIT': 'FD', 'SUSPENSE': 'SUS',
            'JOINT': 'JNT', 'CHILDREN_SAVINGS': 'CHD', 'RETIREMENT': 'RET',
            'EDUCATION': 'EDU', 'HOLIDAY': 'HOL', 'EMERGENCY': 'EMG'
        }
        prefix = prefix_map.get(account_type.upper(), 'ACC')
        random_part = ''.join(random.choices(string.digits, k=8))
        return f"{prefix}{random_part}"


class MemberService(BaseService):
    """Comprehensive member management service"""

    def create_member(self, data: dict) -> str:
        self.require_permission('create_member')

        required = ['first_name', 'last_name', 'id_number', 'phone']
        for field in required:
            if not data.get(field):
                raise ValueError(f"{field} is required")

        existing = self.db.fetch_one(
            "SELECT id FROM members WHERE id_number = ? OR phone = ?",
            (data.get('id_number'), data.get('phone'))
        )
        if existing:
            raise ValueError("Member with this ID or phone already exists")

        member_id = str(uuid.uuid4())
        member_no = self._generate_member_no()

        full_name = f"{data.get('first_name')} {data.get('last_name')}"
        if data.get('other_names'):
            full_name += f" {data.get('other_names')}"

        encrypted_data = self.encrypt_sensitive_fields(
            data, ['id_number', 'phone', 'phone2', 'email', 'address']
        )

        kyc_score = self._calculate_kyc_score(data)
        kyc_status = (KYCStatus.COMPLETE.value if kyc_score >= 80
                      else KYCStatus.INCOMPLETE.value)

        risk_score, risk_category = self._assess_risk(data)

        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO members
                (id, member_no, branch_id, group_id, referrer_id,
                 first_name, last_name, other_names, full_name_search,
                 id_number, id_number_encrypted, passport_number, passport_number_encrypted,
                 date_of_birth, gender, marital_status, nationality,
                 phone, phone_encrypted, phone2, phone2_encrypted,
                 email, email_encrypted, address, address_encrypted,
                 city, county, constituency, ward, postal_code, gps_coordinates,
                 occupation, employer, employer_id, department, job_title,
                 employment_type, employment_start_date, monthly_income, annual_income,
                 kyc_status, kyc_score, risk_score, risk_category,
                 membership_date, created_by, device_id, sync_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                member_id, member_no,
                data.get('branch_id', self.branch_id), data.get('group_id'),
                data.get('referrer_id'), data.get('first_name'),
                data.get('last_name'), data.get('other_names'), full_name,
                data.get('id_number'), encrypted_data.get('id_number_encrypted'),
                data.get('passport_number'), encrypted_data.get('passport_number_encrypted'),
                data.get('date_of_birth'), data.get('gender'),
                data.get('marital_status'), data.get('nationality', 'Kenyan'),
                data.get('phone'), encrypted_data.get('phone_encrypted'),
                data.get('phone2'), encrypted_data.get('phone2_encrypted'),
                data.get('email'), encrypted_data.get('email_encrypted'),
                data.get('address'), encrypted_data.get('address_encrypted'),
                data.get('city'), data.get('county'), data.get('constituency'),
                data.get('ward'), data.get('postal_code'), data.get('gps_coordinates'),
                data.get('occupation'), data.get('employer'), data.get('employer_id'),
                data.get('department'), data.get('job_title'),
                data.get('employment_type'), data.get('employment_start_date'),
                data.get('monthly_income', 0), data.get('annual_income', 0),
                kyc_status, kyc_score, risk_score, risk_category,
                datetime.date.today().isoformat(),
                self.current_user, self.device_id, 'pending', data.get('notes')
            ))

            self.db.log_change('members', member_id, 'INSERT',
                               new_data=data, user_id=self.current_user,
                               device_id=self.device_id, priority=1)

        self.log_audit('CREATE_MEMBER', 'members', member_id, 'CREATE', new_vals=data)
        self._create_default_account(member_id, data.get('branch_id', self.branch_id))
        self._generate_qr_token('member', member_id)
        self._send_welcome_notification(member_id, data)
        return member_id

    def _generate_member_no(self) -> str:
        prefix = "HELA"
        year = datetime.datetime.now().year % 100
        for _ in range(10):
            random_part = ''.join(random.choices(string.digits, k=6))
            candidate = f"{prefix}{year}{random_part}"
            existing = self.db.fetch_one(
                "SELECT id FROM members WHERE member_no = ?", (candidate,)
            )
            if not existing:
                return candidate
        timestamp = int(time.time()) % 1000000
        return f"{prefix}{year}{timestamp:06d}"

    def _calculate_kyc_score(self, data: dict) -> int:
        score = 0
        if data.get('first_name') and data.get('last_name'):
            score += 15
        if data.get('id_number'):
            score += 15
        if data.get('date_of_birth'):
            score += 10
        if data.get('phone'):
            score += 10
        if data.get('email'):
            score += 5
        if data.get('address'):
            score += 5
        if data.get('occupation'):
            score += 10
        if data.get('employer'):
            score += 10
        if data.get('monthly_income', 0) > 0:
            score += 10
        if data.get('photo_uploaded'):
            score += 5
        if data.get('signature_uploaded'):
            score += 5
        return min(score, 100)

    def _assess_risk(self, data: dict) -> Tuple[int, str]:
        score = 0
        if data.get('employment_type') == 'permanent':
            score += 20
        elif data.get('employment_type') == 'contract':
            score += 15
        else:
            score += 10
        income = data.get('monthly_income', 0)
        if income > 100000:
            score += 20
        elif income > 50000:
            score += 15
        elif income > 20000:
            score += 10
        else:
            score += 5
        if data.get('employment_start_date'):
            try:
                start = datetime.datetime.fromisoformat(data['employment_start_date'])
                years = (datetime.datetime.now() - start).days / 365
                score += 20 if years > 5 else 15 if years > 2 else 10
            except Exception:
                score += 10
        if data.get('referrer_id'):
            score += 10
        category = ('low' if score >= 70 else 'medium' if score >= 50
                    else 'high' if score >= 30 else 'very_high')
        return score, category

    def _create_default_account(self, member_id: str, branch_id: str):
        account_id = str(uuid.uuid4())
        account_no = self._generate_account_no('SAVINGS')
        product = self.db.fetch_one(
            "SELECT id FROM products WHERE product_code = 'SAV001'"
        )
        product_id = product['id'] if product else None
        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO accounts
                (id, account_no, member_id, branch_id, product_id, account_type,
                 currency, status, created_by, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id, account_no, member_id, branch_id, product_id,
                'savings', 'KES', 'active',
                self.current_user, self.device_id, 'pending'
            ))

    def _generate_qr_token(self, entity_type: str, entity_id: str):
        token_data = {
            'type': entity_type, 'id': entity_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'expires': (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
        }
        payload = json.dumps(token_data)
        encrypted = self.crypto.encrypt_field(payload)
        signature = (self.crypto.create_digital_signature(encrypted)
                     if self.crypto._private_key else None)
        self.db.execute('''
            INSERT INTO qr_tokens (id, entity_type, entity_id, token_data,
                encrypted_payload, signature, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), entity_type, entity_id,
            json.dumps(token_data), encrypted, signature, token_data['expires']
        ))

    def _send_welcome_notification(self, member_id: str, data: dict):
        pass  # Placeholder for SMS/email integration

    def get_member(self, member_id: str, include_sensitive: bool = False) -> Optional[dict]:
        self.require_permission('view_member')
        row = self.db.fetch_one(
            "SELECT * FROM members WHERE id = ? AND deleted_at IS NULL", (member_id,)
        )
        if not row:
            return None
        member = dict(row)
        if include_sensitive:
            for field in ['id_number', 'phone', 'phone2', 'email', 'address']:
                enc_field = f"{field}_encrypted"
                if member.get(enc_field):
                    member[field] = self.crypto.decrypt_field(member[enc_field])
        member['accounts'] = self._get_member_accounts(member_id)
        member['loans'] = self._get_member_loans(member_id)
        member['beneficiaries'] = self._get_member_beneficiaries(member_id)
        member['documents'] = self._get_member_documents(member_id)
        member['groups'] = self._get_member_groups(member_id)
        return member

    def _get_member_accounts(self, member_id: str) -> List[dict]:
        rows = self.db.fetch_all(
            """SELECT a.*, p.product_name
               FROM accounts a
               LEFT JOIN products p ON a.product_id = p.id
               WHERE a.member_id = ? AND a.deleted_at IS NULL
               ORDER BY a.created_at DESC""",
            (member_id,)
        )
        return [dict(row) for row in rows]

    def _get_member_loans(self, member_id: str) -> List[dict]:
        rows = self.db.fetch_all(
            """SELECT l.*, p.product_name
               FROM loans l
               LEFT JOIN products p ON l.product_id = p.id
               WHERE l.member_id = ? AND l.deleted_at IS NULL
               ORDER BY l.created_at DESC""",
            (member_id,)
        )
        return [dict(row) for row in rows]

    def _get_member_beneficiaries(self, member_id: str) -> List[dict]:
        rows = self.db.fetch_all(
            "SELECT * FROM beneficiaries WHERE member_id = ? AND deleted_at IS NULL",
            (member_id,)
        )
        return [dict(row) for row in rows]

    def _get_member_documents(self, member_id: str) -> List[dict]:
        rows = self.db.fetch_all(
            "SELECT * FROM documents WHERE entity_id = ? AND entity_type = 'member'",
            (member_id,)
        )
        return [dict(row) for row in rows]

    def _get_member_groups(self, member_id: str) -> List[dict]:
        rows = self.db.fetch_all(
            """SELECT g.*, gm.role, gm.joined_date
               FROM member_groups g
               JOIN group_members gm ON g.id = gm.group_id
               WHERE gm.member_id = ? AND gm.is_active = 1""",
            (member_id,)
        )
        return [dict(row) for row in rows]

    def search_members(self, query: str, filters: dict = None,
                       limit: int = 50) -> List[dict]:
        self.require_permission('view_members')
        sql = '''
            SELECT id, member_no, first_name, last_name, other_names,
                   phone, id_number, is_active, kyc_status, risk_category,
                   city, county, created_at
            FROM members
            WHERE deleted_at IS NULL
            AND (first_name LIKE ? OR last_name LIKE ? OR
                 full_name_search LIKE ? OR member_no LIKE ? OR
                 id_number LIKE ? OR phone LIKE ? OR email LIKE ?)
        '''
        params = [f'%{query}%'] * 7
        if filters:
            if filters.get('branch_id'):
                sql += " AND branch_id = ?"
                params.append(filters['branch_id'])
            if filters.get('kyc_status'):
                sql += " AND kyc_status = ?"
                params.append(filters['kyc_status'])
            if filters.get('is_active') is not None:
                sql += " AND is_active = ?"
                params.append(1 if filters['is_active'] else 0)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.db.fetch_all(sql, tuple(params))
        return [dict(row) for row in rows]

    def update_member(self, member_id: str, updates: dict) -> bool:
        self.require_permission('edit_member')
        current = self.get_member(member_id, include_sensitive=True)
        if not current:
            return False
        for field in ['id_number', 'phone', 'phone2', 'email', 'address']:
            if field in updates:
                updates[f"{field}_encrypted"] = self.crypto.encrypt_field(str(updates[field]))
        allowed_fields = [
            'first_name', 'last_name', 'other_names', 'date_of_birth',
            'gender', 'marital_status', 'nationality', 'city', 'county',
            'constituency', 'ward', 'postal_code', 'gps_coordinates',
            'occupation', 'employer', 'department', 'job_title',
            'employment_type', 'employment_start_date', 'monthly_income',
            'email', 'phone', 'address', 'notes'
        ]
        update_fields, values = [], []
        for field in allowed_fields:
            if field in updates:
                update_fields.append(f"{field} = ?")
                values.append(updates[field])
            elif f"{field}_encrypted" in updates:
                update_fields.append(f"{field}_encrypted = ?")
                values.append(updates[f"{field}_encrypted"])
        if not update_fields:
            return False
        update_fields.append("updated_at = ?")
        values.extend([datetime.datetime.now().isoformat(), member_id])
        with self.db.transaction() as cursor:
            cursor.execute(
                f"UPDATE members SET {', '.join(update_fields)} WHERE id = ?",
                values
            )
            self.db.log_change('members', member_id, 'UPDATE',
                               old_data=current, new_data=updates,
                               user_id=self.current_user, device_id=self.device_id)
        self.log_audit('UPDATE_MEMBER', 'members', member_id, 'UPDATE',
                       old_vals=current, new_vals=updates)
        return True

    def add_beneficiary(self, member_id: str, data: dict) -> str:
        self.require_permission('edit_member')
        ben_id = str(uuid.uuid4())
        encrypted = self.encrypt_sensitive_fields(data, ['phone', 'email', 'id_number'])
        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO beneficiaries
                (id, member_id, full_name, relationship, phone, phone_encrypted,
                 email, email_encrypted, id_number, id_number_encrypted,
                 date_of_birth, address, percentage, is_primary, is_nominee,
                 bank_account_number, bank_name, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ben_id, member_id, data.get('full_name'), data.get('relationship'),
                data.get('phone'), encrypted.get('phone_encrypted'),
                data.get('email'), encrypted.get('email_encrypted'),
                data.get('id_number'), encrypted.get('id_number_encrypted'),
                data.get('date_of_birth'), data.get('address'),
                data.get('percentage', 100), data.get('is_primary', 0),
                data.get('is_nominee', 0), data.get('bank_account_number'),
                data.get('bank_name'), self.device_id, 'pending'
            ))
        self.log_audit('ADD_BENEFICIARY', 'beneficiaries', ben_id, 'CREATE')
        return ben_id

    def flag_as_dormant(self, member_id: str, reason: str = None):
        self.require_permission('manage_members')
        now = datetime.datetime.now().isoformat()
        with self.db.transaction() as cursor:
            cursor.execute('''
                UPDATE members SET is_dormant = 1, dormant_since = ?,
                dormancy_reason = ?, updated_at = ? WHERE id = ?
            ''', (now, reason or 'No activity', now, member_id))
        self.log_audit('FLAG_DORMANT', 'members', member_id, 'UPDATE',
                       changes_summary=f"Flagged as dormant: {reason}")

    def reactivate_member(self, member_id: str):
        self.require_permission('manage_members')
        with self.db.transaction() as cursor:
            cursor.execute('''
                UPDATE members SET is_dormant = 0, dormant_since = NULL,
                dormancy_reason = NULL, updated_at = ? WHERE id = ?
            ''', (datetime.datetime.now().isoformat(), member_id))
        self.log_audit('REACTIVATE_MEMBER', 'members', member_id, 'UPDATE')

    def get_dormant_members(self, days: int = 180, limit: int = 100) -> List[dict]:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        rows = self.db.fetch_all('''
            SELECT m.*, MAX(t.posted_date) as last_transaction
            FROM members m
            LEFT JOIN accounts a ON m.id = a.member_id
            LEFT JOIN transactions t ON a.id = t.account_id
            WHERE m.is_dormant = 0 AND m.is_active = 1 AND m.membership_date < ?
            GROUP BY m.id
            HAVING (last_transaction < ? OR last_transaction IS NULL)
            LIMIT ?
        ''', (cutoff, cutoff, limit))
        return [dict(row) for row in rows]

    def get_member_statistics(self) -> dict:
        stats = {}
        result = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM members WHERE is_active = 1 AND deleted_at IS NULL"
        )
        stats['total_active'] = result['c'] if result else 0
        result = self.db.fetch_one("SELECT COUNT(*) as c FROM members WHERE is_dormant = 1")
        stats['total_dormant'] = result['c'] if result else 0
        rows = self.db.fetch_all("SELECT kyc_status, COUNT(*) as c FROM members GROUP BY kyc_status")
        stats['kyc_breakdown'] = {r['kyc_status']: r['c'] for r in rows}
        rows = self.db.fetch_all("SELECT risk_category, COUNT(*) as c FROM members GROUP BY risk_category")
        stats['risk_breakdown'] = {r['risk_category']: r['c'] for r in rows}
        month_start = datetime.date.today().replace(day=1).isoformat()
        result = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM members WHERE membership_date >= ?", (month_start,)
        )
        stats['new_this_month'] = result['c'] if result else 0
        rows = self.db.fetch_all(
            "SELECT gender, COUNT(*) as c FROM members WHERE gender IS NOT NULL GROUP BY gender"
        )
        stats['gender_distribution'] = {r['gender']: r['c'] for r in rows}
        return stats

    def self_register(self, data: dict, username: str = None, password: str = None) -> str:
        """Create member + user account atomically. username/password required for self-service."""
        required = ['first_name', 'last_name', 'id_number', 'phone']
        for field in required:
            if not data.get(field):
                raise ValueError(f"{field.replace('_', ' ').title()} is required")

        # --- Pre-flight checks (before ANY inserts) ---
        if username:
            existing_user = self.db.fetch_one(
                "SELECT id FROM users WHERE username = ?", (username,)
            )
            if existing_user:
                raise ValueError("Username already taken. Please choose a different username.")

        existing_member = self.db.fetch_one(
            "SELECT id FROM members WHERE id_number = ? OR phone = ?",
            (data.get('id_number'), data.get('phone'))
        )
        if existing_member:
            # If there's already a user linked, it's a true duplicate
            linked_user = self.db.fetch_one(
                "SELECT id FROM users WHERE member_id = ?", (existing_member['id'],)
            )
            if linked_user:
                raise ValueError("A member with this ID or phone number already exists.")
            # Orphaned member (no user linked) — clean it up and proceed
            self.db.execute("DELETE FROM accounts WHERE member_id = ?", (existing_member['id'],))
            self.db.execute("DELETE FROM members WHERE id = ?", (existing_member['id'],))

        # Resolve branch_id
        if not data.get('branch_id') and not self.branch_id:
            br = self.db.fetch_one(
                "SELECT id FROM branches WHERE is_active=1 ORDER BY is_head_office DESC, created_at LIMIT 1"
            )
            branch_id = br['id'] if br else None
        else:
            branch_id = data.get('branch_id') or self.branch_id

        member_id = str(uuid.uuid4())
        member_no = self._generate_member_no()
        full_name = f"{data.get('first_name')} {data.get('last_name')}"
        if data.get('other_names'):
            full_name += f" {data.get('other_names')}"

        encrypted_data = self.encrypt_sensitive_fields(
            data, ['id_number', 'phone', 'phone2', 'email', 'address']
        )
        kyc_score = self._calculate_kyc_score(data)
        kyc_status = (KYCStatus.COMPLETE.value if kyc_score >= 80
                      else KYCStatus.INCOMPLETE.value)
        risk_score, risk_category = self._assess_risk(data)

        # --- Single atomic transaction for member + account + user ---
        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO members
                (id, member_no, branch_id, first_name, last_name, other_names,
                 full_name_search, id_number, id_number_encrypted,
                 date_of_birth, gender, marital_status, nationality,
                 phone, phone_encrypted, phone2, phone2_encrypted,
                 email, email_encrypted, address, address_encrypted,
                 city, county, constituency, ward, postal_code,
                 occupation, employer, department, job_title,
                 employment_type, monthly_income,
                 kyc_status, kyc_score, risk_score, risk_category,
                 membership_date, consent_signed, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                member_id, member_no, branch_id,
                data.get('first_name'), data.get('last_name'), data.get('other_names'),
                full_name,
                data.get('id_number'), encrypted_data.get('id_number_encrypted'),
                data.get('date_of_birth'), data.get('gender'),
                data.get('marital_status'), data.get('nationality', 'Kenyan'),
                data.get('phone'), encrypted_data.get('phone_encrypted'),
                data.get('phone2'), encrypted_data.get('phone2_encrypted'),
                data.get('email'), encrypted_data.get('email_encrypted'),
                data.get('address'), encrypted_data.get('address_encrypted'),
                data.get('city'), data.get('county'), data.get('constituency'),
                data.get('ward'), data.get('postal_code'),
                data.get('occupation'), data.get('employer'),
                data.get('department'), data.get('job_title'),
                data.get('employment_type'), data.get('monthly_income', 0),
                kyc_status, kyc_score, risk_score, risk_category,
                datetime.date.today().isoformat(),
                data.get('consent_signed', 0), 'pending'
            ))

            # Savings account
            prod = cursor.execute(
                "SELECT id FROM products WHERE product_code='SAV001'"
            ).fetchone()
            product_id = prod[0] if prod else None
            account_no = self._generate_account_no('SAVINGS')
            cursor.execute('''
                INSERT INTO accounts
                (id, account_no, member_id, branch_id, product_id,
                 account_type, currency, status, created_by, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), account_no, member_id, branch_id, product_id,
                'savings', 'KES', 'active', None, self.device_id or 'reg', 'pending'
            ))

            # User account (in same transaction — all-or-nothing)
            if username and password:
                salt, hashed, iterations = self.crypto.hash_password(password)
                user_id = str(uuid.uuid4())
                now = datetime.datetime.now().isoformat()
                # Check if member_id column exists (safe for older DBs)
                col_check = cursor.execute("PRAGMA table_info(users)").fetchall()
                col_names = [c[1] for c in col_check]
                if 'member_id' not in col_names:
                    try:
                        cursor.execute("ALTER TABLE users ADD COLUMN member_id TEXT")
                    except Exception:
                        pass
                cursor.execute(
                    "INSERT INTO users (id, username, password_hash, salt, iterations, "
                    "role, member_id, is_active, created_at) VALUES (?,?,?,?,?,?,?,1,?)",
                    (user_id, username, hashed, salt, iterations, 'member', member_id, now)
                )

        return member_id

    def create_member_user_account(self, member_id: str, username: str, password: str) -> str:
        """Create a user login linked to a member. Kept for backward compat."""
        existing = self.db.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            raise ValueError("Username already taken.")
        salt, hashed, iterations = self.crypto.hash_password(password)
        user_id = str(uuid.uuid4())
        self._insert_user(user_id, username, hashed, salt, iterations, 'member', member_id)
        return user_id

    def _insert_user(self, user_id, username, hashed, salt, iterations, role, member_id=None):
        """Insert a user row, gracefully handling schemas that lack member_id column."""
        # Check if member_id column exists
        cols_info = self.db.fetch_all("PRAGMA table_info(users)")
        col_names = [c['name'] for c in cols_info]
        now = datetime.datetime.now().isoformat()

        if 'member_id' in col_names:
            self.db.execute(
                "INSERT INTO users (id, username, password_hash, salt, iterations, role, "
                "member_id, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (user_id, username, hashed, salt, iterations, role, member_id, now)
            )
        else:
            # Old schema without member_id — add the column first, then insert
            try:
                self.db.execute("ALTER TABLE users ADD COLUMN member_id TEXT")
            except Exception:
                pass
            self.db.execute(
                "INSERT INTO users (id, username, password_hash, salt, iterations, role, "
                "member_id, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (user_id, username, hashed, salt, iterations, role, member_id, now)
            )



class AccountService(BaseService):
    """Comprehensive account and transaction service"""

    def open_account(self, member_id: str, account_type: str,
                     product_id: str = None, currency: str = 'KES',
                     initial_deposit: int = 0, **kwargs) -> str:
        self.require_permission('open_account')
        member = self.db.fetch_one(
            "SELECT id FROM members WHERE id = ? AND is_active = 1", (member_id,)
        )
        if not member:
            raise ValueError("Member not found or inactive")

        account_id = str(uuid.uuid4())
        account_no = self._generate_account_no(account_type)
        interest_rate = 0

        if product_id:
            product = self.db.fetch_one(
                "SELECT interest_rate, min_opening_balance_minor FROM products WHERE id = ?",
                (product_id,)
            )
            if product:
                interest_rate = product['interest_rate']
                if initial_deposit < product['min_opening_balance_minor']:
                    raise ValueError("Initial deposit below minimum required")

        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO accounts
                (id, account_no, member_id, branch_id, product_id, account_type,
                 currency, status, balance_minor, available_balance_minor,
                 interest_rate, opening_date, created_by, device_id, sync_status,
                 sms_alert_enabled, email_alert_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id, account_no, member_id, self.branch_id, product_id,
                account_type, currency, 'active', initial_deposit, initial_deposit,
                interest_rate, datetime.date.today().isoformat(),
                self.current_user, self.device_id, 'pending',
                kwargs.get('sms_alerts', 1), kwargs.get('email_alerts', 1)
            ))
            if initial_deposit > 0:
                self._post_transaction_internal(
                    cursor, account_id, TransactionType.DEPOSIT.value,
                    initial_deposit, "Initial deposit", channel='branch'
                )
            self.db.log_change('accounts', account_id, 'INSERT',
                               new_data={'type': account_type, 'initial_deposit': initial_deposit},
                               user_id=self.current_user, device_id=self.device_id)
        self.log_audit('OPEN_ACCOUNT', 'accounts', account_id, 'CREATE')
        return account_id

    def post_transaction(self, account_id: str, tx_type: str,
                         amount_minor: int, description: str = "",
                         related_account_id: str = None,
                         channel: str = 'branch', **kwargs) -> str:
        self.require_permission(f'process_{tx_type.lower()}')
        with self.db.transaction() as cursor:
            return self._post_transaction_internal(
                cursor, account_id, tx_type, amount_minor,
                description, related_account_id, channel, **kwargs
            )

    def _post_transaction_internal(self, cursor, account_id: str, tx_type: str,
                                   amount_minor: int, description: str = "",
                                   related_account_id: str = None,
                                   channel: str = 'branch', **kwargs) -> str:
        account = self.db.fetch_one(
            """SELECT a.*, m.first_name, m.last_name, m.phone,
                      m.email_alert_enabled, m.sms_alert_enabled
               FROM accounts a
               JOIN members m ON a.member_id = m.id
               WHERE a.id = ? AND a.deleted_at IS NULL""",
            (account_id,)
        )
        if not account:
            raise ValueError("Account not found")
        if account['status'] != 'active':
            raise ValueError(f"Account is {account['status']}")

        if kwargs.get('idempotency_key'):
            existing = self.db.fetch_one(
                "SELECT id FROM transactions WHERE idempotency_key = ?",
                (kwargs['idempotency_key'],)
            )
            if existing:
                return existing['id']

        current_balance = account['balance_minor'] or 0
        available_balance = account['available_balance_minor'] or 0

        credit_types = [
            TransactionType.DEPOSIT.value, TransactionType.LOAN_DISBURSEMENT.value,
            TransactionType.INTEREST.value, TransactionType.DIVIDEND.value
        ]
        is_credit = tx_type in credit_types

        if is_credit:
            new_balance = current_balance + amount_minor
            new_available = available_balance + amount_minor
        else:
            new_balance = current_balance - amount_minor
            new_available = available_balance - amount_minor
            if new_available < -(account['overdraft_limit_minor'] or 0):
                raise ValueError("Insufficient funds")
            if not self._check_daily_limits(account_id, amount_minor, tx_type):
                raise ValueError("Daily transaction limit exceeded")

        tx_id = str(uuid.uuid4())
        tx_ref = self._generate_transaction_ref()

        last_tx = self.db.fetch_one(
            "SELECT tx_hash FROM transactions WHERE account_id = ? ORDER BY posted_date DESC LIMIT 1",
            (account_id,)
        )
        prev_hash = last_tx['tx_hash'] if last_tx else "0" * 64

        tx_data = {
            'id': tx_id, 'account_id': account_id, 'type': tx_type,
            'amount': amount_minor,
            'timestamp': datetime.datetime.now().isoformat(),
            'prev_hash': prev_hash
        }
        tx_hash = hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest()

        cursor.execute('''
            INSERT INTO transactions
            (id, transaction_ref, account_id, counterparty_account_id, transaction_type,
             amount_minor, currency, description, narrative, reference_number,
             related_transaction_id, teller_id, branch_id, device_id, channel,
             prev_hash, tx_hash, posted_date, value_date, transaction_date,
             idempotency_key, gps_coordinates, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tx_id, tx_ref, account_id, related_account_id, tx_type,
            amount_minor, account['currency'], description,
            kwargs.get('narrative'), kwargs.get('reference_number'),
            kwargs.get('related_transaction_id'), self.current_user,
            self.branch_id, self.device_id, channel,
            prev_hash, tx_hash,
            datetime.datetime.now().isoformat(),
            kwargs.get('value_date', datetime.date.today().isoformat()),
            datetime.date.today().isoformat(),
            kwargs.get('idempotency_key'),
            kwargs.get('gps_coordinates'), kwargs.get('ip_address')
        ))

        cursor.execute('''
            UPDATE accounts SET
            balance_minor = ?, available_balance_minor = ?,
            last_transaction_date = ?, version = version + 1
            WHERE id = ?
        ''', (new_balance, new_available, datetime.datetime.now().isoformat(), account_id))

        if is_credit:
            cursor.execute(
                "UPDATE accounts SET last_deposit_date = ? WHERE id = ?",
                (datetime.date.today().isoformat(), account_id)
            )
        else:
            cursor.execute(
                "UPDATE accounts SET last_withdrawal_date = ? WHERE id = ?",
                (datetime.date.today().isoformat(), account_id)
            )

        self._check_anomalies(account_id, tx_type, amount_minor, channel)
        return tx_id

    def _generate_transaction_ref(self) -> str:
        timestamp = int(time.time())
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"TXN{timestamp}{random_suffix}"

    def _check_daily_limits(self, account_id: str, amount_minor: int, tx_type: str) -> bool:
        today = datetime.date.today().isoformat()
        result = self.db.fetch_one('''
            SELECT COALESCE(SUM(amount_minor), 0) as total
            FROM transactions
            WHERE account_id = ? AND transaction_type = ?
            AND date(transaction_date) = ? AND is_reversed = 0
        ''', (account_id, tx_type, today))
        daily_total = result['total'] if result else 0
        limits = {'withdrawal': 100000000, 'transfer': 500000000}
        limit = limits.get(tx_type.lower(), 1000000000)
        return (daily_total + amount_minor) <= limit

    def _check_anomalies(self, account_id: str, tx_type: str,
                         amount_minor: int, channel: str):
        alerts = []
        if tx_type == TransactionType.DEPOSIT.value and amount_minor > 900000:
            today = datetime.date.today().isoformat()
            result = self.db.fetch_one('''
                SELECT COUNT(*) as c, SUM(amount_minor) as total
                FROM transactions
                WHERE account_id = ? AND transaction_type = 'deposit'
                AND date(posted_date) = ? AND amount_minor > 900000
            ''', (account_id, today))
            if result and result['c'] >= 3:
                alerts.append({
                    'type': 'structuring', 'severity': 'high',
                    'description': f"Multiple large deposits: {result['c']} today"
                })
        recent_count = self.db.fetch_one('''
            SELECT COUNT(*) as c FROM transactions
            WHERE account_id = ? AND posted_date > datetime('now', '-1 hour')
        ''', (account_id,))
        if recent_count and recent_count['c'] > 10:
            alerts.append({
                'type': 'velocity', 'severity': 'medium',
                'description': f"High velocity: {recent_count['c']} transactions in 1 hour"
            })
        for alert in alerts:
            self.db.execute('''
                INSERT INTO anomaly_flags
                (id, entity_type, entity_id, anomaly_type, severity, description, detected_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), 'account', account_id,
                alert['type'], alert['severity'], alert['description'], 'system'
            ))

    def transfer(self, from_account_id: str, to_account_id: str,
                 amount_minor: int, description: str = "", **kwargs) -> Tuple[str, str]:
        self.require_permission('process_transfers')
        if from_account_id == to_account_id:
            raise ValueError("Cannot transfer to same account")
        with self.db.transaction() as cursor:
            tx1 = self._post_transaction_internal(
                cursor, from_account_id, TransactionType.TRANSFER.value,
                amount_minor, f"Transfer to {to_account_id}: {description}",
                to_account_id, 'transfer', **kwargs
            )
            tx2 = self._post_transaction_internal(
                cursor, to_account_id, TransactionType.TRANSFER.value,
                amount_minor, f"Transfer from {from_account_id}: {description}",
                from_account_id, 'transfer', **kwargs
            )
            cursor.execute("UPDATE transactions SET related_transaction_id = ? WHERE id = ?", (tx2, tx1))
            cursor.execute("UPDATE transactions SET related_transaction_id = ? WHERE id = ?", (tx1, tx2))
        self.log_audit('TRANSFER', 'transactions', tx1, 'CREATE',
                       new_vals={'from': from_account_id, 'to': to_account_id, 'amount': amount_minor})
        return tx1, tx2

    def get_account_statement(self, account_id: str, start_date: str = None,
                              end_date: str = None,
                              include_reversed: bool = False) -> List[dict]:
        self.require_permission('view_transactions')
        query = '''
            SELECT t.*, a.account_no, a.account_type, m.first_name, m.last_name
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            JOIN members m ON a.member_id = m.id
            WHERE t.account_id = ? AND t.deleted_at IS NULL
        '''
        params = [account_id]
        if not include_reversed:
            query += " AND t.is_reversed = 0"
        if start_date:
            query += " AND date(t.transaction_date) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date(t.transaction_date) <= ?"
            params.append(end_date)
        query += " ORDER BY t.posted_date DESC"
        rows = self.db.fetch_all(query, tuple(params))
        return [dict(row) for row in rows]

    def calculate_interest(self, account_id: str, as_of_date: str = None) -> dict:
        if not as_of_date:
            as_of_date = datetime.date.today().isoformat()
        account = self.db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
        if not account or account['interest_rate'] <= 0:
            return {'interest': 0, 'calculation_method': 'none'}
        transactions = self.db.fetch_all('''
            SELECT transaction_date,
                   SUM(CASE WHEN transaction_type IN ('deposit', 'loan_disbursement')
                       THEN amount_minor ELSE -amount_minor END) as net_amount
            FROM transactions
            WHERE account_id = ? AND is_reversed = 0 AND date(posted_date) <= ?
            GROUP BY transaction_date ORDER BY transaction_date
        ''', (account_id, as_of_date))
        total_interest = 0
        daily_rate = account['interest_rate'] / 100 / 365
        running_balance = 0
        for tx in transactions:
            running_balance += tx['net_amount']
            total_interest += running_balance * daily_rate
        return {
            'interest_minor': int(total_interest),
            'interest_formatted': total_interest / 100,
            'calculation_method': 'daily_balance',
            'rate': account['interest_rate'],
            'days_calculated': len(transactions)
        }

    def close_account(self, account_id: str, reason: str = "",
                      transfer_to_account_id: str = None):
        self.require_permission('close_account')
        account = self.db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
        if not account:
            raise ValueError("Account not found")
        balance = account['balance_minor'] or 0
        with self.db.transaction() as cursor:
            if balance != 0:
                if not transfer_to_account_id:
                    raise ValueError("Account has balance. Transfer required.")
                self._post_transaction_internal(
                    cursor, account_id, TransactionType.TRANSFER.value,
                    abs(balance), f"Account closure transfer", transfer_to_account_id, 'system'
                )
                self._post_transaction_internal(
                    cursor, transfer_to_account_id, TransactionType.TRANSFER.value,
                    abs(balance), f"Transfer from closing account", account_id, 'system'
                )
            cursor.execute('''
                UPDATE accounts SET status = 'closed', closing_date = ?,
                closing_reason = ?, balance_minor = 0, available_balance_minor = 0,
                updated_at = ? WHERE id = ?
            ''', (
                datetime.date.today().isoformat(), reason,
                datetime.datetime.now().isoformat(), account_id
            ))
        self.log_audit('CLOSE_ACCOUNT', 'accounts', account_id, 'UPDATE',
                       changes_summary=f"Closed: {reason}")


class LoanService(BaseService):
    """Comprehensive loan management service"""

    def apply_loan(self, member_id: str, principal_minor: int,
                   term_months: int, interest_rate: float,
                   purpose: str = "", product_id: str = None, **kwargs) -> str:
        self.require_permission('create_loan')
        member = self.db.fetch_one(
            """SELECT m.*,
                (SELECT COUNT(*) FROM loans WHERE member_id = m.id
                 AND status IN ('active', 'disbursed', 'pending')) as active_loans
               FROM members m WHERE m.id = ?""",
            (member_id,)
        )
        if not member:
            raise ValueError("Member not found")
        if member['active_loans'] > 0 and not kwargs.get('allow_multiple'):
            raise ValueError("Member has existing active loan")
        if member['kyc_status'] not in ['complete', 'verified']:
            raise ValueError("Member KYC incomplete")

        credit_score = self._calculate_credit_score(member_id, principal_minor)
        if credit_score < 30:
            raise ValueError(f"Loan declined: Credit score too low ({credit_score})")

        loan_id = str(uuid.uuid4())
        loan_no = self._generate_loan_no()
        application_date = datetime.date.today()
        maturity_date = application_date + datetime.timedelta(days=30 * term_months)
        first_payment_date = application_date + datetime.timedelta(days=30)

        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO loans
                (id, loan_no, member_id, group_id, product_id, branch_id,
                 loan_purpose, purpose_category, principal_amount_minor,
                 interest_rate, interest_method, term_months, grace_period_days,
                 application_date, maturity_date, first_payment_date,
                 status, credit_score_at_application, created_by, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                loan_id, loan_no, member_id, kwargs.get('group_id'),
                product_id, self.branch_id, purpose,
                kwargs.get('purpose_category', 'general'),
                principal_minor, interest_rate,
                kwargs.get('interest_method', 'flat'),
                term_months, kwargs.get('grace_period_days', 0),
                application_date.isoformat(), maturity_date.isoformat(),
                first_payment_date.isoformat(), 'pending', credit_score,
                self.current_user, self.device_id, 'pending'
            ))

        self._create_approval_workflow(loan_id, principal_minor, 'loan_approval')
        self.log_audit('LOAN_APPLICATION', 'loans', loan_id, 'CREATE',
                       new_vals={'amount': principal_minor, 'term': term_months})
        return loan_id

    def _generate_loan_no(self) -> str:
        year = datetime.datetime.now().year % 100
        random_part = ''.join(random.choices(string.digits, k=6))
        return f"LN{year}{random_part}"

    def _calculate_credit_score(self, member_id: str, requested_amount: int) -> int:
        score = 50
        member = self.db.fetch_one("SELECT * FROM members WHERE id = ?", (member_id,))
        if member:
            if member['kyc_status'] == 'verified':
                score += 15
            elif member['kyc_status'] == 'complete':
                score += 10
            if member['employment_type'] == 'permanent':
                score += 10
            monthly_income = member['monthly_income'] or 0
            if monthly_income > 0:
                ratio = (requested_amount / 100) / monthly_income
                score += 15 if ratio < 3 else 10 if ratio < 6 else -10

        account_age = self.db.fetch_one(
            "SELECT MIN(opening_date) as first_account FROM accounts WHERE member_id = ?",
            (member_id,)
        )
        if account_age and account_age['first_account']:
            try:
                first_date = datetime.datetime.fromisoformat(account_age['first_account'])
                months_member = (datetime.datetime.now() - first_date).days / 30
                score += 10 if months_member > 12 else 5 if months_member > 6 else 0
            except Exception:
                pass

        loan_history = self.db.fetch_one('''
            SELECT COUNT(*) as total_loans,
                   SUM(CASE WHEN status = 'closed' AND days_in_arrears = 0 THEN 1 ELSE 0 END) as good_loans,
                   SUM(CASE WHEN status = 'written_off' THEN 1 ELSE 0 END) as bad_loans
            FROM loans WHERE member_id = ?
        ''', (member_id,))
        if loan_history:
            if loan_history['good_loans']:
                score += min(loan_history['good_loans'] * 5, 20)
            if loan_history['bad_loans']:
                score -= loan_history['bad_loans'] * 20
        return max(0, min(100, score))

    def _create_approval_workflow(self, entity_id: str, amount_minor: int, action: str):
        levels = 3 if amount_minor > 10000000 else 2 if amount_minor > 1000000 else 1
        self.db.execute('''
            INSERT INTO approvals
            (id, entity_type, entity_id, action, requested_by, amount_minor,
             priority, max_levels, status, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), 'loan', entity_id, action, self.current_user,
            amount_minor, 'high' if amount_minor > 5000000 else 'normal',
            levels, 'pending', self.device_id
        ))

    def appraise_loan(self, loan_id: str, score: int, notes: str = "",
                      recommendation: str = None):
        self.require_permission('appraise_loan')
        updates = {
            'appraisal_score': score, 'appraisal_notes': notes,
            'appraisal_date': datetime.datetime.now().isoformat(),
            'appraised_by': self.current_user, 'status': 'appraisal'
        }
        if recommendation:
            updates['sub_status'] = recommendation
        with self.db.transaction() as cursor:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values())
            cursor.execute(
                f"UPDATE loans SET {set_clause}, updated_at = ? WHERE id = ?",
                (*values, datetime.datetime.now().isoformat(), loan_id)
            )
        self.log_audit('LOAN_APPRAISAL', 'loans', loan_id, 'UPDATE', new_vals=updates)

    def committee_review(self, loan_id: str, decision: str, notes: str = "",
                         approved_amount_minor: int = None):
        self.require_permission('approve_loans')
        status = 'approved' if decision == 'approved' else 'rejected'
        updates = {
            'committee_decision': decision, 'committee_notes': notes,
            'committee_date': datetime.datetime.now().isoformat(), 'status': status
        }
        if decision == 'approved' and approved_amount_minor:
            updates['approved_amount_minor'] = approved_amount_minor
            updates['approved_date'] = datetime.datetime.now().isoformat()
            updates['approved_by'] = self.current_user
        with self.db.transaction() as cursor:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values())
            cursor.execute(
                f"UPDATE loans SET {set_clause}, updated_at = ? WHERE id = ?",
                (*values, datetime.datetime.now().isoformat(), loan_id)
            )
        self.log_audit('LOAN_COMMITTEE', 'loans', loan_id, 'UPDATE', new_vals=updates)

    def disburse_loan(self, loan_id: str, amount_minor: int = None,
                      disbursement_method: str = 'cash', **kwargs) -> str:
        self.require_permission('disburse_loan')
        loan = self.db.fetch_one("SELECT * FROM loans WHERE id = ?", (loan_id,))
        if not loan:
            raise ValueError("Loan not found")
        if loan['status'] != 'approved':
            raise ValueError(f"Loan must be approved, current status: {loan['status']}")

        disburse_amount = amount_minor or loan['approved_amount_minor'] or loan['principal_amount_minor']
        account_id = str(uuid.uuid4())
        account_no = self._generate_account_no('LOAN')

        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO accounts
                (id, account_no, member_id, branch_id, account_type,
                 balance_minor, status, created_by, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id, account_no, loan['member_id'],
                loan['branch_id'] or self.branch_id, 'loan',
                disburse_amount, 'active',
                self.current_user, self.device_id, 'pending'
            ))
            cursor.execute('''
                UPDATE loans SET
                disbursement_date = ?, disbursed_by = ?,
                disbursed_amount_minor = ?, outstanding_principal_minor = ?,
                status = ?, updated_at = ? WHERE id = ?
            ''', (
                datetime.date.today().isoformat(), self.current_user,
                disburse_amount, disburse_amount, 'disbursed',
                datetime.datetime.now().isoformat(), loan_id
            ))
            self._generate_schedule(
                cursor, loan_id, disburse_amount,
                loan['interest_rate'], loan['term_months'],
                loan['interest_method']
            )
        self.log_audit('LOAN_DISBURSEMENT', 'loans', loan_id, 'UPDATE',
                       new_vals={'amount': disburse_amount, 'method': disbursement_method})
        return account_id

    def _generate_schedule(self, cursor, loan_id: str, principal: int,
                           rate: float, term: int, method: str = 'flat'):
        if method == 'flat':
            total_interest = int(principal * (rate / 100) * (term / 12))
            monthly_principal = principal // term
            monthly_interest = total_interest // term
            for i in range(1, term + 1):
                due_date = datetime.date.today() + datetime.timedelta(days=30 * i)
                cursor.execute('''
                    INSERT INTO loan_schedule
                    (id, loan_id, installment_no, due_date, principal_amount_minor,
                     interest_amount_minor, total_amount_minor, device_id, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()), loan_id, i, due_date.isoformat(),
                    monthly_principal, monthly_interest,
                    monthly_principal + monthly_interest,
                    self.device_id, 'pending'
                ))
        else:
            monthly_rate = rate / 100 / 12
            monthly_payment = int(
                principal * (monthly_rate * (1 + monthly_rate) ** term) /
                ((1 + monthly_rate) ** term - 1)
            )
            balance = principal
            for i in range(1, term + 1):
                interest = int(balance * monthly_rate)
                principal_payment = min(monthly_payment - interest, balance)
                balance -= principal_payment
                due_date = datetime.date.today() + datetime.timedelta(days=30 * i)
                cursor.execute('''
                    INSERT INTO loan_schedule
                    (id, loan_id, installment_no, due_date, principal_amount_minor,
                     interest_amount_minor, total_amount_minor, device_id, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()), loan_id, i, due_date.isoformat(),
                    principal_payment, interest,
                    principal_payment + interest,
                    self.device_id, 'pending'
                ))

    def process_repayment(self, loan_id: str, amount_minor: int,
                          payment_method: str = 'cash',
                          account_id: str = None) -> dict:
        self.require_permission('process_repayments')
        loan = self.db.fetch_one("SELECT * FROM loans WHERE id = ?", (loan_id,))
        if not loan:
            raise ValueError("Loan not found")
        outstanding = {
            'principal': loan['outstanding_principal_minor'] or 0,
            'interest': loan['outstanding_interest_minor'] or 0,
            'penalties': loan['outstanding_penalties_minor'] or 0,
            'fees': loan['outstanding_fees_minor'] or 0
        }
        total_outstanding = sum(outstanding.values())
        if amount_minor > total_outstanding:
            raise ValueError(f"Payment exceeds outstanding balance: {total_outstanding}")

        allocation = {}
        remaining = amount_minor
        for category in ['penalties', 'fees', 'interest', 'principal']:
            payment = min(remaining, outstanding[category])
            allocation[category] = payment
            remaining -= payment

        new_outstanding = {k: outstanding[k] - allocation[k] for k in outstanding}
        new_status = 'closed' if new_outstanding['principal'] == 0 else loan['status']

        with self.db.transaction() as cursor:
            cursor.execute('''
                UPDATE loans SET
                outstanding_principal_minor = ?, outstanding_interest_minor = ?,
                outstanding_penalties_minor = ?, outstanding_fees_minor = ?,
                total_repaid_minor = total_repaid_minor + ?,
                status = ?, updated_at = ? WHERE id = ?
            ''', (
                new_outstanding['principal'], new_outstanding['interest'],
                new_outstanding['penalties'], new_outstanding['fees'],
                amount_minor, new_status, datetime.datetime.now().isoformat(), loan_id
            ))
            self._update_schedule_payments(cursor, loan_id, allocation)
            if new_status == 'closed':
                cursor.execute(
                    "UPDATE accounts SET status = 'closed' WHERE member_id = ? AND account_type = 'loan'",
                    (loan['member_id'],)
                )

        self.log_audit('LOAN_REPAYMENT', 'loans', loan_id, 'UPDATE',
                       new_vals={'amount': amount_minor, 'allocation': allocation})
        return {
            'amount_paid': amount_minor, 'allocation': allocation,
            'new_outstanding': new_outstanding, 'status': new_status
        }

    def _update_schedule_payments(self, cursor, loan_id: str, allocation: dict):
        total_principal_paid = allocation['principal']
        installments = self.db.fetch_all('''
            SELECT * FROM loan_schedule
            WHERE loan_id = ? AND status IN ('pending', 'partial')
            ORDER BY installment_no
        ''', (loan_id,))
        for inst in installments:
            if total_principal_paid <= 0:
                break
            principal_due = inst['principal_amount_minor'] - (inst['paid_amount_minor'] or 0)
            payment = min(total_principal_paid, principal_due)
            new_paid = (inst['paid_amount_minor'] or 0) + payment
            status = 'paid' if new_paid >= inst['total_amount_minor'] else 'partial'
            cursor.execute('''
                UPDATE loan_schedule SET paid_amount_minor = ?,
                paid_date = ?, status = ? WHERE id = ?
            ''', (
                new_paid,
                datetime.date.today().isoformat() if payment > 0 else None,
                status, inst['id']
            ))
            total_principal_paid -= payment

    def add_guarantor(self, loan_id: str, member_id: str,
                      amount_minor: int, guarantee_type: str = 'secured') -> str:
        self.require_permission('manage_guarantors')
        guarantor = self.db.fetch_one('''
            SELECT m.*,
                   (SELECT SUM(guarantee_amount_minor) FROM guarantors
                    WHERE member_id = m.id AND is_active = 1) as existing_guarantees
            FROM members m WHERE m.id = ?
        ''', (member_id,))
        if not guarantor:
            raise ValueError("Guarantor not found")
        max_guarantee = (guarantor['monthly_income'] or 0) * 12
        existing = guarantor['existing_guarantees'] or 0
        if (existing + amount_minor) > max_guarantee:
            raise ValueError("Guarantor has insufficient capacity")
        guar_id = str(uuid.uuid4())
        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO guarantors
                (id, loan_id, member_id, guarantee_amount_minor, guarantee_type, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (guar_id, loan_id, member_id, amount_minor, guarantee_type, self.device_id, 'pending'))
            cursor.execute(
                "UPDATE loans SET guarantors_count = guarantors_count + 1 WHERE id = ?",
                (loan_id,)
            )
        self.log_audit('ADD_GUARANTOR', 'guarantors', guar_id, 'CREATE')
        return guar_id

    def add_collateral(self, loan_id: str, data: dict) -> str:
        self.require_permission('manage_collateral')
        coll_id = str(uuid.uuid4())
        with self.db.transaction() as cursor:
            cursor.execute('''
                INSERT INTO collateral
                (id, loan_id, member_id, collateral_type, description,
                 registration_number, serial_number, make_model, year_of_manufacture,
                 condition, location, ownership_type, owner_name, owner_id_number,
                 estimated_value_minor, forced_sale_value_minor, valuation_date,
                 valuer_name, valuer_license_number, insurance_required,
                 insurance_company, insurance_policy_no, insurance_coverage_minor,
                 insurance_expiry, document_path, photos_paths, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                coll_id, loan_id, data.get('member_id'), data.get('collateral_type'),
                data.get('description'), data.get('registration_number'),
                data.get('serial_number'), data.get('make_model'),
                data.get('year_of_manufacture'), data.get('condition'),
                data.get('location'), data.get('ownership_type'),
                data.get('owner_name'), data.get('owner_id_number'),
                data.get('estimated_value_minor'), data.get('forced_sale_value_minor'),
                data.get('valuation_date'), data.get('valuer_name'),
                data.get('valuer_license_number'), data.get('insurance_required', 0),
                data.get('insurance_company'), data.get('insurance_policy_no'),
                data.get('insurance_coverage_minor'), data.get('insurance_expiry'),
                data.get('document_path'), json.dumps(data.get('photos_paths', [])),
                self.device_id, 'pending'
            ))
            cursor.execute(
                "UPDATE loans SET collateral_value_minor = collateral_value_minor + ? WHERE id = ?",
                (data.get('estimated_value_minor', 0), loan_id)
            )
        self.log_audit('ADD_COLLATERAL', 'collateral', coll_id, 'CREATE')
        return coll_id

    def reschedule_loan(self, loan_id: str, new_term: int,
                        new_rate: float = None, reason: str = None) -> str:
        self.require_permission('reschedule_loan')
        loan = self.db.fetch_one("SELECT * FROM loans WHERE id = ?", (loan_id,))
        if not loan:
            raise ValueError("Loan not found")
        new_loan_id = str(uuid.uuid4())
        new_loan_no = self._generate_loan_no()
        outstanding = ((loan['outstanding_principal_minor'] or 0) +
                       (loan['outstanding_interest_minor'] or 0))
        with self.db.transaction() as cursor:
            cursor.execute('''
                UPDATE loans SET status = 'rescheduled', is_rescheduled = 1,
                updated_at = ? WHERE id = ?
            ''', (datetime.datetime.now().isoformat(), loan_id))
            cursor.execute('''
                INSERT INTO loans
                (id, loan_no, member_id, principal_amount_minor, interest_rate,
                 term_months, rescheduled_from_loan_id, reschedule_count,
                 status, created_by, device_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_loan_id, new_loan_no, loan['member_id'], outstanding,
                new_rate or loan['interest_rate'], new_term, loan_id,
                (loan['reschedule_count'] or 0) + 1, 'active',
                self.current_user, self.device_id, 'pending'
            ))
            self._generate_schedule(
                cursor, new_loan_id, outstanding,
                new_rate or loan['interest_rate'], new_term
            )
        self.log_audit('LOAN_RESCHEDULE', 'loans', new_loan_id, 'CREATE',
                       new_vals={'old_loan': loan_id, 'new_term': new_term, 'reason': reason})
        return new_loan_id

    def get_loan_portfolio(self, filters: dict = None) -> List[dict]:
        query = '''
            SELECT l.*, m.first_name, m.last_name, m.member_no, m.phone,
                   p.product_name, b.name as branch_name
            FROM loans l
            JOIN members m ON l.member_id = m.id
            LEFT JOIN products p ON l.product_id = p.id
            LEFT JOIN branches b ON l.branch_id = b.id
            WHERE l.deleted_at IS NULL
        '''
        params = []
        if filters:
            if filters.get('status'):
                query += " AND l.status = ?"
                params.append(filters['status'])
            if filters.get('branch_id'):
                query += " AND l.branch_id = ?"
                params.append(filters['branch_id'])
        query += " ORDER BY l.created_at DESC"
        rows = self.db.fetch_all(query, tuple(params))
        return [dict(row) for row in rows]

    def calculate_par(self, as_of_date: str = None) -> dict:
        if not as_of_date:
            as_of_date = datetime.date.today().isoformat()
        rows = self.db.fetch_all('''
            SELECT
                SUM(CASE WHEN days_in_arrears = 0 THEN outstanding_principal_minor ELSE 0 END) as current_,
                SUM(CASE WHEN days_in_arrears BETWEEN 1 AND 30 THEN outstanding_principal_minor ELSE 0 END) as par_30,
                SUM(CASE WHEN days_in_arrears BETWEEN 31 AND 60 THEN outstanding_principal_minor ELSE 0 END) as par_60,
                SUM(CASE WHEN days_in_arrears BETWEEN 61 AND 90 THEN outstanding_principal_minor ELSE 0 END) as par_90,
                SUM(CASE WHEN days_in_arrears > 90 THEN outstanding_principal_minor ELSE 0 END) as par_90_plus,
                SUM(outstanding_principal_minor) as total,
                COUNT(CASE WHEN days_in_arrears > 0 THEN 1 END) as accounts_in_arrears,
                COUNT(*) as total_accounts
            FROM loans WHERE status = 'active' AND deleted_at IS NULL
        ''')
        if not rows or not rows[0]['total']:
            return {
                'current': 0, 'par_1_30': 0, 'par_31_60': 0, 'par_61_90': 0,
                'par_90_plus': 0, 'total': 0, 'par_ratio': 0,
                'accounts_in_arrears': 0, 'total_accounts': 0
            }
        row = rows[0]
        total = row['total'] or 1
        at_risk = sum([
            row['par_30'] or 0, row['par_60'] or 0,
            row['par_90'] or 0, row['par_90_plus'] or 0
        ])
        return {
            'current': row['current_'] or 0,
            'par_1_30': row['par_30'] or 0,
            'par_31_60': row['par_60'] or 0,
            'par_61_90': row['par_90'] or 0,
            'par_90_plus': row['par_90_plus'] or 0,
            'total': total,
            'par_ratio': (at_risk / total) * 100,
            'at_risk_amount': at_risk,
            'accounts_in_arrears': row['accounts_in_arrears'] or 0,
            'total_accounts': row['total_accounts'] or 0
        }

    def get_loan_dashboard_metrics(self) -> dict:
        metrics = {}
        metrics['portfolio'] = self.calculate_par()
        month_start = datetime.date.today().replace(day=1).isoformat()
        result = self.db.fetch_one(
            "SELECT COUNT(*) as c, SUM(principal_amount_minor) as total FROM loans WHERE date(application_date) >= ?",
            (month_start,)
        )
        metrics['new_applications'] = {
            'count': result['c'] if result else 0,
            'amount': (result['total'] or 0) / 100
        }
        result = self.db.fetch_one(
            "SELECT COUNT(*) as c, SUM(disbursed_amount_minor) as total FROM loans WHERE date(disbursement_date) >= ?",
            (month_start,)
        )
        metrics['disbursements'] = {
            'count': result['c'] if result else 0,
            'amount': (result['total'] or 0) / 100
        }
        return metrics


class ReportService(BaseService):
    """Comprehensive reporting service"""

    def get_trial_balance(self, as_of_date: str = None, branch_id: str = None) -> List[dict]:
        if not as_of_date:
            as_of_date = datetime.date.today().isoformat()
        query = '''
            SELECT coa.account_code, coa.account_name, coa.account_type,
                   COALESCE(SUM(gle.debit_minor), 0) as total_debits,
                   COALESCE(SUM(gle.credit_minor), 0) as total_credits,
                   COALESCE(SUM(gle.debit_minor - gle.credit_minor), 0) as balance
            FROM chart_of_accounts coa
            LEFT JOIN gl_entries gle ON coa.id = gle.account_id
                AND date(gle.entry_date) <= ?
            WHERE coa.is_active = 1 AND coa.deleted_at IS NULL
        '''
        params = [as_of_date]
        if branch_id:
            query += " AND gle.branch_id = ?"
            params.append(branch_id)
        query += " GROUP BY coa.id ORDER BY coa.account_code"
        rows = self.db.fetch_all(query, tuple(params))
        return [dict(row) for row in rows]

    def get_balance_sheet(self, as_of_date: str = None) -> dict:
        if not as_of_date:
            as_of_date = datetime.date.today().isoformat()

        def fetch_total(account_type, operation):
            r = self.db.fetch_one(f'''
                SELECT COALESCE(SUM(gle.{operation}), 0) as total
                FROM gl_entries gle
                JOIN chart_of_accounts coa ON gle.account_id = coa.id
                WHERE coa.account_type = ? AND date(gle.entry_date) <= ?
            ''', (account_type, as_of_date))
            return r['total'] if r else 0

        assets = fetch_total('asset', 'debit_minor - gle.credit_minor')
        liabilities = fetch_total('liability', 'credit_minor - gle.debit_minor')
        equity = fetch_total('equity', 'credit_minor - gle.debit_minor')
        return {
            'assets': assets, 'liabilities': liabilities, 'equity': equity,
            'net_worth': assets - liabilities, 'as_of_date': as_of_date
        }

    def get_income_statement(self, start_date: str, end_date: str) -> dict:
        income = self.db.fetch_one('''
            SELECT COALESCE(SUM(gle.credit_minor - gle.debit_minor), 0) as total
            FROM gl_entries gle
            JOIN chart_of_accounts coa ON gle.account_id = coa.id
            WHERE coa.account_type = 'income' AND date(gle.entry_date) BETWEEN ? AND ?
        ''', (start_date, end_date))
        expenses = self.db.fetch_one('''
            SELECT COALESCE(SUM(gle.debit_minor - gle.credit_minor), 0) as total
            FROM gl_entries gle
            JOIN chart_of_accounts coa ON gle.account_id = coa.id
            WHERE coa.account_type = 'expense' AND date(gle.entry_date) BETWEEN ? AND ?
        ''', (start_date, end_date))
        inc = income['total'] or 0
        exp = expenses['total'] or 0
        net = inc - exp
        return {
            'income': inc, 'expenses': exp, 'net_income': net,
            'profit_margin': (net / (inc or 1)) * 100,
            'period': f"{start_date} to {end_date}"
        }

    def get_loan_aging_report(self) -> List[dict]:
        rows = self.db.fetch_all('''
            SELECT l.loan_no, m.member_no,
                   m.first_name || ' ' || m.last_name as member_name, m.phone,
                   l.principal_amount_minor, l.outstanding_principal_minor,
                   l.outstanding_interest_minor, l.days_in_arrears,
                   l.next_payment_date,
                   CASE
                       WHEN l.days_in_arrears = 0 THEN 'Current'
                       WHEN l.days_in_arrears <= 30 THEN '1-30 days'
                       WHEN l.days_in_arrears <= 60 THEN '31-60 days'
                       WHEN l.days_in_arrears <= 90 THEN '61-90 days'
                       ELSE '90+ days'
                   END as aging_bucket, p.product_name
            FROM loans l
            JOIN members m ON l.member_id = m.id
            LEFT JOIN products p ON l.product_id = p.id
            WHERE l.status = 'active' AND l.deleted_at IS NULL
            ORDER BY l.days_in_arrears DESC
        ''')
        return [dict(row) for row in rows]

    def get_staff_performance_report(self, start_date: str, end_date: str) -> List[dict]:
        rows = self.db.fetch_all('''
            SELECT u.full_name, u.role,
                   COUNT(DISTINCT m.id) as members_created,
                   COUNT(DISTINCT l.id) as loans_created,
                   SUM(l.principal_amount_minor) as loan_amount,
                   COUNT(DISTINCT t.id) as transactions_processed
            FROM users u
            LEFT JOIN members m ON m.created_by = u.id AND date(m.created_at) BETWEEN ? AND ?
            LEFT JOIN loans l ON l.created_by = u.id AND date(l.created_at) BETWEEN ? AND ?
            LEFT JOIN transactions t ON t.teller_id = u.id AND date(t.transaction_date) BETWEEN ? AND ?
            WHERE u.is_active = 1 GROUP BY u.id ORDER BY loan_amount DESC
        ''', (start_date, end_date, start_date, end_date, start_date, end_date))
        return [dict(row) for row in rows]


class SyncService(BaseService):
    """Advanced synchronization service"""

    def export_pending_changes(self, batch_size: int = 1000) -> dict:
        changes = self.db.fetch_all('''
            SELECT * FROM change_log WHERE sync_status = 'pending'
            ORDER BY priority ASC, changed_at ASC LIMIT ?
        ''', (batch_size,))
        grouped = defaultdict(list)
        for row in changes:
            change_dict = dict(row)
            for field in ['old_data', 'new_data']:
                if change_dict.get(field):
                    try:
                        change_dict[field] = json.loads(change_dict[field])
                    except Exception:
                        pass
            grouped[change_dict['table_name']].append(change_dict)
        return {
            'export_id': str(uuid.uuid4()),
            'device_id': self.device_id,
            'exported_at': datetime.datetime.now().isoformat(),
            'batch_size': len(changes),
            'changes_by_table': dict(grouped),
            'total_tables': len(grouped)
        }

    def import_sync_response(self, response_data: dict) -> dict:
        results = {'synced': 0, 'failed': 0, 'conflicts': 0, 'errors': []}
        with self.db.transaction() as cursor:
            for record in response_data.get('synced_ids', []):
                try:
                    table = record.get('table')
                    record_id = record.get('id')
                    server_version = record.get('server_version')
                    cursor.execute(f'''
                        UPDATE {table} SET sync_status = 'synced',
                        version = ?, updated_at = ? WHERE id = ?
                    ''', (server_version, datetime.datetime.now().isoformat(), record_id))
                    cursor.execute('''
                        UPDATE change_log SET sync_status = 'synced'
                        WHERE table_name = ? AND record_id = ?
                    ''', (table, record_id))
                    results['synced'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(str(e))
            for conflict in response_data.get('conflicts', []):
                self._handle_conflict(cursor, conflict)
                results['conflicts'] += 1
        return results

    def _handle_conflict(self, cursor, conflict: dict):
        table = conflict.get('table')
        record_id = conflict.get('id')
        if conflict.get('severity') == 'critical':
            cursor.execute('''
                UPDATE change_log SET sync_status = 'conflict', sync_error = ?
                WHERE table_name = ? AND record_id = ?
            ''', (json.dumps(conflict), table, record_id))
        else:
            cursor.execute(
                f"UPDATE {table} SET sync_status = 'synced' WHERE id = ?",
                (record_id,)
            )

    def get_sync_stats(self) -> dict:
        pending = self.db.fetch_one('''
            SELECT COUNT(*) as c,
                   SUM(CASE WHEN priority <= 3 THEN 1 ELSE 0 END) as urgent
            FROM change_log WHERE sync_status = 'pending'
        ''')
        by_table = self.db.fetch_all('''
            SELECT table_name, COUNT(*) as c FROM change_log
            WHERE sync_status = 'pending' GROUP BY table_name
        ''')
        return {
            'pending_total': pending['c'] if pending else 0,
            'urgent_pending': pending['urgent'] if pending else 0,
            'by_table': {r['table_name']: r['c'] for r in by_table},
            'last_sync': self._get_last_sync_time()
        }

    def _get_last_sync_time(self) -> Optional[str]:
        result = self.db.fetch_one(
            "SELECT MAX(changed_at) as last_sync FROM change_log WHERE sync_status = 'synced'"
        )
        return result['last_sync'] if result else None

    def verify_integrity(self) -> dict:
        results = {
            'hash_chain_valid': True, 'balance_mismatches': [],
            'orphaned_records': [], 'duplicate_refs': []
        }
        accounts = self.db.fetch_all("SELECT id FROM accounts WHERE deleted_at IS NULL")
        for acc in accounts:
            txs = self.db.fetch_all('''
                SELECT id, prev_hash, tx_hash, posted_date FROM transactions
                WHERE account_id = ? ORDER BY posted_date
            ''', (acc['id'],))
            prev_hash = "0" * 64
            for tx in txs:
                if tx['prev_hash'] != prev_hash:
                    results['hash_chain_valid'] = False
                    results['orphaned_records'].append({
                        'account': acc['id'], 'transaction': tx['id']
                    })
                prev_hash = tx['tx_hash']

        mismatches = self.db.fetch_all('''
            SELECT a.id, a.account_no, a.balance_minor,
                   COALESCE(SUM(CASE
                       WHEN t.transaction_type IN ('deposit', 'loan_disbursement', 'interest', 'dividend')
                       THEN t.amount_minor ELSE -t.amount_minor
                   END), 0) as calculated_balance
            FROM accounts a
            LEFT JOIN transactions t ON a.id = t.account_id
                AND t.deleted_at IS NULL AND t.is_reversed = 0
            WHERE a.deleted_at IS NULL GROUP BY a.id
            HAVING ABS(a.balance_minor - calculated_balance) > 1
        ''')
        results['balance_mismatches'] = [dict(m) for m in mismatches]
        return results



class AIAssistantService(BaseService):
    """
    Full-featured SACCO AI assistant.
    40+ intents, live DB queries, role-aware, learns from conversations.
    """

    # ── Ordered intent patterns (first match wins) ───────────────────────────
    INTENT_MAP = [
        # Greetings / social
        ('greeting',             ['hello', 'hi ', 'hey ', 'good morning', 'good afternoon',
                                  'good evening', 'howdy', 'habari', 'jambo']),
        ('thanks',               ['thank you', 'thanks', 'asante', 'appreciate', 'great job',
                                  'awesome', 'perfect', 'excellent']),
        ('complaint',            ['complaint', 'problem', 'issue', 'not working', 'wrong',
                                  'bad service', 'disappointed', 'frustrated']),
        ('help',                 ['help', 'what can you do', 'commands', 'features',
                                  'how do i', 'assist me', 'guide me']),
        # Account / balance
        ('my_balance',           ['my balance', 'how much in my account', 'account balance',
                                  'check balance', 'savings balance', 'what do i have',
                                  'how much do i have']),
        ('account_details',      ['my account', 'account number', 'account type',
                                  'account no', 'account details', 'account info']),
        # Transactions
        ('my_transactions',      ['my transactions', 'transaction history', 'recent transactions',
                                  'what did i pay', 'what did i deposit', 'statement',
                                  'payment history', 'activity']),
        ('deposit_query',        ['how do i deposit', 'how to deposit', 'depositing',
                                  'deposit minimum', 'add money', 'top up']),
        ('withdraw_query',       ['how do i withdraw', 'how to withdraw', 'cash out',
                                  'can i withdraw', 'take money', 'withdrawal limit']),
        # Loans - member
        ('my_loans',             ['my loan', 'my loans', 'loan balance', 'loan status',
                                  'how much do i owe', 'outstanding loan', 'active loan']),
        ('next_payment',         ['next payment', 'when do i pay', 'due date',
                                  'payment due', 'installment', 'when is my payment']),
        ('loan_eligibility',     ['am i eligible', 'can i get a loan', 'qualify for loan',
                                  'loan eligibility', 'how much can i borrow', 'borrow limit']),
        ('loan_apply',           ['apply for loan', 'get a loan', 'request loan',
                                  'loan application', 'i want a loan', 'need a loan']),
        ('loan_interest',        ['loan interest', 'interest rate', 'how much interest',
                                  'cost of loan', 'rate of loan']),
        ('loan_products',        ['loan products', 'types of loan', 'what loans',
                                  'loan types', 'available loans', 'loan options']),
        ('repayment_schedule',   ['repayment schedule', 'amortization', 'payment schedule',
                                  'monthly installment', 'my schedule']),
        ('early_repayment',      ['pay early', 'early repayment', 'pay off loan',
                                  'settle loan', 'clear my loan', 'full settlement']),
        # Investments - member
        ('my_investments',       ['my investment', 'my investments', 'investment portfolio',
                                  'fixed deposit', 'unit trust', 'how much invested',
                                  'my shares']),
        ('investment_returns',   ['investment return', 'interest on investment',
                                  'earning from invest', 'how much will i earn',
                                  'expected return', 'maturity amount']),
        ('investment_products',  ['investment products', 'where to invest', 'investment options',
                                  'returns available', 'yields', 'what investment']),
        ('savings_interest',     ['savings interest', 'interest on savings',
                                  'how much earn savings', 'savings rate']),
        # EMI calculator
        ('calculate_emi',        ['calculate', 'emi', 'monthly payment', 'per month',
                                  'loan calculator', 'compute loan', 'what would i pay']),
        # Staff - portfolio
        ('portfolio_summary',    ['portfolio', 'loan portfolio', 'total loans', 'all loans',
                                  'portfolio summary']),
        ('par_ratio',            ['par', 'portfolio at risk', 'non performing',
                                  'bad loans', 'overdue ratio', 'arrears rate']),
        ('member_count',         ['how many members', 'member count', 'total members',
                                  'number of members', 'active members', 'membership total']),
        ('savings_total',        ['total savings', 'total deposits', 'savings portfolio',
                                  'how much savings', 'deposit total']),
        ('income_summary',       ['income', 'revenue', 'interest income',
                                  'fees collected', 'profit', 'earnings this month']),
        ('top_borrowers',        ['top borrowers', 'biggest loans', 'largest loans',
                                  'who has most loans', 'high value loans']),
        ('new_members',          ['new members', 'recently joined', 'joined this month',
                                  'new registrations', 'latest members']),
        ('overdue_summary',      ['overdue', 'arrears', 'defaulters', 'who hasnt paid',
                                  'missed payments', 'late loans']),
        # SACCO knowledge
        ('sacco_info',           ['about sacco', 'what is hela', 'about hela', 'sacco info',
                                  'about us', 'who are you']),
        ('products_info',        ['products', 'services offered', 'what do you offer',
                                  'our products', 'product list', 'what services']),
        ('charges_fees',         ['charges', 'fees', 'how much does it cost', 'penalty',
                                  'processing fee', 'joining fee', 'cost']),
        ('office_hours',         ['office hours', 'when are you open', 'contact',
                                  'phone number', 'email', 'location', 'address']),
        ('regulations',          ['sasra', 'regulated', 'license', 'insured', 'kdic',
                                  'compliance', 'audit', 'supervision']),
        ('kyc_info',             ['kyc', 'know your customer', 'verification',
                                  'documents needed', 'identity', 'id required']),
    ]

    def __init__(self, db, crypto):
        super().__init__(db, crypto)

    def process_query(self, query, context=None):
        """Main entry — detect intent, run handler, save to learning DB."""
        context = context or {}
        q = query.lower().strip()
        intent = self._detect_intent(q)

        # Auto-enrich context with member data
        if not context.get('member_id') and context.get('user_id'):
            row = self.db.fetch_one(
                "SELECT member_id, role FROM users WHERE id=?",
                (context['user_id'],))
            if row:
                context['member_id'] = row.get('member_id')
                context['role'] = row.get('role', 'member')

        role = context.get('role', 'member')

        try:
            response = self._dispatch(intent, q, context, role)
        except Exception as e:
            Logger.warning('AI dispatch error: %s', e)
            response = self._fallback()

        # Save for learning
        try:
            self.db.execute(
                "INSERT INTO chatbot_conversations "
                "(id, user_id, member_id, query, response, intent_detected, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), context.get('user_id'),
                 context.get('member_id'), query,
                 response.get('message', ''), intent,
                 datetime.datetime.now().isoformat()))
        except Exception:
            pass

        return response

    def _detect_intent(self, q):
        for intent, keywords in self.INTENT_MAP:
            for kw in keywords:
                if kw in q:
                    return intent
        return 'unknown'

    def _dispatch(self, intent, q, ctx, role):
        # Member personal data
        personal = {
            'my_balance':         lambda: self._my_balance(ctx),
            'account_details':    lambda: self._account_details(ctx),
            'my_transactions':    lambda: self._my_transactions(ctx),
            'my_loans':           lambda: self._my_loans(ctx),
            'next_payment':       lambda: self._next_payment(ctx),
            'loan_eligibility':   lambda: self._loan_eligibility(ctx),
            'repayment_schedule': lambda: self._repayment_schedule(ctx),
            'my_investments':     lambda: self._my_investments(ctx),
            'investment_returns': lambda: self._investment_returns(ctx),
            'savings_interest':   lambda: self._savings_interest(ctx),
            'calculate_emi':      lambda: self._calculate_emi(q),
        }
        # Staff only
        staff_only = {
            'portfolio_summary':  lambda: self._portfolio_summary(),
            'par_ratio':          lambda: self._par_ratio(),
            'member_count':       lambda: self._member_count(),
            'savings_total':      lambda: self._savings_total(),
            'income_summary':     lambda: self._income_summary(),
            'top_borrowers':      lambda: self._top_borrowers(),
            'new_members':        lambda: self._new_members(),
            'overdue_summary':    lambda: self._overdue_summary(),
        }
        # Knowledge base (all users)
        knowledge = {
            'loan_apply':         'loan_apply',
            'loan_interest':      'loan_interest',
            'loan_products':      'loan_products',
            'deposit_query':      'deposit_query',
            'withdraw_query':     'withdraw_query',
            'early_repayment':    'early_repayment',
            'investment_products':'investment_products',
            'sacco_info':         'sacco_info',
            'products_info':      'products_info',
            'charges_fees':       'charges_fees',
            'office_hours':       'office_hours',
            'regulations':        'regulations',
            'kyc_info':           'kyc_info',
        }
        # Social
        social = {
            'help':      lambda: self._help(role),
            'greeting':  lambda: self._greeting(ctx),
            'thanks':    lambda: {'message': "You're welcome! \U0001f600 Anything else I can help you with?"},
            'complaint': lambda: self._complaint(),
        }

        if intent in personal:
            return personal[intent]()
        if intent in staff_only:
            if role == 'member':
                return {'message': (
                    "That information is restricted to SACCO staff. "
                    "I can help you with your own account instead!\n\n"
                    "Try: 'my balance', 'my loans', or 'help'"
                )}
            return staff_only[intent]()
        if intent in knowledge:
            return self._info(knowledge[intent])
        if intent in social:
            return social[intent]()
        return self._learned_or_fallback(q)

    # ── Personal data handlers ───────────────────────────────────────────────

    def _my_balance(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in as a member to check your balance."}
        accs = self.db.fetch_all(
            "SELECT account_no, account_type, balance_minor, status "
            "FROM accounts WHERE member_id=? AND status='active'",
            (ctx['member_id'],))
        if not accs:
            return {'message': "No active accounts found. Visit the SACCO office for assistance."}
        total = sum((a['balance_minor'] or 0) for a in accs) / 100
        lines = ["Your current balances:\n"]
        for a in accs:
            bal = (a['balance_minor'] or 0) / 100
            atype = a['account_type'].replace('_', ' ').title()
            lines.append(f"  {atype} ({a['account_no']}): **KSh {bal:,.2f}**")
        lines.append(f"\nTotal: **KSh {total:,.2f}**")
        return {'message': '\n'.join(lines), 'data': [dict(a) for a in accs]}

    def _account_details(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in to view account details."}
        accs = self.db.fetch_all(
            "SELECT * FROM accounts WHERE member_id=? AND status='active'",
            (ctx['member_id'],))
        if not accs:
            return {'message': "No active accounts found."}
        lines = ["Your account details:\n"]
        for a in accs:
            lines.append(f"  Account No: **{a['account_no']}**")
            lines.append(f"  Type: {a['account_type'].replace('_',' ').title()}")
            lines.append(f"  Balance: KSh {(a['balance_minor'] or 0)/100:,.2f}\n")
        return {'message': '\n'.join(lines)}

    def _my_transactions(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in to view your transactions."}
        rows = self.db.fetch_all(
            "SELECT t.transaction_type, t.amount_minor, t.posted_date, t.reference_no "
            "FROM transactions t JOIN accounts a ON t.account_id=a.id "
            "WHERE a.member_id=? ORDER BY t.posted_date DESC LIMIT 10",
            (ctx['member_id'],))
        if not rows:
            return {'message': "No transactions on your account yet."}
        lines = [f"Your last {len(rows)} transactions:\n"]
        for tx in rows:
            amt = (tx['amount_minor'] or 0) / 100
            sign = '+' if tx['transaction_type'] == 'deposit' else '-'
            date = str(tx['posted_date'] or '')[:10]
            ttype = tx['transaction_type'].replace('_', ' ').title()
            lines.append(f"  {date}  {ttype}: **{sign}KSh {abs(amt):,.2f}**")
        return {'message': '\n'.join(lines), 'data': [dict(r) for r in rows]}

    def _my_loans(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in to view your loans."}
        loans = self.db.fetch_all(
            "SELECT loan_no, status, outstanding_principal_minor, "
            "outstanding_interest_minor, next_payment_date, days_in_arrears "
            "FROM loans WHERE member_id=? "
            "AND status IN ('active','disbursed','overdue','pending')",
            (ctx['member_id'],))
        if not loans:
            return {'message': (
                "You have no active loans.\n\n"
                "You can apply through the Loans section. "
                "Ask 'am I eligible?' to check your limit!"
            )}
        lines = [f"Your loans ({len(loans)} found):\n"]
        for ln in loans:
            principal = (ln['outstanding_principal_minor'] or 0) / 100
            interest = (ln['outstanding_interest_minor'] or 0) / 100
            lines.append(f"  Loan **{ln['loan_no']}** — {(ln['status'] or '').upper()}")
            lines.append(f"    Outstanding: KSh {principal + interest:,.2f}")
            lines.append(f"    Next payment: {ln.get('next_payment_date') or 'Not set'}")
            if ln.get('days_in_arrears'):
                lines.append(f"    Days in arrears: {ln['days_in_arrears']}")
            lines.append("")
        return {'message': '\n'.join(lines), 'data': [dict(l) for l in loans]}

    def _next_payment(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in."}
        row = self.db.fetch_one(
            "SELECT ls.due_date, ls.total_due_minor, l.loan_no "
            "FROM loan_schedules ls JOIN loans l ON ls.loan_id=l.id "
            "WHERE l.member_id=? AND ls.status='pending' "
            "AND ls.due_date>=date('now') ORDER BY ls.due_date LIMIT 1",
            (ctx['member_id'],))
        if not row:
            return {'message': "No upcoming loan payments. You're all caught up!"}
        amt = (row['total_due_minor'] or 0) / 100
        return {'message': (
            f"Your next payment:\n"
            f"  Date: **{row['due_date']}**\n"
            f"  Amount: **KSh {amt:,.2f}**\n"
            f"  Loan: {row['loan_no']}\n\n"
            "You can pay through the Repayment screen."
        )}

    def _loan_eligibility(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Log in to check your eligibility."}
        member = self.db.fetch_one(
            "SELECT kyc_status, membership_date FROM members WHERE id=?",
            (ctx['member_id'],))
        savings = self.db.fetch_one(
            "SELECT COALESCE(SUM(balance_minor),0) as bal FROM accounts "
            "WHERE member_id=? AND account_type='savings'",
            (ctx['member_id'],))
        overdue = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM loans "
            "WHERE member_id=? AND status='overdue'",
            (ctx['member_id'],))
        bal = (savings or {}).get('bal', 0) or 0
        max_loan = bal * 3 / 100
        kyc_ok = (member or {}).get('kyc_status') in ('verified', 'complete')
        has_overdue = ((overdue or {}).get('c') or 0) > 0

        lines = ["Your loan eligibility:\n"]
        lines.append(f"  KYC: {'Complete' if kyc_ok else 'Incomplete — visit the office'}")
        lines.append(f"  Savings Balance: KSh {bal / 100:,.2f}")
        lines.append(f"  Maximum loan (3x savings): **KSh {max_loan:,.2f}**")
        lines.append(f"  Overdue loans: {'None' if not has_overdue else 'Yes — clear first'}")
        if kyc_ok and not has_overdue and bal >= 50000:
            lines.append("\nYou appear eligible to apply!")
        elif not kyc_ok:
            lines.append("\nComplete KYC first before applying.")
        return {'message': '\n'.join(lines)}

    def _repayment_schedule(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in."}
        rows = self.db.fetch_all(
            "SELECT ls.due_date, ls.total_due_minor, ls.status, l.loan_no "
            "FROM loan_schedules ls JOIN loans l ON ls.loan_id=l.id "
            "WHERE l.member_id=? AND ls.status='pending' "
            "ORDER BY ls.due_date LIMIT 6",
            (ctx['member_id'],))
        if not rows:
            return {'message': "No pending repayments. Great job staying current!"}
        lines = ["Upcoming repayments:\n"]
        for r in rows:
            amt = (r['total_due_minor'] or 0) / 100
            lines.append(f"  {r['due_date']}  KSh {amt:,.2f}  ({r['loan_no']})")
        return {'message': '\n'.join(lines)}

    def _my_investments(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in to view your investments."}
        invs = self.db.fetch_all(
            "SELECT * FROM investments WHERE member_id=? AND status='active' "
            "ORDER BY created_at DESC",
            (ctx['member_id'],))
        if not invs:
            return {'message': (
                "You have no active investments yet.\n\n"
                "We offer:\n"
                "  Fixed Deposits (9-13% p.a.)\n"
                "  Unit Trust (~10% p.a.)\n"
                "  Share Capital (KSh 50/share)\n\n"
                "Visit Investments to start growing your money!"
            )}
        total = sum((i['principal_minor'] or 0) for i in invs) / 100
        lines = ["Your active investments:\n"]
        for inv in invs:
            p = (inv['principal_minor'] or 0) / 100
            name = inv.get('name') or inv.get('investment_type', '—')
            lines.append(f"  **{name}**")
            lines.append(f"    Principal: KSh {p:,.2f}")
            lines.append(f"    Rate: {inv.get('interest_rate', 0):.1f}% p.a.")
            lines.append(f"    Matures: {inv.get('maturity_date', '—')}\n")
        lines.append(f"Total invested: **KSh {total:,.2f}**")
        return {'message': '\n'.join(lines)}

    def _investment_returns(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Please log in."}
        invs = self.db.fetch_all(
            "SELECT * FROM investments WHERE member_id=? AND status='active'",
            (ctx['member_id'],))
        if not invs:
            return {'message': "You have no active investments to calculate returns for."}
        lines = ["Estimated returns at maturity:\n"]
        for inv in invs:
            p = (inv['principal_minor'] or 0) / 100
            rate = (inv.get('interest_rate') or 0) / 100
            months = inv.get('term_months') or 12
            earned = p * rate * months / 12
            name = inv.get('name') or inv.get('investment_type', '—')
            lines.append(f"  **{name}**")
            lines.append(f"    Principal: KSh {p:,.2f}")
            lines.append(f"    Interest at maturity: KSh {earned:,.2f}")
            lines.append(f"    Total at maturity: **KSh {p + earned:,.2f}**\n")
        return {'message': '\n'.join(lines)}

    def _savings_interest(self, ctx):
        if not ctx.get('member_id'):
            return {'message': "Log in to see your savings interest."}
        acc = self.db.fetch_one(
            "SELECT balance_minor FROM accounts "
            "WHERE member_id=? AND account_type='savings' AND status='active'",
            (ctx['member_id'],))
        if not acc:
            return {'message': "No savings account found."}
        bal = (acc['balance_minor'] or 0) / 100
        monthly = bal * 0.04 / 12
        return {'message': (
            f"Your savings earn **4% p.a.**\n\n"
            f"  Current Balance: KSh {bal:,.2f}\n"
            f"  Monthly Interest: ~KSh {monthly:,.2f}\n"
            f"  Annual Interest: ~KSh {bal * 0.04:,.2f}\n\n"
            "Interest is credited monthly to your account."
        )}

    def _calculate_emi(self, q):
        amt_m = re.search(r'([\d,]+)', q)
        rate_m = re.search(r'(\d+(?:\.\d+)?)\s*%', q)
        term_m = re.search(r'(\d+)\s*month', q)
        if amt_m and rate_m and term_m:
            P = float(amt_m.group(1).replace(',', ''))
            r_monthly = float(rate_m.group(1)) / 100 / 12
            n = int(term_m.group(1))
            if r_monthly > 0:
                emi = P * r_monthly * (1 + r_monthly)**n / ((1 + r_monthly)**n - 1)
            else:
                emi = P / n
            total = emi * n
            interest = total - P
            return {'message': (
                f"EMI Calculation:\n"
                f"  Loan Amount: KSh {P:,.2f}\n"
                f"  Monthly EMI: **KSh {emi:,.2f}**\n"
                f"  Total Repayable: KSh {total:,.2f}\n"
                f"  Total Interest: KSh {interest:,.2f}\n\n"
                "For detailed schedule, use the Loan Calculator in the menu."
            )}
        return {'message': (
            "I can calculate your EMI! Tell me:\n"
            "  'Calculate EMI for KSh 100,000 at 18% for 24 months'\n\n"
            "Or open the Loan Calculator in Quick Actions."
        )}

    # ── Staff data handlers ──────────────────────────────────────────────────

    def _portfolio_summary(self):
        r = self.db.fetch_one(
            "SELECT COUNT(*) as total_loans, "
            "COALESCE(SUM(outstanding_principal_minor),0) as principal, "
            "COALESCE(SUM(outstanding_interest_minor),0) as interest, "
            "COALESCE(SUM(outstanding_penalties_minor),0) as penalties "
            "FROM loans WHERE status IN ('active','disbursed','overdue')")
        total = ((r['principal'] or 0) + (r['interest'] or 0) + (r['penalties'] or 0)) / 100
        return {'message': (
            f"Loan Portfolio Summary:\n"
            f"  Active Loans: **{r['total_loans']:,}**\n"
            f"  Principal O/S: KSh {(r['principal'] or 0)/100:,.2f}\n"
            f"  Interest O/S: KSh {(r['interest'] or 0)/100:,.2f}\n"
            f"  Penalties: KSh {(r['penalties'] or 0)/100:,.2f}\n"
            f"  Total O/S: **KSh {total:,.2f}**"
        ), 'data': dict(r)}

    def _par_ratio(self):
        total = self.db.fetch_one(
            "SELECT COALESCE(SUM(outstanding_principal_minor),1) as t "
            "FROM loans WHERE status IN ('active','disbursed','overdue')")
        par = self.db.fetch_one(
            "SELECT COALESCE(SUM(outstanding_principal_minor),0) as p "
            "FROM loans WHERE days_in_arrears>0 AND status IN ('active','overdue')")
        par90 = self.db.fetch_one(
            "SELECT COALESCE(SUM(outstanding_principal_minor),0) as p "
            "FROM loans WHERE days_in_arrears>90 AND status IN ('active','overdue')")
        tot = max((total or {}).get('t') or 1, 1)
        p0 = (par or {}).get('p') or 0
        p90 = (par90 or {}).get('p') or 0
        pct = p0 / tot * 100
        pct90 = p90 / tot * 100
        status = "ABOVE SASRA LIMIT - action required!" if pct90 > 5 else "Within SASRA threshold"
        return {'message': (
            f"Portfolio at Risk:\n"
            f"  PAR > 0 days: {pct:.2f}%\n"
            f"  PAR > 90 days: **{pct90:.2f}%**\n"
            f"  SASRA limit: 5.00%\n"
            f"  Status: {status}\n"
            f"  Amount at risk (>90d): KSh {p90/100:,.2f}"
        )}

    def _member_count(self):
        r = self.db.fetch_one(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active, "
            "SUM(CASE WHEN date(membership_date)>=date('now','start of month') THEN 1 ELSE 0 END) as new_month, "
            "SUM(CASE WHEN kyc_status IN ('verified','complete') THEN 1 ELSE 0 END) as kyc_done "
            "FROM members WHERE deleted_at IS NULL")
        return {'message': (
            f"Member Statistics:\n"
            f"  Total Members: **{(r['total'] or 0):,}**\n"
            f"  Active: {(r['active'] or 0):,}\n"
            f"  KYC Completed: {(r['kyc_done'] or 0):,}\n"
            f"  New This Month: {(r['new_month'] or 0):,}"
        ), 'data': dict(r)}

    def _savings_total(self):
        r = self.db.fetch_one(
            "SELECT COALESCE(SUM(balance_minor),0) as total, COUNT(*) as accounts "
            "FROM accounts WHERE account_type='savings' AND status='active'")
        avg = (r['total'] or 0) / max(r['accounts'] or 1, 1)
        return {'message': (
            f"Savings Portfolio:\n"
            f"  Active Accounts: **{(r['accounts'] or 0):,}**\n"
            f"  Total Deposits: **KSh {(r['total'] or 0)/100:,.2f}**\n"
            f"  Average Balance: KSh {avg/100:,.2f}"
        )}

    def _income_summary(self):
        r = self.db.fetch_one(
            "SELECT "
            "COALESCE(SUM(CASE WHEN transaction_type='loan_fee' THEN amount_minor ELSE 0 END),0) as fees, "
            "COALESCE(SUM(CASE WHEN transaction_type='interest_charge' THEN amount_minor ELSE 0 END),0) as interest "
            "FROM transactions WHERE date(posted_date)>=date('now','start of month')")
        fees = (r['fees'] or 0) / 100
        interest = (r['interest'] or 0) / 100
        return {'message': (
            f"Income This Month:\n"
            f"  Loan Processing Fees: KSh {fees:,.2f}\n"
            f"  Interest Collected: KSh {interest:,.2f}\n"
            f"  Total: **KSh {fees + interest:,.2f}**"
        )}

    def _top_borrowers(self):
        rows = self.db.fetch_all(
            "SELECT m.first_name, m.last_name, m.member_no, "
            "SUM(l.outstanding_principal_minor) as total "
            "FROM loans l JOIN members m ON l.member_id=m.id "
            "WHERE l.status IN ('active','disbursed') "
            "GROUP BY l.member_id ORDER BY total DESC LIMIT 5")
        if not rows:
            return {'message': "No active loans to rank."}
        lines = ["Top 5 borrowers by outstanding balance:\n"]
        for i, r in enumerate(rows, 1):
            amt = (r['total'] or 0) / 100
            lines.append(
                f"  {i}. {r['first_name']} {r['last_name']} "
                f"({r['member_no']}) — KSh {amt:,.2f}")
        return {'message': '\n'.join(lines)}

    def _new_members(self):
        rows = self.db.fetch_all(
            "SELECT first_name, last_name, member_no, membership_date "
            "FROM members WHERE date(membership_date)>=date('now','-30 days') "
            "ORDER BY membership_date DESC LIMIT 10")
        if not rows:
            return {'message': "No new members in the last 30 days."}
        lines = [f"{len(rows)} new members (last 30 days):\n"]
        for r in rows:
            lines.append(
                f"  {r['first_name']} {r['last_name']} "
                f"({r['member_no']}) — {r['membership_date']}")
        return {'message': '\n'.join(lines)}

    def _overdue_summary(self):
        r = self.db.fetch_one(
            "SELECT COUNT(*) as cnt, "
            "COALESCE(SUM(outstanding_principal_minor),0) as total "
            "FROM loans WHERE status='overdue' OR days_in_arrears > 0")
        rows = self.db.fetch_all(
            "SELECT m.first_name, m.last_name, m.member_no, "
            "l.loan_no, l.days_in_arrears, l.outstanding_principal_minor "
            "FROM loans l JOIN members m ON l.member_id=m.id "
            "WHERE l.days_in_arrears > 0 "
            "ORDER BY l.days_in_arrears DESC LIMIT 5")
        cnt = (r or {}).get('cnt') or 0
        tot = (r or {}).get('total') or 0
        lines = [f"Overdue Loans Summary:\n  Count: {cnt}\n  Total at risk: KSh {tot/100:,.2f}\n"]
        if rows:
            lines.append("Top overdue:")
            for row in rows:
                lines.append(
                    f"  {row['first_name']} {row['last_name']} ({row['member_no']}) "
                    f"— {row['days_in_arrears']}d overdue — "
                    f"KSh {(row['outstanding_principal_minor'] or 0)/100:,.0f}")
        return {'message': '\n'.join(lines)}

    # ── Knowledge base ───────────────────────────────────────────────────────

    def _info(self, key):
        kb = {
            'loan_apply': (
                "How to apply for a loan:\n\n"
                "1. Tap Loans in the menu\n"
                "2. Select loan type\n"
                "3. Enter amount and term\n"
                "4. Add guarantors if needed (loans > KSh 50,000)\n"
                "5. Submit\n\n"
                "Requirements:\n"
                "  Active member 3+ months\n"
                "  Completed KYC\n"
                "  No outstanding arrears\n"
                "  Max loan = 3x your savings balance"
            ),
            'loan_interest': (
                "Loan interest rates:\n\n"
                "  Normal Loan: 18% p.a. reducing balance\n"
                "  Emergency Loan: 24% p.a. flat rate\n"
                "  Development Loan: 16% p.a. reducing balance\n\n"
                "Late payment penalty: 5% of overdue installment per month\n"
                "Early repayment: No penalty!"
            ),
            'loan_products': (
                "Available loan products:\n\n"
                "  Normal Loan — Up to 3x savings, 18% p.a., max 36 months\n"
                "  Emergency Loan — Up to 1x savings, 24% flat, max 12 months\n"
                "  Development Loan — Business/property, 16% p.a., max 60 months\n\n"
                "Tap Loans to apply!"
            ),
            'deposit_query': (
                "How to deposit funds:\n\n"
                "1. Tap Deposit in Quick Actions\n"
                "2. Select your account\n"
                "3. Enter amount\n"
                "4. Confirm transaction\n\n"
                "Minimum deposit: KSh 500\n"
                "Methods: Cash at office, M-Pesa, bank transfer"
            ),
            'withdraw_query': (
                "How to withdraw savings:\n\n"
                "1. Tap Withdraw in Quick Actions\n"
                "2. Enter amount\n"
                "3. Confirm with PIN\n\n"
                "Note: 2 free withdrawals per month\n"
                "Extra withdrawals: KSh 50 each\n"
                "Minimum balance: KSh 500 must remain"
            ),
            'early_repayment': (
                "Early Loan Repayment:\n\n"
                "No penalty for paying early!\n\n"
                "You only pay outstanding principal + interest accrued to date.\n"
                "This saves you significant money on future interest.\n\n"
                "To repay: Go to Repay, select loan, enter full amount."
            ),
            'investment_products': (
                "Investment options at HELA SACCO:\n\n"
                "  Fixed Deposit\n"
                "    6 months: 9% p.a.\n"
                "    12 months: 11% p.a.\n"
                "    18 months: 12% p.a.\n"
                "    24 months: 13% p.a.\n"
                "    Minimum: KSh 10,000\n\n"
                "  Unit Trust (KIC Money Market Fund)\n"
                "    ~10% p.a., withdraw any time\n"
                "    Minimum: KSh 1,000\n\n"
                "  Share Capital\n"
                "    KSh 50 per share, dividends annually\n"
                "    Minimum 10 shares\n\n"
                "  Government Bonds\n"
                "    CBK issued, 11-15% p.a., 1-10 year terms\n\n"
                "Open Investments to get started!"
            ),
            'sacco_info': (
                "About HELA SMART SACCO:\n\n"
                "We are a licensed Savings and Credit Co-operative Society (SACCO), "
                "regulated by SASRA.\n\n"
                "We offer savings accounts, loans, and investment products "
                "to help members achieve their financial goals.\n\n"
                "Member deposits are insured up to KSh 100,000 by KDIC."
            ),
            'products_info': (
                "HELA SACCO Products:\n\n"
                "  Savings Account — 4% p.a., no monthly fee\n"
                "  Normal Loan — 18% p.a., up to 3x savings\n"
                "  Emergency Loan — 24% flat, quick processing\n"
                "  Development Loan — 16% p.a., long term\n"
                "  Fixed Deposit — 9-13% p.a.\n"
                "  Unit Trust — ~10% p.a.\n"
                "  Share Capital — Dividends annually\n\n"
                "Ask about any product for more details!"
            ),
            'charges_fees': (
                "HELA SACCO Charges:\n\n"
                "  Joining fee: KSh 500 (once only)\n"
                "  Loan processing: 2% of loan amount\n"
                "  Late payment penalty: 5% of overdue per month\n"
                "  Extra withdrawal: KSh 50 (after 2 free/month)\n"
                "  Early repayment: Free\n"
                "  Statement (printed): KSh 100\n"
                "  Statement (in-app): Free"
            ),
            'office_hours': (
                "HELA SACCO Contact:\n\n"
                "  Monday to Friday: 8:00 AM - 5:00 PM\n"
                "  Saturday: 8:00 AM - 12:00 PM\n"
                "  Sunday and holidays: Closed\n\n"
                "  Phone: 0800-HELA-SACCO\n"
                "  Email: info@helasacco.co.ke\n"
                "  Web: www.helasacco.co.ke"
            ),
            'regulations': (
                "HELA SACCO Compliance:\n\n"
                "  Regulator: SASRA\n"
                "  Deposit insurance: KDIC (up to KSh 100,000)\n"
                "  Capital adequacy: min 10% (SASRA requirement)\n"
                "  PAR > 90 limit: max 5% of gross portfolio\n"
                "  Annual audit: Required\n\n"
                "Your money is safe and fully regulated."
            ),
            'kyc_info': (
                "KYC (Know Your Customer) Requirements:\n\n"
                "To complete KYC, visit our office with:\n"
                "  National ID or Passport (original + copy)\n"
                "  Recent passport photo (2 copies)\n"
                "  Proof of address (utility bill, max 3 months old)\n"
                "  Active phone number (for M-Pesa)\n\n"
                "KYC must be completed before applying for any loan.\n"
                "Office hours: Mon-Fri 8am-5pm"
            ),
        }
        return {'message': kb.get(key, "I have information on that but need more details. Please ask specifically!")}

    def _help(self, role):
        if role == 'member':
            msg = (
                "What I can help you with:\n\n"
                "  Account: 'my balance', 'my transactions', 'account details'\n"
                "  Loans: 'my loans', 'next payment', 'am I eligible', 'repayment schedule'\n"
                "  Investments: 'my investments', 'expected returns', 'investment options'\n"
                "  Calculator: 'calculate EMI for KSh 50000 at 18% for 24 months'\n"
                "  SACCO Info: 'loan interest rates', 'how to deposit', 'office hours'\n"
                "  KYC: 'kyc requirements', 'what documents do I need'\n\n"
                "Just type naturally, I understand plain English!"
            )
        else:
            msg = (
                "Staff AI Assistant Menu:\n\n"
                "  Portfolio: 'portfolio summary', 'PAR ratio', 'overdue loans'\n"
                "  Members: 'member count', 'new members', 'top borrowers'\n"
                "  Finance: 'total savings', 'income summary'\n"
                "  Same as members: balance checks, EMI calc, product info\n\n"
                "Type freely — I understand natural language!"
            )
        return {'message': msg}

    def _greeting(self, ctx):
        hour = datetime.datetime.now().hour
        greet = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'
        name = ''
        if ctx.get('member_id'):
            m = self.db.fetch_one(
                "SELECT first_name FROM members WHERE id=?",
                (ctx['member_id'],))
            if m:
                name = f", {m['first_name']}"
        return {'message': (
            f"{greet}{name}! I'm HELA AI, your SACCO assistant.\n\n"
            "I can help with your balance, loans, investments, and SACCO information.\n"
            "Type 'help' to see everything I can do!"
        )}

    def _complaint(self):
        return {'message': (
            "I'm sorry to hear you're having trouble.\n\n"
            "Please contact us directly:\n"
            "  Phone: 0800-HELA-SACCO\n"
            "  Email: info@helasacco.co.ke\n"
            "  Office: Mon-Fri 8am-5pm\n\n"
            "We'll resolve your issue as quickly as possible."
        )}

    def _learned_or_fallback(self, q):
        """Check past conversations for similar Q&A to reuse."""
        try:
            similar = self.db.fetch_all(
                "SELECT query, response FROM chatbot_conversations "
                "WHERE query LIKE ? AND response IS NOT NULL "
                "AND length(response) > 20 "
                "ORDER BY created_at DESC LIMIT 1",
                (f'%{q[:12]}%',))
            if similar:
                prev = similar[0]['response']
                return {
                    'message': prev + '\n\n(Based on a similar previous question)'
                }
        except Exception:
            pass
        return self._fallback()

    def _fallback(self):
        return {'message': (
            "I'm not sure about that. Here are things I can help with:\n\n"
            "  'my balance' — check your account\n"
            "  'my loans' — loan status\n"
            "  'investment products' — where to grow money\n"
            "  'office hours' — contact details\n"
            "  'help' — full list of topics\n\n"
            "Try rephrasing your question!"
        )}

    def generate_financial_insights(self):
        """Generate AI insights shown on the dashboard."""
        insights = []
        try:
            par_data = self.db.fetch_one(
                "SELECT "
                "SUM(CASE WHEN days_in_arrears>90 THEN outstanding_principal_minor ELSE 0 END) as bad, "
                "SUM(outstanding_principal_minor) as total "
                "FROM loans WHERE status IN ('active','overdue')")
            if par_data and (par_data['total'] or 0) > 0:
                bad_ratio = (par_data['bad'] or 0) / (par_data['total'] or 1) * 100
                if bad_ratio > 5:
                    insights.append({
                        'type': 'error', 'icon': 'alert-circle',
                        'message': f'PAR>90 is {bad_ratio:.1f}% — above 5% SASRA limit. Review overdue loans.',
                        'severity': 'high'})
                elif bad_ratio > 2:
                    insights.append({
                        'type': 'warning', 'icon': 'alert',
                        'message': f'PAR>90 at {bad_ratio:.1f}%. Monitor closely.',
                        'severity': 'medium'})

            this_m = self.db.fetch_one(
                "SELECT COALESCE(SUM(amount_minor),0) as amt FROM transactions "
                "WHERE transaction_type='deposit' "
                "AND date(posted_date)>=date('now','start of month')")
            last_m = self.db.fetch_one(
                "SELECT COALESCE(SUM(amount_minor),0) as amt FROM transactions "
                "WHERE transaction_type='deposit' "
                "AND date(posted_date)>=date('now','start of month','-1 month') "
                "AND date(posted_date)<date('now','start of month')")
            tm = (this_m or {}).get('amt') or 0
            lm = (last_m or {}).get('amt') or 0
            if lm > 0:
                change = (tm - lm) / lm * 100
                if change > 10:
                    insights.append({
                        'type': 'success', 'icon': 'trending-up',
                        'message': f'Deposits up {change:.0f}% vs last month.',
                        'severity': 'low'})
                elif change < -10:
                    insights.append({
                        'type': 'warning', 'icon': 'trending-down',
                        'message': f'Deposits down {abs(change):.0f}% vs last month.',
                        'severity': 'medium'})

            new_m = self.db.fetch_one(
                "SELECT COUNT(*) as c FROM members "
                "WHERE date(membership_date)>=date('now','-7 days')")
            if (new_m or {}).get('c', 0) > 0:
                insights.append({
                    'type': 'info', 'icon': 'account-plus',
                    'message': f"{new_m['c']} new member(s) joined this week.",
                    'severity': 'low'})
        except Exception as e:
            Logger.warning('AI insights error: %s', e)
        return insights


# ============================================================================
# INVESTMENT SERVICE — Realistic products, interest accrual, maturity
# ============================================================================

class InvestmentService(BaseService):
    """
    Manages member investments: Fixed Deposits, Unit Trusts, Shares, Bonds.

    Rate schedule (realistic Kenya SACCO rates, 2024-2026):
        fixed_deposit_6m   : 9.0% p.a.
        fixed_deposit_12m  : 11.0% p.a.
        fixed_deposit_18m  : 12.0% p.a.
        fixed_deposit_24m  : 13.0% p.a.
        unit_trust         : 10.0% p.a. (variable, daily accrual)
        shares             : 8.0% p.a. (dividends, paid annually)
        bonds              : 14.0% p.a. (CBK average 2024-26)
    """

    RATE_SCHEDULE = {
        ('fixed_deposit', 6):  9.0,
        ('fixed_deposit', 12): 11.0,
        ('fixed_deposit', 18): 12.0,
        ('fixed_deposit', 24): 13.0,
        ('unit_trust',    0):  10.0,   # 0 = any term
        ('shares',        0):   8.0,
        ('bonds',         12): 12.5,
        ('bonds',         24): 13.5,
        ('bonds',         60): 14.5,
    }

    TYPE_LABELS = {
        'fixed_deposit': 'Fixed Deposit',
        'unit_trust':    'Unit Trust (KIC MMF)',
        'shares':        'Share Capital',
        'bonds':         'Government Bond',
    }

    MIN_AMOUNTS = {
        'fixed_deposit': 1000000,   # KSh 10,000 in minor
        'unit_trust':     100000,   # KSh 1,000
        'shares':          50000,   # KSh 500 (10 shares)
        'bonds':         500000,    # KSh 5,000
    }

    VALID_TERMS = {
        'fixed_deposit': [6, 12, 18, 24],
        'unit_trust':    [0],        # open-ended
        'shares':        [0],        # no maturity
        'bonds':         [12, 24, 60],
    }

    def get_rate(self, inv_type, term_months):
        """Look up interest rate for a product+term combination."""
        # Exact match
        key = (inv_type, term_months)
        if key in self.RATE_SCHEDULE:
            return self.RATE_SCHEDULE[key]
        # Fallback for open-ended products
        key0 = (inv_type, 0)
        if key0 in self.RATE_SCHEDULE:
            return self.RATE_SCHEDULE[key0]
        # Nearest term
        candidates = [(k, v) for k, v in self.RATE_SCHEDULE.items() if k[0] == inv_type]
        if candidates:
            return min(candidates, key=lambda x: abs(x[0][1] - term_months))[1]
        return 0.0

    def create_investment(self, member_id, inv_type, principal_minor,
                          term_months, notes=''):
        """Create a new investment with market-rate interest."""
        if inv_type not in self.TYPE_LABELS:
            raise ValueError(f"Unknown investment type: {inv_type}")
        min_amt = self.MIN_AMOUNTS.get(inv_type, 100000)
        if principal_minor < min_amt:
            raise ValueError(
                f"Minimum investment for {self.TYPE_LABELS[inv_type]} is "
                f"KSh {min_amt/100:,.0f}")

        # Snap to valid term
        valid = self.VALID_TERMS.get(inv_type, [12])
        if 0 in valid:
            term_months = 0  # open-ended
        else:
            term_months = min(valid, key=lambda t: abs(t - term_months))

        rate = self.get_rate(inv_type, term_months)
        start = datetime.date.today()

        if term_months == 0:
            # Open-ended — maturity 100 years away (unit trust / shares)
            maturity = start.replace(year=start.year + 100)
        else:
            mo = start.month + term_months
            yr = start.year + (mo - 1) // 12
            mo = (mo - 1) % 12 + 1
            try:
                maturity = start.replace(year=yr, month=mo)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(yr, mo)[1]
                maturity = start.replace(year=yr, month=mo, day=last_day)

        # Projected interest at maturity
        if term_months == 0:
            projected_interest = 0  # earned ongoing
        else:
            projected_interest = int(principal_minor * rate / 100 * term_months / 12)

        inv_id = str(uuid.uuid4())
        term_label = f"{term_months}mo" if term_months else "Open"
        name = f"{self.TYPE_LABELS[inv_type]} ({term_label})"

        self.db.execute(
            "INSERT INTO investments "
            "(id, member_id, investment_type, name, principal_minor, "
            "interest_rate, term_months, start_date, maturity_date, "
            "status, interest_earned_minor, notes, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (inv_id, member_id, inv_type, name, principal_minor,
             rate, term_months, start.isoformat(), maturity.isoformat(),
             'active', projected_interest, notes,
             self.current_user_id, datetime.datetime.now().isoformat()))

        # Deduct from savings account
        acc = self.db.fetch_one(
            "SELECT id, balance_minor FROM accounts "
            "WHERE member_id=? AND account_type='savings' AND status='active'",
            (member_id,))
        if acc:
            new_bal = (acc['balance_minor'] or 0) - principal_minor
            if new_bal < 0:
                raise ValueError("Insufficient savings balance for this investment")
            self.db.execute(
                "UPDATE accounts SET balance_minor=?, updated_at=? WHERE id=?",
                (new_bal, datetime.datetime.now().isoformat(), acc['id']))
            # Log the deduction transaction
            self.db.execute(
                "INSERT INTO transactions "
                "(id, account_id, transaction_type, amount_minor, "
                "description, posted_date, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), acc['id'], 'investment_purchase',
                 principal_minor,
                 f"Investment: {name}",
                 datetime.date.today().isoformat(),
                 datetime.datetime.now().isoformat()))

        return inv_id

    def accrue_daily_interest(self):
        """Call daily (via scheduler) to credit interest on unit trusts."""
        invs = self.db.fetch_all(
            "SELECT * FROM investments WHERE status='active' "
            "AND investment_type='unit_trust'")
        today = datetime.date.today().isoformat()
        for inv in invs:
            daily_rate = (inv['interest_rate'] or 0) / 100 / 365
            daily_interest = int((inv['principal_minor'] or 0) * daily_rate)
            self.db.execute(
                "UPDATE investments SET interest_earned_minor=interest_earned_minor+?, "
                "updated_at=? WHERE id=?",
                (daily_interest, datetime.datetime.now().isoformat(), inv['id']))

    def check_maturities(self):
        """Mark matured investments and optionally return funds to savings."""
        today = datetime.date.today().isoformat()
        matured = self.db.fetch_all(
            "SELECT * FROM investments WHERE status='active' "
            "AND maturity_date<=? AND term_months>0", (today,))
        for inv in matured:
            self.db.execute(
                "UPDATE investments SET status='matured', updated_at=? WHERE id=?",
                (datetime.datetime.now().isoformat(), inv['id']))
            if inv.get('payout_at_maturity', 1):
                total = (inv['principal_minor'] or 0) + (inv['interest_earned_minor'] or 0)
                acc = self.db.fetch_one(
                    "SELECT id, balance_minor FROM accounts "
                    "WHERE member_id=? AND account_type='savings' AND status='active'",
                    (inv['member_id'],))
                if acc:
                    self.db.execute(
                        "UPDATE accounts SET balance_minor=balance_minor+?, updated_at=? WHERE id=?",
                        (total, datetime.datetime.now().isoformat(), acc['id']))
                    self.db.execute(
                        "INSERT INTO transactions "
                        "(id, account_id, transaction_type, amount_minor, "
                        "description, posted_date, created_at) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (str(uuid.uuid4()), acc['id'], 'investment_maturity',
                         total, f"Matured: {inv['name']}",
                         today, datetime.datetime.now().isoformat()))
                    # Notify member
                    self.db.execute(
                        "INSERT INTO notifications "
                        "(id, member_id, notification_type, title, message, is_read, created_at) "
                        "VALUES (?,?,?,?,?,0,?)",
                        (str(uuid.uuid4()), inv['member_id'], 'system',
                         'Investment Matured',
                         f"Your {inv['name']} has matured. "
                         f"KSh {total/100:,.2f} credited to your savings account.",
                         datetime.datetime.now().isoformat()))
        return len(matured)

    def redeem_early(self, inv_id, reason=''):
        """Early redemption — apply penalty (50% of earned interest forfeited)."""
        inv = self.db.fetch_one(
            "SELECT * FROM investments WHERE id=? AND status='active'", (inv_id,))
        if not inv:
            raise ValueError("Investment not found or already closed")
        if inv['investment_type'] == 'unit_trust':
            # No penalty for unit trust
            payout = (inv['principal_minor'] or 0) + (inv['interest_earned_minor'] or 0)
            penalty = 0
        else:
            # Accrued interest prorated
            start = datetime.date.fromisoformat(inv['start_date'])
            days_held = (datetime.date.today() - start).days
            daily_rate = (inv['interest_rate'] or 0) / 100 / 365
            accrued = int((inv['principal_minor'] or 0) * daily_rate * days_held)
            penalty = accrued // 2  # 50% of accrued interest forfeited
            payout = (inv['principal_minor'] or 0) + accrued - penalty

        self.db.execute(
            "UPDATE investments SET status='redeemed', updated_at=?, "
            "interest_earned_minor=?, notes=? WHERE id=?",
            (datetime.datetime.now().isoformat(), payout - (inv['principal_minor'] or 0),
             f"Early redemption. Penalty: KSh {penalty/100:,.2f}. {reason}",
             inv_id))

        # Credit payout to savings
        acc = self.db.fetch_one(
            "SELECT id FROM accounts WHERE member_id=? AND account_type='savings'",
            (inv['member_id'],))
        if acc:
            self.db.execute(
                "UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?",
                (payout, acc['id']))
            self.db.execute(
                "INSERT INTO transactions "
                "(id, account_id, transaction_type, amount_minor, "
                "description, posted_date, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), acc['id'], 'investment_redemption',
                 payout, f"Early redemption: {inv['name']}",
                 datetime.date.today().isoformat(),
                 datetime.datetime.now().isoformat()))
        return {'payout': payout, 'penalty': penalty}

    def get_member_investments(self, member_id):
        return self.db.fetch_all(
            "SELECT * FROM investments WHERE member_id=? ORDER BY created_at DESC",
            (member_id,))

    def get_all_investments(self):
        return self.db.fetch_all(
            "SELECT i.*, m.first_name, m.last_name, m.member_no "
            "FROM investments i JOIN members m ON i.member_id=m.id "
            "ORDER BY i.created_at DESC")

    def get_summary(self):
        row = self.db.fetch_one(
            "SELECT COUNT(*) as count, "
            "COALESCE(SUM(principal_minor),0) as total_principal, "
            "COALESCE(SUM(interest_earned_minor),0) as total_interest "
            "FROM investments WHERE status='active'")
        return row or {'count': 0, 'total_principal': 0, 'total_interest': 0}

    def get_portfolio_by_type(self):
        """Summary grouped by investment type."""
        return self.db.fetch_all(
            "SELECT investment_type, COUNT(*) as cnt, "
            "SUM(principal_minor) as total_principal, "
            "AVG(interest_rate) as avg_rate "
            "FROM investments WHERE status='active' GROUP BY investment_type")
