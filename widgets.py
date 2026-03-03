# widgets.py - Reusable UI widget components
import sys as _sys, os as _os; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget

from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFillRoundFlatButton, MDFloatingActionButtonSpeedDial, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDIcon, MDLabel  # MDIcon added (was missing)

from constants import RAINBOW_COLORS, get_color


class AnimatedCard(MDCard):
    """Card with hover and click animations"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.elevation_normal = kwargs.get('elevation', 2)
        self.elevation_hover = self.elevation_normal + 4

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            Animation(elevation=self.elevation_hover, duration=0.1).start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        Animation(elevation=self.elevation_normal, duration=0.2).start(self)
        return super().on_touch_up(touch)


class ColorfulButton(MDFillRoundFlatButton):
    """Button with vibrant colors and animations"""

    def __init__(self, color_key='primary', **kwargs):
        super().__init__(**kwargs)
        self.color_key = color_key
        self.md_bg_color = get_color(color_key)
        self.theme_text_color = "Custom"
        on_color_key = f'on_{color_key}'
        self.text_color = (get_color(on_color_key)
                           if on_color_key in RAINBOW_COLORS else (1, 1, 1, 1))

    def on_press(self):
        Animation(md_bg_color=get_color(self.color_key, 0.7), duration=0.1).start(self)
        super().on_press()

    def on_release(self):
        Animation(md_bg_color=get_color(self.color_key), duration=0.2).start(self)
        super().on_release()


class StatCard(MDCard):
    """
    Stat card that fits inside a 2-col MDGridLayout without overflow.

    Budget: grid height=280, spacing=10 → 135dp/card
    Padding [12,10,12,10] → 20dp vertical → 115dp available
    icon(36)+val(30)+lbl(16)+trend(18)+spacing(3×3=9) = 109dp < 115dp ✓
    """

    def __init__(self, icon, value, label, color_key='primary', trend=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation  = 'vertical'
        self.padding      = [dp(12), dp(10), dp(12), dp(10)]
        self.spacing      = dp(3)
        self.radius       = [dp(16)]
        self.md_bg_color  = get_color('card_bg')
        self.elevation    = 2
        self._value_label = None

        from kivy.uix.relativelayout import RelativeLayout

        # ── Icon badge via RelativeLayout (pos_hint works reliably) ──
        icon_row = MDBoxLayout(orientation='horizontal',
                               size_hint_y=None, height=dp(36))
        badge = RelativeLayout(size_hint=(None, None), size=(dp(36), dp(36)))
        with badge.canvas.before:
            Color(*get_color(f'{color_key}_container', 0.5))
            RoundedRectangle(pos=(0, 0), size=(dp(36), dp(36)), radius=[dp(10)])
        badge.add_widget(MDIcon(
            icon=icon,
            theme_text_color='Custom',
            text_color=get_color(color_key),
            halign='center', valign='middle',
            font_size=sp(20),
            size_hint=(None, None), size=(dp(24), dp(24)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))
        icon_row.add_widget(badge)
        self.add_widget(icon_row)

        # ── Value ─────────────────────────────────────────────────────
        self._value_label = MDLabel(
            text=str(value),
            font_style='H6', bold=True,
            theme_text_color='Custom',
            text_color=get_color('on_background'),
            size_hint_y=None, height=dp(30),
            valign='middle'
        )
        self.add_widget(self._value_label)

        # ── Category label ────────────────────────────────────────────
        self.add_widget(MDLabel(
            text=label,
            font_style='Caption',
            theme_text_color='Secondary',
            size_hint_y=None, height=dp(16),
            valign='middle'
        ))

        # ── Trend row ─────────────────────────────────────────────────
        if trend is not None:
            t_color = 'success' if trend >= 0 else 'error'
            t_icon  = 'trending-up' if trend >= 0 else 'trending-down'
            trend_row = MDBoxLayout(size_hint_y=None, height=dp(18),
                                    spacing=dp(3), orientation='horizontal')
            trend_row.add_widget(MDIcon(
                icon=t_icon,
                theme_text_color='Custom', text_color=get_color(t_color),
                halign='left', valign='middle',
                font_size=sp(13),
                size_hint=(None, None), size=(dp(16), dp(18))
            ))
            trend_row.add_widget(MDLabel(
                text=f"{abs(trend):.1f}%",
                theme_text_color='Custom', text_color=get_color(t_color),
                font_style='Caption',
                size_hint_y=None, height=dp(18), valign='middle'
            ))
            self.add_widget(trend_row)

    def set_value(self, text):
        if self._value_label:
            self._value_label.text = str(text)


class ChartWidget(Widget):
    """Simple canvas-based bar/pie chart widget"""

    def __init__(self, data, chart_type='bar', **kwargs):
        super().__init__(**kwargs)
        self.data = data
        self.chart_type = chart_type

    def on_size(self, *args):
        self.draw()

    def draw(self):
        self.canvas.clear()
        if not self.data:
            return
        with self.canvas:
            Color(*get_color('surface_variant', 0.3))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
            if self.chart_type == 'bar':
                self._draw_bar_chart()

    def _draw_bar_chart(self):
        if not self.data:
            return
        max_value = max(d['value'] for d in self.data)
        if max_value == 0:
            return
        bar_width = (self.width - dp(40)) / len(self.data)
        colors_list = ['primary', 'secondary', 'tertiary', 'quaternary', 'quinary']
        for i, item in enumerate(self.data):
            bar_height = (item['value'] / max_value) * (self.height - dp(60))
            x = self.x + dp(20) + i * bar_width
            y = self.y + dp(40)
            with self.canvas:
                Color(*get_color(colors_list[i % len(colors_list)]))
                RoundedRectangle(
                    pos=(x + dp(4), y),
                    size=(bar_width - dp(8), bar_height),
                    radius=[dp(4), dp(4), 0, 0]
                )


class FloatingActionMenu(MDFloatingActionButtonSpeedDial):
    """Custom floating action menu with vibrant colors"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = {
            'Deposit': 'cash-plus',
            'Withdraw': 'cash-minus',
            'Transfer': 'bank-transfer',
            'New Member': 'account-plus',
        }
        self.root_button_anim = True
        self.bg_color_stack_button = get_color('primary')
        self.bg_color_root_button = get_color('secondary')
        self.color_icon_stack_button = get_color('on_primary')
        self.color_icon_root_button = get_color('on_secondary')
