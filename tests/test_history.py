from __future__ import annotations

from app.core.history import HistoryStore


def test_history_crud(tmp_path) -> None:
    store = HistoryStore(tmp_path / "h.db")
    rec_id = store.add("tts", "音色A", "C:/out/a.wav", 3.5, input_text="你好", params={"speed": 1.2})
    rows = store.list()
    assert len(rows) == 1
    assert rows[0]["id"] == rec_id
    assert rows[0]["params"]["speed"] == 1.2
    store.delete(rec_id)
    assert store.list() == []


def test_history_clear(tmp_path) -> None:
    store = HistoryStore(tmp_path / "h.db")
    store.add("vc", "音色B", "C:/out/b.wav", 2.0)
    store.add("tts", "音色B", "C:/out/c.wav", 1.0)
    store.clear()
    assert store.list() == []
