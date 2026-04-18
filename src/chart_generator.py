"""
chart_generator.py - Graphiques optimises pour ecran mobile (Poco F7 / 1080x2400)
Format PORTRAIT, gros textes, lignes epaisses, haute resolution.
"""

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import os
import tempfile
from datetime import datetime

from analyzer import (
    compute_rsi, compute_macd, compute_bollinger_bands,
    compute_sma, compute_ema, compute_stochastic, compute_atr
)

# Theme AMOLED
BG = '#000000'
PANEL = '#0d1117'
GRID = '#1a1f2e'
TXT = '#f0f3f8'
GREEN = '#00e676'
RED = '#ff1744'
BLUE = '#448aff'
ORANGE = '#ffab00'
PURPLE = '#b388ff'
CYAN = '#18ffff'
YELLOW = '#ffea00'
DIM = '#546e7a'
GOLD = '#ffd740'
PINK = '#ff4081'
WHITE = '#ffffff'

# Taille mobile portrait (ratio ~9:16)
FIG_W = 6
FIG_H_SMALL = 5
FIG_H_MED = 6.5
FIG_H_TALL = 8
DPI = 220


def _style():
    plt.rcParams.update({
        'figure.facecolor': BG,
        'axes.facecolor': PANEL,
        'axes.edgecolor': GRID,
        'axes.labelcolor': TXT,
        'text.color': TXT,
        'xtick.color': DIM,
        'ytick.color': DIM,
        'grid.color': GRID,
        'grid.alpha': 0.25,
        'grid.linestyle': '-',
        'grid.linewidth': 0.5,
        'font.size': 13,
        'axes.titlesize': 16,
        'axes.labelsize': 13,
        'xtick.labelsize': 11,
        'ytick.labelsize': 11,
    })


def _save(fig, path):
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor=BG,
                edgecolor='none', pad_inches=0.05)
    plt.close(fig)
    return path


def _tmp(name):
    return os.path.join(tempfile.gettempdir(), f"sa_{name}.png")


def _draw_candles(ax, df, width=0.55):
    for i in range(len(df)):
        d = mdates.date2num(df.index[i])
        o, c = df['Open'].iloc[i], df['Close'].iloc[i]
        h, l = df['High'].iloc[i], df['Low'].iloc[i]
        color = GREEN if c >= o else RED
        ax.plot([d, d], [l, h], color=color, linewidth=1.0)
        body = abs(c - o) or 0.001
        rect = mpatches.FancyBboxPatch(
            (d - width/2, min(o, c)), width, body,
            boxstyle="round,pad=0.01", facecolor=color, edgecolor='none', alpha=0.9
        )
        ax.add_patch(rect)


def _format_dates(ax, short=False):
    if short:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=35, fontsize=10, ha='right')


def _legend(ax):
    ax.legend(loc='upper left', fontsize=10, facecolor=PANEL, edgecolor=GRID,
              labelcolor=TXT, framealpha=0.85, borderpad=0.4)


# ================================================================
# 1. PRIX + Chandeliers + MM + Bollinger
# ================================================================

def chart_prix(df, ticker, name, result=None):
    _style()
    fig, (ax, ax_vol) = plt.subplots(2, 1, figsize=(FIG_W, FIG_H_MED),
        gridspec_kw={'height_ratios': [4, 1]}, sharex=True)
    fig.subplots_adjust(hspace=0.03, left=0.14, right=0.96, top=0.92, bottom=0.08)

    _draw_candles(ax, df)
    close = df['Close']
    dates = df.index

    sma20 = compute_sma(close, 20)
    sma50 = compute_sma(close, 50)
    ax.plot(dates, sma20, color=BLUE, linewidth=2, label='MM20')
    ax.plot(dates, sma50, color=ORANGE, linewidth=2, label='MM50')

    upper, mid, lower = compute_bollinger_bands(close)
    ax.fill_between(dates, lower, upper, alpha=0.08, color=PURPLE)
    ax.plot(dates, upper, color=PURPLE, linewidth=0.8, alpha=0.5, linestyle='--')
    ax.plot(dates, lower, color=PURPLE, linewidth=0.8, alpha=0.5, linestyle='--')

    last = close.iloc[-1]
    ax.axhline(last, color=CYAN, linewidth=0.7, linestyle=':', alpha=0.4)
    ax.annotate(f' {last:.2f}', xy=(dates[-1], last),
                fontsize=14, fontweight='bold', color=CYAN)

    sig = ""
    if result:
        sig = f"\n{result.signal.value} ({result.score:+.0f})"
    ax.set_title(f"{name}  -  {last:.2f} EUR{sig}", fontweight='bold', fontsize=15, pad=6)
    _legend(ax)
    ax.grid(True)
    ax.set_ylabel('Prix (EUR)', fontsize=12)

    vol_colors = [GREEN if close.iloc[i] >= df['Open'].iloc[i] else RED for i in range(len(df))]
    ax_vol.bar(dates, df['Volume'], color=vol_colors, alpha=0.5, width=0.55)
    ax_vol.set_ylabel('Vol.', fontsize=10)
    ax_vol.grid(True)
    ax_vol.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, p: f'{x/1e6:.1f}M' if x >= 1e6 else f'{x/1e3:.0f}K'))
    _format_dates(ax_vol)

    return _save(fig, _tmp(f"prix_{ticker.replace('.','_')}"))


