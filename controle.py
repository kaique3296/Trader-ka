#!/usr/bin/env python3
"""Comandos autorizados de controle do robô educacional (somente paper)."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from robo import save_json
import json

ALLOWED = {'checar', 'iniciar', 'pausar', 'encerrar'}
ISSUE_TO_ACTION = {'TRADERKA_START': 'iniciar', 'TRADERKA_PAUSE': 'pausar', 'TRADERKA_CLOSE': 'encerrar'}
DEFAULT = {'modo': 'pausado', 'ultimo_comando': 'inicial', 'atualizado_utc': None}


def normalize_action(raw: str) -> str:
    raw = str(raw or 'checar').strip()
    action = ISSUE_TO_ACTION.get(raw, raw)
    if action not in ALLOWED:
        raise ValueError('Comando não permitido')
    return action


def load_control(path: Path) -> dict:
    if not path.exists():
        return dict(DEFAULT)
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('modo') not in ('ativo', 'pausado'):
        raise ValueError('Estado do controle inválido; nenhuma entrada executada.')
    return data


def apply_command(control: dict, action: str) -> tuple[dict, bool, bool]:
    """Retorna controle, indicador de início novo, solicitação de fechamento."""
    action = normalize_action(action)
    updated = dict(control)
    was_active = control.get('modo') == 'ativo'
    new_start = action == 'iniciar' and not was_active
    close_position = action == 'encerrar'
    if action == 'iniciar':
        updated['modo'] = 'ativo'
    elif action in ('pausar', 'encerrar'):
        updated['modo'] = 'pausado'
    if action != 'checar':
        updated['ultimo_comando'] = action
        updated['atualizado_utc'] = datetime.now(timezone.utc).isoformat()
    return updated, new_start, close_position


def save_control(path: Path, data: dict) -> None:
    save_json(path, data)
