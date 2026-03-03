# screens.py - HELA SMART SACCO v3.0 - All core screens
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import datetime
import threading

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.dialog import MDDialog
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import RAINBOW_COLORS, get_color
from widgets import AnimatedCard, ColorfulButton, StatCard


# ============================================================================
# BASE SCREEN
# ============================================================================

class BaseScreen(MDScreen):
    """Enhanced base screen with theming and utilities"""

    def __init__(self, app=None, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.colors = RAINBOW_COLORS

    def show_snackbar(self, message, color_key='primary', duration=3):
        """KivyMD 1.2.0 compatible snackbar"""
        try:
            snackbar = MDSnackbar(
                MDLabel(
                    text=message,
                    theme_text_color='Custom',
                    text_color=(1, 1, 1, 1),
                    valign='middle'
                ),
                duration=duration,
                size_hint_x=0.9,
                pos_hint={'center_x': 0.5},
                md_bg_color=get_color(color_key),
            )
            snackbar.open()
        except Exception as e:
            Logger.warning(f'Snackbar error: {e}')

    def show_error(self, message):
        self.show_snackbar(message, 'error')

    def show_success(self, message):
        self.show_snackbar(message, 'success')

    def show_info(self, message):
        self.show_snackbar(message, 'info')

    def confirm_dialog(self, title, text, on_confirm, on_cancel=None):
        def _confirm(instance):
            dialog.dismiss()
            on_confirm()

        def _cancel(instance):
            dialog.dismiss()
            if on_cancel:
                on_cancel()

        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDFlatButton(
                    text='CANCEL',
                    theme_text_color='Custom',
                    text_color=get_color('secondary'),
                    on_release=_cancel
                ),
                MDRaisedButton(
                    text='CONFIRM',
                    md_bg_color=get_color('primary'),
                    on_release=_confirm
                )
            ]
        )
        dialog.open()

    def loading_overlay(self, show=True):
        if show:
            if not hasattr(self, '_loading'):
                self._loading = MDBoxLayout(
                    md_bg_color=(0, 0, 0, 0.5),
                    pos_hint={'center_x': 0.5, 'center_y': 0.5},
                    size_hint=(1, 1)
                )
                spinner = MDSpinner(
                    size_hint=(None, None),
                    size=(dp(48), dp(48)),
                    pos_hint={'center_x': 0.5, 'center_y': 0.5},
                    active=True,
                    color=get_color('primary')
                )
                self._loading.add_widget(spinner)
                self.add_widget(self._loading)
        else:
            if hasattr(self, '_loading'):
                self.remove_widget(self._loading)
                del self._loading


# ============================================================================
# LOGIN SCREEN
# ============================================================================

class LoginScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'login'
        self._build()

    def _build(self):
        # Full-screen scroll so nothing is cut off on small screens
        scroll = MDScrollView()
        root = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=0,
            padding=0
        )
        root.bind(minimum_height=root.setter('height'))

        # ── Hero card ──────────────────────────────────────────────────
        hero = MDCard(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(280),
            padding=[dp(24), dp(32), dp(24), dp(28)],
            spacing=dp(10),
            radius=[0, 0, dp(36), dp(36)],
            md_bg_color=get_color('primary'),
            elevation=4
        )

        # Logo circle — AnchorLayout ensures icon stays centered
        from kivy.uix.anchorlayout import AnchorLayout
        from kivy.graphics import Color, Ellipse
        from kivy.uix.widget import Widget as _W

        logo_anchor = AnchorLayout(
            anchor_x='center',
            anchor_y='center',
            size_hint=(None, None),
            size=(dp(80), dp(80)),
            pos_hint={'center_x': 0.5}
        )

        class _Circle(_W):
            def __init__(self, **kw):
                super().__init__(**kw)
                self.bind(pos=self._draw, size=self._draw)
            def _draw(self, *a):
                self.canvas.before.clear()
                with self.canvas.before:
                    Color(1, 1, 1, 0.22)
                    Ellipse(pos=self.pos, size=self.size)

        circle_bg = _Circle(size_hint=(1, 1))
        logo_anchor.add_widget(circle_bg)
        logo_anchor.add_widget(MDIcon(
            icon='bank',
            theme_text_color='Custom',
            text_color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            font_size=sp(42),
            size_hint=(None, None),
            size=(dp(80), dp(80))
        ))
        hero.add_widget(logo_anchor)

        hero.add_widget(MDLabel(
            text='[b]HELA SMART[/b]',
            markup=True,
            font_style='H5',
            halign='center',
            valign='middle',
            theme_text_color='Custom',
            text_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(40)
        ))
        hero.add_widget(MDLabel(
            text='SACCO MANAGEMENT SYSTEM',
            font_style='Subtitle2',
            halign='center',
            valign='middle',
            theme_text_color='Custom',
            text_color=(1, 1, 1, 0.85),
            size_hint_y=None,
            height=dp(24)
        ))
        hero.add_widget(MDLabel(
            text='Empowering Communities Through Finance',
            font_style='Caption',
            halign='center',
            valign='middle',
            theme_text_color='Custom',
            text_color=(1, 1, 1, 0.65),
            size_hint_y=None,
            height=dp(20)
        ))
        root.add_widget(hero)

        # ── Sign-in form ───────────────────────────────────────────────
        form_card = MDBoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(340),
            padding=[dp(24), dp(24), dp(24), dp(16)],
            spacing=dp(12),
        )

        form_card.add_widget(MDLabel(
            text='Sign In to Your Account',
            font_style='H6',
            theme_text_color='Custom',
            text_color=get_color('primary'),
            size_hint_y=None,
            height=dp(36),
            valign='middle'
        ))

        self.username_field = MDTextField(
            hint_text='Username',
            icon_right='account-outline',
            mode='rectangle',
            size_hint_y=None,
            height=dp(56),
            line_color_focus=get_color('primary'),
        )
        self.password_field = MDTextField(
            hint_text='Password',
            icon_right='lock-outline',
            password=True,
            mode='rectangle',
            size_hint_y=None,
            height=dp(56),
            line_color_focus=get_color('primary'),
        )
        form_card.add_widget(self.username_field)
        form_card.add_widget(self.password_field)

        form_card.add_widget(MDLabel(
            text='🔒  Secured with AES-256-GCM encryption',
            font_style='Caption',
            halign='center',
            valign='middle',
            theme_text_color='Custom',
            text_color=get_color('outline'),
            size_hint_y=None,
            height=dp(20)
        ))

        self.login_button = MDRaisedButton(
            text='SIGN IN',
            size_hint=(1, None),
            height=dp(52),
            md_bg_color=get_color('primary'),
            font_size=sp(15),
            on_release=self.do_login
        )
        form_card.add_widget(self.login_button)
        root.add_widget(form_card)

        # ── OR divider ─────────────────────────────────────────────────
        sep_box = MDBoxLayout(
            size_hint=(1, None),
            height=dp(32),
            spacing=dp(8),
            padding=[dp(24), 0]
        )
        sep_box.add_widget(MDBoxLayout(
            md_bg_color=get_color('outline_variant'),
            size_hint=(1, None),
            height=dp(1),
            pos_hint={'center_y': 0.5}
        ))
        sep_box.add_widget(MDLabel(
            text='OR',
            halign='center',
            valign='middle',
            theme_text_color='Custom',
            text_color=get_color('outline'),
            size_hint=(None, None),
            size=(dp(36), dp(32))
        ))
        sep_box.add_widget(MDBoxLayout(
            md_bg_color=get_color('outline_variant'),
            size_hint=(1, None),
            height=dp(1),
            pos_hint={'center_y': 0.5}
        ))
        root.add_widget(sep_box)

        # ── Register card ──────────────────────────────────────────────
        register_card = MDCard(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(64),
            radius=[dp(12)],
            md_bg_color=get_color('secondary_container'),
            ripple_behavior=True,
            elevation=0,
            padding=[dp(14), 0],
            spacing=dp(10),
            on_release=lambda x: self._go_to_register()
        )

        register_card.add_widget(MDIcon(
            icon='account-plus-outline',
            theme_text_color='Custom',
            text_color=get_color('secondary'),
            size_hint=(None, None),
            size=(dp(28), dp(28)),
            pos_hint={'center_y': 0.5}
        ))
        reg_text = MDBoxLayout(orientation='vertical', spacing=dp(2))
        reg_text.add_widget(MDLabel(
            text='New Member? Create an Account',
            font_style='Subtitle2',
            bold=True,
            theme_text_color='Custom',
            text_color=get_color('secondary'),
            size_hint_y=None,
            height=dp(22),
            valign='middle'
        ))
        reg_text.add_widget(MDLabel(
            text='Register in minutes — free to join',
            font_style='Caption',
            theme_text_color='Custom',
            text_color=get_color('outline'),
            size_hint_y=None,
            height=dp(18),
            valign='middle'
        ))
        register_card.add_widget(reg_text)
        register_card.add_widget(MDIcon(
            icon='chevron-right',
            theme_text_color='Custom',
            text_color=get_color('secondary'),
            size_hint=(None, None),
            size=(dp(24), dp(24)),
            pos_hint={'center_y': 0.5}
        ))

        reg_wrapper = MDBoxLayout(
            size_hint=(1, None),
            height=dp(64),
            padding=[dp(24), 0]
        )
        reg_wrapper.add_widget(register_card)
        root.add_widget(reg_wrapper)

        # Bottom padding
        root.add_widget(MDBoxLayout(size_hint_y=None, height=dp(32)))

        scroll.add_widget(root)
        self.add_widget(scroll)

    def _go_to_register(self):
        if self.app:
            self.app.root_sm.current = 'register'

    def do_login(self, *args):
        username = self.username_field.text.strip()
        password = self.password_field.text.strip()
        if not username or not password:
            self.show_error('Please enter both username and password')
            return
        self.login_button.text = 'Authenticating...'
        self.login_button.disabled = True
        threading.Thread(target=self._authenticate, args=(username, password), daemon=True).start()

    def _authenticate(self, username, password):
        try:
            db = self.app.db
            crypto = self.app.crypto

            user = db.fetch_one(
                "SELECT * FROM users WHERE username = ? AND is_active = 1 AND deleted_at IS NULL",
                (username,)
            )

            if not user:
                Clock.schedule_once(lambda dt: self._login_failed('Invalid username or password'), 0)
                return

            if user['is_locked']:
                locked_until = user['locked_until']
                if locked_until:
                    try:
                        lu = datetime.datetime.fromisoformat(str(locked_until))
                        if datetime.datetime.now() < lu:
                            Clock.schedule_once(
                                lambda dt: self._login_failed('Account locked. Try again later.'), 0
                            )
                            return
                        else:
                            db.execute(
                                "UPDATE users SET is_locked=0, failed_attempts=0 WHERE id=?",
                                (user['id'],)
                            )
                    except Exception:
                        pass
                else:
                    Clock.schedule_once(
                        lambda dt: self._login_failed('Account locked. Contact administrator.'), 0
                    )
                    return

            if not crypto.verify_password(
                password, user['salt'], user['password_hash'], user['iterations']
            ):
                new_attempts = (user['failed_attempts'] or 0) + 1
                is_locked = 1 if new_attempts >= 5 else 0
                locked_until = None
                if is_locked:
                    locked_until = (
                        datetime.datetime.now() + datetime.timedelta(minutes=30)
                    ).isoformat()
                db.execute(
                    "UPDATE users SET failed_attempts=?, is_locked=?, locked_until=? WHERE id=?",
                    (new_attempts, is_locked, locked_until, user['id'])
                )
                Clock.schedule_once(
                    lambda dt: self._login_failed(
                        f'Wrong password. Attempt {new_attempts}/5'
                    ), 0
                )
                return

            db.execute(
                "UPDATE users SET failed_attempts=0, last_login=?, device_binding=?, session_token=? WHERE id=?",
                (datetime.datetime.now().isoformat(), self.app.device_id,
                 crypto.generate_secure_token(), user['id'])
            )
            Clock.schedule_once(lambda dt: self._login_success(user), 0)

        except Exception as e:
            Logger.error(f'Login error: {e}')
            import traceback; traceback.print_exc()
            Clock.schedule_once(
                lambda dt, _e=str(e): self._login_failed(f'Login error: {_e[:60]}'), 0
            )

    def _login_failed(self, message):
        self.login_button.text = 'SIGN IN'
        self.login_button.disabled = False
        self.show_error(message)

    def _login_success(self, user):
        self.app.current_user_id = user['id']
        self.app.current_user_role = user['role']
        name = user['full_name'] or user['username']
        self.app.current_user_name = name
        self.app.current_branch_id = user['branch_id']

        services = [
            self.app.member_service, self.app.account_service,
            self.app.loan_service, self.app.sync_service,
            self.app.report_service, self.app.ai_service
        ]
        for svc in services:
            try:
                svc.set_context(user['id'], self.app.device_id, user['branch_id'])
            except Exception as e:
                Logger.warning(f'set_context error: {e}')

        self.login_button.text = 'SIGN IN'
        self.login_button.disabled = False
        self.show_success(f"Welcome, {name.split()[0]}!")
        Clock.schedule_once(lambda dt: self.app.navigate_to('dashboard'), 0.1)

    def on_enter(self):
        """Reset the login screen every time it is shown — handles logout return."""
        self.username_field.text = ''
        self.password_field.text = ''
        self.login_button.text = 'SIGN IN'
        self.login_button.disabled = False


