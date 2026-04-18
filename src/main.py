"""
StockAnalyzer IA v2.1 - Optimise mobile (Poco F7 / 1080x2400 AMOLED)
9 graphiques + Score IA (11 indicateurs) + Prediction future + Notifications
Scenarios haut/bas, Pic/Creux, Toggle notifs, Scalping 5min
"""

import os
os.environ["KIVY_LOG_LEVEL"] = "warning"

import re
import logging
logging.getLogger('yfinance').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import platform

from kivymd.app import MDApp

import threading
from datetime import datetime

# === Interface KV - Optimisee mobile ===

KV = '''
#:import NoTransition kivy.uix.screenmanager.NoTransition
#:import AsyncImage kivy.uix.image.AsyncImage

MDScreenManager:
    transition: NoTransition()

    MDScreen:
        name: "main"

        MDBoxLayout:
            orientation: "vertical"
            md_bg_color: 0, 0, 0, 1

            # Header
            MDBoxLayout:
                size_hint_y: None
                height: dp(48)
                padding: dp(8), dp(6)
                spacing: dp(2)
                md_bg_color: 0, 0, 0, 1

                MDLabel:
                    text: "StockAnalyzer IA"
                    font_style: "H6"
                    bold: True
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1

                Widget:
                    size_hint_x: None
                    width: dp(1)

                MDIconButton:
                    id: notif_icon
                    icon: "bell"
                    theme_text_color: "Custom"
                    text_color: 0, 0.82, 0.42, 1
                    on_release: app.quick_toggle_notif()
                    size_hint: None, None
                    size: dp(38), dp(38)
                    pos_hint: {"center_y": 0.5}

                MDIconButton:
                    icon: "refresh"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    on_release: app.refresh_all()
                    size_hint: None, None
                    size: dp(38), dp(38)
                    pos_hint: {"center_y": 0.5}

                MDIconButton:
                    icon: "briefcase-outline"
                    theme_text_color: "Custom"
                    text_color: 0, 0.82, 0.42, 1
                    on_release: app.open_pea_screen()
                    size_hint: None, None
                    size: dp(38), dp(38)
                    pos_hint: {"center_y": 0.5}

                MDIconButton:
                    icon: "cog"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    on_release: app.open_settings_screen()
                    size_hint: None, None
                    size: dp(38), dp(38)
                    pos_hint: {"center_y": 0.5}

            # Recherche
            MDBoxLayout:
                orientation: "horizontal"
                size_hint_y: None
                height: dp(50)
                padding: dp(8), dp(4)
                spacing: dp(8)
                md_bg_color: 0, 0, 0, 1

                MDTextField:
                    id: search_field
                    hint_text: "ISIN ou Ticker (FR0013341781)"
                    mode: "fill"
                    fill_color_normal: 0.06, 0.07, 0.10, 1
                    fill_color_focus: 0.08, 0.10, 0.15, 1
                    text_color_normal: 1, 1, 1, 1
                    text_color_focus: 1, 1, 1, 1
                    hint_text_color_normal: 0.35, 0.4, 0.5, 1
                    line_color_focus: 0, 0.82, 0.42, 1
                    size_hint_x: 0.62
                    font_size: sp(14)
                    on_text_validate: app.analyze_action()

                MDRaisedButton:
                    text: "ANALYSER"
                    size_hint: 0.38, None
                    height: dp(42)
                    font_size: sp(13)
                    md_bg_color: 0, 0.82, 0.42, 1
                    text_color: 0, 0, 0, 1
                    elevation: 0
                    on_release: app.analyze_action()

            # Status bar
            MDBoxLayout:
                size_hint_y: None
                height: dp(40)
                padding: dp(8), dp(4)
                spacing: dp(6)
                md_bg_color: 0, 0, 0, 1

                MDLabel:
                    id: monitor_status
                    text: "Surveillance: Arretee"
                    theme_text_color: "Custom"
                    text_color: 0.35, 0.4, 0.5, 1
                    font_style: "Caption"
                    size_hint_x: 0.4

                MDRaisedButton:
                    id: monitor_btn
                    text: "Demarrer"
                    font_size: sp(11)
                    size_hint: 0.3, None
                    height: dp(32)
                    md_bg_color: 0.15, 0.25, 0.65, 1
                    elevation: 0
                    on_release: app.toggle_monitor()

                MDRaisedButton:
                    id: add_watch_btn
                    text: "+ Suivre"
                    font_size: sp(11)
                    size_hint: 0.3, None
                    height: dp(32)
                    md_bg_color: 0, 0.52, 0.35, 1
                    elevation: 0
                    on_release: app.add_to_watchlist()
                    opacity: 0
                    disabled: True

            # Loading
            MDBoxLayout:
                id: loading_box
                size_hint_y: None
                height: dp(24)
                padding: dp(10), 0
                opacity: 0

                MDSpinner:
                    size_hint: None, None
                    size: dp(18), dp(18)
                    active: True
                    color: 0, 0.82, 0.42, 1

                MDLabel:
                    id: loading_label
                    text: ""
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    font_style: "Caption"

            # Contenu scrollable
            ScrollView:
                do_scroll_x: False
                bar_width: dp(2)

                MDBoxLayout:
                    id: content_box
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(5)
                    spacing: dp(4)

                    # === Signal Card ===
                    MDCard:
                        id: signal_card
                        orientation: "vertical"
                        size_hint_y: None
                        height: dp(130)
                        padding: dp(10), dp(6)
                        spacing: dp(2)
                        elevation: 0
                        radius: [dp(14)]
                        md_bg_color: 0.04, 0.045, 0.07, 1
                        opacity: 0

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(22)

                            MDLabel:
                                id: stock_name
                                text: ""
                                font_style: "Body1"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: 0.9, 0.92, 0.95, 1

                            MDLabel:
                                id: stock_price
                                text: ""
                                font_style: "Body1"
                                halign: "right"
                                bold: True

                        # Signal + Score sur une ligne
                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(32)
                            spacing: dp(6)

                            MDLabel:
                                id: signal_label
                                text: ""
                                font_style: "H6"
                                bold: True
                                halign: "center"
                                size_hint_x: 0.5

                            MDLabel:
                                id: score_label
                                text: ""
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: 0.55, 0.6, 0.65, 1
                                font_style: "Caption"
                                size_hint_x: 0.5

                        # Score bar
                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(10)
                            padding: dp(12), 0

                            MDProgressBar:
                                id: score_bar
                                value: 50
                                color: 0, 0.82, 0.42, 1

                        # Predictions J+5 / J+10
                        MDLabel:
                            id: pred_quick_label
                            text: ""
                            halign: "center"
                            font_style: "Caption"
                            bold: True
                            size_hint_y: None
                            height: dp(16)

                        # Pic / Creux
                        MDLabel:
                            id: summary_label
                            text: ""
                            font_style: "Caption"
                            theme_text_color: "Custom"
                            text_color: 0.35, 0.4, 0.5, 1
                            size_hint_y: None
                            height: dp(14)
                            halign: "center"
                            shorten: True
                            shorten_from: "right"

                    # === Scalping Quick Card ===
                    MDCard:
                        id: scalping_card
                        orientation: "vertical"
                        size_hint_y: None
                        height: dp(58)
                        padding: dp(10), dp(4)
                        spacing: dp(1)
                        elevation: 0
                        radius: [dp(12)]
                        md_bg_color: 0.04, 0.045, 0.07, 1
                        opacity: 0

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(22)
                            spacing: dp(8)

                            MDLabel:
                                id: scalp_signal_label
                                text: ""
                                font_style: "Body1"
                                bold: True
                                halign: "center"
                                size_hint_x: 0.35

                            MDLabel:
                                id: scalp_dir_label
                                text: ""
                                font_style: "Caption"
                                bold: True
                                halign: "center"
                                size_hint_x: 0.3

                            MDLabel:
                                id: scalp_conf_label
                                text: ""
                                font_style: "Caption"
                                halign: "center"
                                theme_text_color: "Custom"
                                text_color: 0.55, 0.6, 0.65, 1
                                size_hint_x: 0.35

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(18)
                            spacing: dp(6)

                            MDLabel:
                                id: scalp_obj_label
                                text: ""
                                font_style: "Caption"
                                halign: "center"
                                size_hint_x: 0.4

                            MDLabel:
                                id: scalp_sl_label
                                text: ""
                                font_style: "Caption"
                                halign: "center"
                                size_hint_x: 0.3

                            MDLabel:
                                id: scalp_tp_label
                                text: ""
                                font_style: "Caption"
                                halign: "center"
                                size_hint_x: 0.3

                    # === Onglets sur 2 lignes ===
                    MDBoxLayout:
                        id: tabs_scroll
                        orientation: "vertical"
                        size_hint_y: None
                        height: dp(78)
                        opacity: 0
                        spacing: dp(4)
                        padding: dp(4), dp(2)

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(35)
                            spacing: dp(4)
                            padding: dp(1), 0

                            MDRaisedButton:
                                text: "Jour J"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0, 0.52, 0.35, 1
                                elevation: 0
                                on_release: app.show_chart("today")

                            MDRaisedButton:
                                text: "Prix"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("prix")

                            MDRaisedButton:
                                text: "RSI"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("rsi")

                            MDRaisedButton:
                                text: "MACD"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("macd")

                            MDRaisedButton:
                                text: "5 Jours"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("intraday")

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(35)
                            spacing: dp(4)
                            padding: dp(1), 0

                            MDRaisedButton:
                                text: "1 An"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("1y")

                            MDRaisedButton:
                                text: "Prediction"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("prediction")

                            MDRaisedButton:
                                text: "Scalping"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("scalping")

                            MDRaisedButton:
                                text: "Score IA"
                                font_size: sp(10.5)
                                size_hint: 1, None
                                height: dp(32)
                                md_bg_color: 0.08, 0.09, 0.13, 1
                                elevation: 0
                                on_release: app.show_chart("analyse")

                    # === Graphique ===
                    MDCard:
                        id: chart_card
                        orientation: "vertical"
                        size_hint_y: None
                        height: dp(380)
                        radius: [dp(12)]
                        md_bg_color: 0, 0, 0, 1
                        elevation: 0
                        opacity: 0
                        padding: 0

                        AsyncImage:
                            id: chart_image
                            source: ""
                            allow_stretch: True
                            keep_ratio: True

                    # === Indicateurs ===
                    MDCard:
                        id: details_card
                        orientation: "vertical"
                        size_hint_y: None
                        height: dp(310)
                        padding: dp(10), dp(6)
                        spacing: dp(1)
                        radius: [dp(14)]
                        md_bg_color: 0.04, 0.045, 0.07, 1
                        elevation: 0
                        opacity: 0

                        MDLabel:
                            text: "Indicateurs techniques"
                            font_style: "Subtitle2"
                            bold: True
                            size_hint_y: None
                            height: dp(18)

                        MDSeparator:
                            height: dp(1)

                        MDLabel:
                            id: rsi_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: macd_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: ma_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: boll_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: stoch_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: mom_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: vol_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: trend_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: adx_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: obv_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDLabel:
                            id: ichi_label
                            text: ""
                            font_style: "Caption"
                            size_hint_y: None
                            height: dp(17)

                        MDSeparator:
                            height: dp(1)

                        MDLabel:
                            id: sr_label
                            text: ""
                            font_style: "Caption"
                            theme_text_color: "Custom"
                            text_color: 0.4, 0.5, 0.6, 1
                            size_hint_y: None
                            height: dp(30)

                    # === Watchlist ===
                    MDLabel:
                        text: "  Actions surveillees"
                        font_style: "Subtitle2"
                        bold: True
                        size_hint_y: None
                        height: dp(26)

                    MDBoxLayout:
                        id: watchlist_box
                        orientation: "vertical"
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(3)

                        MDLabel:
                            text: "Aucune action surveillee."
                            halign: "center"
                            theme_text_color: "Hint"
                            size_hint_y: None
                            height: dp(40)

    MDScreen:
        name: "pea"

        MDBoxLayout:
            orientation: "vertical"
            md_bg_color: 0, 0, 0, 1

            # Header PEA
            MDBoxLayout:
                size_hint_y: None
                height: dp(48)
                padding: dp(8), dp(6)
                spacing: dp(4)
                md_bg_color: 0, 0, 0, 1

                MDIconButton:
                    icon: "arrow-left"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    on_release: app.go_main()
                    size_hint: None, None
                    size: dp(38), dp(38)

                MDLabel:
                    text: "Mon PEA"
                    font_style: "H6"
                    bold: True
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1

                Widget:
                    size_hint_x: None
                    width: dp(1)

                MDIconButton:
                    icon: "plus-circle"
                    theme_text_color: "Custom"
                    text_color: 0, 0.82, 0.42, 1
                    on_release: app.pea_buy_dialog()
                    size_hint: None, None
                    size: dp(38), dp(38)

                MDIconButton:
                    icon: "refresh"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    on_release: app.refresh_pea()
                    size_hint: None, None
                    size: dp(38), dp(38)

            # Resume PEA
            MDCard:
                id: pea_summary_card
                orientation: "vertical"
                size_hint_y: None
                height: dp(200)
                padding: dp(12), dp(8)
                spacing: dp(2)
                elevation: 0
                radius: [dp(14)]
                md_bg_color: 0.04, 0.045, 0.07, 1

                MDLabel:
                    id: pea_total_value
                    text: "0.00 EUR"
                    font_style: "H5"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 1, 1, 1, 1
                    size_hint_y: None
                    height: dp(32)

                MDLabel:
                    id: pea_pnl_label
                    text: "+0.00 EUR (+0.00%)"
                    font_style: "Body1"
                    bold: True
                    halign: "center"
                    size_hint_y: None
                    height: dp(24)

                MDProgressBar:
                    id: pea_plafond_bar
                    value: 0
                    color: 0, 0.82, 0.42, 1
                    size_hint_y: None
                    height: dp(6)

                MDLabel:
                    id: pea_plafond_label
                    text: "Versements: 0 / 150 000 EUR"
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    size_hint_y: None
                    height: dp(16)

                MDLabel:
                    id: pea_fiscal_label
                    text: ""
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    size_hint_y: None
                    height: dp(16)

                MDLabel:
                    id: pea_impot_label
                    text: ""
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.5, 0.6, 1
                    size_hint_y: None
                    height: dp(16)

                MDLabel:
                    id: pea_net_label
                    text: ""
                    font_style: "Caption"
                    bold: True
                    halign: "center"
                    size_hint_y: None
                    height: dp(18)

                MDLabel:
                    id: pea_eligible_label
                    text: ""
                    font_style: "Caption"
                    halign: "center"
                    size_hint_y: None
                    height: dp(16)

            # Boutons achat/vente
            MDBoxLayout:
                size_hint_y: None
                height: dp(46)
                padding: dp(8), dp(4)
                spacing: dp(8)

                MDRaisedButton:
                    text: "ACHETER"
                    size_hint_x: 0.5
                    height: dp(38)
                    md_bg_color: 0, 0.52, 0.35, 1
                    text_color: 1, 1, 1, 1
                    font_size: sp(14)
                    elevation: 0
                    on_release: app.pea_buy_dialog()

                MDRaisedButton:
                    text: "VENDRE"
                    size_hint_x: 0.5
                    height: dp(38)
                    md_bg_color: 0.7, 0.1, 0.1, 1
                    text_color: 1, 1, 1, 1
                    font_size: sp(14)
                    elevation: 0
                    on_release: app.pea_sell_dialog()

            # Positions
            MDLabel:
                text: "  Positions"
                font_style: "Subtitle2"
                bold: True
                theme_text_color: "Custom"
                text_color: 0.7, 0.75, 0.8, 1
                size_hint_y: None
                height: dp(28)

            ScrollView:
                do_scroll_x: False
                bar_width: dp(2)

                MDBoxLayout:
                    id: pea_positions_box
                    orientation: "vertical"
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(5)
                    spacing: dp(4)

                    MDLabel:
                        text: "Aucune position"
                        halign: "center"
                        theme_text_color: "Hint"
                        size_hint_y: None
                        height: dp(60)
'''