# ================================================================
# 2. RSI
# ================================================================

def chart_rsi(df, ticker, name):
    _style()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H_SMALL))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.90, bottom=0.10)

    dates = df.index
    rsi = compute_rsi(df['Close'])
    current = rsi.iloc[-1]

    ax.plot(dates, rsi, color=CYAN, linewidth=2.8, zorder=3)
    ax.fill_between(dates, rsi, 50, where=(rsi > 50), alpha=0.1, color=RED)
    ax.fill_between(dates, rsi, 50, where=(rsi < 50), alpha=0.1, color=GREEN)

    ax.axhline(80, color=RED, linestyle='--', linewidth=1.2, alpha=0.8)
    ax.axhline(70, color=RED, linestyle=':', linewidth=1, alpha=0.5)
    ax.axhline(50, color=DIM, linestyle='-', linewidth=0.6, alpha=0.3)
    ax.axhline(30, color=GREEN, linestyle=':', linewidth=1, alpha=0.5)
    ax.axhline(20, color=GREEN, linestyle='--', linewidth=1.2, alpha=0.8)

    ax.fill_between(dates, 70, 100, alpha=0.08, color=RED)
    ax.fill_between(dates, 0, 30, alpha=0.08, color=GREEN)

    ax.text(dates[1], 87, 'SURACHETE', fontsize=13, color=RED, alpha=0.7, fontweight='bold')
    ax.text(dates[1], 8, 'SURVENDU', fontsize=13, color=GREEN, alpha=0.7, fontweight='bold')

    rsi_color = RED if current > 70 else (GREEN if current < 30 else CYAN)
    ax.plot(dates[-1], current, 'o', color=rsi_color, markersize=10, zorder=4)
    ax.annotate(f'  {current:.1f}', xy=(dates[-1], current),
                fontsize=16, fontweight='bold', color=rsi_color, zorder=4)

    ax.set_title(f"RSI (14)  -  {name}", fontweight='bold', fontsize=15, pad=6)
    ax.set_ylim(0, 100)
    ax.set_ylabel('RSI', fontsize=12)
    ax.grid(True)
    _format_dates(ax)

    return _save(fig, _tmp(f"rsi_{ticker.replace('.','_')}"))


# ================================================================
# 3. MACD
# ================================================================

def chart_macd(df, ticker, name):
    _style()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H_SMALL))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.90, bottom=0.10)

    dates = df.index
    macd_line, signal_line, histogram = compute_macd(df['Close'])

    hist_colors = [GREEN if h >= 0 else RED for h in histogram]
    ax.bar(dates, histogram, color=hist_colors, alpha=0.35, width=0.55, label='Histogramme')
    ax.plot(dates, macd_line, color=BLUE, linewidth=2.5, label='MACD')
    ax.plot(dates, signal_line, color=ORANGE, linewidth=2.5, label='Signal')
    ax.axhline(0, color=DIM, linewidth=0.6)

    for i in range(max(len(dates)-20, 1), len(dates)):
        if i > 0:
            prev_diff = macd_line.iloc[i-1] - signal_line.iloc[i-1]
            curr_diff = macd_line.iloc[i] - signal_line.iloc[i]
            if prev_diff < 0 and curr_diff > 0:
                ax.annotate('ACHAT', xy=(dates[i], macd_line.iloc[i]),
                           fontsize=12, fontweight='bold', color=GREEN,
                           xytext=(0, 20), textcoords='offset points',
                           arrowprops=dict(arrowstyle='->', color=GREEN, lw=2))
            elif prev_diff > 0 and curr_diff < 0:
                ax.annotate('VENTE', xy=(dates[i], macd_line.iloc[i]),
                           fontsize=12, fontweight='bold', color=RED,
                           xytext=(0, -25), textcoords='offset points',
                           arrowprops=dict(arrowstyle='->', color=RED, lw=2))

    ax.set_title(f"MACD  -  {name}", fontweight='bold', fontsize=15, pad=6)
    ax.set_ylabel('MACD', fontsize=12)
    _legend(ax)
    ax.grid(True)
    _format_dates(ax)

    return _save(fig, _tmp(f"macd_{ticker.replace('.','_')}"))


# ================================================================
# 4. JOUR J - Temps reel
# ================================================================

