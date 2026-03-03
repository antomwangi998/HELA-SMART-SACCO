# screens_transactions.py - Deposit, Withdrawal, Transfer screens
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import datetime
import threading

from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen


def _fmt(minor):
    try:
        return f"KSh {int(minor) / 100:,.2f}"
    except Exception:
        return "KSh 0.00"


def _to_minor(text):
    try:
        return int(float(str(text).replace(',', '')) * 100)
    except Exception:
        return 0

# Alias kept for backward compatibility
_amount_from_text = _to_minor


def _receipt_dialog(title, lines, on_dismiss=None):
    content = MDBoxLayout(
        orientation='vertical', spacing=dp(8), padding=dp(4),
        size_hint_y=None, height=dp(max(len(lines) * 36 + 16, 60))
    )
    for label, value in lines:
        row = MDBoxLayout(size_hint_y=None, height=dp(32))
        row.add_widget(MDLabel(
            text=str(label), theme_text_color='Secondary',
            size_hint_x=0.5, font_style='Caption',
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=str(value), bold=True, size_hint_x=0.5, halign='right',
            valign='middle'
        ))
        content.add_widget(row)

    dialog = MDDialog(
        title=f'✅  {title}',
        type='custom',
        content_cls=content,
        buttons=[
            MDRaisedButton(
                text='DONE',
                md_bg_color=get_color('primary'),
                on_release=lambda x: (dialog.dismiss(), on_dismiss() if on_dismiss else None)
            )
        ]
    )
    dialog.open()