class StockAnalyzerApp(MDApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.monitor = None
        self.current_ticker = None
        self.current_result = None
        self.current_name = None
        self._chart_cache = {}
        self._chart_lock = threading.Lock()
        self._active_tab = "today"
        self.notifications_enabled = True
        self.pea = None

    def build(self):
        self.title = "StockAnalyzer IA"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"

        if platform not in ('android', 'ios'):
            # Simule ratio Poco F7 (1080x2400) en petit
            Window.size = (390, 844)

        return Builder.load_string(KV)

    def on_start(self):
        self._load_settings()
        from monitor import MarketMonitor
        self.monitor = MarketMonitor(
            on_signal=self._on_market_signal,
            check_interval=self._check_interval,
        )
        from pea_manager import PEAManager
        self.pea = PEAManager()
        self._refresh_watchlist_view()
        self._update_notif_icon()

        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.INTERNET, Permission.POST_NOTIFICATIONS])
            except ImportError:
                pass

        # Gestion bouton retour Android
        from kivy.base import EventLoop
        EventLoop.window.bind(on_keyboard=self._on_keyboard)

    def _load_settings(self):
        import json
        try:
            with open(self._settings_path(), 'r') as f:
                s = json.load(f)
                self.notifications_enabled = s.get('notifications', True)
                self._check_interval = s.get('check_interval', 300)
                self._max_watchlist = s.get('max_watchlist', 20)
        except Exception:
            self.notifications_enabled = True
            self._check_interval = 300
            self._max_watchlist = 20

    def _save_settings(self):
        import json
        try:
            with open(self._settings_path(), 'r') as f:
                s = json.load(f)
        except Exception:
            s = {}
        s['notifications'] = self.notifications_enabled
        s['check_interval'] = getattr(self, '_check_interval', 300)
        s['max_watchlist'] = getattr(self, '_max_watchlist', 20)
        try:
            with open(self._settings_path(), 'w') as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass

    def _settings_path(self):
        try:
            from android.storage import app_storage_path
            return os.path.join(app_storage_path(), 'settings.json')
        except ImportError:
            return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'settings.json')

    @mainthread
    def _show_toast(self, text: str):
        try:
            from kivymd.toast import toast
            toast(text)
        except Exception:
            print(f"[INFO] {text}")

    def _update_notif_icon(self):
        ids = self.root.ids
        if self.notifications_enabled:
            ids.notif_icon.icon = "bell"
            ids.notif_icon.text_color = (0, 0.82, 0.42, 1)
        else:
            ids.notif_icon.icon = "bell-off"
            ids.notif_icon.text_color = (0.4, 0.2, 0.2, 1)

    def quick_toggle_notif(self):
        self.notifications_enabled = not self.notifications_enabled
        self._save_settings()
        self._update_notif_icon()
        state = "activees" if self.notifications_enabled else "desactivees"
        self._show_toast(f"Notifications {state}")

    def _on_keyboard(self, window, key, *args):
        if key == 27:  # Bouton retour Android / Echap
            if platform == 'android':
                return True  # Empêcher la fermeture sur Android
            return False  # Permettre la fermeture sur desktop
        return False

    # === Analyse ===

    def analyze_action(self):
        ticker = self.root.ids.search_field.text.strip()
        if not ticker:
            self._show_toast("Entrez un code ISIN ou un ticker")
            return
        # Validation: ISIN (2 lettres + 10 chiffres) ou ticker (lettres/chiffres/points, max 20 chars)
        if not re.match(r'^[A-Za-z]{2}\d{10}$', ticker) and not re.match(r'^[A-Za-z0-9._-]{1,20}$', ticker):
            self._show_toast("Format invalide. Ex: AAPL, MC.PA, FR0000121014")
            return
        self.current_ticker = ticker
        with self._chart_lock:
            self._chart_cache.clear()
        self._show_loading(True, f"Analyse de {ticker}...")
        threading.Thread(target=self._do_analysis, args=(ticker,), daemon=True).start()

    def _do_analysis(self, ticker: str):
        try:
            from data_fetcher import fetch_stock_data, fetch_realtime_price, get_stock_name, isin_to_ticker
            from analyzer import analyze_stock
            from chart_generator import (chart_prix, chart_rsi, chart_macd, chart_today,
                                         chart_intraday, chart_annuel, chart_prediction, chart_analyse,
                                         chart_scalping)

            resolved = isin_to_ticker(ticker)

            # Nettoyer anciens fichiers PNG temporaires
            import tempfile, glob
            for old_png in glob.glob(os.path.join(tempfile.gettempdir(), "sa_*.png")):
                try:
                    os.remove(old_png)
                except OSError:
                    pass

            df_3mo = fetch_stock_data(ticker, period="3mo", interval="1d")
            result = analyze_stock(df_3mo)
            price_info = fetch_realtime_price(ticker)
            name = get_stock_name(ticker)

            self.current_result = result
            self.current_name = name

            # Jour J
            try:
                df_today = fetch_stock_data(ticker, period="1d", interval="5m")
                if len(df_today) > 2:
                    self._chart_cache["today"] = chart_today(df_today, resolved, name)
            except Exception:
                pass

            # Prix 3 mois
            self._chart_cache["prix"] = chart_prix(df_3mo, resolved, name, result)
            self._chart_cache["rsi"] = chart_rsi(df_3mo, resolved, name)
            self._chart_cache["macd"] = chart_macd(df_3mo, resolved, name)

            # Prediction
            if result.prediction:
                self._chart_cache["prediction"] = chart_prediction(
                    df_3mo, result.prediction, resolved, name, result)

            # Score IA
            self._chart_cache["analyse"] = chart_analyse(result)

            # Scalping intraday 5 min
            try:
                from data_fetcher import fetch_intraday_data
                from analyzer import predict_intraday
                df_intra_5m = fetch_intraday_data(ticker)
                if len(df_intra_5m) > 10:
                    intra_pred = predict_intraday(df_intra_5m, df_3mo)
                    result.intraday = intra_pred
                    self._chart_cache["scalping"] = chart_scalping(
                        intra_pred, resolved, name, float(df_intra_5m['Close'].iloc[-1]))
            except Exception:
                pass

            # Extra
            self._gen_extra(ticker, resolved, name)

            first = self._chart_cache.get("today", self._chart_cache.get("prix", ""))
            self._update_ui(name, result, price_info, first)

            # Notification automatique si signal d'achat/vente detecte
            if self.notifications_enabled:
                self._send_signal_alert(name, result)

        except Exception as e:
            self._show_toast(f"Erreur: {e}")
        finally:
            self._show_loading(False)

    def _gen_extra(self, ticker, resolved, name):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from data_fetcher import fetch_stock_data
        from chart_generator import chart_annuel, chart_intraday

        def _make_1y():
            df = fetch_stock_data(ticker, period="1y", interval="1d")
            return "1y", chart_annuel(df, resolved, name)

        def _make_intra():
            df = fetch_stock_data(ticker, period="5d", interval="1h")
            return "intraday", chart_intraday(df, resolved, name)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_make_1y), pool.submit(_make_intra)]
            for fut in as_completed(futures):
                try:
                    key, path = fut.result()
                    self._chart_cache[key] = path
                except Exception:
                    pass

    @mainthread
    def _update_ui(self, name, result, price_info, chart_path):
        ids = self.root.ids

        ids.stock_name.text = (name[:24] + "...") if len(name) > 26 else name

        currency = price_info.get('currency', 'EUR')
        self._currency = currency
        change = price_info.get('change_percent', 0)
        sign = "+" if change >= 0 else ""
        ids.stock_price.text = f"{result.price:.2f} {currency}  {sign}{change:.2f}%"
        ids.stock_price.theme_text_color = "Custom"
        ids.stock_price.text_color = (0, 0.9, 0.42, 1) if change >= 0 else (1, 0.1, 0.27, 1)

        # Signal
        ids.signal_label.text = result.signal.value
        ids.signal_label.theme_text_color = "Custom"
        cmap = {
            "ACHAT FORT": (0, 0.9, 0.42, 1), "ACHAT": (0, 0.78, 0.35, 1),
            "NEUTRE": (1, 0.67, 0, 1),
            "VENTE": (1, 0.1, 0.27, 1), "VENTE FORTE": (1, 0, 0.15, 1),
        }
        sc = cmap.get(result.signal.value, (1, 1, 1, 1))
        ids.signal_label.text_color = sc

        ids.score_bar.value = (result.score + 100) / 2
        ids.score_bar.color = sc
        ids.score_label.text = f"Score IA: {result.score:+.1f}/100  |  Confiance: {result.confidence:.0f}%"

        # Prediction rapide
        if result.prediction:
            p = result.prediction
            pc = (0, 0.9, 0.42, 1) if p.variation_5j_pct >= 0 else (1, 0.1, 0.27, 1)
            s5 = "+" if p.variation_5j_pct >= 0 else ""
            s10 = "+" if p.variation_10j_pct >= 0 else ""
            ids.pred_quick_label.text = (
                f"J+5: {p.objectif_5j:.2f} ({s5}{p.variation_5j_pct:.1f}%)  |  "
                f"J+10: {p.objectif_10j:.2f} ({s10}{p.variation_10j_pct:.1f}%)")
            ids.pred_quick_label.theme_text_color = "Custom"
            ids.pred_quick_label.text_color = pc

            # Pic / Creux
            pic_var = ((p.pic_prix / result.price) - 1) * 100
            creux_var = ((p.creux_prix / result.price) - 1) * 100
            ids.summary_label.text = (
                f"Pic: {p.pic_prix:.2f} J+{p.pic_jour} (+{pic_var:.1f}%)  "
                f"Creux: {p.creux_prix:.2f} J+{p.creux_jour} ({creux_var:+.1f}%)")
        else:
            ids.summary_label.text = result.summary

        # Indicateurs
        d = result.details
        def _ind(key, label):
            s = d[key]['score']
            c = (0, 0.9, 0.42, 1) if s > 2 else ((1, 0.1, 0.27, 1) if s < -2 else (1, 0.67, 0, 1))
            return f"[color={'%02x%02x%02x' % (int(c[0]*255), int(c[1]*255), int(c[2]*255))}]{s:+.0f}[/color]"

        ids.rsi_label.markup = True
        ids.rsi_label.text = f"RSI: {d['rsi']['value']:.0f}  {_ind('rsi','RSI')}  {d['rsi']['desc'][:45]}"
        ids.macd_label.markup = True
        ids.macd_label.text = f"MACD  {_ind('macd','MACD')}  {d['macd']['desc'][:45]}"
        ids.ma_label.markup = True
        ids.ma_label.text = f"MM  {_ind('moyennes_mobiles','MM')}  {d['moyennes_mobiles']['desc'][:45]}"
        ids.boll_label.markup = True
        ids.boll_label.text = f"Bollinger  {_ind('bollinger','B')}  {d['bollinger']['desc'][:40]}"
        ids.stoch_label.markup = True
        ids.stoch_label.text = f"Stoch  {_ind('stochastique','S')}  {d['stochastique']['desc'][:40]}"
        ids.mom_label.markup = True
        ids.mom_label.text = f"Momentum  {_ind('momentum','M')}  {d['momentum']['desc'][:40]}"
        ids.vol_label.markup = True
        ids.vol_label.text = f"Volume  {_ind('volume','V')}  {d['volume']['desc'][:40]}"
        ids.trend_label.markup = True
        ids.trend_label.text = f"Tendance  {_ind('tendance','T')}  {d['tendance']['desc'][:40]}"

        ids.adx_label.markup = True
        ids.adx_label.text = f"ADX  {_ind('adx','ADX')}  {d['adx']['desc'][:40]}" if 'adx' in d else ""
        ids.obv_label.markup = True
        ids.obv_label.text = f"OBV  {_ind('obv','OBV')}  {d['obv']['desc'][:40]}" if 'obv' in d else ""
        ids.ichi_label.markup = True
        ids.ichi_label.text = f"Ichimoku  {_ind('ichimoku','I')}  {d['ichimoku']['desc'][:40]}" if 'ichimoku' in d else ""

        supports = d.get('supports', [])
        resistances = d.get('resistances', [])
        sr = "S: " + (" / ".join(f"{s:.2f}" for s in supports[:3]) if supports else "---")
        sr += "  |  R: " + (" / ".join(f"{r:.2f}" for r in resistances[:3]) if resistances else "---")
        ids.sr_label.text = sr

        # Graphique
        if chart_path:
            ids.chart_image.source = chart_path
            ids.chart_image.reload()
            self._active_tab = "today" if "today" in self._chart_cache else "prix"

        ids.signal_card.opacity = 1
        ids.tabs_scroll.opacity = 1
        ids.chart_card.opacity = 1
        ids.details_card.opacity = 1
        ids.add_watch_btn.opacity = 1
        ids.add_watch_btn.disabled = False

        # Scalping quick card
        if result.intraday:
            ip = result.intraday
            sc_map = {
                "ACHAT IMMEDIAT": (0, 0.9, 0.42, 1), "VENTE IMMEDIATE": (1, 0.1, 0.27, 1),
                "ATTENTE": (1, 0.67, 0, 1),
            }
            sc_color = sc_map.get(ip.signal_scalping, (1, 1, 1, 1))
            ids.scalp_signal_label.text = ip.signal_scalping
            ids.scalp_signal_label.theme_text_color = "Custom"
            ids.scalp_signal_label.text_color = sc_color
            ids.scalp_dir_label.text = f"{ip.direction} ({ip.force:.0f}%)"
            ids.scalp_dir_label.theme_text_color = "Custom"
            ids.scalp_dir_label.text_color = sc_color
            ids.scalp_conf_label.text = f"Conf.: {ip.confiance:.0f}%"
            s30 = "+" if ip.variation_30min_pct >= 0 else ""
            ids.scalp_obj_label.text = f"30min: {ip.objectif_30min:.2f} ({s30}{ip.variation_30min_pct:.2f}%)"
            ids.scalp_obj_label.theme_text_color = "Custom"
            ids.scalp_obj_label.text_color = sc_color
            ids.scalp_sl_label.text = f"Stop: {ip.stop_loss:.2f}"
            ids.scalp_sl_label.theme_text_color = "Custom"
            ids.scalp_sl_label.text_color = (1, 0.1, 0.27, 1)
            ids.scalp_tp_label.text = f"Obj.: {ip.take_profit:.2f}"
            ids.scalp_tp_label.theme_text_color = "Custom"
            ids.scalp_tp_label.text_color = (0, 0.9, 0.42, 1)
            ids.scalping_card.opacity = 1
        else:
            ids.scalping_card.opacity = 0

        self._highlight_tab(self._active_tab)

    @mainthread
    def show_chart(self, chart_type):
        if chart_type in self._chart_cache:
            ids = self.root.ids
            ids.chart_image.source = self._chart_cache[chart_type]
            ids.chart_image.reload()
            self._active_tab = chart_type
            h = {"today": 380, "prix": 400, "rsi": 320, "macd": 320,
                 "intraday": 380, "1y": 320, "prediction": 520, "scalping": 560, "analyse": 500}
            ids.chart_card.height = dp(h.get(chart_type, 380))
            self._highlight_tab(chart_type)
        else:
            self._show_toast("Graphique non disponible")

    def _highlight_tab(self, active):
        tab_map = {
            "today": (0, 0), "prix": (0, 1), "rsi": (0, 2), "macd": (0, 3), "intraday": (0, 4),
            "1y": (1, 0), "prediction": (1, 1), "scalping": (1, 2), "analyse": (1, 3),
        }
        on = (0, 0.52, 0.35, 1)
        off = (0.08, 0.09, 0.13, 1)
        target = tab_map.get(active)
        rows = self.root.ids.tabs_scroll.children
        for row_idx, row in enumerate(reversed(list(rows))):
            if hasattr(row, 'children'):
                for col_idx, btn in enumerate(reversed(list(row.children))):
                    btn.md_bg_color = on if target == (row_idx, col_idx) else off

    @mainthread
    def _show_loading(self, show, text=""):
        self.root.ids.loading_box.opacity = 1 if show else 0
        self.root.ids.loading_label.text = text if show else ""

    def _send_signal_alert(self, name, result):
        """Envoie une notification push + message quand signal ACHAT ou VENTE detecte."""
        sig = result.signal.value
        if sig == "NEUTRE":
            return

        p = result.prediction
        ccy = getattr(self, '_currency', 'EUR')
        title = f"Signal {sig} - {name}"

        if not p:
            msg = f"Score: {result.score:+.1f} | Prix: {result.price:.2f} {ccy}"
        elif sig in ("ACHAT FORT", "ACHAT"):
            msg = (f"Score: {result.score:+.1f} | Confiance: {result.confidence:.0f}%\n"
                   f"Prix: {result.price:.2f} {ccy}\n"
                   f"Objectif J+5: {p.objectif_5j:.2f} ({p.variation_5j_pct:+.1f}%)\n"
                   f"Pic attendu: {p.pic_prix:.2f} a J+{p.pic_jour}")
        else:
            msg = (f"Score: {result.score:+.1f} | Confiance: {result.confidence:.0f}%\n"
                   f"Prix: {result.price:.2f} {ccy}\n"
                   f"Risque J+5: {p.objectif_5j:.2f} ({p.variation_5j_pct:+.1f}%)\n"
                   f"Creux attendu: {p.creux_prix:.2f} a J+{p.creux_jour}")

        try:
            from plyer import notification
            notification.notify(title=title, message=msg, app_name="StockAnalyzer", timeout=30)
        except Exception:
            pass
        self._show_signal_dialog(title, msg, sig)

    @mainthread
    def _show_signal_dialog(self, title, msg, sig):
        """Affiche un dialog popup avec le signal detecte."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton

        color = "00E676" if "ACHAT" in sig else "FF1744"
        dialog = MDDialog(
            title=f"[color=#{color}]{title}[/color]",
            text=msg,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())])
        dialog.open()

    # === Watchlist ===

    def add_to_watchlist(self):
        if not self.current_ticker:
            return
        wl = self.monitor.get_watchlist()
        if self.current_ticker in wl:
            self._show_toast("Deja dans la liste")
            return
        max_wl = getattr(self, '_max_watchlist', 20)
        if len(wl) >= max_wl:
            self._show_toast(f"Limite atteinte ({max_wl} actions max)")
            return
        name = self.monitor.add_stock(self.current_ticker)
        if self.current_result:
            r = self.current_result
            wl = self.monitor.get_watchlist()
            if self.current_ticker in wl:
                wl[self.current_ticker].update({
                    "last_signal": r.signal.value, "last_score": r.score,
                    "last_price": r.price, "last_check": datetime.now().isoformat(),
                })
                self.monitor._save_watchlist()
        self._show_toast(f"{name} ajoute")
        self._refresh_watchlist_view()

    def remove_from_watchlist(self, ticker):
        self.monitor.remove_stock(ticker)
        self._refresh_watchlist_view()

    @mainthread
    def _refresh_watchlist_view(self):
        from kivymd.uix.card import MDCard
        from kivymd.uix.label import MDLabel
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDIconButton

        box = self.root.ids.watchlist_box
        box.clear_widgets()
        watchlist = self.monitor.get_watchlist()

        if not watchlist:
            box.add_widget(MDLabel(
                text="Aucune action surveillee.", halign="center",
                theme_text_color="Hint", size_hint_y=None, height=dp(40)))
            return

        for ticker, info in watchlist.items():
            signal = info.get("last_signal", "---")
            score = info.get("last_score", 0)
            price = info.get("last_price", 0)
            name = info.get("name", ticker)

            if signal in ("ACHAT FORT", "ACHAT"):
                sig_color = (0, 0.9, 0.42, 1); icon = "trending-up"
            elif signal in ("VENTE FORTE", "VENTE"):
                sig_color = (1, 0.1, 0.27, 1); icon = "trending-down"
            else:
                sig_color = (1, 0.67, 0, 1); icon = "trending-neutral"

            card = MDCard(
                orientation="horizontal", size_hint_y=None, height=dp(52),
                padding=(dp(6), dp(4)), radius=[dp(12)],
                md_bg_color=(0.04, 0.045, 0.07, 1), elevation=0,
                on_release=lambda x, t=ticker: self._on_watchlist_click(t))

            card.add_widget(MDIconButton(
                icon=icon, theme_text_color="Custom", text_color=sig_color,
                size_hint=(None, None), size=(dp(34), dp(34))))

            info_box = MDBoxLayout(orientation="vertical", padding=(dp(3), 0))
            info_box.add_widget(MDLabel(
                text=name[:22], font_style="Body2", bold=True,
                size_hint_y=None, height=dp(18)))
            info_box.add_widget(MDLabel(
                text=f"{signal} | {score:+.0f} | {price:.2f} {getattr(self, '_currency', 'EUR')}",
                font_style="Caption", theme_text_color="Custom",
                text_color=sig_color, size_hint_y=None, height=dp(15)))
            card.add_widget(info_box)

            card.add_widget(MDIconButton(
                icon="close-circle-outline", theme_text_color="Custom",
                text_color=(0.4, 0.2, 0.2, 1), size_hint=(None, None),
                size=(dp(30), dp(30)),
                on_release=lambda x, t=ticker: self.remove_from_watchlist(t)))
            box.add_widget(card)

    def _on_watchlist_click(self, ticker):
        self.root.ids.search_field.text = ticker
        self.analyze_action()

    # === Monitoring ===

    def toggle_monitor(self):
        if self.monitor.is_running:
            self.monitor.stop()
            self._update_monitor_status(False)
        else:
            self.monitor.start()
            self._update_monitor_status(True)

    @mainthread
    def _update_monitor_status(self, running):
        ids = self.root.ids
        if running:
            ids.monitor_status.text = "Surveillance: Active"
            ids.monitor_status.text_color = (0, 0.9, 0.42, 1)
            ids.monitor_btn.text = "Arreter"
            ids.monitor_btn.md_bg_color = (0.7, 0.1, 0.1, 1)
        else:
            ids.monitor_status.text = "Surveillance: Arretee"
            ids.monitor_status.text_color = (0.35, 0.4, 0.5, 1)
            ids.monitor_btn.text = "Demarrer"
            ids.monitor_btn.md_bg_color = (0.15, 0.25, 0.65, 1)

    def refresh_all(self):
        if not self.monitor.get_watchlist():
            self._show_toast("Aucune action a rafraichir")
            return
        self._show_loading(True, "Rafraichissement...")
        def _do():
            self.monitor.check_all()
            self._on_refresh_done()
        threading.Thread(target=_do, daemon=True).start()

    @mainthread
    def _on_refresh_done(self):
        self._show_loading(False)
        self._refresh_watchlist_view()
        self._show_toast("Mise a jour terminee")

    def _on_market_signal(self, ticker, signal, result):
        self._refresh_watchlist_view()
        if not self.notifications_enabled:
            return
        name = self.monitor.get_watchlist().get(ticker, {}).get("name", ticker)
        if signal.value in ("ACHAT FORT", "ACHAT"):
            title = f"Signal ACHAT - {name}"
        elif signal.value in ("VENTE FORTE", "VENTE"):
            title = f"Signal VENTE - {name}"
        else:
            title = f"Signal Neutre - {name}"
        message = f"{result.signal.value} | Score: {result.score:+.1f}\nPrix: {result.price:.2f} {getattr(self, '_currency', 'EUR')}"
        try:
            from plyer import notification
            notification.notify(title=title, message=message, app_name="StockAnalyzer", timeout=30)
        except Exception:
            self._show_toast(title)

    def open_settings_screen(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel

        # Contenu du dialog
        content = MDBoxLayout(
            orientation="vertical", spacing=dp(6), padding=(dp(8), dp(4)),
            size_hint_y=None, height=dp(280))

        # Toggle notifications
        notif_row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        notif_row.add_widget(MDLabel(
            text="Notifications", font_style="Body1", bold=True, size_hint_x=0.6))
        notif_btn = MDRaisedButton(
            text="ACTIVE" if self.notifications_enabled else "DESACTIVE",
            size_hint_x=0.4,
            md_bg_color=(0, 0.52, 0.35, 1) if self.notifications_enabled else (0.5, 0.15, 0.15, 1),
            elevation=0, font_size=sp(13))

        def _toggle_notif(inst):
            self.notifications_enabled = not self.notifications_enabled
            self._save_settings()
            inst.text = "ACTIVE" if self.notifications_enabled else "DESACTIVE"
            inst.md_bg_color = (0, 0.52, 0.35, 1) if self.notifications_enabled else (0.5, 0.15, 0.15, 1)

        notif_btn.bind(on_release=_toggle_notif)
        notif_row.add_widget(notif_btn)
        content.add_widget(notif_row)

        # Info
        content.add_widget(MDLabel(
            text=f"Surveillance: toutes les {self.monitor.check_interval // 60} min",
            font_style="Caption", theme_text_color="Custom",
            text_color=(0.5, 0.55, 0.6, 1), size_hint_y=None, height=dp(18)))
        content.add_widget(MDLabel(
            text=f"Actions surveillees: {len(self.monitor.get_watchlist())}",
            font_style="Caption", theme_text_color="Custom",
            text_color=(0.5, 0.55, 0.6, 1), size_hint_y=None, height=dp(18)))

        content.add_widget(MDLabel(text="", size_hint_y=None, height=dp(6)))

        content.add_widget(MDLabel(
            text="11 Indicateurs IA :", font_style="Body2", bold=True,
            size_hint_y=None, height=dp(18)))
        content.add_widget(MDLabel(
            text="  MACD 15% | RSI 12% | MM 12% | Tendance 12%\n  Stoch 8% | Bollinger 8% | Momentum 8%\n  ADX 7% | Ichimoku 7% | OBV 6% | Volume 5%",
            font_style="Caption", theme_text_color="Custom",
            text_color=(0.4, 0.45, 0.5, 1), size_hint_y=None, height=dp(48)))

        content.add_widget(MDLabel(text="", size_hint_y=None, height=dp(4)))

        content.add_widget(MDLabel(
            text="Prediction IA : J+5 / J+10 / J+20\nSupport / Resistance automatiques",
            font_style="Caption", theme_text_color="Custom",
            text_color=(0.4, 0.45, 0.5, 1), size_hint_y=None, height=dp(36)))

        content.add_widget(MDLabel(
            text="StockAnalyzer IA v2.1", font_style="Caption",
            halign="center", theme_text_color="Custom",
            text_color=(0.3, 0.33, 0.38, 1), size_hint_y=None, height=dp(18)))

        dialog = MDDialog(
            title="Parametres",
            type="custom",
            content_cls=content,
            buttons=[MDFlatButton(text="FERMER", on_release=lambda x: dialog.dismiss())])
        dialog.open()

    # === PEA ===

    def open_pea_screen(self):
        self.root.current = "pea"
        self._refresh_pea_view()

    def go_main(self):
        self.root.current = "main"

    def refresh_pea(self):
        self._show_toast("Mise a jour PEA...")
        threading.Thread(target=self._do_refresh_pea, daemon=True).start()

    def _do_refresh_pea(self):
        from data_fetcher import fetch_realtime_price, isin_to_ticker
        prix_actuels = {}
        for ticker in list(self.pea.positions.keys()):
            try:
                info = fetch_realtime_price(ticker)
                prix_actuels[ticker] = info.get("price", 0)
            except Exception:
                pass
        self._refresh_pea_view(prix_actuels)

    @mainthread
    def _refresh_pea_view(self, prix_actuels=None):
        from kivymd.uix.card import MDCard
        from kivymd.uix.label import MDLabel
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDIconButton

        ids = self.root.ids
        resume = self.pea.get_resume(prix_actuels)

        # Valeur totale
        ids.pea_total_value.text = f"{resume['total_value']:.2f} EUR"

        # P&L
        pnl = resume["pnl_total"]
        pnl_pct = resume["pnl_total_pct"]
        sign = "+" if pnl >= 0 else ""
        pnl_color = (0, 0.9, 0.42, 1) if pnl >= 0 else (1, 0.1, 0.27, 1)
        ids.pea_pnl_label.text = f"{sign}{pnl:.2f} EUR ({sign}{pnl_pct:.2f}%)"
        ids.pea_pnl_label.theme_text_color = "Custom"
        ids.pea_pnl_label.text_color = pnl_color

        # Plafond
        pct_plafond = (resume["total_versements"] / 150000) * 100
        ids.pea_plafond_bar.value = min(100, pct_plafond)
        ids.pea_plafond_label.text = (
            f"Versements: {resume['total_versements']:,.0f} / 150 000 EUR  "
            f"(reste {resume['plafond_restant']:,.0f})")

        # Fiscalite
        fisc = resume["fiscalite"]
        ids.pea_fiscal_label.text = f"Regime: {fisc['regime']}"
        ids.pea_impot_label.text = f"Impot estime: {resume['impot_estime']:.2f} EUR ({fisc['taux_total']}%)"

        net = resume["pnl_net"]
        net_sign = "+" if net >= 0 else ""
        net_color = (0, 0.9, 0.42, 1) if net >= 0 else (1, 0.1, 0.27, 1)
        ids.pea_net_label.text = f"P&L net apres impot: {net_sign}{net:.2f} EUR"
        ids.pea_net_label.theme_text_color = "Custom"
        ids.pea_net_label.text_color = net_color

        anc = resume["anciennete"]
        if anc > 0:
            ids.pea_eligible_label.text = f"Anciennete: {anc:.1f} an(s) | {'Exonere IR' if anc >= 5 else f'{5-anc:.1f} an(s) avant exoneration'}"
            ids.pea_eligible_label.theme_text_color = "Custom"
            ids.pea_eligible_label.text_color = (0, 0.82, 0.42, 1) if anc >= 5 else (1, 0.67, 0, 1)
        else:
            ids.pea_eligible_label.text = "PEA non ouvert"

        # Positions
        box = ids.pea_positions_box
        box.clear_widgets()

        positions = resume["positions"]
        if not positions:
            box.add_widget(MDLabel(
                text="Aucune position", halign="center",
                theme_text_color="Hint", size_hint_y=None, height=dp(60)))
            return

        for p in positions:
            pnl_pos = p["pnl"]
            pnl_pct_pos = p["pnl_pct"]
            pos_color = (0, 0.9, 0.42, 1) if pnl_pos >= 0 else (1, 0.1, 0.27, 1)
            icon = "trending-up" if pnl_pos >= 0 else "trending-down"

            card = MDCard(
                orientation="horizontal", size_hint_y=None, height=dp(64),
                padding=(dp(6), dp(4)), radius=[dp(12)],
                md_bg_color=(0.04, 0.045, 0.07, 1), elevation=0)

            card.add_widget(MDIconButton(
                icon=icon, theme_text_color="Custom", text_color=pos_color,
                size_hint=(None, None), size=(dp(34), dp(34))))

            info_box = MDBoxLayout(orientation="vertical", padding=(dp(3), 0))
            info_box.add_widget(MDLabel(
                text=f"{p['name'][:20]}  x{p['quantity']}", font_style="Body2", bold=True,
                size_hint_y=None, height=dp(18)))

            s = "+" if pnl_pos >= 0 else ""
            info_box.add_widget(MDLabel(
                text=f"PRU: {p['pru']:.2f}  |  Actuel: {p['prix_actuel']:.2f}",
                font_style="Caption", theme_text_color="Custom",
                text_color=(0.4, 0.5, 0.6, 1), size_hint_y=None, height=dp(14)))
            info_box.add_widget(MDLabel(
                text=f"P&L: {s}{pnl_pos:.2f} EUR ({s}{pnl_pct_pos:.1f}%)  |  Val: {p['value']:.2f}",
                font_style="Caption", theme_text_color="Custom",
                text_color=pos_color, size_hint_y=None, height=dp(14)))
            card.add_widget(info_box)

            card.add_widget(MDIconButton(
                icon="minus-circle-outline", theme_text_color="Custom",
                text_color=(0.7, 0.1, 0.1, 1), size_hint=(None, None),
                size=(dp(30), dp(30)),
                on_release=lambda x, t=p["ticker"]: self.pea_sell_dialog(t)))

            box.add_widget(card)

    def pea_buy_dialog(self):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.label import MDLabel

        content = MDBoxLayout(
            orientation="vertical", spacing=dp(8), padding=(dp(8), dp(4)),
            size_hint_y=None, height=dp(220))

        ticker_field = MDTextField(
            hint_text="ISIN ou Ticker (ex: FR0013341781, MC.PA)",
            mode="fill", size_hint_y=None, height=dp(48), font_size=sp(14))

        qty_field = MDTextField(
            hint_text="Quantite", mode="fill", input_filter="int",
            size_hint_y=None, height=dp(48), font_size=sp(14))

        price_field = MDTextField(
            hint_text="Prix unitaire (EUR)", mode="fill", input_filter="float",
            size_hint_y=None, height=dp(48), font_size=sp(14))

        elig_label = MDLabel(
            text="", font_style="Caption", halign="center",
            size_hint_y=None, height=dp(18))

        reste = self.pea.PEA_PLAFOND - self.pea.total_versements if hasattr(self.pea, 'total_versements') else 150000
        info_label = MDLabel(
            text=f"Plafond restant: {reste:,.0f} EUR",
            font_style="Caption", halign="center",
            theme_text_color="Custom", text_color=(0.4, 0.5, 0.6, 1),
            size_hint_y=None, height=dp(18))

        def _check_elig(instance, value):
            from pea_manager import PEAManager
            if len(value.strip()) >= 3:
                if PEAManager.is_pea_eligible(value.strip()):
                    elig_label.text = "Eligible PEA"
                    elig_label.theme_text_color = "Custom"
                    elig_label.text_color = (0, 0.82, 0.42, 1)
                else:
                    elig_label.text = "NON eligible PEA (hors EEE)"
                    elig_label.theme_text_color = "Custom"
                    elig_label.text_color = (1, 0.1, 0.27, 1)
            else:
                elig_label.text = ""

        ticker_field.bind(text=_check_elig)

        # Pre-remplir si analyse en cours
        if self.current_ticker:
            ticker_field.text = self.current_ticker
        if self.current_result:
            price_field.text = f"{self.current_result.price:.2f}"

        content.add_widget(ticker_field)
        content.add_widget(elig_label)
        content.add_widget(qty_field)
        content.add_widget(price_field)
        content.add_widget(info_label)

        dialog = MDDialog(
            title="Achat PEA",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="ACHETER", md_bg_color=(0, 0.52, 0.35, 1),
                    on_release=lambda x: self._exec_pea_buy(
                        dialog, ticker_field.text, qty_field.text, price_field.text)),
            ])
        dialog.open()

    def _exec_pea_buy(self, dialog, ticker_raw, qty_raw, price_raw):
        try:
            ticker = ticker_raw.strip()
            if not ticker:
                self._show_toast("Entrez un ticker ou ISIN")
                return
            qty = int(qty_raw)
            prix = float(price_raw)
        except (ValueError, TypeError):
            self._show_toast("Quantite/prix invalide")
            return

        from data_fetcher import get_stock_name
        name = get_stock_name(ticker)
        result = self.pea.acheter(ticker, name, qty, prix)

        if result["success"]:
            dialog.dismiss()
            self._show_toast(f"Achat {name} x{qty} a {prix:.2f} EUR = {result['montant']:.2f} EUR")
            self._refresh_pea_view()
        else:
            self._show_toast(result["error"])

    def pea_sell_dialog(self, ticker=None):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.label import MDLabel

        positions = self.pea.get_positions()
        if not positions:
            self._show_toast("Aucune position a vendre")
            return

        content = MDBoxLayout(
            orientation="vertical", spacing=dp(8), padding=(dp(8), dp(4)),
            size_hint_y=None, height=dp(180))

        ticker_field = MDTextField(
            hint_text="Ticker de la position",
            mode="fill", size_hint_y=None, height=dp(48), font_size=sp(14))
        if ticker:
            ticker_field.text = ticker

        qty_field = MDTextField(
            hint_text="Quantite a vendre", mode="fill", input_filter="int",
            size_hint_y=None, height=dp(48), font_size=sp(14))

        price_field = MDTextField(
            hint_text="Prix de vente (EUR)", mode="fill", input_filter="float",
            size_hint_y=None, height=dp(48), font_size=sp(14))

        # Pre-remplir le prix actuel
        if self.current_result and ticker == self.current_ticker:
            price_field.text = f"{self.current_result.price:.2f}"

        # Afficher quantite dispo
        pos_label = MDLabel(
            text="", font_style="Caption", halign="center",
            theme_text_color="Custom", text_color=(0.4, 0.5, 0.6, 1),
            size_hint_y=None, height=dp(16))

        def _update_info(instance, value):
            t = value.strip()
            if t in positions:
                pos = positions[t]
                pos_label.text = f"Disponible: {pos['quantity']} x {pos['name']}  (PRU: {pos['pru']:.2f})"
            else:
                pos_label.text = ""

        ticker_field.bind(text=_update_info)
        if ticker and ticker in positions:
            pos = positions[ticker]
            pos_label.text = f"Disponible: {pos['quantity']} x {pos['name']}  (PRU: {pos['pru']:.2f})"

        content.add_widget(ticker_field)
        content.add_widget(pos_label)
        content.add_widget(qty_field)
        content.add_widget(price_field)

        dialog = MDDialog(
            title="Vente PEA",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="ANNULER", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(
                    text="VENDRE", md_bg_color=(0.7, 0.1, 0.1, 1),
                    on_release=lambda x: self._exec_pea_sell(
                        dialog, ticker_field.text, qty_field.text, price_field.text)),
            ])
        dialog.open()

    def _exec_pea_sell(self, dialog, ticker_raw, qty_raw, price_raw):
        try:
            ticker = ticker_raw.strip()
            qty = int(qty_raw)
            prix = float(price_raw)
        except (ValueError, TypeError):
            self._show_toast("Quantite/prix invalide")
            return

        result = self.pea.vendre(ticker, qty, prix)

        if result["success"]:
            dialog.dismiss()
            pnl = result.get("pnl", 0)
            sign = "+" if pnl >= 0 else ""
            self._show_toast(f"Vente x{qty} a {prix:.2f} | P&L: {sign}{pnl:.2f} EUR")
            self._refresh_pea_view()
        else:
            self._show_toast(result["error"])

    def on_stop(self):
        if self.monitor:
            self.monitor.stop()


if __name__ == "__main__":
    StockAnalyzerApp().run()
