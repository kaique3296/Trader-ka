"""Testes mecânicos, com candles inventados; não são prova de rentabilidade."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scalping import (MicroConfig, validate_candles, signals_1m,
                      backtest_1m, refresh_report_if_due)


def fake_prices(n=300):
    start=datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows=[]
    p=500000.0
    for i in range(n):
        old=p
        p *= 1 + (0.00075 if i%75<45 else -0.0008) + (i%9-4)*.00013
        rows.append({'time':start+timedelta(minutes=i),'open':old,
                     'high':max(old,p)*1.0012,'low':min(old,p)*.9988,
                     'close':p, 'volume':1+(i%7)/10})
    return pd.DataFrame(rows)


class ScalpingTests(unittest.TestCase):
    def test_does_not_future_peek(self):
        df=fake_prices(310)
        first=signals_1m(df.iloc[:225]).iloc[-1]
        later=signals_1m(df).iloc[224]
        for name in ('ema9','ema21','rsi'):
            self.assertAlmostEqual(first[name],later[name],places=8)
        self.assertEqual(bool(first['buy_signal']),bool(later['buy_signal']))

    def test_rejects_gap_duplicate_or_bad_high_low(self):
        original=fake_prices()
        gapped=original.drop(index=140)
        duplicated=pd.concat([original,original.iloc[[120]]]).sort_values('time')
        bad=original.copy();bad.loc[10,'high']=bad.loc[10,'low']*.8
        for series in (gapped,duplicated,bad):
            with self.assertRaises(ValueError): validate_candles(series)

    def test_synthetic_summary_no_real_orders(self):
        report=backtest_1m(fake_prices(1440))
        self.assertEqual(report['initial_brl'],1000)
        self.assertEqual(report['period'],'1m')
        self.assertLessEqual(report['max_position_brl'],150)
        self.assertGreaterEqual(report['final_brl'],0)
        self.assertEqual(len(report['trades_sample'])<=30,True)
        self.assertEqual(report['fee_pct_per_side'],.15)

    def test_intrabar_stop_before_target_and_next_bar_entry(self):
        df=validate_candles(fake_prices(160))
        # Garantimos que cada candle tem ranges alcançando os dois limites no minuto 120.
        # O sinal nasce no candle 119; preço de compra = abertura do 120.
        df.loc[120,'high']=df.loc[120,'open']*1.03
        df.loc[120,'low']=df.loc[120,'open']*.97
        with patch('scalping.signals_1m') as signals:
            x=df.copy();x['buy_signal']=False;x['exit_signal']=False
            x.loc[119,'buy_signal']=True
            signals.return_value=x
            summary=backtest_1m(df)
        self.assertEqual(summary['trades'],1)
        t=summary['trades_sample'][0]
        self.assertEqual(t['reason'],'stop')
        self.assertEqual(t['duration_minutes'],0)
        self.assertEqual(t['entry_time_utc'],df.loc[120,'time'].isoformat())
        self.assertLess(t['profit_brl'],0)

    def test_costs_reduce_pnl_even_with_flat_market(self):
        df=validate_candles(fake_prices(160))
        with patch('scalping.signals_1m') as signals:
            x=df.copy();x['buy_signal']=False;x['exit_signal']=False
            x.loc[119,'buy_signal']=True
            x.loc[120,'exit_signal']=True
            # Para não bater stop/alvo, mantemos preço estável nas duas barras.
            for i in (120,121):
                x.loc[i,['open','high','low','close']]=500000.0
            signals.return_value=x
            out=backtest_1m(df)
        self.assertEqual(out['trades'],1)
        self.assertLess(out['trades_sample'][0]['profit_brl'],0)
        self.assertGreater(out['total_estimated_cost_brl'],0)

    def test_refresh_failure_does_not_write_fabricated_data(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'report.json'
            with patch('scalping.fetch_minute_candles',side_effect=RuntimeError('API off')):
                with self.assertRaises(RuntimeError):refresh_report_if_due(target)
            self.assertFalse(target.exists())

    def test_refresh_cache_preserves_same_day(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'report.json'
            now=datetime.now(timezone.utc)
            target.write_text(json.dumps({'type':'BACKTEST_SCALPING_1M_EXPERIMENTAL','generated_at_utc':now.isoformat()}))
            with patch('scalping.fetch_minute_candles',side_effect=RuntimeError('should not call')):
                self.assertFalse(refresh_report_if_due(target,now=now))

    def test_does_not_corrupt_paper_states(self):
        code=(Path(__file__).resolve().parents[1]/'scalping.py').read_text()
        self.assertNotIn('api/v3/order',code)
        self.assertNotIn('estado_paper.json',code)
        self.assertNotIn('estado_comparacao_v5.json',code)

if __name__=='__main__': unittest.main()
