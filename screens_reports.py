# screens_reports.py — Reports & Analytics  HELA SMART SACCO v3.1
# FIX: removed MDProgressBar (canvas thread-safety bug) — use card-based bars
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import datetime, threading, csv, os

from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp, sp

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen
from screens_transactions import _fmt


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — all card-based, zero canvas instructions = thread-safe
# ─────────────────────────────────────────────────────────────────────────────

def _bar_row(label, value_text, ratio, color, height=dp(36), label_width=dp(90)):
    ratio = max(min(ratio, 1.0), 0.02)
    row = MDBoxLayout(size_hint_y=None, height=height, spacing=dp(8))
    row.add_widget(MDLabel(
        text=label, font_style='Caption',
        size_hint=(None, None), size=(label_width, height),
        theme_text_color='Secondary', valign='middle'
    ))
    bar_bg = MDCard(size_hint=(1, None), height=dp(16), radius=[dp(8)],
                    md_bg_color=get_color('surface_variant', 0.35), elevation=0)
    bar_fg = MDCard(size_hint=(ratio, 1), radius=[dp(8)],
                    md_bg_color=get_color(color, 0.82), elevation=0)
    bar_bg.add_widget(bar_fg)
    row.add_widget(bar_bg)
    row.add_widget(MDLabel(
        text=value_text, font_style='Caption',
        size_hint=(None, None), size=(dp(80), height),
        theme_text_color='Custom', text_color=get_color(color), valign='middle'
    ))
    return row


def _health_bar(pct, color, height=dp(12)):
    """Safe fill bar — no MDProgressBar, pure MDCard sizing."""
    pct = max(min(pct, 100.0), 0.0)
    outer = MDCard(size_hint=(1, None), height=height, radius=[dp(height / 2)],
                   md_bg_color=get_color('surface_variant', 0.35), elevation=0)
    inner = MDCard(size_hint=(pct / 100, 1), radius=[dp(height / 2)],
                   md_bg_color=get_color(color, 0.9), elevation=0)
    outer.add_widget(inner)
    return outer


