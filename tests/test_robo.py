import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from robo import Config, backtest, indicators, normalize, paper_once, execution_price


def candles(n=150, growth=0.001):
    rows = []
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 500000.0
    for i in range(n):
        nxt = price * (1 + growth)
        rows.append({'time': start + timedelta(hours=4*i),
                     'open': price, 'high': max(price, nxt) * 1.001,
                     'low': min(price, nxt) * 0.999, 'close': nxt})
        price = nxt
    return pd.DataFrame(rows)


class RoboTests(unittest.TestCase):
    def test_backtest_no_money_creation_without_trades(self):
        summary, trades, curve = backtest(candles())
        self.assertEqual(summary['trades'], 0)
        self.assertAlmostEqual(summary['final_brl'], 1000.0)
        self.assertEqual(len(curve), 150)

    def test_rsi_calculated_without_future_data(self):
        df = candles(160, 0.001)
        one = indicators(df.iloc[:140]).iloc[-1]
        full = indicators(df).iloc[139]
        self.assertAlmostEqual(one['ema20'], full['ema20'], places=7)
        self.assertAlmostEqual(one['ema50'], full['ema50'], places=7)

    def test_prices_are_protected_against_invalid_ohlc(self):
        df = candles(110)
        df.loc[0, 'low'] = df.loc[0, 'high'] + 1
        with self.assertRaises(ValueError):
            normalize(df)

    def test_nonconsecutive_candles_rejected(self):
        df = candles(110).drop(index=[20])
        with self.assertRaises(ValueError):
            normalize(df)

    def test_slippage_side_direction(self):
        c = Config()
        self.assertGreater(execution_price(100, 'buy', c), 100)
        self.assertLess(execution_price(100, 'sell', c), 100)

    def test_simulator_never_includes_live_trading_calls(self):
        import inspect
        src = inspect.getsource(paper_once)
        self.assertNotIn('POST /api', src)
        self.assertNotIn('api/v3/order', src)


if __name__ == '__main__':
    unittest.main()

class TestSimulationMechanics(unittest.TestCase):
    def test_signal_executes_next_bar_and_stop_precedes_target(self):
        from unittest.mock import patch
        original = candles(110, 0)
        original.loc[101, 'high'] = original.loc[101, 'open'] * 1.10
        original.loc[101, 'low'] = original.loc[101, 'open'] * 0.90
        fake = normalize(original)
        fake['enter'] = False
        fake['trend_exit'] = False
        fake.loc[100, 'enter'] = True
        with patch('robo.indicators', return_value=fake):
            summary, trades, _ = backtest(original)
        self.assertEqual(summary['trades'], 1)
        self.assertEqual(trades.iloc[0]['reason'], 'stop')
        self.assertEqual(trades.iloc[0]['entry_time_utc'], fake.iloc[101]['time'].isoformat())
        self.assertLess(summary['final_brl'], 1000)

    def test_paper_repeated_check_does_not_buy_twice(self):
        import tempfile
        from unittest.mock import patch
        from robo import paper_once
        df = normalize(candles(150))
        df['enter'] = False
        df['trend_exit'] = False
        df.loc[149, 'enter'] = True
        with tempfile.TemporaryDirectory() as td, patch('robo.fetch_klines', return_value=df), \
             patch('robo.indicators', return_value=df), \
             patch('robo.api_request', return_value={'price': '500000'}):
            path = Path(td) / 'paper.json'
            first = paper_once(path)
            second = paper_once(path)
        self.assertTrue(first['new_closed_candle'])
        self.assertFalse(second['new_closed_candle'])
        self.assertGreater(first['btc_qty'], 0)
        self.assertEqual(first['btc_qty'], second['btc_qty'])
        self.assertEqual(first['cash_brl'], second['cash_brl'])

    def test_official_binance_microseconds_archive(self):
        import tempfile
        from robo import load_price_files
        sample = candles(101, growth=0.0001)
        rows = []
        for _, r in sample.iterrows():
            start_us = int(r['time'].timestamp() * 1_000_000)
            rows.append([start_us, r['open'], r['high'], r['low'], r['close'], 1,
                        start_us + 4*3600*1_000_000-1, 0, 0, 0, 0, 0])
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / 'BTCBRL-4h-test.csv'
            pd.DataFrame(rows).to_csv(f, index=False, header=False)
            imported = load_price_files([str(f)])
        self.assertEqual(len(imported), 101)
        self.assertEqual(imported['time'].iloc[0], sample['time'].iloc[0])
