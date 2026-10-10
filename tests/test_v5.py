"""Testes da V5: comparação não manipula a V4, nem envia ordens reais."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robo import backtest, indicators, normalize, paper_once
from comparador import comparison_from_candles, generate_if_due


def path_prices(n=820):
    # Preços artificiais PARA TESTAR O CÓDIGO, não para estimar rentabilidade.
    start=datetime(2025, 1, 1, tzinfo=timezone.utc)
    prices=[]; current=500000.
    for i in range(n):
        growth=.003 if (i//90)%2==0 else -.0022
        current=current * (1 + growth + .004*((i%11)-5)/5)
        high=max(current, current/(1+growth))*1.015
        low=min(current, current/(1+growth))*.985
        prices.append({'time':start+timedelta(hours=4*i),'open':current/(1+growth),
                       'high':high,'low':low,'close':current,'volume':1})
    return normalize(pd.DataFrame(prices))


class V5Tests(unittest.TestCase):
    def test_v4_backward_compatible(self):
        df=path_prices()
        old=indicators(df)
        explicit=indicators(df,strategy='v4')
        self.assertEqual(old['enter'].tolist(),explicit['enter'].tolist())
        a, _, _ = backtest(df)
        b, _, _ = backtest(df,strategy='v4')
        self.assertEqual(a['final_brl'],b['final_brl'])

    def test_v5_indicators_only_use_closed_past(self):
        df=path_prices()
        first=indicators(df.iloc[:600],strategy='v5').iloc[-1]
        full=indicators(df,strategy='v5').iloc[599]
        for col in ('ema20','ema50','rsi','atr_pct','adx','entry_stop_pct'):
            self.assertAlmostEqual(first[col],full[col],places=8)
        self.assertEqual(bool(first['enter']),bool(full['enter']))

    def test_v5_entry_is_subset_and_stop_bounded(self):
        df=indicators(path_prices(),strategy='v5')
        base=indicators(path_prices())
        self.assertTrue((~df['enter'] | base['enter']).all())
        self.assertTrue(df['entry_stop_pct'].dropna().between(.015,.04).all())
        self.assertTrue((df['entry_target_pct'].dropna() == df['entry_stop_pct'].dropna()*2).all())

    def test_comparison_uses_same_period_and_costs(self):
        result=comparison_from_candles(path_prices(820))
        for period in ('ultimo_ano','ultimos_90_dias'):
            item=result['windows'][period]
            a,b=item['v4'],item['v5']
            self.assertEqual(a['initial_brl'],1000)
            self.assertEqual(b['initial_brl'],1000)
            self.assertEqual(a['start_utc'],b['start_utc'])
            self.assertEqual(a['end_utc'],b['end_utc'])
            self.assertEqual(a['fee_pct_per_side'],b['fee_pct_per_side'])
            self.assertEqual(a['slippage_pct_per_side'],b['slippage_pct_per_side'])
        self.assertEqual(result['windows']['ultimos_90_dias']['candles'],540)

    def test_fetch_fail_does_not_create_comparison(self):
        with tempfile.TemporaryDirectory() as td, patch('comparador.fetch_klines',side_effect=RuntimeError('network')):
            target=Path(td)/'compare.json'
            with self.assertRaises(RuntimeError): generate_if_due(target)
            self.assertFalse(target.exists())

    def test_v5_shadow_creates_separate_state_without_modifying_v4(self):
        df=path_prices(160)
        with tempfile.TemporaryDirectory() as td:
            v4=Path(td)/'main_v4.json'
            v4.write_text('{"cash_brl": 777.0, "btc_qty": 0.0}')
            shadow=Path(td)/'v5.json'
            paper_once(shadow,allow_entries=False,strategy='v5',market_data=(df,500000))
            saved=json.loads(shadow.read_text())
            self.assertEqual(saved['cash_brl'],1000)
            self.assertEqual(saved['strategy'],'v5')
            self.assertEqual(json.loads(v4.read_text())['cash_brl'],777)

    def test_no_live_broker_order_workflow(self):
        script=(Path(__file__).resolve().parents[1]/'executar_nuvem.py').read_text()
        self.assertNotIn('api/v3/order',script)
        self.assertNotIn('secret_key',script.lower())

if __name__=='__main__':unittest.main()
