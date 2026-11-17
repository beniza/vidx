"""Tests for the Bible Brain import feature (offline: a fake client replaces the API)."""
import sys
from unittest.mock import patch

import pytest

from vidx.biblebrain import (
    BibleBrainClient, BibleBrainError, CachedClient, eligible_bibles, to_usfm,
    stamps_to_rows, import_chapter, jobs_yaml, run_biblebrain,
    parse_chapters, import_book, run_biblebrain_batch,
)
from vidx.usfm_parser import USFMParser, TimingParser

RAW = [
    {"abbr": "MALMAL", "name": "Malayalam Bible",
     "filesets": {"dbp-prod": [{"id": "MALMALN_ET", "type": "text_plain", "size": "NT"},
                               {"id": "MALMALN1DA", "type": "audio", "size": "NT"}]}},
    {"abbr": "XXXONE", "name": "Text only",
     "filesets": {"dbp-prod": [{"id": "XXXONE", "type": "text_plain", "size": "C"}]}},
    {"abbr": "YYYTWO", "name": "Audio only",
     "filesets": {"dbp-prod": [{"id": "YYYTWO1DA", "type": "audio_drama", "size": "C"}]}},
    {"abbr": "ZZZTHR", "name": "Stream only",
     "filesets": {"dbp-prod": [{"id": "ZZZTHRSA", "type": "audio_stream", "size": "C"},
                               {"id": "ZZZTHR", "type": "text_plain", "size": "C"}]}},
]


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path_factory, monkeypatch):
    """Never touch the real ~/.vidx cache from tests."""
    monkeypatch.setenv("VIDX_BB_CACHE", str(tmp_path_factory.mktemp("bbcache") / "cache.json"))


class FakeClient:
    """Stands in for BibleBrainClient; the audio 'download' writes a stub file."""

    def __init__(self, with_timing=True, max_chapter=None):
        self.with_timing = with_timing
        self.max_chapter = max_chapter
        self.calls = {"countries": 0, "languages": 0, "bibles": 0}

    def bible(self, bible_id):
        return RAW[0] if bible_id == "MALMAL" else None

    def countries(self):
        self.calls["countries"] += 1
        return [{"name": "India", "codes": {"iso_a2": "IN"}}]

    def languages(self, country):
        self.calls["languages"] += 1
        assert country == "IN"
        return [{"name": "Malayalam", "iso": "mal"}, {"name": "Textonly", "iso": "xxx"}]

    def bibles(self, code):
        self.calls["bibles"] += 1
        return RAW[:1] if code == "mal" else RAW[1:2]

    def chapter_text(self, fileset_id, book, chapter):
        if self.max_chapter and chapter > self.max_chapter:
            return []
        return [("1", "First verse."), ("2", "Second verse."), ("3", "Third verse.")]

    def chapter_audio(self, fileset_id, book, chapter):
        return "https://cdn.example/x.mp3?sig=1", 30.0

    def timestamps(self, fileset_id, book, chapter):
        if not self.with_timing:
            return []
        return [("1", None, 0.0), ("2", None, 10.0), ("3", None, 20.0)]

    def download(self, url, dest):
        open(dest, "wb").write(b"mp3")


def test_filter_keeps_only_text_plus_downloadable_audio():
    assert [o.bible_id for o in eligible_bibles(RAW)] == ["MALMAL"]


def test_usfm_roundtrips_through_vidx_parser():
    usfm = to_usfm("1CO", 2, [("1", "One."), ("2", "Two.")], "Test")
    p = USFMParser(usfm, target_chapter="2")
    assert len(p.verses) == 2


def test_stamps_become_contiguous_rows_with_range_ids():
    rows = stamps_to_rows([("2", "3", 5.0), ("1", None, 0.0), ("0", None, 0.0)], total=12.5)
    assert rows == [(0.0, 5.0, "1"), (5.0, 12.5, "2-3")]


def test_import_chapter_biblebrain_timing_parses(tmp_path):
    opts = eligible_bibles(RAW)
    res = import_chapter(FakeClient(), opts[0], "1CO", 3, tmp_path, "biblebrain", total_hint=30.0)
    t = TimingParser(res["timing"].read_text(encoding="utf-8"), filepath=res["timing"])
    assert t.chapter == "3" and len(t.entries) == 3
    assert res["audio"].name == "03_1CO.mp3"  # chapter must be the FIRST number in the stem


def test_import_chapter_vidx_timing_leaves_timing_to_align(tmp_path):
    opts = eligible_bibles(RAW)
    res = import_chapter(FakeClient(), opts[0], "MRK", 1, tmp_path, "vidx", total_hint=30.0)
    assert not res["timing"].exists()
    assert res["timing"].name == "MRK-01-timing.txt"  # same name --align writes


