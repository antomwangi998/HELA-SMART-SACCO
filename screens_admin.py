# screens_admin.py - Admin & management screens
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
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen
from screens_transactions import _fmt


# ─────────────────────────────────────────────────────────────────────────────
# MEMBER EDIT SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class MemberEditScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'member_edit'
        self.member_id = None
        self._member = None
        self._fields = {}
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Edit Member',
            md_bg_color=get_color('secondary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['content-save', lambda x: self._save()]
            ]
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        self.body = MDBoxLayout(
            orientation='vertical', spacing=dp(12),
            padding=dp(16), size_hint_y=None
        )
        self.body.bind(minimum_height=self.body.setter('height'))
        scroll.add_widget(self.body)
        root.add_widget(scroll)

        # Suspend / Activate toggle
        action_bar = MDBoxLayout(
            size_hint_y=None, height=dp(60),
            padding=[dp(16), dp(8)], spacing=dp(12),
            md_bg_color=get_color('surface_variant', 0.2)
        )
        self.save_btn = MDRaisedButton(
            text='SAVE CHANGES',
            md_bg_color=get_color('secondary'),
            on_release=lambda x: self._save()
        )
        self.suspend_btn = MDRaisedButton(
            text='SUSPEND',
            md_bg_color=get_color('error'),
            on_release=lambda x: self._toggle_suspend()
        )
        action_bar.add_widget(self.save_btn)
        action_bar.add_widget(Widget())
        action_bar.add_widget(self.suspend_btn)
        root.add_widget(action_bar)

        self.add_widget(root)

    def _fld(self, key, hint, value='', **kwargs):
        if key not in self._fields:
            f = MDTextField(
                hint_text=hint, text=str(value) if value else '',
                mode='rectangle', line_color_focus=get_color('secondary'),
                size_hint_y=None, height=dp(56), **kwargs
            )
            self._fields[key] = f
        return self._fields[key]

    def _sec(self, text, icon):
        row = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(44),
            radius=[dp(8)], padding=[dp(12), 0], spacing=dp(8),
            md_bg_color=get_color('secondary_container', 0.35), elevation=0
        )
        row.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color('secondary'), size_hint_x=None, width=dp(28),
            valign='middle'
        ))
        row.add_widget(MDLabel(
            text=text, font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color('secondary'),
            valign='middle'
        ))
        return row

    def on_enter(self):
        if self.member_id:
            threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            m = self.app.member_service.get_member(self.member_id, include_sensitive=True)
            Clock.schedule_once(lambda dt: self._populate(m), 0)
        except Exception as e:
            Logger.error(f'MemberEdit: {e}')

    def _populate(self, member):
        if not member:
            return
        self._member = member
        self.body.clear_widgets()
        self._fields.clear()

        self.toolbar.title = f"Edit — {member.get('first_name')} {member.get('last_name')}"
        self.suspend_btn.text = 'ACTIVATE' if not member.get('is_active') else 'SUSPEND'
        self.suspend_btn.md_bg_color = get_color('success') if not member.get('is_active') else get_color('error')

        # Personal
        self.body.add_widget(self._sec('Personal', 'account-edit'))
        for key, hint in [
            ('first_name', 'First Name *'),
            ('last_name', 'Last Name *'),
            ('other_names', 'Other Names'),
            ('date_of_birth', 'Date of Birth'),
            ('gender', 'Gender'),
            ('marital_status', 'Marital Status'),
        ]:
            self.body.add_widget(self._fld(key, hint, member.get(key, '')))

        # Contact
        self.body.add_widget(self._sec('Contact', 'phone'))
        for key, hint in [
            ('phone', 'Phone Number *'),
            ('phone2', 'Alt Phone'),
            ('email', 'Email'),
            ('address', 'Address'),
            ('city', 'City'),
            ('county', 'County'),
        ]:
            self.body.add_widget(self._fld(key, hint, member.get(key, '')))

        # Employment
        self.body.add_widget(self._sec('Employment', 'briefcase'))
        for key, hint in [
            ('occupation', 'Occupation'),
            ('employer', 'Employer'),
            ('job_title', 'Job Title'),
            ('employment_type', 'Employment Type'),
            ('monthly_income', 'Monthly Income (KSh)'),
        ]:
            self.body.add_widget(self._fld(key, hint, member.get(key, '')))

        # Notes
        self.body.add_widget(self._sec('Notes', 'note-text'))
        self.body.add_widget(self._fld('notes', 'Internal Notes', member.get('notes', '')))

    def _save(self):
        if not self._member:
            return
        self.save_btn.disabled = True
        data = {k: f.text.strip() for k, f in self._fields.items() if f.text.strip()}
        if 'monthly_income' in data:
            try:
                data['monthly_income'] = float(data['monthly_income'])
            except ValueError:
                data.pop('monthly_income')

        threading.Thread(target=self._run_save, args=(data,), daemon=True).start()

    def _run_save(self, data: dict):
        try:
            # Build UPDATE query dynamically
            cols = ', '.join(f"{k} = ?" for k in data)
            vals = list(data.values()) + [self.member_id]
            self.app.db.execute(
                f"UPDATE members SET {cols}, updated_at = ? WHERE id = ?",
                vals[:-1] + [datetime.datetime.now().isoformat(), self.member_id]
            )
            self.app.db.log_change(
                'members', self.member_id, 'UPDATE',
                new_data=data, user_id=self.app.current_user_id,
                device_id=self.app.device_id
            )
            Clock.schedule_once(lambda dt: self._on_saved(), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self._on_error(_e), 0)

    def _on_saved(self):
        self.save_btn.disabled = False
        self.show_success('Member updated successfully')
        self.app.go_back()

    def _on_error(self, msg):
        self.save_btn.disabled = False
        self.show_error(msg)

    def _toggle_suspend(self):
        if not self._member:
            return
        is_active = self._member.get('is_active', 1)
        action = 'activate' if not is_active else 'suspend'

        def _do():
            self.app.db.execute(
                "UPDATE members SET is_active = ? WHERE id = ?",
                (0 if is_active else 1, self.member_id)
            )
            Clock.schedule_once(
                lambda dt: (self.show_success(f'Member {action}d'), self._load()), 0
            )

        self.confirm_dialog(
            f'{action.title()} Member',
            f'Are you sure you want to {action} this member?',
            _do
        )