def chart_today(df_today, ticker, name):
    _style()
    fig, (ax, ax_vol) = plt.subplots(2, 1, figsize=(FIG_W, FIG_H_MED),
        gridspec_kw={'height_ratios': [4, 1]}, sharex=True)
    fig.subplots_adjust(hspace=0.03, left=0.14, right=0.96, top=0.90, bottom=0.08)

    dates = df_today.index
    close = df_today['Close']
    volume = df_today['Volume']

    typical_price = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
    cum_vol = volume.cumsum()
    vwap = (typical_price * volume).cumsum() / cum_vol.replace(0, np.nan)

    open_price = df_today['Open'].iloc[0]
    last_price = close.iloc[-1]
    change = last_price - open_price
    change_pct = (change / open_price * 100) if open_price != 0 else 0

    up = last_price >= open_price
    main_color = GREEN if up else RED

    ax.plot(dates, close, color=main_color, linewidth=2.8, zorder=3)
    ax.fill_between(dates, close, open_price, alpha=0.1, color=main_color)

    ax.plot(dates, vwap, color=PURPLE, linewidth=1.8, linestyle='--', alpha=0.8, label='VWAP')

    ax.axhline(open_price, color=DIM, linewidth=1, linestyle=':', alpha=0.5)
    ax.text(dates[0], open_price, f' Ouv: {open_price:.2f}', fontsize=11, color=DIM, va='bottom')

    ax.plot(dates[-1], last_price, 'o', color=main_color, markersize=12, zorder=5)
    ax.plot(dates[-1], last_price, 'o', color=main_color, markersize=20, alpha=0.3, zorder=4)
    sign = "+" if change >= 0 else ""
    ax.annotate(f' {last_price:.2f}\n ({sign}{change_pct:.2f}%)',
                xy=(dates[-1], last_price), fontsize=14, fontweight='bold',
                color=main_color, zorder=5)

    day_high = df_today['High'].max()
    day_low = df_today['Low'].min()
    ax.axhline(day_high, color=GREEN, linewidth=0.6, linestyle=':', alpha=0.3)
    ax.axhline(day_low, color=RED, linewidth=0.6, linestyle=':', alpha=0.3)

    now_str = datetime.now().strftime('%H:%M')
    ax.set_title(f"{name}  -  JOUR J  {now_str}\n"
                 f"H: {day_high:.2f}  B: {day_low:.2f}  {sign}{change:.2f} ({sign}{change_pct:.1f}%)",
                 fontweight='bold', fontsize=14, pad=4)
    _legend(ax)
    ax.grid(True)
    ax.set_ylabel('Prix (EUR)', fontsize=12)

    vol_colors = [GREEN if close.iloc[i] >= df_today['Open'].iloc[i] else RED for i in range(len(df_today))]
    ax_vol.bar(dates, volume, color=vol_colors, alpha=0.5, width=0.003)
    ax_vol.set_ylabel('Vol.', fontsize=10)
    ax_vol.grid(True)
    ax_vol.xaxis.set_major_formatter(mdates.DateFormatter('%Hh%M'))
    ax_vol.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    plt.setp(ax_vol.get_xticklabels(), rotation=35, fontsize=10, ha='right')

    return _save(fig, _tmp(f"today_{ticker.replace('.','_')}"))


# ================================================================
# 5. Intraday 5 jours
# ================================================================

def chart_intraday(df_intra, ticker, name):
    _style()
    fig, (ax, ax_vol) = plt.subplots(2, 1, figsize=(FIG_W, FIG_H_MED),
        gridspec_kw={'height_ratios': [4, 1]}, sharex=True)
    fig.subplots_adjust(hspace=0.03, left=0.14, right=0.96, top=0.92, bottom=0.08)

    dates = df_intra.index
    close = df_intra['Close']

    ax.plot(dates, close, color=BLUE, linewidth=2.8)
    ax.fill_between(dates, close, close.min(), alpha=0.06, color=BLUE)

    ema9 = compute_ema(close, 9)
    ema21 = compute_ema(close, 21)
    ax.plot(dates, ema9, color=ORANGE, linewidth=1.5, alpha=0.8, label='EMA9')
    ax.plot(dates, ema21, color=PURPLE, linewidth=1.5, alpha=0.8, label='EMA21')

    last_price = close.iloc[-1]
    ax.axhline(last_price, color=CYAN, linewidth=0.8, linestyle=':', alpha=0.4)
    ax.plot(dates[-1], last_price, 'o', color=CYAN, markersize=10, zorder=4)
    ax.annotate(f' {last_price:.2f} EUR', xy=(dates[-1], last_price),
                fontsize=14, fontweight='bold', color=CYAN)

    ax.set_title(f"{name}  -  5 Jours", fontweight='bold', fontsize=15, pad=6)
    _legend(ax)
    ax.grid(True)
    ax.set_ylabel('Prix (EUR)', fontsize=12)

    vol_colors = [GREEN if close.iloc[i] >= df_intra['Open'].iloc[i] else RED for i in range(len(df_intra))]
    ax_vol.bar(dates, df_intra['Volume'], color=vol_colors, alpha=0.5, width=0.02)
    ax_vol.set_ylabel('Vol.', fontsize=10)
    ax_vol.grid(True)
    _format_dates(ax_vol, short=True)

    return _save(fig, _tmp(f"intra_{ticker.replace('.','_')}"))


# ================================================================
# 6. 1 An
# ================================================================