def test_jobs_yaml_loads_as_vidx_config(tmp_path):
    from vidx.config import Config
    opts = eligible_bibles(RAW)
    res = import_chapter(FakeClient(), opts[0], "MRK", 1, tmp_path, "biblebrain", total_hint=30.0)
    (tmp_path / "jobs.yaml").write_text(jobs_yaml([res], tmp_path / "out"), encoding="utf-8")
    cfg = Config(config_path=str(tmp_path / "jobs.yaml"))
    assert len(cfg.raw_config["jobs"]) == 1


def test_wizard_end_to_end(tmp_path):
    answers = iter(["1", "1", "1", "MRK", "1", "", "y"])  # country, language, bible, book, ch, last, use BB timing
    out = []
    run_biblebrain(FakeClient(), tmp_path, ask=lambda _p: next(answers), say=out.append)
    assert (tmp_path / "bb_jobs.yaml").exists()
    assert any("Textonly" in line for line in out) is False  # language without audio omitted


def test_missing_key_rejected(monkeypatch):
    monkeypatch.delenv("BIBLE_BRAIN_KEY", raising=False)
    with pytest.raises(BibleBrainError):
        BibleBrainClient("")


def test_cli_biblebrain_flag_runs_wizard(tmp_path, monkeypatch):
    from vidx.cli import main
    answers = iter(["1", "1", "1", "MRK", "1", "", "y"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    monkeypatch.setenv("BIBLE_BRAIN_KEY", "test-key")
    with patch("vidx.cli.BibleBrainClient", return_value=FakeClient()):
        with patch.object(sys, "argv", ["vidx", "--biblebrain", "--bb-out", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc:
                main()
    assert exc.value.code == 0
    assert (tmp_path / "bb_jobs.yaml").exists()


def test_cli_biblebrain_timing_vidx_skips_probe(tmp_path, monkeypatch):
    from vidx.cli import main
    answers = iter(["1", "1", "1", "MRK", "1", ""])  # no timing question asked
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    monkeypatch.setenv("BIBLE_BRAIN_KEY", "test-key")
    with patch("vidx.cli.BibleBrainClient", return_value=FakeClient()):
        with patch.object(sys, "argv", ["vidx", "--biblebrain", "--bb-out", str(tmp_path),
                                        "--bb-timing", "vidx"]):
            with pytest.raises(SystemExit):
                main()
    assert not list(tmp_path.rglob("*-timing.txt"))


# ---- cache ---------------------------------------------------------------
def test_cache_serves_second_lookup_without_api_call(tmp_path):
    inner = FakeClient()
    c = CachedClient(inner, tmp_path / "c.json")
    c.countries(); c.countries()
    c.languages("IN"); c.languages("IN")
    c.bibles("mal"); c.bibles("mal")
    assert inner.calls == {"countries": 1, "languages": 1, "bibles": 1}


def test_cache_persists_across_instances_and_expires(tmp_path):
    inner = FakeClient()
    CachedClient(inner, tmp_path / "c.json").countries()
    CachedClient(inner, tmp_path / "c.json").countries()
    assert inner.calls["countries"] == 1
    CachedClient(inner, tmp_path / "c.json", ttl=-1).countries()  # everything is stale
    assert inner.calls["countries"] == 2


def test_cache_refresh_bypasses_but_updates(tmp_path):
    inner = FakeClient()
    CachedClient(inner, tmp_path / "c.json").countries()
    CachedClient(inner, tmp_path / "c.json", refresh=True).countries()
    assert inner.calls["countries"] == 2
    CachedClient(inner, tmp_path / "c.json").countries()
    assert inner.calls["countries"] == 2


def test_cache_holds_no_secrets_and_survives_corruption(tmp_path):
    path = tmp_path / "c.json"
    inner = FakeClient()
    inner.api_key = "SECRET-KEY"
    CachedClient(inner, path).bibles("mal")
    text = path.read_text(encoding="utf-8")
    assert "SECRET-KEY" not in text and "sig=" not in text
    path.write_text("{not json", encoding="utf-8")
    assert CachedClient(inner, path).bibles("mal")  # falls back to the API, no crash


def test_cache_passes_content_calls_through(tmp_path):
    c = CachedClient(FakeClient(), tmp_path / "c.json")
    assert c.chapter_text("x", "MRK", 1)[0][0] == "1"


# ---- chapters / whole book -----------------------------------------------
def test_parse_chapters():
    assert parse_chapters("1-3,5") == [1, 2, 3, 5]
    assert parse_chapters("7") == [7]
    assert parse_chapters("all") is None
    for bad in ("", "0", "3-1", "a-b", "1,,2"):
        with pytest.raises(ValueError):
            parse_chapters(bad)


def test_import_book_all_stops_at_first_missing_chapter(tmp_path):
    opts = eligible_bibles(RAW)
    imports, failures = import_book(FakeClient(max_chapter=4), opts[0], "MRK", None,
                                    tmp_path, "biblebrain", say=lambda m: None)
    assert [i["name"] for i in imports] == [f"MRK-0{n}" for n in (1, 2, 3, 4)]
    assert failures == []  # running off the end of the book is not a failure


def test_import_book_explicit_range_reports_failures_and_continues(tmp_path):
    opts = eligible_bibles(RAW)
    imports, failures = import_book(FakeClient(max_chapter=2), opts[0], "MRK", [1, 2, 3, 4],
                                    tmp_path, "biblebrain", say=lambda m: None)
    assert len(imports) == 2
    assert [f[0] for f in failures] == [3, 4]


def test_import_book_all_with_nothing_found_raises(tmp_path):
    opts = eligible_bibles(RAW)
    with pytest.raises(BibleBrainError):
        import_book(FakeClient(max_chapter=0 or None) if False else _NoText(), opts[0], "XXX", None,
                    tmp_path, "biblebrain", say=lambda m: None)


class _NoText(FakeClient):
    def chapter_text(self, *a):
        return []


# ---- scripted (non-interactive) mode ------------------------------------
def test_batch_mode_whole_book_auto_timing(tmp_path):
    jobs, failures = run_biblebrain_batch(FakeClient(max_chapter=3), tmp_path, bible_id="MALMAL",
                                          language="mal", book="MRK", chapters=None,
                                          timing="auto", say=lambda m: None)
    assert failures == [] and jobs.exists()
    assert len(list(tmp_path.rglob("*-timing.txt"))) == 3  # auto picked Bible Brain timing


def test_batch_mode_auto_falls_back_to_vidx_when_no_timing(tmp_path):
    out = []
    jobs, _ = run_biblebrain_batch(FakeClient(with_timing=False, max_chapter=2), tmp_path,
                                   bible_id="MALMAL", language="mal", book="MRK", chapters=None,
                                   timing="auto", say=out.append)
    assert not list(tmp_path.rglob("*-timing.txt"))
    assert any("--align" in line for line in out)


def test_batch_mode_resolves_bible_without_language(tmp_path):
    jobs, _ = run_biblebrain_batch(FakeClient(max_chapter=1), tmp_path, bible_id="MALMAL",
                                   language=None, book="MRK", chapters=[1],
                                   timing="biblebrain", say=lambda m: None)
    assert jobs.exists()


def test_batch_mode_unknown_bible_or_no_text_audio_is_an_error(tmp_path):
    with pytest.raises(BibleBrainError):
        run_biblebrain_batch(FakeClient(), tmp_path, bible_id="NOPE00", language=None, book="MRK",
                             chapters=[1], timing="auto", say=lambda m: None)
    with pytest.raises(BibleBrainError):  # exists, but text only
        run_biblebrain_batch(FakeClient(), tmp_path, bible_id="XXXONE", language="xxx", book="MRK",
                             chapters=[1], timing="auto", say=lambda m: None)


def test_cli_scripted_whole_book(tmp_path, monkeypatch):
    from vidx.cli import main
    monkeypatch.setenv("BIBLE_BRAIN_KEY", "test-key")
    monkeypatch.setenv("VIDX_BB_CACHE", str(tmp_path / "cache.json"))
    monkeypatch.setattr("builtins.input", lambda _p="": pytest.fail("scripted mode must not prompt"))
    with patch("vidx.cli.BibleBrainClient", return_value=FakeClient(max_chapter=2)):
        with patch.object(sys, "argv", ["vidx", "--biblebrain", "--bb-bible", "MALMAL",
                                        "--bb-language", "mal", "--bb-book", "mrk",
                                        "--bb-chapters", "all", "--bb-out", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc:
                main()
    assert exc.value.code == 0
    assert (tmp_path / "bb_jobs.yaml").exists()


def test_cli_scripted_requires_book(tmp_path, monkeypatch, capsys):
    from vidx.cli import main
    monkeypatch.setenv("BIBLE_BRAIN_KEY", "test-key")
    with patch("vidx.cli.BibleBrainClient", return_value=FakeClient()):
        with patch.object(sys, "argv", ["vidx", "--biblebrain", "--bb-bible", "MALMAL",
                                        "--bb-out", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc:
                main()
    assert exc.value.code == 1
    assert "--bb-book" in capsys.readouterr().out


def test_cli_scripted_exit_code_is_1_when_a_chapter_fails(tmp_path, monkeypatch):
    from vidx.cli import main
    monkeypatch.setenv("BIBLE_BRAIN_KEY", "test-key")
    monkeypatch.setenv("VIDX_BB_CACHE", str(tmp_path / "cache.json"))
    with patch("vidx.cli.BibleBrainClient", return_value=FakeClient(max_chapter=1)):
        with patch.object(sys, "argv", ["vidx", "--biblebrain", "--bb-bible", "MALMAL",
                                        "--bb-book", "MRK", "--bb-chapters", "1-3",
                                        "--bb-out", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc:
                main()
    assert exc.value.code == 1
