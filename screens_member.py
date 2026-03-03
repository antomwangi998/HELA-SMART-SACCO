# screens_member.py — Member-facing production screens
# Statement Screen + Loan Calculator Screen
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import datetime
import threading

from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, RoundedRectangle

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen


def _fmt(minor):
    return f"KSh {(minor or 0) / 100:,.2f}"


# ============================================================================
# ACCOUNT STATEMENT SCREEN
# ============================================================================

class StatementScreen(BaseScreen):
    """Full account statement — shows transactions, running balance, filters."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'statement'
        self._all_txns = []
        self._account_id = None
        self._build()

    def _build(self):
        from kivy.uix.floatlayout import FloatLayout
        float_root = FloatLayout()
        root = MDBoxLayout(orientation='vertical', size_hint=(1, 1))

        toolbar = MDTopAppBar(
            title='Account Statement',
            elevation=2,
            md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.navigate_back()]],
            right_action_items=[['download', lambda x: self._export()]],
        )
        root.add_widget(toolbar)

        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation='vertical', spacing=dp(10),
            padding=[dp(14), dp(14), dp(14), dp(20)],
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))

        # ── Account summary card ───────────────────────────────────
        self._summary_card = MDCard(
            orientation='horizontal',
            padding=[dp(16), dp(14)], spacing=dp(12),
            radius=[dp(14)], md_bg_color=get_color('primary'),
            size_hint_y=None, height=dp(80), elevation=3
        )
        self._acc_no_lbl = MDLabel(
            text='Account: —', font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(26), valign='middle'
        )
        self._bal_lbl = MDLabel(
            text='Balance: KSh 0.00', font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.8),
            size_hint_y=None, height=dp(20), valign='middle'
        )
        info_col = MDBoxLayout(orientation='vertical', spacing=dp(2))
        info_col.add_widget(self._acc_no_lbl)
        info_col.add_widget(self._bal_lbl)
        self._summary_card.add_widget(info_col)
        content.add_widget(self._summary_card)

        # ── Date-range filter row ──────────────────────────────────
        filter_row = MDBoxLayout(
            size_hint_y=None, height=dp(44), spacing=dp(8)
        )
        self._period_btns = {}
        for key, label in [('7d','7 Days'),('30d','30 Days'),('90d','3 Months'),('all','All Time')]:
            active = key == '30d'
            btn = MDCard(
                size_hint=(None, None), size=(dp(74), dp(36)),
                radius=[dp(18)],
                md_bg_color=get_color('primary') if active else get_color('surface_variant', 0.4),
                ripple_behavior=True,
                on_release=lambda x, k=key: self._set_period(k)
            )
            lbl = MDLabel(
                text=label, halign='center', valign='middle',
                font_style='Caption', bold=active,
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface')
            )
            btn.add_widget(lbl)
            self._period_btns[key] = (btn, lbl)
            filter_row.add_widget(btn)
        self._active_period = '30d'
        content.add_widget(filter_row)

        # ── Totals strip ───────────────────────────────────────────
        totals_row = MDGridLayout(
            cols=3, spacing=dp(8), size_hint_y=None, height=dp(64)
        )
        self._total_in_card  = self._mini_card('KSh 0', 'Total In',  'success')
        self._total_out_card = self._mini_card('KSh 0', 'Total Out', 'error')
        self._txn_count_card = self._mini_card('0',     'Transactions', 'secondary')
        totals_row.add_widget(self._total_in_card)
        totals_row.add_widget(self._total_out_card)
        totals_row.add_widget(self._txn_count_card)
        content.add_widget(totals_row)

        # ── Transaction list ───────────────────────────────────────
        content.add_widget(MDLabel(
            text='TRANSACTIONS', font_style='Caption',
            theme_text_color='Secondary', bold=True,
            size_hint_y=None, height=dp(22), valign='middle'
        ))
        self._txn_list = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self._txn_list.bind(minimum_height=self._txn_list.setter('height'))
        content.add_widget(self._txn_list)

        scroll.add_widget(content)
        root.add_widget(scroll)
        float_root.add_widget(root)
        self.add_widget(float_root)

    def _mini_card(self, value, label, color):
        card = MDCard(
            orientation='vertical', padding=[dp(8), dp(6)],
            radius=[dp(10)],
            md_bg_color=get_color(f'{color}_container', 0.25),
            elevation=0
        )
        v = MDLabel(
            text=value, font_style='Subtitle2', bold=True,
            theme_text_color='Custom', text_color=get_color(color),
            halign='center', valign='middle',
            size_hint_y=None, height=dp(26)
        )
        l = MDLabel(
            text=label, font_style='Caption',
            theme_text_color='Secondary',
            halign='center', valign='middle',
            size_hint_y=None, height=dp(18)
        )
        card.add_widget(v)
        card.add_widget(l)
        card._v = v
        return card

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            uid = self.app.current_user_id
            role = self.app.current_user_role or 'member'
            if role == 'member':
                user = self.app.db.fetch_one("SELECT member_id FROM users WHERE id=?", (uid,))
                mid = (user or {}).get('member_id')
                acc = self.app.db.fetch_one(
                    "SELECT * FROM accounts WHERE member_id=? AND account_type='savings'", (mid,)
                ) if mid else None
            else:
                # staff — use member_id passed via navigate kwargs if available
                mid = getattr(self, '_target_member_id', None)
                acc = self.app.db.fetch_one(
                    "SELECT * FROM accounts WHERE member_id=? AND account_type='savings'", (mid,)
                ) if mid else None

            if not acc:
                Clock.schedule_once(lambda dt: self._show_no_account(), 0)
                return

            self._account_id = acc.get('id')
            txns = self.app.db.fetch_all(
                "SELECT * FROM transactions WHERE account_id=? ORDER BY posted_date DESC LIMIT 200",
                (self._account_id,)
            )
            Clock.schedule_once(lambda dt: self._render(acc, txns), 0)
        except Exception as e:
            Logger.error(f'Statement load: {e}')
            import traceback; traceback.print_exc()

    def _show_no_account(self):
        self._txn_list.clear_widgets()
        self._txn_list.add_widget(MDLabel(
            text='No savings account found.',
            halign='center', theme_text_color='Secondary',
            size_hint_y=None, height=dp(60), valign='middle'
        ))

    def _render(self, acc, txns):
        self._all_txns = txns
        self._acc_no_lbl.text = f"Account: {acc.get('account_no', '—')}"
        bal = (acc.get('balance_minor') or 0) / 100
        self._bal_lbl.text = f"Balance: KSh {bal:,.2f}"
        self._apply_period(self._active_period)

    def _set_period(self, key):
        self._active_period = key
        for k, (btn, lbl) in self._period_btns.items():
            active = k == key
            btn.md_bg_color = get_color('primary') if active else get_color('surface_variant', 0.4)
            lbl.text_color = (1, 1, 1, 1) if active else get_color('on_surface')
            lbl.bold = active
        self._apply_period(key)

    def _apply_period(self, key):
        today = datetime.date.today()
        if key == '7d':
            cutoff = (today - datetime.timedelta(days=7)).isoformat()
        elif key == '30d':
            cutoff = (today - datetime.timedelta(days=30)).isoformat()
        elif key == '90d':
            cutoff = (today - datetime.timedelta(days=90)).isoformat()
        else:
            cutoff = None

        filtered = [t for t in self._all_txns
                    if cutoff is None or (t.get('posted_date') or '') >= cutoff]

        total_in  = sum((t.get('amount_minor') or 0) for t in filtered
                        if t.get('transaction_type') in ('deposit',))
        total_out = sum((t.get('amount_minor') or 0) for t in filtered
                        if t.get('transaction_type') in ('withdrawal', 'loan_repayment'))

        self._total_in_card._v.text  = f"KSh {total_in/100:,.0f}"
        self._total_out_card._v.text = f"KSh {total_out/100:,.0f}"
        self._txn_count_card._v.text = str(len(filtered))

        self._txn_list.clear_widgets()
        if not filtered:
            self._txn_list.add_widget(MDLabel(
                text='No transactions in this period.',
                halign='center', theme_text_color='Secondary',
                size_hint_y=None, height=dp(50), valign='middle'
            ))
            return

        for tx in filtered:
            self._txn_list.add_widget(self._txn_row(tx))

    def _txn_row(self, tx):
        ttype = tx.get('transaction_type', '')
        is_credit = ttype == 'deposit'
        color = 'success' if is_credit else 'error'
        icon  = 'arrow-down-circle' if is_credit else 'arrow-up-circle'

        card = MDCard(
            orientation='horizontal',
            padding=[dp(12), dp(8)], spacing=dp(10),
            radius=[dp(10)],
            md_bg_color=get_color('surface_variant', 0.1),
            size_hint_y=None, height=dp(60), elevation=0
        )
        ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(36), dp(36)))
        with ic_rl.canvas.before:
            Color(*get_color(f'{color}_container', 0.45))
            RoundedRectangle(pos=(0, 0), size=(dp(36), dp(36)), radius=[dp(18)])
        ic_rl.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom', text_color=get_color(color),
            halign='center', valign='middle', font_size=sp(18),
            size_hint=(None, None), size=(dp(22), dp(22)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        card.add_widget(ic_rl)

        info = MDBoxLayout(orientation='vertical', spacing=dp(2))
        info.add_widget(MDLabel(
            text=ttype.replace('_', ' ').title(),
            font_style='Subtitle2', size_hint_y=None, height=dp(22), valign='middle'
        ))
        date_str = (tx.get('posted_date') or tx.get('created_at') or '')[:10]
        ref = tx.get('reference_no') or tx.get('id', '')[:8]
        info.add_widget(MDLabel(
            text=f"{date_str}  •  Ref: {ref}",
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(18), valign='middle'
        ))
        card.add_widget(info)

        amt = (tx.get('amount_minor') or 0) / 100
        sign = '+' if is_credit else '-'
        card.add_widget(MDLabel(
            text=f"{sign}KSh {abs(amt):,.2f}",
            font_style='Subtitle2', bold=True,
            halign='right', valign='middle',
            theme_text_color='Custom',
            text_color=get_color(color)
        ))
        return card

    def _export(self):
        self.show_info('Statement export coming soon')


# ============================================================================
# LOAN CALCULATOR SCREEN
# ============================================================================

class LoanCalculatorScreen(BaseScreen):
    """EMI / amortisation loan calculator — works offline, no DB needed."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'loan_calculator'
        self._build()

    def _build(self):
        from kivy.uix.floatlayout import FloatLayout
        float_root = FloatLayout()
        root = MDBoxLayout(orientation='vertical', size_hint=(1, 1))

        toolbar = MDTopAppBar(
            title='Loan Calculator',
            elevation=2,
            md_bg_color=get_color('quaternary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.navigate_back()]],
        )
        root.add_widget(toolbar)

        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation='vertical', spacing=dp(14),
            padding=[dp(16), dp(16), dp(16), dp(24)],
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))

        # ── Input card ─────────────────────────────────────────────
        input_card = MDCard(
            orientation='vertical',
            padding=dp(16), spacing=dp(10),
            radius=[dp(14)],
            md_bg_color=get_color('surface_variant', 0.15),
            size_hint_y=None, elevation=1
        )
        input_card.bind(minimum_height=input_card.setter('height'))

        input_card.add_widget(MDLabel(
            text='Loan Details', font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color('quaternary'),
            size_hint_y=None, height=dp(28), valign='middle'
        ))

        self._amount_field = MDTextField(
            hint_text='Loan Amount (KSh)', mode='rectangle',
            input_filter='float', size_hint_y=None, height=dp(56)
        )
        self._rate_field = MDTextField(
            hint_text='Annual Interest Rate (%)', mode='rectangle',
            input_filter='float', size_hint_y=None, height=dp(56),
            text='18'
        )
        self._term_field = MDTextField(
            hint_text='Loan Term (months)', mode='rectangle',
            input_filter='int', size_hint_y=None, height=dp(56),
            text='12'
        )

        # Repayment method selector
        method_row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._method = 'reducing'
        self._method_btns = {}
        for key, label in [('reducing', 'Reducing Balance'), ('flat', 'Flat Rate')]:
            active = key == 'reducing'
            btn = MDCard(
                size_hint=(1, None), height=dp(36), radius=[dp(18)],
                md_bg_color=get_color('quaternary') if active else get_color('surface_variant', 0.4),
                ripple_behavior=True,
                on_release=lambda x, k=key: self._set_method(k)
            )
            lbl = MDLabel(
                text=label, halign='center', valign='middle',
                font_style='Caption', bold=active,
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface')
            )
            btn.add_widget(lbl)
            self._method_btns[key] = (btn, lbl)
            method_row.add_widget(btn)

        for w in [self._amount_field, self._rate_field, self._term_field, method_row]:
            input_card.add_widget(w)

        calc_btn = MDRaisedButton(
            text='CALCULATE', md_bg_color=get_color('quaternary'),
            size_hint_y=None, height=dp(48),
            on_release=lambda x: self._calculate()
        )
        input_card.add_widget(calc_btn)
        content.add_widget(input_card)

        # ── Result cards ───────────────────────────────────────────
        self._result_grid = MDGridLayout(
            cols=2, spacing=dp(10), size_hint_y=None, height=dp(0)
        )
        content.add_widget(self._result_grid)

        # ── Schedule section ───────────────────────────────────────
        self._schedule_label = MDLabel(
            text='', font_style='Caption', theme_text_color='Secondary',
            bold=True, size_hint_y=None, height=dp(0), valign='middle'
        )
        content.add_widget(self._schedule_label)

        self._schedule_box = MDBoxLayout(
            orientation='vertical', spacing=dp(4), size_hint_y=None
        )
        self._schedule_box.bind(minimum_height=self._schedule_box.setter('height'))
        content.add_widget(self._schedule_box)

        scroll.add_widget(content)
        root.add_widget(scroll)
        float_root.add_widget(root)
        self.add_widget(float_root)

    def _set_method(self, key):
        self._method = key
        for k, (btn, lbl) in self._method_btns.items():
            active = k == key
            btn.md_bg_color = get_color('quaternary') if active else get_color('surface_variant', 0.4)
            lbl.text_color  = (1, 1, 1, 1) if active else get_color('on_surface')
            lbl.bold = active

    def _calculate(self):
        try:
            P = float(self._amount_field.text or 0)
            r = float(self._rate_field.text or 0) / 100
            n = int(self._term_field.text or 12)
            if P <= 0 or n <= 0:
                self.show_error('Enter a valid amount and term.')
                return

            if self._method == 'reducing':
                monthly_r = r / 12
                if monthly_r == 0:
                    emi = P / n
                else:
                    emi = P * monthly_r * (1 + monthly_r)**n / ((1 + monthly_r)**n - 1)
                total_pay = emi * n
                total_int = total_pay - P

                # Generate schedule
                schedule = []
                balance = P
                for i in range(1, n + 1):
                    interest = balance * monthly_r
                    principal_part = emi - interest
                    balance -= principal_part
                    schedule.append({
                        'month': i, 'emi': emi,
                        'principal': principal_part,
                        'interest': interest,
                        'balance': max(balance, 0)
                    })
            else:
                # Flat rate
                total_int = P * r * (n / 12)
                total_pay = P + total_int
                emi = total_pay / n
                schedule = []
                monthly_int = total_int / n
                monthly_princ = P / n
                balance = P
                for i in range(1, n + 1):
                    balance -= monthly_princ
                    schedule.append({
                        'month': i, 'emi': emi,
                        'principal': monthly_princ,
                        'interest': monthly_int,
                        'balance': max(balance, 0)
                    })

            self._render_results(P, emi, total_int, total_pay, n, schedule)
        except Exception as e:
            self.show_error(f'Calculation error: {e}')

    def _render_results(self, principal, emi, total_int, total_pay, n, schedule):
        # Result summary cards
        self._result_grid.clear_widgets()
        self._result_grid.height = dp(280)
        for value, label, color in [
            (f"KSh {emi:,.2f}",      'Monthly EMI',       'quaternary'),
            (f"KSh {principal:,.2f}",'Loan Amount',        'primary'),
            (f"KSh {total_int:,.2f}",'Total Interest',     'error'),
            (f"KSh {total_pay:,.2f}",'Total Repayable',    'secondary'),
            (f"{total_int/principal*100:.1f}%", 'Interest Rate Eff.', 'warning'),
            (f"{n} months",          'Term',               'tertiary'),
        ]:
            card = MDCard(
                orientation='vertical', padding=[dp(10), dp(8)],
                radius=[dp(12)],
                md_bg_color=get_color(f'{color}_container', 0.25),
                elevation=0
            )
            card.add_widget(MDLabel(
                text=value, font_style='Subtitle1', bold=True,
                theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle',
                size_hint_y=None, height=dp(28)
            ))
            card.add_widget(MDLabel(
                text=label, font_style='Caption',
                theme_text_color='Secondary',
                halign='center', valign='middle',
                size_hint_y=None, height=dp(18)
            ))
            self._result_grid.add_widget(card)

        # Amortisation schedule header
        self._schedule_label.text = 'REPAYMENT SCHEDULE'
        self._schedule_label.height = dp(26)

        self._schedule_box.clear_widgets()
        # Column header
        hdr = MDBoxLayout(size_hint_y=None, height=dp(28))
        for txt, weight in [('Mo.', 0.1), ('EMI', 0.25), ('Principal', 0.25),
                             ('Interest', 0.22), ('Balance', 0.18)]:
            hdr.add_widget(MDLabel(
                text=txt, font_style='Caption', bold=True,
                theme_text_color='Secondary',
                halign='right' if weight < 0.2 else 'right',
                size_hint_x=weight, valign='middle',
                size_hint_y=None, height=dp(28)
            ))
        self._schedule_box.add_widget(hdr)

        for row in schedule:
            r = MDBoxLayout(
                size_hint_y=None, height=dp(24),
                md_bg_color=get_color('surface_variant', 0.08) if row['month'] % 2 == 0 else (0, 0, 0, 0)
            )
            for val, weight in [
                (str(row['month']),             0.10),
                (f"{row['emi']:,.0f}",          0.25),
                (f"{row['principal']:,.0f}",    0.25),
                (f"{row['interest']:,.0f}",     0.22),
                (f"{row['balance']:,.0f}",      0.18),
            ]:
                r.add_widget(MDLabel(
                    text=val, font_style='Caption',
                    halign='right', valign='middle',
                    size_hint_x=weight,
                    size_hint_y=None, height=dp(24)
                ))
            self._schedule_box.add_widget(r)


