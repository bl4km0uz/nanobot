from nanobot.config.schema import Config


def test_heartbeat_model_override_accepts_camel_case() -> None:
    cfg = Config.model_validate(
        {"gateway": {"heartbeat": {"modelOverride": "openai/gpt-4.1-mini"}}}
    )

    assert cfg.gateway.heartbeat.model_override == "openai/gpt-4.1-mini"


def test_heartbeat_model_override_accepts_legacy_model_key() -> None:
    cfg = Config.model_validate(
        {"gateway": {"heartbeat": {"model": "openrouter/anthropic/claude-3.5-haiku"}}}
    )

    assert cfg.gateway.heartbeat.model_override == "openrouter/anthropic/claude-3.5-haiku"
