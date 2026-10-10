#!/usr/bin/env python3
"""Prepara a simulação na nuvem e alimenta o painel, exclusivamente paper.

Não implementa ordens reais nem lê credenciais de API.
"""
from __future__ import annotations
import sys
import os
import json
from controle import normalize_action, load_control, apply_command, save_control
from painel_export import build_payload, write_panel_data
from robo import paper_once, api_request
from pathlib import Path
from robo import backtest, fetch_klines, save_json
from comparador import generate_if_due
from acompanhar import check_and_export
from scalping import refresh_report_if_due

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'estado_paper.json'
REPORTS = ROOT / 'relatorios' / 'historico'
PANEL = ROOT / 'painel'
CONTROL = ROOT / 'controle_robo.json'
SHADOW_V4 = ROOT / 'estado_comparacao_v4.json'
SHADOW_V5 = ROOT / 'estado_comparacao_v5.json'
COMPARISON = ROOT / 'relatorios' / 'comparativo' / 'resumo.json'
SCALPING_REPORT = ROOT / 'relatorios' / 'scalping_1m' / 'resumo.json'


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
    try:
        changed = generate_if_due(COMPARISON)
        print('Comparação histórica: ' + ('calculada no mesmo histórico' if changed else 'relatório recente preservado'), flush=True)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        # A falha do comparativo não remove o relatório histórico existente.
        print(f'AVISO: comparação histórica indisponível: {error}', file=sys.stderr, flush=True)
    # Laboratório V6: backtest de 1 minuto (14 dias), SEM papel 'ao vivo'.
    # GitHub Actions pode atrasar e não deve executar stops de scalping.
    try:
        updated = refresh_report_if_due(SCALPING_REPORT, days=14)
        print('Scalping V6 1m: ' + ('backtest calculado' if updated else 'backtest recente preservado'), flush=True)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        print(f'AVISO: pesquisa V6 1m indisponível: {error}', file=sys.stderr, flush=True)
    action = normalize_action(os.environ.get('ROBO_ACAO', 'checar'))
    control, new_start, force_close = apply_command(load_control(CONTROL), action)
    print(f'Controle: {action}; estado solicitado: {control["modo"]}; SEM ordens reais.', flush=True)
    # Nunca cria entradas enquanto pausado. Pausa mantém a proteção simulada de posições;
    # encerrar solicita venda simulada ao preço observado pela API.
    # Mesma amostra e mesmo preço para carteiras espelhadas V4/V5.
    # A carteira V4 principal continua sendo preservada no arquivo de origem.
    snapshot = (fetch_klines(days=25), float(api_request('/api/v3/ticker/price', {'symbol': 'BTCBRL'})['price']))
    status = paper_once(STATE, allow_entries=control['modo'] == 'ativo',
                        force_close=force_close, new_start=new_start,
                        market_data=snapshot)
    status_v4 = paper_once(SHADOW_V4, allow_entries=control['modo'] == 'ativo',
                           force_close=force_close, new_start=new_start,
                           market_data=snapshot)
    status_v5 = paper_once(SHADOW_V5, allow_entries=control['modo'] == 'ativo',
                           force_close=force_close, new_start=new_start,
                           strategy='v5', market_data=snapshot)
    print(f'Comparação paper (2 carteiras VIRTUAIS): V4 R$ {status_v4["equity_brl"]:.2f}; V5 R$ {status_v5["equity_brl"]:.2f}.', flush=True)
    save_control(CONTROL, control)
    payload = build_payload(REPORTS, STATE)
    payload['control'] = control
    from painel_export import read_paper
    payload['comparison'] = {
        'historical': json.loads(COMPARISON.read_text(encoding='utf-8')) if COMPARISON.is_file() else None,
        'paper_v4': read_paper(SHADOW_V4),
        'paper_v5': read_paper(SHADOW_V5),
        'paper_description': 'Carteiras novas iniciadas juntas, separadas da simulação principal V4.',
    }
    payload['scalping_v6'] = json.loads(SCALPING_REPORT.read_text(encoding='utf-8')) if SCALPING_REPORT.is_file() else None
    write_panel_data(payload, PANEL)
    print(f'Checagem concluída. Patrimônio fictício: R$ {status["equity_brl"]:.2f}.', flush=True)
    print(' | '.join(status['events']), flush=True)
    print('Painel publicado na próxima etapa do workflow.', flush=True)


if __name__ == '__main__':
    main()