# ============================================================================
# MY PROFILE SCREEN  (member's own profile — read only + request edit)
# ============================================================================

class MyProfileScreen(BaseScreen):
    """Member's own profile screen with account summary and quick actions."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'my_profile'
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')
        toolbar = MDTopAppBar(
            title='My Profile',
            elevation=2, md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.navigate_back()]],
        )
        root.add_widget(toolbar)

        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation='vertical', spacing=dp(12),
            padding=[dp(14), dp(14), dp(14), dp(24)],
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))

        # Avatar + name hero
        self._hero = MDCard(
            orientation='vertical',
            padding=[dp(20), dp(16)], spacing=dp(4),
            radius=[dp(16)], md_bg_color=get_color('primary'),
            size_hint_y=None, height=dp(130), elevation=3
        )
        av_row = MDBoxLayout(size_hint_y=None, height=dp(60), spacing=dp(14))
        self._av_rl = RelativeLayout(size_hint=(None, None), size=(dp(60), dp(60)))
        with self._av_rl.canvas.before:
            Color(1, 1, 1, 0.22)
            RoundedRectangle(pos=(0, 0), size=(dp(60), dp(60)), radius=[dp(30)])
        self._initials_lbl = MDLabel(
            text='?', halign='center', valign='middle',
            font_style='H5', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint=(None, None), size=(dp(60), dp(60)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self._av_rl.add_widget(self._initials_lbl)
        av_row.add_widget(self._av_rl)
        name_col = MDBoxLayout(orientation='vertical', spacing=dp(2))
        self._name_lbl = MDLabel(
            text='—', font_style='H6', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(30), valign='middle'
        )
        self._memno_lbl = MDLabel(
            text='—', font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.75),
            size_hint_y=None, height=dp(20), valign='middle'
        )
        self._kyc_lbl = MDLabel(
            text='KYC: Pending', font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.65),
            size_hint_y=None, height=dp(18), valign='middle'
        )
        for w in [self._name_lbl, self._memno_lbl, self._kyc_lbl]:
            name_col.add_widget(w)
        av_row.add_widget(name_col)
        self._hero.add_widget(av_row)
        content.add_widget(self._hero)

        # Account balance card
        self._bal_card = MDCard(
            orientation='horizontal',
            padding=[dp(16), dp(12)], spacing=dp(12),
            radius=[dp(14)],
            md_bg_color=get_color('tertiary_container', 0.3),
            size_hint_y=None, height=dp(70), elevation=1
        )
        bal_icon = RelativeLayout(size_hint=(None, None), size=(dp(44), dp(44)))
        with bal_icon.canvas.before:
            Color(*get_color('tertiary_container', 0.6))
            RoundedRectangle(pos=(0, 0), size=(dp(44), dp(44)), radius=[dp(12)])
        bal_icon.add_widget(MDIcon(
            icon='bank', theme_text_color='Custom', text_color=get_color('tertiary'),
            halign='center', valign='middle', font_size=sp(22),
            size_hint=(None, None), size=(dp(26), dp(26)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        self._bal_card.add_widget(bal_icon)
        bal_info = MDBoxLayout(orientation='vertical', spacing=dp(2))
        self._bal_lbl = MDLabel(
            text='KSh 0.00', font_style='H6', bold=True,
            theme_text_color='Custom', text_color=get_color('tertiary'),
            size_hint_y=None, height=dp(28), valign='middle'
        )
        bal_info.add_widget(self._bal_lbl)
        bal_info.add_widget(MDLabel(
            text='Savings Account Balance',
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(18), valign='middle'
        ))
        self._bal_card.add_widget(bal_info)
        content.add_widget(self._bal_card)

        # Quick action buttons — row 1 (general)
        from kivy.uix.relativelayout import RelativeLayout as _RL
        actions_row = MDBoxLayout(size_hint_y=None, height=dp(72), spacing=dp(8))
        for label, color, screen, icon in [
            ('Statement',  'primary',    'statement',      'file-document'),
            ('Calculator', 'quaternary', 'loan_calculator','calculator'),
            ('Invest',     'info',       'investments',    'trending-up'),
        ]:
            btn = MDCard(
                orientation='vertical', radius=[dp(12)],
                md_bg_color=get_color(f'{color}_container', 0.25),
                ripple_behavior=True, elevation=0,
                size_hint_x=1, size_hint_y=None, height=dp(72), padding=[dp(4),dp(6)],
                on_release=lambda x, s=screen: self.app.navigate_to(s)
            )
            ic_rl = _RL(size_hint_y=None, height=dp(36))
            ic_rl.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle', font_size=sp(22),
                size_hint=(None,None), size=(dp(28),dp(28)),
                pos_hint={'center_x':0.5,'center_y':0.5}
            ))
            btn.add_widget(ic_rl)
            btn.add_widget(MDLabel(
                text=label, halign='center', font_style='Caption',
                theme_text_color='Custom', text_color=get_color('on_surface'),
                size_hint_y=None, height=dp(18)
            ))
            actions_row.add_widget(btn)
        content.add_widget(actions_row)

        # Quick action buttons — row 2 (mobile money)
        mm_row = MDBoxLayout(size_hint_y=None, height=dp(72), spacing=dp(8))
        for label, color, icon, provider in [
            ('M-Pesa',       'success', 'alpha-m-circle', 'mpesa'),
            ('Airtel Money', 'error',   'alpha-a-circle', 'airtel'),
        ]:
            btn = MDCard(
                orientation='vertical', radius=[dp(12)],
                md_bg_color=get_color(f'{color}_container', 0.25),
                ripple_behavior=True, elevation=0,
                size_hint_x=1, size_hint_y=None, height=dp(72), padding=[dp(4),dp(6)],
                on_release=lambda x, p=provider: self._goto_mm(p)
            )
            ic_rl = _RL(size_hint_y=None, height=dp(36))
            ic_rl.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle', font_size=sp(24),
                size_hint=(None,None), size=(dp(30),dp(30)),
                pos_hint={'center_x':0.5,'center_y':0.5}
            ))
            btn.add_widget(ic_rl)
            btn.add_widget(MDLabel(
                text=label, halign='center', font_style='Caption',
                theme_text_color='Custom', text_color=get_color('on_surface'),
                size_hint_y=None, height=dp(18)
            ))
            mm_row.add_widget(btn)
        content.add_widget(mm_row)

        # Personal details
        self._details_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self._details_box.bind(minimum_height=self._details_box.setter('height'))
        content.add_widget(self._details_box)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _goto_mm(self, provider):
        """Navigate to mobile money screen with this member + provider pre-set."""
        try:
            user = self.app.db.fetch_one(
                "SELECT member_id FROM users WHERE id=?", (self.app.current_user_id,))
            mid = (user or {}).get('member_id')
            mm_screen = self.app.screens_cache.get('mobile_money')
            if mm_screen:
                mm_screen._provider_key = provider
                mm_screen.member_id     = mid
            self.app.navigate_to('mobile_money', member_id=mid)
        except Exception as e:
            self.show_error(str(e))

    def _load(self):
        try:
            user = self.app.db.fetch_one(
                "SELECT member_id FROM users WHERE id=?", (self.app.current_user_id,))
            mid = (user or {}).get('member_id')
            if not mid:
                return
            member = self.app.db.fetch_one("SELECT * FROM members WHERE id=?", (mid,))
            acc = self.app.db.fetch_one(
                "SELECT * FROM accounts WHERE member_id=? AND account_type='savings'", (mid,))
            Clock.schedule_once(lambda dt: self._render(member, acc), 0)
        except Exception as e:
            Logger.error(f'MyProfile load: {e}')

    def _render(self, member, acc):
        if not member:
            return
        fn = member.get('first_name', '')
        ln = member.get('last_name', '')
        initials = ((fn[0] if fn else '') + (ln[0] if ln else '')).upper() or '?'
        self._initials_lbl.text = initials
        self._name_lbl.text = f"{fn} {ln}"
        self._memno_lbl.text = member.get('member_no', '—')
        kyc = member.get('kyc_status', 'pending') or 'pending'
        self._kyc_lbl.text = f"KYC: {kyc.title()}"

        bal = (acc.get('balance_minor') or 0) / 100 if acc else 0
        self._bal_lbl.text = f"KSh {bal:,.2f}"

        # Personal details card
        self._details_box.clear_widgets()
        fields = [
            ('Phone',        member.get('phone', '—')),
            ('Email',        member.get('email', '—')),
            ('ID Number',    member.get('id_number', '—')),
            ('Date of Birth',member.get('date_of_birth', '—')),
            ('Gender',       member.get('gender', '—')),
            ('Occupation',   member.get('occupation', '—')),
            ('Joined',       member.get('membership_date', '—')),
        ]
        card = MDCard(
            orientation='vertical', padding=dp(14), spacing=dp(2),
            radius=[dp(12)],
            md_bg_color=get_color('surface_variant', 0.15),
            size_hint_y=None, elevation=0
        )
        card.add_widget(MDLabel(
            text='Personal Information', font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color('primary'),
            size_hint_y=None, height=dp(28), valign='middle'
        ))
        for label, value in fields:
            row = MDBoxLayout(size_hint_y=None, height=dp(28))
            row.add_widget(MDLabel(
                text=label, font_style='Caption',
                theme_text_color='Secondary', size_hint_x=0.38,
                size_hint_y=None, height=dp(28), valign='middle'
            ))
            row.add_widget(MDLabel(
                text=str(value or '—'), font_style='Body2',
                size_hint_x=0.62,
                size_hint_y=None, height=dp(28), valign='middle'
            ))
            card.add_widget(row)
        card.height = dp(14 + 28 + sum(28 for _, v in fields) + 14)
        self._details_box.add_widget(card)


# ============================================================================
# MEMBER SETTINGS SCREEN
# ============================================================================


class MemberSettingsScreen(BaseScreen):
    """Member-facing settings — personal preferences, security, appearance."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'member_settings'
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')
        root.add_widget(MDTopAppBar(
            title='My Settings',
            md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        ))

        scroll = MDScrollView()
        body = MDBoxLayout(
            orientation='vertical', spacing=dp(10),
            padding=[dp(14), dp(14), dp(14), dp(30)], size_hint_y=None
        )
        body.bind(minimum_height=body.setter('height'))

        # ── SECTION helper ─────────────────────────────────────────────────────
        def _section(title, icon, color):
            hdr = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(42),
                padding=[dp(12), 0], spacing=dp(10),
                radius=[dp(10), dp(10), 0, 0],
                md_bg_color=get_color(f'{color}_container', 0.35), elevation=0
            )
            hdr.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom', text_color=get_color(color),
                size_hint_x=None, width=dp(24), valign='middle'
            ))
            hdr.add_widget(MDLabel(
                text=title, font_style='Subtitle2', bold=True,
                theme_text_color='Custom', text_color=get_color(color), valign='middle'
            ))
            body.add_widget(hdr)
            card = MDCard(
                orientation='vertical', padding=[dp(12), dp(10)], spacing=dp(0),
                radius=[0, 0, dp(10), dp(10)],
                md_bg_color=get_color('surface_variant', 0.12),
                size_hint_y=None, elevation=0
            )
            card.bind(minimum_height=card.setter('height'))
            body.add_widget(card)
            return card

        # ── ROW helpers ────────────────────────────────────────────────────────
        def _toggle(parent, label, subtitle, db_key, default='0'):
            row = MDBoxLayout(size_hint_y=None, height=dp(56), padding=[dp(4), 0])
            info = MDBoxLayout(orientation='vertical', spacing=dp(1))
            info.add_widget(MDLabel(text=label, font_style='Subtitle2',
                                    size_hint_y=None, height=dp(24), valign='middle'))
            info.add_widget(MDLabel(text=subtitle, font_style='Caption',
                                    theme_text_color='Secondary',
                                    size_hint_y=None, height=dp(18), valign='middle'))
            row.add_widget(info)
            row.add_widget(MDBoxLayout())
            sw = MDSwitch(size_hint=(None, None), size=(dp(56), dp(28)))

            def _save(inst, val):
                try:
                    self.app.db.execute(
                        'INSERT OR REPLACE INTO system_settings (key,value) VALUES (?,?)',
                        (db_key, '1' if val else '0')
                    )
                except Exception as e:
                    Logger.error(f'MemberSettings {db_key}: {e}')

            sw.bind(active=_save)
            row.add_widget(sw)
            parent.add_widget(row)

            def _load(dt):
                try:
                    r = self.app.db.fetch_one(
                        'SELECT value FROM system_settings WHERE key=?', (db_key,))
                    sw.active = ((r or {}).get('value') or default) == '1'
                except Exception:
                    pass
            Clock.schedule_once(_load, 0.2)

        def _action(parent, label, subtitle, icon, color, fn):
            btn = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(56),
                padding=[dp(10), 0], spacing=dp(12), elevation=0,
                md_bg_color=(0,0,0,0), ripple_behavior=True,
                on_release=lambda x: fn()
            )
            btn.add_widget(MDCard(
                size_hint=(None, None), size=(dp(36), dp(36)),
                radius=[dp(8)], md_bg_color=get_color(f'{color}_container', 0.3),
                elevation=0
            ))
            # re-add icon inside the color circle
            parent.add_widget(btn)  # add btn first so we can patch
            parent.children[0].children[0].add_widget(MDIcon(
                icon=icon, theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle'
            ))
            info = MDBoxLayout(orientation='vertical', spacing=dp(1))
            info.add_widget(MDLabel(text=label, font_style='Subtitle2',
                                    size_hint_y=None, height=dp(24), valign='middle'))
            info.add_widget(MDLabel(text=subtitle, font_style='Caption',
                                    theme_text_color='Secondary',
                                    size_hint_y=None, height=dp(18), valign='middle'))
            btn.add_widget(info)
            btn.add_widget(MDIcon(icon='chevron-right', theme_text_color='Secondary',
                                  size_hint_x=None, width=dp(20), valign='middle'))

        # ── NOTIFICATIONS ─────────────────────────────────────────────────────
        n = _section('Notifications', 'bell-badge-outline', 'info')
        _toggle(n, 'SMS Alerts', 'SMS when a transaction is posted to your account',
                'mbr_sms_alerts', '1')
        _toggle(n, 'Email Alerts', 'Email notifications for transactions',
                'mbr_email_alerts', '1')
        _toggle(n, 'Loan Reminders', 'Reminder before loan repayment due date',
                'mbr_loan_reminders', '1')
        _toggle(n, 'Monthly Statement', 'Auto-send monthly statement to your email',
                'mbr_monthly_stmt', '0')

        # ── SECURITY ──────────────────────────────────────────────────────────
        s = _section('Security', 'shield-lock-outline', 'error')
        _toggle(s, 'Require PIN on transactions',
                'Ask for PIN before every withdrawal or transfer',
                'mbr_require_pin', '1')
        _toggle(s, 'Biometric Login', 'Use fingerprint / face ID to sign in',
                'mbr_biometric', '0')
        # Change password row — built manually for clean layout
        pw_row = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(56),
            padding=[dp(10), 0], spacing=dp(12), elevation=0,
            md_bg_color=(0,0,0,0), ripple_behavior=True,
            on_release=lambda x: self._change_password()
        )
        pw_icon_box = MDCard(size_hint=(None,None), size=(dp(36),dp(36)),
                             radius=[dp(8)], md_bg_color=get_color('error_container',0.3),
                             elevation=0)
        pw_icon_box.add_widget(MDIcon(icon='lock-reset', theme_text_color='Custom',
                                      text_color=get_color('error'),
                                      halign='center', valign='middle'))
        pw_row.add_widget(pw_icon_box)
        pw_info = MDBoxLayout(orientation='vertical', spacing=dp(1))
        pw_info.add_widget(MDLabel(text='Change Password', font_style='Subtitle2',
                                   size_hint_y=None, height=dp(24), valign='middle'))
        pw_info.add_widget(MDLabel(text='Update your login password',
                                   font_style='Caption', theme_text_color='Secondary',
                                   size_hint_y=None, height=dp(18), valign='middle'))
        pw_row.add_widget(pw_info)
        pw_row.add_widget(MDIcon(icon='chevron-right', theme_text_color='Secondary',
                                 size_hint_x=None, width=dp(20), valign='middle'))
        s.add_widget(pw_row)

        # ── APPEARANCE ────────────────────────────────────────────────────────
        ap = _section('Appearance', 'palette-outline', 'primary')
        theme_row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for t, icon in [('Light', 'white-balance-sunny'), ('Dark', 'moon-waning-crescent'), ('System', 'circle-half-full')]:
            btn = MDCard(
                orientation='vertical', size_hint_x=1, size_hint_y=None, height=dp(44),
                radius=[dp(8)], ripple_behavior=True,
                md_bg_color=get_color('primary', 0.15),
                on_release=lambda x, _t=t: self._set_theme(_t)
            )
            btn.add_widget(MDIcon(icon=icon, halign='center', font_size=sp(18),
                                  theme_text_color='Custom', text_color=get_color('primary'),
                                  size_hint_y=None, height=dp(26)))
            btn.add_widget(MDLabel(text=t, halign='center', font_style='Caption', bold=True,
                                   theme_text_color='Custom', text_color=get_color('primary'),
                                   size_hint_y=None, height=dp(16)))
            theme_row.add_widget(btn)
        ap.add_widget(theme_row)
        _toggle(ap, 'Compact View', 'Denser layout with smaller text', 'mbr_compact', '0')

        # ── ACCOUNT ───────────────────────────────────────────────────────────
        ac = _section('My Account', 'account-circle-outline', 'tertiary')

        profile_row = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(56),
            padding=[dp(10), 0], spacing=dp(12), elevation=0,
            md_bg_color=(0,0,0,0), ripple_behavior=True,
            on_release=lambda x: self.app.navigate_to('my_profile')
        )
        p_icon = MDCard(size_hint=(None,None), size=(dp(36),dp(36)),
                        radius=[dp(8)], md_bg_color=get_color('tertiary_container',0.3), elevation=0)
        p_icon.add_widget(MDIcon(icon='account-edit', theme_text_color='Custom',
                                 text_color=get_color('tertiary'), halign='center', valign='middle'))
        profile_row.add_widget(p_icon)
        p_info = MDBoxLayout(orientation='vertical', spacing=dp(1))
        p_info.add_widget(MDLabel(text='My Profile', font_style='Subtitle2',
                                  size_hint_y=None, height=dp(24), valign='middle'))
        p_info.add_widget(MDLabel(text='View and update your personal details',
                                  font_style='Caption', theme_text_color='Secondary',
                                  size_hint_y=None, height=dp(18), valign='middle'))
        profile_row.add_widget(p_info)
        profile_row.add_widget(MDIcon(icon='chevron-right', theme_text_color='Secondary',
                                      size_hint_x=None, width=dp(20), valign='middle'))
        ac.add_widget(profile_row)

        stmt_row = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(56),
            padding=[dp(10), 0], spacing=dp(12), elevation=0,
            md_bg_color=(0,0,0,0), ripple_behavior=True,
            on_release=lambda x: self.app.navigate_to('statement')
        )
        st_icon = MDCard(size_hint=(None,None), size=(dp(36),dp(36)),
                         radius=[dp(8)], md_bg_color=get_color('tertiary_container',0.3), elevation=0)
        st_icon.add_widget(MDIcon(icon='file-chart', theme_text_color='Custom',
                                  text_color=get_color('tertiary'), halign='center', valign='middle'))
        stmt_row.add_widget(st_icon)
        st_info = MDBoxLayout(orientation='vertical', spacing=dp(1))
        st_info.add_widget(MDLabel(text='Account Statement', font_style='Subtitle2',
                                   size_hint_y=None, height=dp(24), valign='middle'))
        st_info.add_widget(MDLabel(text='View your full transaction history',
                                   font_style='Caption', theme_text_color='Secondary',
                                   size_hint_y=None, height=dp(18), valign='middle'))
        stmt_row.add_widget(st_info)
        stmt_row.add_widget(MDIcon(icon='chevron-right', theme_text_color='Secondary',
                                   size_hint_x=None, width=dp(20), valign='middle'))
        ac.add_widget(stmt_row)

        # ── LANGUAGE ──────────────────────────────────────────────────────────
        lg = _section('Language', 'translate', 'secondary')
        lang_row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for code, label in [('English', 'English'), ('Swahili', 'Kiswahili')]:
            btn = MDCard(size_hint_x=1, size_hint_y=None, height=dp(44),
                         radius=[dp(8)], ripple_behavior=True,
                         md_bg_color=get_color('secondary', 0.12),
                         on_release=lambda x, _l=label: self.show_info(f'{_l} — coming soon'))
            btn.add_widget(MDLabel(text=label, halign='center', font_style='Body2', bold=True,
                                   theme_text_color='Custom', text_color=get_color('secondary'),
                                   valign='middle'))
            lang_row.add_widget(btn)
        lg.add_widget(lang_row)

        # ── ABOUT ─────────────────────────────────────────────────────────────
        ab = _section('About', 'information-outline', 'outline')
        for label, value in [
            ('App',     'HELA SMART SACCO'),
            ('Version', 'v3.0'),
            ('Support', 'support@helasacco.co.ke'),
            ('Hotline', '+254 700 000 000'),
        ]:
            rr = MDBoxLayout(size_hint_y=None, height=dp(30), padding=[dp(4), 0])
            rr.add_widget(MDLabel(text=label, font_style='Caption',
                                  theme_text_color='Secondary', size_hint_x=0.35, valign='middle'))
            rr.add_widget(MDLabel(text=value, font_style='Body2', bold=True,
                                  size_hint_x=0.65, valign='middle'))
            ab.add_widget(rr)

        # ── LOG OUT ───────────────────────────────────────────────────────────
        body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(12)))
        body.add_widget(MDRaisedButton(
            text='LOG OUT', size_hint_x=1, height=dp(50),
            md_bg_color=get_color('error'),
            on_release=lambda x: self.confirm_dialog(
                title='Log Out?',
                text='You will be returned to the login screen.',
                on_confirm=lambda: self.app.logout()
            )
        ))

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    # ── ACTIONS ───────────────────────────────────────────────────────────────

    def _set_theme(self, theme):
        try:
            self.app.theme_cls.theme_style = 'Dark' if theme == 'Dark' else 'Light'
        except Exception:
            pass
        self.show_info(f'Theme: {theme}')

    def _change_password(self):
        """Change password using direct DB update with proper hashing."""
        import hashlib, base64, os as _os
        fields = {}
        content = MDBoxLayout(orientation='vertical', spacing=dp(8),
                              size_hint_y=None, height=dp(190))
        for key, hint in [('current', 'Current password'),
                          ('new',     'New password  (min. 6 chars)'),
                          ('confirm', 'Confirm new password')]:
            tf = MDTextField(hint_text=hint, mode='rectangle',
                             password=True, size_hint_y=None, height=dp(56))
            fields[key] = tf
            content.add_widget(tf)

        dlg = [None]

        def _do():
            cur  = fields['current'].text.strip()
            new  = fields['new'].text.strip()
            conf = fields['confirm'].text.strip()
            if not cur or not new:
                self.show_error('Fill in all three fields')
                return
            if new != conf:
                self.show_error('New passwords do not match')
                return
            if len(new) < 6:
                self.show_error('Password must be at least 6 characters')
                return
            try:
                uid = self.app.current_user_id
                row = self.app.db.fetch_one(
                    'SELECT password_hash, salt, iterations FROM users WHERE id=?', (uid,))
                if not row:
                    self.show_error('User not found'); return
                # Verify current password
                salt = row['salt']; iters = row['iterations'] or 600000
                h_cur = base64.b64encode(hashlib.pbkdf2_hmac(
                    'sha256', cur.encode(), base64.b64decode(salt), iters, 32
                )).decode()
                if h_cur != row['password_hash']:
                    self.show_error('Current password is incorrect'); return
                # Hash new password
                new_salt = base64.b64encode(_os.urandom(32)).decode()
                h_new = base64.b64encode(hashlib.pbkdf2_hmac(
                    'sha256', new.encode(), base64.b64decode(new_salt), iters, 32
                )).decode()
                self.app.db.execute(
                    'UPDATE users SET password_hash=?, salt=? WHERE id=?',
                    (h_new, new_salt, uid)
                )
                dlg[0].dismiss()
                self.show_success('Password changed successfully ✓')
            except Exception as e:
                self.show_error(str(e))

        dlg[0] = MDDialog(
            title='Change Password', type='custom', content_cls=content,
            buttons=[
                MDFlatButton(text='CANCEL', on_release=lambda x: dlg[0].dismiss()),
                MDRaisedButton(text='CHANGE', md_bg_color=get_color('primary'),
                               on_release=lambda x: _do()),
            ]
        )
        dlg[0].open()

