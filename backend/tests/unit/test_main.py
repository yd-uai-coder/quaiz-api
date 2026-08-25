"""ENVIRONMENT=production時にSwagger UI/ReDoc/OpenAPIスキーマが無効化されることを検証する。"""

import importlib
import os

import app.core.config as config_module
import app.main as main_module


def _reload_main_with_environment(environment: str) -> object:
    """ENVIRONMENTを切り替えてapp.core.config/app.mainを再構築し、構築後のappを返す。

    `settings`はapp.core.configのモジュール変数として一度だけ生成されるため、
    ENVIRONMENTの変更を反映させるにはconfigモジュール自体もreloadする必要がある
    （main.py側でget_settings.cache_clear()するだけでは、main.pyがimport時に
    束縛した古いsettingsオブジェクトは変わらない）。
    """
    original_environment = os.environ.get("ENVIRONMENT")
    os.environ["ENVIRONMENT"] = environment
    try:
        importlib.reload(config_module)
        reloaded = importlib.reload(main_module)
        return reloaded.app
    finally:
        if original_environment is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = original_environment
        importlib.reload(config_module)
        importlib.reload(main_module)


def test_docs_routes_disabled_in_production() -> None:
    app = _reload_main_with_environment("production")

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_docs_routes_enabled_outside_production() -> None:
    app = _reload_main_with_environment("test")

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"
