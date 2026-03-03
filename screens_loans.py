# screens_loans.py - Loan Application, Repayment, Schedule screens
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import datetime
import threading

from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen
from screens_transactions import _fmt, _amount_from_text, _receipt_dialog


# ─────────────────────────────────────────────────────────────────────────────
# LOAN APPLICATION SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class LoanApplicationScreen(BaseScreen):

    STEPS = ['product', 'details', 'review']
    STEP_LABELS = ['Product', 'Details', 'Review']
    STEP_COLORS = ['quaternary', 'quinary', 'success']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'loan_application'
        self.member_id = None
        self._products = []
        self._selected_product = None
        self._current_step = 0
        self._fields = {}
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.progress = MDProgressBar(
            value=33, color=get_color('quaternary'),
            size_hint_y=None, height=dp(5)
        )
        root.add_widget(self.progress)

        self.toolbar = MDTopAppBar(
            title='Loan Application',
            md_bg_color=get_color('quaternary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self._prev()]],
        )
        root.add_widget(self.toolbar)

        # Step pills
        self.step_bar = MDBoxLayout(
            size_hint_y=None, height=dp(48),
            padding=[dp(12), dp(6)], spacing=dp(6)
        )
        self._step_btns = []
        for i, (label, color) in enumerate(zip(self.STEP_LABELS, self.STEP_COLORS)):
            btn = MDCard(
                size_hint_x=1, size_hint_y=None, height=dp(36),
                radius=[dp(8)],
                md_bg_color=get_color(color) if i == 0 else get_color('surface_variant', 0.4),
                elevation=2 if i == 0 else 0
            )
            btn.add_widget(MDLabel(
                text=label, halign='center', font_style='Caption',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if i == 0 else get_color('outline'),
                valign='middle'
            ))
            self._step_btns.append(btn)
            self.step_bar.add_widget(btn)
        root.add_widget(self.step_bar)

        self.page_scroll = MDScrollView()
        self.page_box = MDBoxLayout(
            orientation='vertical', spacing=dp(14),
            padding=dp(16), size_hint_y=None
        )
        self.page_box.bind(minimum_height=self.page_box.setter('height'))
        self.page_scroll.add_widget(self.page_box)
        root.add_widget(self.page_scroll)

        nav = MDBoxLayout(
            size_hint_y=None, height=dp(64),
            padding=[dp(16), dp(8)], spacing=dp(12),
            md_bg_color=get_color('surface_variant', 0.2)
        )
        self.prev_btn = MDFlatButton(
            text='← BACK',
            theme_text_color='Custom', text_color=get_color('quaternary'),
            on_release=lambda x: self._prev()
        )
        self.next_btn = MDRaisedButton(
            text='NEXT →',
            md_bg_color=get_color('quaternary'),
            on_release=lambda x: self._next()
        )
        self.submit_btn = MDRaisedButton(
            text='SUBMIT APPLICATION',
            md_bg_color=get_color('success'),
            on_release=lambda x: self._submit(),
            opacity=0, disabled=True
        )
        nav.add_widget(self.prev_btn)
        nav.add_widget(Widget())
        nav.add_widget(self.next_btn)
        nav.add_widget(self.submit_btn)
        root.add_widget(nav)

        self.add_widget(root)
        self._render_step(0)

    # ── step rendering ────────────────────────────────────────────────────────

    def _render_step(self, idx):
        self._current_step = idx
        color = self.STEP_COLORS[idx]
        self.page_box.clear_widgets()
        self.progress.value = (idx + 1) * 33
        self.progress.color = get_color(color)
        self.toolbar.md_bg_color = get_color(color)

        for i, btn in enumerate(self._step_btns):
            active = i == idx
            c = self.STEP_COLORS[i]
            btn.md_bg_color = get_color(c) if active else get_color('surface_variant', 0.4)
            btn.elevation = 2 if active else 0
            btn.children[0].text_color = (1, 1, 1, 1) if active else get_color('outline')

        is_last = idx == len(self.STEPS) - 1
        self.next_btn.opacity = 0 if is_last else 1
        self.next_btn.disabled = is_last
        self.submit_btn.opacity = 1 if is_last else 0
        self.submit_btn.disabled = not is_last

        [self._build_product_step, self._build_details_step, self._build_review_step][idx]()

    def _field(self, key, hint, **kwargs):
        if key not in self._fields:
            c = self.STEP_COLORS[self._current_step]
            self._fields[key] = MDTextField(
                hint_text=hint, mode='rectangle',
                line_color_focus=get_color(c), **kwargs
            )
        return self._fields[key]

    def _section(self, text, icon):
        color = self.STEP_COLORS[self._current_step]
        row = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(44),
            radius=[dp(8)], padding=[dp(12), 0], spacing=dp(8),
            md_bg_color=get_color(f'{color}_container', 0.4), elevation=0
        )
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom', text_color=get_color(color),
            size_hint_x=None, width=dp(28),
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=text, font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color(color),
            valign='middle'
        ))
        return row

    # ── step 1: product ──────────────────────────────────────────────────────

    def _build_product_step(self):
        pb = self.page_box
        pb.add_widget(self._section('Select Loan Product', 'cash-multiple'))

        self.product_container = MDBoxLayout(
            orientation='vertical', spacing=dp(8), size_hint_y=None
        )
        self.product_container.bind(minimum_height=self.product_container.setter('height'))
        pb.add_widget(self.product_container)

        if self._products:
            self._render_products(self._products)
        elif self.app:
            threading.Thread(target=self._load_products, daemon=True).start()

    def _load_products(self):
        try:
            products = self.app.db.fetch_all(
                "SELECT * FROM products WHERE product_type = 'loan' AND is_active = 1"
            )
            Clock.schedule_once(lambda dt: self._set_products(products), 0)
        except Exception as e:
            Logger.error(f'LoanApp load products: {e}')

    def _set_products(self, products):
        # Convert sqlite3.Row objects to plain dicts so .get() works
        products = [dict(p) if hasattr(p, 'keys') else p for p in (products or [])]
        self._products = products
        self._render_products(products)

    def _render_products(self, products):
        self.product_container.clear_widgets()
        for p in products:
            active = self._selected_product and self._selected_product['id'] == p['id']
            card = MDCard(
                orientation='vertical', size_hint_y=None, height=dp(100),
                padding=dp(16), radius=[dp(12)],
                md_bg_color=get_color('quaternary') if active else get_color('surface_variant', 0.25),
                ripple_behavior=True, elevation=3 if active else 1,
                on_release=lambda x, prod=p: self._select_product(prod)
            )
            row1 = MDBoxLayout(size_hint_y=None, height=dp(28))
            row1.add_widget(MDLabel(
                text=p.get('name', ''), font_style='Subtitle1', bold=True,
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface'),
                valign='middle'
            ))
            row1.add_widget(MDLabel(
                text=f"{p.get('interest_rate', 0):.1f}% p.a.",
                halign='right', font_style='Subtitle1',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('quaternary'),
                valign='middle'
            ))
            row2 = MDLabel(
                text=f"Min: {_fmt(p.get('min_amount_minor', 0))}  •  Max: {_fmt(p.get('max_amount_minor', 0))}  •  Up to {p.get('max_term_months', 0)} months",
                font_style='Caption',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 0.8) if active else get_color('outline'),
                valign='middle'
            )
            card.add_widget(row1)
            card.add_widget(row2)
            if active:
                card.add_widget(MDIcon(
                    icon='check-circle', theme_text_color='Custom',
                    text_color=(1, 1, 1, 1), halign='right',
                    valign='middle'
                ))
            self.product_container.add_widget(card)

    def _select_product(self, product):
        self._selected_product = product
        self._render_products(self._products)

    # ── step 2: details ──────────────────────────────────────────────────────

    def _build_details_step(self):
        pb = self.page_box
        pb.add_widget(self._section('Loan Details', 'file-document-edit'))

        p = self._selected_product or {}
        max_amt = p.get('max_amount_minor', 100_000_00)
        max_term = p.get('max_term_months', 60)

        # Amount card
        amt_card = MDCard(
            orientation='vertical', padding=dp(14),
            radius=[dp(10)], md_bg_color=get_color('quaternary_container', 0.2),
            size_hint_y=None, height=dp(180), elevation=0
        )
        amt_card.add_widget(MDLabel(
            text=f'Amount (Max: {_fmt(max_amt)})',
            font_style='Subtitle2', bold=True,
            theme_text_color='Custom', text_color=get_color('quaternary'),
            size_hint_y=None, height=dp(24),
            valign='middle'
        ))
        amt_card.add_widget(self._field(
            'amount', 'Loan Amount (KSh)', input_filter='float',
            size_hint_y=None, height=dp(60), font_size=sp(22)
        ))
        amt_card.add_widget(MDLabel(
            text='Repayment Period (months)', font_style='Caption',
            theme_text_color='Secondary', size_hint_y=None, height=dp(20),
            valign='middle'
        ))
        amt_card.add_widget(self._field(
            'term', f'Term (1–{max_term} months)', input_filter='int',
            size_hint_y=None, height=dp(56)
        ))
        pb.add_widget(amt_card)

        # Purpose
        purpose_card = MDCard(
            orientation='vertical', padding=dp(14),
            radius=[dp(10)], md_bg_color=get_color('quaternary_container', 0.1),
            size_hint_y=None, height=dp(120), elevation=0
        )
        purpose_card.add_widget(self._field('purpose', 'Loan Purpose'))
        purpose_card.add_widget(self._field('guarantor_phone', 'Guarantor Phone Number (optional)'))
        pb.add_widget(purpose_card)

        # Monthly installment preview
        self.installment_card = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(64),
            padding=dp(16), radius=[dp(10)],
            md_bg_color=get_color('success', 0.1), elevation=0
        )
        self.installment_lbl = MDLabel(
            text='Enter amount & term to see monthly instalment',
            font_style='Body2', theme_text_color='Secondary',
            valign='middle'
        )
        self.installment_card.add_widget(MDIcon(
            icon='calculator', theme_text_color='Custom',
            text_color=get_color('success'), size_hint_x=None, width=dp(32),
            valign='middle'
        ))
        self.installment_card.add_widget(self.installment_lbl)
        pb.add_widget(self.installment_card)

        # Bind auto-calc
        self._fields['amount'].bind(text=self._calc_installment)
        self._fields['term'].bind(text=self._calc_installment)

    def _calc_installment(self, *args):
        try:
            p = self._selected_product or {}
            rate = p.get('interest_rate', 18) / 100 / 12
            amount = float(self._fields.get('amount', type('', (), {'text': '0'})()).text or 0)
            term = int(self._fields.get('term', type('', (), {'text': '0'})()).text or 0)
            if amount > 0 and term > 0:
                if rate > 0:
                    instalment = amount * rate / (1 - (1 + rate) ** -term)
                else:
                    instalment = amount / term
                total = instalment * term
                self.installment_lbl.text = (
                    f"Monthly: KSh {instalment:,.2f}   |   Total: KSh {total:,.2f}"
                )
                self.installment_lbl.theme_text_color = 'Custom'
                self.installment_lbl.text_color = get_color('success')
        except Exception:
            pass

    # ── step 3: review ───────────────────────────────────────────────────────

    def _build_review_step(self):
        pb = self.page_box
        pb.add_widget(self._section('Review & Submit', 'check-all'))

        p = self._selected_product or {}
        amount_text = self._fields.get('amount', type('', (), {'text': '0'})()).text or '0'
        term_text = self._fields.get('term', type('', (), {'text': '0'})()).text or '0'

        try:
            amount = float(amount_text) * 100
            term = int(term_text)
            rate = p.get('interest_rate', 18) / 100 / 12
            if rate > 0 and term > 0:
                installment = amount * rate / (1 - (1 + rate) ** -term)
                total = installment * term
            else:
                installment = amount / max(term, 1)
                total = amount
        except Exception:
            amount = installment = total = 0
            term = 0

        review_card = MDCard(
            orientation='vertical', padding=dp(16),
            radius=[dp(12)], md_bg_color=get_color('surface_variant', 0.2),
            size_hint_y=None, elevation=0
        )
        for label, value in [
            ('Product', p.get('name', '—')),
            ('Amount', _fmt(int(amount))),
            ('Term', f"{term} months"),
            ('Interest Rate', f"{p.get('interest_rate', 0):.1f}% p.a."),
            ('Monthly Instalment', f"KSh {installment / 100:,.2f}"),
            ('Total Repayment', f"KSh {total / 100:,.2f}"),
            ('Purpose', self._fields.get('purpose', type('', (), {'text': '—'})()).text or '—'),
        ]:
            row = MDBoxLayout(size_hint_y=None, height=dp(36))
            row.add_widget(MDLabel(
                text=label, theme_text_color='Secondary', size_hint_x=0.45,
                valign='middle'
            ))
            row.add_widget(MDLabel(
                text=str(value), bold=True, size_hint_x=0.55,
                valign='middle'
            ))
            review_card.add_widget(row)
        review_card.height = dp(40 + 7 * 36)
        pb.add_widget(review_card)

        pb.add_widget(MDLabel(
            text='⚠  Submitting will initiate the approval workflow.',
            font_style='Caption', theme_text_color='Custom',
            text_color=get_color('warning'),
            size_hint_y=None, height=dp(32),
            valign='middle'
        ))

    # ── navigation ────────────────────────────────────────────────────────────

    def _next(self):
        if self._current_step == 0 and not self._selected_product:
            self.show_error('Select a loan product')
            return
        if self._current_step == 1:
            if not self._fields.get('amount') or not self._fields['amount'].text:
                self.show_error('Enter loan amount')
                return
            if not self._fields.get('term') or not self._fields['term'].text:
                self.show_error('Enter repayment term')
                return
        if self._current_step < len(self.STEPS) - 1:
            self._render_step(self._current_step + 1)

    def _prev(self):
        if self._current_step > 0:
            self._render_step(self._current_step - 1)
        else:
            self.app.go_back()

    def on_enter(self):
        if not self._products and self.app:
            threading.Thread(target=self._load_products, daemon=True).start()

    # ── submit ────────────────────────────────────────────────────────────────

    def _submit(self):
        self.submit_btn.disabled = True
        self.submit_btn.text = 'Submitting…'
        threading.Thread(target=self._run_submit, daemon=True).start()

    def _run_submit(self):
        try:
            p = self._selected_product or {}
            amount_minor = int(float(self._fields['amount'].text) * 100)
            term = int(self._fields['term'].text)
            rate = p.get('interest_rate', 18)
            purpose = self._fields.get('purpose', type('', (), {'text': ''})()).text

            loan_id = self.app.loan_service.apply_loan(
                self.member_id, amount_minor, term, rate,
                purpose=purpose, product_id=p.get('id')
            )
            Clock.schedule_once(lambda dt: self._on_success(loan_id, amount_minor), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_success(self, loan_id, amount):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'SUBMIT APPLICATION'
        _receipt_dialog(
            'Application Submitted',
            [
                ('Loan Amount', _fmt(amount)),
                ('Status', 'Pending Approval'),
                ('Date', datetime.datetime.now().strftime('%d %b %Y')),
            ],
            on_dismiss=lambda: self.app.navigate_to('loan_schedule', loan_id=loan_id)
        )

    def _on_error(self, msg):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'SUBMIT APPLICATION'
        self.show_error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# REPAYMENT SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class RepaymentScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'repayment'
        self.member_id = None
        self._loans = []
        self._selected_loan_id = None
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Loan Repayment',
            md_bg_color=get_color('quinary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        body = MDBoxLayout(
            orientation='vertical', spacing=dp(16),
            padding=dp(16), size_hint_y=None
        )
        body.bind(minimum_height=body.setter('height'))

        # Loan selector
        body.add_widget(self._sec('Select Loan', 'cash-multiple', 'quinary'))
        self.loan_container = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.loan_container.bind(minimum_height=self.loan_container.setter('height'))
        body.add_widget(self.loan_container)

        # Loan summary
        self.summary_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(0),
            padding=dp(16), radius=[dp(12)],
            md_bg_color=get_color('quinary', 0.1), elevation=0
        )
        self._sum_labels = {}
        for key in ['Balance', 'Next Due', 'Overdue', 'Arrears']:
            row = MDBoxLayout(size_hint_y=None, height=dp(32))
            row.add_widget(MDLabel(
                text=key, theme_text_color='Secondary', size_hint_x=0.5,
                valign='middle'
            ))
            val = MDLabel(text='—', bold=True, size_hint_x=0.5, halign='right',
                valign='middle'
            )
            self._sum_labels[key] = val
            row.add_widget(val)
            self.summary_card.add_widget(row)
        body.add_widget(self.summary_card)

        # Amount
        body.add_widget(self._sec('Repayment Amount', 'cash-check', 'quinary'))
        self.amount_field = MDTextField(
            hint_text='0.00', mode='rectangle', input_filter='float',
            line_color_focus=get_color('quinary'),
            size_hint_y=None, height=dp(60), font_size=sp(22)
        )
        body.add_widget(self.amount_field)

        # Pay-full toggle
        full_row = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))
        full_row.add_widget(MDLabel(text='Pay full outstanding balance', font_style='Body2',
            valign='middle'
        ))
        self.full_switch = MDSwitch(
            size_hint=(None, None), size=(dp(56), dp(28)),
            on_active=self._on_full_toggle
        )
        full_row.add_widget(self.full_switch)
        body.add_widget(full_row)

        self.desc_field = MDTextField(
            hint_text='Reference / Notes (optional)',
            mode='rectangle', line_color_focus=get_color('quinary'),
            size_hint_y=None, height=dp(56)
        )
        body.add_widget(self.desc_field)

        self.submit_btn = MDRaisedButton(
            text='REPAY',
            size_hint_x=1, height=dp(54),
            md_bg_color=get_color('quinary'),
            font_size=sp(15), on_release=self._confirm
        )
        body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(8)))
        body.add_widget(self.submit_btn)

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    def _sec(self, text, icon, color='primary'):
        row = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color(color), size_hint_x=None, width=dp(24),
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=text.upper(), font_style='Caption',
            theme_text_color='Custom', text_color=get_color(color), bold=True,
            valign='middle'
        ))
        return row

    def on_enter(self):
        if self.member_id:
            threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            loans = self.app.db.fetch_all(
                "SELECT * FROM loans WHERE member_id = ? "
                "AND status IN ('active', 'disbursed', 'overdue')",
                (self.member_id,)
            )
            Clock.schedule_once(lambda dt: self._render_loans(loans), 0)
        except Exception as e:
            Logger.error(f'RepaymentScreen: {e}')

    def _render_loans(self, loans):
        self._loans = loans
        self.loan_container.clear_widgets()
        if not loans:
            self.loan_container.add_widget(MDLabel(
                text='No active loans found',
                theme_text_color='Secondary', size_hint_y=None, height=dp(40),
                valign='middle'
            ))
            return
        for loan in loans:
            active = loan['id'] == self._selected_loan_id
            status_color = 'error' if loan.get('status') == 'overdue' else 'quinary'
            card = MDCard(
                orientation='vertical', size_hint_y=None, height=dp(80),
                padding=dp(12), radius=[dp(10)],
                md_bg_color=get_color('quinary') if active else get_color('surface_variant', 0.25),
                ripple_behavior=True, elevation=2 if active else 0,
                on_release=lambda x, l=loan: self._select_loan(l)
            )
            row1 = MDBoxLayout(size_hint_y=None, height=dp(28))
            row1.add_widget(MDLabel(
                text=loan.get('loan_no', ''), font_style='Subtitle2', bold=True,
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface'),
                valign='middle'
            ))
            row1.add_widget(MDLabel(
                text=loan.get('status', '').upper(),
                halign='right', font_style='Caption',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 0.9) if active else get_color(status_color),
                valign='middle'
            ))
            row2 = MDLabel(
                text=f"Outstanding: {_fmt(loan.get('outstanding_principal_minor', 0))}",
                font_style='Caption', theme_text_color='Custom',
                text_color=(1, 1, 1, 0.8) if active else get_color('outline'),
                valign='middle'
            )
            card.add_widget(row1)
            card.add_widget(row2)
            self.loan_container.add_widget(card)

        if loans and not self._selected_loan_id:
            self._select_loan(loans[0])

    def _select_loan(self, loan: dict):
        self._selected_loan = loan
        self._selected_loan_id = loan['id']
        self._render_loans(self._loans)

        outstanding = loan.get('outstanding_principal_minor', 0)
        interest = loan.get('accrued_interest_minor', 0)
        self._sum_labels['Balance'].text = _fmt(outstanding)
        self._sum_labels['Next Due'].text = loan.get('next_payment_date', '—') or '—'
        self._sum_labels['Overdue'].text = '✅ No' if loan.get('status') != 'overdue' else '⚠ Yes'
        self._sum_labels['Arrears'].text = _fmt(loan.get('arrears_minor', 0))
        self.summary_card.height = dp(16 + 4 * 32)

    def _on_full_toggle(self, switch, value):
        if value and hasattr(self, '_selected_loan'):
            outstanding = self._selected_loan.get('outstanding_principal_minor', 0)
            interest = self._selected_loan.get('accrued_interest_minor', 0)
            self.amount_field.text = f"{(outstanding + interest) / 100:.2f}"
        elif not value:
            self.amount_field.text = ''

    def _confirm(self, *args):
        if not self._selected_loan_id:
            self.show_error('Select a loan')
            return
        amount = _amount_from_text(self.amount_field.text)
        if amount <= 0:
            self.show_error('Enter a valid amount')
            return

        dialog = MDDialog(
            title='Confirm Repayment',
            text=f"Repay [b]{_fmt(amount)}[/b] for loan [b]{self._selected_loan.get('loan_no', '')}[/b]?",
            radius=[dp(16)],
            buttons=[
                MDFlatButton(text='CANCEL', on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text='CONFIRM', md_bg_color=get_color('quinary'),
                    on_release=lambda x: (dialog.dismiss(), self._execute(amount))
                )
            ]
        )
        dialog.open()

    def _execute(self, amount: int):
        self.submit_btn.disabled = True
        self.submit_btn.text = 'Processing…'
        desc = self.desc_field.text.strip() or 'Loan repayment'
        threading.Thread(target=self._run, args=(amount, desc), daemon=True).start()

    def _run(self, amount: int, desc: str):
        try:
            self.app.loan_service.process_repayment(
                self._selected_loan_id, amount, description=desc
            )
            Clock.schedule_once(lambda dt: self._on_success(amount), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_success(self, amount):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'REPAY'
        self.amount_field.text = ''
        self.full_switch.active = False
        _receipt_dialog(
            'Repayment Successful',
            [
                ('Loan', self._selected_loan.get('loan_no', '')),
                ('Amount Paid', _fmt(amount)),
                ('Date', datetime.datetime.now().strftime('%d %b %Y %H:%M')),
            ],
            on_dismiss=lambda: self._load()
        )

    def _on_error(self, msg):
        self.submit_btn.disabled = False
        self.submit_btn.text = 'REPAY'
        self.show_error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# LOAN SCHEDULE SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class LoanScheduleScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'loan_schedule'
        self.loan_id = None
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Loan Schedule',
            md_bg_color=get_color('quaternary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['file-pdf-box', lambda x: self._export_pdf()]
            ]
        )
        root.add_widget(self.toolbar)

        # Loan summary banner
        self.summary_card = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(100),
            padding=dp(16), md_bg_color=get_color('quaternary'), elevation=4
        )
        self._sum_info = MDBoxLayout(orientation='vertical')
        self.loan_no_lbl = MDLabel(
            text='Loading…', font_style='H6', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            valign='middle'
        )
        self.loan_meta_lbl = MDLabel(
            text='', font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.8),
            valign='middle'
        )
        self._sum_info.add_widget(self.loan_no_lbl)
        self._sum_info.add_widget(self.loan_meta_lbl)
        self.summary_card.add_widget(self._sum_info)

        progress_col = MDBoxLayout(
            orientation='vertical', size_hint_x=None, width=dp(80)
        )
        self.repaid_lbl = MDLabel(
            text='0%', font_style='H5', bold=True,
            halign='center', theme_text_color='Custom', text_color=(1, 1, 1, 1),
            valign='middle'
        )
        progress_col.add_widget(self.repaid_lbl)
        progress_col.add_widget(MDLabel(
            text='Repaid', font_style='Caption', halign='center',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.8),
            valign='middle'
        ))
        self.summary_card.add_widget(progress_col)
        root.add_widget(self.summary_card)

        # Progress bar
        self.loan_progress = MDProgressBar(
            value=0, color=get_color('success'),
            size_hint_y=None, height=dp(8)
        )
        root.add_widget(self.loan_progress)

        # Schedule table header
        header = MDBoxLayout(
            size_hint_y=None, height=dp(36),
            md_bg_color=get_color('quaternary_container', 0.4),
            padding=[dp(12), 0]
        )
        for col, w in [('#', 0.08), ('Due Date', 0.25), ('Principal', 0.22), ('Interest', 0.22), ('Status', 0.23)]:
            header.add_widget(MDLabel(
                text=col, font_style='Caption', bold=True,
                theme_text_color='Custom', text_color=get_color('quaternary'),
                size_hint_x=w,
                valign='middle'
            ))
        root.add_widget(header)

        # Schedule rows
        scroll = MDScrollView()
        self.schedule_box = MDBoxLayout(
            orientation='vertical', size_hint_y=None, spacing=dp(1)
        )
        self.schedule_box.bind(minimum_height=self.schedule_box.setter('height'))
        scroll.add_widget(self.schedule_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_enter(self):
        if self.loan_id:
            threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            loan = self.app.db.fetch_one(
                "SELECT * FROM loans WHERE id = ?", (self.loan_id,)
            )
            schedule = self.app.db.fetch_all(
                "SELECT * FROM loan_schedule WHERE loan_id = ? ORDER BY installment_no",
                (self.loan_id,)
            )
            Clock.schedule_once(lambda dt: self._render(loan, schedule), 0)
        except Exception as e:
            Logger.error(f'LoanSchedule: {e}')

    def _render(self, loan, schedule):
        if not loan:
            return

        principal = loan.get('principal_amount_minor', 0)
        outstanding = loan.get('outstanding_principal_minor', principal)
        paid = max(0, principal - outstanding)
        pct = (paid / principal * 100) if principal > 0 else 0

        self.loan_no_lbl.text = f"Loan {loan.get('loan_no', '')}  •  {loan.get('status', '').title()}"
        self.loan_meta_lbl.text = (
            f"{_fmt(principal)} @ {loan.get('interest_rate', 0):.1f}%  •  "
            f"{loan.get('term_months', 0)} months  •  Due {loan.get('maturity_date', '—')}"
        )
        self.repaid_lbl.text = f"{pct:.0f}%"
        self.loan_progress.value = pct

        self.schedule_box.clear_widgets()
        for i, row in enumerate(schedule):
            is_paid = row.get('status') == 'paid'
            is_overdue = (
                not is_paid
                and row.get('due_date', '9999') < datetime.date.today().isoformat()
            )
            bg = (
                get_color('success', 0.08) if is_paid
                else get_color('error', 0.08) if is_overdue
                else ((1, 1, 1, 1) if i % 2 == 0 else get_color('surface_variant', 0.2))
            )
            status_color = (
                get_color('success') if is_paid
                else get_color('error') if is_overdue
                else get_color('outline')
            )
            status_icon = '✅' if is_paid else '⚠' if is_overdue else '◷'

            r = MDBoxLayout(
                size_hint_y=None, height=dp(44),
                md_bg_color=bg, padding=[dp(12), 0]
            )
            for text, w in [
                (str(row.get('installment_no', i + 1)), 0.08),
                (row.get('due_date', '—'), 0.25),
                (f"KSh {row.get('principal_minor', 0) / 100:,.0f}", 0.22),
                (f"KSh {row.get('interest_minor', 0) / 100:,.0f}", 0.22),
                (f"{status_icon} {row.get('status', 'pending').title()}", 0.23),
            ]:
                lbl = MDLabel(
                    text=text, font_style='Caption', size_hint_x=w,
                    valign='middle'
                )
                if text.startswith(status_icon):
                    lbl.theme_text_color = 'Custom'
                    lbl.text_color = status_color
                r.add_widget(lbl)
            self.schedule_box.add_widget(r)

    def _export_pdf(self):
        self.show_info('PDF export feature coming soon')
