# permissions.py - Role-Based Access Control (RBAC)
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from typing import List, Dict
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from models import Roles


class PermissionManager:
    """Comprehensive RBAC with resource-level permissions"""

    PERMISSIONS = {
        Roles.SUPER_ADMIN: {'*': True},

        Roles.ADMIN: {
            '*': True,
            'delete_system_data': False,
            'modify_super_admin': False,
        },

        Roles.MANAGER: {
            'view_dashboard': True, 'view_analytics': True,
            'view_reports': True, 'view_all_branches': True,
            'approve_loans': True, 'approve_large_transactions': True,
            'approve_write_offs': True, 'manage_users': True,
            'manage_branches': True, 'manage_products': True,
            'manage_settings': True, 'view_audit_logs': True,
            'reverse_transactions': True, 'view_all_members': True,
            'export_data': True, 'process_end_of_day': True,
            'process_end_of_month': True, 'process_end_of_year': True,
            'view_gl': True, 'post_journal_entries': True,
            'approve_journal_entries': True, 'view_budget': True,
            'manage_budget': True,
        },

        Roles.BRANCH_MANAGER: {
            'view_dashboard': True, 'view_branch_analytics': True,
            'view_reports': True, 'view_own_branch': True,
            'approve_loans': True, 'approve_medium_transactions': True,
            'manage_branch_users': True, 'view_branch_members': True,
            'export_branch_data': True, 'process_branch_eod': True,
            'view_branch_gl': True, 'post_branch_journal': True,
        },

        Roles.LOANS_OFFICER: {
            'view_dashboard': True, 'view_members': True,
            'view_member': True, 'create_member': True,
            'edit_member': True, 'create_loan': True,
            'appraise_loan': True, 'view_loan_portfolio': True,
            'manage_guarantors': True, 'manage_collateral': True,
            'process_repayments': True, 'view_reports': True,
            'reschedule_loan': True, 'restructure_loan': True,
            'manage_loan_products': False, 'view_credit_scores': True,
        },

        Roles.SENIOR_LOANS_OFFICER: {
            'view_dashboard': True, 'view_members': True,
            'view_member': True, 'create_member': True,
            'edit_member': True, 'create_loan': True,
            'appraise_loan': True, 'approve_small_loans': True,
            'view_loan_portfolio': True, 'manage_guarantors': True,
            'manage_collateral': True, 'process_repayments': True,
            'view_reports': True, 'reschedule_loan': True,
            'restructure_loan': True, 'manage_loan_products': True,
            'view_credit_scores': True, 'write_off_loans': False,
        },

        Roles.TELLER: {
            'view_dashboard': True, 'process_deposits': True,
            'process_withdrawals': True, 'process_transfers': True,
            'view_member': True, 'view_members': True,
            'create_member': True, 'edit_member_basic': True,
            'view_own_till': True, 'close_till': True,
            'print_receipts': True, 'view_transactions': True,
            'process_cheque_deposits': True, 'process_mobile_money': True,
        },

        Roles.SENIOR_TELLER: {
            'view_dashboard': True, 'process_deposits': True,
            'process_withdrawals': True, 'process_transfers': True,
            'process_large_withdrawals': True, 'view_member': True,
            'view_members': True, 'create_member': True,
            'edit_member': True, 'view_all_tills': True,
            'approve_till_reconciliation': True,
            'reverse_same_day_transactions': True,
            'process_cheque_deposits': True,
            'process_cheque_withdrawals': True,
            'process_mobile_money': True, 'process_bank_transfers': True,
        },

        Roles.ACCOUNTANT: {
            'view_dashboard': True, 'view_gl': True,
            'post_journal_entries': True, 'view_trial_balance': True,
            'view_balance_sheet': True, 'view_income_statement': True,
            'manage_chart_of_accounts': True,
            'process_reconciliations': True, 'view_budget': True,
            'manage_budget': True, 'view_audit_logs': True,
            'export_financial_data': True,
        },

        Roles.AUDITOR: {
            'view_dashboard': True, 'view_audit_logs': True,
            'view_all_transactions': True, 'view_all_accounts': True,
            'view_all_loans': True, 'view_reports': True,
            'run_integrity_checks': True, 'view_user_sessions': True,
            'export_audit_data': True, 'view_gl': True,
            'view_system_settings': True, 'view_member': True,
            'view_members': True, 'create_audit_findings': True,
            'track_issue_resolution': True,
        },

        Roles.FIELD_OFFICER: {
            'view_dashboard': True, 'view_assigned_members': True,
            'view_members': True, 'view_member': True,
            'create_member': True, 'edit_member': True,
            'collect_repayments': True, 'process_repayments': True,
            'view_loans': True, 'offline_access': True,
            'register_group': True, 'appraise_loan': True,
            'gps_tracking': True,
        },

        Roles.CREDIT_ANALYST: {
            'view_dashboard': True, 'view_members': True,
            'view_member': True, 'view_credit_reports': True,
            'analyze_creditworthiness': True,
            'recommend_loan_amounts': True,
            'view_financial_statements': True,
            'calculate_debt_ratio': True,
            'generate_credit_memos': True,
        },

        Roles.AGENT: {
            'view_dashboard': True, 'process_deposits': True,
            'process_withdrawals': True, 'process_mobile_money': True,
            'view_member_limited': True, 'register_members': True,
            'collect_repayments': True, 'agent_commission_view': True,
        },

        Roles.MEMBER: {
            'view_own_profile': True, 'view_own_accounts': True,
            'view_own_loans': True, 'view_own_transactions': True,
            'request_services': True, 'update_own_profile': True,
            'change_own_password': True, 'view_own_statements': True,
            'download_own_documents': True, 'make_online_payments': True,
            'contact_support': True,
        },
    }

    @classmethod
    def has_permission(cls, user_role: str, action: str,
                       resource_id: str = None) -> bool:
        """Check if role has permission for action on resource"""
        try:
            role = Roles(user_role)
        except ValueError:
            return False

        perms = cls.PERMISSIONS.get(role, {})
        if perms.get('*', False):
            return True
        return perms.get(action, False)

    @classmethod
    def get_allowed_actions(cls, user_role: str) -> List[str]:
        """Get list of allowed actions for role"""
        try:
            role = Roles(user_role)
        except ValueError:
            return []

        perms = cls.PERMISSIONS.get(role, {})
        if perms.get('*', False):
            return ['*']
        return [action for action, allowed in perms.items() if allowed]

    @classmethod
    def get_role_hierarchy(cls) -> Dict[str, List[str]]:
        """Get role hierarchy for escalation"""
        return {
            'member': ['agent', 'field_officer'],
            'agent': ['teller', 'field_officer'],
            'field_officer': ['loans_officer', 'teller'],
            'teller': ['senior_teller', 'loans_officer'],
            'loans_officer': ['senior_loans_officer', 'branch_manager'],
            'senior_teller': ['branch_manager', 'accountant'],
            'accountant': ['manager', 'auditor'],
            'branch_manager': ['manager'],
            'manager': ['admin'],
            'auditor': ['admin'],
            'admin': ['super_admin'],
        }
