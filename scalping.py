#!/usr/bin/env python3
"""V6: pesquisa de scalping 1m BTC/BRL, backtest exclusivamente virtual.

Não executa operações reais nem se autodenomina serviço de scalping contínuo.
A execução horária no GitHub é utilizada apenas para atualizar relatórios retrospectivos.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from robo import api_request, max_drawdown, save_json


@dataclass(frozen=True)
class MicroConfig:
    initial_brl: float = 1000.0
    position_brl: float = 150.0
    position_fraction: float = 0.15
    fee_per_side: float = 0.0015  # premissa conservadora para ordem taker fiat BTC/BRL
    slippage_per_side: float = 0.0007  # inclui atrito de execução estimado; NÃO spread medido
    target_pct: float = 0.010
    stop_pct: float = 0.006
    max_hold_bars: int = 20
    cooldown_bars: int = 5
    max_trades_per_day: int = 10
    max_losses_in_day: int = 3
    max_realized_loss_day_brl: float = 15.0
    max_equity_drawdown: float = 0.06


def validate_candles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    needed = ('time', 'open', 'high', 'low', 'close', 'volume')
    if not set(needed).issubset(df.columns):
        raise ValueError('Dados de 1 minuto precisam de time/open/high/low/close/volume.')
    df['time'] = pd.to_datetime(df['time'], utc=True)
    for name in needed[1:]:
        df[name] = pd.to_numeric(df[name], errors='raise')
    if df[list(needed)].isna().any().any():
        raise ValueError('Dados de 1 minuto possuem valores ausentes.')
    if (df[['open','high','low','close']] <= 0).any().any() or (df['volume'] < 0).any():
        raise ValueError('Preços ou volume inválidos.')
    if (df['high'] < df[['open','close','low']].max(axis=1)).any() or (df['low'] > df[['open','close','high']].min(axis=1)).any():
        raise ValueError('Candles inconsistentes.')
    if not df['time'].is_monotonic_increasing or df['time'].duplicated().any():
        raise ValueError('Candles fora de ordem ou duplicados.')
    if len(df) < 150 or (df['time'].diff().dropna() != pd.Timedelta(minutes=1)).any():
        raise ValueError('São necessários pelo menos 150 candles de 1 minuto consecutivos.')
    return df.reset_index(drop=True)


def fetch_minute_candles(days: int = 14, *, now_ms: int | None = None) -> pd.DataFrame:
    """Obtém APENAS candles fechados. Consulta endpoint público, sem chave/ordem."""
    if not (2 <= days <= 30):
        raise ValueError('Use entre 2 e 30 dias de histórico de 1 minuto.')
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    cursor = now_ms - days * 86400000
    end_ms = now_ms - 60000   # não processa o minuto corrente
    records = []
    while cursor <= end_ms:
        batch = api_request('/api/v3/klines', {
            'symbol': 'BTCBRL', 'interval': '1m', 'startTime': cursor,
            'endTime': end_ms, 'limit': 1000,
        })
        if not batch:
            raise RuntimeError('Binance não retornou a sequência de candles de 1 minuto.')
        for row in batch:
            if int(row[6]) < now_ms:
                records.append({'time': pd.to_datetime(int(row[0]), unit='ms', utc=True),
                                'open': float(row[1]), 'high': float(row[2]),
                                'low': float(row[3]), 'close': float(row[4]),
                                'volume': float(row[5])})
        next_cursor = int(batch[-1][0]) + 60000
        if next_cursor <= cursor:
            raise RuntimeError('API retornou paginação sem avanço.')
        cursor = next_cursor
        if len(batch) < 1000:
            break
    return validate_candles(pd.DataFrame(records))


def signals_1m(candles: pd.DataFrame) -> pd.DataFrame:
    df = validate_candles(candles)
    close = df['close']
    df['ema9'] = close.ewm(span=9, min_periods=9, adjust=False).mean()
    df['ema21'] = close.ewm(span=21, min_periods=21, adjust=False).mean()
    gains = close.diff().clip(lower=0)
    losses = -close.diff().clip(upper=0)
    g = gains.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    l = losses.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    ratio = g / l.replace(0, float('nan'))
    df['rsi'] = (100 - 100 / (1 + ratio)).mask((l == 0) & (g > 0), 100).mask((l == 0) & (g == 0), 50)
    avg_volume = df['volume'].rolling(30, min_periods=30).mean()
    candle_range = (df['high'] - df['low']) / close
    # Todas as condições se formam somente no fechamento da barra i.
    # Compra hipotética ocorre na ABERTURA da próxima barra i+1.
    df['buy_signal'] = ((df['ema9'] > df['ema21']) & (df['close'] > df['ema9']) &
                        (df['ema21'] > df['ema21'].shift(5)) &
                        df['rsi'].between(55, 72) & (df['rsi'].shift(1) < 55) &
                        (df['volume'] >= .8 * avg_volume) &
                        candle_range.between(.0003, .015)).fillna(False)
    df['exit_signal'] = ((df['ema9'] < df['ema21']) | (df['rsi'] < 45)).fillna(False)
    return df


def backtest_1m(candles: pd.DataFrame, cfg: MicroConfig = MicroConfig()) -> dict:
    if cfg.target_pct <= 0 or cfg.stop_pct <= 0 or cfg.position_brl <= 0:
        raise ValueError('Configuração de risco inválida.')
    df = signals_1m(candles)
    cash = cfg.initial_brl
    btc = 0.0
    entry_cost = entry_price = 0.0
    entry_idx = -1
    stop = target = 0.0
    highwater = cfg.initial_brl
    halted = False
    cooldown_end = -1
    day = None
    day_result = 0.0
    trades_today = losses_today = 0
    trades = []
    marks = []
    estimated_cost_brl = 0.0
    max_gross_exposure = 0.0

    def sell(mid, i, reason):
        nonlocal cash, btc, entry_cost, entry_price, entry_idx, cooldown_end
        nonlocal day_result, losses_today, estimated_cost_brl
        fill = mid * (1 - cfg.slippage_per_side)
        gross = btc * fill
        fee = gross * cfg.fee_per_side
        proceeds = gross - fee
        pnl = proceeds - entry_cost
        # Include estimated slippage relative to mid-price to show cost drag.
        estimated_cost_brl += btc * mid * cfg.slippage_per_side + fee
        cash += proceeds
        day_result += pnl
        if pnl < 0:
            losses_today += 1
        else:
            losses_today = 0
        trades.append({'entry_time_utc': df.iloc[entry_idx]['time'].isoformat(),
                       'exit_time_utc': df.iloc[i]['time'].isoformat(),
                       'entry_brl': round(entry_price, 2),
                       'exit_brl': round(fill, 2), 'profit_brl': round(pnl, 4),
                       'duration_minutes': i - entry_idx, 'reason': reason,
                       'notional_brl': round(entry_cost, 2)})
        btc = entry_cost = entry_price = 0.0
        entry_idx = -1
        cooldown_end = i + cfg.cooldown_bars

    for i in range(1, len(df)):
        row, prev = df.iloc[i], df.iloc[i-1]
        current_day = row['time'].strftime('%Y-%m-%d')
        if current_day != day:
            day = current_day
            day_result, trades_today, losses_today = 0.0, 0, 0
        op = float(row['open'])
        # Marca patrimônio a preço executável, não preço teórico sem taxas.
        opening_equity = cash + btc * op * (1-cfg.slippage_per_side) * (1-cfg.fee_per_side)
        highwater = max(highwater, opening_equity)
        if opening_equity < highwater * (1 - cfg.max_equity_drawdown):
            halted = True

        was_open = btc > 0
        if was_open:
            reason, mid = None, None
            if op <= stop:
                reason, mid = 'gap_stop', op
            elif op >= target:
                reason, mid = 'gap_target', op
            elif i-entry_idx >= cfg.max_hold_bars:
                reason, mid = 'tempo_maximo', op
            elif bool(prev['exit_signal']):
                reason, mid = 'reversao', op
            elif float(row['low']) <= stop:
                # Conservador: assume stop antes do alvo se ambos forem tocados.
                reason, mid = 'stop', stop
            elif float(row['high']) >= target:
                reason, mid = 'alvo', target
            if reason:
                sell(mid, i, reason)
        # Não reabre no mesmo minuto em que encerrou uma posição.
        if (not was_open and btc == 0 and not halted and
            i > cooldown_end and trades_today < cfg.max_trades_per_day and
            losses_today < cfg.max_losses_in_day and day_result > -cfg.max_realized_loss_day_brl and
            bool(prev['buy_signal'])):
            size = min(cfg.position_brl, cash*cfg.position_fraction)
            if size >= 20 and size <= cash:
                fill = op*(1+cfg.slippage_per_side)
                fee_fraction = 1+cfg.fee_per_side
                btc = size/(fill*fee_fraction)
                entry_price, entry_cost, entry_idx = fill, size, i
                stop = fill*(1-cfg.stop_pct)
                target = fill*(1+cfg.target_pct)
                estimated_cost_brl += btc*op*cfg.slippage_per_side + btc*fill*cfg.fee_per_side
                cash -= size
                max_gross_exposure = max(max_gross_exposure, size)
                trades_today += 1
                # Mesmo minuto da compra; se os dois limites tocam, assume stop.
                if float(row['low']) <= stop:
                    sell(stop, i, 'stop')
                elif float(row['high']) >= target:
                    sell(target, i, 'alvo')

        eq = cash + btc * float(row['close'])*(1-cfg.slippage_per_side)*(1-cfg.fee_per_side)
        highwater = max(highwater, eq)
        if eq < highwater*(1-cfg.max_equity_drawdown):
            halted = True
        if i % 20 == 0 or i == len(df)-1:
            marks.append({'time': row['time'].isoformat(), 'equity_brl': round(eq, 4)})

    last = df.iloc[-1]
    final_brl = cash + btc * float(last['close'])*(1-cfg.slippage_per_side)*(1-cfg.fee_per_side)
    win_count = sum(1 for t in trades if t['profit_brl'] > 0)
    balances = pd.Series([cfg.initial_brl] + [m['equity_brl'] for m in marks])
    return {
        'type': 'BACKTEST_SCALPING_1M_EXPERIMENTAL', 'market': 'BTCBRL',
        'period': '1m', 'first_candle_utc': df.iloc[0]['time'].isoformat(),
        'last_candle_utc': last['time'].isoformat(), 'candles': len(df),
        'initial_brl': cfg.initial_brl, 'final_brl': round(final_brl, 2),
        'profit_brl': round(final_brl-cfg.initial_brl, 2),
        'return_pct': round((final_brl/cfg.initial_brl-1)*100, 2),
        'max_drawdown_pct': round(max_drawdown(balances)*100, 2),
        'trades': len(trades), 'wins': win_count,
        'win_rate_pct': round(win_count/len(trades)*100, 2) if trades else None,
        'open_position': btc > 0, 'halted': halted,
        'total_estimated_cost_brl': round(estimated_cost_brl, 2),
        'max_position_brl': round(max_gross_exposure, 2),
        'fee_pct_per_side': cfg.fee_per_side*100,
        'slippage_pct_per_side': cfg.slippage_per_side*100,
        'assumptions': asdict(cfg),
        'trades_sample': trades[-30:], 'equity_curve': marks[-1000:],
        'source': 'Binance API público /api/v3/klines BTCBRL 1m',
        'warning': 'Backtest educacional com OHLC de 1 minuto; custos hipotéticos, fills intrabar não verificáveis, sem ordens reais e sem operação contínua. Não garante lucro.',
    }


def refresh_report_if_due(path: Path, *, days: int = 14, now: datetime | None = None, candles: pd.DataFrame | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if path.is_file():
        try:
            prior = json.loads(path.read_text(encoding='utf-8'))
            updated = datetime.fromisoformat(prior['generated_at_utc'])
            if (prior.get('type') == 'BACKTEST_SCALPING_1M_EXPERIMENTAL' and
                updated.tzinfo and now-updated < timedelta(hours=24)):
                return False
        except (ValueError, KeyError, OSError, TypeError):
            pass
    source = fetch_minute_candles(days=days) if candles is None else candles
    result = backtest_1m(source)
    result['generated_at_utc'] = now.isoformat()
    result['dataset_origin'] = 'API pública Binance BTCBRL 1m / não auditado externamente'
    save_json(path, result)
    return True
