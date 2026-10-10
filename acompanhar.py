#!/usr/bin/env python3
"""Acompanhamento LOCAL de paper trading. Nunca envia ordens financeiras."""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from painel_export import build_payload, write_panel_data
from robo import paper_once

ROOT = Path(__file__).resolve().parent


def check_and_export(estado: Path, relatorio: Path, destino: Path):
    status = paper_once(estado)
    payload = build_payload(relatorio, estado)
    write_panel_data(payload, destino)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'[{timestamp}] Checagem paper trading (SIMULADA) concluída. '
          f'Patrimônio simulado: R$ {status["equity_brl"]:.2f}. '
          f'Painel atualizado em {destino}.', flush=True)
    print(' | '.join(status['events']), flush=True)
    return status


def cli():
    parser = argparse.ArgumentParser(description='Roda simulação de BTCBRL e atualiza painel local.')
    parser.add_argument('--estado', type=Path, default=ROOT / 'estado_paper.json')
    parser.add_argument('--relatorio', type=Path, default=ROOT / 'relatorios' / 'historico')
    parser.add_argument('--destino', type=Path, default=ROOT / 'painel')
    parser.add_argument('--intervalo-minutos', type=int, default=5)
    parser.add_argument('--uma-vez', action='store_true', help='Uma checagem apenas; bom para Agendador de Tarefas/cron.')
    args = parser.parse_args()
    if args.intervalo_minutos < 1:
        parser.error('Intervalo mínimo de 1 minuto.')
    print('MODO PAPER: apenas operações virtuais. Nenhuma ordem real será enviada.', flush=True)
    while True:
        try:
            check_and_export(args.estado, args.relatorio, args.destino)
        except (ValueError, OSError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
            print(f'ERRO: {exc}. Últimos dados publicados preservados.', file=sys.stderr, flush=True)
            if args.uma_vez:
                return 1
        if args.uma_vez:
            return 0
        try:
            time.sleep(args.intervalo_minutos * 60)
        except KeyboardInterrupt:
            print('\nAcompanhamento simulado interrompido pelo usuário.')
            return 0


if __name__ == '__main__':
    sys.exit(cli())
