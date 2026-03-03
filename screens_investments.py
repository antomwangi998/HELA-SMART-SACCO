# screens_investments.py  -- HELA SMART SACCO
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
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDFloatingActionButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen


def _fmt(minor):
    return f"KSh {(minor or 0) / 100:,.2f}"


class InvestmentsScreen(BaseScreen):
    PRODUCT_INFO = [
        ("fixed_deposit", "Fixed Deposit",       "bank-outline",         "primary",
         "9-13% p.a.  |  Min KSh 10,000  |  6-24 months"),
        ("unit_trust",    "Unit Trust (MMF)",     "trending-up",          "secondary",
         "~10% p.a.  |  Min KSh 1,000  |  Withdraw anytime"),
        ("shares",        "Share Capital",        "chart-pie",            "tertiary",
         "~8% dividends  |  KSh 50/share  |  Min 10 shares"),
        ("bonds",         "Government Bond",      "shield-check-outline", "quaternary",
         "11-15% p.a.  |  Min KSh 5,000  |  1-10 years"),
    ]
    RATE_TABLE = {
        "fixed_deposit": [(6, 9.0), (12, 11.0), (18, 12.0), (24, 13.0)],
        "unit_trust":    [(0, 10.0)],
        "shares":        [(0, 8.0)],
        "bonds":         [(12, 12.5), (24, 13.5), (60, 14.5)],
    }
    COLOR_MAP = {k: c for k, _, _, c, _ in PRODUCT_INFO}
    ICON_MAP  = {k: ic for k, _, ic, _, _ in PRODUCT_INFO}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "investments"
        self._dialog = None
        self._all_investments = []
        self._selected_type = "fixed_deposit"
        self._build()

    def _build(self):
        from kivy.uix.floatlayout import FloatLayout
        float_root = FloatLayout()
        root = MDBoxLayout(orientation="vertical", size_hint=(1, 1))

        toolbar = MDTopAppBar(
            title="Investments", elevation=2,
            md_bg_color=get_color("primary"),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[["arrow-left", lambda x: self.app.navigate_back()]],
            right_action_items=[["refresh",
                lambda x: threading.Thread(target=self._load, daemon=True).start()]],
        )
        root.add_widget(toolbar)

        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation="vertical", spacing=dp(12),
            padding=[dp(14), dp(14), dp(14), dp(80)], size_hint_y=None
        )
        content.bind(minimum_height=content.setter("height"))

        # Summary strip
        sg = MDGridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(80))
        self._s_count  = self._mini_stat("0",     "Active",          "primary")
        self._s_total  = self._mini_stat("KSh 0", "Total Principal", "tertiary")
        self._s_earned = self._mini_stat("KSh 0", "Interest Earned", "success")
        for c in [self._s_count, self._s_total, self._s_earned]:
            sg.add_widget(c)
        content.add_widget(sg)

        # Product showcase
        content.add_widget(MDLabel(
            text="INVESTMENT PRODUCTS", font_style="Caption",
            theme_text_color="Secondary", bold=True,
            size_hint_y=None, height=dp(22), valign="middle"
        ))
        pg = MDGridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(200))
        for key, label, icon, color, desc in self.PRODUCT_INFO:
            card = MDCard(
                orientation="vertical", padding=[dp(10), dp(8)], spacing=dp(4),
                radius=[dp(12)], md_bg_color=get_color(f"{color}_container", 0.2),
                elevation=1, ripple_behavior=True,
                on_release=lambda x, k=key: self._open_new_dialog(k)
            )
            ic_row = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6))
            ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(28), dp(28)))
            with ic_rl.canvas.before:
                Color(*get_color(f"{color}_container", 0.6))
                RoundedRectangle(pos=(0, 0), size=(dp(28), dp(28)), radius=[dp(8)])
            ic_rl.add_widget(MDIcon(
                icon=icon, theme_text_color="Custom", text_color=get_color(color),
                halign="center", valign="middle", font_size=sp(16),
                size_hint=(None, None), size=(dp(18), dp(18)),
                pos_hint={"center_x": 0.5, "center_y": 0.5}
            ))
            ic_row.add_widget(ic_rl)
            ic_row.add_widget(MDLabel(
                text=label, font_style="Caption", bold=True,
                theme_text_color="Custom", text_color=get_color(color), valign="middle"
            ))
            card.add_widget(ic_row)
            card.add_widget(MDLabel(
                text=desc, font_style="Caption", theme_text_color="Secondary",
                size_hint_y=None, height=dp(36), valign="top"
            ))
            card.add_widget(MDLabel(
                text="Tap to invest", font_style="Caption",
                theme_text_color="Custom", text_color=get_color(color),
                halign="right", valign="middle", size_hint_y=None, height=dp(16)
            ))
            pg.add_widget(card)
        content.add_widget(pg)

        # Filter pills
        fs = MDScrollView(size_hint_y=None, height=dp(44),
                          do_scroll_x=True, do_scroll_y=False)
        fr = MDBoxLayout(size_hint_x=None, height=dp(44),
                         spacing=dp(8), padding=[0, dp(4)])
        fr.bind(minimum_width=fr.setter("width"))
        self._filter = "all"
        self._filter_btns = {}
        pill_items = [("all", "All", "", "primary", "")] + list(self.PRODUCT_INFO)
        for key, label, _ic, color, _d in pill_items:
            active = key == "all"
            btn = MDCard(
                size_hint=(None, None), size=(dp(90), dp(34)),
                radius=[dp(17)],
                md_bg_color=get_color(color) if active else get_color("surface_variant", 0.4),
                ripple_behavior=True,
                on_release=lambda x, k=key: self._set_filter(k)
            )
            lbl = MDLabel(
                text=label.split(" ")[0], halign="center", valign="middle",
                font_style="Caption", bold=active,
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1) if active else get_color("on_surface")
            )
            btn.add_widget(lbl)
            self._filter_btns[key] = (btn, lbl, color)
            fr.add_widget(btn)
        fs.add_widget(fr)
        content.add_widget(fs)

        # Portfolio list
        content.add_widget(MDLabel(
            text="YOUR PORTFOLIO", font_style="Caption",
            theme_text_color="Secondary", bold=True,
            size_hint_y=None, height=dp(22), valign="middle"
        ))
        self._list_box = MDBoxLayout(
            orientation="vertical", spacing=dp(8), size_hint_y=None
        )
        self._list_box.bind(minimum_height=self._list_box.setter("height"))
        content.add_widget(self._list_box)

        scroll.add_widget(content)
        root.add_widget(scroll)
        float_root.add_widget(root)

        fab = MDFloatingActionButton(
            icon="plus", md_bg_color=get_color("primary"),
            pos_hint={"right": 0.95, "y": 0.03},
            on_release=lambda x: self._open_new_dialog()
        )
        float_root.add_widget(fab)
        self.add_widget(float_root)

    def _mini_stat(self, value, label, color):
        card = MDCard(
            orientation="vertical", padding=[dp(8), dp(6)], spacing=dp(2),
            radius=[dp(10)], md_bg_color=get_color(f"{color}_container", 0.25), elevation=0
        )
        v = MDLabel(
            text=value, font_style="H6", bold=True, halign="center",
            theme_text_color="Custom", text_color=get_color(color),
            size_hint_y=None, height=dp(28), valign="middle"
        )
        card.add_widget(v)
        card.add_widget(MDLabel(
            text=label, font_style="Caption", halign="center",
            theme_text_color="Secondary", size_hint_y=None, height=dp(16), valign="middle"
        ))
        card._v = v
        return card

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            svc = self.app.investment_service
            svc.set_context(self.app.current_user_id, self.app.device_id,
                            self.app.current_branch_id)
            role = self.app.current_user_role or "member"
            if role == "member":
                user = self.app.db.fetch_one(
                    "SELECT member_id FROM users WHERE id=?",
                    (self.app.current_user_id,))
                mid = (user or {}).get("member_id")
                invs = svc.get_member_investments(mid) if mid else []
                summary = {
                    "count": sum(1 for i in invs if i.get("status") == "active"),
                    "total_principal": sum(
                        i.get("principal_minor", 0) for i in invs
                        if i.get("status") == "active"),
                    "total_interest": sum(
                        i.get("interest_earned_minor", 0) for i in invs
                        if i.get("status") == "active"),
                }
            else:
                invs = svc.get_all_investments()
                summary = svc.get_summary()
            Clock.schedule_once(lambda dt: self._update_ui(invs, summary), 0)
        except Exception as e:
            Logger.error("Investments load: %s", e)
            import traceback; traceback.print_exc()

    def _update_ui(self, invs, summary):
        self._all_investments = invs
        self._s_count._v.text  = str(summary.get("count", 0))
        self._s_total._v.text  = _fmt(summary.get("total_principal", 0))
        self._s_earned._v.text = _fmt(summary.get("total_interest", 0))
        self._render_list(invs)

    def _set_filter(self, key):
        self._filter = key
        for k, (btn, lbl, color) in self._filter_btns.items():
            active = k == key
            btn.md_bg_color = (get_color(color) if active
                               else get_color("surface_variant", 0.4))
            lbl.text_color = (1, 1, 1, 1) if active else get_color("on_surface")
            lbl.bold = active
        self._render_list(self._all_investments)

    def _render_list(self, invs):
        self._list_box.clear_widgets()
        filtered = [i for i in (invs or [])
                    if self._filter == "all" or i.get("investment_type") == self._filter]
        if not filtered:
            empty = MDCard(
                orientation="vertical", padding=dp(24), radius=[dp(12)],
                elevation=0, md_bg_color=get_color("surface_variant", 0.15),
                size_hint_y=None, height=dp(100)
            )
            empty.add_widget(MDLabel(
                text="No investments yet.\nTap + or a product card above to start investing.",
                halign="center", valign="middle",
                theme_text_color="Secondary", font_style="Body2"
            ))
            self._list_box.add_widget(empty)
            return
        for inv in filtered:
            self._list_box.add_widget(self._inv_card(inv))

    def _inv_card(self, inv):
        itype   = inv.get("investment_type", "fixed_deposit")
        color   = self.COLOR_MAP.get(itype, "primary")
        icon    = self.ICON_MAP.get(itype, "cash")
        status  = inv.get("status", "active")
        s_color = {"active": "success", "matured": "info",
                   "cancelled": "error", "redeemed": "warning"}.get(status, "outline")

        principal = inv.get("principal_minor", 0) or 0
        interest  = inv.get("interest_earned_minor", 0) or 0
        projected = principal + interest
        term      = inv.get("term_months", 0) or 0

        days_left = None
        mat = inv.get("maturity_date")
        if mat and term > 0:
            try:
                days_left = (datetime.date.fromisoformat(mat) - datetime.date.today()).days
            except Exception:
                pass

        card = MDCard(
            orientation="vertical", padding=[dp(12), dp(10)], spacing=dp(6),
            radius=[dp(14)], md_bg_color=get_color("surface_variant", 0.1),
            size_hint_y=None, height=dp(130), elevation=1, ripple_behavior=True,
        )

        # Top row
        top = MDBoxLayout(size_hint_y=None, height=dp(36), spacing=dp(10))
        ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(36), dp(36)))
        with ic_rl.canvas.before:
            Color(*get_color(f"{color}_container", 0.5))
            RoundedRectangle(pos=(0, 0), size=(dp(36), dp(36)), radius=[dp(10)])
        ic_rl.add_widget(MDIcon(
            icon=icon, theme_text_color="Custom", text_color=get_color(color),
            halign="center", valign="middle", font_size=sp(18),
            size_hint=(None, None), size=(dp(22), dp(22)),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        ))
        top.add_widget(ic_rl)
        name = inv.get("name") or itype.replace("_", " ").title()
        if inv.get("first_name"):
            name = f"{inv['first_name']} {inv.get('last_name','')} -- {name}"
        top.add_widget(MDLabel(
            text=name, font_style="Subtitle2", bold=True,
            size_hint_y=None, height=dp(36), valign="middle"
        ))
        # Status pill
        st_rl = RelativeLayout(size_hint=(None, None), size=(dp(68), dp(22)),
                                pos_hint={"center_y": 0.5})
        with st_rl.canvas.before:
            Color(*get_color(f"{s_color}_container", 0.5))
            RoundedRectangle(pos=(0, 0), size=(dp(68), dp(22)), radius=[dp(11)])
        st_rl.add_widget(MDLabel(
            text=status.title(), font_style="Caption", bold=True,
            halign="center", valign="middle",
            theme_text_color="Custom", text_color=get_color(s_color),
            size_hint=(None, None), size=(dp(68), dp(22)),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        ))
        top.add_widget(st_rl)
        card.add_widget(top)

        # Details grid
        dg = MDGridLayout(cols=3, spacing=dp(4), size_hint_y=None, height=dp(42))
        for val, lbl in [(_fmt(principal), "Principal"),
                         (f"{inv.get('interest_rate',0):.1f}% p.a.", "Rate"),
                         (_fmt(projected), "At Maturity")]:
            cell = MDBoxLayout(orientation="vertical")
            cell.add_widget(MDLabel(
                text=val, font_style="Caption", bold=True,
                theme_text_color="Custom", text_color=get_color(color),
                halign="center", size_hint_y=None, height=dp(22), valign="middle"
            ))
            cell.add_widget(MDLabel(
                text=lbl, font_style="Caption", theme_text_color="Secondary",
                halign="center", size_hint_y=None, height=dp(16), valign="middle"
            ))
            dg.add_widget(cell)
        card.add_widget(dg)

        # Bottom row: maturity info + redeem
        bot = MDBoxLayout(size_hint_y=None, height=dp(26), spacing=dp(8))
        if days_left is not None and status == "active":
            if days_left <= 0:
                mt, mc = "Matured today!", "success"
            elif days_left <= 30:
                mt, mc = f"Matures in {days_left}d", "warning"
            else:
                mt, mc = f"Matures {mat}", "outline"
            bot.add_widget(MDLabel(
                text=mt, font_style="Caption",
                theme_text_color="Custom", text_color=get_color(mc),
                valign="middle", size_hint_y=None, height=dp(26)
            ))
        elif term == 0 and status == "active":
            bot.add_widget(MDLabel(
                text="Open-ended - withdraw anytime",
                font_style="Caption", theme_text_color="Secondary",
                valign="middle", size_hint_y=None, height=dp(26)
            ))
        else:
            bot.add_widget(MDLabel(text="", size_hint_y=None, height=dp(26)))

        if status == "active":
            rb = MDCard(
                size_hint=(None, None), size=(dp(72), dp(24)), radius=[dp(12)],
                md_bg_color=get_color("error_container", 0.4), ripple_behavior=True,
                on_release=lambda x, iid=inv.get("id"): self._confirm_redeem(iid)
            )
            rb.add_widget(MDLabel(
                text="Redeem", halign="center", valign="middle",
                font_style="Caption", bold=True,
                theme_text_color="Custom", text_color=get_color("error")
            ))
            bot.add_widget(rb)
        card.add_widget(bot)
        return card

    def _open_new_dialog(self, inv_type="fixed_deposit"):
        self._selected_type = inv_type
        if self._dialog:
            self._dialog.dismiss()

        role = self.app.current_user_role or "member"

        # Type buttons
        type_row = MDBoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        self._type_btns = {}
        for key, label, _, color, _ in self.PRODUCT_INFO:
            active = key == inv_type
            btn = MDCard(
                size_hint=(1, None), height=dp(30), radius=[dp(15)],
                md_bg_color=get_color(color) if active else get_color("surface_variant", 0.4),
                ripple_behavior=True,
                on_release=lambda x, k=key: self._select_type(k)
            )
            lbl = MDLabel(
                text=label.split(" ")[0], halign="center", valign="middle",
                font_style="Caption", bold=active, theme_text_color="Custom",
                text_color=(1, 1, 1, 1) if active else get_color("on_surface")
            )
            btn.add_widget(lbl)
            self._type_btns[key] = (btn, lbl, color)
            type_row.add_widget(btn)

        self._rate_info_lbl = MDLabel(
            text=self._rate_info_text(inv_type),
            font_style="Caption", theme_text_color="Secondary",
            size_hint_y=None, height=dp(30), valign="middle"
        )
        self._amount_field = MDTextField(
            hint_text="Principal Amount (KSh)", mode="rectangle",
            input_filter="float", size_hint_y=None, height=dp(52)
        )
        self._term_field = MDTextField(
            hint_text="Term (months)", mode="rectangle",
            input_filter="int", text="12", size_hint_y=None, height=dp(52)
        )
        self._notes_field = MDTextField(
            hint_text="Notes (optional)", mode="rectangle",
            size_hint_y=None, height=dp(52)
        )

        form = MDBoxLayout(
            orientation="vertical", spacing=dp(8), size_hint_y=None, padding=[dp(4), dp(8)]
        )
        form.bind(minimum_height=form.setter("height"))

        self._member_field = None
        if role != "member":
            self._member_field = MDTextField(
                hint_text="Member No or ID (staff)", mode="rectangle",
                size_hint_y=None, height=dp(52)
            )

        widgets = [type_row, self._rate_info_lbl, self._amount_field, self._term_field]
        if self._member_field:
            widgets.append(self._member_field)
        widgets.append(self._notes_field)
        for w in widgets:
            form.add_widget(w)

        sv = MDScrollView(size_hint=(1, None), size=(dp(300), dp(340)))
        sv.add_widget(form)

        self._dialog = MDDialog(
            title="New Investment", type="custom", content_cls=sv,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self._dialog.dismiss()),
                MDRaisedButton(text="INVEST", md_bg_color=get_color("primary"),
                               on_release=lambda x: self._do_save()),
            ]
        )
        self._dialog.open()

    def _rate_info_text(self, inv_type):
        table = self.RATE_TABLE.get(inv_type, [])
        if not table:
            return "Rate: contact office"
        parts = [(f"{m}mo={r}%" if m > 0 else f"Open={r}%") for m, r in table]
        return "Rates: " + "  |  ".join(parts)

    def _select_type(self, key):
        self._selected_type = key
        for k, (btn, lbl, color) in self._type_btns.items():
            active = k == key
            btn.md_bg_color = (get_color(color) if active
                               else get_color("surface_variant", 0.4))
            lbl.text_color = (1, 1, 1, 1) if active else get_color("on_surface")
            lbl.bold = active
        if hasattr(self, "_rate_info_lbl"):
            self._rate_info_lbl.text = self._rate_info_text(key)

    def _do_save(self):
        try:
            amount_minor = int(float(self._amount_field.text or 0) * 100)
            term         = int(self._term_field.text or 12)
            inv_type     = self._selected_type
            notes        = self._notes_field.text or ""
            role         = self.app.current_user_role or "member"

            if role == "member":
                user = self.app.db.fetch_one(
                    "SELECT member_id FROM users WHERE id=?",
                    (self.app.current_user_id,))
                mid = (user or {}).get("member_id")
            else:
                raw = (self._member_field.text or "").strip()
                m = self.app.db.fetch_one(
                    "SELECT id FROM members WHERE member_no=? OR id=?", (raw, raw))
                mid = (m or {}).get("id")

            if not mid:
                self.show_error("Member not found")
                return

            svc = self.app.investment_service
            svc.set_context(self.app.current_user_id, self.app.device_id,
                            self.app.current_branch_id)
            svc.create_investment(mid, inv_type, amount_minor, term, notes)
            self._dialog.dismiss()
            self.show_success("Investment created successfully!")
            threading.Thread(target=self._load, daemon=True).start()
        except ValueError as e:
            self.show_error(str(e))
        except Exception as e:
            Logger.error("Investment create: %s", e)
            self.show_error(f"Error: {e}")

    def _confirm_redeem(self, inv_id):
        if not inv_id:
            return
        self.confirm_dialog(
            "Redeem Investment",
            "Early redemption forfeits 50%% of accrued interest "
            "(Unit Trusts: no penalty). Proceed?",
            on_confirm=lambda: self._do_redeem(inv_id)
        )

    def _do_redeem(self, inv_id):
        def _work():
            try:
                svc = self.app.investment_service
                svc.set_context(self.app.current_user_id, self.app.device_id,
                                self.app.current_branch_id)
                result  = svc.redeem_early(inv_id, reason="Member requested")
                payout  = result["payout"] / 100
                penalty = result["penalty"] / 100
                msg = f"Redeemed! KSh {payout:,.2f} credited to savings."
                if penalty:
                    msg += f" Penalty: KSh {penalty:,.2f}"
                Clock.schedule_once(lambda dt: (
                    self.show_success(msg),
                    threading.Thread(target=self._load, daemon=True).start()
                ), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self.show_error(str(e)), 0)
        threading.Thread(target=_work, daemon=True).start()