def chart_annuel(df_1y, ticker, name):
    _style()
    fig, (ax, ax_vol) = plt.subplots(2, 1, figsize=(FIG_W, FIG_H_SMALL + 1),
                                      gridspec_kw={'height_ratios': [4, 1]}, sharex=True)
    fig.subplots_adjust(left=0.14, right=0.96, top=0.90, bottom=0.12, hspace=0.05)

    dates = df_1y.index
    close = df_1y['Close']
    opens = df_1y['Open']
    highs = df_1y['High']
    lows = df_1y['Low']

    # Chandeliers
    up = close >= opens
    down = ~up
    bar_width = max(0.6, min(2.0, 250 / len(dates)))

    ax.bar(dates[up], (close[up] - opens[up]), bottom=opens[up], width=bar_width, color=GREEN, alpha=0.85)
    ax.bar(dates[up], (highs[up] - close[up]), bottom=close[up], width=bar_width * 0.15, color=GREEN, alpha=0.6)
    ax.bar(dates[up], (opens[up] - lows[up]), bottom=lows[up], width=bar_width * 0.15, color=GREEN, alpha=0.6)

    ax.bar(dates[down], (opens[down] - close[down]), bottom=close[down], width=bar_width, color=RED, alpha=0.85)
    ax.bar(dates[down], (highs[down] - opens[down]), bottom=opens[down], width=bar_width * 0.15, color=RED, alpha=0.6)
    ax.bar(dates[down], (close[down] - lows[down]), bottom=lows[down], width=bar_width * 0.15, color=RED, alpha=0.6)

    sma50 = compute_sma(close, 50)
    sma200 = compute_sma(close, 200)
    ax.plot(dates, sma50, color=ORANGE, linewidth=1.8, alpha=0.8, label='MM50')
    if sma200.notna().sum() > 10:
        ax.plot(dates, sma200, color=RED, linewidth=1.8, alpha=0.8, label='MM200')

    ax.plot(dates[-1], close.iloc[-1], 'o', color=CYAN, markersize=10, zorder=4)
    ax.annotate(f' {close.iloc[-1]:.2f}', xy=(dates[-1], close.iloc[-1]),
                fontsize=14, fontweight='bold', color=CYAN)

    if len(close) > 1:
        perf = ((close.iloc[-1] / close.iloc[0]) - 1) * 100
        perf_color = GREEN if perf >= 0 else RED
        ax.text(0.5, 0.97, f"Performance 1 an: {perf:+.1f}%", transform=ax.transAxes,
                fontsize=14, fontweight='bold', color=perf_color, ha='center', va='top')

    ax.set_title(f"{name}  -  1 An (Chandeliers)", fontweight='bold', fontsize=15, pad=6)
    _legend(ax)
    ax.grid(True)
    ax.set_ylabel('Prix', fontsize=12)

    # Volume
    vol_colors = [GREEN if c >= o else RED for c, o in zip(close, opens)]
    ax_vol.bar(dates, df_1y['Volume'], width=bar_width, color=vol_colors, alpha=0.5)
    ax_vol.set_ylabel('Vol', fontsize=10)
    ax_vol.grid(True, alpha=0.3)

    ax_vol.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
    ax_vol.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax_vol.get_xticklabels(), rotation=35, fontsize=10, ha='right')

    return _save(fig, _tmp(f"1y_{ticker.replace('.','_')}"))


# ================================================================
# 7. PREDICTION FUTURE IA
# ================================================================

