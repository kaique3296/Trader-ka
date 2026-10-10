#!/usr/bin/env python3
"""Robô BTC/BRL v1 - backtest e paper trading, SEM operações reais."""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

API_ROOT = 'https://data-api.binance.vision'
SYMBOL = 'BTCBRL'
INTERVAL = '4h'
CANDLE_MS = 4 * 3600 * 1000
COLUMNS = ['time', 'open', 'high', 'low', 'close', 'volume', 'close_time']


@dataclass(frozen=True)
class Config:
    initial_brl: float = 1000.0
    max_position_brl: float = 200.0
    max_equity_fraction: float = 0.20
    stop_pct: float = 0.03
    target_pct: float = 0.06
    fee_pct: float = 0.001
    slippage_pct: float = 0.0005
    daily_loss_brl: float = 20.0
    max_equity_drawdown_pct: float = 0.10
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_window: int = 14
    minimum_notional_brl: float = 20.0  # limiar conservador hipotético; regras reais do par podem variar


def api_request(endpoint: str, params: dict | None = None):
    query = ('?' + urllib.parse.urlencode(params)) if params else ''
    req = urllib.request.Request(
        API_ROOT + endpoint + query,
        headers={'User-Agent': 'RoboEducacional-BTCBRL/1.0'},
    )
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f'Falha ao acessar dados públicos Binance: {exc}. Confira conexão, região e par BTCBRL.') from exc


def from_binance_rows(rows: list) -> pd.DataFrame:
    if not rows:
        raise ValueError('Nenhum candle recebido.')
    records = []
    for r in rows:
        records.append({
            'time': pd.to_datetime(int(r[0]), unit='ms', utc=True),
            'open': float(r[1]), 'high': float(r[2]), 'low': float(r[3]),
            'close': float(r[4]), 'volume': float(r[5]),
            'close_time': int(r[6]),
        })
    return normalize(pd.DataFrame(records))


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if 'time' not in df.columns:
        raise ValueError('CSV exige as colunas time,open,high,low,close (volume e close_time opcionais).')
    if pd.api.types.is_numeric_dtype(df['time']):
        stamps = pd.to_numeric(df['time'])
        unit = 'us' if stamps.abs().median() >= 1e14 else 'ms'
        df['time'] = pd.to_datetime(stamps, unit=unit, utc=True)
    else:
        df['time'] = pd.to_datetime(df['time'], utc=True)
    for col in ['open', 'high', 'low', 'close']:
        if col not in df.columns:
            raise ValueError(f'Coluna obrigatória ausente: {col}')
        df[col] = pd.to_numeric(df[col], errors='raise')
    if 'volume' not in df.columns:
        df['volume'] = 0.0
    df['volume'] = pd.to_numeric(df['volume'], errors='raise')
    if df[['open', 'high', 'low', 'close']].isna().any().any():
        raise ValueError('Há valores de preço ausentes.')
    if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
        raise ValueError('Preços devem ser maiores que zero.')
    if (df['high'] < df[['open', 'close', 'low']].max(axis=1)).any() or (df['low'] > df[['open', 'close', 'high']].min(axis=1)).any():
        raise ValueError('Candles OHLC inconsistentes.')
    df = df.sort_values('time').drop_duplicates('time', keep='last').reset_index(drop=True)
    if len(df) >= 2:
        delta = df['time'].diff().dropna()
        if (delta != pd.Timedelta(hours=4)).any():
            raise ValueError('Os candles devem ser consecutivos com intervalo fixo de 4 horas (UTC).')
    return df


def fetch_klines(days: int = 365) -> pd.DataFrame:
    if days < 15 or days > 730:
        raise ValueError('Use --days entre 15 e 730.')
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days * 86400000
    data = []
    while start_ms < now_ms:
        batch = api_request('/api/v3/klines', {
            'symbol': SYMBOL, 'interval': INTERVAL, 'startTime': start_ms,
            'endTime': now_ms, 'limit': 1000,
        })
        if not batch:
            break
        data.extend(batch)
        new_ms = int(batch[-1][0]) + CANDLE_MS
        if new_ms <= start_ms:
            raise RuntimeError('Paginação interrompida: a API não avançou.')
        start_ms = new_ms
        if len(batch) < 1000:
            break
    # Usa APENAS candles finalizados: a última barra retornada pode estar aberta.
    complete = [row for row in data if int(row[6]) < int(time.time() * 1000)]
    return from_binance_rows(complete)



