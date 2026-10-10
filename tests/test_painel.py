import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from painel_export import build_payload, read_paper, read_backtest, write_panel_data
from acompanhar import check_and_export

ROOT=Path(__file__).resolve().parents[1]

class PainelTests(unittest.TestCase):
    def test_cloud_panel_starts_without_fake_returns(self):
        self.assertEqual((ROOT/'painel'/'dados.js').read_text().strip(), 'window.ROBO_DASHBOARD_DATA = null;')
        self.assertEqual(json.loads((ROOT/'painel'/'dados.json').read_text()), {})
        self.assertIn('schema_version', (ROOT/'painel'/'app.js').read_text())

    def test_real_paper_state_is_exported_without_broker_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'paper.json'
            state={'cash_brl':800.0,'btc_qty':0.0003,'equity_brl':990.0,'last_price_brl':630000.0,
                   'checks':1,'halted':False,'last_check_utc':'2026-10-10T02:00:00+00:00',
                   'trades':[],'entry_brl':625000.0,'stop_brl':606250.0,'target_brl':662500.0,
                   'buy_cost_brl':200.0,'fake_api_key':'shhh',
                   'equity_history':[{'time':'2026-10-10T02:00:00+00:00','equity_brl':990.0}]}
            path.write_text(json.dumps(state))
            result=build_payload(Path(td)/'absent',path)
            self.assertEqual(result['paper']['equity_brl'],990.0)
            self.assertIsNone(result['backtest'])
            self.assertNotIn('shhh',json.dumps(result))
            self.assertEqual(len(result['paper']['equity_curve']),1)
    def test_missing_sources_raise_explicit_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'Nenhum relatório'):
                build_payload(Path(td),Path(td)/'nothing')
    def test_paper_check_updates_panel_with_mocked_source(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.json'
            dest=Path(td)/'panel'
            def fake_paper(p):
                p.write_text(json.dumps({'cash_brl':1000,'btc_qty':0,'equity_brl':1000,
                    'last_check_utc':'2026-10-10T02:00:00+00:00','trades':[],
                    'equity_history':[{'time':'2026-10-10T02:00:00+00:00','equity_brl':1000}]}))
                return {'equity_brl':1000,'events':['Sem operação nesta checagem.']}
            with patch('acompanhar.paper_once',side_effect=fake_paper):
                check_and_export(path,Path(td)/'missing',dest)
            self.assertTrue((dest/'dados.js').is_file())
            self.assertIsNone(json.loads((dest/'dados.json').read_text())['backtest'])

if __name__=='__main__':
    unittest.main()