def chart_prediction(df, prediction, ticker, name, result=None):
    _style()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H_TALL + 1))
    fig.subplots_adjust(left=0.15, right=0.85, top=0.88, bottom=0.08)

    close = df['Close']
    price = close.iloc[-1]

    # Historique
    hist_days = min(30, len(close) - 1)
    hist_close = close.iloc[-hist_days:]
    hist_x = list(range(-hist_days + 1, 1))

    # Future
    pred_x = list(range(1, len(prediction.days) + 1))
    p = prediction

    # ---- LIGNES ----

    # Historique
    ax.plot(hist_x, hist_close.values, color=BLUE, linewidth=2.5, label='Historique', zorder=3)

    # Cone 95%
    ax.fill_between(pred_x, p.prix_tres_bas, p.prix_tres_haut,
                    alpha=0.06, color=PURPLE, label='Zone 95%')
    # Cone 68%
    ax.fill_between(pred_x, p.prix_bas, p.prix_haut,
                    alpha=0.12, color=CYAN, label='Zone 68%')

    # Scenario HAUT (optimiste)
    full_x = [0] + pred_x
    full_opt = [price] + list(p.scenario_haut)
    ax.plot(full_x, full_opt, color=GREEN, linewidth=2, linestyle='--',
            label='Scenario haut', zorder=4, alpha=0.7)

    # Scenario BAS (pessimiste)
    full_pes = [price] + list(p.scenario_bas)
    ax.plot(full_x, full_pes, color=RED, linewidth=2, linestyle='--',
            label='Scenario bas', zorder=4, alpha=0.7)

    # CHEMIN IA PRINCIPAL (ligne solide doree)
    full_y = [price] + list(p.prix_moyen)
    ax.plot(full_x, full_y, color=GOLD, linewidth=3.5, solid_capstyle='round',
            label='Chemin IA', zorder=6)
    ax.plot(full_x, full_y, color=GOLD, linewidth=8, alpha=0.12,
            solid_capstyle='round', zorder=5)

    # Points intermediaires discrets
    for i, (px, py) in enumerate(zip(pred_x, p.prix_moyen)):
        if px in (5, 10, 15, 20):
            ax.plot(px, py, 'o', color=GOLD, markersize=5, zorder=6, alpha=0.7)

    # Point J0
    ax.plot(0, price, 'o', color=GOLD, markersize=12, zorder=7)
    ax.axhline(price, color=DIM, linewidth=0.5, linestyle=':', alpha=0.25)
    ax.axvline(0, color=GOLD, linewidth=1, linestyle='-', alpha=0.2)

    # ---- ANNOTATIONS INTELLIGENTES (marge droite) ----
    # On place les labels a DROITE du graphique, empiles verticalement
    # pour ne jamais se chevaucher

    # Calcul du range Y visible
    all_prices = list(hist_close.values) + p.prix_moyen + p.scenario_haut + p.scenario_bas
    y_min = min(all_prices) * 0.92
    y_max = max(all_prices) * 1.08
    y_range = y_max - y_min
    ax.set_ylim(y_min, y_max)

    # Label J0 - a gauche du graphique
    ax.annotate(f'{price:.2f}\nAUJ.',
                xy=(0, price), xytext=(-65, 0), textcoords='offset points',
                fontsize=10, fontweight='bold', color=GOLD, ha='center', va='center', zorder=8,
                bbox=dict(boxstyle='round,pad=0.25', facecolor=PANEL, edgecolor=GOLD, alpha=0.9),
                arrowprops=dict(arrowstyle='->', color=GOLD, lw=1.2))

    # Collecter tous les marqueurs a droite et les empiler sans chevauchement
    right_labels = []

    # J+5, J+10, J+20
    for d, obj, var, label in [
        (5, p.objectif_5j, p.variation_5j_pct, "J+5"),
        (10, p.objectif_10j, p.variation_10j_pct, "J+10"),
        (20, p.objectif_20j, p.variation_20j_pct, "J+20"),
    ]:
        if d <= len(pred_x):
            c = GREEN if var >= 0 else RED
            sign = "+" if var >= 0 else ""
            ax.plot(d, obj, 's', color=c, markersize=10, zorder=7,
                    markeredgecolor=WHITE, markeredgewidth=1)
            right_labels.append({
                'x': d, 'y': obj, 'color': c,
                'text': f'{label}: {obj:.2f}\n({sign}{var:.1f}%)',
            })

    # PIC
    pic_var = ((p.pic_prix / price) - 1) * 100
    ax.plot(p.pic_jour, p.pic_prix, '^', color=GREEN, markersize=13, zorder=8,
            markeredgecolor=WHITE, markeredgewidth=1.2)
    right_labels.append({
        'x': p.pic_jour, 'y': p.pic_prix, 'color': GREEN,
        'text': f'PIC J+{p.pic_jour}: {p.pic_prix:.2f}\n(+{pic_var:.1f}%)',
    })

    # CREUX
    creux_var = ((p.creux_prix / price) - 1) * 100
    ax.plot(p.creux_jour, p.creux_prix, 'v', color=RED, markersize=13, zorder=8,
            markeredgecolor=WHITE, markeredgewidth=1.2)
    right_labels.append({
        'x': p.creux_jour, 'y': p.creux_prix, 'color': RED,
        'text': f'CREUX J+{p.creux_jour}: {p.creux_prix:.2f}\n({creux_var:+.1f}%)',
    })

    # Trier par prix descendant pour empiler de haut en bas
    right_labels.sort(key=lambda l: l['y'], reverse=True)

    # Espacement minimum entre labels (en unites Y)
    min_gap = y_range * 0.075
    # Ajuster les positions Y pour eviter chevauchement
    placed_y = []
    for lbl in right_labels:
        target_y = lbl['y']
        for py in placed_y:
            if abs(target_y - py) < min_gap:
                # Pousser vers le haut ou le bas
                if target_y >= py:
                    target_y = py + min_gap
                else:
                    target_y = py - min_gap
        placed_y.append(target_y)
        lbl['placed_y'] = target_y

    # Dessiner les annotations a droite du graphique
    x_right = max(pred_x) + 0.5
    for lbl in right_labels:
        ax.annotate(lbl['text'],
                   xy=(lbl['x'], lbl['y']),
                   xytext=(x_right, lbl['placed_y']),
                   fontsize=9, fontweight='bold', color=lbl['color'],
                   ha='left', va='center', zorder=9,
                   bbox=dict(boxstyle='round,pad=0.2', facecolor=PANEL,
                             edgecolor=lbl['color'], alpha=0.9, linewidth=1),
                   arrowprops=dict(arrowstyle='->', color=lbl['color'],
                                   lw=1, connectionstyle='arc3,rad=0.15'))

    # ---- TITRE ET VERDICT ----
    tend_colors = {"haussiere": GREEN, "baissiere": RED, "laterale": ORANGE}
    tend_c = tend_colors.get(p.tendance, DIM)
    tend_text = p.tendance.upper()
    score_text = f"  |  Score IA: {result.score:+.0f}" if result else ""

    ax.set_title(f"PREDICTION IA  -  {name}\n"
                 f"Tendance: {tend_text}  |  Confiance: {p.confiance:.0f}%{score_text}",
                 fontweight='bold', fontsize=14, color=TXT, pad=8)

    verdict = "HAUSSE ATTENDUE" if p.tendance == "haussiere" else (
              "BAISSE ATTENDUE" if p.tendance == "baissiere" else "NEUTRE / LATERAL")
    ax.text(0.02, 0.02, f" {verdict} ", transform=ax.transAxes,
            fontsize=12, fontweight='bold', color=tend_c, ha='left', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=PANEL, edgecolor=tend_c, alpha=0.85))

    ax.set_xlabel('Jours (0 = aujourd\'hui)', fontsize=11)
    ax.set_ylabel('Prix (EUR)', fontsize=11)
    ax.legend(loc='upper left', fontsize=8.5, facecolor=PANEL, edgecolor=GRID,
              labelcolor=TXT, framealpha=0.85, borderpad=0.3)
    ax.grid(True)

    return _save(fig, _tmp(f"pred_{ticker.replace('.','_')}"))