def load_price_files(paths: list[str]) -> pd.DataFrame:
    """Carrega CSV próprio ou CSV/ZIP oficial de klines Spot Binance (12 colunas, sem cabeçalho)."""
    files = []
    for item in paths:
        matches = sorted(glob.glob(item))
        if not matches:
            raise ValueError(f'Arquivo não encontrado: {item}')
        files.extend(matches)
    pieces = []
    for file in files:
        # CSV oficial de 12 colunas sem cabeçalho, com timestamps em µs após 2025.
        probe = pd.read_csv(file, header=None, nrows=1)
        is_archive = len(probe.columns) == 12 and str(probe.iloc[0, 0]).strip().isdigit()
        if is_archive:
            raw = pd.read_csv(file, header=None, names=[
                'time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
        else:
            raw = pd.read_csv(file)
        pieces.append(raw)
    return normalize(pd.concat(pieces, ignore_index=True))

def indicators(data: pd.DataFrame, c: Config = Config()) -> pd.DataFrame:
    df = normalize(data)
    close = df['close']
    df['ema20'] = close.ewm(span=c.ema_fast, adjust=False, min_periods=c.ema_fast).mean()
    df['ema50'] = close.ewm(span=c.ema_slow, adjust=False, min_periods=c.ema_slow).mean()
    diff = close.diff()
    gain = diff.clip(lower=0)
    loss = -diff.clip(upper=0)
    # RSI de Wilder (EMA alpha=1/N), sem antecipar dados futuros.
    ag = gain.ewm(alpha=1 / c.rsi_window, adjust=False, min_periods=c.rsi_window).mean()
    al = loss.ewm(alpha=1 / c.rsi_window, adjust=False, min_periods=c.rsi_window).mean()
    rs = ag / al.replace(0, float('nan'))
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.mask((al == 0) & (ag > 0), 100)
    rsi = rsi.mask((al == 0) & (ag == 0), 50)
    df['rsi'] = rsi
    df['enter'] = (
        (df['ema20'] > df['ema50']) &
        (df['close'] > df['ema20']) &
        (df['rsi'] >= 50) & (df['rsi'] <= 68) &
        (df['rsi'].shift(1) < 50)
    ).fillna(False)
    df['trend_exit'] = ((df['ema20'] < df['ema50']) | (df['rsi'] < 45)).fillna(False)
    return df


def execution_price(mid: float, side: str, c: Config) -> float:
    """Pior preço aproximado devido ao deslizamento, inclusive em gaps."""
    return mid * (1 + c.slippage_pct if side == 'buy' else 1 - c.slippage_pct)


def mark_equity(cash: float, btc: float, mid: float, c: Config) -> float:
    return cash + btc * execution_price(mid, 'sell', c) * (1 - c.fee_pct)


def max_drawdown(equities: pd.Series) -> float:
    if equities.empty:
        return 0.0
    high = equities.cummax()
    return float((equities / high - 1).min())


def backtest(data: pd.DataFrame, c: Config = Config()):
    df = indicators(data, c)
    if len(df) < 100:
        raise ValueError('Backtest exige pelo menos 100 candles consecutivos de 4 horas.')
    cash, qty, buy_cost, entry = c.initial_brl, 0.0, 0.0, 0.0
    stop, target = 0.0, 0.0
    peak = c.initial_brl
    halted = False
    daily_pnl: dict[str, float] = {}
    trades, equity_rows = [], []

    def sell(mid: float, when, reason: str):
        nonlocal cash, qty, buy_cost, entry, stop, target
        if qty <= 0:
            return
        fill = execution_price(mid, 'sell', c)
        gross = qty * fill
        fee = gross * c.fee_pct
        proceeds = gross - fee
        cash += proceeds
        profit = proceeds - buy_cost
        date = when.strftime('%Y-%m-%d')
        daily_pnl[date] = daily_pnl.get(date, 0.0) + profit
        trades.append({
            'exit_time_utc': when.isoformat(), 'entry_time_utc': entry_time.isoformat(),
            'entry_brl': round(entry, 2), 'exit_brl': round(fill, 2),
            'notional_brl': round(buy_cost, 2), 'profit_brl': round(profit, 2),
            'profit_pct_on_notional': round(profit / buy_cost * 100, 4), 'reason': reason,
        })
        qty, buy_cost, entry, stop, target = 0.0, 0.0, 0.0, 0.0, 0.0

    entry_time = None
    for i, r in df.iterrows():
        current_time = r['time'].to_pydatetime()
        day = current_time.strftime('%Y-%m-%d')
        op, hi, lo, cl = (float(r[k]) for k in ('open', 'high', 'low', 'close'))
        equity_open = mark_equity(cash, qty, op, c)
        peak = max(peak, equity_open)
        if (peak - equity_open) / peak >= c.max_equity_drawdown_pct:
            halted = True

        # Sinal da barra ANTERIOR -> execução na abertura da barra atual.
        if i > 0 and qty > 0 and bool(df.iloc[i - 1]['trend_exit']):
            sell(op, current_time, 'trend_exit')
        if i > 0 and qty == 0 and (not halted) and daily_pnl.get(day, 0.0) > -c.daily_loss_brl:
            if bool(df.iloc[i - 1]['enter']):
                size = min(c.max_position_brl, max(0.0, cash * c.max_equity_fraction))
                if size >= c.minimum_notional_brl and size <= cash:
                    fill = execution_price(op, 'buy', c)
                    qty = size / (fill * (1 + c.fee_pct))
                    buy_cost = size
                    entry = fill
                    entry_time = current_time
                    stop = fill * (1 - c.stop_pct)
                    target = fill * (1 + c.target_pct)
                    cash -= size
        if qty > 0:
            # Se ambos níveis forem tocados no mesmo candle: stop primeiro.
            # Gaps e execução ocorrem a um preço possivelmente pior que o nível indicado.
            if lo <= stop:
                sell(min(op, stop), current_time, 'stop')
            elif hi >= target:
                sell(max(op, target), current_time, 'target')

        eq = mark_equity(cash, qty, cl, c)
        peak = max(peak, eq)
        if (peak - eq) / peak >= c.max_equity_drawdown_pct:
            halted = True
        equity_rows.append({'time': r['time'].isoformat(), 'equity_brl': round(eq, 4),
                            'cash_brl': round(cash, 4), 'btc_qty': round(qty, 10),
                            'halted': halted})

    # Finaliza a posição para tornar o P&L comparável e não omitir custos de saída.
    if qty > 0:
        sell(float(df.iloc[-1]['close']), df.iloc[-1]['time'].to_pydatetime(), 'end_of_test')
        equity_rows[-1]['equity_brl'] = round(cash, 4)
        equity_rows[-1]['cash_brl'] = round(cash, 4)
        equity_rows[-1]['btc_qty'] = 0.0

    curve = pd.DataFrame(equity_rows)
    closed_trades = pd.DataFrame(trades)
    result = cash
    # Benchmark comprar no primeiro fechamento e vender no último, mesmas taxas e slippage.
    first = float(df.iloc[0]['close'])
    last = float(df.iloc[-1]['close'])
    qty_hold = c.initial_brl / (execution_price(first, 'buy', c) * (1 + c.fee_pct))
    final_hold = qty_hold * execution_price(last, 'sell', c) * (1 - c.fee_pct)
    wins = sum(t['profit_brl'] > 0 for t in trades)
    summary = {
        'type': 'BACKTEST_EM_DADOS_FORNECIDOS',
        'symbol': SYMBOL, 'quote_currency': 'BRL', 'interval': INTERVAL,
        'start_utc': df.iloc[0]['time'].isoformat(), 'end_utc': df.iloc[-1]['time'].isoformat(),
        'candles': len(df), 'initial_brl': round(c.initial_brl, 2),
        'final_brl': round(result, 2), 'net_result_brl': round(result - c.initial_brl, 2),
        'net_return_pct': round((result / c.initial_brl - 1) * 100, 2),
        'max_drawdown_pct': round(max_drawdown(curve['equity_brl']) * 100, 2),
        'trades': len(trades), 'wins': wins,
        'win_rate_pct': round(wins / len(trades) * 100, 2) if trades else None,
        'benchmark_buy_hold_brl': round(final_hold, 2),
        'benchmark_buy_hold_return_pct': round((final_hold / c.initial_brl - 1) * 100, 2),
        'halted_by_drawdown': halted, 'fee_pct_per_side': c.fee_pct * 100,
        'slippage_pct_per_side': c.slippage_pct * 100,
    }
    return summary, closed_trades, curve


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Escrita atômica: evita estado parcialmente escrito em falha de execução.
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmppath = Path(tmp.name)
    os.replace(tmppath, path)


def paper_once(state_path: Path, c: Config = Config()):
    """Uma única checagem de preço; paper trading local, sem enviar ordens."""
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
    else:
        state = {
            'cash_brl': c.initial_brl, 'btc_qty': 0.0, 'entry_brl': 0.0,
            'buy_cost_brl': 0.0, 'stop_brl': 0.0, 'target_brl': 0.0,
            'entry_time_utc': None, 'last_processed_bar': None,
            'peak_equity_brl': c.initial_brl, 'halted': False,
            'daily_realized_brl': {}, 'trades': [], 'checks': 0,
            'equity_history': [],
        }
    # Não aceita estado de estratégias/valores arbitrários sem validação de saldos.
    if float(state['cash_brl']) < -0.00001 or float(state['btc_qty']) < 0:
        raise ValueError('Estado de simulação inválido.')
    df = indicators(fetch_klines(days=25), c)
    if len(df) < 100:
        raise RuntimeError('Não há candles suficientes para calcular indicadores.')
    raw_ticker = api_request('/api/v3/ticker/price', {'symbol': SYMBOL})
    price = float(raw_ticker['price'])
    if price <= 0:
        raise RuntimeError('Preço recebido inválido.')
    now = datetime.now(timezone.utc)
    day = now.strftime('%Y-%m-%d')
    new_bar = state['last_processed_bar'] != df.iloc[-1]['time'].isoformat()
    state['checks'] += 1
    events = []
    qty = float(state['btc_qty'])
    eq = mark_equity(float(state['cash_brl']), qty, price, c)
    state['peak_equity_brl'] = max(float(state['peak_equity_brl']), eq)
    if (state['peak_equity_brl'] - eq) / state['peak_equity_brl'] >= c.max_equity_drawdown_pct:
        state['halted'] = True
        events.append('TRAVA: drawdown máximo atingido. Não serão abertas novas posições.')

    # Stops de software: checados somente quando o programa roda.
    exit_reason = None
    if qty > 0:
        if price <= float(state['stop_brl']):
            exit_reason = 'stop_software'
        elif price >= float(state['target_brl']):
            exit_reason = 'target_software'
        elif new_bar and bool(df.iloc[-1]['trend_exit']):
            exit_reason = 'trend_exit'
    if exit_reason:
        fill = execution_price(price, 'sell', c)
        proceeds = qty * fill * (1 - c.fee_pct)
        pnl = proceeds - float(state['buy_cost_brl'])
        state['cash_brl'] += proceeds
        state['daily_realized_brl'][day] = state['daily_realized_brl'].get(day, 0.0) + pnl
        state['trades'].append({
            'entry_time_utc': state['entry_time_utc'], 'exit_time_utc': now.isoformat(),
            'entry_brl': state['entry_brl'], 'exit_brl': round(fill, 2),
            'profit_brl': round(pnl, 2), 'reason': exit_reason,
        })
        state.update({'btc_qty': 0.0, 'entry_brl': 0.0, 'buy_cost_brl': 0.0,
                      'stop_brl': 0.0, 'target_brl': 0.0, 'entry_time_utc': None})
        events.append(f'VENDA SIMULADA: {exit_reason}, P&L R$ {pnl:.2f}')

    # Sinal formado em candle já encerrado, executado no preço OBSERVADO agora.
    if new_bar:
        state['last_processed_bar'] = df.iloc[-1]['time'].isoformat()
        if (state['btc_qty'] == 0 and not state['halted'] and
                state['daily_realized_brl'].get(day, 0.0) > -c.daily_loss_brl and
                bool(df.iloc[-1]['enter']) and not exit_reason):
            size = min(c.max_position_brl, state['cash_brl'] * c.max_equity_fraction)
            if c.minimum_notional_brl <= size <= state['cash_brl']:
                fill = execution_price(price, 'buy', c)
                qty = size / (fill * (1 + c.fee_pct))
                state['cash_brl'] -= size
                state.update({'btc_qty': qty, 'entry_brl': fill, 'buy_cost_brl': size,
                              'stop_brl': fill * (1 - c.stop_pct),
                              'target_brl': fill * (1 + c.target_pct),
                              'entry_time_utc': now.isoformat()})
                events.append(f'COMPRA SIMULADA: R$ {size:.2f}; preço BTC R$ {fill:.2f}')
    state['last_check_utc'] = now.isoformat()
    state['last_price_brl'] = price
    state['equity_brl'] = round(mark_equity(state['cash_brl'], state['btc_qty'], price, c), 4)
    history = state.setdefault('equity_history', [])
    # Registra um ponto por candle de 4h no gráfico de patrimônio,
    # substituindo o último ponto se houver outra checagem do mesmo candle.
    point = {'time': state['last_check_utc'], 'equity_brl': state['equity_brl'],
             'bar': state['last_processed_bar']}
    if history and history[-1].get('bar') == point['bar']:
        history[-1] = point
    else:
        history.append(point)
    state['equity_history'] = history[-900:]
    save_json(state_path, state)
    return {
        'timestamp_utc': state['last_check_utc'], 'paper_only': True,
        'last_close_candle_utc': state['last_processed_bar'],
        'price_brl': price, 'equity_brl': round(state['equity_brl'], 2),
        'cash_brl': round(state['cash_brl'], 2),
        'btc_qty': round(state['btc_qty'], 10), 'halted': state['halted'],
        'new_closed_candle': new_bar, 'events': events or ['Sem operação nesta checagem.'],
    }


def cli():
    parser = argparse.ArgumentParser(description='Robô BTC/BRL educacional, exclusivamente simulado.')
    sub = parser.add_subparsers(dest='command', required=True)
    dl = sub.add_parser('baixar', help='Baixar histórico público de candles BTC/BRL 4h da Binance')
    dl.add_argument('--dias', type=int, default=365)
    dl.add_argument('--saida', default='dados_btcbrl_4h.csv')
    bt = sub.add_parser('backtest', help='Simular trades sobre um CSV de candles OHLC 4h')
    bt.add_argument('--csv', nargs='+', required=True, help='Um ou mais CSV/ZIP; aceita glob entre aspas')
    bt.add_argument('--pasta', default='relatorios')
    pp = sub.add_parser('paper', help='Executar uma checagem no mercado e simular ordens (SEM operação real)')
    pp.add_argument('--estado', default='estado_paper.json')
    args = parser.parse_args()
    try:
        if args.command == 'baixar':
            df = fetch_klines(days=args.dias)
            Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(args.saida, index=False)
            print(f'Salvos {len(df)} candles completos em {args.saida}.')
        elif args.command == 'backtest':
            df = load_price_files(args.csv)
            summary, trades, curve = backtest(df)
            summary['dataset_label'] = ('SINTETICO_FICTICIO_SEM_VALIDADE_FINANCEIRA'
                                        if any('FICTICIO' in x.upper() for x in args.csv)
                                        else 'DADOS_IMPORTADOS_NAO_VERIFICADOS')
            summary['source_files'] = args.csv
            folder = Path(args.pasta)
            folder.mkdir(parents=True, exist_ok=True)
            save_json(folder / 'resumo.json', summary)
            trades.to_csv(folder / 'operacoes.csv', index=False)
            curve.to_csv(folder / 'evolucao_saldo.csv', index=False)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print(f'Relatórios salvos em {folder.resolve()}')
        else:
            print(json.dumps(paper_once(Path(args.estado)), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    cli()
