from __future__ import annotations

from pathlib import Path

from app.core.config import Config, Settings


def test_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    cfg = Config(path)
    cfg.update(consent_accepted=True, output_format="mp3", rvc_f0up_key=2)
    cfg2 = Config(path)
    assert cfg2.settings.consent_accepted is True
    assert cfg2.settings.output_format == "mp3"
    assert cfg2.settings.rvc_f0up_key == 2


def test_settings_from_dict_ignores_unknown() -> None:
    s = Settings.from_dict({"consent_accepted": True, "bogus": 1})
    assert s.consent_accepted is True
    assert not hasattr(s, "bogus")