def _q1(db, sql, params=()):
    """Fetch single value from first row."""
    try:
        row = db.fetch_one(sql, params)
        if row is None:
            return 0
        return list(row.values())[0] or 0
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
class ReportsScreen(BaseScreen):

    TABS = [
        'Overview', 'Loans', 'Members', 'Savings',
        'Investments', 'Transactions', 'Compliance', 'Cash Flow',
    ]
    TAB_ICONS = [
        'view-dashboard-outline', 'cash-multiple',
        'account-group', 'piggy-bank-outline',
        'trending-up', 'swap-horizontal',
        'shield-check-outline', 'chart-areaspline',
    ]
    TAB_COLORS = [
        'primary', 'quaternary', 'secondary', 'success',
        'tertiary', 'quinary', 'error', 'warning',
    ]
    DATE_FILTERS = [('7d', 7), ('30d', 30), ('90d', 90), ('1yr', 365), ('All', None)]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'reports'
        self._active_tab = 0
        self._date_days = 30
        self._date_filter_btns = {}
        self._tab_btns = []
        self._build()

    # ─── BUILD ───────────────────────────────────────────────────────────────

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Reports & Analytics',
            md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['file-pdf-box', lambda x: self._export_pdf()],
                ['download-outline', lambda x: self._export_current()],
                ['refresh', lambda x: self._reload()],
            ]
        )
        root.add_widget(self.toolbar)

        # Date filter bar
        df_bar = MDBoxLayout(size_hint_y=None, height=dp(40),
                             md_bg_color=get_color('surface_variant', 0.12),
                             padding=[dp(10), dp(5)], spacing=dp(6))
        df_bar.add_widget(MDLabel(text='Period:', font_style='Caption', bold=True,
                                  size_hint=(None, None), size=(dp(46), dp(30)),
                                  theme_text_color='Secondary', valign='middle'))
        for label, days in self.DATE_FILTERS:
            active = (days == self._date_days)
            btn = MDCard(size_hint=(None, None), size=(dp(42), dp(28)), radius=[dp(14)],
                         md_bg_color=get_color('primary') if active else get_color('surface_variant', 0.4),
                         ripple_behavior=True,
                         on_release=lambda x, d=days: self._set_date_filter(d))
            lbl = MDLabel(text=label, halign='center', valign='middle',
                          font_style='Caption', bold=active,
                          theme_text_color='Custom',
                          text_color=(1, 1, 1, 1) if active else get_color('on_surface'))
            btn.add_widget(lbl)
            self._date_filter_btns[days] = (btn, lbl)
            df_bar.add_widget(btn)
        root.add_widget(df_bar)

        # Tab bar
        tab_scroll = MDScrollView(size_hint_y=None, height=dp(60),
                                   do_scroll_x=True, do_scroll_y=False)
        tab_row = MDBoxLayout(size_hint_x=None, height=dp(60),
                               spacing=dp(6), padding=[dp(8), dp(6)])
        tab_row.bind(minimum_width=tab_row.setter('width'))
        for i, (label, icon, color) in enumerate(zip(self.TABS, self.TAB_ICONS, self.TAB_COLORS)):
            active = i == 0
            btn = MDCard(size_hint=(None, None), size=(dp(78), dp(48)), radius=[dp(12)],
                         md_bg_color=get_color(color) if active else get_color('surface_variant', 0.35),
                         ripple_behavior=True, elevation=3 if active else 0,
                         on_release=lambda x, idx=i: self._switch_tab(idx))
            inner = MDBoxLayout(orientation='vertical', spacing=dp(1), padding=[0, dp(4)])
            inner.add_widget(MDIcon(icon=icon, halign='center', font_size=sp(16),
                                     theme_text_color='Custom',
                                     text_color=(1,1,1,1) if active else get_color('outline'),
                                     valign='middle', size_hint_y=None, height=dp(22)))
            inner.add_widget(MDLabel(text=label, font_style='Caption', halign='center',
                                      theme_text_color='Custom',
                                      text_color=(1,1,1,1) if active else get_color('outline'),
                                      valign='middle', size_hint_y=None, height=dp(16),
                                      font_size=sp(9)))
            btn.add_widget(inner)
            self._tab_btns.append((btn, inner, color))
            tab_row.add_widget(btn)
        tab_scroll.add_widget(tab_row)
        root.add_widget(tab_scroll)

        # Content area
        self.content_scroll = MDScrollView(size_hint=(1, 1))
        self.content_box = MDBoxLayout(orientation='vertical', spacing=dp(12),
                                        padding=[dp(12), dp(12), dp(12), dp(30)],
                                        size_hint_y=None)
        self.content_box.bind(minimum_height=self.content_box.setter('height'))
        self.content_scroll.add_widget(self.content_box)
        root.add_widget(self.content_scroll)
        self.add_widget(root)

    # ─── NAV ─────────────────────────────────────────────────────────────────

    def on_enter(self):
        self._switch_tab(0)

    def _reload(self):
        self._switch_tab(self._active_tab)

    def _set_date_filter(self, days):
        self._date_days = days
        for d, (btn, lbl) in self._date_filter_btns.items():
            active = d == days
            btn.md_bg_color = get_color('primary') if active else get_color('surface_variant', 0.4)
            lbl.text_color  = (1,1,1,1) if active else get_color('on_surface')
            lbl.bold = active
        self._switch_tab(self._active_tab)

    def _switch_tab(self, idx):
        self._active_tab = idx
        color = self.TAB_COLORS[idx]
        self.toolbar.md_bg_color = get_color(color)
        for i, (btn, inner, c) in enumerate(self._tab_btns):
            active = i == idx
            btn.md_bg_color = get_color(c) if active else get_color('surface_variant', 0.35)
            btn.elevation   = 3 if active else 0
            for child in inner.children:
                try:
                    child.text_color = (1,1,1,1) if active else get_color('outline')
                except Exception:
                    pass
        self._show_loading()
        threading.Thread(target=self._fetch_data, args=(idx,), daemon=True).start()

    # ─── LOADING / ERROR ─────────────────────────────────────────────────────

    def _show_loading(self):
        self.content_box.clear_widgets()
        loader = MDCard(orientation='vertical', size_hint_y=None, height=dp(90),
                         padding=dp(20), radius=[dp(12)],
                         md_bg_color=get_color('surface_variant', 0.15), elevation=0)
        loader.add_widget(MDLabel(text='Loading data…', halign='center',
                                   theme_text_color='Secondary', font_style='Body2', valign='middle'))
        self.content_box.add_widget(loader)

    def _show_error(self, msg):
        self.content_box.clear_widgets()
        card = MDCard(orientation='horizontal', size_hint_y=None, height=dp(80),
                       padding=dp(16), radius=[dp(12)], spacing=dp(10),
                       md_bg_color=get_color('error_container', 0.2), elevation=0)
        card.add_widget(MDIcon(icon='alert-circle-outline', theme_text_color='Custom',
                                text_color=get_color('error'),
                                size_hint=(None,None), size=(dp(32),dp(32))))
        info = MDBoxLayout(orientation='vertical')
        info.add_widget(MDLabel(text='Could not load report', font_style='Subtitle2', bold=True,
                                 theme_text_color='Custom', text_color=get_color('error'),
                                 size_hint_y=None, height=dp(26), valign='middle'))
        info.add_widget(MDLabel(text=str(msg)[:120], font_style='Caption',
                                 theme_text_color='Secondary', valign='middle'))
        card.add_widget(info)
        self.content_box.add_widget(card)
        self.content_box.add_widget(MDRaisedButton(
            text='Retry', md_bg_color=get_color('error'),
            size_hint_x=None, width=dp(100),
            on_release=lambda x: self._reload()))

    # ─── DATA FETCHERS (background thread) ───────────────────────────────────

    def _date_clause(self, col='posted_date'):
        if self._date_days:
            return f"AND date({col}) >= date('now', '-{self._date_days} days')"
        return ''

    def _fetch_data(self, idx):
        try:
            fetchers = [
                self._fetch_overview, self._fetch_loans,
                self._fetch_members,  self._fetch_savings,
                self._fetch_investments, self._fetch_transactions,
                self._fetch_compliance, self._fetch_cashflow,
            ]
            data = fetchers[idx]()
            Clock.schedule_once(lambda dt: self._build_tab(idx, data), 0)
        except Exception as e:
            Logger.error('Reports fetch tab=%s: %s', idx, e)
            import traceback; traceback.print_exc()
            Clock.schedule_once(lambda dt, _e=str(e): self._show_error(_e), 0)

    def _fetch_overview(self):
        db = self.app.db
        dc  = self._date_clause('membership_date')
        dct = self._date_clause('posted_date')
        par = self.app.loan_service.calculate_par() or {}
        return {
            'members_active': _q1(db,"SELECT COUNT(*) c FROM members WHERE is_active=1"),
            'members_new':    _q1(db,f"SELECT COUNT(*) c FROM members WHERE 1=1 {dc}"),
            'savings':        _q1(db,"SELECT COALESCE(SUM(balance_minor),0) c FROM accounts WHERE account_type='savings' AND status='active'"),
            'loans_count':    _q1(db,"SELECT COUNT(*) c FROM loans WHERE status IN ('active','disbursed','overdue')"),
            'loans_bal':      _q1(db,"SELECT COALESCE(SUM(outstanding_principal_minor),0) c FROM loans WHERE status IN ('active','disbursed','overdue')"),
            'deposits':       _q1(db,f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type='deposit' {dct}"),
            'withdrawals':    _q1(db,f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type='withdrawal' {dct}"),
            'repayments':     _q1(db,f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type IN ('loan_repayment','repayment') {dct}"),
            'investments':    _q1(db,"SELECT COALESCE(SUM(principal_minor),0) c FROM investments WHERE status='active'"),
            'fees':           _q1(db,f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type='loan_fee' {dct}"),
            'par': par,
            'collections_rate': self._calc_collections(db, dct),
            'daily_tx': db.fetch_all(f"SELECT DATE(posted_date) d,SUM(CASE WHEN transaction_type='deposit' THEN amount_minor ELSE 0 END) dep,SUM(CASE WHEN transaction_type='withdrawal' THEN amount_minor ELSE 0 END) wdl FROM transactions WHERE 1=1 {dct} GROUP BY DATE(posted_date) ORDER BY d DESC LIMIT 10"),
            'top_overdue': db.fetch_all("SELECT m.first_name,m.last_name,l.outstanding_principal_minor,l.days_in_arrears FROM loans l JOIN members m ON l.member_id=m.id WHERE l.days_in_arrears>0 ORDER BY l.days_in_arrears DESC LIMIT 5"),
        }

    def _fetch_loans(self):
        db = self.app.db
        return {
            'aging':    self.app.loan_service.get_loan_aging_report(),
            'par':      self.app.loan_service.calculate_par() or {},
            'by_type':  db.fetch_all("SELECT loan_type,COUNT(*) cnt,COALESCE(SUM(outstanding_principal_minor),0) bal FROM loans WHERE status IN ('active','disbursed','overdue') GROUP BY loan_type"),
            'overdue':  db.fetch_all("SELECT m.first_name,m.last_name,m.phone,l.loan_no,l.days_in_arrears,l.outstanding_principal_minor FROM loans l JOIN members m ON l.member_id=m.id WHERE l.status='overdue' ORDER BY l.days_in_arrears DESC LIMIT 15"),
            'portfolio':db.fetch_all("SELECT l.loan_no,l.status,l.outstanding_principal_minor,l.days_in_arrears,m.first_name,m.last_name,l.interest_rate FROM loans l JOIN members m ON l.member_id=m.id WHERE l.status IN ('active','disbursed','overdue') ORDER BY l.outstanding_principal_minor DESC LIMIT 30"),
            'monthly':  db.fetch_all("SELECT strftime('%Y-%m',created_at) m,COUNT(*) cnt,COALESCE(SUM(principal_minor),0) total FROM loans GROUP BY m ORDER BY m DESC LIMIT 6"),
        }

    def _fetch_members(self):
        db = self.app.db
        dc = self._date_clause('membership_date')
        stats = self.app.member_service.get_member_statistics()
        return {
            'stats':        stats,
            'by_kyc':       db.fetch_all("SELECT kyc_status,COUNT(*) c FROM members WHERE is_active=1 GROUP BY kyc_status"),
            'by_gender':    db.fetch_all("SELECT COALESCE(gender,'Unknown') g,COUNT(*) c FROM members WHERE is_active=1 GROUP BY gender"),
            'by_occupation':db.fetch_all("SELECT COALESCE(occupation,'Unspecified') o,COUNT(*) c FROM members WHERE is_active=1 GROUP BY occupation ORDER BY c DESC LIMIT 6"),
            'recent':       db.fetch_all(f"SELECT first_name,last_name,member_no,kyc_status,membership_date,phone FROM members WHERE is_active=1 {dc} ORDER BY membership_date DESC LIMIT 20"),
            'monthly':      db.fetch_all("SELECT strftime('%Y-%m',membership_date) m,COUNT(*) c FROM members WHERE is_active=1 GROUP BY m ORDER BY m DESC LIMIT 8"),
            'dormant':      db.fetch_all("SELECT first_name,last_name,member_no,phone FROM members WHERE is_dormant=1 LIMIT 10"),
            'by_branch':    db.fetch_all("SELECT COALESCE(b.name,'HQ') branch,COUNT(*) c FROM members m LEFT JOIN branches b ON m.branch_id=b.id WHERE m.is_active=1 GROUP BY m.branch_id"),
        }

    def _fetch_savings(self):
        db = self.app.db
        dc = self._date_clause()
        total = db.fetch_one("SELECT COALESCE(SUM(balance_minor),0) s,COUNT(*) c FROM accounts WHERE account_type='savings' AND status='active'") or {}
        brackets = [('< 1K',0,100000),('1-10K',100000,1000000),('10-50K',1000000,5000000),('50-100K',5000000,10000000),('> 100K',10000000,999999999)]
        bdata = [{'label':l,'count':_q1(db,f"SELECT COUNT(*) c FROM accounts WHERE account_type='savings' AND status='active' AND balance_minor BETWEEN {lo} AND {hi}")} for l,lo,hi in brackets]
        return {
            'total':         total,
            'deposits_sum':  db.fetch_one(f"SELECT COALESCE(SUM(amount_minor),0) s FROM transactions WHERE transaction_type='deposit' {dc}") or {},
            'withdrawals_sum':db.fetch_one(f"SELECT COALESCE(SUM(amount_minor),0) s FROM transactions WHERE transaction_type='withdrawal' {dc}") or {},
            'top_savers':    db.fetch_all("SELECT m.first_name,m.last_name,m.member_no,a.balance_minor FROM accounts a JOIN members m ON a.member_id=m.id WHERE a.account_type='savings' AND a.status='active' ORDER BY a.balance_minor DESC LIMIT 10"),
            'monthly_net':   db.fetch_all("SELECT strftime('%Y-%m',posted_date) m,SUM(CASE WHEN transaction_type='deposit' THEN amount_minor ELSE 0 END) dep,SUM(CASE WHEN transaction_type='withdrawal' THEN amount_minor ELSE 0 END) wdl FROM transactions WHERE transaction_type IN ('deposit','withdrawal') GROUP BY m ORDER BY m DESC LIMIT 8"),
            'brackets':      bdata,
            'zero_balance':  _q1(db,"SELECT COUNT(*) c FROM accounts WHERE account_type='savings' AND status='active' AND balance_minor<=0"),
        }

    def _fetch_investments(self):
        db = self.app.db
        summary = db.fetch_one("SELECT COUNT(*) c,COALESCE(SUM(principal_minor),0) principal,COALESCE(SUM(interest_earned_minor),0) interest FROM investments WHERE status='active'") or {}
        return {
            'summary':      summary,
            'by_type':      db.fetch_all("SELECT investment_type,COUNT(*) c,COALESCE(SUM(principal_minor),0) principal,COALESCE(SUM(interest_earned_minor),0) interest,AVG(interest_rate) avg_rate FROM investments WHERE status='active' GROUP BY investment_type"),
            'maturing_soon':db.fetch_all("SELECT i.name,i.principal_minor,i.interest_earned_minor,i.maturity_date,i.interest_rate,m.first_name,m.last_name FROM investments i JOIN members m ON i.member_id=m.id WHERE i.status='active' AND i.term_months>0 AND date(i.maturity_date)<=date('now','+30 days') ORDER BY i.maturity_date LIMIT 10"),
            'recent':       db.fetch_all("SELECT i.name,i.principal_minor,i.interest_rate,i.start_date,i.status,m.first_name,m.last_name FROM investments i JOIN members m ON i.member_id=m.id ORDER BY i.created_at DESC LIMIT 20"),
            'matured_value':_q1(db,"SELECT COALESCE(SUM(principal_minor+interest_earned_minor),0) c FROM investments WHERE status='matured'"),
            'monthly':      db.fetch_all("SELECT strftime('%Y-%m',created_at) m,COUNT(*) cnt,COALESCE(SUM(principal_minor),0) total FROM investments GROUP BY m ORDER BY m DESC LIMIT 6"),
        }

    def _fetch_transactions(self):
        db = self.app.db
        dc = self._date_clause()
        return {
            'daily':  db.fetch_all(f"SELECT DATE(posted_date) d,SUM(CASE WHEN transaction_type='deposit' THEN amount_minor ELSE 0 END) dep,SUM(CASE WHEN transaction_type='withdrawal' THEN amount_minor ELSE 0 END) wdl,COUNT(*) cnt FROM transactions WHERE 1=1 {dc} GROUP BY DATE(posted_date) ORDER BY d DESC LIMIT 14"),
            'by_type':db.fetch_all(f"SELECT transaction_type,COUNT(*) cnt,COALESCE(SUM(amount_minor),0) total FROM transactions WHERE 1=1 {dc} GROUP BY transaction_type ORDER BY total DESC"),
            'recent': db.fetch_all(f"SELECT t.*,m.first_name,m.last_name,a.account_no FROM transactions t JOIN accounts a ON t.account_id=a.id JOIN members m ON a.member_id=m.id WHERE 1=1 {dc} ORDER BY t.posted_date DESC LIMIT 40"),
            'totals': db.fetch_one(f"SELECT COUNT(*) cnt,COALESCE(SUM(amount_minor),0) total FROM transactions WHERE 1=1 {dc}") or {},
            'hourly': db.fetch_all(f"SELECT strftime('%H',posted_date) hr,COUNT(*) cnt FROM transactions WHERE 1=1 {dc} GROUP BY hr ORDER BY hr"),
        }

    def _fetch_compliance(self):
        db = self.app.db
        par          = self.app.loan_service.calculate_par() or {}
        total_savings= _q1(db,"SELECT COALESCE(SUM(balance_minor),0) c FROM accounts WHERE account_type='savings' AND status='active'")
        total_loans  = _q1(db,"SELECT COALESCE(SUM(outstanding_principal_minor),0) c FROM loans WHERE status IN ('active','disbursed','overdue')")
        total_members= _q1(db,"SELECT COUNT(*) c FROM members WHERE is_active=1")
        kyc_done     = _q1(db,"SELECT COUNT(*) c FROM members WHERE kyc_status IN ('verified','complete') AND is_active=1")
        inv_total    = _q1(db,"SELECT COALESCE(SUM(principal_minor),0) c FROM investments WHERE status='active'")
        liquid       = _q1(db,"SELECT COALESCE(SUM(balance_minor),0) c FROM accounts WHERE account_type IN ('current','liquidity') AND status='active'")
        return {
            'par':             par,
            'loan_to_deposit': (total_loans  / max(total_savings,  1)) * 100,
            'kyc_compliance':  (kyc_done     / max(total_members, 1)) * 100,
            'liquidity_ratio': (liquid        / max(total_savings,  1)) * 100,
            'total_assets':    total_savings + total_loans + inv_total,
            'total_savings':   total_savings,
            'total_loans':     total_loans,
            'total_members':   total_members,
            'kyc_done':        kyc_done,
            'overdue_count':   _q1(db,"SELECT COUNT(*) c FROM loans WHERE status='overdue'"),
            'overdue_bal':     _q1(db,"SELECT COALESCE(SUM(outstanding_principal_minor),0) c FROM loans WHERE status='overdue'"),
            'pending_kyc':     db.fetch_all("SELECT first_name,last_name,member_no,membership_date FROM members WHERE kyc_status IN ('incomplete','pending') AND is_active=1 ORDER BY membership_date DESC LIMIT 10"),
            'loan_types':      db.fetch_all("SELECT loan_type,COUNT(*) cnt FROM loans WHERE status IN ('active','disbursed','overdue') GROUP BY loan_type"),
            'write_offs':      _q1(db,"SELECT COUNT(*) c FROM loans WHERE status='written_off'"),
        }

    def _fetch_cashflow(self):
        db = self.app.db
        dc = self._date_clause()
        return {
            'monthly': db.fetch_all("SELECT strftime('%Y-%m',posted_date) m,SUM(CASE WHEN transaction_type='deposit' THEN amount_minor ELSE 0 END) inflow,SUM(CASE WHEN transaction_type='withdrawal' THEN amount_minor ELSE 0 END) outflow,SUM(CASE WHEN transaction_type IN ('loan_repayment','repayment') THEN amount_minor ELSE 0 END) repay,SUM(CASE WHEN transaction_type='loan_fee' THEN amount_minor ELSE 0 END) fees FROM transactions GROUP BY m ORDER BY m DESC LIMIT 10"),
            'weekly':  db.fetch_all(f"SELECT strftime('%Y-W%W',posted_date) wk,SUM(CASE WHEN transaction_type='deposit' THEN amount_minor ELSE 0 END) inflow,SUM(CASE WHEN transaction_type='withdrawal' THEN amount_minor ELSE 0 END) outflow FROM transactions WHERE 1=1 {dc} GROUP BY wk ORDER BY wk DESC LIMIT 8"),
            'income':  _q1(db,f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type='loan_fee' {dc}"),
            'repayments_in': _q1(db,f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type IN ('loan_repayment','repayment') {dc}"),
            'net_period': _q1(db,f"SELECT COALESCE(SUM(CASE WHEN transaction_type='deposit' THEN amount_minor ELSE -amount_minor END),0) c FROM transactions WHERE 1=1 {dc}"),
            'largest_in':  db.fetch_all(f"SELECT t.amount_minor,m.first_name,m.last_name,t.posted_date FROM transactions t JOIN accounts a ON t.account_id=a.id JOIN members m ON a.member_id=m.id WHERE t.transaction_type='deposit' {dc} ORDER BY t.amount_minor DESC LIMIT 5"),
            'largest_out': db.fetch_all(f"SELECT t.amount_minor,m.first_name,m.last_name,t.posted_date FROM transactions t JOIN accounts a ON t.account_id=a.id JOIN members m ON a.member_id=m.id WHERE t.transaction_type='withdrawal' {dc} ORDER BY t.amount_minor DESC LIMIT 5"),
        }

    def _calc_collections(self, db, dc):
        dc2  = dc.replace('posted_date','due_date')
        due  = _q1(db, f"SELECT COALESCE(SUM(total_due_minor),0) c FROM loan_schedules WHERE 1=1 {dc2}")
        paid = _q1(db, f"SELECT COALESCE(SUM(amount_minor),0) c FROM transactions WHERE transaction_type IN ('loan_repayment','repayment') {dc}")
        return (paid / max(due, 1)) * 100

    # ─── TAB BUILDERS (main thread) ──────────────────────────────────────────

    def _build_tab(self, idx, data):
        self.content_box.clear_widgets()
        [self._build_overview, self._build_loans, self._build_members,
         self._build_savings,  self._build_investments, self._build_transactions,
         self._build_compliance, self._build_cashflow][idx](data)

    # ─── OVERVIEW ────────────────────────────────────────────────────────────

    def _build_overview(self, d):
        par    = d['par']
        period = f"Last {self._date_days} days" if self._date_days else "All time"
        self._hdr('Key Performance Indicators', 'view-dashboard', 'primary')

        g = MDGridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(370))
        for icon, val, lbl, color, sub in [
            ('account-group',         str(d['members_active']),              'Active Members',   'primary',    f"+{d['members_new']} new"),
            ('piggy-bank-outline',    _fmt(d['savings']),                    'Total Savings',    'success',    '4% p.a.'),
            ('cash-multiple',         str(d['loans_count']),                 'Active Loans',     'quaternary', _fmt(d['loans_bal'])),
            ('alert-circle-outline',  f"{par.get('par_ratio',0):.1f}%",     'PAR Ratio',        'error' if par.get('par_ratio',0)>5 else 'success','SASRA limit 5%'),
            ('trending-up',           _fmt(d['investments']),               'Investments',      'tertiary',   'Active portfolio'),
            ('clipboard-check-outline',f"{d['collections_rate']:.0f}%",    'Collections Rate', 'success' if d['collections_rate']>=90 else 'warning','Loan repayments'),
        ]:
            g.add_widget(self._kpi(icon, val, lbl, sub, color))
        self.content_box.add_widget(g)

        # Cash flow strip
        self._hdr(f'Cash Flow — {period}', 'chart-bar', 'primary')
        net = d['deposits'] - d['withdrawals']
        cf = MDCard(orientation='horizontal', size_hint_y=None, height=dp(90),
                    padding=dp(12), radius=[dp(12)],
                    md_bg_color=get_color('surface_variant', 0.18), elevation=0)
        for amt, lbl, color in [
            (d['deposits'],   'Deposits',   'success'),
            (d['withdrawals'],'Withdrawals','error'),
            (net,             'Net Flow',   'primary' if net>=0 else 'error'),
            (d['repayments'], 'Repayments', 'quaternary'),
        ]:
            box = MDBoxLayout(orientation='vertical', size_hint_x=0.25)
            box.add_widget(MDLabel(text=_fmt(amt), font_style='Caption', bold=True, halign='center',
                                    theme_text_color='Custom', text_color=get_color(color),
                                    size_hint_y=None, height=dp(26), valign='middle'))
            box.add_widget(MDLabel(text=lbl, font_style='Caption', halign='center',
                                    theme_text_color='Secondary', size_hint_y=None, height=dp(18), valign='middle'))
            cf.add_widget(box)
        self.content_box.add_widget(cf)

        # Daily bar chart
        if d['daily_tx']:
            self._hdr('Daily Deposit Activity', 'chart-line', 'primary')
            max_dep = max((r.get('dep') or 0 for r in d['daily_tx']), default=1) or 1
            for r in reversed(d['daily_tx'][-8:]):
                dep = r.get('dep') or 0
                self.content_box.add_widget(_bar_row(
                    str(r['d'])[5:], _fmt(dep), dep/max_dep, 'success',
                    height=dp(30), label_width=dp(50)))

        # Portfolio health — SAFE card-based bar (no MDProgressBar)
        self._hdr('Loan Portfolio Health', 'heart-pulse', 'quaternary')
        health  = max(0.0, 100.0 - par.get('par_ratio', 0))
        hcolor  = 'success' if health > 90 else 'warning' if health > 75 else 'error'
        hc = MDCard(orientation='vertical', padding=[dp(14),dp(10)], radius=[dp(12)],
                    md_bg_color=get_color('surface_variant',0.2), elevation=0,
                    size_hint_y=None, height=dp(118))
        hc.add_widget(MDLabel(
            text=f"Outstanding: {_fmt(d['loans_bal'])}  •  PAR: {par.get('par_ratio',0):.2f}%",
            font_style='Body2', bold=True, size_hint_y=None, height=dp(26), valign='middle'))
        hc.add_widget(MDLabel(
            text=f"At risk: {_fmt(par.get('at_risk_amount',0))}  •  In arrears: {par.get('accounts_in_arrears',0)} loans",
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(20), valign='middle'))
        hc.add_widget(_health_bar(health, hcolor, height=dp(14)))
        hc.add_widget(MDLabel(
            text=f"Portfolio Health Score: {health:.1f}%",
            font_style='Caption', theme_text_color='Custom', text_color=get_color(hcolor),
            size_hint_y=None, height=dp(22), valign='middle'))
        self.content_box.add_widget(hc)

        # Top overdue
        if d.get('top_overdue'):
            self._hdr('Overdue Alerts', 'alert', 'error')
            for r in d['top_overdue']:
                self.content_box.add_widget(self._alert(
                    f"{r.get('first_name','')} {r.get('last_name','')}",
                    f"{_fmt(r.get('outstanding_principal_minor',0))}  •  {r.get('days_in_arrears',0)}d overdue",
                    'error'))

        # Income summary
        self._hdr('Income Summary', 'cash-register', 'primary')
        ic = MDCard(orientation='horizontal', size_hint_y=None, height=dp(66),
                    padding=dp(14), radius=[dp(12)],
                    md_bg_color=get_color('primary_container',0.2), elevation=0)
        ic.add_widget(MDIcon(icon='bank-outline', theme_text_color='Custom',
                              text_color=get_color('primary'),
                              size_hint=(None,None), size=(dp(34),dp(34))))
        iv = MDBoxLayout(orientation='vertical')
        iv.add_widget(MDLabel(text=f"Fees Collected: {_fmt(d['fees'])}", font_style='Body2',
                               bold=True, size_hint_y=None, height=dp(26), valign='middle'))
        iv.add_widget(MDLabel(text=f"Period: {period}", font_style='Caption',
                               theme_text_color='Secondary', size_hint_y=None, height=dp(20), valign='middle'))
        ic.add_widget(iv)
        self.content_box.add_widget(ic)

    # ─── LOANS ───────────────────────────────────────────────────────────────

    def _build_loans(self, d):
        par = d['par']
        self._hdr('Loan Aging Report', 'clock-outline', 'quaternary')
        aging_def = [('Current (0d)','success'),('1-30 Days','warning'),('31-90 Days','quinary'),('>90 Days NPL','error')]
        g = MDGridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(190))
        for i,(label,color) in enumerate(aging_def):
            bucket = d['aging'][i] if i < len(d['aging']) else {}
            card = MDCard(orientation='vertical', padding=dp(12), radius=[dp(10)],
                          md_bg_color=get_color(f'{color}_container',0.3), elevation=1)
            card.add_widget(MDLabel(text=_fmt(bucket.get('amount',0)), font_style='Subtitle2', bold=True,
                                     halign='center', theme_text_color='Custom', text_color=get_color(color),
                                     size_hint_y=None, height=dp(30), valign='middle'))
            card.add_widget(MDLabel(text=f"{bucket.get('count',0)} loans", font_style='Caption',
                                     halign='center', theme_text_color='Secondary',
                                     size_hint_y=None, height=dp(20), valign='middle'))
            card.add_widget(MDLabel(text=label, font_style='Caption', halign='center',
                                     theme_text_color='Custom', text_color=get_color(color),
                                     size_hint_y=None, height=dp(18), valign='middle'))
            g.add_widget(card)
        self.content_box.add_widget(g)

        # PAR banner with safe bar
        par_pct   = par.get('par_ratio', 0)
        par_color = 'error' if par_pct > 5 else 'success'
        par_card = MDCard(orientation='vertical', size_hint_y=None, height=dp(84),
                          padding=[dp(12),dp(8)], radius=[dp(10)], spacing=dp(4),
                          md_bg_color=get_color(f'{par_color}_container',0.25), elevation=0)
        par_card.add_widget(MDLabel(
            text=f"PAR: {par_pct:.2f}%  —  {'ABOVE' if par_pct>5 else 'Within'} SASRA 5% threshold",
            font_style='Subtitle2', bold=True,
            theme_text_color='Custom', text_color=get_color(par_color),
            size_hint_y=None, height=dp(28), valign='middle'))
        par_card.add_widget(_health_bar(min(par_pct/10*100,100), par_color, height=dp(12)))
        par_card.add_widget(MDLabel(
            text=f"At risk: {_fmt(par.get('at_risk_amount',0))}  •  Accounts in arrears: {par.get('accounts_in_arrears',0)}",
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(22), valign='middle'))
        self.content_box.add_widget(par_card)

        # Monthly disbursements
        if d.get('monthly'):
            self._hdr('Monthly Disbursements', 'chart-timeline', 'quaternary')
            max_v = max((r.get('total') or 0 for r in d['monthly']), default=1) or 1
            for r in reversed(d['monthly']):
                self.content_box.add_widget(_bar_row(
                    r.get('m','')[:7], f"{r.get('cnt',0)}  {_fmt(r.get('total',0))}",
                    (r.get('total') or 0)/max_v, 'quaternary', height=dp(30), label_width=dp(60)))

        # By type
        if d['by_type']:
            self._hdr('Portfolio by Loan Type', 'format-list-bulleted', 'quaternary')
            total_bal = sum((r.get('bal') or 0) for r in d['by_type']) or 1
            colors = ['quaternary','primary','secondary','tertiary','success']
            for i,r in enumerate(d['by_type']):
                pct   = (r.get('bal') or 0) / total_bal
                color = colors[i % len(colors)]
                self.content_box.add_widget(_bar_row(
                    (r.get('loan_type') or 'Other').replace('_',' ')[:14],
                    f"{r.get('cnt',0)}  {pct*100:.0f}%", max(pct,0.02), color))

        # Overdue list
        if d['overdue']:
            self._hdr('Overdue Loans — Action Required', 'alert-octagram', 'error')
            for m in d['overdue']:
                days = m.get('days_in_arrears') or 0
                self.content_box.add_widget(self._alert(
                    f"{m.get('first_name','')} {m.get('last_name','')}  •  {m.get('loan_no','')}",
                    f"Outstanding: {_fmt(m.get('outstanding_principal_minor',0))}  •  {days}d  •  {m.get('phone','')}",
                    'error'))

        # Active portfolio table
        self._hdr('Active Loan Portfolio', 'format-list-text', 'quaternary')
        self._thdr(['Member','Loan No','Outstanding','Rate','Status'],[0.26,0.22,0.22,0.1,0.2],'quaternary')
        for i,loan in enumerate(d['portfolio']):
            sc = 'error' if loan.get('status')=='overdue' else 'warning' if (loan.get('days_in_arrears') or 0)>0 else 'success'
            self._trow([f"{loan.get('first_name','')} {loan.get('last_name','')}",loan.get('loan_no',''),
                        _fmt(loan.get('outstanding_principal_minor',0)),f"{loan.get('interest_rate',0):.1f}%",
                        (loan.get('status') or '').title()],[0.26,0.22,0.22,0.1,0.2],i,status_col=4,status_color=sc)

    # ─── MEMBERS ─────────────────────────────────────────────────────────────

    def _build_members(self, d):
        stats = d['stats']
        self._hdr('Member Statistics', 'account-group', 'secondary')
        g = MDGridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(110))
        for val,lbl,color in [(stats.get('total_active',0),'Active','success'),
                               (stats.get('total_dormant',0),'Dormant','warning'),
                               (stats.get('new_this_month',0),'New (30d)','primary')]:
            g.add_widget(self._mkpi(str(val), lbl, color))
        self.content_box.add_widget(g)

        self._hdr('KYC Compliance', 'check-decagram', 'secondary')
        kyc_c = {'verified':'success','complete':'primary','incomplete':'warning','pending':'error'}
        total_m = sum(r['c'] for r in d['by_kyc']) or 1
        for r in d['by_kyc']:
            status = r.get('kyc_status') or 'pending'
            color  = kyc_c.get(status, 'outline')
            self.content_box.add_widget(_bar_row(
                status.title(), f"{r['c']} ({r['c']/total_m*100:.0f}%)",
                max(r['c']/total_m, 0.02), color))

        if d['by_gender']:
            self._hdr('Gender Distribution', 'gender-male-female', 'secondary')
            gtotal = sum(r['c'] for r in d['by_gender']) or 1
            gbar   = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
            gc     = {'Male':'primary','Female':'secondary','Unknown':'outline'}
            for r in d['by_gender']:
                gname = r.get('g','Unknown')
                color = gc.get(gname,'outline')
                pct   = r['c']/gtotal
                seg   = MDCard(size_hint=(pct,1), radius=[dp(4)],
                               md_bg_color=get_color(color,0.75), elevation=0)
                seg.add_widget(MDLabel(text=f"{gname} {pct*100:.0f}%", font_style='Caption',
                                        halign='center', valign='middle',
                                        theme_text_color='Custom', text_color=(1,1,1,1)))
                gbar.add_widget(seg)
            self.content_box.add_widget(gbar)

        if d['by_occupation']:
            self._hdr('Top Occupations', 'briefcase-outline', 'secondary')
            max_c  = max(r['c'] for r in d['by_occupation']) or 1
            oc     = ['secondary','primary','tertiary','quaternary','success','warning']
            for i,r in enumerate(d['by_occupation']):
                self.content_box.add_widget(_bar_row(
                    (r.get('o') or 'Unspecified')[:16], str(r['c']),
                    r['c']/max_c, oc[i%len(oc)]))

        if d.get('by_branch'):
            self._hdr('Members by Branch', 'office-building-outline', 'secondary')
            max_b = max(r['c'] for r in d['by_branch']) or 1
            for r in d['by_branch']:
                self.content_box.add_widget(_bar_row(
                    (r.get('branch') or 'HQ')[:16], str(r['c']),
                    r['c']/max_b, 'secondary'))

        if d['monthly']:
            self._hdr('Monthly Member Growth', 'chart-line', 'secondary')
            max_c = max(r['c'] for r in d['monthly']) or 1
            for r in reversed(d['monthly']):
                self.content_box.add_widget(_bar_row(
                    r.get('m','')[:7], str(r['c']),
                    r['c']/max_c, 'secondary', height=dp(30), label_width=dp(62)))

        if d.get('dormant'):
            self._hdr('Dormant Members', 'account-clock-outline', 'warning')
            self._thdr(['Name','Member No','Phone'],[0.4,0.3,0.3],'warning')
            for i,m in enumerate(d['dormant']):
                self._trow([f"{m.get('first_name','')} {m.get('last_name','')}",
                             m.get('member_no',''),m.get('phone','')],[0.4,0.3,0.3],i)

        self._hdr('Recent Members', 'account-plus', 'secondary')
        self._thdr(['Name','Member No','Joined','KYC'],[0.32,0.22,0.24,0.22],'secondary')
        for i,m in enumerate(d['recent']):
            kc = kyc_c.get(m.get('kyc_status'),'outline')
            self._trow([f"{m.get('first_name','')} {m.get('last_name','')}",
                        m.get('member_no',''),str(m.get('membership_date',''))[:10],
                        (m.get('kyc_status') or 'pending').title()],
                       [0.32,0.22,0.24,0.22],i,status_col=3,status_color=kc)

    # ─── SAVINGS ─────────────────────────────────────────────────────────────

    def _build_savings(self, d):
        total = d['total']
        self._hdr('Savings Portfolio Overview', 'piggy-bank', 'success')
        g = MDGridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(220))
        for val,lbl,color,sub in [
            (_fmt(total.get('s',0)),'Total Savings','success',f"{total.get('c',0)} accounts"),
            (_fmt(d['deposits_sum'].get('s',0)),'Total Deposits','primary',f"Last {self._date_days or 'all'} days"),
            (_fmt(d['withdrawals_sum'].get('s',0)),'Total Withdrawals','error',f"Last {self._date_days or 'all'} days"),
            (_fmt((total.get('s',0) or 0)//max(total.get('c',1),1)),'Avg Balance','tertiary','Per account'),
        ]:
            g.add_widget(self._kpi('piggy-bank-outline', val, lbl, sub, color))
        self.content_box.add_widget(g)

        zb = d.get('zero_balance', 0)
        if zb > 0:
            self.content_box.add_widget(self._alert(
                f"{zb} accounts with zero balance",
                'These members may be inactive — consider follow-up', 'warning'))

        self._hdr('Balance Distribution', 'chart-histogram', 'success')
        max_c  = max((b.get('count',0) for b in d['brackets']), default=1) or 1
        bcols  = ['error','warning','primary','success','tertiary']
        for i,b in enumerate(d['brackets']):
            self.content_box.add_widget(_bar_row(
                b['label'], str(b['count']), b['count']/max_c,
                bcols[i], label_width=dp(80)))

        if d['monthly_net']:
            self._hdr('Monthly Savings Flow', 'chart-areaspline', 'success')
            all_v  = [(r.get('dep') or 0) for r in d['monthly_net']]+[(r.get('wdl') or 0) for r in d['monthly_net']]
            max_v  = max(all_v, default=1) or 1
            for r in reversed(d['monthly_net']):
                dep = r.get('dep') or 0
                wdl = r.get('wdl') or 0
                net = dep - wdl
                m_row = MDBoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
                m_row.add_widget(MDLabel(text=r.get('m','')[:7], font_style='Caption',
                                          size_hint=(None,None), size=(dp(58),dp(52)),
                                          theme_text_color='Secondary', valign='middle'))
                bars = MDBoxLayout(orientation='vertical', spacing=dp(2))
                for val, color in [(dep,'success'),(wdl,'error')]:
                    bg = MDCard(size_hint=(1,None), height=dp(10), radius=[dp(5)],
                                md_bg_color=get_color('surface_variant',0.3), elevation=0)
                    fg = MDCard(size_hint=(max(val/max_v,0.02),1), radius=[dp(5)],
                                md_bg_color=get_color(color,0.8), elevation=0)
                    bg.add_widget(fg); bars.add_widget(bg)
                m_row.add_widget(bars)
                nc = 'success' if net>=0 else 'error'
                m_row.add_widget(MDLabel(text=_fmt(net), font_style='Caption',
                                          size_hint=(None,None), size=(dp(80),dp(52)),
                                          theme_text_color='Custom', text_color=get_color(nc), valign='middle'))
                self.content_box.add_widget(m_row)

        self._hdr('Top 10 Savers', 'trophy-outline', 'success')
        self._thdr(['Rank','Member','Member No','Balance'],[0.1,0.38,0.25,0.27],'success')
        for i,s in enumerate(d['top_savers']):
            self._trow([str(i+1), f"{s.get('first_name','')} {s.get('last_name','')}",
                        s.get('member_no',''), _fmt(s.get('balance_minor',0))],
                       [0.1,0.38,0.25,0.27], i)

    # ─── INVESTMENTS ─────────────────────────────────────────────────────────

    def _build_investments(self, d):
        summary = d['summary']
        self._hdr('Investment Portfolio', 'trending-up', 'tertiary')
        g = MDGridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(170))
        for val,lbl,color in [
            (str(summary.get('c',0)),'Active Investments','tertiary'),
            (_fmt(summary.get('principal',0)),'Total Principal','primary'),
            (_fmt(summary.get('interest',0)),'Interest Earned','success'),
            (_fmt((summary.get('principal',0) or 0)+(summary.get('interest',0) or 0)),'Total Value','quaternary'),
        ]:
            g.add_widget(self._mkpi(val, lbl, color))
        self.content_box.add_widget(g)

        mv = d.get('matured_value', 0)
        if mv > 0:
            self.content_box.add_widget(self._alert(
                f'Matured portfolio: {_fmt(mv)}',
                'Total principal + interest already paid out to members', 'success'))

        if d.get('monthly'):
            self._hdr('Monthly Investment Activity', 'chart-timeline', 'tertiary')
            max_v = max((r.get('total') or 0 for r in d['monthly']), default=1) or 1
            for r in reversed(d['monthly']):
                self.content_box.add_widget(_bar_row(
                    r.get('m','')[:7], f"{r.get('cnt',0)} new  {_fmt(r.get('total',0))}",
                    (r.get('total') or 0)/max_v, 'tertiary', height=dp(30), label_width=dp(62)))

        if d['by_type']:
            self._hdr('By Investment Type', 'chart-donut', 'tertiary')
            tc = {'fixed_deposit':'primary','unit_trust':'secondary','shares':'tertiary','bonds':'quaternary'}
            tl = {'fixed_deposit':'Fixed Deposit','unit_trust':'Unit Trust','shares':'Share Capital','bonds':'Gov. Bond'}
            total_p = sum((r.get('principal') or 0) for r in d['by_type']) or 1
            for r in d['by_type']:
                itype = r.get('investment_type','')
                color = tc.get(itype,'primary')
                pct   = (r.get('principal') or 0) / total_p
                card  = MDCard(orientation='horizontal', size_hint_y=None, height=dp(64),
                               padding=[dp(12),dp(8)], spacing=dp(10), radius=[dp(10)],
                               md_bg_color=get_color(f'{color}_container',0.2), elevation=0)
                pct_c = MDCard(size_hint=(None,None), size=(dp(44),dp(44)),
                               radius=[dp(10)], md_bg_color=get_color(f'{color}_container',0.5))
                pct_c.add_widget(MDLabel(text=f"{pct*100:.0f}%", halign='center', valign='middle',
                                          font_style='Caption', bold=True,
                                          theme_text_color='Custom', text_color=get_color(color)))
                card.add_widget(pct_c)
                info = MDBoxLayout(orientation='vertical')
                info.add_widget(MDLabel(text=tl.get(itype,itype), font_style='Subtitle2',
                                         size_hint_y=None, height=dp(22), valign='middle'))
                info.add_widget(MDLabel(
                    text=f"{r.get('c',0)} inv  •  {_fmt(r.get('principal',0))}  •  Avg {(r.get('avg_rate') or 0):.1f}%",
                    font_style='Caption', theme_text_color='Secondary',
                    size_hint_y=None, height=dp(18), valign='middle'))
                card.add_widget(info)
                self.content_box.add_widget(card)

        if d['maturing_soon']:
            self._hdr('Maturing Within 30 Days', 'clock-alert-outline', 'warning')
            for m in d['maturing_soon']:
                payout = (m.get('principal_minor') or 0)+(m.get('interest_earned_minor') or 0)
                self.content_box.add_widget(self._alert(
                    f"{m.get('first_name','')} {m.get('last_name','')}  —  {m.get('name','')}",
                    f"Matures: {m.get('maturity_date','')}  •  Payout: {_fmt(payout)}",
                    'warning'))

        self._hdr('Recent Investments', 'history', 'tertiary')
        self._thdr(['Investor','Product','Principal','Rate','Status'],[0.24,0.22,0.22,0.14,0.18],'tertiary')
        sc = {'active':'success','matured':'primary','redeemed':'warning','cancelled':'error'}
        for i,r in enumerate(d['recent']):
            self._trow([f"{r.get('first_name','')} {r.get('last_name','')}",
                        (r.get('name','') or '')[:18],
                        _fmt(r.get('principal_minor',0)),
                        f"{r.get('interest_rate',0):.1f}%",
                        (r.get('status') or '').title()],
                       [0.24,0.22,0.22,0.14,0.18],i,status_col=4,
                       status_color=sc.get(r.get('status',''),'outline'))

    # ─── TRANSACTIONS ─────────────────────────────────────────────────────────

    def _build_transactions(self, d):
        totals = d['totals']
        period = f"Last {self._date_days} days" if self._date_days else "All time"
        self._hdr(f'Transaction Summary — {period}', 'swap-horizontal', 'quinary')

        g = MDGridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(120))
        g.add_widget(self._mkpi(str(totals.get('cnt',0)), 'Total Transactions', 'quinary'))
        g.add_widget(self._mkpi(_fmt(totals.get('total',0)), 'Total Volume', 'primary'))
        self.content_box.add_widget(g)

        if d['by_type']:
            self._hdr('Volume by Transaction Type', 'format-list-bulleted', 'quinary')
            tc = {'deposit':'success','withdrawal':'error','transfer':'secondary',
                  'loan_disbursement':'quaternary','loan_repayment':'primary',
                  'repayment':'primary','loan_fee':'warning'}
            max_v = max((r.get('total') or 0) for r in d['by_type']) or 1
            for r in d['by_type']:
                ttype = r.get('transaction_type','')
                color = tc.get(ttype,'outline')
                self.content_box.add_widget(_bar_row(
                    ttype.replace('_',' ').title()[:18],
                    f"{r.get('cnt',0)}  {_fmt(r.get('total',0))}",
                    (r.get('total') or 0)/max_v, color, label_width=dp(110)))

        # Hourly heatmap
        if d.get('hourly'):
            self._hdr('Activity Heatmap (Hour of Day)', 'clock-outline', 'quinary')
            max_h = max(r.get('cnt',0) for r in d['hourly']) or 1
            h_row = MDBoxLayout(size_hint_y=None, height=dp(60), spacing=dp(3))
            for hr in range(24):
                match = next((r for r in d['hourly'] if int(r.get('hr',-1))==hr), None)
                cnt   = match.get('cnt',0) if match else 0
                pct   = cnt / max_h
                col_b = MDBoxLayout(orientation='vertical', size_hint_x=None, width=dp(10))
                col_b.add_widget(MDBoxLayout())
                fill  = MDCard(size_hint=(1, max(pct,0.04)),
                               md_bg_color=get_color('quinary', 0.15+0.7*pct), elevation=0,
                               radius=[dp(2)])
                col_b.add_widget(fill)
                h_row.add_widget(col_b)
            self.content_box.add_widget(h_row)
            self.content_box.add_widget(MDLabel(
                text='12am  3am  6am  9am  12pm  3pm  6pm  9pm  11pm',
                font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(16)))

        self._hdr('Daily Activity', 'calendar-today', 'quinary')
        self._thdr(['Date','Deposits','Withdrawals','Txns'],[0.26,0.28,0.28,0.18],'quinary')
        for i,r in enumerate(d['daily']):
            self._trow([str(r.get('d',''))[:10],_fmt(r.get('dep') or 0),
                        _fmt(r.get('wdl') or 0),str(r.get('cnt',0))],
                       [0.26,0.28,0.28,0.18],i)

        self._hdr('Recent Transactions', 'receipt', 'quinary')
        self._thdr(['Member','Type','Amount','Acct','Date'],[0.24,0.22,0.22,0.16,0.16],'quinary')
        tcm = {'deposit':'success','withdrawal':'error','transfer':'secondary',
               'loan_disbursement':'quaternary','loan_repayment':'primary','repayment':'primary'}
        for i,tx in enumerate(d['recent']):
            ttype = tx.get('transaction_type','')
            self._trow([f"{tx.get('first_name','')} {tx.get('last_name','')}",
                        ttype.replace('_',' ').title(),
                        _fmt(tx.get('amount_minor',0)),
                        tx.get('account_no',''),
                        str(tx.get('posted_date',''))[:10]],
                       [0.24,0.22,0.22,0.16,0.16],i,
                       status_col=1,status_color=tcm.get(ttype,'outline'))

    # ─── COMPLIANCE ──────────────────────────────────────────────────────────

    def _build_compliance(self, d):
        self._hdr('SASRA Regulatory Compliance', 'shield-check', 'error')

        par_ok  = d['par']['par_ratio'] <= 5
        kyc_ok  = d['kyc_compliance'] >= 80
        ldr_ok  = d['loan_to_deposit'] <= 80
        liq_ok  = d['liquidity_ratio'] >= 10
        score   = sum([par_ok, kyc_ok, ldr_ok, liq_ok]) * 25
        s_color = 'success' if score>=75 else 'warning' if score>=50 else 'error'

        score_card = MDCard(orientation='vertical', size_hint_y=None, height=dp(130),
                            padding=[dp(16),dp(12)], radius=[dp(14)],
                            md_bg_color=get_color(f'{s_color}_container',0.25), elevation=2)
        score_card.add_widget(MDLabel(
            text=f"Compliance Score: {score}% — {sum([par_ok,kyc_ok,ldr_ok,liq_ok])}/4 ratios pass",
            font_style='H6', bold=True,
            theme_text_color='Custom', text_color=get_color(s_color),
            size_hint_y=None, height=dp(36), valign='middle'))
        score_card.add_widget(_health_bar(score, s_color, height=dp(16)))
        score_card.add_widget(MDLabel(
            text='Generated: ' + datetime.date.today().isoformat(),
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(22), valign='middle'))
        score_card.add_widget(MDLabel(
            text='Based on SASRA Kenya SACCO Regulations 2020',
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(22), valign='middle'))
        self.content_box.add_widget(score_card)

        self._hdr('Key SASRA Ratios', 'scale-balance', 'error')
        self._thdr(['Ratio','Actual','Limit','Status'],[0.36,0.22,0.22,0.20],'error')
        for i,(lbl,actual,limit,ok) in enumerate([
            ('PAR Ratio',        f"{d['par']['par_ratio']:.2f}%",  '≤ 5%',  par_ok),
            ('KYC Compliance',   f"{d['kyc_compliance']:.1f}%",   '≥ 80%', kyc_ok),
            ('Loan-to-Deposit',  f"{d['loan_to_deposit']:.1f}%",  '≤ 80%', ldr_ok),
            ('Liquidity Ratio',  f"{d['liquidity_ratio']:.1f}%",  '≥ 10%', liq_ok),
        ]):
            self._trow([lbl,actual,limit,'PASS' if ok else 'FAIL'],
                       [0.36,0.22,0.22,0.20],i,
                       status_col=3,status_color='success' if ok else 'error')

        self._hdr('Balance Sheet Snapshot', 'bank-outline', 'error')
        bs = MDCard(orientation='vertical', size_hint_y=None, height=dp(170),
                    padding=[dp(14),dp(8)], radius=[dp(12)],
                    md_bg_color=get_color('surface_variant',0.15), elevation=0)
        for lbl,val,color in [
            ('Total Assets',      _fmt(d['total_assets']),  'primary'),
            ('Total Savings',     _fmt(d['total_savings']), 'success'),
            ('Outstanding Loans', _fmt(d['total_loans']),   'quaternary'),
            ('Overdue Portfolio', _fmt(d['overdue_bal']),   'error'),
        ]:
            row = MDBoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
            row.add_widget(MDLabel(text=lbl, font_style='Body2',
                                    size_hint_x=0.5, valign='middle'))
            row.add_widget(MDLabel(text=val, font_style='Body2', bold=True,
                                    theme_text_color='Custom', text_color=get_color(color),
                                    halign='right', size_hint_x=0.5, valign='middle'))
            bs.add_widget(row)
        self.content_box.add_widget(bs)

        if d.get('pending_kyc'):
            self._hdr(f"Pending KYC ({len(d['pending_kyc'])} members)", 'account-alert', 'warning')
            self._thdr(['Name','Member No','Joined'],[0.4,0.3,0.3],'warning')
            for i,m in enumerate(d['pending_kyc']):
                self._trow([f"{m.get('first_name','')} {m.get('last_name','')}",
                             m.get('member_no',''),str(m.get('membership_date',''))[:10]],
                            [0.4,0.3,0.3],i)

        wo = d.get('write_offs',0)
        if wo > 0:
            self.content_box.add_widget(self._alert(
                f'{wo} loans written off',
                'Must be declared in quarterly SASRA submission', 'error'))

        if d.get('loan_types'):
            self._hdr('Loan Portfolio Diversification', 'chart-scatter-plot', 'error')
            total_lt = sum(r.get('cnt',0) for r in d['loan_types']) or 1
            for r in d['loan_types']:
                pct = r.get('cnt',0)/total_lt
                self.content_box.add_widget(_bar_row(
                    (r.get('loan_type') or 'Other').replace('_',' ')[:16],
                    f"{r.get('cnt',0)} ({pct*100:.0f}%)",
                    max(pct,0.02), 'error'))

    # ─── CASH FLOW ────────────────────────────────────────────────────────────

    def _build_cashflow(self, d):
        period = f"Last {self._date_days} days" if self._date_days else "All time"
        self._hdr(f'Cash Flow Analysis — {period}', 'chart-areaspline', 'warning')

        net = d.get('net_period',0)
        g   = MDGridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(170))
        g.add_widget(self._kpi('cash-plus',    _fmt(d.get('income',0)),           'Fee Income',       period, 'success'))
        g.add_widget(self._kpi('cash-check',   _fmt(d.get('repayments_in',0)),    'Repayments In',    period, 'primary'))
        g.add_widget(self._mkpi(_fmt(net),      'Net Cash Position', 'success' if net>=0 else 'error'))
        g.add_widget(self._mkpi('Positive' if net>=0 else 'Negative', 'Position', 'success' if net>=0 else 'error'))
        self.content_box.add_widget(g)

        if d['monthly']:
            self._hdr('Monthly Cash Flow (Green=In / Red=Out)', 'chart-bar', 'warning')
            all_v  = [(r.get('inflow') or 0) for r in d['monthly']]+[(r.get('outflow') or 0) for r in d['monthly']]
            max_v  = max(all_v, default=1) or 1
            for r in reversed(d['monthly']):
                inflow  = r.get('inflow') or 0
                outflow = r.get('outflow') or 0
                net_m   = inflow - outflow
                m_card = MDCard(orientation='vertical', size_hint_y=None, height=dp(78),
                                padding=[dp(10),dp(6)], radius=[dp(8)],
                                md_bg_color=get_color('surface_variant',0.12), elevation=0, spacing=dp(3))
                hrow = MDBoxLayout(size_hint_y=None, height=dp(20))
                hrow.add_widget(MDLabel(text=r.get('m','')[:7], font_style='Caption', bold=True,
                                         valign='middle', size_hint_x=0.3))
                hrow.add_widget(MDLabel(
                    text=f"In: {_fmt(inflow)}  Out: {_fmt(outflow)}  Net: {_fmt(net_m)}",
                    font_style='Caption', theme_text_color='Secondary', valign='middle', size_hint_x=0.7))
                m_card.add_widget(hrow)
                for val,color in [(inflow,'success'),(outflow,'error')]:
                    bg = MDCard(size_hint=(1,None), height=dp(10), radius=[dp(5)],
                                md_bg_color=get_color('surface_variant',0.3), elevation=0)
                    fg = MDCard(size_hint=(max(val/max_v,0.02),1), radius=[dp(5)],
                                md_bg_color=get_color(color,0.8), elevation=0)
                    bg.add_widget(fg); m_card.add_widget(bg)
                self.content_box.add_widget(m_card)

        if d['weekly']:
            self._hdr('Weekly Inflow Trend', 'calendar-week', 'warning')
            all_w = [(r.get('inflow') or 0) for r in d['weekly']]
            max_w = max(all_w, default=1) or 1
            for r in reversed(d['weekly']):
                inflow = r.get('inflow') or 0
                self.content_box.add_widget(_bar_row(
                    r.get('wk','')[-6:], _fmt(inflow),
                    inflow/max_w, 'warning', height=dp(28), label_width=dp(70)))

        if d.get('largest_in'):
            self._hdr('Largest Deposits', 'arrow-down-circle', 'success')
            self._thdr(['Member','Amount','Date'],[0.4,0.35,0.25],'success')
            for i,r in enumerate(d['largest_in']):
                self._trow([f"{r.get('first_name','')} {r.get('last_name','')}",
                             _fmt(r.get('amount_minor',0)),str(r.get('posted_date',''))[:10]],
                            [0.4,0.35,0.25],i)

        if d.get('largest_out'):
            self._hdr('Largest Withdrawals', 'arrow-up-circle', 'error')
            self._thdr(['Member','Amount','Date'],[0.4,0.35,0.25],'error')
            for i,r in enumerate(d['largest_out']):
                self._trow([f"{r.get('first_name','')} {r.get('last_name','')}",
                             _fmt(r.get('amount_minor',0)),str(r.get('posted_date',''))[:10]],
                            [0.4,0.35,0.25],i)

    # ─── REUSABLE WIDGET HELPERS ─────────────────────────────────────────────

    def _hdr(self, text, icon, color):
        row = MDCard(orientation='horizontal', size_hint_y=None, height=dp(42),
                     radius=[dp(10)], padding=[dp(12),0], spacing=dp(8),
                     md_bg_color=get_color(f'{color}_container',0.28), elevation=0)
        row.add_widget(MDIcon(icon=icon, theme_text_color='Custom',
                               text_color=get_color(color),
                               size_hint=(None,None), size=(dp(26),dp(26)), valign='middle'))
        row.add_widget(MDLabel(text=text, font_style='Subtitle2', bold=True,
                                theme_text_color='Custom', text_color=get_color(color),
                                valign='middle'))
        self.content_box.add_widget(row)

    def _kpi(self, icon, value, label, sub, color):
        card = MDCard(orientation='vertical', padding=[dp(12),dp(10)], radius=[dp(14)],
                      md_bg_color=get_color(f'{color}_container',0.25), elevation=1)
        ic_row = MDBoxLayout(size_hint_y=None, height=dp(30))
        ic_row.add_widget(MDIcon(icon=icon, theme_text_color='Custom',
                                   text_color=get_color(color), font_size=sp(18),
                                   size_hint_x=None, width=dp(26), valign='middle'))
        ic_row.add_widget(MDBoxLayout())
        card.add_widget(ic_row)
        card.add_widget(MDLabel(text=value, font_style='H6', bold=True, halign='left',
                                 theme_text_color='Custom', text_color=get_color(color),
                                 size_hint_y=None, height=dp(30), valign='middle'))
        card.add_widget(MDLabel(text=label, font_style='Caption', halign='left',
                                 theme_text_color='Secondary', size_hint_y=None, height=dp(18), valign='middle'))
        card.add_widget(MDLabel(text=sub, font_style='Caption', halign='left',
                                 theme_text_color='Custom', text_color=get_color(color,0.7),
                                 size_hint_y=None, height=dp(16), valign='middle'))
        return card

    def _mkpi(self, value, label, color):
        card = MDCard(orientation='vertical', padding=dp(12), radius=[dp(12)],
                      md_bg_color=get_color(f'{color}_container',0.25), elevation=1)
        card.add_widget(MDLabel(text=value, font_style='H5', bold=True, halign='center',
                                 theme_text_color='Custom', text_color=get_color(color),
                                 size_hint_y=None, height=dp(38), valign='middle'))
        card.add_widget(MDLabel(text=label, font_style='Caption', halign='center',
                                 theme_text_color='Secondary', size_hint_y=None, height=dp(18), valign='middle'))
        return card

    def _alert(self, title, subtitle, color):
        card = MDCard(orientation='horizontal', size_hint_y=None, height=dp(62),
                      padding=[dp(12),dp(8)], spacing=dp(10), radius=[dp(10)],
                      md_bg_color=get_color(f'{color}_container',0.18), elevation=0)
        icon = 'alert-circle' if color=='error' else 'information' if color=='warning' else 'check-circle'
        card.add_widget(MDIcon(icon=icon, theme_text_color='Custom',
                                text_color=get_color(color),
                                size_hint=(None,None), size=(dp(24),dp(24))))
        info = MDBoxLayout(orientation='vertical')
        info.add_widget(MDLabel(text=title, font_style='Subtitle2',
                                 size_hint_y=None, height=dp(22), valign='middle'))
        info.add_widget(MDLabel(text=subtitle, font_style='Caption',
                                 theme_text_color='Secondary',
                                 size_hint_y=None, height=dp(18), valign='middle'))
        card.add_widget(info)
        return card

    def _thdr(self, cols, widths, color):
        h = MDCard(orientation='horizontal', size_hint_y=None, height=dp(30),
                   md_bg_color=get_color(f'{color}_container',0.3),
                   radius=[dp(6)], padding=[dp(8),0], elevation=0)
        for col,w in zip(cols, widths):
            h.add_widget(MDLabel(text=col, font_style='Caption', bold=True,
                                  theme_text_color='Custom', text_color=get_color(color),
                                  size_hint_x=w, valign='middle'))
        self.content_box.add_widget(h)

    def _trow(self, cells, widths, row_index, status_col=None, status_color='outline'):
        row = MDBoxLayout(size_hint_y=None, height=dp(38),
                          md_bg_color=(1,1,1,0.02) if row_index%2==0 else get_color('surface_variant',0.12),
                          padding=[dp(8),0])
        for i,(text,w) in enumerate(zip(cells, widths)):
            lbl = MDLabel(text=str(text), font_style='Caption', size_hint_x=w, valign='middle')
            if i == status_col:
                lbl.theme_text_color = 'Custom'
                lbl.text_color = get_color(status_color)
                lbl.bold = True
            row.add_widget(lbl)
        self.content_box.add_widget(row)

    # ─── EXPORT ──────────────────────────────────────────────────────────────

    def _export_current(self):
        self.show_info(f'Exporting {self.TABS[self._active_tab]} report…')
        threading.Thread(target=self._do_export, daemon=True).start()

    def _export_pdf(self):
        self.show_info('PDF export — coming soon')

    def _do_export(self):
        try:
            tab  = self.TABS[self._active_tab].lower().replace(' ','_')
            dc   = self._date_clause()
            fname= f"hela_{tab}_{datetime.date.today()}.csv"
            path = os.path.join(self.app.exports_dir, fname)
            qmap = {
                'overview':    f"SELECT t.*,m.first_name,m.last_name FROM transactions t JOIN accounts a ON t.account_id=a.id JOIN members m ON a.member_id=m.id WHERE 1=1 {dc} ORDER BY t.posted_date DESC LIMIT 2000",
                'loans':       "SELECT l.*,m.first_name,m.last_name,m.member_no FROM loans l JOIN members m ON l.member_id=m.id ORDER BY l.created_at DESC LIMIT 2000",
                'members':     "SELECT first_name,last_name,member_no,phone,email,kyc_status,membership_date,gender,occupation FROM members WHERE is_active=1 ORDER BY membership_date DESC",
                'savings':     "SELECT a.account_no,a.balance_minor,m.first_name,m.last_name FROM accounts a JOIN members m ON a.member_id=m.id WHERE a.account_type='savings' ORDER BY a.balance_minor DESC",
                'investments': "SELECT i.*,m.first_name,m.last_name FROM investments i JOIN members m ON i.member_id=m.id ORDER BY i.created_at DESC",
                'transactions':f"SELECT t.*,m.first_name,m.last_name,a.account_no FROM transactions t JOIN accounts a ON t.account_id=a.id JOIN members m ON a.member_id=m.id WHERE 1=1 {dc} ORDER BY t.posted_date DESC LIMIT 5000",
                'compliance':  "SELECT m.member_no,m.first_name,m.last_name,m.kyc_status,m.membership_date FROM members WHERE is_active=1",
                'cash_flow':   f"SELECT transaction_type,SUM(amount_minor) total,COUNT(*) cnt FROM transactions WHERE 1=1 {dc} GROUP BY transaction_type",
            }
            rows = self.app.db.fetch_all(qmap.get(tab, qmap['transactions']))
            if rows:
                with open(path, 'w', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=rows[0].keys())
                    w.writeheader()
                    w.writerows([dict(r) for r in rows])
                Clock.schedule_once(lambda dt: self.show_success(f'Exported {len(rows)} rows → {fname}'), 0)
            else:
                Clock.schedule_once(lambda dt: self.show_info('No data to export'), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(f'Export failed: {_e}'), 0)
