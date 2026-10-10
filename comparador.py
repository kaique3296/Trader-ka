#!/usr/bin/env python3
"""Comparação experimental do robô V4 x V5; nunca envia ordens reais."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from robo import backtest, fetch_klines, save_json

HISTORICAL_DAYS = 365
RECENT_DAYS = 90
REFRESH_DAYS = 7


def comparison_from_candles(candles):
    """Mesmo histórico, capital, custos e janelas para as duas estratégias."""
    if len(candles) < 600:
        raise ValueError('Comparação histórica exige pelo menos 600 candles completos de 4h.')
    cutoff = max(0, len(candles) - RECENT_DAYS * 6)
    windows = {'ultimo_ano': 0, 'ultimos_90_dias': cutoff}
    sections = {}
    for label, start in windows.items():
        summaries = {}
        for name in ('v4', 'v5'):
            summary, _, _ = backtest(candles, strategy=name, start_at_index=start)
            summaries[name] = summary
        a = summaries['v4']; b = summaries['v5']
        if a['start_utc'] != b['start_utc'] or a['end_utc'] != b['end_utc']:
            raise RuntimeError('Janelas incompatíveis; comparação interrompida.')
        sections[label] = {'start_utc': a['start_utc'], 'end_utc': a['end_utc'],
                           'candles': a['candles'], 'v4': a, 'v5': b}
    return {
        'kind': 'BACKTEST_COMPARATIVO_EXPERIMENTAL',
        'dataset_label': 'BINANCE_PUBLICO_BTCBRL_A_VERIFICAR',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'market': 'BTCBRL_SPOT_4H', 'initial_brl_each': 1000.0,
        'source': 'Binance Spot API candles completos BTCBRL 4h',
        'windows': sections,
        'caveat': 'Simulações históricas, não validação independente, não representam promessa de lucro.',
    }


def generate_if_due(dest: Path, *, now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    if dest.is_file():
        try:
            old = json.loads(dest.read_text(encoding='utf-8'))
            dt = datetime.fromisoformat(old['generated_at_utc'])
            if dt.tzinfo and dt > now - timedelta(days=REFRESH_DAYS) and old.get('kind') == 'BACKTEST_COMPARATIVO_EXPERIMENTAL':
                return False
        except (OSError, ValueError, KeyError, TypeError):
            pass
    candles = fetch_klines(days=HISTORICAL_DAYS)
    result = comparison_from_candles(candles)
    save_json(dest, result)
    return True