# ─────────────────────────────────────────────────────────────────────────────
# DEPOSIT SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class DepositScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'deposit'
        self.member_id = None
        self._accounts = []
        self._selected_account_id = None
        self._channel = 'branch'
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Deposit',
            md_bg_color=get_color('success'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        body = MDBoxLayout(
            orientation='vertical', spacing=dp(14),
            padding=dp(14), size_hint_y=None
        )
        body.bind(minimum_height=body.setter('height'))

        # Member search row
        search_row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.member_search = MDTextField(
            hint_text='Search member by name, ID or phone',
            mode='rectangle', line_color_focus=get_color('success')
        )
        search_btn = MDRaisedButton(
            text='Find',
            md_bg_color=get_color('success'),
            size_hint_x=None, width=dp(70),
            on_release=lambda x: self._search_member()
        )
        search_row.add_widget(self.member_search)
        search_row.add_widget(search_btn)
        body.add_widget(search_row)

        # Member banner
        self.member_card = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(64),
            radius=[dp(10)], padding=dp(12),
            md_bg_color=get_color('success', 0.08), elevation=0
        )
        self.member_icon = MDCard(
            size_hint=(None, None), size=(dp(40), dp(40)),
            radius=[dp(20)], md_bg_color=get_color('success', 0.2)
        )
        self.member_icon.add_widget(MDIcon(
            icon='account', theme_text_color='Custom',
            text_color=get_color('success'), halign='center',
            valign='middle'
        ))
        self.member_name_lbl = MDLabel(
            text='No member selected', font_style='Subtitle2',
            theme_text_color='Secondary',
            valign='middle'
        )
        self.member_card.add_widget(self.member_icon)
        self.member_card.add_widget(self.member_name_lbl)
        body.add_widget(self.member_card)

        # Account picker
        body.add_widget(self._sec('To Account', 'bank-outline'))
        self.account_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.account_box.bind(minimum_height=self.account_box.setter('height'))
        body.add_widget(self.account_box)

        # Amount
        body.add_widget(self._sec('Amount (KSh)', 'cash-plus'))
        self.amount_field = MDTextField(
            hint_text='0.00', mode='rectangle',
            input_filter='float', font_size=sp(22),
            line_color_focus=get_color('success'),
            size_hint_y=None, height=dp(60)
        )
        body.add_widget(self.amount_field)

        # Quick amounts
        chips = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for amt in [500, 1000, 2000, 5000, 10000]:
            c = MDCard(
                size_hint=(None, None), size=(dp(74), dp(36)),
                radius=[dp(18)],
                md_bg_color=get_color('success_container', 0.4),
                ripple_behavior=True,
                on_release=lambda x, a=amt: setattr(self.amount_field, 'text', str(a))
            )
            c.add_widget(MDLabel(
                text=f'{amt:,}', halign='center', font_style='Caption',
                theme_text_color='Custom', text_color=get_color('success'),
                valign='middle'
            ))
            chips.add_widget(c)
        body.add_widget(chips)

        self.desc_field = MDTextField(
            hint_text='Reference / Description (optional)',
            mode='rectangle', line_color_focus=get_color('success'),
            size_hint_y=None, height=dp(56)
        )
        body.add_widget(self.desc_field)

        # Channel selector
        body.add_widget(self._sec('Channel', 'swap-horizontal'))
        channel_row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._channel_btns = {}
        for ch in ['branch', 'mobile', 'agent', 'online']:
            btn = MDCard(
                size_hint_x=1, size_hint_y=None, height=dp(38),
                radius=[dp(8)],
                md_bg_color=get_color('success') if ch == 'branch' else get_color('surface_variant', 0.4),
                ripple_behavior=True,
                on_release=lambda x, c=ch: self._pick_channel(c)
            )
            btn.add_widget(MDLabel(
                text=ch.title(), halign='center', font_style='Caption',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if ch == 'branch' else get_color('outline'),
                valign='middle'
            ))
            self._channel_btns[ch] = btn
            channel_row.add_widget(btn)
        body.add_widget(channel_row)

        self.submit_btn = MDRaisedButton(
            text='DEPOSIT',
            size_hint_x=1, height=dp(54),
            md_bg_color=get_color('success'),
            font_size=sp(15),
            on_release=self._confirm
        )
        body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(8)))
        body.add_widget(self.submit_btn)

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    def _sec(self, text, icon):
        row = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color('success'), size_hint_x=None, width=dp(22),
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=text.upper(), font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('success'),
            valign='middle'
        ))
        return row

    def _pick_channel(self, ch):
        self._channel = ch
        for c, btn in self._channel_btns.items():
            active = c == ch
            btn.md_bg_color = get_color('success') if active else get_color('surface_variant', 0.4)
            btn.children[0].text_color = (1, 1, 1, 1) if active else get_color('outline')

    def on_enter(self):
        if self.member_id:
            threading.Thread(target=self._load_member_by_id, args=(self.member_id,), daemon=True).start()

    def _search_member(self):
        q = self.member_search.text.strip()
        if not q:
            self.show_error('Enter a name, phone, or ID to search')
            return
        threading.Thread(target=self._run_member_search, args=(q,), daemon=True).start()

    def _run_member_search(self, q):
        try:
            m = self.app.db.fetch_one(
                "SELECT * FROM members WHERE is_active=1 AND "
                "(first_name LIKE ? OR last_name LIKE ? OR phone=? OR id_number=? OR member_no=?) LIMIT 1",
                (f'%{q}%', f'%{q}%', q, q, q)
            )
            if m:
                Clock.schedule_once(lambda dt: self._load_member(m), 0)
            else:
                Clock.schedule_once(lambda dt: self.show_error('Member not found'), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _load_member_by_id(self, mid):
        try:
            m = self.app.db.fetch_one("SELECT * FROM members WHERE id=?", (mid,))
            accs = self.app.db.fetch_all(
                "SELECT * FROM accounts WHERE member_id=? AND status='active'", (mid,)
            )
            Clock.schedule_once(lambda dt: (self._update_member_banner(m), self._render_accounts(accs)), 0)
        except Exception as e:
            Logger.error(f'Deposit load: {e}')

    def _load_member(self, m):
        self.member_id = m['id']
        self._update_member_banner(m)
        threading.Thread(target=self._load_accounts, daemon=True).start()

    def _update_member_banner(self, m):
        if m:
            self.member_name_lbl.text = f"{m.get('first_name','')} {m.get('last_name','')}  •  {m.get('member_no','')}"
            self.member_name_lbl.theme_text_color = 'Custom'
            self.member_name_lbl.text_color = get_color('success')

    def _load_accounts(self):
        try:
            accs = self.app.db.fetch_all(
                "SELECT * FROM accounts WHERE member_id=? AND status='active' AND account_type!='loan'",
                (self.member_id,)
            )
            Clock.schedule_once(lambda dt: self._render_accounts(accs), 0)
        except Exception as e:
            Logger.error(f'Deposit accounts: {e}')

    def _render_accounts(self, accs):
        self._accounts = accs
        self.account_box.clear_widgets()
        if not accs:
            self.account_box.add_widget(MDLabel(
                text='No accounts found for this member',
                theme_text_color='Secondary', size_hint_y=None, height=dp(36),
                valign='middle'
            ))
            return
        if not self._selected_account_id and accs:
            self._selected_account_id = accs[0]['id']
        for acc in accs:
            active = acc['id'] == self._selected_account_id
            card = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(60),
                radius=[dp(10)], padding=dp(12),
                md_bg_color=get_color('success') if active else get_color('surface_variant', 0.2),
                ripple_behavior=True, elevation=2 if active else 0,
                on_release=lambda x, a=acc: self._select_account(a)
            )
            card.add_widget(MDIcon(
                icon='bank', theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('success'),
                size_hint_x=None, width=dp(28),
                valign='middle'
            ))
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(
                text=acc.get('account_no', ''), font_style='Subtitle2', bold=True,
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface'),
                valign='middle'
            ))
            info.add_widget(MDLabel(
                text=f"{acc.get('account_type','').replace('_',' ').title()}  •  Bal: {_fmt(acc.get('balance_minor',0))}",
                font_style='Caption', theme_text_color='Custom',
                text_color=(1, 1, 1, 0.8) if active else get_color('outline'),
                valign='middle'
            ))
            card.add_widget(info)
            if active:
                card.add_widget(MDIcon(
                    icon='check-circle', theme_text_color='Custom',
                    text_color=(1, 1, 1, 1), size_hint_x=None, width=dp(28),
                    valign='middle'
                ))
            self.account_box.add_widget(card)

    def _select_account(self, acc):
        self._selected_account_id = acc['id']
        self._render_accounts(self._accounts)

    def _confirm(self, *args):
        if not self.member_id:
            self.show_error('Search and select a member first')
            return
        if not self._selected_account_id:
            self.show_error('Select an account')
            return
        amount = _to_minor(self.amount_field.text)
        if amount <= 0:
            self.show_error('Enter a valid amount')
            return
        acc = next((a for a in self._accounts if a['id'] == self._selected_account_id), {})
        dialog = MDDialog(
            title='Confirm Deposit',
            text=f"Deposit [b]{_fmt(amount)}[/b] into {acc.get('account_no', '')}?",
            buttons=[
                MDFlatButton(text='CANCEL', on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text='CONFIRM', md_bg_color=get_color('success'),
                    on_release=lambda x: (dialog.dismiss(), self._execute(amount))
                )
            ]
        )
        dialog.open()

    def _execute(self, amount):
        self.submit_btn.disabled = True
        self.submit_btn.text = 'Processing…'
        desc = self.desc_field.text.strip() or 'Cash deposit'
        threading.Thread(target=self._run, args=(amount, desc), daemon=True).start()

    def _run(self, amount, desc):
        try:
            self.app.account_service.post_transaction(
                self._selected_account_id, 'deposit', amount, desc, channel=self._channel
            )
            acc = self.app.db.fetch_one("SELECT * FROM accounts WHERE id=?", (self._selected_account_id,))
            Clock.schedule_once(lambda dt: self._on_success(amount, acc), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_success(self, amount, acc):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'DEPOSIT'
        self.amount_field.text = ''
        self.desc_field.text = ''
        _receipt_dialog('Deposit Successful', [
            ('Account', acc.get('account_no', '')),
            ('Amount', _fmt(amount)),
            ('New Balance', _fmt(acc.get('balance_minor', 0))),
            ('Date', datetime.datetime.now().strftime('%d %b %Y %H:%M')),
        ], on_dismiss=lambda: threading.Thread(target=self._load_accounts, daemon=True).start())

    def _on_error(self, msg):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'DEPOSIT'
        self.show_error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# WITHDRAWAL SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class WithdrawalScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'withdrawal'
        self.member_id = None
        self._accounts = []
        self._selected_account_id = None
        self._selected_acc = {}
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')
        self.toolbar = MDTopAppBar(
            title='Withdraw',
            md_bg_color=get_color('error'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        body = MDBoxLayout(
            orientation='vertical', spacing=dp(14),
            padding=dp(14), size_hint_y=None
        )
        body.bind(minimum_height=body.setter('height'))

        # Member search
        search_row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.member_search = MDTextField(
            hint_text='Search member…', mode='rectangle',
            line_color_focus=get_color('error')
        )
        search_row.add_widget(self.member_search)
        search_row.add_widget(MDRaisedButton(
            text='Find', md_bg_color=get_color('error'),
            size_hint_x=None, width=dp(70),
            on_release=lambda x: self._search_member()
        ))
        body.add_widget(search_row)

        # Balance banner
        self.balance_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(70),
            radius=[dp(10)], padding=dp(14),
            md_bg_color=get_color('error'), elevation=3
        )
        self.balance_card.add_widget(MDLabel(
            text='Available Balance', font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.8),
            size_hint_y=None, height=dp(20),
            valign='middle'
        ))
        self.balance_lbl = MDLabel(
            text='KSh 0.00', font_style='H5', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            valign='middle'
        )
        self.balance_card.add_widget(self.balance_lbl)
        body.add_widget(self.balance_card)

        # Account picker
        body.add_widget(self._sec('From Account', 'bank-minus'))
        self.account_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.account_box.bind(minimum_height=self.account_box.setter('height'))
        body.add_widget(self.account_box)

        # Amount
        body.add_widget(self._sec('Amount (KSh)', 'cash-minus'))
        self.amount_field = MDTextField(
            hint_text='0.00', mode='rectangle',
            input_filter='float', font_size=sp(22),
            line_color_focus=get_color('error'),
            size_hint_y=None, height=dp(60)
        )
        body.add_widget(self.amount_field)

        chips = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for amt in [500, 1000, 2000, 5000, 10000]:
            c = MDCard(
                size_hint=(None, None), size=(dp(74), dp(36)),
                radius=[dp(18)],
                md_bg_color=get_color('error_container', 0.4),
                ripple_behavior=True,
                on_release=lambda x, a=amt: setattr(self.amount_field, 'text', str(a))
            )
            c.add_widget(MDLabel(
                text=f'{amt:,}', halign='center', font_style='Caption',
                theme_text_color='Custom', text_color=get_color('error'),
                valign='middle'
            ))
            chips.add_widget(c)
        body.add_widget(chips)

        self.desc_field = MDTextField(
            hint_text='Purpose / Reference',
            mode='rectangle', line_color_focus=get_color('error'),
            size_hint_y=None, height=dp(56)
        )
        body.add_widget(self.desc_field)

        self.submit_btn = MDRaisedButton(
            text='WITHDRAW (Cash)', size_hint_x=1, height=dp(54),
            md_bg_color=get_color('error'), font_size=sp(15),
            on_release=self._confirm
        )
        body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(8)))
        body.add_widget(self.submit_btn)

        # ── Mobile Money shortcut ─────────────────────────────────────────────
        body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(10)))
        mm_card = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(60),
            radius=[dp(14)], padding=[dp(14), dp(8)], spacing=dp(12),
            md_bg_color=get_color('success_container', 0.35),
            ripple_behavior=True, elevation=0,
            on_release=lambda x: self.app.navigate_to('mobile_money', member_id=self.member_id)
        )
        mm_card.add_widget(MDIcon(
            icon='cellphone-arrow-down',
            theme_text_color='Custom', text_color=get_color('success'),
            size_hint=(None, None), size=(dp(32), dp(44)), valign='middle'
        ))
        mm_info = MDBoxLayout(orientation='vertical')
        mm_info.add_widget(MDLabel(
            text='Send to M-Pesa or Airtel Money',
            font_style='Subtitle2', bold=True, valign='middle',
            size_hint_y=None, height=dp(24)
        ))
        mm_info.add_widget(MDLabel(
            text='Instant mobile money transfer',
            font_style='Caption', theme_text_color='Secondary', valign='middle',
            size_hint_y=None, height=dp(18)
        ))
        mm_card.add_widget(mm_info)
        mm_card.add_widget(MDIcon(
            icon='chevron-right',
            theme_text_color='Custom', text_color=get_color('success'),
            size_hint=(None, None), size=(dp(24), dp(44)), valign='middle'
        ))
        body.add_widget(mm_card)

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    def _sec(self, text, icon):
        row = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color('error'), size_hint_x=None, width=dp(22),
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=text.upper(), font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('error'),
            valign='middle'
        ))
        return row

    def on_enter(self):
        if self.member_id:
            threading.Thread(target=self._load_by_id, args=(self.member_id,), daemon=True).start()

    def _search_member(self):
        q = self.member_search.text.strip()
        if not q:
            return
        threading.Thread(target=self._run_search, args=(q,), daemon=True).start()

    def _run_search(self, q):
        try:
            m = self.app.db.fetch_one(
                "SELECT * FROM members WHERE is_active=1 AND "
                "(first_name LIKE ? OR last_name LIKE ? OR phone=? OR id_number=?) LIMIT 1",
                (f'%{q}%', f'%{q}%', q, q)
            )
            if m:
                self.member_id = m['id']
                Clock.schedule_once(lambda dt: threading.Thread(target=self._load_by_id, args=(m['id'],), daemon=True).start(), 0)
            else:
                Clock.schedule_once(lambda dt: self.show_error('Member not found'), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _load_by_id(self, mid):
        try:
            accs = self.app.db.fetch_all(
                "SELECT * FROM accounts WHERE member_id=? AND status='active' AND account_type!='loan'", (mid,)
            )
            Clock.schedule_once(lambda dt: self._render_accounts(accs), 0)
        except Exception as e:
            Logger.error(f'Withdrawal: {e}')

    def _render_accounts(self, accs):
        self._accounts = accs
        self.account_box.clear_widgets()
        if not accs:
            self.account_box.add_widget(MDLabel(
                text='No accounts found', theme_text_color='Secondary',
                size_hint_y=None, height=dp(36),
                valign='middle'
            ))
            return
        if not self._selected_account_id:
            self._select_account(accs[0])
        for acc in accs:
            active = acc['id'] == self._selected_account_id
            card = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(60),
                radius=[dp(10)], padding=dp(12),
                md_bg_color=get_color('error') if active else get_color('surface_variant', 0.2),
                ripple_behavior=True, elevation=2 if active else 0,
                on_release=lambda x, a=acc: self._select_account(a)
            )
            card.add_widget(MDIcon(
                icon='bank', theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('error'),
                size_hint_x=None, width=dp(28),
                valign='middle'
            ))
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(
                text=acc.get('account_no', ''), font_style='Subtitle2',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface'),
                valign='middle'
            ))
            info.add_widget(MDLabel(
                text=f"Available: {_fmt(acc.get('available_balance_minor', acc.get('balance_minor', 0)))}",
                font_style='Caption', theme_text_color='Custom',
                text_color=(1, 1, 1, 0.8) if active else get_color('outline'),
                valign='middle'
            ))
            card.add_widget(info)
            self.account_box.add_widget(card)

    def _select_account(self, acc):
        self._selected_account_id = acc['id']
        self._selected_acc = acc
        avail = acc.get('available_balance_minor', acc.get('balance_minor', 0))
        self.balance_lbl.text = _fmt(avail)
        self._render_accounts(self._accounts)

    def _confirm(self, *args):
        if not self.member_id or not self._selected_account_id:
            self.show_error('Select a member and account first')
            return
        amount = _to_minor(self.amount_field.text)
        if amount <= 0:
            self.show_error('Enter a valid amount')
            return
        avail = self._selected_acc.get('available_balance_minor',
                                        self._selected_acc.get('balance_minor', 0))
        if amount > avail:
            self.show_error(f'Insufficient balance. Available: {_fmt(avail)}')
            return

        dialog = MDDialog(
            title='Confirm Withdrawal',
            text=f"Withdraw [b]{_fmt(amount)}[/b] from {self._selected_acc.get('account_no', '')}?",
            buttons=[
                MDFlatButton(text='CANCEL', on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text='CONFIRM', md_bg_color=get_color('error'),
                    on_release=lambda x: (dialog.dismiss(), self._execute(amount))
                )
            ]
        )
        dialog.open()

    def _execute(self, amount):
        self.submit_btn.disabled = True
        self.submit_btn.text = 'Processing…'
        desc = self.desc_field.text.strip() or 'Cash withdrawal'
        threading.Thread(target=self._run, args=(amount, desc), daemon=True).start()

    def _run(self, amount, desc):
        try:
            self.app.account_service.post_transaction(
                self._selected_account_id, 'withdrawal', amount, desc
            )
            acc = self.app.db.fetch_one("SELECT * FROM accounts WHERE id=?", (self._selected_account_id,))
            Clock.schedule_once(lambda dt: self._on_success(amount, acc), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_success(self, amount, acc):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'WITHDRAW'
        self.amount_field.text = ''
        _receipt_dialog('Withdrawal Successful', [
            ('Account', acc.get('account_no', '')),
            ('Amount', _fmt(amount)),
            ('Balance', _fmt(acc.get('balance_minor', 0))),
            ('Date', datetime.datetime.now().strftime('%d %b %Y %H:%M')),
        ], on_dismiss=lambda: threading.Thread(target=self._load_by_id, args=(self.member_id,), daemon=True).start())

    def _on_error(self, msg):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'WITHDRAW'
        self.show_error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFER SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class TransferScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'transfer'
        self.member_id = None
        self._from_accounts = []
        self._from_id = None
        self._to_account_id = None
        self._to_label = ''
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')
        self.toolbar = MDTopAppBar(
            title='Transfer',
            md_bg_color=get_color('secondary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        body = MDBoxLayout(
            orientation='vertical', spacing=dp(14),
            padding=dp(14), size_hint_y=None
        )
        body.bind(minimum_height=body.setter('height'))

        # From member search
        search_row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.from_search = MDTextField(
            hint_text='From member (name/phone/ID)…',
            mode='rectangle', line_color_focus=get_color('secondary')
        )
        search_row.add_widget(self.from_search)
        search_row.add_widget(MDRaisedButton(
            text='Find', md_bg_color=get_color('secondary'),
            size_hint_x=None, width=dp(70),
            on_release=lambda x: self._search_from()
        ))
        body.add_widget(search_row)

        body.add_widget(self._sec('From Account', 'arrow-top-right'))
        self.from_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.from_box.bind(minimum_height=self.from_box.setter('height'))
        body.add_widget(self.from_box)

        body.add_widget(self._sec('To Account', 'arrow-bottom-left'))
        to_row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.to_search = MDTextField(
            hint_text='Destination account number…',
            mode='rectangle', line_color_focus=get_color('secondary')
        )
        to_row.add_widget(self.to_search)
        to_row.add_widget(MDRaisedButton(
            text='Find', md_bg_color=get_color('secondary'),
            size_hint_x=None, width=dp(70),
            on_release=lambda x: self._search_to()
        ))
        body.add_widget(to_row)

        self.to_result = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(0),
            radius=[dp(10)], padding=dp(12),
            md_bg_color=get_color('secondary_container', 0.3), elevation=0,
            opacity=0
        )
        self.to_lbl = MDLabel(text='', font_style='Subtitle2', valign='middle')
        from kivy.uix.relativelayout import RelativeLayout
        from kivy.graphics import Color as _C, RoundedRectangle as _RR
        ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(28), dp(28)))
        with ic_rl.canvas.before:
            _C(*get_color('success_container', 0.6))
            _RR(pos=(0, 0), size=(dp(28), dp(28)), radius=[dp(14)])
        ic_rl.add_widget(MDIcon(
            icon='check-circle-outline', theme_text_color='Custom',
            text_color=get_color('success'), halign='center', valign='middle',
            font_size=sp(18), size_hint=(None, None), size=(dp(20), dp(20)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        self.to_result.add_widget(ic_rl)
        self.to_result.add_widget(self.to_lbl)
        body.add_widget(self.to_result)

        body.add_widget(self._sec('Amount (KSh)', 'bank-transfer'))
        self.amount_field = MDTextField(
            hint_text='0.00', mode='rectangle',
            input_filter='float', font_size=sp(22),
            line_color_focus=get_color('secondary'),
            size_hint_y=None, height=dp(60)
        )
        body.add_widget(self.amount_field)

        self.desc_field = MDTextField(
            hint_text='Narration / Reference',
            mode='rectangle', line_color_focus=get_color('secondary'),
            size_hint_y=None, height=dp(56)
        )
        body.add_widget(self.desc_field)

        self.submit_btn = MDRaisedButton(
            text='TRANSFER', size_hint_x=1, height=dp(54),
            md_bg_color=get_color('secondary'), font_size=sp(15),
            on_release=self._confirm
        )
        body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(8)))
        body.add_widget(self.submit_btn)

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    def _sec(self, text, icon):
        row = MDBoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color('secondary'), size_hint_x=None, width=dp(22),
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=text.upper(), font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('secondary'),
            valign='middle'
        ))
        return row

    def on_enter(self):
        # Reset destination result card (hide it cleanly every visit)
        self.to_result.height = dp(0)
        self.to_result.opacity = 0
        self.to_lbl.text = ''
        self._to_account_id = None
        self.to_search.text = ''
        self.amount_field.text = ''
        self.desc_field.text = ''
        self.submit_btn.disabled = False
        self.submit_btn.text = 'TRANSFER'
        if self.member_id:
            threading.Thread(target=self._load_from, args=(self.member_id,), daemon=True).start()

    def _search_from(self):
        q = self.from_search.text.strip()
        if not q:
            return
        threading.Thread(target=self._run_from_search, args=(q,), daemon=True).start()

    def _run_from_search(self, q):
        try:
            m = self.app.db.fetch_one(
                "SELECT * FROM members WHERE is_active=1 AND "
                "(first_name LIKE ? OR last_name LIKE ? OR phone=?) LIMIT 1",
                (f'%{q}%', f'%{q}%', q)
            )
            if m:
                self.member_id = m['id']
                Clock.schedule_once(lambda dt: threading.Thread(
                    target=self._load_from, args=(m['id'],), daemon=True
                ).start(), 0)
            else:
                Clock.schedule_once(lambda dt: self.show_error('Member not found'), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _load_from(self, mid):
        try:
            accs = self.app.db.fetch_all(
                "SELECT * FROM accounts WHERE member_id=? AND status='active' AND account_type!='loan'", (mid,)
            )
            Clock.schedule_once(lambda dt: self._render_from(accs), 0)
        except Exception as e:
            Logger.error(f'Transfer from: {e}')

    def _render_from(self, accs):
        self._from_accounts = accs
        self.from_box.clear_widgets()
        if not accs:
            self.from_box.add_widget(MDLabel(text='No accounts', theme_text_color='Secondary', size_hint_y=None, height=dp(36),
                valign='middle'
            ))
            return
        if not self._from_id:
            self._from_id = accs[0]['id']
        for acc in accs:
            active = acc['id'] == self._from_id
            card = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(56),
                radius=[dp(10)], padding=dp(12),
                md_bg_color=get_color('secondary') if active else get_color('surface_variant', 0.2),
                ripple_behavior=True, elevation=1,
                on_release=lambda x, a=acc: self._select_from(a)
            )
            card.add_widget(MDIcon(
                icon='bank', theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('secondary'),
                size_hint_x=None, width=dp(28),
                valign='middle'
            ))
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(
                text=acc.get('account_no', ''), font_style='Subtitle2',
                theme_text_color='Custom', text_color=(1, 1, 1, 1) if active else get_color('on_surface'),
                valign='middle'
            ))
            info.add_widget(MDLabel(
                text=f"Bal: {_fmt(acc.get('balance_minor', 0))}",
                font_style='Caption', theme_text_color='Custom',
                text_color=(1, 1, 1, 0.8) if active else get_color('outline'),
                valign='middle'
            ))
            card.add_widget(info)
            self.from_box.add_widget(card)

    def _select_from(self, acc):
        self._from_id = acc['id']
        self._render_from(self._from_accounts)

    def _search_to(self):
        q = self.to_search.text.strip()
        if not q:
            return
        threading.Thread(target=self._run_to_search, args=(q,), daemon=True).start()

    def _run_to_search(self, q):
        try:
            acc = self.app.db.fetch_one(
                "SELECT a.*, m.first_name, m.last_name FROM accounts a "
                "JOIN members m ON a.member_id=m.id "
                "WHERE a.account_no=? AND a.status='active'", (q,)
            )
            Clock.schedule_once(lambda dt: self._show_to(acc), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _show_to(self, acc):
        if not acc:
            self.show_error('Account not found')
            return
        self._to_account_id = acc['id']
        self._to_label = (
            f"{acc.get('first_name', '')} {acc.get('last_name', '')}  "
            f"•  {acc.get('account_no', '')}"
        )
        self.to_lbl.text = self._to_label
        from kivy.animation import Animation
        Animation(height=dp(52), opacity=1, duration=0.2).start(self.to_result)

    def _confirm(self, *args):
        if not self._from_id:
            self.show_error('Select source account')
            return
        if not self._to_account_id:
            self.show_error('Search and select destination account')
            return
        if self._from_id == self._to_account_id:
            self.show_error('Source and destination cannot be the same')
            return
        amount = _to_minor(self.amount_field.text)
        if amount <= 0:
            self.show_error('Enter valid amount')
            return

        dialog = MDDialog(
            title='Confirm Transfer',
            text=f"Transfer [b]{_fmt(amount)}[/b] to [b]{self._to_label}[/b]?",
            buttons=[
                MDFlatButton(text='CANCEL', on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text='TRANSFER', md_bg_color=get_color('secondary'),
                    on_release=lambda x: (dialog.dismiss(), self._execute(amount))
                )
            ]
        )
        dialog.open()

    def _execute(self, amount):
        self.submit_btn.disabled = True
        self.submit_btn.text = 'Processing…'
        desc = self.desc_field.text.strip() or 'Member transfer'
        threading.Thread(target=self._run, args=(amount, desc), daemon=True).start()

    def _run(self, amount, desc):
        try:
            self.app.account_service.transfer(self._from_id, self._to_account_id, amount, desc)
            Clock.schedule_once(lambda dt: self._on_success(amount), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_success(self, amount):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'TRANSFER'
        self.amount_field.text = ''
        _receipt_dialog('Transfer Successful', [
            ('Amount', _fmt(amount)),
            ('To', self._to_label),
            ('Date', datetime.datetime.now().strftime('%d %b %Y %H:%M')),
        ])

    def _on_error(self, msg):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'TRANSFER'
        self.show_error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# MOBILE MONEY WITHDRAWAL SCREEN  (M-Pesa & Airtel Money)
# ─────────────────────────────────────────────────────────────────────────────

# Official Safaricom M-Pesa B2C charge tiers (KSh, as of 2024)
_MPESA_CHARGES = [
    (1,       100,     0),
    (101,     500,     11),
    (501,     1_000,   29),
    (1_001,   1_500,   29),
    (1_501,   2_500,   29),
    (2_501,   3_500,   52),
    (3_501,   5_000,   69),
    (5_001,   7_500,   87),
    (7_501,   10_000,  115),
    (10_001,  15_000,  167),
    (15_001,  20_000,  197),
    (20_001,  25_000,  228),
    (25_001,  30_000,  261),
    (30_001,  35_000,  294),
    (35_001,  40_000,  326),
    (40_001,  45_000,  356),
    (45_001,  70_000,  385),
]

# Airtel Money charges (KSh, as of 2024)
_AIRTEL_CHARGES = [
    (1,       100,     0),
    (101,     500,     10),
    (501,     1_000,   25),
    (1_001,   2_500,   30),
    (2_501,   5_000,   55),
    (5_001,   10_000,  90),
    (10_001,  20_000,  160),
    (20_001,  35_000,  250),
    (35_001,  50_000,  340),
    (50_001,  70_000,  385),
]


def _get_charge(amount_ksh, table):
    """Return transaction charge in KSh for given amount using charge table."""
    for lo, hi, charge in table:
        if lo <= amount_ksh <= hi:
            return charge
    return 385  # cap


def _fmt_ksh(ksh):
    return f"KSh {ksh:,.2f}"



class MobileMoneyWithdrawalScreen(BaseScreen):
    """
    Mobile Money screen — two modes:
      SEND:    Withdraw from savings → M-Pesa or Airtel Money (B2C)
      RECEIVE: STK Push → member pays into SACCO via M-Pesa (C2B)
    """

    # ── PROVIDER CONFIG ───────────────────────────────────────────────────────
    PROVIDERS = {
        'mpesa': {
            'name':    'M-Pesa',
            'short':   'M-PESA',
            'icon':    'alpha-m-circle',
            'color':   'success',
            'bg':      '#00A550',
            'charges': _MPESA_CHARGES,
            'prefix':  '254',
            'hint':    '07XX or 01XX number',
            'limit':   70_000,
        },
        'airtel': {
            'name':    'Airtel Money',
            'short':   'AIRTEL',
            'icon':    'alpha-a-circle',
            'color':   'error',
            'bg':      '#E00000',
            'charges': _AIRTEL_CHARGES,
            'prefix':  '254',
            'hint':    '073X or 078X number',
            'limit':   70_000,
        },
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name              = 'mobile_money'
        self.member_id         = None
        self._accounts         = []
        self._selected_account_id = None
        self._provider_key     = 'mpesa'
        self._mode             = 'send'   # 'send' or 'receive'
        self._stk_checkout_id  = None
        self._build()

    # ── BUILD ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Mobile Money',
            md_bg_color=get_color('success'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        self.body = MDBoxLayout(
            orientation='vertical', spacing=dp(12),
            padding=[dp(14), dp(14), dp(14), dp(24)], size_hint_y=None
        )
        self.body.bind(minimum_height=self.body.setter('height'))

        # ── PROVIDER TABS  ────────────────────────────────────────────────────
        provider_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(100),
            radius=[dp(16)], padding=[dp(10), dp(10)], spacing=dp(6),
            md_bg_color=get_color('surface_variant', 0.12), elevation=0
        )
        provider_label = MDLabel(
            text='SELECT PROVIDER', font_style='Caption', bold=True,
            theme_text_color='Secondary',
            size_hint_y=None, height=dp(18), valign='middle', halign='center'
        )
        provider_card.add_widget(provider_label)
        provider_row = MDBoxLayout(size_hint_y=None, height=dp(64), spacing=dp(10))
        self._provider_btns = {}
        for key, p in self.PROVIDERS.items():
            active = key == self._provider_key
            btn = MDCard(
                orientation='vertical', radius=[dp(14)],
                md_bg_color=get_color(p['color']) if active else get_color('surface_variant', 0.25),
                ripple_behavior=True, elevation=4 if active else 0,
                size_hint_y=None, height=dp(64),
                on_release=lambda x, k=key: self._select_provider(k)
            )
            icon_row = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6), padding=[dp(8),0])
            icon_row.add_widget(MDIcon(
                icon=p['icon'], font_size=sp(20),
                theme_text_color='Custom',
                text_color=(1,1,1,1) if active else get_color(p['color']),
                size_hint_x=None, width=dp(24), valign='middle'
            ))
            icon_row.add_widget(MDLabel(
                text=p['name'], font_style='Caption', bold=True,
                theme_text_color='Custom',
                text_color=(1,1,1,1) if active else get_color('on_surface'),
                valign='middle'
            ))
            btn.add_widget(icon_row)
            btn.add_widget(MDLabel(
                text=p['hint'], font_style='Overline',
                theme_text_color='Custom',
                text_color=(1,1,1,0.75) if active else get_color('outline'),
                halign='center', size_hint_y=None, height=dp(16), valign='middle'
            ))
            self._provider_btns[key] = btn
            provider_row.add_widget(btn)
        provider_card.add_widget(provider_row)
        self.body.add_widget(provider_card)

        # ── MODE TABS (SEND / RECEIVE) ─────────────────────────────────────────
        mode_row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self._mode_btns = {}
        mode_defs = [
            ('send',    'WITHDRAW TO PHONE',       'bank-arrow-right'),
            ('receive', 'COLLECT VIA STK PUSH',    'bank-arrow-left'),
        ]
        for mode, label, icon in mode_defs:
            active = mode == self._mode
            btn = MDCard(
                orientation='horizontal', radius=[dp(10)],
                md_bg_color=get_color('primary') if active else get_color('surface_variant', 0.25),
                size_hint_x=1, size_hint_y=None, height=dp(44),
                padding=[dp(8), 0], spacing=dp(6),
                ripple_behavior=True,
                on_release=lambda x, m=mode: self._select_mode(m)
            )
            btn.add_widget(MDIcon(
                icon=icon, font_size=sp(16),
                theme_text_color='Custom',
                text_color=(1,1,1,1) if active else get_color('primary'),
                size_hint_x=None, width=dp(20), valign='middle'
            ))
            btn.add_widget(MDLabel(
                text=label, font_style='Overline', bold=True,
                theme_text_color='Custom',
                text_color=(1,1,1,1) if active else get_color('on_surface'),
                valign='middle'
            ))
            self._mode_btns[mode] = btn
            mode_row.add_widget(btn)
        self.body.add_widget(mode_row)

        # ── LIVE/SANDBOX BADGE ────────────────────────────────────────────────
        badge_row = MDBoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
        self._badge_icon = MDIcon(
            icon='circle', font_size=sp(10),
            theme_text_color='Custom', text_color=get_color('success'),
            size_hint_x=None, width=dp(16), valign='middle'
        )
        self._badge_lbl = MDLabel(
            text='LIVE MODE — real money',
            font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('success'),
            valign='middle'
        )
        badge_row.add_widget(self._badge_icon)
        badge_row.add_widget(self._badge_lbl)
        self.body.add_widget(badge_row)

        # ── MEMBER SEARCH ─────────────────────────────────────────────────────
        search_row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.member_search = MDTextField(
            hint_text='Search member name, phone or ID number…',
            mode='rectangle', line_color_focus=get_color('success')
        )
        search_row.add_widget(self.member_search)
        search_row.add_widget(MDRaisedButton(
            text='Find', md_bg_color=get_color('success'),
            size_hint_x=None, width=dp(70),
            on_release=lambda x: self._search_member()
        ))
        self.body.add_widget(search_row)

        # ── MEMBER + BALANCE BANNER ───────────────────────────────────────────
        self.balance_card = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(72),
            radius=[dp(14)], padding=[dp(14), dp(10)], spacing=dp(10),
            md_bg_color=get_color('success'), elevation=3
        )
        bal_icon_box = MDCard(
            size_hint=(None, None), size=(dp(44), dp(44)),
            radius=[dp(12)], md_bg_color=(1,1,1,0.15), elevation=0
        )
        bal_icon_box.add_widget(MDIcon(
            icon='account-cash', theme_text_color='Custom',
            text_color=(1,1,1,1), halign='center', valign='middle', font_size=sp(22)
        ))
        self.balance_card.add_widget(bal_icon_box)
        bal_info = MDBoxLayout(orientation='vertical', spacing=dp(2))
        self.member_name_lbl = MDLabel(
            text='No member selected', font_style='Subtitle2', bold=True,
            theme_text_color='Custom', text_color=(1,1,1,0.85),
            size_hint_y=None, height=dp(26), valign='middle'
        )
        self.balance_lbl = MDLabel(
            text='—', font_style='Caption',
            theme_text_color='Custom', text_color=(1,1,1,1),
            size_hint_y=None, height=dp(22), valign='middle'
        )
        bal_info.add_widget(self.member_name_lbl)
        bal_info.add_widget(self.balance_lbl)
        self.balance_card.add_widget(bal_info)
        self.body.add_widget(self.balance_card)

        # ── ACCOUNT PICKER ────────────────────────────────────────────────────
        self.body.add_widget(self._sec_hdr('Savings Account', 'bank', 'primary'))
        self.account_box = MDBoxLayout(orientation='vertical', spacing=dp(6), size_hint_y=None)
        self.account_box.bind(minimum_height=self.account_box.setter('height'))
        self.body.add_widget(self.account_box)

        # ── PHONE FIELD ───────────────────────────────────────────────────────
        self._phone_hdr = self._sec_hdr('Send to Phone', 'phone-arrow-right', 'success')
        self.body.add_widget(self._phone_hdr)

        # Phone row with beneficiary button
        phone_row = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.phone_field = MDTextField(
            hint_text='07XX XXX XXX',
            mode='rectangle', input_filter='int',
            line_color_focus=get_color('success'),
        )
        self.phone_field.bind(text=self._on_amount_changed)
        phone_row.add_widget(self.phone_field)
        phone_row.add_widget(MDRaisedButton(
            text='📋', size_hint_x=None, width=dp(46), height=dp(46),
            md_bg_color=get_color('success', 0.7),
            on_release=lambda x: self._show_beneficiaries()
        ))
        self.body.add_widget(phone_row)

        self.phone_confirm_field = MDTextField(
            hint_text='Confirm phone number',
            mode='rectangle', input_filter='int',
            line_color_focus=get_color('success'),
            size_hint_y=None, height=dp(56)
        )
        self.body.add_widget(self.phone_confirm_field)

        # ── AMOUNT ────────────────────────────────────────────────────────────
        self._amount_hdr = self._sec_hdr('Amount (KSh)', 'cash', 'success')
        self.body.add_widget(self._amount_hdr)
        self.amount_field = MDTextField(
            hint_text='0.00', mode='rectangle',
            input_filter='float', font_size=sp(22),
            line_color_focus=get_color('success'),
            size_hint_y=None, height=dp(60)
        )
        self.amount_field.bind(text=self._on_amount_changed)
        self.body.add_widget(self.amount_field)

        # Quick chips
        chips = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for amt in [500, 1_000, 2_000, 5_000, 10_000]:
            c = MDCard(
                size_hint=(None, None), size=(dp(74), dp(36)),
                radius=[dp(18)],
                md_bg_color=get_color('success_container', 0.4),
                ripple_behavior=True,
                on_release=lambda x, a=amt: self._set_amount(a)
            )
            c.add_widget(MDLabel(
                text=f'{amt:,}', halign='center', font_style='Caption',
                theme_text_color='Custom', text_color=get_color('success'), valign='middle'
            ))
            chips.add_widget(c)
        self.body.add_widget(chips)

        # ── CHARGE BREAKDOWN (SEND mode) ──────────────────────────────────────
        self.charge_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(140),
            radius=[dp(12)], padding=[dp(16), dp(12)], spacing=dp(6),
            md_bg_color=get_color('surface_variant', 0.18), elevation=0
        )
        self.charge_card.add_widget(MDLabel(
            text='TRANSACTION BREAKDOWN', font_style='Caption', bold=True,
            theme_text_color='Secondary', size_hint_y=None, height=dp(18), valign='middle'
        ))
        for attr, label, color in [
            ('charge_withdraw_lbl', 'Deducted from savings',  'on_surface'),
            ('charge_fee_lbl',      'Provider charge',        'error'),
            ('charge_receive_lbl',  'They will receive',       'success'),
        ]:
            row = MDBoxLayout(size_hint_y=None, height=dp(28))
            row.add_widget(MDLabel(
                text=label, font_style='Caption',
                theme_text_color='Secondary', valign='middle', size_hint_x=0.55
            ))
            lbl = MDLabel(
                text='—', font_style='Body2', bold=(color == 'success'),
                halign='right', valign='middle',
                theme_text_color='Custom',
                text_color=get_color(color) if color != 'on_surface' else get_color('on_surface'),
                size_hint_x=0.45
            )
            row.add_widget(lbl)
            setattr(self, attr, lbl)
            self.charge_card.add_widget(row)
        self.charge_limit_lbl = MDLabel(
            text='', font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(18), valign='middle'
        )
        self.charge_card.add_widget(self.charge_limit_lbl)
        self.body.add_widget(self.charge_card)

        # ── STK PUSH INFO (RECEIVE mode) ──────────────────────────────────────
        self.stk_info_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(100),
            radius=[dp(12)], padding=[dp(14), dp(10)], spacing=dp(6),
            md_bg_color=get_color('primary_container', 0.2), elevation=0
        )
        self.stk_info_card.add_widget(MDLabel(
            text='HOW STK PUSH WORKS', font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('primary'),
            size_hint_y=None, height=dp(20), valign='middle'
        ))
        for step in [
            '1. Enter amount + member phone below and tap Collect',
            '2. Member''s phone shows M-Pesa payment prompt',
            '3. Member enters PIN → money credited to their savings',
        ]:
            self.stk_info_card.add_widget(MDLabel(
                text=step, font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(20), valign='middle'
            ))
        self.body.add_widget(self.stk_info_card)

        # ── REF FIELD ─────────────────────────────────────────────────────────
        self.ref_field = MDTextField(
            hint_text='Reason / Reference (optional)',
            mode='rectangle', line_color_focus=get_color('success'),
            size_hint_y=None, height=dp(52)
        )
        self.body.add_widget(self.ref_field)

        # ── SUBMIT BUTTON ─────────────────────────────────────────────────────
        self.body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(6)))
        self.submit_btn = MDRaisedButton(
            text='SEND MONEY', size_hint_x=1, height=dp(54),
            md_bg_color=get_color('success'), font_size=sp(15),
            on_release=self._confirm
        )
        self.body.add_widget(self.submit_btn)

        self.body.add_widget(MDLabel(
            text='Charges deducted from savings with the withdrawal amount.',
            font_style='Caption', theme_text_color='Secondary',
            halign='center', size_hint_y=None, height=dp(30)
        ))

        # ── RECENT TRANSACTIONS ───────────────────────────────────────────────
        self.body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(12)))
        self.body.add_widget(self._sec_hdr('Recent Mobile Money', 'history', 'outline'))
        self.recent_mm_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.recent_mm_box.bind(minimum_height=self.recent_mm_box.setter('height'))
        self.recent_mm_box.add_widget(MDLabel(
            text='Select a member to see recent transfers',
            font_style='Caption', theme_text_color='Secondary',
            halign='center', size_hint_y=None, height=dp(30)
        ))
        self.body.add_widget(self.recent_mm_box)

        scroll.add_widget(self.body)
        root.add_widget(scroll)
        self.add_widget(root)

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _sec_hdr(self, text, icon, color):
        row = MDBoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color(color), size_hint_x=None, width=dp(20), valign='middle',
            font_size=sp(16)
        ))
        row.add_widget(MDLabel(
            text=text.upper(), font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color(color), valign='middle'
        ))
        return row

    def _set_amount(self, amt):
        self.amount_field.text = str(amt)

    def _select_provider(self, key):
        self._provider_key = key
        p = self.PROVIDERS[key]
        self.toolbar.md_bg_color = get_color(p['color'])
        for k, btn in self._provider_btns.items():
            active  = k == key
            bp      = self.PROVIDERS[k]
            btn.md_bg_color = get_color(bp['color']) if active else get_color('surface_variant', 0.25)
            btn.elevation   = 4 if active else 0
            for i, child in enumerate(reversed(list(btn.children))):
                # icon_row children: icon + label; also hint label
                if hasattr(child, 'text_color'):
                    if active:
                        child.text_color = (1,1,1,1) if i < 2 else (1,1,1,0.75)
                    else:
                        child.text_color = get_color(bp['color']) if i == 0 else get_color('outline')
                elif hasattr(child, 'children'):
                    for sub in child.children:
                        if hasattr(sub, 'text_color'):
                            sub.text_color = (1,1,1,1) if active else get_color('on_surface' if i > 0 else bp['color'])
        self.phone_field.hint_text = p['hint']
        # Hide STK receive for Airtel (not supported yet)
        if key == 'airtel':
            if self._mode == 'receive':
                self._select_mode('send')
            for m, btn in self._mode_btns.items():
                btn.opacity  = 1 if m == 'send' else 0.35
                btn.disabled = m == 'receive'
        else:
            for btn in self._mode_btns.values():
                btn.opacity  = 1
                btn.disabled = False
        self._on_amount_changed()

    def _select_mode(self, mode):
        self._mode = mode
        send = mode == 'send'
        for m, btn in self._mode_btns.items():
            active = m == mode
            btn.md_bg_color = get_color('primary') if active else get_color('surface_variant', 0.25)
            for child in btn.children:
                if hasattr(child, 'text_color'):
                    child.text_color = (1,1,1,1) if active else get_color('on_surface')
        # Show/hide SEND-only widgets
        self.charge_card.opacity   = 1 if send else 0
        self.charge_card.disabled  = not send
        self.stk_info_card.opacity = 0 if send else 1
        self.phone_confirm_field.opacity  = 1 if send else 0
        self.phone_confirm_field.disabled = not send
        # Update headers + button
        if send:
            self._phone_hdr.children[0].text  = 'Send to Phone'
            self.submit_btn.text               = 'SEND MONEY'
            self.submit_btn.md_bg_color        = get_color('success')
        else:
            self._phone_hdr.children[0].text  = 'Collect From Phone (STK Push)'
            self.submit_btn.text               = 'COLLECT VIA M-PESA'
            self.submit_btn.md_bg_color        = get_color('primary')

    def _on_amount_changed(self, *args):
        try:
            amount_ksh = float(self.amount_field.text or '0')
        except ValueError:
            amount_ksh = 0
        p      = self.PROVIDERS[self._provider_key]
        charge = _get_charge(amount_ksh, p['charges']) if amount_ksh > 0 else 0
        total  = amount_ksh + charge

        self.charge_withdraw_lbl.text = _fmt_ksh(total)   if amount_ksh > 0 else '—'
        self.charge_fee_lbl.text      = f'-{_fmt_ksh(charge)}' if amount_ksh > 0 else '—'
        self.charge_receive_lbl.text  = _fmt_ksh(amount_ksh) if amount_ksh > 0 else '—'
        if amount_ksh > p['limit']:
            self.charge_limit_lbl.text       = f"⚠ Max: {_fmt_ksh(p['limit'])}"
            self.charge_limit_lbl.text_color = get_color('error')
        else:
            self.charge_limit_lbl.text       = f"Max {_fmt_ksh(p['limit'])}  •  Charge: {_fmt_ksh(charge)}"
            self.charge_limit_lbl.text_color = get_color('outline')

    # ── LIFECYCLE ─────────────────────────────────────────────────────────────

    def on_enter(self):
        try:
            from services_mobile_money import _get_setting as _mm_get
            sandbox = _mm_get(self.app.db, 'mpesa_sandbox', '0') == '1'
            if sandbox:
                self._badge_lbl.text       = 'SANDBOX MODE — test only'
                self._badge_lbl.text_color = get_color('warning')
                self._badge_icon.text_color= get_color('warning')
            else:
                self._badge_lbl.text       = 'LIVE MODE — real money'
                self._badge_lbl.text_color = get_color('success')
                self._badge_icon.text_color= get_color('success')
        except Exception:
            pass
        self._select_mode(self._mode)
        self._select_provider(self._provider_key)
        if self.member_id:
            threading.Thread(target=self._load_by_id, args=(self.member_id,), daemon=True).start()

    def _load_by_id(self, mid):
        try:
            member = self.app.db.fetch_one("SELECT * FROM members WHERE id=?", (mid,))
            accs   = self.app.db.fetch_all(
                "SELECT * FROM accounts WHERE member_id=? AND account_type='savings' AND status='active'",
                (mid,)
            )
            Clock.schedule_once(lambda dt: self._populate(member, accs), 0)
        except Exception as e:
            Logger.error(f'MobileMoney load_by_id: {e}')

    def _populate(self, member, accs):
        if not member:
            return
        fname = member.get('first_name','')
        lname = member.get('last_name','')
        self.member_name_lbl.text = f"{fname} {lname}".strip() or 'Unknown'
        # Auto-fill phone
        phone = member.get('phone','')
        if phone and not self.phone_field.text:
            self.phone_field.text = phone
        self._accounts = accs or []
        self.account_box.clear_widgets()
        if not self._accounts:
            self.account_box.add_widget(MDLabel(
                text='No active savings account', theme_text_color='Secondary',
                size_hint_y=None, height=dp(36), halign='center'
            ))
            return
        for acc in self._accounts:
            bal  = (acc.get('balance_minor') or 0) / 100
            name = acc.get('account_name') or acc.get('product_name') or 'Savings'
            row  = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(52),
                radius=[dp(10)], padding=[dp(12), dp(4)], spacing=dp(8),
                md_bg_color=get_color('success_container', 0.15),
                ripple_behavior=True, elevation=0,
                on_release=lambda x, a=acc: self._pick_account(a)
            )
            selected = self._selected_account_id == acc['id']
            if selected:
                row.md_bg_color = get_color('success', 0.15)
            info = MDBoxLayout(orientation='vertical', spacing=dp(2))
            info.add_widget(MDLabel(
                text=name, font_style='Subtitle2', bold=selected,
                theme_text_color='Custom',
                text_color=get_color('success') if selected else get_color('on_surface'),
                size_hint_y=None, height=dp(24), valign='middle'
            ))
            info.add_widget(MDLabel(
                text=f"KSh {bal:,.2f}", font_style='Caption',
                theme_text_color='Secondary',
                size_hint_y=None, height=dp(18), valign='middle'
            ))
            row.add_widget(info)
            if selected:
                row.add_widget(MDIcon(
                    icon='check-circle', theme_text_color='Custom',
                    text_color=get_color('success'),
                    size_hint_x=None, width=dp(24), valign='middle'
                ))
            self.account_box.add_widget(row)
        # Auto-select first account
        if not self._selected_account_id and self._accounts:
            self._pick_account(self._accounts[0])
        # Load recent MM transactions for this member
        threading.Thread(target=self._load_recent_mm, daemon=True).start()

    def _pick_account(self, acc):
        self._selected_account_id = acc['id']
        bal = (acc.get('balance_minor') or 0) / 100
        self.balance_lbl.text = f"Balance: KSh {bal:,.2f}"
        self._populate(
            self.app.db.fetch_one("SELECT * FROM members WHERE id=?", (acc['member_id'],)),
            self._accounts
        )

    def _search_member(self):
        q = self.member_search.text.strip()
        if not q:
            return
        threading.Thread(target=self._run_search, args=(q,), daemon=True).start()

    def _run_search(self, q):
        try:
            like = f'%{q}%'
            rows = self.app.db.fetch_all(
                "SELECT * FROM members WHERE is_active=1 AND ("
                "first_name LIKE ? OR last_name LIKE ? OR "
                "phone LIKE ? OR id_number LIKE ? OR member_no LIKE ?) LIMIT 10",
                (like, like, like, like, like)
            )
            Clock.schedule_once(lambda dt: self._show_search_results(rows), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _show_search_results(self, rows):
        if not rows:
            self.show_error('No members found')
            return
        if len(rows) == 1:
            self.member_id = rows[0]['id']
            threading.Thread(target=self._load_by_id, args=(rows[0]['id'],), daemon=True).start()
            return
        from kivymd.uix.dialog import MDDialog
        content = MDBoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        content.bind(minimum_height=content.setter('height'))
        dlg = [None]
        for r in rows:
            name = f"{r.get('first_name','')} {r.get('last_name','')}".strip()
            phone = r.get('phone','')
            btn = MDRaisedButton(
                text=f"{name}  {phone}", size_hint_x=1,
                md_bg_color=get_color('success'),
                on_release=lambda x, mid=r['id']: (
                    dlg[0].dismiss(),
                    setattr(self, 'member_id', mid),
                    threading.Thread(target=self._load_by_id, args=(mid,), daemon=True).start()
                )
            )
            content.add_widget(btn)
        content.height = len(rows) * dp(50)
        dlg[0] = MDDialog(title='Select Member', type='custom', content_cls=content,
                          buttons=[MDFlatButton(text='CANCEL', on_release=lambda x: dlg[0].dismiss())])
        dlg[0].open()

    # ── CONFIRM & SUBMIT ──────────────────────────────────────────────────────

    def _confirm(self, *args):
        if not self._selected_account_id:
            self.show_error('Select a member and account first')
            return
        phone = self.phone_field.text.strip()
        if not phone or len(phone) < 9:
            self.show_error('Enter a valid phone number')
            return
        if self._mode == 'send' and phone != self.phone_confirm_field.text.strip():
            self.show_error('Phone numbers do not match — re-enter to confirm')
            return
        # Network mismatch check
        from services_mobile_money import normalize_phone, classify_network
        try:
            phone_254 = normalize_phone(phone)
            network   = classify_network(phone_254)
            if self._provider_key == 'mpesa' and network == 'airtel':
                self.show_error(f'⚠ {phone_254} is an Airtel number. Switch to Airtel Money.')
                return
            if self._provider_key == 'airtel' and network == 'mpesa':
                self.show_error(f'⚠ {phone_254} is a Safaricom number. Switch to M-Pesa.')
                return
        except ValueError as e:
            self.show_error(str(e))
            return

        try:
            amount_ksh = float(self.amount_field.text or '0')
        except ValueError:
            self.show_error('Enter a valid amount')
            return
        if amount_ksh <= 0:
            self.show_error('Amount must be greater than zero')
            return

        p          = self.PROVIDERS[self._provider_key]
        charge_ksh = _get_charge(amount_ksh, p['charges']) if self._mode == 'send' else 0
        total      = amount_ksh + charge_ksh
        ref        = self.ref_field.text.strip()
        provider   = p['name']

        if self._mode == 'send':
            acc = self._get_selected_acc()
            bal = (acc.get('balance_minor') or 0) / 100 if acc else 0
            if total > bal:
                self.show_error(f'Insufficient balance. Available: KSh {bal:,.2f}')
                return
            lines = [
                ('Provider',        provider),
                ('Send to',         phone_254),
                ('Amount to send',  _fmt_ksh(amount_ksh)),
                ('Provider charge', _fmt_ksh(charge_ksh)),
                ('Total deducted',  _fmt_ksh(total)),
                ('Remaining bal.',  _fmt_ksh(bal - total)),
            ]
            if ref:
                lines.append(('Reference', ref))
        else:
            lines = [
                ('STK Push to',   phone_254),
                ('Amount',        _fmt_ksh(amount_ksh)),
                ('On success',    'Credit to member savings'),
            ]

        self.confirm_dialog(
            title=f"{'Send' if self._mode=='send' else 'Collect'} via {provider}?",
            text='\n'.join(f"{k}:  {v}" for k, v in lines),
            on_confirm=lambda: threading.Thread(
                target=self._run,
                args=(amount_ksh, charge_ksh, total, phone_254, provider, ref),
                daemon=True
            ).start()
        )

    def _get_selected_acc(self):
        for a in self._accounts:
            if a['id'] == self._selected_account_id:
                return a
        return {}

    def _run(self, amount_ksh, charge_ksh, total_ksh, phone, provider, ref):
        try:
            from services_mobile_money import MMResult
            import uuid as _uuid
            mobile_ref = f"MM{_uuid.uuid4().hex[:10].upper()}"

            Clock.schedule_once(lambda dt: setattr(
                self.submit_btn, 'text',
                f'Calling {self._provider_key.upper()} API…'
            ), 0)

            mm_svc = self.app.mobile_money_service

            if self._mode == 'send':
                result = mm_svc.send(
                    phone=phone,
                    amount_ksh=amount_ksh,
                    provider=self._provider_key,
                    remarks=f"SACCO withdrawal | {ref}" if ref else "SACCO Withdrawal",
                    reference=mobile_ref,
                )
                if result['status'] not in (MMResult.SUCCESS, MMResult.PENDING):
                    raise RuntimeError(result.get('message') or 'Transfer rejected')

                # Deduct from savings
                amount_minor = int(round(amount_ksh * 100))
                charge_minor = int(round(charge_ksh * 100))
                total_minor  = int(round(total_ksh  * 100))
                api_ref = result.get('conversation_id') or result.get('airtel_id') or mobile_ref
                desc = (
                    f"{provider} withdrawal to {phone} | "
                    f"Ref: {mobile_ref} | API: {api_ref}"
                )
                self.app.account_service.post_transaction(
                    self._selected_account_id, 'withdrawal', total_minor,
                    desc, channel='mobile_money',
                    narrative=f'{provider} withdrawal to {phone}',
                    reference_number=mobile_ref,
                )
                # Update log with account link
                try:
                    self.app.db.execute(
                        "UPDATE mobile_money_transactions SET account_id=?, charge_ksh=? WHERE reference=?",
                        (self._selected_account_id, charge_ksh, mobile_ref)
                    )
                except Exception:
                    pass

                acc = self.app.db.fetch_one("SELECT * FROM accounts WHERE id=?", (self._selected_account_id,))
                Clock.schedule_once(lambda dt: self._on_send_success(
                    amount_ksh, charge_ksh, phone, provider, mobile_ref, api_ref, acc, result
                ), 0)
                # Auto-save beneficiary
                self._save_beneficiary(phone)

            else:
                # STK Push — collect FROM phone INTO savings
                acc_row = self.app.db.fetch_one("SELECT * FROM accounts WHERE id=?", (self._selected_account_id,))
                acct_ref = (acc_row.get('account_number') or 'SACCO')[:12]
                result = mm_svc.receive_stk_push(
                    phone=phone,
                    amount_ksh=amount_ksh,
                    account_ref=acct_ref,
                    description='SACCO Deposit'[:13],
                )
                if result['status'] not in (MMResult.SUCCESS, MMResult.PENDING):
                    raise RuntimeError(result.get('message') or 'STK Push failed')

                self._stk_checkout_id = result.get('checkout_id','')
                Clock.schedule_once(lambda dt: self._on_stk_pending(
                    amount_ksh, phone, provider, result
                ), 0)

        except Exception as e:
            Logger.error(f'MobileMoney._run: {e}')
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_send_success(self, amount_ksh, charge_ksh, phone, provider, ref, api_ref, acc, api_result):
        self.submit_btn.disabled = False
        self.submit_btn.text     = 'SEND MONEY'
        self.amount_field.text   = ''
        self.phone_confirm_field.text = ''
        from services_mobile_money import MMResult
        status_note = (
            'Sent ✓ (Confirmed)' if api_result.get('status') == MMResult.SUCCESS
            else 'Queued ✓ — SMS arrives in seconds'
        )
        lines = [
            ('Provider',        provider),
            ('Sent to',         phone),
            ('Amount sent',     _fmt_ksh(amount_ksh)),
            ('Charge',          _fmt_ksh(charge_ksh)),
            ('Total deducted',  _fmt_ksh(amount_ksh + charge_ksh)),
            ('New balance',     _fmt_ksh((acc.get('balance_minor') or 0) / 100) if acc else '—'),
            ('Our Reference',   ref),
        ]
        if api_ref and api_ref != ref:
            lines.append(('API Reference', api_ref[:30]))
        lines.append(('Status', status_note))
        _receipt_dialog(f'{provider} {status_note}', lines,
            on_dismiss=lambda: threading.Thread(
                target=self._load_by_id, args=(self.member_id,), daemon=True
            ).start() if self.member_id else None
        )

    def _on_stk_pending(self, amount_ksh, phone, provider, result):
        self.submit_btn.disabled = False
        self.submit_btn.text     = 'COLLECT VIA M-PESA'
        checkout_id = result.get('checkout_id', '')
        msg = result.get('message', 'Check phone for M-Pesa prompt')

        # Show a dialog with CHECK STATUS + MANUAL CONFIRM buttons
        status_lbl = [None]  # mutable ref so nested fn can update it
        dlg = [None]

        def _check_status():
            """Poll Daraja for STK result and auto-credit if confirmed."""
            if not checkout_id:
                self.show_error('No checkout ID — cannot query status')
                return
            if status_lbl[0]:
                status_lbl[0].text = 'Checking with Safaricom…'

            def _poll():
                try:
                    mm = self.app.mobile_money_service
                    r = mm.poll_stk_status(checkout_id)
                    rc = str(r.get('ResultCode', r.get('errorCode', '-1')))
                    if rc == '0':
                        # SUCCESS — credit savings now
                        Clock.schedule_once(
                            lambda dt: self._credit_savings_stk(amount_ksh, phone, checkout_id, dlg[0]), 0
                        )
                    elif rc in ('1032', '1037', '17'):
                        Clock.schedule_once(
                            lambda dt: _update('Cancelled by user — no charge'), 0)
                    elif rc == '1':
                        Clock.schedule_once(
                            lambda dt: _update('Insufficient M-Pesa balance'), 0)
                    else:
                        desc = r.get('ResultDesc', r.get('errorMessage', f'Code {rc}'))
                        Clock.schedule_once(
                            lambda dt, d=desc: _update(f'Pending / Unknown: {d}'), 0)
                except Exception as e:
                    Clock.schedule_once(
                        lambda dt, _e=str(e): _update(f'Error: {_e[:100]}'), 0)

            def _update(txt):
                if status_lbl[0]:
                    status_lbl[0].text = txt

            threading.Thread(target=_poll, daemon=True).start()

        def _manual_confirm():
            """Admin manually confirms the STK was paid — credits savings directly."""
            if dlg[0]:
                dlg[0].dismiss()
            self._credit_savings_stk(amount_ksh, phone, checkout_id, None)

        content = MDBoxLayout(orientation='vertical', spacing=dp(8),
                              size_hint_y=None, height=dp(190))
        content.add_widget(MDLabel(
            text=f'STK prompt sent to {phone}', font_style='Subtitle2', bold=True,
            theme_text_color='Custom', text_color=get_color('success'),
            size_hint_y=None, height=dp(26), valign='middle'
        ))
        content.add_widget(MDLabel(
            text=msg, font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(20), valign='middle'
        ))
        content.add_widget(MDLabel(
            text=f'Amount: {_fmt_ksh(amount_ksh)}',
            font_style='Body2', theme_text_color='Custom',
            text_color=get_color('on_surface'),
            size_hint_y=None, height=dp(22), valign='middle'
        ))
        sl = MDLabel(
            text='Waiting for member to enter PIN…',
            font_style='Caption', theme_text_color='Custom',
            text_color=get_color('warning'),
            size_hint_y=None, height=dp(20), valign='middle'
        )
        status_lbl[0] = sl
        content.add_widget(sl)
        content.add_widget(MDLabel(
            text='• Tap CHECK STATUS to query Daraja\n'
                 '• If member paid but status unclear, use MANUAL CONFIRM',
            font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(52), valign='top'
        ))

        dlg[0] = MDDialog(
            title='STK Push Sent ✓',
            type='custom',
            content_cls=content,
            buttons=[
                MDFlatButton(text='CLOSE', on_release=lambda x: dlg[0].dismiss()),
                MDRaisedButton(
                    text='CHECK STATUS',
                    md_bg_color=get_color('info'),
                    on_release=lambda x: _check_status()
                ),
                MDRaisedButton(
                    text='MANUAL CONFIRM',
                    md_bg_color=get_color('success'),
                    on_release=lambda x: _manual_confirm()
                ),
            ]
        )
        dlg[0].open()

    def _credit_savings_stk(self, amount_ksh, phone, checkout_id, dlg):
        """Credit member savings after STK push confirmed (manual or auto)."""
        if not self._selected_account_id:
            self.show_error('No account selected — cannot credit savings')
            return
        if dlg:
            dlg.dismiss()

        def _run():
            try:
                amount_minor = int(round(amount_ksh * 100))
                desc = f"M-Pesa STK deposit from {phone} | CID: {checkout_id[:20]}"
                self.app.account_service.post_transaction(
                    self._selected_account_id, 'deposit', amount_minor,
                    desc, channel='mobile_money',
                    narrative=f'M-Pesa deposit via STK Push',
                    reference_number=checkout_id[:30] if checkout_id else None,
                )
                # Update mobile money log
                try:
                    self.app.db.execute(
                        "UPDATE mobile_money_transactions SET status='completed', "
                        "updated_at=datetime('now') WHERE conversation_id=?",
                        (checkout_id,)
                    )
                except Exception:
                    pass
                acc = self.app.db.fetch_one(
                    "SELECT * FROM accounts WHERE id=?", (self._selected_account_id,))
                Clock.schedule_once(lambda dt: self._show_stk_success(amount_ksh, phone, acc), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt, _e=str(e): self.show_error(f'Credit failed: {_e}'), 0)

        threading.Thread(target=_run, daemon=True).start()

    def _show_stk_success(self, amount_ksh, phone, acc):
        bal = (acc.get('balance_minor') or 0) / 100 if acc else 0
        _receipt_dialog('Deposit Credited ✓', [
            ('Received from', phone),
            ('Amount',        _fmt_ksh(amount_ksh)),
            ('New balance',   _fmt_ksh(bal)),
            ('Channel',       'M-Pesa STK Push'),
        ])
        if self.member_id:
            threading.Thread(target=self._load_by_id, args=(self.member_id,), daemon=True).start()

    def _on_error(self, msg):
        self.submit_btn.disabled = False
        self.submit_btn.text     = 'SEND MONEY' if self._mode == 'send' else 'COLLECT VIA M-PESA'
        self.show_error(msg)

    # ── EXTRA: BENEFICIARY BOOK ───────────────────────────────────────────────

    def _show_beneficiaries(self):
        """Show saved beneficiary numbers — tap to fill phone field."""
        try:
            rows = self.app.db.fetch_all(
                "SELECT * FROM beneficiaries WHERE provider=? ORDER BY name",
                (self._provider_key,)
            )
        except Exception:
            rows = []
        if not rows:
            self.show_info('No saved beneficiaries. Save one after a successful transfer.')
            return
        content = MDBoxLayout(orientation='vertical', spacing=dp(6),
                              size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))
        dlg = [None]
        for r in rows:
            name = r.get('name','')
            phone = r.get('phone','')
            row = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(48),
                md_bg_color=get_color('surface_variant', 0.2),
                radius=[dp(8)], padding=[dp(10), 0], spacing=dp(10),
                ripple_behavior=True,
                on_release=lambda x, p=phone: (
                    setattr(self.phone_field, 'text', p),
                    setattr(self.phone_confirm_field, 'text', p),
                    dlg[0].dismiss()
                )
            )
            row.add_widget(MDIcon(
                icon='account-circle', theme_text_color='Custom',
                text_color=get_color(self._provider_key == 'mpesa' and 'success' or 'error'),
                size_hint_x=None, width=dp(28), valign='middle'
            ))
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(text=name or phone, font_style='Body2', bold=True,
                                    size_hint_y=None, height=dp(22), valign='middle'))
            info.add_widget(MDLabel(text=phone, font_style='Caption',
                                    theme_text_color='Secondary',
                                    size_hint_y=None, height=dp(18), valign='middle'))
            row.add_widget(info)
            content.add_widget(row)
        dlg[0] = MDDialog(
            title='Saved Beneficiaries', type='custom', content_cls=content,
            buttons=[MDFlatButton(text='CLOSE', on_release=lambda x: dlg[0].dismiss())]
        )
        dlg[0].open()

    def _save_beneficiary(self, phone, name=''):
        """Save a phone number as beneficiary after successful transfer."""
        try:
            import uuid as _uuid
            self.app.db.execute(
                "CREATE TABLE IF NOT EXISTS beneficiaries "
                "(id TEXT PRIMARY KEY, provider TEXT, phone TEXT, name TEXT, "
                " use_count INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            # Upsert — increment use_count if already saved
            existing = self.app.db.fetch_one(
                "SELECT id, use_count FROM beneficiaries WHERE provider=? AND phone=?",
                (self._provider_key, phone)
            )
            if existing:
                self.app.db.execute(
                    "UPDATE beneficiaries SET use_count=use_count+1 WHERE id=?",
                    (existing['id'],)
                )
            else:
                self.app.db.execute(
                    "INSERT INTO beneficiaries (id, provider, phone, name) VALUES (?,?,?,?)",
                    (str(_uuid.uuid4()), self._provider_key, phone, name)
                )
        except Exception as e:
            Logger.warning(f'Beneficiary save: {e}')

    # ── EXTRA: RECENT MM TRANSACTIONS ─────────────────────────────────────────

    def _load_recent_mm(self):
        """Load and display recent mobile money transactions for this member."""
        try:
            mid = None
            if self.member_id:
                mid = self.member_id
            elif self._selected_account_id:
                acc = self.app.db.fetch_one(
                    "SELECT member_id FROM accounts WHERE id=?", (self._selected_account_id,))
                mid = (acc or {}).get('member_id')
            if not mid:
                return
            rows = self.app.db.fetch_all(
                "SELECT * FROM mobile_money_transactions WHERE member_id=? "
                "ORDER BY created_at DESC LIMIT 8", (mid,)
            )
            Clock.schedule_once(lambda dt: self._show_recent_mm(rows), 0)
        except Exception as e:
            Logger.warning(f'MM recent: {e}')

    def _show_recent_mm(self, rows):
        if not rows:
            return
        # Update the recent_box if it exists
        if not hasattr(self, 'recent_mm_box'):
            return
        self.recent_mm_box.clear_widgets()
        for r in rows:
            status = (r.get('status') or 'pending')
            color = 'success' if status == 'completed' else ('error' if status == 'failed' else 'warning')
            provider = (r.get('provider') or 'mpesa').upper()
            amount = _fmt_ksh(r.get('amount_ksh') or 0)
            phone = r.get('phone', '')
            date = str(r.get('created_at') or '')[:16]
            row = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(52),
                md_bg_color=get_color('surface_variant', 0.15),
                radius=[dp(8)], padding=[dp(10), 0], spacing=dp(8), elevation=0
            )
            status_dot = MDCard(
                size_hint=(None, None), size=(dp(8), dp(8)),
                radius=[dp(4)], md_bg_color=get_color(color), elevation=0
            )
            info = MDBoxLayout(orientation='vertical', spacing=dp(1))
            info.add_widget(MDLabel(
                text=f"{provider}  →  {phone}",
                font_style='Caption', bold=True,
                size_hint_y=None, height=dp(20), valign='middle'
            ))
            info.add_widget(MDLabel(
                text=date, font_style='Caption',
                theme_text_color='Secondary',
                size_hint_y=None, height=dp(16), valign='middle'
            ))
            amt_lbl = MDLabel(
                text=amount, font_style='Body2', bold=True,
                halign='right', valign='middle',
                theme_text_color='Custom', text_color=get_color(color),
                size_hint_x=None, width=dp(90)
            )
            row.add_widget(status_dot)
            row.add_widget(info)
            row.add_widget(amt_lbl)
            self.recent_mm_box.add_widget(row)

