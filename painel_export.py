#!/usr/bin/env python3
"""Exporta somente dados simulados para painel estático. Nenhuma ordem é enviada."""
from __future__ import annotations
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def finite_number(value, default=None):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def read_csv(path, columns=None, max_rows=3000):
    if not path.is_file():
        return []
    with path.open('r', encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if columns and not set(columns).issubset(set(reader.fieldnames or [])):
            raise ValueError(f'Colunas ausentes no arquivo {path.name}.')
        rows = list(reader)
    return rows[-max_rows:]


def normalize_curve(rows, date_column='time'):
    out = []
    for row in rows:
        value = finite_number(row.get('equity_brl'))
        date = str(row.get(date_column) or row.get('timestamp_utc') or '')
        if value is not None and value >= 0 and date:
            out.append({'time': date, 'equity_brl': round(value, 4)})
    # Limita o tamanho do painel sem fabricar pontos e preserva o primeiro/último.
    if len(out) > 900:
        ids = sorted(set(round(i * (len(out) - 1) / 899) for i in range(900)))
        return [out[i] for i in ids]
    return out


def normalize_trades(rows):
    out = []
    for row in rows[-100:]:
        pnl = finite_number(row.get('profit_brl'))
        if pnl is None:
            continue
        out.append({
            'entry_time_utc': str(row.get('entry_time_utc') or ''),
            'exit_time_utc': str(row.get('exit_time_utc') or ''),
            'entry_brl': finite_number(row.get('entry_brl')),
            'exit_brl': finite_number(row.get('exit_brl')),
            'notional_brl': finite_number(row.get('notional_brl')),
            'profit_brl': round(pnl, 4),
            'reason': str(row.get('reason') or 'nao_informado'),
        })
    return out


def read_backtest(folder: Path):
    summary_file = folder / 'resumo.json'
    if not summary_file.is_file():
        return None
    summary = json.loads(summary_file.read_text(encoding='utf-8'))
    if not isinstance(summary, dict) or summary.get('type') != 'BACKTEST_EM_DADOS_FORNECIDOS':
        raise ValueError('Resumo não parece ser um backtest do robô.')
    curve = normalize_curve(read_csv(folder / 'evolucao_saldo.csv', ['time', 'equity_brl']))
    trades = normalize_trades(read_csv(folder / 'operacoes.csv'))
    return {'summary': summary, 'equity_curve': curve, 'trades': trades}


def read_paper(path: Path, initial_brl=1000.0):
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(state, dict) or 'cash_brl' not in state or 'btc_qty' not in state:
        raise ValueError('Estado de simulação inválido.')
    cash = finite_number(state.get('cash_brl'))
    equity = finite_number(state.get('equity_brl'))
    btc = finite_number(state.get('btc_qty'))
    price = finite_number(state.get('last_price_brl'))
    if None in (cash, btc) or cash < 0 or btc < 0:
        raise ValueError('Saldo de paper trading inválido.')
    # Um estado antigo sem equity_brl mostra apenas campos disponíveis.
    return {
        'initial_brl': initial_brl,
        'cash_brl': cash,
        'btc_qty': btc,
        'equity_brl': equity,
        'price_brl': price,
        'entry_brl': finite_number(state.get('entry_brl')),
        'stop_brl': finite_number(state.get('stop_brl')),
        'target_brl': finite_number(state.get('target_brl')),
        'buy_cost_brl': finite_number(state.get('buy_cost_brl')),
        'checks': int(state.get('checks') or 0),
        'halted': bool(state.get('halted')),
        'last_check_utc': state.get('last_check_utc'),
        'started_utc': state.get('started_utc'),
        'last_processed_bar': state.get('last_processed_bar'),
        'trades': normalize_trades(state.get('trades') or []),
        'equity_curve': normalize_curve(state.get('equity_history') or [], 'time'),
    }


def build_payload(report_folder: Path, state_file: Path, initial_brl=1000.0):
    backtest = read_backtest(report_folder)
    paper = read_paper(state_file, initial_brl=initial_brl)
    if backtest is None and paper is None:
        raise ValueError('Nenhum relatório/estado encontrado. Rode backtest ou paper antes de exportar.')
    dataset_label = (backtest or {}).get('summary', {}).get('dataset_label', '')
    is_fake = ('FICTICIO' in dataset_label.upper() or 'SINTETICO' in dataset_label.upper())
    return {
        'schema_version': 2,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'title': 'BTC/BRL • Monitor de estratégia',
        'paper_only': True,
        'has_synthetic_example': is_fake,
        'backtest': backtest,
        'paper': paper,
    }


def write_panel_data(payload: dict, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    (dest / 'dados.json').write_text(content + '\n', encoding='utf-8')
    # Também suportado pelo protocolo file:// para abrir index.html sem servidor.
    js_content = 'window.ROBO_DASHBOARD_DATA = ' + content.replace('</', '<\\/') + ';\n'
    (dest / 'dados.js').write_text(js_content, encoding='utf-8')


def cli():
    parser = argparse.ArgumentParser(description='Exporta backtest/paper para painel responsivo offline.')
    parser.add_argument('--relatorio', type=Path, default=ROOT / 'relatorios' / 'historico')
    parser.add_argument('--estado', type=Path, default=ROOT / 'estado_paper.json')
    parser.add_argument('--destino', type=Path, default=ROOT / 'painel')
    parser.add_argument('--capital-inicial', type=float, default=1000.0)
    args = parser.parse_args()
    if args.capital_inicial <= 0 or not math.isfinite(args.capital_inicial):
        parser.error('Capital inicial precisa ser positivo.')
    try:
        payload = build_payload(args.relatorio, args.estado, args.capital_inicial)
        write_panel_data(payload, args.destino)
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f'ERRO: {exc}\n')
    print(f'Painel exportado para {args.destino.resolve()}')
    print('Abra painel/index.html ou publique SOMENTE a pasta painel em um serviço estático.')
    print('OBS: a publicação estática não atualiza dados automaticamente; é necessário reexportar e republicar.')


if __name__ == '__main__':
    cli()