# ================================================================
# 8. Score IA - Carte d'analyse
# ================================================================

def chart_analyse(result):
    _style()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H_TALL))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.96, bottom=0.02)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    r = result
    d = r.details

    sig_colors = {"ACHAT FORT": GREEN, "ACHAT": GREEN, "NEUTRE": ORANGE, "VENTE": RED, "VENTE FORTE": RED}
    sig_c = sig_colors.get(r.signal.value, TXT)

    # Banniere signal
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.3, 9.0), 9.4, 0.85, boxstyle="round,pad=0.12",
        facecolor=sig_c, alpha=0.18, edgecolor=sig_c, linewidth=2))
    ax.text(5, 9.42, r.signal.value, fontsize=30, fontweight='bold', color=sig_c, ha='center', va='center')

    # Score + Confiance + Prix
    ax.text(5, 8.55, f"Score: {r.score:+.1f}/100   Confiance: {r.confidence:.0f}%",
            fontsize=14, ha='center', color=TXT, fontweight='bold')
    ax.text(5, 8.15, f"{r.price:.2f} EUR",
            fontsize=13, ha='center', color=CYAN, fontweight='bold')

    # Barre score globale
    bar_x, bar_w, bar_h = 0.8, 8.4, 0.30
    ax.add_patch(mpatches.FancyBboxPatch(
        (bar_x, 7.55), bar_w, bar_h, boxstyle="round,pad=0.03",
        facecolor=GRID, alpha=0.6))
    score_ratio = max(0.01, (r.score + 100) / 200)
    fill_color = GREEN if r.score > 10 else (RED if r.score < -10 else ORANGE)
    ax.add_patch(mpatches.FancyBboxPatch(
        (bar_x, 7.55), bar_w * score_ratio, bar_h, boxstyle="round,pad=0.03",
        facecolor=fill_color, alpha=0.8))
    ax.text(bar_x + 0.1, 7.40, '-100', fontsize=9, color=RED, ha='left')
    ax.text(bar_x + bar_w/2, 7.40, '0', fontsize=9, color=DIM, ha='center')
    ax.text(bar_x + bar_w - 0.1, 7.40, '+100', fontsize=9, color=GREEN, ha='right')

    # Separateur
    ax.plot([0.5, 9.5], [7.15, 7.15], color=GRID, linewidth=1)
    ax.text(5, 7.25, '8 INDICATEURS TECHNIQUES', fontsize=10, ha='center', color=DIM)

    # 8 indicateurs
    indicators = [
        ("MACD", d['macd']['score'], 35, d['macd']['desc']),
        ("RSI", d['rsi']['score'], 50, f"RSI {d['rsi']['value']:.0f} - {d['rsi']['desc']}"),
        ("Moy. Mob.", d['moyennes_mobiles']['score'], 36, d['moyennes_mobiles']['desc']),
        ("Bollinger", d['bollinger']['score'], 25, d['bollinger']['desc']),
        ("Stochast.", d['stochastique']['score'], 20, d['stochastique']['desc']),
        ("Tendance", d['tendance']['score'], 15, d['tendance']['desc']),
        ("Momentum", d['momentum']['score'], 13, d['momentum']['desc']),
        ("Volume", d['volume']['score'], 8, d['volume']['desc']),
    ]

    y = 6.75
    bar_w_ind = 3.5
    for label, score, max_s, desc in indicators:
        # Nom
        ax.text(0.15, y, label, fontsize=12, fontweight='bold', va='center')

        # Barre fond
        bx, bh = 2.0, 0.28
        ax.add_patch(mpatches.FancyBboxPatch(
            (bx, y - bh/2), bar_w_ind, bh, boxstyle="round,pad=0.03",
            facecolor=GRID, alpha=0.5))

        # Barre remplie
        if max_s > 0:
            ratio = max(0.02, min(1, (score + max_s) / (2 * max_s)))
        else:
            ratio = 0.5
        fill_c = GREEN if score > 2 else (RED if score < -2 else ORANGE)
        ax.add_patch(mpatches.FancyBboxPatch(
            (bx, y - bh/2), bar_w_ind * ratio, bh, boxstyle="round,pad=0.03",
            facecolor=fill_c, alpha=0.75))

        # Score
        sc = GREEN if score > 0 else (RED if score < 0 else ORANGE)
        ax.text(5.7, y, f"{score:+.0f}", fontsize=12, fontweight='bold', color=sc, va='center')

        # Description (tronquee)
        ax.text(6.3, y, desc[:38], fontsize=8.5, color=DIM, va='center')
        y -= 0.58

    # Separateur
    y -= 0.1
    ax.plot([0.5, 9.5], [y + 0.15, y + 0.15], color=GRID, linewidth=1)

    # Prediction
    if r.prediction:
        p = r.prediction
        ax.text(5, y, 'PREDICTION FUTURE IA', fontsize=11, ha='center', color=GOLD, fontweight='bold')
        y -= 0.45

        tend_c = GREEN if p.tendance == "haussiere" else (RED if p.tendance == "baissiere" else ORANGE)
        ax.text(5, y, f"Tendance {p.tendance.upper()}  -  Confiance {p.confiance:.0f}%",
                fontsize=11, ha='center', color=tend_c, fontweight='bold')
        y -= 0.55

        for lbl, obj, var in [
            ("J+5", p.objectif_5j, p.variation_5j_pct),
            ("J+10", p.objectif_10j, p.variation_10j_pct),
            ("J+20", p.objectif_20j, p.variation_20j_pct)
        ]:
            c = GREEN if var >= 0 else RED
            sign = "+" if var >= 0 else ""
            ax.text(1.5, y, lbl, fontsize=13, fontweight='bold', color=TXT, va='center')
            ax.text(4, y, f"{obj:.2f} EUR", fontsize=13, fontweight='bold', color=c, va='center')
            ax.text(7, y, f"({sign}{var:.1f}%)", fontsize=13, fontweight='bold', color=c, va='center')
            y -= 0.48

    # Support / Resistance
    supports = d.get('supports', [])
    resistances = d.get('resistances', [])
    if supports or resistances:
        y -= 0.15
        ax.plot([0.5, 9.5], [y + 0.15, y + 0.15], color=GRID, linewidth=1)
        s_text = "S: " + " / ".join(f"{s:.2f}" for s in supports[:3]) if supports else "S: ---"
        r_text = "R: " + " / ".join(f"{r:.2f}" for r in resistances[:3]) if resistances else "R: ---"
        ax.text(2.5, y, s_text, fontsize=10, color=GREEN, va='center', ha='center')
        ax.text(7.5, y, r_text, fontsize=10, color=RED, va='center', ha='center')

    # Resume
    ax.text(5, 0.25, r.summary[:90], fontsize=9, ha='center', color=DIM, style='italic')

    return _save(fig, _tmp("analyse"))


