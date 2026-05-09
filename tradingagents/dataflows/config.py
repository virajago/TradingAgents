import contextvars
import tradingagents.default_config as default_config
from typing import Dict, Optional

_config_var: contextvars.ContextVar[Optional[Dict]] = contextvars.ContextVar(
    "tradingagents_config", default=None
)


def set_config(config: Dict) -> None:
    """Set the configuration for the current context, merged over defaults."""
    merged = default_config.DEFAULT_CONFIG.copy()
    merged.update(config)
    _config_var.set(merged)


def get_config() -> Dict:
    """Get the current configuration, falling back to defaults if not set."""
    val = _config_var.get()
    if val is None:
        return default_config.DEFAULT_CONFIG.copy()
    return val.copy()


def initialize_config() -> None:
    """No-op: kept for backward compatibility; config is now context-local."""
    pass
