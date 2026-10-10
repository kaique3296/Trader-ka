#!/usr/bin/env python3
"""Prepara a simulação na nuvem e alimenta o painel, exclusivamente paper.

Não implementa ordens reais nem lê credenciais de API.
"""
from __future__ import annotations
import sys
from pathlib import Path
from robo import backtest, fetch_klines, save_json
from acompanhar import check_and_export

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'estado_paper.json'
REPORTS = ROOT / 'relatorios' / 'historico'
PANEL = ROOT / 'painel'


def maybe_generate_first_backtest():
    """Testa histórico real quando disponível; nunca inventa resultados."""
    if (REPORTS / 'resumo.json').is_file():
        print('Backtest inicial já existe. Preservando análise histórica.', flush=True)
        return
    try:
        print('Baixando 365 dias de candles públicos para backtest inicial...', flush=True)
        candles = fetch_klines(days=365)
        summary, trades, curve = backtest(candles)
        summary['dataset_label'] = 'BINANCE_PUBLICO_BTCBRL_NA_DATA_DA_COLETA'
        summary['source_files'] = ['Binance Spot API klines BTCBRL 4h']
        REPORTS.mkdir(parents=True, exist_ok=True)
        save_json(REPORTS / 'resumo.json', summary)
        trades.to_csv(REPORTS / 'operacoes.csv', index=False)
        curve.to_csv(REPORTS / 'evolucao_saldo.csv', index=False)
        print(f'Backtest inicial com {len(candles)} candles encerrados. '
              f'Resultado retrospectivo R$ {summary["final_brl"]:.2f} (não garante retorno).', flush=True)
    except (ValueError, RuntimeError, OSError) as error:
        print(f'AVISO: backtest não gerado nesta execução: {error}. '
              'O paper trading será tentado mesmo assim.', file=sys.stderr, flush=True)


def main():
    maybe_generate_first_backtest()
    print('Executando uma checagem de paper trading na nuvem (SEM ordens reais).', flush=True)
    check_and_export(STATE, REPORTS, PANEL)
    print('Painel com dados atualizados e prontos para publicar.', flush=True)


if __name__ == '__main__':
    main()
