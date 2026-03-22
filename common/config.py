"""
PaperTerrace 統合設定管理モジュール。

dynaconf を使用して common/settings.toml の設定を一元管理する。

優先順位 (高→低):
  1. 実際の環境変数 (K8s Secret / OS 環境変数)
  2. local-files/secrets/.env (ローカル秘密情報)
  3. common/settings.toml の環境セクション ([local] / [prod])
  4. common/settings.toml の [default] セクション

使用方法:
  from common.config import settings
  model = settings.MODEL_CHAT
  db_url = settings.get("DATABASE_URL")
"""

from pathlib import Path

from dotenv import load_dotenv
from dynaconf import Dynaconf

# common/ の親 = プロジェクトルート
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_SETTINGS_TOML = Path(__file__).parent / "settings.toml"
_SECRETS_ENV = _PROJECT_ROOT / "local-files" / "secrets" / ".env"

# secrets/.env を os.environ に一度だけロード（ローカル開発用・K8s では存在しない）
if _SECRETS_ENV.exists():
    load_dotenv(_SECRETS_ENV, override=False)

settings = Dynaconf(
    # 環境変数プレフィックスなし（既存の APP_ENV, DATABASE_URL 等をそのまま読む）
    envvar_prefix=False,
    # common/settings.toml（Docker イメージに収録）
    settings_file=str(_SETTINGS_TOML),
    # [default] → [local] or [prod] の階層ロードを有効化
    # default_env は指定しない（指定すると [default] セクションが無視される）
    environments=True,
    env_switcher="APP_ENV",
)


def _log_overrides():
    """設定のソース（環境変数、TOMLセクション、デフォルト）を判定してログ出力する。"""
    import os
    import sys
    import tomllib

    try:
        # settings.toml を読み込んで各セクションの定義を把握
        with open(_SETTINGS_TOML, "rb") as f:
            toml_data = tomllib.load(f)

        app_env = str(settings.get("APP_ENV", "local")).lower()
        if app_env in ("production", "prod"):
            env_section = "prod"
        elif app_env == "staging":
            env_section = "staging"
        else:
            env_section = "local"

        # セクションごとにキーを抽出
        default_keys = set(toml_data.get("default", {}).keys())
        env_keys = set(toml_data.get(env_section, {}).keys())
        
        # .env に書かれているキーを抽出
        env_file_keys = set()
        if _SECRETS_ENV.exists():
            with open(_SECRETS_ENV, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        env_file_keys.add(line.split("=", 1)[0].strip().upper())

        # 全ての既知のアプリ設定キー
        all_app_keys = (default_keys | env_keys | env_file_keys)
        
        # ソースを判定
        messages = []
        for key in sorted(all_app_keys, key=str.upper):
            key_upper = key.upper()
            val = settings.get(key_upper)
            if val is None:
                continue

            # ソース判定
            if key_upper in os.environ:
                source = "ENV"
            elif key_upper in [k.upper() for k in env_keys]:
                source = f"TOML:[{env_section}]"
            elif key_upper in [k.upper() for k in default_keys]:
                source = "TOML:[default]"
            else:
                source = "UNKNOWN"

            # 秘密情報のマスク
            str_val = str(val)
            if any(s in key_upper for s in ["KEY", "SECRET", "PASSWORD", "TOKEN", "URL"]):
                display_val = (
                    str_val[:4] + "..." + str_val[-4:]
                    if len(str_val) > 8 else "****"
                )
            else:
                display_val = str_val
            
            messages.append(f"{key_upper}={display_val} ({source})")

        if messages:
            print("--- Effective Configuration ---", file=sys.stdout)
            for msg in messages:
                print(f"  {msg}", file=sys.stdout)
            print("-------------------------------", file=sys.stdout, flush=True)

    except Exception:
        pass


_log_overrides()


def _get_app_env() -> str:
    """現在の環境を正規化して返す（prod / staging / local）。"""
    env = str(settings.get("APP_ENV", "local")).lower()
    if env in ("production", "prod"):
        return "prod"
    if env == "staging":
        return "staging"
    return "local"


def get_redis_url() -> str:
    """環境に応じた Redis URL を返す。

    環境別の優先順位:
      prod    : REDIS_URL
      staging : REDIS_URL_STAGING → REDIS_URL
      local   : REDIS_URL_LOCAL   → REDIS_URL → redis://localhost:6379/0
    """
    _default = "redis://localhost:6379/0"
    env = _get_app_env()
    if env == "prod":
        return settings.get("REDIS_URL", _default)
    if env == "staging":
        return settings.get("REDIS_URL_STAGING") or settings.get("REDIS_URL", _default)
    return settings.get("REDIS_URL_LOCAL") or settings.get("REDIS_URL", _default)
