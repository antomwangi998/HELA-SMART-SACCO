# main.py - Application entry point - HELA SMART SACCO v3.0
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import os
import uuid

from kivy.clock import Clock
from kivy.logger import Logger
from kivy.uix.screenmanager import FadeTransition, ScreenManager, SlideTransition

from kivymd.app import MDApp
from kivymd.uix.navigationdrawer import MDNavigationDrawer, MDNavigationLayout
from kivymd.uix.screen import MDScreen
from kivy.metrics import dp

from crypto import AdvancedCryptoManager
from database import AdvancedDatabaseManager

from screens import (
    DashboardScreen, LoginScreen, MemberListScreen, MemberProfileScreen,
    MemberRegistrationScreen, NavigationDrawerContent,
)
from screens_transactions import DepositScreen, WithdrawalScreen, TransferScreen, MobileMoneyWithdrawalScreen
from screens_loans import LoanApplicationScreen, LoanScheduleScreen, RepaymentScreen
from screens_ai import AIAssistantScreen
from screens_reports import ReportsScreen
from screens_investments import InvestmentsScreen
from screens_member import StatementScreen, LoanCalculatorScreen, MyProfileScreen, MemberSettingsScreen
from screens_admin import (
    AuditLogScreen, BranchManagementScreen, KYCApprovalScreen,
    MemberEditScreen, NotificationsScreen, SettingsScreen,
)
from services_mobile_money import MobileMoneyService
try:
    from server import start_server, get_portal_url
    _API_SERVER_AVAILABLE = True
except ImportError:
    _API_SERVER_AVAILABLE = False
from services import (
    AccountService, AIAssistantService, InvestmentService, LoanService,
    MemberService, ReportService, SyncService,
)


