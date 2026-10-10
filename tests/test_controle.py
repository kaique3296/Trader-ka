import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controle import apply_command, load_control, normalize_action
from robo import paper_once

class ControlTests(unittest.TestCase):
    def test_starts_only_after_explicit_start(self):
        with tempfile.TemporaryDirectory() as td:
            state_file=Path(td)/'controle.json'
            self.assertEqual(load_control(state_file)['modo'],'pausado')
            active, new_start, close = apply_command(load_control(state_file),'TRADERKA_START')
            self.assertEqual(active['modo'],'ativo')
            self.assertTrue(new_start)
            self.assertFalse(close)
            _, second_start, _ = apply_command(active,'iniciar')
            self.assertFalse(second_start)

    def test_pause_and_close(self):
        active={'modo':'ativo'}
        paused, fresh, close=apply_command(active,'TRADERKA_PAUSE')
        self.assertEqual(paused['modo'],'pausado')
        self.assertFalse(fresh)
        self.assertFalse(close)
        closed, _, close=apply_command(active,'TRADERKA_CLOSE')
        self.assertEqual(closed['modo'],'pausado')
        self.assertTrue(close)

    def test_reject_unknown(self):
        for action in ('comprar_agora','resetar_saldo','', '../iniciar'):
            if not action:
                self.assertEqual(normalize_action(action),'checar')
            else:
                with self.assertRaises(ValueError): normalize_action(action)

    def test_paused_still_processes_exits(self):
        # 110 completed candles; includes an entry condition that must be ignored while paused.
        df=pd.DataFrame({'time':pd.date_range('2026-01-01',periods=110,freq='4h',tz='UTC'),
                         'enter':[True]*110,'trend_exit':[False]*110})
        with tempfile.TemporaryDirectory() as td, patch('robo.fetch_klines',return_value=df), \
            patch('robo.indicators', side_effect=lambda x,c:x), \
            patch('robo.api_request',return_value={'price':'100000'}):
            state=Path(td)/'paper.json'
            zero=paper_once(state, allow_entries=False)
            self.assertEqual(zero['btc_qty'],0)
            active=paper_once(state, allow_entries=True, new_start=True)
            self.assertGreater(active['btc_qty'],0)
            qty=active['btc_qty']
            # A pausada não pode comprar outra vez nem forçar fechamento de posição existente.
            paused=paper_once(state, allow_entries=False)
            self.assertEqual(paused['btc_qty'],qty)
            # Encerrar encerra apenas a posição simulada, com custos contabilizados.
            closed=paper_once(state, allow_entries=False, force_close=True)
            self.assertEqual(closed['btc_qty'],0)
            saved=json.loads(state.read_text())
            self.assertEqual(saved['trades'][-1]['reason'],'manual_close')
            self.assertLess(closed['equity_brl'],1000)
            # Repetir o encerramento não duplica vendas.
            paper_once(state, allow_entries=False, force_close=True)
            self.assertEqual(len(json.loads(state.read_text())['trades']),1)

    def test_issue_actions_guarded_by_owner(self):
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/robo-paper.yml').read_text()
        self.assertIn("github.event.issue.user.login == github.repository_owner",workflow)
        self.assertIn('types: [opened]',workflow)
        self.assertIn("ref: main",workflow)

if __name__ == '__main__': unittest.main()