# ============================================================================
# MEMBER REGISTRATION SCREEN
# ============================================================================

class MemberRegistrationScreen(BaseScreen):

    STEPS = ['personal', 'contact', 'employment', 'documents']
    STEP_LABELS = ['Personal', 'Contact', 'Employment', 'Documents']
    STEP_COLORS = ['primary', 'secondary', 'tertiary', 'quaternary']
    STEP_ICONS = ['account-edit', 'phone', 'briefcase-outline', 'file-document-outline']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'register'
        self._current_step = 0
        self.fields = {}
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        self.progress = MDProgressBar(
            value=25,
            color=get_color(self.STEP_COLORS[0]),
            size_hint_y=None, height=dp(5)
        )
        root.add_widget(self.progress)

        self.toolbar = MDTopAppBar(
            title='Create Account',
            md_bg_color=get_color(self.STEP_COLORS[0]),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self._prev_step()]],
        )
        root.add_widget(self.toolbar)

        # Step indicator pills
        from kivy.uix.anchorlayout import AnchorLayout
        self.pill_bar = MDBoxLayout(
            size_hint_y=None, height=dp(52),
            padding=[dp(10), dp(6)], spacing=dp(6)
        )
        self._pills = []
        self._pill_icons = []
        for i, (label, icon) in enumerate(zip(self.STEP_LABELS, self.STEP_ICONS)):
            pill = MDCard(
                orientation='vertical',
                size_hint_x=1, size_hint_y=None, height=dp(38),
                radius=[dp(8)], padding=0, spacing=0,
                md_bg_color=get_color(self.STEP_COLORS[i]) if i == 0 else get_color('surface_variant', 0.5),
                elevation=2 if i == 0 else 0,
                on_release=lambda x, idx=i: self._jump_to_step(idx)
            )
            anchor = AnchorLayout(anchor_x='center', anchor_y='center', size_hint=(1, 1))
            ic = MDIcon(
                icon=icon,
                halign='center',
                valign='middle',
                font_size=sp(16),
                size_hint=(None, None),
                size=(dp(24), dp(24)),
                theme_text_color='Custom',
                text_color=(1, 1, 1, 1) if i == 0 else get_color('outline')
            )
            anchor.add_widget(ic)
            pill.add_widget(anchor)
            self._pills.append(pill)
            self._pill_icons.append(ic)
            self.pill_bar.add_widget(pill)
        root.add_widget(self.pill_bar)

        # Scrollable content area
        self.page_scroll = MDScrollView()
        self.page_box = MDBoxLayout(
            orientation='vertical', spacing=dp(12),
            padding=dp(14), size_hint_y=None
        )
        self.page_box.bind(minimum_height=self.page_box.setter('height'))
        self.page_scroll.add_widget(self.page_box)
        root.add_widget(self.page_scroll)

        # Navigation buttons
        nav = MDBoxLayout(
            size_hint_y=None, height=dp(60),
            padding=[dp(14), dp(8)], spacing=dp(10),
            md_bg_color=get_color('surface_variant', 0.15)
        )
        self.back_btn = MDFlatButton(
            text='← BACK',
            theme_text_color='Custom',
            text_color=get_color(self.STEP_COLORS[0]),
            on_release=lambda x: self._prev_step()
        )
        self.next_btn = MDRaisedButton(
            text='NEXT →',
            md_bg_color=get_color(self.STEP_COLORS[0]),
            on_release=lambda x: self._next_step()
        )
        self.submit_btn = MDRaisedButton(
            text='CREATE ACCOUNT',
            md_bg_color=get_color('success'),
            on_release=lambda x: self._submit(),
            opacity=0, disabled=True
        )
        nav.add_widget(self.back_btn)
        nav.add_widget(Widget())
        nav.add_widget(self.next_btn)
        nav.add_widget(self.submit_btn)
        root.add_widget(nav)

        self.add_widget(root)
        self._render_step(0)

    def _render_step(self, idx):
        self._current_step = idx
        color = self.STEP_COLORS[idx]
        self.page_box.clear_widgets()

        self.progress.value = (idx + 1) * 25
        self.progress.color = get_color(color)
        self.toolbar.md_bg_color = get_color(color)
        self.back_btn.text_color = get_color(color)
        self.next_btn.md_bg_color = get_color(color)

        # Update pills
        for i, pill in enumerate(self._pills):
            active = i == idx
            c = self.STEP_COLORS[i]
            pill.md_bg_color = get_color(c) if active else get_color('surface_variant', 0.5)
            pill.elevation = 2 if active else 0
            if i < len(self._pill_icons):
                self._pill_icons[i].text_color = (1, 1, 1, 1) if active else get_color('outline')

        is_last = idx == len(self.STEPS) - 1
        self.next_btn.opacity = 0 if is_last else 1
        self.next_btn.disabled = is_last
        self.submit_btn.opacity = 1 if is_last else 0
        self.submit_btn.disabled = not is_last

        builders = [self._step_personal, self._step_contact,
                    self._step_employment, self._step_documents]
        builders[idx]()

    def _field(self, key, hint, **kwargs):
        color = self.STEP_COLORS[self._current_step]
        if key not in self.fields:
            self.fields[key] = MDTextField(
                hint_text=hint,
                mode='rectangle',
                line_color_focus=get_color(color),
                size_hint_y=None, height=dp(56),
                **kwargs
            )
        return self.fields[key]

    def _section(self, text, icon=None):
        color = self.STEP_COLORS[self._current_step]
        row = MDCard(
            orientation='horizontal',
            size_hint_y=None, height=dp(44),
            radius=[dp(8)], padding=[dp(12), 0], spacing=dp(8),
            md_bg_color=get_color(f'{color}_container', 0.4), elevation=0
        )
        if icon:
            row.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom',
                text_color=get_color(color), size_hint_x=None, width=dp(28)
            ))
        row.add_widget(MDLabel(
            text=text, font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color(color),
            valign='middle'
        ))
        return row

    def _step_personal(self):
        pb = self.page_box
        pb.add_widget(self._section('Login Credentials', 'lock-outline'))
        pb.add_widget(self._field('username', 'Username *'))
        pb.add_widget(self._field('password', 'Password *', password=True))
        pb.add_widget(self._field('confirm_password', 'Confirm Password *', password=True))
        pb.add_widget(self._section('Personal Details', 'account'))
        pb.add_widget(self._field('first_name', 'First Name *'))
        pb.add_widget(self._field('last_name', 'Last Name *'))
        pb.add_widget(self._field('other_names', 'Other Names'))
        pb.add_widget(self._field('id_number', 'National ID Number *'))
        pb.add_widget(self._field('date_of_birth', 'Date of Birth (YYYY-MM-DD)'))
        pb.add_widget(self._field('gender', 'Gender (Male/Female/Other)'))
        pb.add_widget(self._field('marital_status', 'Marital Status'))

    def _step_contact(self):
        pb = self.page_box
        pb.add_widget(self._section('Contact Information', 'phone'))
        pb.add_widget(self._field('phone', 'Phone Number * (e.g. 0712345678)', input_filter='int'))
        pb.add_widget(self._field('phone2', 'Alternative Phone'))
        pb.add_widget(self._field('email', 'Email Address'))
        pb.add_widget(self._field('address', 'Physical Address'))
        pb.add_widget(self._section('Location', 'map-marker'))
        pb.add_widget(self._field('city', 'City/Town'))
        pb.add_widget(self._field('county', 'County'))
        pb.add_widget(self._field('constituency', 'Constituency'))
        pb.add_widget(self._field('ward', 'Ward'))

    def _step_employment(self):
        pb = self.page_box
        pb.add_widget(self._section('Employment Details', 'briefcase'))
        pb.add_widget(self._field('occupation', 'Occupation'))
        pb.add_widget(self._field('employer', 'Employer Name'))
        pb.add_widget(self._field('department', 'Department'))
        pb.add_widget(self._field('job_title', 'Job Title'))
        pb.add_widget(self._field('employment_type', 'Employment Type (permanent/contract/self-employed)'))
        pb.add_widget(self._field('monthly_income', 'Monthly Income (KSh)', input_filter='float'))
        pb.add_widget(self._field('employment_start_date', 'Employment Start Date (YYYY-MM-DD)'))

    def _step_documents(self):
        pb = self.page_box
        color = self.STEP_COLORS[3]
        pb.add_widget(self._section('Documents', 'file-document'))

        for label, icon in [
            ('National ID - Front', 'card-account-details'),
            ('National ID - Back', 'card-account-details-outline'),
            ('Passport Photo', 'camera-account'),
            ('Signature', 'draw-pen'),
        ]:
            card = MDCard(
                orientation='horizontal',
                size_hint_y=None, height=dp(72),
                radius=[dp(10)], padding=dp(12), spacing=dp(12),
                md_bg_color=get_color('quaternary_container', 0.2), elevation=0
            )
            ic = MDCard(
                size_hint=(None, None), size=(dp(44), dp(44)),
                radius=[dp(22)], md_bg_color=get_color('quaternary_container', 0.6)
            )
            ic.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom',
                text_color=get_color(color), halign='center'
            ))
            card.add_widget(ic)
            info = MDBoxLayout(orientation='vertical')
            info.add_widget(MDLabel(text=label, font_style='Subtitle2', bold=True,
                valign='middle'
            ))
            info.add_widget(MDLabel(
                text='Tap camera to upload or take photo',
                font_style='Caption', theme_text_color='Secondary',
                valign='middle'
            ))
            card.add_widget(info)
            card.add_widget(MDIconButton(
                icon='camera',
                theme_text_color='Custom',
                text_color=get_color(color),
                size_hint_x=None, width=dp(40)
            ))
            pb.add_widget(card)

        pb.add_widget(MDBoxLayout(size_hint_y=None, height=dp(10)))
        # Always create a fresh switch - reusing a widget that already has a parent crashes Kivy
        prev_active = getattr(self, 'consent_checkbox', None)
        prev_state = prev_active.active if prev_active is not None else False
        self.consent_checkbox = MDSwitch(
            size_hint=(None, None), size=(dp(56), dp(28))
        )
        # Defer active state to avoid KivyMD 1.2.0 ids.thumb crash
        if prev_state:
            Clock.schedule_once(lambda dt, sw=self.consent_checkbox: setattr(sw, 'active', True), 0)
        consent_card = MDCard(
            orientation='horizontal',
            size_hint_y=None, height=dp(60),
            radius=[dp(10)], padding=dp(14), spacing=dp(12),
            md_bg_color=get_color('success', 0.06), elevation=0
        )
        consent_card.add_widget(self.consent_checkbox)
        consent_card.add_widget(MDLabel(
            text='I agree to the [b]Terms & Conditions[/b] and consent to data processing',
            markup=True, font_style='Body2',
            theme_text_color='Custom', text_color=get_color('on_surface'),
            valign='middle'
        ))
        pb.add_widget(consent_card)

    # Navigation
    def _jump_to_step(self, idx):
        if idx < self._current_step:
            self._render_step(idx)

    def _next_step(self):
        if not self._validate_current():
            return
        if self._current_step < len(self.STEPS) - 1:
            self._render_step(self._current_step + 1)

    def _prev_step(self):
        if self._current_step > 0:
            self._render_step(self._current_step - 1)
        else:
            self._go_back_or_login()

    def _go_back_or_login(self):
        if self.app:
            self.app.root_sm.current = 'login'

    def _validate_current(self):
        step = self.STEPS[self._current_step]
        if step == 'personal':
            for key in ['username', 'password', 'confirm_password', 'first_name', 'last_name', 'id_number']:
                f = self.fields.get(key)
                if not f or not f.text.strip():
                    self.show_error(f'{key.replace("_", " ").title()} is required')
                    return False
            if self.fields['password'].text != self.fields['confirm_password'].text:
                self.show_error('Passwords do not match')
                return False
            if len(self.fields['password'].text) < 6:
                self.show_error('Password must be at least 6 characters')
                return False
        elif step == 'contact':
            f = self.fields.get('phone')
            if not f or not f.text.strip():
                self.show_error('Phone number is required')
                return False
        return True

    def _submit(self):
        if not getattr(self, 'consent_checkbox', None) or not self.consent_checkbox.active:
            self.show_error('Please accept the terms and conditions')
            return
        data = {k: v.text.strip() for k, v in self.fields.items() if v.text.strip()}
        if 'monthly_income' in data:
            try:
                data['monthly_income'] = float(data['monthly_income'])
            except ValueError:
                data['monthly_income'] = 0.0
        data['consent_signed'] = 1
        self.submit_btn.disabled = True
        self.submit_btn.text = 'Creating...'
        self.loading_overlay(True)
        threading.Thread(target=self._submit_thread, args=(data,), daemon=True).start()

    def _submit_thread(self, data):
        try:
            username = data.pop('username')
            password = data.pop('password')
            data.pop('confirm_password', None)
            # All three (member + account + user) in one atomic transaction
            self.app.member_service.self_register(data, username=username, password=password)
            Clock.schedule_once(lambda dt: self._submit_success(username, password), 0)
        except ValueError as e:
            msg = str(e)
            Clock.schedule_once(lambda dt, m=msg: self._submit_error(m), 0)
        except Exception as e:
            msg = f'Registration failed: {str(e)[:100]}'
            Logger.error(f'Registration error: {e}')
            import traceback; traceback.print_exc()
            Clock.schedule_once(lambda dt, m=msg: self._submit_error(m), 0)

    def _submit_success(self, username, password):
        self.loading_overlay(False)
        self.submit_btn.disabled = False
        self.submit_btn.text = 'CREATE ACCOUNT'
        self.show_success('Account created successfully! Signing you in...')
        Clock.schedule_once(lambda dt: self._auto_login(username, password), 0.2)

    def _auto_login(self, username, password):
        self.app.root_sm.current = 'login'
        login_screen = self.app.root_sm.get_screen('login')
        login_screen.username_field.text = username
        login_screen.password_field.text = password
        login_screen.do_login()

    def _submit_error(self, message):
        self.loading_overlay(False)
        self.submit_btn.disabled = False
        self.submit_btn.text = 'CREATE ACCOUNT'
        self.show_error(message)


