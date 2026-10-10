import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import executar_nuvem

class CloudTests(unittest.TestCase):
    def test_empty_website_does_not_contain_demo_profits(self):
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(json.loads((root/'painel/dados.json').read_text()), {})
        self.assertNotIn('1027.21', (root/'painel/dados.js').read_text())
        workflow=(root/'.github/workflows/robo-paper.yml').read_text()
        self.assertIn("17 * * * *",workflow)
        self.assertIn('deploy-pages@v4',workflow)
        self.assertIn('workflow_dispatch',workflow)
        self.assertNotIn('api_key',workflow.lower())

    def test_network_failure_cannot_create_fake_backtest(self):
        with tempfile.TemporaryDirectory() as td, \
            patch.object(executar_nuvem,'REPORTS',Path(td)/'reports'), \
            patch.object(executar_nuvem,'fetch_klines',side_effect=RuntimeError('no network')):
            executar_nuvem.maybe_generate_first_backtest()
            self.assertFalse((Path(td)/'reports'/'resumo.json').exists())

    def test_cloud_calls_paper_only(self):
        with tempfile.TemporaryDirectory() as td, \
            patch.object(executar_nuvem,'maybe_generate_first_backtest'), \
            patch.object(executar_nuvem,'STATE',Path(td)/'estado.json'), \
            patch.object(executar_nuvem,'CONTROL',Path(td)/'controle.json'), \
            patch.object(executar_nuvem,'PANEL',Path(td)/'painel'), \
            patch.object(executar_nuvem,'paper_once', return_value={'equity_brl':1000.0,'events':['Sem operação.']}) as mocked, \
            patch.object(executar_nuvem,'build_payload',return_value={'schema_version':2,'paper_only':True, 'paper': {}}), \
            patch.object(executar_nuvem,'write_panel_data') as mocked_panel:
            executar_nuvem.main()
            mocked.assert_called_once_with(executar_nuvem.STATE, allow_entries=False, force_close=False, new_start=False)
            mocked_panel.assert_called_once()
            self.assertEqual(json.loads(executar_nuvem.CONTROL.read_text())['modo'],'pausado')

if __name__=='__main__':unittest.main()
