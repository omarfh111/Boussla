from boussla.config import Settings


def test_settings_never_expose_secrets():
    s = Settings(openai_chat_model="m", _secrets={"OPENAI_API_KEY": "sk-test-SECRET"})
    assert s.secret("OPENAI_API_KEY") == "sk-test-SECRET"
    assert "SECRET" not in repr(s) and "SECRET" not in str(s.describe())
    assert s.describe()["openai_key"] == "set"


def test_missing_secret_is_none():
    s = Settings()
    assert s.secret("OPENAI_API_KEY") is None and s.describe()["openai_key"] == "missing"
