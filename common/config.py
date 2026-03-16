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
