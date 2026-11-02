#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preferências e dados do usuário.

Tudo fica em ``%APPDATA%\Semantorium`` (ou em ``LEXIMA_DATA_DIR``, usado nos testes).. O arquivo ``settings.json`` guarda:

  * configuração da análise;
  * documentos recentes;
  * favoritos;
  * histórico de análises;
  * modelos de análise/exportação criados pelo usuário.

A gravação é tolerante a falhas: um JSON corrompido não impede o aplicativo
de abrir — os valores padrão são usados e o arquivo é reescrito na próxima
alteração.
"""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SETTINGS_ENV = "_DATA_DIR"
_MAX_RECENT = 12
_MAX_HISTORY = 40

DEFAULTS: Dict = {
    "version": 1,
    "config": {},
    "preferred_format": "html",
    "recent": [],
    "favorites": [],
    "history": [],
    "templates": {},
    "ui_language": "pt-BR",
    "theme": "light",
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    "extraction_matrix": [],
    "prisma_counts": {},
    "prisma_checklist": {},
    "explore_filters": {},
    "last_tab": "",
    "last_tab_group": 0,
    "ollama_enabled": False,
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "llama3.2",
    "ollama_timeout": 300,
    "ollama_max_chars": 12000,
}


def data_dir() -> Path:
    """Diretório de dados do usuário (criado sob demanda)."""
    override = os.environ.get(SETTINGS_ENV)
    if override:
        return Path(override)
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "Semantorium"
    return Path.home() / ".semantorium"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _as_list(value) -> List:
    return value if isinstance(value, list) else []


def _as_dict(value) -> Dict:
    return value if isinstance(value, dict) else {}


def load_settings() -> Dict:
    """Carrega as preferências, preenchendo chaves ausentes."""
    path = settings_path()
    payload: Dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                payload = data
        except Exception:
            payload = {}

    settings = dict(DEFAULTS)
    settings.update({k: v for k, v in payload.items() if k in DEFAULTS})
    settings["config"] = _as_dict(settings.get("config"))
    settings["recent"] = _as_list(settings.get("recent"))[:_MAX_RECENT]
    settings["favorites"] = _as_list(settings.get("favorites"))
    settings["history"] = _as_list(settings.get("history"))[:_MAX_HISTORY]
    settings["templates"] = _as_dict(settings.get("templates"))
    settings["explore_filters"] = _as_dict(settings.get("explore_filters"))
    settings["preferred_format"] = str(
        settings.get("preferred_format") or "html"
    ).lower()
    return settings


def save_settings(settings: Dict) -> Path:
    """Grava as preferências de forma atômica."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULTS)
    payload.update(settings or {})
    payload["updated_at"] = _now()
    payload.pop("_dirty", None)
    handle, temp_name = tempfile.mkstemp(
        prefix="settings-", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass
    return path


def update_settings(patch: Dict) -> Dict:
    """Aplica um patch raso e devolve o estado atualizado."""
    settings = load_settings()
    for key, value in (patch or {}).items():
        if key in DEFAULTS:
            settings[key] = value
    save_settings(settings)
    return settings


# ---------------------------------------------------------------------------
# Documentos recentes e favoritos
# ---------------------------------------------------------------------------
def _document_entry(path: str, meta: Optional[Dict] = None) -> Dict:
    meta = meta or {}
    absolute = "",
    try:
        absolute = str(Path(path).resolve())
    except Exception:
        absolute = str(path or "")
    return {
        "path": absolute,
        "name": meta.get("filename") or Path(absolute).name,
        "at": _now(),
        "words": int(meta.get("words") or 0),
        "language": meta.get("language") or "",
    }


def record_recent(path: str, meta: Optional[Dict] = None) -> List[Dict]:
    """Marca um documento como recente (sem duplicatas)."""
    if not path:
        return load_settings().get("recent", [])
    settings = load_settings()
    entry = _document_entry(path, meta)
    recent = [item for item in settings.get("recent", [])
              if item.get("path") != entry["path"]]
    recent.insert(0, entry)
    settings["recent"] = recent[:_MAX_RECENT]
    save_settings(settings)
    return settings["recent"]


def recent_files() -> List[Dict]:
    return [
        item for item in load_settings().get("recent", [])
        if item.get("path")
    ]


def is_favorite(path: str) -> bool:
    if not path:
        return False
    try:
        target = str(Path(path).resolve())
    except Exception:
        target = str(path)
    return any(item.get("path") == target
               for item in load_settings().get("favorites", []))


def toggle_favorite(path: str, meta: Optional[Dict] = None) -> bool:
    """Adiciona/remove um favorito. Devolve True se ficou favoritado."""
    if not path:
        return False
    settings = load_settings()
    entry = _document_entry(path, meta)
    favorites = settings.get("favorites", [])
    remaining = [item for item in favorites
                 if item.get("path") != entry["path"]]
    if len(remaining) == len(favorites):
        remaining.insert(0, entry)
        active = True
    else:
        active = False
    settings["favorites"] = remaining
    save_settings(settings)
    return active


def favorites() -> List[Dict]:
    return [
        item for item in load_settings().get("favorites", [])
        if item.get("path")
    ]


# ---------------------------------------------------------------------------
# Histórico de análises
# ---------------------------------------------------------------------------
def record_history(path: str, meta: Optional[Dict], result: Dict) -> List[Dict]:
    """Registra uma análise concluída (metadados leves, sem o texto)."""
    result = result or {}
    meta = meta or result.get("meta") or {}
    settings = load_settings()
    entry = _document_entry(path, meta)
    entry.update({
        "language": result.get("language") or entry.get("language", ""),
        "language_label": result.get("language_label", ""),
        "sentences": int((result.get("stats") or {}).get("sentences") or 0),
        "summary": (result.get("summary") or "")[:280],
        "keywords": [item.get("keyword") for item in
                     (result.get("keywords") or [])[:8]],
        "duration": result.get("duration_seconds", 0),
        "warnings": len(result.get("warnings") or []),
        "engine": result.get("engine", ""),
    })
    history = [
        item for item in settings.get("history", [])
        if item.get("path") != entry["path"]
    ]
    history.insert(0, entry)
    settings["history"] = history[:_MAX_HISTORY]
    save_settings(settings)
    return settings["history"]


def history() -> List[Dict]:
    return [
        item for item in load_settings().get("history", [])
        if item.get("path")
    ]


def clear_history() -> None:
    settings = load_settings()
    settings["history"] = []
    save_settings(settings)


# ---------------------------------------------------------------------------
# Modelos (configurações nomeadas)
# ---------------------------------------------------------------------------
_TEMPLATE_NAME = re.compile(r"\s+")


def clean_template_name(name: str) -> str:
    return _TEMPLATE_NAME.sub(" ", (name or "").strip())[:60]


def list_templates() -> Dict[str, Dict]:
    return dict(load_settings().get("templates") or {})


def save_template(name: str, config: Dict,
                  preferred_format: str = "html") -> Dict:
    name = clean_template_name(name)
    if not name:
        raise ValueError("Informe um nome para o modelo.")
    settings = load_settings()
    templates = dict(settings.get("templates") or {})
    templates[name] = {
        "config": dict(config or {}),
        "preferred_format": (preferred_format or "html").lower(),
        "updated_at": _now(),
    }
    settings["templates"] = templates
    save_settings(settings)
    return templates


def delete_template(name: str) -> Dict:
    settings = load_settings()
    templates = dict(settings.get("templates") or {})
    templates.pop(clean_template_name(name), None)
    settings["templates"] = templates
    save_settings(settings)
    return templates


def config_from_dict(data: Optional[Dict], config_cls) -> object:
    """Constrói AnalysisConfig apenas com campos conhecidos e válidos."""
    cfg = config_cls()
    for key, value in (data or {}).items():
        if not hasattr(cfg, key) or key == "exclude_terms":
            continue
        current = getattr(cfg, key)
        try:
            if isinstance(current, bool):
                setattr(cfg, key, bool(value))
            elif isinstance(current, int) and not isinstance(current, bool):
                setattr(cfg, key, int(value))
            elif isinstance(current, float):
                setattr(cfg, key, float(value))
            elif isinstance(current, str):
                setattr(cfg, key, str(value))
        except (TypeError, ValueError):
            continue
    excluded = (data or {}).get("exclude_terms")
    if isinstance(excluded, list):
        cfg.exclude_terms = [str(item) for item in excluded if str(item).strip()]
    return cfg


def config_to_dict(config) -> Dict:
    """Serializa os campos públicos de AnalysisConfig."""
    data: Dict = {}
    for key in getattr(config, "__dataclass_fields__", {}):
        value = getattr(config, key, None)
        if isinstance(value, list):
            data[key] = list(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            data[key] = value
    return data