# ─────────────────────────────────────────────────────────────────────────────
# KYC APPROVAL SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class KYCApprovalScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'kyc_approval'
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='KYC Approval Queue',
            md_bg_color=get_color('warning'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        # Stats row
        self.stats_row = MDBoxLayout(
            size_hint_y=None, height=dp(60),
            padding=[dp(12), dp(8)], spacing=dp(8)
        )
        self._stat_lbls = {}
        for key, color in [('Pending', 'warning'), ('Complete', 'primary'), ('Verified', 'success'), ('Rejected', 'error')]:
            card = MDCard(
                orientation='vertical', size_hint_x=1, size_hint_y=None, height=dp(44),
                padding=dp(4), radius=[dp(8)],
                md_bg_color=get_color(f'{color}_container', 0.35), elevation=0
            )
            lbl_n = MDLabel(text='—', font_style='H6', bold=True, halign='center',
                            theme_text_color='Custom', text_color=get_color(color),
                valign='middle'
            )
            lbl_k = MDLabel(text=key, font_style='Caption', halign='center', theme_text_color='Secondary',
                valign='middle'
            )
            card.add_widget(lbl_n)
            card.add_widget(lbl_k)
            self._stat_lbls[key] = lbl_n
            self.stats_row.add_widget(card)
        root.add_widget(self.stats_row)

        # Filter tabs
        filter_row = MDBoxLayout(
            size_hint_y=None, height=dp(44),
            padding=[dp(8), dp(4)], spacing=dp(6)
        )
        self._filter = 'pending'
        self._filter_btns = {}
        for status, color in [('pending', 'warning'), ('complete', 'primary'), ('verified', 'success')]:
            btn = MDCard(
                size_hint_x=1, size_hint_y=None, height=dp(36),
                radius=[dp(8)],
                md_bg_color=get_color(color) if status == 'pending' else get_color('surface_variant', 0.4),
                ripple_behavior=True,
                on_release=lambda x, s=status: self._set_filter(s)
            )
            btn.add_widget(MDLabel(
                text=status.title(), halign='center', font_style='Caption',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if status == 'pending' else get_color('outline'),
                valign='middle'
            ))
            self._filter_btns[status] = btn
            filter_row.add_widget(btn)
        root.add_widget(filter_row)

        scroll = MDScrollView()
        self.list_box = MDBoxLayout(
            orientation='vertical', spacing=dp(8),
            padding=dp(12), size_hint_y=None
        )
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            stats = {}
            for status in ['pending', 'complete', 'verified', 'rejected']:
                r = self.app.db.fetch_one(
                    "SELECT COUNT(*) c FROM members WHERE kyc_status=?", (status,)
                )
                stats[status.title()] = r['c']
            members = self.app.db.fetch_all(
                "SELECT * FROM members WHERE kyc_status=? AND is_active=1 "
                "ORDER BY membership_date DESC LIMIT 50",
                (self._filter,)
            )
            Clock.schedule_once(lambda dt: self._render(members, stats), 0)
        except Exception as e:
            Logger.error(f'KYCApproval: {e}')

    def _render(self, members, stats):
        for key, lbl in self._stat_lbls.items():
            lbl.text = str(stats.get(key, 0))

        self.list_box.clear_widgets()
        if not members:
            self.list_box.add_widget(MDLabel(
                text='No members in this queue',
                halign='center', theme_text_color='Secondary',
                size_hint_y=None, height=dp(60),
                valign='middle'
            ))
            return

        for m in members:
            card = MDCard(
                orientation='vertical', size_hint_y=None, height=dp(120),
                padding=dp(14), radius=[dp(12)],
                md_bg_color=get_color('surface_variant', 0.2), elevation=1
            )
            # Header row
            hrow = MDBoxLayout(size_hint_y=None, height=dp(28))
            hrow.add_widget(MDLabel(
                text=f"{m.get('first_name')} {m.get('last_name')}",
                font_style='Subtitle1', bold=True,
                valign='middle'
            ))
            score = m.get('kyc_score', 0)
            score_color = 'success' if score >= 80 else 'warning' if score >= 50 else 'error'
            hrow.add_widget(MDLabel(
                text=f"Score: {score}/100",
                halign='right', font_style='Caption',
                theme_text_color='Custom', text_color=get_color(score_color),
                valign='middle'
            ))
            # Meta
            meta = MDLabel(
                text=f"{m.get('member_no', '')}  •  {m.get('phone', '')}  •  Joined {m.get('membership_date', '')}",
                font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(22),
                valign='middle'
            )
            # Action row
            arow = MDBoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
            if self._filter in ('pending', 'complete'):
                arow.add_widget(MDRaisedButton(
                    text='VERIFY',
                    md_bg_color=get_color('success'),
                    size_hint_x=None, width=dp(90),
                    on_release=lambda x, mid=m['id']: self._approve(mid, 'verified')
                ))
                arow.add_widget(MDRaisedButton(
                    text='REJECT',
                    md_bg_color=get_color('error'),
                    size_hint_x=None, width=dp(90),
                    on_release=lambda x, mid=m['id']: self._approve(mid, 'rejected')
                ))
            arow.add_widget(MDFlatButton(
                text='VIEW PROFILE',
                theme_text_color='Custom',
                text_color=get_color('primary'),
                on_release=lambda x, mid=m['id']: self.app.navigate_to('member_profile', member_id=mid)
            ))

            card.add_widget(hrow)
            card.add_widget(meta)
            card.add_widget(arow)
            self.list_box.add_widget(card)

    def _set_filter(self, status: str):
        self._filter = status
        filter_colors = {'pending': 'warning', 'complete': 'primary', 'verified': 'success'}
        for s, btn in self._filter_btns.items():
            active = s == status
            c = filter_colors.get(s, 'outline')
            btn.md_bg_color = get_color(c) if active else get_color('surface_variant', 0.4)
            btn.children[0].text_color = (1, 1, 1, 1) if active else get_color('outline')
        threading.Thread(target=self._load, daemon=True).start()

    def _approve(self, member_id: str, new_status: str):
        def _do():
            self.app.db.execute(
                "UPDATE members SET kyc_status=?, updated_at=? WHERE id=?",
                (new_status, datetime.datetime.now().isoformat(), member_id)
            )
            Clock.schedule_once(
                lambda dt: (self.show_success(f'KYC status updated to {new_status}'),
                            threading.Thread(target=self._load, daemon=True).start()), 0
            )

        self.confirm_dialog(
            f'{"Verify" if new_status == "verified" else "Reject"} KYC',
            f'Set KYC status to [b]{new_status}[/b] for this member?',
            _do
        )


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class NotificationsScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'notifications'
        self._build()

    def _build(self):
        from kivy.uix.floatlayout import FloatLayout
        float_root = FloatLayout()
        root = MDBoxLayout(orientation='vertical', size_hint=(1, 1))

        self.toolbar = MDTopAppBar(
            title='Notifications',
            md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['check-all', lambda x: self._mark_all_read()]
            ]
        )
        root.add_widget(self.toolbar)

        # Admin compose panel — hidden by default, shown for staff only
        self._compose_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(0),
            padding=[dp(16), 0], radius=[dp(0)],
            md_bg_color=get_color('primary_container', 0.2), elevation=0,
            opacity=0
        )
        self._compose_card.add_widget(MDLabel(
            text='📢  Send Notification to Members', font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color('primary'),
            size_hint_y=None, height=dp(32), valign='middle'
        ))
        self.sms_field = MDTextField(
            hint_text='Type your message to members…',
            mode='rectangle', multiline=True,
            line_color_focus=get_color('primary'),
            size_hint_y=None, height=dp(72)
        )
        self._compose_card.add_widget(self.sms_field)
        sms_btn_row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8), padding=[0, dp(4)])
        for label, target, color in [
            ('All Members', 'all', 'primary'),
            ('Overdue', 'overdue', 'error'),
            ('New (30d)', 'new', 'success'),
            ('Custom', 'custom', 'secondary'),
        ]:
            sms_btn_row.add_widget(MDRaisedButton(
                text=label, md_bg_color=get_color(color), size_hint_x=1,
                size_hint_y=None, height=dp(38),
                on_release=lambda x, t=target: self._send_bulk_sms(t)
            ))
        self._compose_card.add_widget(sms_btn_row)

        # Filter tabs (All | Unread | System)
        filter_row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6),
                                 padding=[dp(12), dp(4)])
        self._active_filter = 'all'
        self._filter_btns = {}
        for key, lbl in [('all','All'),('unread','Unread'),('system','System'),('sms','SMS')]:
            active = key == 'all'
            btn = MDCard(size_hint=(None,None), size=(dp(64), dp(34)),
                         radius=[dp(17)],
                         md_bg_color=get_color('primary') if active else get_color('surface_variant',0.4),
                         ripple_behavior=True,
                         on_release=lambda x,k=key: self._set_filter(k))
            bl = MDLabel(text=lbl, halign='center', valign='middle',
                         font_style='Caption', bold=active,
                         theme_text_color='Custom',
                         text_color=(1,1,1,1) if active else get_color('on_surface'))
            btn.add_widget(bl)
            self._filter_btns[key] = (btn, bl)
            filter_row.add_widget(btn)

        scroll = MDScrollView(size_hint=(1,1))
        self.notif_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6),
            padding=[dp(12), dp(8)], size_hint_y=None
        )
        self.notif_box.bind(minimum_height=self.notif_box.setter('height'))
        scroll.add_widget(self.notif_box)

        root.add_widget(self._compose_card)
        root.add_widget(filter_row)
        root.add_widget(scroll)
        float_root.add_widget(root)
        self.add_widget(float_root)
        self._all_notifs = []

    def on_enter(self):
        # Show/hide compose panel based on role
        role = self.app.current_user_role or 'member'
        is_staff = role not in ('member',)
        from kivy.animation import Animation as _Anim
        if is_staff:
            _Anim(height=dp(164), opacity=1, duration=0.2).start(self._compose_card)
        else:
            _Anim(height=dp(0), opacity=0, duration=0.1).start(self._compose_card)
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            role = self.app.current_user_role or 'member'
            uid = self.app.current_user_id
            if role == 'member':
                # Members see only their own notifications
                user = self.app.db.fetch_one(
                    "SELECT member_id FROM users WHERE id=?", (uid,))
                mid = (user or {}).get('member_id')
                if mid:
                    notifs = self.app.db.fetch_all(
                        "SELECT * FROM notifications WHERE member_id=? "
                        "ORDER BY created_at DESC LIMIT 100", (mid,))
                else:
                    notifs = self.app.db.fetch_all(
                        "SELECT * FROM notifications WHERE user_id=? "
                        "ORDER BY created_at DESC LIMIT 100", (uid,))
            else:
                # Staff see all
                notifs = self.app.db.fetch_all(
                    "SELECT n.*, m.first_name, m.last_name FROM notifications n "
                    "LEFT JOIN members m ON n.member_id=m.id "
                    "ORDER BY n.created_at DESC LIMIT 200")
            Clock.schedule_once(lambda dt: self._got_notifs(notifs), 0)
        except Exception as e:
            Logger.error(f'Notifications: {e}')
            Clock.schedule_once(lambda dt: self._got_notifs([]), 0)

    def _got_notifs(self, notifs):
        self._all_notifs = notifs
        self._render(notifs)

    def _set_filter(self, key):
        self._active_filter = key
        for k, (btn, lbl) in self._filter_btns.items():
            active = k == key
            btn.md_bg_color = get_color('primary') if active else get_color('surface_variant', 0.4)
            lbl.text_color = (1,1,1,1) if active else get_color('on_surface')
            lbl.bold = active
        if key == 'unread':
            filtered = [n for n in self._all_notifs if not n.get('is_read')]
        elif key == 'system':
            filtered = [n for n in self._all_notifs if n.get('notification_type') in ('system','push','alert')]
        elif key == 'sms':
            filtered = [n for n in self._all_notifs if n.get('notification_type') == 'sms']
        else:
            filtered = self._all_notifs
        self._render(filtered)

    def _render(self, notifs):
        from kivy.uix.relativelayout import RelativeLayout
        from kivy.graphics import Color as _C, RoundedRectangle as _RR
        self.notif_box.clear_widgets()
        if not notifs:
            self.notif_box.add_widget(MDLabel(
                text="No notifications yet. You're all caught up!",
                halign='center', theme_text_color='Secondary',
                size_hint_y=None, height=dp(80), valign='middle'
            ))
            return

        type_icons = {
            'sms': 'message-text', 'email': 'email-outline', 'push': 'bell-ring',
            'loan_reminder': 'cash-clock', 'overdue': 'alert-circle',
            'system': 'information-outline', 'alert': 'alert-circle-outline',
        }
        type_colors = {
            'sms': 'primary', 'email': 'secondary', 'push': 'tertiary',
            'loan_reminder': 'quaternary', 'overdue': 'error',
            'system': 'info', 'alert': 'warning',
        }
        for n in notifs:
            ntype = n.get('notification_type', 'sms')
            color = type_colors.get(ntype, 'primary')
            icon = type_icons.get(ntype, 'bell-outline')
            is_read = bool(n.get('is_read'))

            card = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(80),
                padding=[dp(12), dp(8)], spacing=dp(10), radius=[dp(12)],
                md_bg_color=get_color('surface_variant', 0.1) if is_read
                            else get_color(f'{color}_container', 0.18),
                elevation=0 if is_read else 1,
                ripple_behavior=True,
                on_release=lambda x, nid=n.get('id'): self._mark_read(nid)
            )

            # Icon circle
            ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(42), dp(42)))
            with ic_rl.canvas.before:
                _C(*get_color(f'{color}_container', 0.55))
                _RR(pos=(0,0), size=(dp(42),dp(42)), radius=[dp(21)])
            ic_rl.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle', font_size=sp(18),
                size_hint=(None,None), size=(dp(22),dp(22)),
                pos_hint={'center_x':0.5,'center_y':0.5}
            ))
            card.add_widget(ic_rl)

            info = MDBoxLayout(orientation='vertical', spacing=dp(2))
            title = n.get('title') or ntype.replace('_',' ').title()
            msg = n.get('message','')
            info.add_widget(MDLabel(
                text=title,
                font_style='Subtitle2', bold=not is_read,
                theme_text_color='Primary' if not is_read else 'Secondary',
                size_hint_y=None, height=dp(22), valign='middle'
            ))
            info.add_widget(MDLabel(
                text=msg[:70] + ('…' if len(msg) > 70 else ''),
                font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(18), valign='middle'
            ))
            date_str = str(n.get('created_at') or n.get('sent_at') or '')[:16]
            sender_str = ''
            if n.get('first_name'):
                sender_str = f"To: {n['first_name']} {n.get('last_name','')}  •  "
            info.add_widget(MDLabel(
                text=f"{sender_str}{date_str}",
                font_style='Caption', theme_text_color='Hint',
                size_hint_y=None, height=dp(16), valign='middle'
            ))
            card.add_widget(info)

            if not is_read:
                dot_rl = RelativeLayout(size_hint=(None,None), size=(dp(10),dp(10)),
                                        pos_hint={'center_y':0.5})
                with dot_rl.canvas.before:
                    _C(*get_color(color))
                    _RR(pos=(0,0), size=(dp(10),dp(10)), radius=[dp(5)])
                card.add_widget(dot_rl)

            self.notif_box.add_widget(card)

    def _mark_read(self, notif_id):
        if not notif_id:
            return
        try:
            self.app.db.execute(
                "UPDATE notifications SET is_read=1, read_at=? WHERE id=?",
                (datetime.datetime.now().isoformat(), notif_id)
            )
            threading.Thread(target=self._load, daemon=True).start()
        except Exception as e:
            Logger.warning(f'Mark read: {e}')

    def _send_bulk_sms(self, target: str):
        role = self.app.current_user_role or 'member'
        if role == 'member':
            self.show_error('Members cannot send notifications')
            return
        msg = self.sms_field.text.strip()
        if not msg:
            self.show_error('Enter a message first')
            return
        self.show_info(f'Sending to {target} members…')
        threading.Thread(target=self._do_send, args=(msg, target), daemon=True).start()

    def _do_send(self, msg: str, target: str):
        try:
            if target == 'all':
                members = self.app.db.fetch_all(
                    "SELECT id FROM members WHERE is_active=1"
                )
            elif target == 'overdue':
                members = self.app.db.fetch_all(
                    "SELECT DISTINCT a.member_id id FROM loans l "
                    "JOIN accounts a ON l.member_id=a.member_id "
                    "WHERE l.status='overdue'"
                )
            else:
                members = self.app.db.fetch_all(
                    "SELECT id FROM members WHERE membership_date >= date('now','-30 days')"
                )
            count = len(members)
            for m in members:
                self.app.db.execute(
                    "INSERT INTO notifications (id, member_id, notification_type, title, message, is_read, created_at) "
                    "VALUES (?, ?, 'sms', 'Announcement', ?, 0, ?)",
                    (__import__('uuid').uuid4().hex, m['id'], msg,
                     datetime.datetime.now().isoformat())
                )
            Clock.schedule_once(
                lambda dt: (self.show_success(f'SMS sent to {count} members'),
                            self.on_enter()), 0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _mark_all_read(self):
        self.app.db.execute("UPDATE notifications SET is_read=1")
        self.on_enter()


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class SettingsScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'settings'
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Settings',
            md_bg_color=get_color('outline'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        body = MDBoxLayout(
            orientation='vertical', spacing=dp(8),
            padding=dp(14), size_hint_y=None
        )
        body.bind(minimum_height=body.setter('height'))

        sections = [
            ('Theme & Display', 'palette', 'primary', self._build_theme_section),
            ('Security', 'shield-lock', 'error', self._build_security_section),
            ('Mobile Money (M-Pesa / Airtel)', 'cellphone-arrow-down', 'success', self._build_mpesa_section),
            ('Notifications', 'bell', 'quinary', self._build_notif_section),
            ('Data & Sync', 'sync', 'secondary', self._build_sync_section),
            ('About', 'information', 'outline', self._build_about_section),
        ]

        for title, icon, color, builder in sections:
            header = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(44),
                padding=[dp(12), 0], spacing=dp(8), radius=[dp(8), dp(8), 0, 0],
                md_bg_color=get_color(f'{color}_container', 0.35), elevation=0
            )
            header.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom',
                text_color=get_color(color), size_hint_x=None, width=dp(28),
                valign='middle'
            ))
            header.add_widget(MDLabel(
                text=title, font_style='Subtitle1', bold=True,
                theme_text_color='Custom', text_color=get_color(color),
                valign='middle'
            ))
            body.add_widget(header)

            content = MDCard(
                orientation='vertical', padding=dp(8), radius=[0, 0, dp(8), dp(8)],
                md_bg_color=get_color('surface_variant', 0.15),
                size_hint_y=None, elevation=0
            )
            builder(content)
            content.bind(minimum_height=content.setter('height'))
            body.add_widget(content)
            body.add_widget(MDBoxLayout(size_hint_y=None, height=dp(8)))

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    def _toggle_row(self, label, subtitle, default=False):
        row = MDBoxLayout(size_hint_y=None, height=dp(52), padding=[dp(4), 0])
        info = MDBoxLayout(orientation='vertical')
        info.add_widget(MDLabel(text=label, font_style='Subtitle2', size_hint_y=None, height=dp(24),
            valign='middle'
        ))
        info.add_widget(MDLabel(
            text=subtitle, font_style='Caption',
            theme_text_color='Secondary', size_hint_y=None, height=dp(18),
            valign='middle'
        ))
        sw = MDSwitch(
            size_hint=(None, None), size=(dp(56), dp(28)),
        )
        # Set active after construction to avoid KivyMD 1.2.0 ids.thumb crash
        from kivy.clock import Clock as _Clk
        _Clk.schedule_once(lambda dt, _sw=sw, _d=default: setattr(_sw, 'active', _d), 0)
        row.add_widget(info)
        row.add_widget(Widget())
        row.add_widget(sw)
        return row, sw

    def _build_mpesa_section(self, parent):
        """M-Pesa Daraja + Airtel Money credentials — stored in system_settings."""
        from services_mobile_money import _get_setting, _set_setting

        def _read(k):
            try:
                return _get_setting(self.app.db, k, '')
            except Exception:
                return ''

        def _field(db_key, hint, password=False):
            tf = MDTextField(
                hint_text=hint, mode='rectangle',
                password=password,
                line_color_focus=get_color('success'),
                size_hint_y=None, height=dp(54)
            )
            tf._mm_db_key = db_key
            # Populate text after widget is added (avoids build-time app.db timing issues)
            from kivy.clock import Clock as _Clk
            _Clk.schedule_once(lambda dt, _tf=tf, _k=db_key: setattr(_tf, 'text', _read(_k)), 0.1)
            parent.add_widget(tf)
            return tf

        def _lbl(text, color='success'):
            parent.add_widget(MDLabel(
                text=text, font_style='Caption', bold=True,
                theme_text_color='Custom', text_color=get_color(color),
                size_hint_y=None, height=dp(28), valign='middle'
            ))

        def _sublbl(text):
            parent.add_widget(MDLabel(
                text=text, font_style='Caption',
                theme_text_color='Secondary',
                size_hint_y=None, height=dp(20), valign='middle'
            ))

        def _toggle(db_key, label, value_fn=None, read_fn=None):
            """
            db_key:   key to save '1'/'0' in system_settings
            label:    display text
            value_fn: optional callable(val:bool) called on toggle — overrides default save
            read_fn:  optional callable() -> bool to read initial state
            """
            row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            row.add_widget(MDLabel(text=label, font_style='Body2', valign='middle'))
            row.add_widget(MDBoxLayout())   # spacer
            sw = MDSwitch(size_hint=(None, None), size=(dp(56), dp(28)))
            row.add_widget(sw)
            parent.add_widget(row)

            def _on_change(inst, val):
                try:
                    if value_fn:
                        value_fn(val)
                    else:
                        _set_setting(self.app.db, db_key, '1' if val else '0')
                except Exception as e:
                    Logger.error(f'Settings toggle {db_key}: {e}')

            sw.bind(active=_on_change)

            # Set initial value after render
            from kivy.clock import Clock as _Clk
            def _set_initial(dt):
                try:
                    if read_fn:
                        sw.active = read_fn()
                    else:
                        sw.active = _read(db_key) == '1'
                except Exception:
                    pass
            _Clk.schedule_once(_set_initial, 0.15)

        # ─────────────────────────────────────────────────────────────────────
        # M-PESA
        # ─────────────────────────────────────────────────────────────────────
        _lbl('① M-PESA  (Safaricom Daraja B2C)')
        _toggle(
            'mpesa_sandbox',
            'Sandbox / Test mode  (turn OFF for real money)',
            read_fn=lambda: _read('mpesa_sandbox') == '1'
        )

        fields_mpesa = []
        for db_key, hint, pw in [
            ('mpesa_consumer_key',        'Consumer Key  (from Daraja portal)',                                  False),
            ('mpesa_consumer_secret',     'Consumer Secret  (from Daraja portal)',                              True),
            ('mpesa_shortcode',           'Paybill Number  (your business shortcode)',                         False),
            ('mpesa_initiator_name',      'Initiator Name  (API operator username)',                           False),
            ('mpesa_security_credential', 'Security Credential  (Base64 from Daraja portal — see guide below)', True),
        ]:
            fields_mpesa.append(_field(db_key, hint, pw))

        # Security credential guide card
        guide_card = MDCard(
            orientation='vertical', padding=[dp(12), dp(8)], spacing=dp(2),
            radius=[dp(8)], elevation=0,
            md_bg_color=get_color('primary_container', 0.2),
            size_hint_y=None, height=dp(118)
        )
        guide_card.add_widget(MDLabel(
            text='🔑  How to get Security Credential:',
            font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('primary'),
            size_hint_y=None, height=dp(22), valign='middle'
        ))
        for step in [
            '1. Go to developer.safaricom.co.ke  →  Login',
            '2. APIs → M-Pesa → Security Credential Generator',
            '3. Select Production, enter Initiator Password → Generate',
            '4. Copy the long Base64 string and paste it above',
        ]:
            guide_card.add_widget(MDLabel(
                text=step, font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(22), valign='middle'
            ))
        parent.add_widget(guide_card)

        # STK Push fields
        parent.add_widget(MDBoxLayout(size_hint_y=None, height=dp(6)))
        _lbl('STK Push — Collect from members (optional)')
        _sublbl('Get Passkey: Daraja portal → Production → Lipa Na M-Pesa Online')
        for db_key, hint, pw in [
            ('mpesa_passkey', 'Lipa Na M-Pesa Passkey  (for STK Push deposits)', True),
            ('mpesa_stk_url', 'STK Callback URL  (optional)',                    False),
            ('mpesa_b2c_url', 'B2C Callback URL  (optional)',                    False),
        ]:
            fields_mpesa.append(_field(db_key, hint, pw))

        parent.add_widget(MDRaisedButton(
            text='TEST M-PESA CONNECTION',
            md_bg_color=get_color('success'),
            size_hint_y=None, height=dp(44),
            on_release=lambda x: self._test_mm_connection('mpesa')
        ))

        # ─────────────────────────────────────────────────────────────────────
        # AIRTEL MONEY
        # ─────────────────────────────────────────────────────────────────────
        parent.add_widget(MDBoxLayout(size_hint_y=None, height=dp(12)))
        _lbl('② AIRTEL MONEY')
        _toggle(
            'airtel_env',
            'Staging / Test mode  (turn OFF for real money)',
            value_fn=lambda val: _set_setting(self.app.db, 'airtel_env', 'staging' if val else 'production'),
            read_fn=lambda: _read('airtel_env') == 'staging'
        )

        fields_airtel = []
        for db_key, hint, pw in [
            ('airtel_client_id',     'Client ID  (from developers.airtel.africa)',    False),
            ('airtel_client_secret', 'Client Secret  (from developers.airtel.africa)', True),
            ('airtel_pin',           'Merchant PIN  (Airtel Business account PIN)',   True),
        ]:
            fields_airtel.append(_field(db_key, hint, pw))

        parent.add_widget(MDRaisedButton(
            text='TEST AIRTEL CONNECTION',
            md_bg_color=get_color('error'),
            size_hint_y=None, height=dp(44),
            on_release=lambda x: self._test_mm_connection('airtel')
        ))

        # ─────────────────────────────────────────────────────────────────────
        # SAVE ALL
        # ─────────────────────────────────────────────────────────────────────
        parent.add_widget(MDBoxLayout(size_hint_y=None, height=dp(8)))
        all_fields = fields_mpesa + fields_airtel
        parent.add_widget(MDRaisedButton(
            text='💾  SAVE ALL CREDENTIALS',
            md_bg_color=get_color('primary'),
            size_hint_y=None, height=dp(50),
            on_release=lambda x, flds=all_fields: self._save_mm_credentials(flds)
        ))

    def _save_mm_credentials(self, fields):
        from services_mobile_money import _set_setting
        saved = 0
        for tf in fields:
            if not hasattr(tf, '_mm_db_key'):
                continue
            # Skip the internal toggle proxy key — airtel_env is set by the switch directly
            if tf._mm_db_key == 'airtel_env_toggle':
                continue
            if tf.text.strip():
                _set_setting(self.app.db, tf._mm_db_key, tf.text.strip())
                saved += 1
        # Invalidate cached tokens so next call re-authenticates with new creds
        try:
            self.app.mobile_money_service.mpesa._token  = None
            self.app.mobile_money_service.airtel._token = None
        except Exception:
            pass
        self.show_success(f'Saved {saved} credential(s) ✓  Tap Test to verify.')

    def _test_mm_connection(self, provider):
        """Auto-save credentials from fields then test API connection."""
        from services_mobile_money import _set_setting as _mm_set
        # Collect all credential fields and auto-save them first
        all_fields = []
        def _collect(w):
            if hasattr(w, '_mm_db_key'):
                all_fields.append(w)
            for c in w.children:
                _collect(c)
        _collect(self)
        for tf in all_fields:
            if tf.text.strip():
                _mm_set(self.app.db, tf._mm_db_key, tf.text.strip())
        # Invalidate cached tokens
        try:
            self.app.mobile_money_service.mpesa._token  = None
            self.app.mobile_money_service.airtel._token = None
        except Exception:
            pass

        api_name = 'Safaricom Daraja' if provider == 'mpesa' else 'Airtel Africa'
        prog = MDDialog(
            title='Testing ' + provider.upper() + ' Connection...',
            text='Authenticating with ' + api_name + ' API. Please wait...',
            buttons=[]
        )
        prog.open()

        def _run():
            ok    = False
            title = ''
            body  = ''
            try:
                svc = self.app.mobile_money_service
                if provider == 'mpesa':
                    if not svc.mpesa.is_configured():
                        raise ValueError(
                            'M-Pesa credentials incomplete.\n'
                            'Required: Consumer Key, Consumer Secret,\n'
                            'Paybill Number, Initiator Name,\n'
                            'AND Security Credential (from Daraja portal).'
                        )
                    token     = svc.mpesa._get_token()
                    mode      = 'SANDBOX' if svc.mpesa._is_sandbox else 'LIVE'
                    has_cred  = bool(svc.mpesa._cfg('security_credential'))
                    cred_note = 'Security Credential: ✓ Set' if has_cred else '⚠ Security Credential: NOT SET\n(Required for B2C transfers)'
                    title = 'M-Pesa Connected ✓'
                    body  = (
                        'OAuth token received!\n\n'
                        'Mode: ' + mode + '\n'
                        'Paybill: ' + svc.mpesa._cfg('shortcode') + '\n'
                        'Initiator: ' + svc.mpesa._cfg('initiator_name') + '\n'
                        + cred_note + '\n'
                        'Token: ' + token[:20] + '...'
                    )
                    ok = not (mode == 'LIVE' and not has_cred)
                    if mode == 'LIVE' and not has_cred:
                        title = 'Auth OK but incomplete ⚠'
                else:
                    if not svc.airtel.is_configured():
                        raise ValueError(
                            'Airtel credentials incomplete.\n'
                            'Fill in: Client ID and Client Secret.'
                        )
                    token = svc.airtel._get_token()
                    mode  = 'STAGING' if svc.airtel._is_staging else 'PRODUCTION'
                    title = 'Airtel Money Connected ✓'
                    body  = (
                        'Connection successful!\n\n'
                        'Mode: ' + mode + '\n'
                        'Country: ' + svc.airtel._cfg('country', 'KE') + '\n'
                        'Token: ' + token[:20] + '...'
                    )
                    ok = True
            except Exception as e:
                err   = str(e)
                title = provider.upper() + ' Connection Failed'
                if 'HTTP 401' in err or 'bad credentials' in err.lower():
                    body = ('Authentication failed (401).\n\n'
                            'Wrong Consumer Key or Secret.\n'
                            'Copy them exactly from the developer portal.')
                elif 'HTTP 400' in err:
                    body = 'Bad request (400).\n' + err[:300]
                elif 'Network error' in err or 'timed out' in err.lower():
                    body = ('Cannot reach API server.\n\n'
                            'Check internet connection and firewall settings.')
                elif 'not configured' in err.lower() or 'incomplete' in err.lower():
                    body = err
                elif 'cert' in err.lower():
                    body = ('Certificate error.\n\n'
                            'Production: place safaricom_cert.cer in data/ folder.\n'
                            'Or enable Sandbox mode for testing.')
                else:
                    body = 'Error: ' + err[:400]

            def _show(dt):
                prog.dismiss()
                d = MDDialog(
                    title=title,
                    text=body,
                    buttons=[MDRaisedButton(
                        text='OK',
                        md_bg_color=get_color('success' if ok else 'error'),
                        on_release=lambda x: d.dismiss()
                    )]
                )
                d.open()
            Clock.schedule_once(_show, 0)

        threading.Thread(target=_run, daemon=True).start()

    def _build_theme_section(self, parent):
        themes = ['Light', 'Dark', 'System']
        theme_row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6), padding=[dp(4), dp(4)])
        for t in themes:
            active = t == 'Light'
            btn = MDCard(
                size_hint_x=1, size_hint_y=None, height=dp(36),
                radius=[dp(8)],
                md_bg_color=get_color('primary') if active else get_color('surface_variant', 0.4),
                ripple_behavior=True,
                on_release=lambda x, theme=t: self._set_theme(theme)
            )
            btn.add_widget(MDLabel(
                text=t, halign='center', font_style='Caption',
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if active else get_color('on_surface'),
                valign='middle'
            ))
            theme_row.add_widget(btn)
        parent.add_widget(theme_row)

    def _build_security_section(self, parent):
        r1, _ = self._toggle_row('Require PIN on startup', 'Ask for PIN every time app opens', True)
        r2, _ = self._toggle_row('Biometric login', 'Use fingerprint or face ID', False)
        r3, _ = self._toggle_row('Auto-lock after 5 min', 'Lock screen after inactivity', True)
        for r in [r1, r2, r3]:
            parent.add_widget(r)

        parent.add_widget(MDRaisedButton(
            text='CHANGE PASSWORD',
            md_bg_color=get_color('error'),
            size_hint_y=None, height=dp(44),
            on_release=lambda x: self._change_password()
        ))

    def _build_notif_section(self, parent):
        r1, _ = self._toggle_row('SMS Alerts', 'Receive SMS on transactions', True)
        r2, _ = self._toggle_row('Email Alerts', 'Receive email summaries', True)
        r3, _ = self._toggle_row('Overdue Reminders', 'Alert for overdue loans', True)
        r4, _ = self._toggle_row('Daily Summary', 'Receive daily digest', False)
        for r in [r1, r2, r3, r4]:
            parent.add_widget(r)

    def _build_sync_section(self, parent):
        r1, _ = self._toggle_row('Auto-sync', 'Sync data automatically on Wi-Fi', True)
        parent.add_widget(r1)
        parent.add_widget(MDRaisedButton(
            text='SYNC NOW',
            md_bg_color=get_color('secondary'),
            size_hint_y=None, height=dp(44),
            on_release=lambda x: self._manual_sync()
        ))
        parent.add_widget(MDRaisedButton(
            text='BACKUP DATABASE',
            md_bg_color=get_color('tertiary'),
            size_hint_y=None, height=dp(44),
            on_release=lambda x: self._backup()
        ))

    def _build_about_section(self, parent):
        for label, value in [
            ('App Version', 'HELA SMART SACCO v3.0'),
            ('Build', '2025.1'),
            ('Database', 'SQLite WAL'),
            ('Encryption', 'AES-256-GCM'),
        ]:
            row = MDBoxLayout(size_hint_y=None, height=dp(36), padding=[dp(4), 0])
            row.add_widget(MDLabel(
                text=label, theme_text_color='Secondary', size_hint_x=0.5,
                valign='middle'
            ))
            row.add_widget(MDLabel(text=value, size_hint_x=0.5, bold=True,
                valign='middle'
            ))
            parent.add_widget(row)

    def _set_theme(self, theme: str):
        styles = {'Light': 'Light', 'Dark': 'Dark'}
        if theme in styles:
            self.app.theme_cls.theme_style = styles[theme]
        self.show_info(f'Theme set to {theme}')

    def _change_password(self):
        self.show_info('Password change dialog coming soon')

    def _manual_sync(self):
        self.show_info('Sync started…')
        threading.Thread(target=self._run_sync, daemon=True).start()

    def _run_sync(self):
        try:
            stats = self.app.sync_service.get_sync_stats()
            Clock.schedule_once(
                lambda dt: self.show_success(f"Sync complete. Pending: {stats.get('pending_changes', 0)}"), 0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _backup(self):
        self.show_info('Database backup started…')
        threading.Thread(target=self._run_backup, daemon=True).start()

    def _run_backup(self):
        import shutil, os
        try:
            src = os.path.join(self.app.data_dir, 'hela_sacco_v3.db')
            dst = os.path.join(
                self.app.backups_dir,
                f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            shutil.copy2(src, dst)
            Clock.schedule_once(
                lambda dt: self.show_success(f'Backup saved'), 0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)


# ─────────────────────────────────────────────────────────────────────────────
# BRANCH MANAGEMENT SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class BranchManagementScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'branch_management'
        self._branches = []
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Branch Management',
            md_bg_color=get_color('tertiary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['plus', lambda x: self._add_branch_dialog()]
            ]
        )
        root.add_widget(self.toolbar)

        scroll = MDScrollView()
        self.branch_box = MDBoxLayout(
            orientation='vertical', spacing=dp(10),
            padding=dp(14), size_hint_y=None
        )
        self.branch_box.bind(minimum_height=self.branch_box.setter('height'))
        scroll.add_widget(self.branch_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            branches = self.app.db.fetch_all(
                "SELECT b.*, "
                "(SELECT COUNT(*) FROM members WHERE branch_id=b.id AND is_active=1) member_count, "
                "(SELECT COUNT(*) FROM loans WHERE branch_id=b.id AND status IN ('active','disbursed')) loan_count "
                "FROM branches b WHERE b.is_active=1 ORDER BY b.name"
            )
            Clock.schedule_once(lambda dt: self._render(branches), 0)
        except Exception as e:
            Logger.error(f'BranchMgmt: {e}')

    def _render(self, branches):
        self._branches = branches
        self.branch_box.clear_widgets()

        if not branches:
            self.branch_box.add_widget(MDLabel(
                text='No branches found. Add one with the + button.',
                halign='center', theme_text_color='Secondary',
                size_hint_y=None, height=dp(80),
                valign='middle'
            ))
            return

        for b in branches:
            card = MDCard(
                orientation='vertical', size_hint_y=None, height=dp(120),
                padding=dp(16), radius=[dp(12)],
                md_bg_color=get_color('surface_variant', 0.2), elevation=1
            )
            hrow = MDBoxLayout(size_hint_y=None, height=dp(30))
            hrow.add_widget(MDLabel(
                text=b.get('name', ''), font_style='Subtitle1', bold=True,
                valign='middle'
            ))
            status = 'active' if b.get('is_active') else 'inactive'
            hrow.add_widget(MDLabel(
                text=('🟢 Active' if status == 'active' else '🔴 Inactive'),
                halign='right', font_style='Caption',
                theme_text_color='Custom',
                text_color=get_color('success' if status == 'active' else 'error'),
                valign='middle'
            ))
            card.add_widget(hrow)
            card.add_widget(MDLabel(
                text=f"📍 {b.get('address') or ''}  •  {b.get('phone') or ''}",
                font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(22),
                valign='middle'
            ))

            stats_row = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(16))
            for val, label, color in [
                (b.get('member_count', 0), 'Members', 'primary'),
                (b.get('loan_count', 0), 'Active Loans', 'quaternary'),
            ]:
                stats_row.add_widget(MDLabel(
                    text=f"[b]{val}[/b] {label}", markup=True,
                    font_style='Caption', theme_text_color='Custom',
                    text_color=get_color(color),
                    valign='middle'
                ))
            card.add_widget(stats_row)

            btn_row = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
            btn_row.add_widget(MDFlatButton(
                text='EDIT',
                theme_text_color='Custom', text_color=get_color('tertiary'),
                on_release=lambda x, br=b: self._edit_branch_dialog(br)
            ))
            btn_row.add_widget(MDFlatButton(
                text='DEACTIVATE',
                theme_text_color='Custom', text_color=get_color('error'),
                on_release=lambda x, br=b: self._deactivate(br['id'])
            ))
            card.add_widget(btn_row)
            self.branch_box.add_widget(card)

    def _add_branch_dialog(self):
        self._branch_form_dialog(None)

    def _edit_branch_dialog(self, branch: dict):
        self._branch_form_dialog(branch)

    def _branch_form_dialog(self, branch):
        name_field = MDTextField(
            hint_text='Branch Name *',
            text=(branch.get('name') or '') if branch else '',
            mode='rectangle'
        )
        addr_field = MDTextField(
            hint_text='Address',
            text=(branch.get('address') or '') if branch else '',
            mode='rectangle'
        )
        phone_field = MDTextField(
            hint_text='Phone',
            text=(branch.get('phone') or '') if branch else '',
            mode='rectangle'
        )
        content = MDBoxLayout(
            orientation='vertical', spacing=dp(10),
            size_hint_y=None, height=dp(200)
        )
        content.add_widget(name_field)
        content.add_widget(addr_field)
        content.add_widget(phone_field)

        def _save(x):
            if not name_field.text.strip():
                return
            dialog.dismiss()
            threading.Thread(
                target=self._save_branch,
                args=(branch, name_field.text.strip(),
                      addr_field.text.strip(), phone_field.text.strip()),
                daemon=True
            ).start()

        dialog = MDDialog(
            title='Add Branch' if not branch else 'Edit Branch',
            type='custom', content_cls=content, radius=[dp(16)],
            buttons=[
                MDFlatButton(text='CANCEL', on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text='SAVE', md_bg_color=get_color('tertiary'),
                    on_release=_save
                )
            ]
        )
        dialog.open()

    def _save_branch(self, existing, name, address, phone):
        import uuid
        try:
            if existing:
                self.app.db.execute(
                    "UPDATE branches SET name=?, address=?, phone=? WHERE id=?",
                    (name, address, phone, existing['id'])
                )
            else:
                self.app.db.execute(
                    "INSERT INTO branches (id, name, address, phone, is_active, created_at) "
                    "VALUES (?, ?, ?, ?, 1, ?)",
                    (str(uuid.uuid4()), name, address, phone,
                     datetime.datetime.now().isoformat())
                )
            Clock.schedule_once(
                lambda dt: (self.show_success('Branch saved'),
                            threading.Thread(target=self._load, daemon=True).start()), 0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt, _e=str(e): self.show_error(_e), 0)

    def _deactivate(self, branch_id: str):
        def _do():
            self.app.db.execute(
                "UPDATE branches SET is_active=0 WHERE id=?", (branch_id,)
            )
            Clock.schedule_once(
                lambda dt: (self.show_success('Branch deactivated'),
                            threading.Thread(target=self._load, daemon=True).start()), 0
            )
        self.confirm_dialog('Deactivate Branch', 'Are you sure?', _do)


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'audit_log'
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.toolbar = MDTopAppBar(
            title='Audit Log',
            md_bg_color=get_color('error'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['filter-variant', lambda x: self._filter_dialog()]
            ]
        )
        root.add_widget(self.toolbar)

        # Search
        search_row = MDBoxLayout(
            size_hint_y=None, height=dp(60), padding=dp(10), spacing=dp(8)
        )
        self.search_field = MDTextField(
            hint_text='Search by user, table, or action…',
            mode='round', line_color_focus=get_color('error')
        )
        self.search_field.bind(text=self._debounce_search)
        search_row.add_widget(self.search_field)
        root.add_widget(search_row)

        # Table header
        header = MDBoxLayout(
            size_hint_y=None, height=dp(34),
            md_bg_color=get_color('error_container', 0.3),
            padding=[dp(10), 0]
        )
        for col, w in [('Timestamp', 0.22), ('User', 0.18), ('Action', 0.18), ('Table', 0.18), ('Record', 0.24)]:
            header.add_widget(MDLabel(
                text=col, font_style='Caption', bold=True,
                theme_text_color='Custom', text_color=get_color('error'),
                size_hint_x=w,
                valign='middle'
            ))
        root.add_widget(header)

        scroll = MDScrollView()
        self.log_box = MDBoxLayout(
            orientation='vertical', size_hint_y=None, spacing=dp(1)
        )
        self.log_box.bind(minimum_height=self.log_box.setter('height'))
        scroll.add_widget(self.log_box)
        root.add_widget(scroll)

        self.add_widget(root)
        self._search_handle = None

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _debounce_search(self, inst, val):
        if self._search_handle:
            from kivy.clock import Clock as _C
            _C.unschedule(self._search_handle)
        from kivy.clock import Clock as _C
        self._search_handle = _C.schedule_once(
            lambda dt: threading.Thread(target=self._load, daemon=True).start(), 0.5
        )

    def _load(self):
        query = self.search_field.text.strip() if hasattr(self, 'search_field') else ''
        try:
            if query:
                logs = self.app.db.fetch_all(
                    "SELECT * FROM audit_log "
                    "WHERE user_id LIKE ? OR action LIKE ? OR table_name LIKE ? "
                    "ORDER BY timestamp DESC LIMIT 200",
                    (f'%{query}%', f'%{query}%', f'%{query}%')
                )
            else:
                logs = self.app.db.fetch_all(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 200"
                )
            Clock.schedule_once(lambda dt: self._render(logs), 0)
        except Exception as e:
            Logger.error(f'AuditLog: {e}')
            Clock.schedule_once(lambda dt: self._render([]), 0)

    def _render(self, logs):
        self.log_box.clear_widgets()
        if not logs:
            self.log_box.add_widget(MDLabel(
                text='No audit records found', halign='center',
                theme_text_color='Secondary', size_hint_y=None, height=dp(60),
                valign='middle'
            ))
            return

        action_colors = {
            'CREATE': 'success', 'UPDATE': 'warning',
            'DELETE': 'error', 'LOGIN': 'primary', 'EXPORT': 'secondary',
        }
        for i, log in enumerate(logs):
            action = log.get('action', '').upper()
            color = action_colors.get(action, 'outline')
            bg = (1, 1, 1, 1) if i % 2 == 0 else get_color('surface_variant', 0.15)

            row = MDBoxLayout(
                size_hint_y=None, height=dp(40),
                md_bg_color=bg, padding=[dp(10), 0]
            )
            ts = str(log.get('timestamp', ''))[:16]
            user = str(log.get('user_id', ''))[:8] + '…'
            table = log.get('table_name', '')
            record = str(log.get('record_id', ''))[:12] + '…'

            for text, w in [
                (ts, 0.22), (user, 0.18),
                (action, 0.18), (table, 0.18), (record, 0.24)
            ]:
                lbl = MDLabel(text=text, font_style='Caption', size_hint_x=w,
                    valign='middle'
                )
                if text == action:
                    lbl.theme_text_color = 'Custom'
                    lbl.text_color = get_color(color)
                row.add_widget(lbl)
            self.log_box.add_widget(row)

    def _filter_dialog(self):
        self.show_info('Advanced filters coming soon')
