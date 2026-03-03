# screens_ai.py — HELA SMART SACCO AI Assistant
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import datetime
import threading

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

from constants import get_color
from screens import BaseScreen


class AIAssistantScreen(BaseScreen):
    MEMBER_PROMPTS = [
        ('My Balance',       'What is my account balance?'),
        ('My Loans',         'Show my active loans'),
        ('Next Payment',     'When is my next loan payment?'),
        ('Am I Eligible?',   'Am I eligible for a loan?'),
        ('My Investments',   'Show my investments'),
        ('Returns',          'What are my expected investment returns?'),
        ('Calc EMI',         'Calculate EMI for KSh 100000 at 18% for 24 months'),
        ('Deposit',          'How do I deposit money?'),
        ('Loan Types',       'What loan products do you offer?'),
        ('Office Hours',     'What are your office hours?'),
    ]
    STAFF_PROMPTS = [
        ('Portfolio',       'Show loan portfolio summary'),
        ('PAR Ratio',       'What is the current PAR ratio?'),
        ('Members',         'How many active members do we have?'),
        ('Savings Total',   'What is the total savings balance?'),
        ('Income',          'Show income summary for this month'),
        ('Top Borrowers',   'Who are our top 5 borrowers?'),
        ('New Members',     'Show new members this month'),
        ('Overdue',         'Show overdue loans summary'),
        ('My Balance',      'What is my account balance?'),
        ('Loan Types',      'What loan products do you offer?'),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'ai_assistant'
        self._messages = []
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation='vertical')

        toolbar = MDTopAppBar(
            title='HELA AI Assistant',
            md_bg_color=get_color('septenary'),
            specific_text_color=(1, 1, 1, 1),
            left_action_items=[['arrow-left', lambda x: self.app.go_back()]],
            right_action_items=[
                ['delete-sweep', lambda x: self._clear_chat()],
                ['help-circle-outline', lambda x: self._send('help')],
            ]
        )
        root.add_widget(toolbar)

        self.welcome_card = MDCard(
            orientation='vertical', size_hint_y=None, height=dp(96),
            padding=[dp(16), dp(10)], spacing=dp(4),
            md_bg_color=get_color('septenary', 0.08), radius=[0], elevation=0
        )
        icon_row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        av = RelativeLayout(size_hint=(None, None), size=(dp(40), dp(40)))
        with av.canvas.before:
            Color(*get_color('septenary'))
            RoundedRectangle(pos=(0, 0), size=(dp(40), dp(40)), radius=[dp(20)])
        av.add_widget(MDIcon(
            icon='robot-excited', theme_text_color='Custom',
            text_color=(1, 1, 1, 1), halign='center', valign='middle',
            font_size=sp(20), size_hint=(None, None), size=(dp(24), dp(24)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        icon_row.add_widget(av)
        icon_row.add_widget(MDLabel(
            text='HELA AI', font_style='H6', bold=True,
            theme_text_color='Custom', text_color=get_color('septenary'),
            valign='middle'
        ))
        self.welcome_card.add_widget(icon_row)
        self.welcome_card.add_widget(MDLabel(
            text='Ask about your balance, loans, investments, or any SACCO info.',
            font_style='Body2', theme_text_color='Secondary',
            size_hint_y=None, height=dp(34), valign='middle'
        ))
        root.add_widget(self.welcome_card)

        self._chips_scroll = MDScrollView(
            size_hint_y=None, height=dp(46),
            do_scroll_x=True, do_scroll_y=False
        )
        self._chips_row = MDBoxLayout(
            size_hint_x=None, height=dp(46),
            spacing=dp(7), padding=[dp(10), dp(6)]
        )
        self._chips_row.bind(minimum_width=self._chips_row.setter('width'))
        self._chips_scroll.add_widget(self._chips_row)
        root.add_widget(self._chips_scroll)

        self.chat_scroll = MDScrollView()
        self.chat_box = MDBoxLayout(
            orientation='vertical', spacing=dp(8),
            padding=[dp(12), dp(6)], size_hint_y=None
        )
        self.chat_box.bind(minimum_height=self.chat_box.setter('height'))
        self.chat_scroll.add_widget(self.chat_box)
        root.add_widget(self.chat_scroll)

        self.typing_card = MDCard(
            orientation='horizontal', size_hint_y=None, height=dp(0),
            padding=[dp(10), 0], radius=[dp(14), dp(14), dp(14), dp(4)],
            md_bg_color=get_color('surface_variant', 0.4),
            elevation=0, size_hint_x=0.4, opacity=0
        )
        self.typing_card.add_widget(MDLabel(
            text='  typing...', font_style='Caption',
            theme_text_color='Custom', text_color=get_color('septenary'),
            valign='middle'
        ))
        self.chat_box.add_widget(self.typing_card)

        input_bar = MDBoxLayout(
            size_hint_y=None, height=dp(62),
            padding=[dp(10), dp(8)], spacing=dp(8),
            md_bg_color=get_color('surface_variant', 0.15)
        )
        self.input_field = MDTextField(
            hint_text='Ask me anything...',
            mode='round',
            line_color_focus=get_color('septenary'),
            multiline=False,
            on_text_validate=lambda x: self._send_input()
        )
        send_btn = MDCard(
            size_hint=(None, None), size=(dp(44), dp(44)),
            radius=[dp(22)], md_bg_color=get_color('septenary'),
            ripple_behavior=True,
            on_release=lambda x: self._send_input()
        )
        ic_rl = RelativeLayout()
        ic_rl.add_widget(MDIcon(
            icon='send', theme_text_color='Custom', text_color=(1, 1, 1, 1),
            halign='center', valign='middle', font_size=sp(18),
            size_hint=(None, None), size=(dp(22), dp(22)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        send_btn.add_widget(ic_rl)
        input_bar.add_widget(self.input_field)
        input_bar.add_widget(send_btn)
        root.add_widget(input_bar)
        self.add_widget(root)

    def on_enter(self):
        self._rebuild_chips()
        if not self._messages:
            Clock.schedule_once(lambda dt: self._show_greeting(), 0.3)

    def _rebuild_chips(self):
        self._chips_row.clear_widgets()
        role = self.app.current_user_role or 'member'
        prompts = self.STAFF_PROMPTS if role != 'member' else self.MEMBER_PROMPTS
        for label, prompt in prompts:
            chip = MDCard(
                size_hint=(None, None), size=(dp(112), dp(30)),
                padding=[dp(8), 0], radius=[dp(15)],
                md_bg_color=get_color('septenary_container', 0.3),
                ripple_behavior=True,
                on_release=lambda x, p=prompt: self._send(p)
            )
            chip.add_widget(MDLabel(
                text=label, font_style='Caption',
                theme_text_color='Custom', text_color=get_color('septenary'),
                halign='center', valign='middle'
            ))
            self._chips_row.add_widget(chip)

    def _show_greeting(self):
        hour = datetime.datetime.now().hour
        greet = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'
        name = getattr(self.app, 'current_user_name', '') or ''
        name_part = (', ' + name.split()[0]) if name else ''
        role = self.app.current_user_role or 'member'
        if role == 'member':
            body = ('I can help with your balance, loans, investments,\n'
                    'EMI calculations, and SACCO information.\n\n'
                    'Tap a quick prompt above or type your question!')
        else:
            body = ('Staff dashboard: portfolio, PAR, member stats,\n'
                    'savings totals, income, overdue analysis, and more.\n\n'
                    'Type naturally — I understand plain English!')
        self._add_bot_message(greet + name_part + '! I\'m HELA AI.\n\n' + body)

    def _send_input(self):
        text = self.input_field.text.strip()
        if text:
            self.input_field.text = ''
            self._send(text)

    def _send(self, text):
        if self.welcome_card.height > 0:
            Animation(height=0, opacity=0, duration=0.2).start(self.welcome_card)
        self._add_user_message(text)
        self._show_typing(True)
        context = {
            'user_id': getattr(self.app, 'current_user_id', None),
            'role': getattr(self.app, 'current_user_role', 'member'),
        }
        threading.Thread(target=self._process, args=(text, context), daemon=True).start()

    def _process(self, text, context):
        try:
            response = self.app.ai_service.process_query(text, context)
            Clock.schedule_once(lambda dt: self._on_response(response), 0)
        except Exception as e:
            Logger.error('AI screen: %s', e)
            Clock.schedule_once(lambda dt: self._on_response(
                {'message': 'Sorry, something went wrong. Please try again.'}), 0)

    def _on_response(self, response):
        self._show_typing(False)
        self._add_bot_message(response.get('message', ''))
        data = response.get('data')
        if data and isinstance(data, (list, dict)):
            self._add_data_card(data)
        self._add_feedback_row()
        self._scroll_bottom()

    def _add_user_message(self, text):
        bubble = MDBoxLayout(orientation='horizontal', size_hint_y=None, spacing=dp(8))
        bubble.add_widget(Widget())
        card = MDCard(
            orientation='vertical', size_hint_x=0.78, size_hint_y=None,
            padding=[dp(12), dp(8)], radius=[dp(16), dp(16), dp(4), dp(16)],
            md_bg_color=get_color('primary'), elevation=2
        )
        lbl = MDLabel(
            text=text, font_style='Body2',
            theme_text_color='Custom', text_color=(1, 1, 1, 1),
            size_hint_y=None, valign='middle'
        )
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(4)))
        card.add_widget(lbl)
        card.add_widget(MDLabel(
            text=datetime.datetime.now().strftime('%H:%M'),
            font_style='Caption', halign='right',
            theme_text_color='Custom', text_color=(1, 1, 1, 0.6),
            size_hint_y=None, height=dp(16), valign='middle'
        ))
        card.bind(minimum_height=card.setter('height'))
        bubble.add_widget(card)
        bubble.height = dp(50)
        card.bind(height=lambda i, v: setattr(bubble, 'height', v + dp(12)))
        self.chat_box.add_widget(bubble)
        self._messages.append({'role': 'user', 'text': text})
        self._scroll_bottom()

    def _add_bot_message(self, text):
        bubble = MDBoxLayout(orientation='horizontal', size_hint_y=None, spacing=dp(8))
        av = RelativeLayout(size_hint=(None, None), size=(dp(30), dp(30)))
        with av.canvas.before:
            Color(*get_color('septenary'))
            RoundedRectangle(pos=(0, 0), size=(dp(30), dp(30)), radius=[dp(15)])
        av.add_widget(MDIcon(
            icon='robot', theme_text_color='Custom', text_color=(1, 1, 1, 1),
            halign='center', valign='middle', font_size=sp(14),
            size_hint=(None, None), size=(dp(18), dp(18)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        bubble.add_widget(av)

        card = MDCard(
            orientation='vertical', size_hint_x=0.78, size_hint_y=None,
            padding=[dp(12), dp(8)], radius=[dp(16), dp(16), dp(16), dp(4)],
            md_bg_color=get_color('surface_variant', 0.45), elevation=1
        )
        # Process **bold** markdown
        parts = text.split('**')
        display = ''
        for i, part in enumerate(parts):
            display += ('[b]' + part + '[/b]') if i % 2 == 1 else part

        lbl = MDLabel(
            text=display, markup=True, font_style='Body2',
            size_hint_y=None, valign='middle'
        )
        lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1] + dp(8)))
        card.add_widget(lbl)
        card.bind(minimum_height=card.setter('height'))
        bubble.add_widget(card)
        bubble.add_widget(Widget())
        bubble.height = dp(50)
        card.bind(height=lambda i, v: setattr(bubble, 'height', v + dp(12)))
        self.chat_box.add_widget(bubble)
        self._messages.append({'role': 'bot', 'text': text})

    def _add_feedback_row(self):
        row = MDBoxLayout(
            orientation='horizontal', size_hint_y=None, height=dp(26),
            spacing=dp(6), padding=[dp(42), 0, 0, 0]
        )
        for icon, tip in [('thumb-up-outline', 'Helpful'), ('thumb-down-outline', 'Not helpful')]:
            btn = MDCard(
                size_hint=(None, None), size=(dp(26), dp(20)),
                radius=[dp(10)],
                md_bg_color=get_color('surface_variant', 0.3),
                ripple_behavior=True,
                on_release=lambda x, t=tip, r=row: self._on_rated(t, r)
            )
            btn.add_widget(MDIcon(
                icon=icon, theme_text_color='Custom',
                text_color=get_color('outline'),
                halign='center', valign='middle', font_size=sp(11)
            ))
            row.add_widget(btn)
        row.add_widget(MDLabel(
            text='Helpful?', font_style='Caption',
            theme_text_color='Hint', valign='middle'
        ))
        self.chat_box.add_widget(row)

    def _on_rated(self, tip, row):
        try:
            self.chat_box.remove_widget(row)
        except Exception:
            pass
        thanks = MDLabel(
            text=('Thanks!' if 'Helpful' in tip else "Got it, I'll improve!"),
            font_style='Caption', theme_text_color='Hint',
            size_hint_y=None, height=dp(18), valign='middle',
            padding=[dp(42), 0, 0, 0]
        )
        self.chat_box.add_widget(thanks)

    def _add_data_card(self, data):
        if isinstance(data, dict):
            data = [data]
        if not data:
            return
        card = MDCard(
            orientation='vertical', size_hint_y=None,
            padding=[dp(10), dp(6)], radius=[dp(10)],
            md_bg_color=get_color('primary_container', 0.18),
            elevation=1, size_hint_x=0.86
        )
        card.add_widget(MDLabel(
            text='Data', font_style='Caption', bold=True,
            theme_text_color='Custom', text_color=get_color('primary'),
            size_hint_y=None, height=dp(20), valign='middle'
        ))
        for item in data[:5]:
            if isinstance(item, dict):
                for k, v in list(item.items())[:3]:
                    r = MDBoxLayout(size_hint_y=None, height=dp(24))
                    r.add_widget(MDLabel(
                        text=str(k).replace('_', ' ').title(),
                        font_style='Caption', theme_text_color='Secondary',
                        size_hint_x=0.5, valign='middle'
                    ))
                    r.add_widget(MDLabel(
                        text=str(v), font_style='Caption', bold=True,
                        size_hint_x=0.5, valign='middle'
                    ))
                    card.add_widget(r)
        card.bind(minimum_height=card.setter('height'))
        wrap = MDBoxLayout(size_hint_y=None)
        wrap.add_widget(card)
        wrap.add_widget(Widget())
        wrap.bind(minimum_height=wrap.setter('height'))
        card.bind(height=lambda i, v: setattr(wrap, 'height', v + dp(6)))
        self.chat_box.add_widget(wrap)

    def _show_typing(self, show):
        if show:
            Animation(height=dp(38), opacity=1, duration=0.15).start(self.typing_card)
        else:
            Animation(height=0, opacity=0, duration=0.1).start(self.typing_card)

    def _scroll_bottom(self):
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.1)

    def _clear_chat(self):
        self.chat_box.clear_widgets()
        self.chat_box.add_widget(self.typing_card)
        self._messages.clear()
        Animation(height=dp(96), opacity=1, duration=0.2).start(self.welcome_card)
