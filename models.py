# models.py - HELA SMART SACCO v3.0
# Enumerations and data model definitions

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Roles(Enum):
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    TELLER = "teller"
    SENIOR_TELLER = "senior_teller"
    LOANS_OFFICER = "loans_officer"
    SENIOR_LOANS_OFFICER = "senior_loans_officer"
    MANAGER = "manager"
    BRANCH_MANAGER = "branch_manager"
    AUDITOR = "auditor"
    FIELD_OFFICER = "field_officer"
    CREDIT_ANALYST = "credit_analyst"
    ACCOUNTANT = "accountant"
    MEMBER = "member"
    AGENT = "agent"


class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    LOAN_DISBURSEMENT = "loan_disbursement"
    LOAN_REPAYMENT = "loan_repayment"
    SHARE_PURCHASE = "share_purchase"
    SHARE_SALE = "share_sale"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    PENALTY = "penalty"
    CHARGE = "charge"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"
    STANDING_ORDER = "standing_order"
    BULK_PAYMENT = "bulk_payment"
    MOBILE_MONEY = "mobile_money"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE_DEPOSIT = "cheque_deposit"
    CHEQUE_WITHDRAWAL = "cheque_withdrawal"


class AccountType(Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    FIXED_DEPOSIT = "fixed_deposit"
    SHARE_CAPITAL = "share_capital"
    LOAN = "loan"
    SUSPENSE = "suspense"
    JOINT = "joint"
    CHILDREN_SAVINGS = "children_savings"
    RETIREMENT = "retirement"
    EDUCATION = "education"
    HOLIDAY = "holiday"
    EMERGENCY = "emergency"


class LoanStatus(Enum):
    PENDING = "pending"
    APPRAISAL = "appraisal"
    COMMITTEE = "committee"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISBURSED = "disbursed"
    ACTIVE = "active"
    CLOSED = "closed"
    WRITTEN_OFF = "written_off"
    RESCHEDULED = "rescheduled"
    RESTRUCTURED = "restructured"
    SUSPENDED = "suspended"


class KYCStatus(Enum):
    PENDING = "pending"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNDER_REVIEW = "under_review"


class SyncStatus(Enum):
    PENDING = "pending"
    SYNCED = "synced"
    CONFLICT = "conflict"
    ERROR = "error"
    QUEUED = "queued"
    SYNCING = "syncing"