# ================================================================
# 9. SCALPING 5 MIN - Prediction intraday
# ================================================================

def chart_scalping(intraday_pred, ticker, name, current_price):
    """Graphique de prediction scalping 5 min avec cone de volatilite."""
    _style()
    fig = plt.figure(figsize=(FIG_W, FIG_H_TALL + 2))

    # Layout: chart en haut (75%), info en bas (25%)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.08)
    ax = fig.add_subplot(gs[0])
    ax_info = fig.add_subplot(gs[1])
    ax_info.axis('off')

    fig.subplots_adjust(left=0.13, right=0.87, top=0.92, bottom=0.04)

    p = intraday_pred
    minutes = p.intervals       # [5, 10, 15, 20, 25, 30]
    x = [0] + minutes
    y_pred = [current_price] + p.prix_predit
    y_haut = [current_price] + p.prix_haut
    y_bas = [current_price] + p.prix_bas
    y_ext_h = [current_price] + p.prix_extreme_haut
    y_ext_b = [current_price] + p.prix_extreme_bas

    # Cone 95%
    ax.fill_between(x, y_ext_b, y_ext_h, alpha=0.06, color=PURPLE, label='Zone 95%')
    # Cone 68%
    ax.fill_between(x, y_bas, y_haut, alpha=0.15, color=CYAN, label='Zone 68%')

    # Chemin IA principal
    dir_color = GREEN if p.direction == "HAUSSE" else (RED if p.direction == "BAISSE" else ORANGE)
    ax.plot(x, y_pred, color=dir_color, linewidth=3.5, solid_capstyle='round',
            label='Prediction IA', zorder=6)
    ax.plot(x, y_pred, color=dir_color, linewidth=10, alpha=0.1, solid_capstyle='round', zorder=5)

    # Lignes hautes/basses
    ax.plot(x, y_haut, color=GREEN, linewidth=1.2, linestyle='--', alpha=0.5, zorder=4)
    ax.plot(x, y_bas, color=RED, linewidth=1.2, linestyle='--', alpha=0.5, zorder=4)

    # Point actuel
    ax.plot(0, current_price, 'o', color=GOLD, markersize=14, zorder=8)
    ax.axhline(current_price, color=DIM, linewidth=0.6, linestyle=':', alpha=0.3)
    ax.annotate(f'{current_price:.2f}',
                xy=(0, current_price), xytext=(-45, 0), textcoords='offset points',
                fontsize=11, fontweight='bold', color=GOLD, ha='center', va='center', zorder=9,
                bbox=dict(boxstyle='round,pad=0.2', facecolor=PANEL, edgecolor=GOLD, alpha=0.9))

    # Points aux intervalles cles
    for i, m in enumerate(minutes):
        c = GREEN if p.prix_predit[i] >= current_price else RED
        ax.plot(m, p.prix_predit[i], 's', color=c, markersize=7, zorder=7,
                markeredgecolor=WHITE, markeredgewidth=0.8)

    # Annotations a droite du graphique, empilees sans chevauchement
    all_y = list(y_pred) + [p.stop_loss, p.take_profit]
    y_min_chart = min(all_y) * 0.998
    y_max_chart = max(all_y) * 1.002
    y_range = y_max_chart - y_min_chart

    annot_items = [
        (5, p.objectif_5min, p.variation_5min_pct, "5min"),
        (15, p.objectif_15min, p.variation_15min_pct, "15min"),
        (30, p.objectif_30min, p.variation_30min_pct, "30min"),
    ]
    # Sort by Y descending to stack from top
    annot_items.sort(key=lambda a: a[1], reverse=True)
    min_gap = y_range * 0.12
    placed = []
    for m_val, obj, var, lbl in annot_items:
        c = GREEN if var >= 0 else RED
        sign = "+" if var >= 0 else ""
        target_y = obj
        for py in placed:
            if abs(target_y - py) < min_gap:
                target_y = py - min_gap if target_y < py else py + min_gap
        placed.append(target_y)
        ax.annotate(f'{lbl}: {obj:.2f}\n({sign}{var:.3f}%)',
                    xy=(m_val, obj), xytext=(32, 0),
                    xycoords=('data', 'data'), textcoords='offset points',
                    fontsize=9, fontweight='bold', color=c, ha='left', va='center', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor=PANEL, edgecolor=c, alpha=0.92),
                    arrowprops=dict(arrowstyle='->', color=c, lw=1, connectionstyle='arc3,rad=0.1'))

    # Stop-Loss et Take-Profit
    ax.axhline(p.stop_loss, color=RED, linewidth=1.5, linestyle='--', alpha=0.6)
    ax.axhline(p.take_profit, color=GREEN, linewidth=1.5, linestyle='--', alpha=0.6)
    ax.text(31.5, p.stop_loss, f'Stop: {p.stop_loss:.2f}', fontsize=8.5,
            fontweight='bold', color=RED, va='center',
            bbox=dict(boxstyle='round,pad=0.15', facecolor=PANEL, edgecolor=RED, alpha=0.8))
    ax.text(31.5, p.take_profit, f'Obj.: {p.take_profit:.2f}', fontsize=8.5,
            fontweight='bold', color=GREEN, va='center',
            bbox=dict(boxstyle='round,pad=0.15', facecolor=PANEL, edgecolor=GREEN, alpha=0.8))

    # Titre
    sig_c = GREEN if p.signal_scalping == "ACHAT IMMEDIAT" else (RED if p.signal_scalping == "VENTE IMMEDIATE" else ORANGE)
    ax.set_title(f"SCALPING 5 MIN  -  {name}\n"
                 f"Signal: {p.signal_scalping}  |  {p.direction}  |  "
                 f"Confiance: {p.confiance:.0f}%",
                 fontweight='bold', fontsize=13, color=TXT, pad=8)

    ax.set_xlabel('Minutes', fontsize=11)
    ax.set_ylabel('Prix (EUR)', fontsize=11)
    ax.set_xticks([0, 5, 10, 15, 20, 25, 30])
    ax.legend(loc='upper left', fontsize=8.5, facecolor=PANEL, edgecolor=GRID,
              labelcolor=TXT, framealpha=0.85)
    ax.grid(True)

    # === Panneau info en bas ===
    # Grand signal central
    ax_info.text(0.5, 0.82, f" {p.signal_scalping} ", transform=ax_info.transAxes,
                 fontsize=26, fontweight='bold', color=sig_c, ha='center', va='center',
                 bbox=dict(boxstyle='round,pad=0.35', facecolor=PANEL,
                           edgecolor=sig_c, alpha=0.95, linewidth=2.5))

    # Raisons en 2 colonnes
    n_raisons = len(p.raisons)
    mid = (n_raisons + 1) // 2
    col1 = p.raisons[:mid]
    col2 = p.raisons[mid:6]

    for i, r in enumerate(col1):
        ax_info.text(0.02, 0.50 - i * 0.14, f"  {r}",
                     transform=ax_info.transAxes, fontsize=7.5, color=DIM, va='top')
    for i, r in enumerate(col2):
        ax_info.text(0.52, 0.50 - i * 0.14, f"  {r}",
                     transform=ax_info.transAxes, fontsize=7.5, color=DIM, va='top')

    return _save(fig, _tmp(f"scalp_{ticker.replace('.','_')}"))