class HelaSaccoApp(MDApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = 'HELA SMART SACCO v3.0'
        self.theme_cls.primary_palette = 'Green'
        self.theme_cls.accent_palette = 'Purple'
        self.theme_cls.theme_style = 'Light'

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.exports_dir = os.path.join(self.base_dir, 'exports')
        self.backups_dir = os.path.join(self.base_dir, 'backups')
        self.logs_dir = os.path.join(self.base_dir, 'logs')
        self.temp_dir = os.path.join(self.base_dir, 'temp')
        for d in [self.data_dir, self.exports_dir, self.backups_dir,
                  self.logs_dir, self.temp_dir]:
            os.makedirs(d, exist_ok=True)

        self.device_id = self._get_device_id()
        self.crypto = AdvancedCryptoManager('HELA_SACCO_MASTER_SECRET_v3', self.device_id)
        self.db = AdvancedDatabaseManager(
            os.path.join(self.data_dir, 'hela_sacco_v3.db'), self.crypto
        )

        self.member_service = MemberService(self.db, self.crypto)
        self.account_service = AccountService(self.db, self.crypto)
        self.loan_service = LoanService(self.db, self.crypto)
        self.sync_service = SyncService(self.db, self.crypto)
        self.report_service = ReportService(self.db, self.crypto)
        self.ai_service = AIAssistantService(self.db, self.crypto)
        self.investment_service = InvestmentService(self.db, self.crypto)
        self.mobile_money_service = MobileMoneyService(self.db)

        self.current_user_id = None
        self.current_user_role = None
        self.current_user_name = None
        self.current_branch_id = None

        self.screens_cache = {}
        self.nav_drawer = None
        self.main_sm = None
        self.main_screen = None
        self._nav_stack = []
        self._drawer_content = None
        self._prebuild_queue = []

    def _get_device_id(self):
        fpath = os.path.join(self.data_dir, '.device_id')
        try:
            if os.path.exists(fpath):
                return open(fpath).read().strip()
            did = str(uuid.uuid4())
            open(fpath, 'w').write(did)
            return did
        except Exception:
            return str(uuid.uuid4())

    def build(self):
        self.root_sm = ScreenManager(transition=FadeTransition())
        self.root_sm.add_widget(LoginScreen(app=self))
        self.root_sm.add_widget(MemberRegistrationScreen(app=self))
        return self.root_sm

    # ── Screen build queue (pre-built while user is on login screen) ──────────
    _SCREEN_CLASSES = [
        # Critical first — dashboard loads immediately after login
        'DashboardScreen',
        # Transactions
        'DepositScreen', 'WithdrawalScreen', 'TransferScreen', 'MobileMoneyWithdrawalScreen',
        # Loans
        'LoanApplicationScreen', 'LoanScheduleScreen', 'RepaymentScreen',
        # Member
        'MemberListScreen', 'MemberProfileScreen',
        # Investments + member tools
        'InvestmentsScreen', 'StatementScreen', 'LoanCalculatorScreen', 'MyProfileScreen', 'MemberSettingsScreen',
        # AI
        'AIAssistantScreen',
        # Reports
        'ReportsScreen',
        # Admin
        'NotificationsScreen', 'MemberEditScreen', 'KYCApprovalScreen',
        'SettingsScreen', 'BranchManagementScreen', 'AuditLogScreen',
    ]

    def build_main_screen(self):
        """Called by navigate_to. If pre-build is done this returns instantly.
        If still building (very fast login), finish synchronously."""
        if self.main_screen:
            return
        # Pre-build not done yet — finish remaining screens now
        while self._prebuild_queue:
            self._build_one_screen()
        self._finalize_main_screen()

    def _start_prebuild(self, dt):
        """Begin building screens one-per-frame while user is on login screen."""
        if self.main_screen:
            return
        self.main_sm = ScreenManager(transition=SlideTransition())
        self._prebuild_queue = list(self._SCREEN_CLASSES)
        Clock.schedule_once(self._prebuild_tick, 0)

    def _prebuild_tick(self, dt):
        """Build one screen per frame — keeps UI responsive on login screen."""
        if self._prebuild_queue:
            self._build_one_screen()
            if self._prebuild_queue:
                Clock.schedule_once(self._prebuild_tick, 0)
            else:
                self._finalize_main_screen()

    def _build_one_screen(self):
        name = self._prebuild_queue.pop(0)
        cls_map = {
            'DashboardScreen': DashboardScreen,
            'MemberListScreen': MemberListScreen,
            'MemberProfileScreen': MemberProfileScreen,
            'DepositScreen': DepositScreen,
            'WithdrawalScreen': WithdrawalScreen,
            'TransferScreen': TransferScreen,
            'MobileMoneyWithdrawalScreen': MobileMoneyWithdrawalScreen,
            'LoanApplicationScreen': LoanApplicationScreen,
            'LoanScheduleScreen': LoanScheduleScreen,
            'RepaymentScreen': RepaymentScreen,
            'ReportsScreen': ReportsScreen,
            'AIAssistantScreen': AIAssistantScreen,
            'InvestmentsScreen': InvestmentsScreen,
            'StatementScreen': StatementScreen,
            'LoanCalculatorScreen': LoanCalculatorScreen,
            'MyProfileScreen': MyProfileScreen,
            'MemberSettingsScreen': MemberSettingsScreen,
            'MemberEditScreen': MemberEditScreen,
            'KYCApprovalScreen': KYCApprovalScreen,
            'NotificationsScreen': NotificationsScreen,
            'SettingsScreen': SettingsScreen,
            'BranchManagementScreen': BranchManagementScreen,
            'AuditLogScreen': AuditLogScreen,
        }
        cls = cls_map.get(name)
        if not cls:
            return
        try:
            s = cls(app=self)
            self.main_sm.add_widget(s)
            self.screens_cache[s.name] = s
        except Exception as e:
            Logger.error(f'HelaSacco: failed to build {name}: {e}')

    def _finalize_main_screen(self):
        """Wire up drawer + nav layout. Called once all screens are built."""
        if self.main_screen:
            return
        self._drawer_content = NavigationDrawerContent(app_ref=self)
        self.nav_drawer = MDNavigationDrawer(
            radius=[0, dp(16), dp(16), 0],
            width=dp(290),
            enable_swiping=True,
        )
        self.nav_drawer.add_widget(self._drawer_content)
        nav_layout = MDNavigationLayout()
        nav_layout.add_widget(self.main_sm)
        nav_layout.add_widget(self.nav_drawer)
        self.main_screen = MDScreen(name='main')
        self.main_screen.add_widget(nav_layout)
        self.root_sm.add_widget(self.main_screen)
        Logger.info('HelaSacco: main screen ready (%d screens)', len(self.screens_cache))

    def navigate_to(self, screen_name, **kwargs):
        """Navigate to a screen, saving history for back navigation."""
        self.build_main_screen()

        screen = self.screens_cache.get(screen_name)
        if not screen:
            Logger.warning(f'HelaSacco: screen "{screen_name}" not found')
            # Fallback to dashboard
            screen = self.screens_cache.get('dashboard')
            if not screen:
                return
            screen_name = 'dashboard'

        # Set attributes passed as kwargs (e.g. member_id, loan_id)
        for k, v in kwargs.items():
            try:
                setattr(screen, k, v)
            except Exception:
                pass

        # Save current screen to history stack (not dashboard to avoid loops)
        current = self.main_sm.current if self.main_sm else None
        if current and current != screen_name:
            self._nav_stack.append(current)
            # Cap stack at 20
            if len(self._nav_stack) > 20:
                self._nav_stack = self._nav_stack[-20:]

        self.main_sm.transition.direction = 'left'
        self.main_sm.current = screen_name
        self.root_sm.current = 'main'

    def go_back(self):
        self.navigate_back()

    def navigate_back(self):
        """Navigate to previous screen, or dashboard if no history."""
        if not self.main_sm:
            return
        if self._nav_stack:
            prev = self._nav_stack.pop()
            self.main_sm.transition.direction = 'right'
            self.main_sm.current = prev
        else:
            self.main_sm.transition.direction = 'right'
            self.main_sm.current = 'dashboard'

    def open_drawer(self):
        if self.nav_drawer:
            if self._drawer_content:
                name = self.current_user_name or 'User'
                role = (self.current_user_role or 'member').lower().strip()
                self._drawer_content.name_label.text = name
                self._drawer_content.role_label.text = role.replace('_', ' ').title()
                self._drawer_content.rebuild_for_role(role)
            self.nav_drawer.set_state('open')

    def close_drawer(self):
        if self.nav_drawer:
            self.nav_drawer.set_state('close')

    def logout(self):
        self.current_user_id = None
        self.current_user_role = None
        self.current_user_name = None
        self.current_branch_id = None
        self._nav_stack.clear()
        for svc in [self.member_service, self.account_service,
                    self.loan_service, self.sync_service,
                    self.report_service, self.ai_service]:
            try:
                svc.set_context(None, None, None)
            except Exception:
                pass
        if self.main_sm:
            self.main_sm.current = 'dashboard'
        self.root_sm.current = 'login'

    def on_start(self):
        Logger.info('HelaSacco: App started')
        self._patch_mdlabel_alignment()
        # Build screens incrementally while user is on login screen —
        # by login time they are ready, so navigate_to is instant.
        Clock.schedule_once(self._start_prebuild, 0.3)
        # Start the member web portal + API server in background
        if _API_SERVER_AVAILABLE:
            Clock.schedule_once(lambda dt: start_server(self), 1.0)

    @staticmethod
    def _patch_mdlabel_alignment():
        """
        Kivy's MDLabel defaults to valign='bottom'. This monkey-patch makes
        every label center its text vertically and respects halign correctly.
        Called after KivyMD is fully initialized.
        """
        try:
            from kivymd.uix.label import MDLabel
            _orig_init = MDLabel.__init__

            def _new_init(self, **kwargs):
                # Default vertical alignment to middle
                kwargs.setdefault('valign', 'middle')
                _orig_init(self, **kwargs)
                # Bind text_size so halign (center/right/left) works properly
                def _on_size(inst, val):
                    inst.text_size = (val[0], None)
                self.bind(size=_on_size)
                # Set initial value
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: setattr(
                    self, 'text_size', (self.width, None)
                ), 0)

            MDLabel.__init__ = _new_init
            Logger.info('HelaSacco: MDLabel alignment patch applied')
        except Exception as e:
            Logger.warning(f'HelaSacco: MDLabel patch failed: {e}')

    def get_portal_url(self):
        """Return the local URL for the web portal (shown in settings)."""
        if _API_SERVER_AVAILABLE:
            return get_portal_url()
        return None

    def on_stop(self):
        Logger.info('HelaSacco: App stopped')


if __name__ == '__main__':
    HelaSaccoApp().run()