# ============================================================================
# DASHBOARD SCREEN
# ============================================================================

class DashboardScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'dashboard'
        self._build()

    # ── Role-based action definitions ──────────────────────────
    # (icon, label, color_key, screen, allowed_roles or None=all)
    # Format: (icon, label, color, screen, allowed_roles, navigate_kwargs)
    ALL_ACTIONS = [
        ('cash-plus',            'Deposit',      'success',    'deposit',         None,  {}),
        ('cash-minus',           'Withdraw',     'error',      'withdrawal',      None,  {}),
        ('alpha-m-circle',       'M-Pesa',       'success',    'mobile_money',    None,  {'provider': 'mpesa'}),
        ('alpha-a-circle',       'Airtel Money', 'error',      'mobile_money',    None,  {'provider': 'airtel'}),
        ('bank-transfer',        'Transfer',     'secondary',  'transfer',        None,  {}),
        ('account-group',        'Members',      'tertiary',   'member_list',
            ['super_admin','admin','manager','branch_manager',
             'loans_officer','senior_loans_officer','teller','senior_teller',
             'field_officer','credit_analyst','auditor'], {}),
        ('cash-multiple',        'Loans',        'quaternary', 'loan_application',None,  {}),
        ('cash-check',           'Repay',        'quinary',    'repayment',       None,  {}),
        ('trending-up',          'Invest',       'info',       'investments',     None,  {}),
        ('chart-bar',            'Reports',      'senary',     'reports',
            ['super_admin','admin','manager','branch_manager',
             'loans_officer','senior_loans_officer','accountant','auditor'], {}),
        ('robot-outline',        'AI Assist',    'septenary',  'ai_assistant',    None,  {}),
        ('calculator',           'Calculator',   'octonary',   'loan_calculator', None,  {}),
        ('file-document',        'Statement',    'primary',    'statement',
            ['super_admin','admin','manager','branch_manager',
             'teller','senior_teller','member'], {}),
        ('bell-outline',         'Alerts',       'warning',    'notifications',   None,  {}),
    ]

    def _build(self):
        from kivy.uix.floatlayout import FloatLayout
        from kivymd.uix.button import MDFloatingActionButton

        float_root = FloatLayout()
        root = MDBoxLayout(orientation='vertical', size_hint=(1, 1))

        toolbar = MDTopAppBar(
            title='HELA SMART SACCO',
            elevation=2,
            md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['menu', lambda x: self.app.open_drawer()]],
            right_action_items=[
                ['bell-outline',          lambda x: self.app.navigate_to('notifications')],
                ['account-circle-outline',lambda x: self._show_profile()],
            ]
        )
        root.add_widget(toolbar)

        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation='vertical', spacing=dp(14),
            padding=[dp(14), dp(14), dp(14), dp(80)],
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))

        # ── Welcome banner ─────────────────────────────────────────────
        welcome_card = MDCard(
            orientation='vertical',
            padding=[dp(20), dp(14), dp(20), dp(14)],
            spacing=dp(2),
            radius=[dp(16)], md_bg_color=get_color('primary'),
            size_hint_y=None, height=dp(84), elevation=3
        )
        self.welcome_label = MDLabel(
            text='Good Morning!', font_style='H5', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(36), valign='middle'
        )
        self.date_label = MDLabel(
            text=datetime.datetime.now().strftime('%A, %d %B %Y'),
            font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.75),
            size_hint_y=None, height=dp(20), valign='middle'
        )
        welcome_card.add_widget(self.welcome_label)
        welcome_card.add_widget(self.date_label)
        content.add_widget(welcome_card)

        # ── Stat cards — grid height=280 gives 135dp/card, content=109dp ✓
        self._stats_grid = MDGridLayout(
            cols=2, spacing=dp(10),
            size_hint_y=None, height=dp(280)
        )
        self.stat_cards = {}
        self._build_stat_cards('super_admin')   # populated properly in on_enter
        content.add_widget(self._stats_grid)

        # ── Quick Actions ──────────────────────────────────────────────
        content.add_widget(MDLabel(
            text='QUICK ACTIONS', font_style='Caption',
            theme_text_color='Secondary', bold=True,
            size_hint_y=None, height=dp(22), valign='middle'
        ))
        self._actions_grid = MDGridLayout(
            cols=4, spacing=dp(8),
            size_hint_y=None, height=dp(190)
        )
        self._build_action_buttons('super_admin')  # rebuilt in on_enter
        content.add_widget(self._actions_grid)

        # ── Recent Activity ────────────────────────────────────────────
        content.add_widget(MDLabel(
            text='RECENT ACTIVITY', font_style='Caption',
            theme_text_color='Secondary', bold=True,
            size_hint_y=None, height=dp(26), valign='middle'
        ))
        self.activity_list = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.activity_list.bind(minimum_height=self.activity_list.setter('height'))
        content.add_widget(self.activity_list)

        # ── AI Insights ────────────────────────────────────────────────
        self.insights_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6), size_hint_y=None
        )
        self.insights_box.bind(minimum_height=self.insights_box.setter('height'))
        content.add_widget(self.insights_box)

        scroll.add_widget(content)
        root.add_widget(scroll)
        float_root.add_widget(root)

        fab = MDFloatingActionButton(
            icon='plus', md_bg_color=get_color('secondary'),
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            pos_hint={'right': 0.95, 'y': 0.03},
            on_release=lambda x: self.app.navigate_to('deposit')
        )
        float_root.add_widget(fab)
        self.add_widget(float_root)

    def _build_stat_cards(self, role):
        """Build stat cards appropriate for the user's role."""
        self._stats_grid.clear_widgets()
        self.stat_cards.clear()
        if role == 'member':
            defs = [
                ('bank',                  '—', 'My Balance',    'primary',   None),
                ('cash-multiple',         '—', 'My Loans',      'secondary', None),
                ('calendar-clock',        '—', 'Next Payment',  'warning',   None),
                ('trending-up',           '—', 'Investments',   'info',      None),
            ]
        else:
            defs = [
                ('account-group',         '—', 'Members',       'primary',   5.2),
                ('cash-multiple',         '—', 'Active Loans',  'secondary', -2.1),
                ('bank',                  '—', 'Total Savings', 'tertiary',  8.5),
                ('alert-circle-outline',  '—', 'PAR Ratio',     'error',     -15.3),
            ]
        keys = ['s0', 's1', 's2', 's3']
        for key, (icon, val, lbl, color, trend) in zip(keys, defs):
            card = StatCard(icon, val, lbl, color, trend=trend)
            self.stat_cards[key] = card
            self._stats_grid.add_widget(card)

    def _build_action_buttons(self, role):
        """Build quick action buttons filtered for this role."""
        self._actions_grid.clear_widgets()
        visible = [
            (icon, label, color, screen, kwargs)
            for icon, label, color, screen, allowed, kwargs in self.ALL_ACTIONS
            if allowed is None or role in allowed
        ]
        # Trim to max 8 for 2-row 4-col grid
        visible = visible[:8]
        rows = (len(visible) + 3) // 4
        self._actions_grid.height = dp(rows * 90 + (rows - 1) * 8)
        for icon, label, color, screen, nav_kwargs in visible:
            btn = MDCard(
                orientation='vertical',
                padding=[dp(4), dp(6)], spacing=dp(2),
                radius=[dp(12)],
                md_bg_color=get_color(f'{color}_container', 0.3),
                ripple_behavior=True,
                on_release=lambda x, s=screen, kw=nav_kwargs: self._navigate_action(s, **kw)
            )
            from kivy.uix.relativelayout import RelativeLayout
            ic_rl = RelativeLayout(size_hint_y=None, height=dp(38))
            ic_rl.add_widget(MDIcon(
                icon=icon,
                theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle',
                font_size=sp(24),
                size_hint=(None, None), size=(dp(28), dp(28)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            ))
            btn.add_widget(ic_rl)
            btn.add_widget(MDLabel(
                text=label, halign='center', valign='middle',
                font_style='Caption',
                theme_text_color='Custom', text_color=get_color('on_surface'),
                size_hint_y=None, height=dp(16)
            ))
            self._actions_grid.add_widget(btn)

    def _navigate_action(self, screen, provider=None, **kwargs):
        """Navigate to a screen, pre-setting provider on mobile_money screen."""
        if screen == 'mobile_money' and provider:
            mm = self.app.screens_cache.get('mobile_money')
            if mm:
                mm._provider_key = provider
                mm.member_id = None   # clear so no stale member shown
        self.app.navigate_to(screen, **kwargs)
    def on_enter(self):
        role = (self.app.current_user_role or 'member')
        self._build_stat_cards(role)
        self._build_action_buttons(role)
        self._update_welcome()
        threading.Thread(target=self._load_data, daemon=True).start()

    def _update_welcome(self):
        hour = datetime.datetime.now().hour
        greeting = ('Good Morning' if hour < 12 else
                    'Good Afternoon' if hour < 17 else 'Good Evening')
        name = ''
        if self.app and hasattr(self.app, 'current_user_name') and self.app.current_user_name:
            name = ', ' + self.app.current_user_name.split()[0]
        self.welcome_label.text = f"{greeting}{name}!"

    def _load_data(self):
        role = (self.app.current_user_role or 'member')
        try:
            if role == 'member':
                # Load this member's personal data only
                user_row = self.app.db.fetch_one(
                    "SELECT member_id FROM users WHERE id=?",
                    (self.app.current_user_id,)
                )
                mid = (user_row or {}).get('member_id')
                if mid:
                    bal = self.app.db.fetch_one(
                        "SELECT COALESCE(SUM(balance_minor),0) as b FROM accounts "
                        "WHERE member_id=? AND account_type='savings' AND status='active'", (mid,))
                    loans = self.app.db.fetch_one(
                        "SELECT COUNT(*) as c FROM loans WHERE member_id=? "
                        "AND status IN ('active','disbursed')", (mid,))
                    try:
                        nxt = self.app.db.fetch_one(
                            "SELECT MIN(due_date) as d FROM loan_schedule ls "
                            "JOIN loans l ON ls.loan_id=l.id "
                            "WHERE l.member_id=? AND ls.status='pending' AND ls.due_date>=date('now')",
                            (mid,))
                    except Exception:
                        nxt = None
                    invs = self.app.db.fetch_one(
                        "SELECT COALESCE(SUM(principal_minor),0) as t FROM investments "
                        "WHERE member_id=? AND status='active'", (mid,))
                    txns = self.app.db.fetch_all(
                        "SELECT t.*, a.account_no FROM transactions t "
                        "JOIN accounts a ON t.account_id=a.id "
                        "WHERE a.member_id=? ORDER BY t.posted_date DESC LIMIT 8", (mid,))
                    stats = {
                        's0': f"KSh {((bal or {}).get('b') or 0)/100:,.2f}",
                        's1': str((loans or {}).get('c', 0)),
                        's2': (nxt or {}).get('d') or 'None due',
                        's3': f"KSh {((invs or {}).get('t') or 0)/100:,.0f}",
                    }
                else:
                    txns, stats = [], {'s0':'—','s1':'—','s2':'—','s3':'—'}
                Clock.schedule_once(
                    lambda dt: self._update_ui(stats, txns, []), 0)
            else:
                members  = self.app.db.fetch_one("SELECT COUNT(*) as c FROM members WHERE is_active=1")
                loans    = self.app.db.fetch_one(
                    "SELECT COUNT(*) as c FROM loans WHERE status IN ('active','disbursed')")
                savings  = self.app.db.fetch_one(
                    "SELECT COALESCE(SUM(balance_minor),0) as total FROM accounts "
                    "WHERE account_type='savings' AND status='active'")
                par_data = self.app.loan_service.calculate_par()
                txns     = self.app.db.fetch_all(
                    "SELECT t.*, a.account_no, m.first_name, m.last_name "
                    "FROM transactions t "
                    "JOIN accounts a ON t.account_id=a.id "
                    "JOIN members m ON a.member_id=m.id "
                    "ORDER BY t.posted_date DESC LIMIT 8")
                insights = self.app.ai_service.generate_financial_insights()
                stats = {
                    's0': f"{(members or {}).get('c', 0):,}",
                    's1': f"{(loans or {}).get('c', 0):,}",
                    's2': f"KSh {((savings or {}).get('total') or 0)/100:,.0f}",
                    's3': f"{(par_data or {}).get('par_ratio', 0) or 0:.1f}%",
                }
                Clock.schedule_once(
                    lambda dt: self._update_ui(stats, txns, insights), 0)
        except Exception as e:
            Logger.error(f'Dashboard load error: {e}')
            import traceback; traceback.print_exc()
            Clock.schedule_once(
                lambda dt: self._update_ui(
                    {'s0': '—', 's1': '—', 's2': '—', 's3': '—'}, [], []), 0)

    def _update_ui(self, stats, transactions, insights):
        try:
            for key, val in stats.items():
                if key in self.stat_cards:
                    self.stat_cards[key].set_value(val)
        except Exception as e:
            Logger.warning(f'Stats update error: {e}')

        self.activity_list.clear_widgets()
        if not transactions:
            self.activity_list.add_widget(MDLabel(
                text='No recent transactions', theme_text_color='Secondary',
                halign='center', size_hint_y=None, height=dp(40), valign='middle'
            ))
        else:
            for tx in transactions:
                self.activity_list.add_widget(self._activity_item(tx))

        self.insights_box.clear_widgets()
        insight_list = insights or []
        if not insight_list:
            from kivy.uix.relativelayout import RelativeLayout
            placeholder = MDCard(
                orientation='horizontal',
                size_hint_y=None, height=dp(56),
                radius=[dp(12)], padding=[dp(14), 0], spacing=dp(10),
                md_bg_color=get_color('primary_container', 0.25), elevation=0
            )
            ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(28), dp(28)))
            ic_rl.add_widget(MDIcon(
                icon='robot-outline',
                theme_text_color='Custom', text_color=get_color('primary'),
                halign='center', valign='middle', font_size=sp(20),
                size_hint=(None, None), size=(dp(24), dp(24)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            ))
            placeholder.add_widget(ic_rl)
            placeholder.add_widget(MDLabel(
                text='AI insights will appear as your SACCO grows.',
                font_style='Caption',
                theme_text_color='Custom', text_color=get_color('outline'),
                valign='middle'
            ))
            self.insights_box.add_widget(placeholder)
        else:
            for insight in insight_list[:3]:
                self.insights_box.add_widget(self._insight_card(insight))

    def _insight_card(self, insight):
        from kivy.uix.relativelayout import RelativeLayout
        from kivy.graphics import Color as _C, RoundedRectangle as _RR
        itype = insight.get('type', 'info')
        card = MDCard(
            orientation='horizontal',
            padding=[dp(12), dp(8)], spacing=dp(10),
            radius=[dp(10)],
            md_bg_color=get_color(f'{itype}_container', 0.25),
            size_hint_y=None, height=dp(60), elevation=0
        )
        ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(34), dp(34)))
        ic_rl.add_widget(MDIcon(
            icon=insight.get('icon', 'lightbulb-outline'),
            theme_text_color='Custom', text_color=get_color(itype),
            halign='center', valign='middle', font_size=sp(20),
            size_hint=(None, None), size=(dp(24), dp(24)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        card.add_widget(ic_rl)
        card.add_widget(MDLabel(
            text=insight.get('message', ''),
            font_style='Body2',
            theme_text_color='Custom', text_color=get_color('on_surface'),
            valign='middle'
        ))
        return card

    def _activity_item(self, tx):
        ttype = tx.get('transaction_type', '')
        colors = {'deposit': 'success', 'withdrawal': 'error',
                  'transfer': 'secondary', 'loan_repayment': 'quinary'}
        color = colors.get(ttype, 'primary')
        icon_map = {'deposit': 'arrow-down-circle', 'withdrawal': 'arrow-up-circle',
                    'transfer': 'bank-transfer', 'loan_repayment': 'cash-check'}
        icon = icon_map.get(ttype, 'cash')

        card = MDCard(
            orientation='horizontal', padding=[dp(12), dp(8)], spacing=dp(10),
            radius=[dp(10)],
            md_bg_color=get_color('surface_variant', 0.15),
            size_hint_y=None, height=dp(62), elevation=0
        )
        from kivy.uix.relativelayout import RelativeLayout
        from kivy.graphics import Color as _C, RoundedRectangle as _RR
        ic_rl = RelativeLayout(size_hint=(None, None), size=(dp(38), dp(38)))
        with ic_rl.canvas.before:
            _C(*get_color(f'{color}_container', 0.5))
            _RR(pos=(0, 0), size=(dp(38), dp(38)), radius=[dp(19)])
        ic_rl.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom', text_color=get_color(color),
            halign='center', valign='middle', font_size=sp(18),
            size_hint=(None, None), size=(dp(22), dp(22)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        card.add_widget(ic_rl)

        info = MDBoxLayout(orientation='vertical', spacing=dp(2))
        name_str = f"{tx.get('first_name','')} {tx.get('last_name','')}".strip() or ttype.replace('_',' ').title()
        info.add_widget(MDLabel(
            text=name_str, font_style='Subtitle2',
            size_hint_y=None, height=dp(22), valign='middle'
        ))
        acc_str = f"{ttype.replace('_',' ').title()}  •  {tx.get('account_no','')}"
        info.add_widget(MDLabel(
            text=acc_str, font_style='Caption', theme_text_color='Secondary',
            size_hint_y=None, height=dp(18), valign='middle'
        ))
        card.add_widget(info)

        amt = (tx.get('amount_minor', 0) or 0) / 100
        is_credit = ttype == 'deposit'
        card.add_widget(MDLabel(
            text=f"{'+'if is_credit else '-'}KSh {abs(amt):,.2f}",
            font_style='Subtitle2', bold=True, halign='right',
            theme_text_color='Custom', text_color=get_color(color),
            valign='middle'
        ))
        return card

    def _show_profile(self):
        role = self.app.current_user_role or 'member'
        if role == 'member':
            self.app.navigate_to('member_settings')
        else:
            self.app.navigate_to('settings')


# ============================================================================
# MEMBER LIST SCREEN
# ============================================================================

class MemberListScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'member_list'
        self._members = []
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        MDTopAppBar(
            title='Members',
            md_bg_color=get_color('secondary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[['account-plus', lambda x: self.app.navigate_to('register')]],
        )
        self.toolbar = MDTopAppBar(
            title='Members',
            md_bg_color=get_color('secondary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[['account-plus', lambda x: self.app.root_sm.current == 'register']],
        )
        root.add_widget(self.toolbar)

        search_row = MDBoxLayout(
            size_hint_y=None, height=dp(60), padding=[dp(10), dp(8)], spacing=dp(8)
        )
        self.search_field = MDTextField(
            hint_text='Search by name, phone or ID…',
            mode='round', line_color_focus=get_color('secondary')
        )
        self.search_field.bind(text=self._on_search)
        search_row.add_widget(self.search_field)
        root.add_widget(search_row)

        # Stats row
        self.stats_row = MDBoxLayout(
            size_hint_y=None, height=dp(44),
            padding=[dp(10), dp(4)], spacing=dp(10)
        )
        self.count_lbl = MDLabel(
            text='Loading members…', font_style='Caption',
            theme_text_color='Secondary',
            valign='middle'
        )
        self.stats_row.add_widget(self.count_lbl)
        root.add_widget(self.stats_row)

        scroll = MDScrollView()
        self.list_box = MDBoxLayout(
            orientation='vertical', spacing=dp(6),
            padding=[dp(10), dp(4)], size_hint_y=None
        )
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_enter(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self, query=''):
        try:
            if query:
                members = self.app.db.fetch_all(
                    "SELECT * FROM members WHERE is_active=1 AND "
                    "(first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? OR "
                    "member_no LIKE ? OR id_number LIKE ?) "
                    "ORDER BY first_name LIMIT 100",
                    (f'%{query}%',) * 5
                )
            else:
                members = self.app.db.fetch_all(
                    "SELECT * FROM members WHERE is_active=1 ORDER BY first_name LIMIT 100"
                )
            Clock.schedule_once(lambda dt: self._render(members), 0)
        except Exception as e:
            Logger.error(f'MemberList: {e}')

    def _render(self, members):
        self._members = members
        self.count_lbl.text = f'{len(members)} members found'
        self.list_box.clear_widgets()

        if not members:
            self.list_box.add_widget(MDLabel(
                text='No members found', halign='center',
                theme_text_color='Secondary', size_hint_y=None, height=dp(80),
                valign='middle'
            ))
            return

        kyc_colors = {
            'verified': 'success', 'complete': 'primary',
            'incomplete': 'warning', 'pending': 'error'
        }
        for m in members:
            kyc = m.get('kyc_status', 'pending') or 'pending'
            kc = kyc_colors.get(kyc, 'outline')
            fn = m.get('first_name', ' ')
            ln = m.get('last_name', ' ')

            card = MDCard(
                orientation='horizontal', size_hint_y=None, height=dp(68),
                padding=dp(12), radius=[dp(10)],
                md_bg_color=(1, 1, 1, 1), elevation=1, ripple_behavior=True,
                on_release=lambda x, mid=m['id']: self.app.navigate_to('member_profile', member_id=mid)
            )
            # Avatar
            av = MDCard(
                size_hint=(None, None), size=(dp(44), dp(44)),
                radius=[dp(22)],
                md_bg_color=get_color(f'{kc}_container', 0.5)
            )
            av.add_widget(MDLabel(
                text=(fn[0] + ln[0]).upper() if fn and ln else '?',
                halign='center', font_style='H6',
                theme_text_color='Custom', text_color=get_color(kc),
                valign='middle'
            ))
            card.add_widget(av)
            info = MDBoxLayout(orientation='vertical', padding=[dp(10), 0])
            info.add_widget(MDLabel(
                text=f'{fn} {ln}', font_style='Subtitle2', bold=True,
                size_hint_y=None, height=dp(24),
                valign='middle'
            ))
            info.add_widget(MDLabel(
                text=f"{m.get('member_no','—')}  •  {m.get('phone','—')}",
                font_style='Caption', theme_text_color='Secondary',
                size_hint_y=None, height=dp(18),
                valign='middle'
            ))
            card.add_widget(info)
            card.add_widget(MDLabel(
                text=kyc.title(), halign='right', font_style='Caption',
                theme_text_color='Custom', text_color=get_color(kc),
                valign='middle'
            ))
            self.list_box.add_widget(card)

    def _on_search(self, inst, text):
        threading.Thread(target=self._load, args=(text.strip(),), daemon=True).start()


# ============================================================================
# MEMBER PROFILE SCREEN
# ============================================================================

class MemberProfileScreen(BaseScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'member_profile'
        self.member_id = None
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')
        self.toolbar = MDTopAppBar(
            title='Member Profile',
            md_bg_color=get_color('primary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['account-edit', lambda x: self.app.navigate_to('member_edit', member_id=self.member_id)],
            ]
        )
        root.add_widget(self.toolbar)

        self.scroll = MDScrollView()
        self.body = MDBoxLayout(
            orientation='vertical', spacing=dp(12),
            padding=dp(14), size_hint_y=None
        )
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll.add_widget(self.body)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_enter(self):
        if self.member_id:
            threading.Thread(target=self._load, daemon=True).start()

    def _profile_action(self, action, member_id):
        """Handle quick action button taps on member profile."""
        if action in ('mpesa_mm', 'airtel_mm'):
            provider = 'mpesa' if action == 'mpesa_mm' else 'airtel'
            mm = self.app.screens_cache.get('mobile_money')
            if mm:
                mm._provider_key = provider
                mm.member_id     = member_id
            self.app.navigate_to('mobile_money', member_id=member_id)
        else:
            self.app.navigate_to(action, member_id=member_id)

    def _load(self):
        try:
            member = self.app.db.fetch_one(
                "SELECT * FROM members WHERE id=?", (self.member_id,)
            )
            accounts = self.app.db.fetch_all(
                "SELECT * FROM accounts WHERE member_id=? AND status='active'",
                (self.member_id,)
            )
            loans = self.app.db.fetch_all(
                "SELECT * FROM loans WHERE member_id=? AND status IN ('active','disbursed','overdue')",
                (self.member_id,)
            )
            Clock.schedule_once(lambda dt: self._render(member, accounts, loans), 0)
        except Exception as e:
            Logger.error(f'MemberProfile: {e}')

    def _render(self, member, accounts, loans):
        self.body.clear_widgets()
        if not member:
            self.body.add_widget(MDLabel(text='Member not found', halign='center',
                valign='middle'
            ))
            return

        fn = member.get('first_name', '')
        ln = member.get('last_name', '')
        kyc = member.get('kyc_status', 'pending') or 'pending'
        kyc_colors = {'verified': 'success', 'complete': 'primary', 'incomplete': 'warning', 'pending': 'error'}
        kc = kyc_colors.get(kyc, 'outline')

        self.toolbar.title = f"{fn} {ln}"

        # Hero card
        hero = MDCard(
            orientation='horizontal', padding=[dp(16), dp(12)],
            spacing=dp(12),
            radius=[dp(16)], md_bg_color=get_color('primary'),
            size_hint_y=None, height=dp(100), elevation=4
        )
        # Avatar with properly centered initials
        av_anchor = AnchorLayout(
            anchor_x='center', anchor_y='center',
            size_hint=(None, None), size=(dp(64), dp(64))
        )
        av_bg = MDCard(
            size_hint=(None, None), size=(dp(60), dp(60)),
            radius=[dp(30)], md_bg_color=(1, 1, 1, 0.22), elevation=0
        )
        av_inner = AnchorLayout(anchor_x='center', anchor_y='center')
        initials = ((fn[0] if fn else '') + (ln[0] if ln else '')).upper() or '?'
        av_inner.add_widget(MDLabel(
            text=initials, halign='center', valign='middle',
            font_style='H5', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint=(None, None), size=(dp(60), dp(60))
        ))
        av_bg.add_widget(av_inner)
        av_anchor.add_widget(av_bg)
        hero.add_widget(av_anchor)

        info = MDBoxLayout(
            orientation='vertical', spacing=dp(2),
            padding=[dp(4), dp(8)]
        )
        info.add_widget(MDLabel(
            text=f'{fn} {ln}', font_style='H6', bold=True,
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(30), valign='middle'
        ))
        info.add_widget(MDLabel(
            text=member.get('member_no', '—'), font_style='Subtitle2',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.8),
            size_hint_y=None, height=dp(22), valign='middle'
        ))
        info.add_widget(MDLabel(
            text=f"KYC: {kyc.title()}", font_style='Caption',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.7),
            size_hint_y=None, height=dp(18), valign='middle'
        ))
        hero.add_widget(info)
        self.body.add_widget(hero)

        # Quick action buttons — icon cards matching dashboard style
        action_row = MDBoxLayout(size_hint_y=None, height=dp(72), spacing=dp(6))
        for text, color, screen, icon in [
            ('Deposit',  'success',    'deposit',         'cash-plus'),
            ('Withdraw', 'error',      'withdrawal',      'cash-minus'),
            ('M-Pesa',   'success',    'mpesa_mm',        'alpha-m-circle'),
            ('Airtel',   'error',      'airtel_mm',       'alpha-a-circle'),
            ('Loan',     'quaternary', 'loan_application','cash-multiple'),
        ]:
            btn = MDCard(
                orientation='vertical', radius=[dp(12)],
                md_bg_color=get_color(f'{color}_container', 0.25),
                ripple_behavior=True, elevation=0,
                size_hint_x=1, size_hint_y=None, height=dp(72),
                padding=[dp(4), dp(6)],
                on_release=lambda x, s=screen, mid=member['id']: self._profile_action(s, mid)
            )
            from kivy.uix.relativelayout import RelativeLayout as _RL
            ic_rl = _RL(size_hint_y=None, height=dp(32))
            ic_rl.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom', text_color=get_color(color),
                halign='center', valign='middle', font_size=sp(22),
                size_hint=(None, None), size=(dp(28), dp(28)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            ))
            btn.add_widget(ic_rl)
            btn.add_widget(MDLabel(
                text=text, halign='center', font_style='Caption',
                theme_text_color='Custom', text_color=get_color('on_surface'),
                size_hint_y=None, height=dp(16)
            ))
            action_row.add_widget(btn)
        self.body.add_widget(action_row)

        # Contact action buttons
        phone = (member.get('phone') or '').strip()
        email = (member.get('email') or '').strip()
        if phone or email:
            contact_card = MDCard(
                orientation='vertical', padding=[dp(14), dp(10)], spacing=dp(8),
                radius=[dp(12)], md_bg_color=get_color('surface_variant', 0.15), elevation=0,
                size_hint_y=None, height=dp(120 if (phone and email) else 70)
            )
            contact_card.add_widget(MDLabel(
                text='CONTACT', font_style='Caption', bold=True,
                theme_text_color='Secondary', size_hint_y=None, height=dp(18), valign='middle'
            ))
            if phone:
                phone_row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
                phone_row.add_widget(MDIcon(icon='phone', theme_text_color='Custom',
                                             text_color=get_color('success'),
                                             size_hint=(None,None), size=(dp(24),dp(40)), valign='middle'))
                phone_row.add_widget(MDLabel(text=phone, font_style='Body2',
                                              valign='middle', size_hint_x=1))
                for icon_name, color, action in [
                    ('phone', 'success', 'call'),
                    ('message-text', 'primary', 'sms'),
                    ('whatsapp', 'success', 'whatsapp'),
                ]:
                    btn = MDCard(size_hint=(None,None), size=(dp(36),dp(36)),
                                  radius=[dp(18)], ripple_behavior=True,
                                  md_bg_color=get_color(f'{color}_container', 0.5),
                                  on_release=lambda x, p=phone, a=action: self._contact_action(p, a))
                    btn.add_widget(MDIcon(icon=icon_name, theme_text_color='Custom',
                                          text_color=get_color(color), halign='center',
                                          valign='middle', font_size=sp(16)))
                    phone_row.add_widget(btn)
                contact_card.add_widget(phone_row)
            if email:
                email_row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
                email_row.add_widget(MDIcon(icon='email', theme_text_color='Custom',
                                             text_color=get_color('quaternary'),
                                             size_hint=(None,None), size=(dp(24),dp(40)), valign='middle'))
                email_row.add_widget(MDLabel(text=email, font_style='Body2',
                                              valign='middle', size_hint_x=1))
                btn_email = MDCard(size_hint=(None,None), size=(dp(36),dp(36)),
                                    radius=[dp(18)], ripple_behavior=True,
                                    md_bg_color=get_color('quaternary_container', 0.5),
                                    on_release=lambda x, e=email: self._contact_action(e, 'email'))
                btn_email.add_widget(MDIcon(icon='email-outline', theme_text_color='Custom',
                                             text_color=get_color('quaternary'), halign='center',
                                             valign='middle', font_size=sp(16)))
                email_row.add_widget(btn_email)
                contact_card.add_widget(email_row)
            self.body.add_widget(contact_card)

        # Info sections
        for title, icon, fields in [
            ('Personal', 'account', [
                ('Phone', member.get('phone','')),
                ('Email', member.get('email','')),
                ('ID Number', member.get('id_number','')),
                ('Date of Birth', member.get('date_of_birth','')),
                ('Gender', member.get('gender','')),
                ('Joined', member.get('membership_date','')),
            ]),
            ('Employment', 'briefcase', [
                ('Occupation', member.get('occupation','')),
                ('Employer', member.get('employer','')),
                ('Income', f"KSh {(member.get('monthly_income') or 0):,.2f}/mo"),
            ]),
        ]:
            self.body.add_widget(self._info_card(title, icon, fields))

        # Accounts section
        self.body.add_widget(MDLabel(
            text='ACCOUNTS', font_style='Caption',
            theme_text_color='Secondary', bold=True,
            size_hint_y=None, height=dp(28),
            valign='middle'
        ))
        for acc in accounts:
            self.body.add_widget(self._account_card(acc))

        # Loans section
        if loans:
            self.body.add_widget(MDLabel(
                text='ACTIVE LOANS', font_style='Caption',
                theme_text_color='Secondary', bold=True,
                size_hint_y=None, height=dp(28),
                valign='middle'
            ))
            for loan in loans:
                self.body.add_widget(self._loan_card(loan))

    def _contact_action(self, value, action):
        """Launch phone call, SMS, WhatsApp, or email via Android intent."""
        try:
            import subprocess, platform
            sys_name = platform.system()
            if action == 'call':
                try:
                    from android import mActivity
                    from jnius import autoclass
                    Intent   = autoclass('android.content.Intent')
                    Uri      = autoclass('android.net.Uri')
                    intent   = Intent(Intent.ACTION_DIAL)
                    intent.setData(Uri.parse(f'tel:{value}'))
                    mActivity.startActivity(intent)
                except Exception:
                    self.show_info(f'Call: {value}')
            elif action == 'sms':
                try:
                    from android import mActivity
                    from jnius import autoclass
                    Intent = autoclass('android.content.Intent')
                    Uri    = autoclass('android.net.Uri')
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(f'sms:{value}'))
                    mActivity.startActivity(intent)
                except Exception:
                    self.show_info(f'SMS: {value}')
            elif action == 'whatsapp':
                try:
                    from android import mActivity
                    from jnius import autoclass
                    Intent = autoclass('android.content.Intent')
                    Uri    = autoclass('android.net.Uri')
                    phone  = value.lstrip('0')
                    if phone and not phone.startswith('+'):
                        phone = '254' + phone  # Kenya country code
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(f'https://wa.me/{phone}'))
                    intent.setPackage('com.whatsapp')
                    mActivity.startActivity(intent)
                except Exception:
                    self.show_info(f'WhatsApp: {value}')
            elif action == 'email':
                try:
                    from android import mActivity
                    from jnius import autoclass
                    Intent = autoclass('android.content.Intent')
                    Uri    = autoclass('android.net.Uri')
                    intent = Intent(Intent.ACTION_SENDTO)
                    intent.setData(Uri.parse(f'mailto:{value}'))
                    mActivity.startActivity(intent)
                except Exception:
                    self.show_info(f'Email: {value}')
        except Exception as e:
            self.show_error(str(e))

    def _info_card(self, title, icon, fields):
        card = MDCard(
            orientation='vertical', padding=dp(14), spacing=dp(2),
            radius=[dp(12)],
            md_bg_color=get_color('surface_variant', 0.15),
            size_hint_y=None, elevation=0
        )
        # Section header row
        hrow = MDBoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        ic_a = AnchorLayout(anchor_x='center', anchor_y='center',
                            size_hint=(None, None), size=(dp(24), dp(34)))
        ic_a.add_widget(MDIcon(
            icon=icon, theme_text_color='Custom',
            text_color=get_color('primary'),
            halign='center', valign='middle',
            font_size=sp(18), size_hint=(None, None), size=(dp(20), dp(20))
        ))
        hrow.add_widget(ic_a)
        hrow.add_widget(MDLabel(
            text=title, font_style='Subtitle1', bold=True,
            theme_text_color='Custom', text_color=get_color('primary'),
            size_hint_y=None, height=dp(34), valign='middle'
        ))
        card.add_widget(hrow)
        for label, value in fields:
            if value:
                row = MDBoxLayout(size_hint_y=None, height=dp(30))
                row.add_widget(MDLabel(
                    text=label, theme_text_color='Secondary',
                    font_style='Caption', size_hint_x=0.38,
                    size_hint_y=None, height=dp(30), valign='middle'
                ))
                row.add_widget(MDLabel(
                    text=str(value), font_style='Body2', size_hint_x=0.62,
                    size_hint_y=None, height=dp(30), valign='middle'
                ))
                card.add_widget(row)
        card.height = dp(14 + 34 + 2 + sum(30 for _, v in fields if v) + 14)
        return card

    def _account_card(self, acc):
        atype = acc.get('account_type', '').replace('_', ' ').title()
        bal = (acc.get('balance_minor') or 0) / 100
        colors = {'savings': 'primary', 'loan': 'error', 'share_capital': 'success'}
        color = colors.get(acc.get('account_type'), 'primary')
        card = MDCard(
            orientation='horizontal', padding=dp(14),
            radius=[dp(10)], size_hint_y=None, height=dp(72),
            md_bg_color=get_color(f'{color}_container', 0.2), elevation=0
        )
        ic = MDCard(
            size_hint=(None, None), size=(dp(44), dp(44)),
            radius=[dp(22)], md_bg_color=get_color(f'{color}_container', 0.6),
            elevation=0
        )
        ic_a = AnchorLayout(anchor_x='center', anchor_y='center')
        ic_a.add_widget(MDIcon(
            icon='bank', theme_text_color='Custom',
            text_color=get_color(color),
            halign='center', valign='middle',
            font_size=sp(20), size_hint=(None, None), size=(dp(24), dp(24))
        ))
        ic.add_widget(ic_a)
        card.add_widget(ic)
        info = MDBoxLayout(orientation='vertical', padding=[dp(10), 0])
        info.add_widget(MDLabel(text=atype, font_style='Subtitle2', bold=True,
            valign='middle'
        ))
        info.add_widget(MDLabel(
            text=acc.get('account_no', ''), font_style='Caption',
            theme_text_color='Secondary',
            valign='middle'
        ))
        card.add_widget(info)
        card.add_widget(MDLabel(
            text=f"KSh {bal:,.2f}", font_style='H6',
            theme_text_color='Custom', text_color=get_color(color), halign='right',
            valign='middle'
        ))
        return card

    def _loan_card(self, loan):
        outstanding = (loan.get('outstanding_principal_minor') or 0) / 100
        status = loan.get('status', '')
        sc = 'error' if status == 'overdue' else 'quaternary'
        card = MDCard(
            orientation='horizontal', padding=dp(14),
            radius=[dp(10)], size_hint_y=None, height=dp(72),
            md_bg_color=get_color(f'{sc}_container', 0.2), elevation=0
        )
        ic = MDCard(
            size_hint=(None, None), size=(dp(40), dp(40)),
            radius=[dp(20)], md_bg_color=get_color(f'{sc}_container', 0.6)
        )
        ic.add_widget(MDIcon(
            icon='cash-multiple', theme_text_color='Custom',
            text_color=get_color(sc), halign='center'
        ))
        card.add_widget(ic)
        info = MDBoxLayout(orientation='vertical', padding=[dp(10), 0])
        info.add_widget(MDLabel(text=loan.get('loan_no', '—'), font_style='Subtitle2', bold=True,
            valign='middle'
        ))
        info.add_widget(MDLabel(
            text=f"Status: {status.title()}", font_style='Caption',
            theme_text_color='Custom', text_color=get_color(sc),
            valign='middle'
        ))
        card.add_widget(info)
        card.add_widget(MDLabel(
            text=f"KSh {outstanding:,.2f}", font_style='H6',
            theme_text_color='Custom', text_color=get_color(sc), halign='right',
            valign='middle'
        ))
        return card


# ============================================================================
# NAVIGATION DRAWER
# ============================================================================

class NavigationDrawerContent(MDBoxLayout):

    # Define which screens each role can access
    # Format: (icon, label, screen, color, min_roles)
    # min_roles=None means all roles; otherwise list of allowed roles
    ALL_ITEMS = [
        ('view-dashboard',   'Dashboard',     'dashboard',         'primary',    None),
        ('account-group',    'Members',        'member_list',       'secondary',  ['super_admin','admin','manager','branch_manager','loans_officer','senior_loans_officer','teller','senior_teller','field_officer','credit_analyst','auditor']),
        ('cash-plus',        'Deposit',        'deposit',           'success',    None),
        ('cash-minus',       'Withdraw',       'withdrawal',        'error',      None),
        ('cellphone-arrow-down', 'Mobile Money',  'mobile_money',      'success',    None),
        ('bank-transfer',    'Transfer',       'transfer',          'tertiary',   None),
        ('cash-multiple',    'Loans',          'loan_application',  'quaternary', None),
        ('cash-check',       'Repayment',      'repayment',         'quinary',    None),
        ('trending-up',      'Investments',    'investments',       'info',       None),
        ('chart-bar',        'Reports',        'reports',           'senary',     ['super_admin','admin','manager','branch_manager','loans_officer','senior_loans_officer','accountant','auditor','credit_analyst']),
        ('robot-outline',    'AI Assistant',   'ai_assistant',      'septenary',  None),
        ('check-decagram',   'KYC Approval',   'kyc_approval',      'warning',    ['super_admin','admin','manager','branch_manager','loans_officer','senior_loans_officer','teller','senior_teller']),
        ('bell-outline',     'Notifications',  'notifications',     'info',       None),
        ('source-branch',    'Branches',       'branch_management', 'octonary',   ['super_admin','admin','manager']),
        ('shield-search',    'Audit Log',      'audit_log',         'error',      ['super_admin','admin','manager','auditor']),
        ('cog-outline',      'Settings',       'settings',          'outline',    ['super_admin','admin','manager']),
        ('cog-outline',      'Settings',       'member_settings',   'outline',    ['member']),
    ]

    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        self.orientation = 'vertical'
        self._menu_box = None

        # Header
        header = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(160),
            padding=[dp(16), dp(20), dp(16), dp(12)],
            md_bg_color=get_color('primary')
        )
        from kivy.uix.anchorlayout import AnchorLayout
        av_anchor = AnchorLayout(anchor_x='center', anchor_y='center',
                                 size_hint=(1, None), height=dp(64))
        avatar = MDCard(
            size_hint=(None, None), size=(dp(60), dp(60)),
            radius=[dp(30)], md_bg_color=(1, 1, 1, 0.2),
        )
        av_inner = AnchorLayout(anchor_x='center', anchor_y='center')
        av_inner.add_widget(MDLabel(
            text='A', halign='center', valign='middle',
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            font_style='H5',
            size_hint=(None, None), size=(dp(60), dp(60))
        ))
        avatar.add_widget(av_inner)
        av_anchor.add_widget(avatar)
        self.name_label = MDLabel(
            text='Administrator', halign='center',
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            font_style='Subtitle1', bold=True,
            size_hint_y=None, height=dp(26), valign='middle'
        )
        self.role_label = MDLabel(
            text='Super Admin', halign='center',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.7),
            font_style='Caption',
            size_hint_y=None, height=dp(20), valign='middle'
        )
        header.add_widget(av_anchor)
        header.add_widget(self.name_label)
        header.add_widget(self.role_label)
        self.add_widget(header)

        scroll = MDScrollView()
        self._menu_box = MDBoxLayout(
            orientation='vertical', spacing=dp(2),
            padding=[dp(8), dp(8)], size_hint_y=None
        )
        self._menu_box.bind(minimum_height=self._menu_box.setter('height'))
        self._build_menu('super_admin')  # default, rebuilt on open
        scroll.add_widget(self._menu_box)
        self.add_widget(scroll)

    def _build_menu(self, role):
        role = (role or 'member').lower().strip()   # normalise — DB may store 'Member'
        self._menu_box.clear_widgets()
        for icon, text, screen, color, allowed_roles in self.ALL_ITEMS:
            if allowed_roles is not None and role not in allowed_roles:
                continue
            item = MDCard(
                orientation='horizontal',
                padding=[dp(12), 0], spacing=dp(12),
                size_hint_y=None, height=dp(46),
                radius=[dp(8)], ripple_behavior=True,
                md_bg_color=(0, 0, 0, 0),
                on_release=lambda x, s=screen: self.navigate(s)
            )
            from kivy.uix.anchorlayout import AnchorLayout
            ic_a = AnchorLayout(anchor_x='center', anchor_y='center',
                                size_hint=(None, None), size=(dp(28), dp(46)))
            ic_a.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom',
                text_color=get_color(color),
                halign='center', valign='middle',
                font_size=sp(20),
                size_hint=(None, None), size=(dp(22), dp(22))
            ))
            item.add_widget(ic_a)
            item.add_widget(MDLabel(
                text=text, font_style='Body1', valign='middle'
            ))
            self._menu_box.add_widget(item)

        self._menu_box.add_widget(MDBoxLayout(
            size_hint_y=None, height=dp(1),
            md_bg_color=get_color('outline_variant')
        ))
        logout_item = MDCard(
            orientation='horizontal',
            padding=[dp(12), 0], spacing=dp(12),
            size_hint_y=None, height=dp(46),
            radius=[dp(8)], ripple_behavior=True,
            md_bg_color=(0, 0, 0, 0),
            on_release=self.logout
        )
        from kivy.uix.anchorlayout import AnchorLayout as _AL
        lo_a = _AL(anchor_x='center', anchor_y='center',
                   size_hint=(None, None), size=(dp(28), dp(46)))
        lo_a.add_widget(MDIcon(
            icon='logout', theme_text_color='Custom',
            text_color=get_color('error'),
            halign='center', valign='middle',
            font_size=sp(20), size_hint=(None, None), size=(dp(22), dp(22))
        ))
        logout_item.add_widget(lo_a)
        logout_item.add_widget(MDLabel(
            text='Logout', font_style='Body1',
            theme_text_color='Custom', text_color=get_color('error'),
            valign='middle'
        ))
        self._menu_box.add_widget(logout_item)

    def rebuild_for_role(self, role):
        self._build_menu((role or 'member').lower().strip())

    def navigate(self, screen):
        self.app_ref.close_drawer()
        self.app_ref.navigate_to(screen)

    def logout(self, *args):
        self.app_ref.close_drawer()
        self.app_ref.logout()
