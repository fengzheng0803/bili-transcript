from pathlib import Path

import pytest

import audio
from audio import (AudioStreamInfo, BiliApiError, _resolve_exe, build_extract_audio_cmd,
                   build_probe_cmd, build_slice_cmd, download_audio, pick_best_audio, run_ffmpeg)


def test_pick_best_audio_max_bandwidth():
    streams = [AudioStreamInfo("u1", 64000), AudioStreamInfo("u2", 128000),
               AudioStreamInfo("u3", 96000)]
    assert pick_best_audio(streams).url == "u2"


def test_pick_best_audio_empty():
    with pytest.raises(BiliApiError, match="音频流"):
        pick_best_audio([])


def test_build_extract_audio_cmd():
    assert build_extract_audio_cmd(Path("raw.m4s"), Path("out.m4a")) == [
        "ffmpeg", "-y", "-i", "raw.m4s", "-vn", "-c", "copy", "out.m4a"]


def test_build_slice_cmd():
    cmd = build_slice_cmd(Path("a.m4a"), Path("work/chunk_%03d.mp3"), 600)
    assert cmd[0] == "ffmpeg" and "-y" in cmd
    assert "-segment_time" in cmd and "600" in cmd
    assert "work/chunk_%03d.mp3" in cmd


def test_build_probe_cmd():
    cmd = build_probe_cmd(Path("a.m4a"))
    assert cmd[0] == "ffprobe"
    assert cmd[-1] == "a.m4a"


def test_resolve_exe_prefers_dep_dir(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "ffmpeg").write_text("")
    assert _resolve_exe("ffmpeg", tmp_path) == str(tmp_path / "bin" / "ffmpeg")


def test_resolve_exe_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    with pytest.raises(BiliApiError, match="setup.sh"):
        _resolve_exe("ffmpeg", tmp_path)


def test_run_ffmpeg_substitutes_path(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    ff = tmp_path / "bin" / "ffmpeg"
    ff.write_text("")
    calls = []
    monkeypatch.setattr(audio.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or None)
    run_ffmpeg(["ffmpeg", "-y", "a", "b"], tmp_path)
    assert calls and calls[0][0] == str(ff)


def test_download_audio_403_hints_cookie(tmp_path):
    class Resp403:
        status_code = 403

        def raise_for_status(self):
            raise RuntimeError()

    with pytest.raises(BiliApiError, match="cookie"):
        download_audio("http://x", tmp_path / "a.m4s", request=lambda m, u, **kw: Resp403())


def test_download_audio_writes_bytes(tmp_path):
    class RespOK:
        status_code = 200
        content = b"audio-data"

        def raise_for_status(self):
            pass

    dest = download_audio("http://x", tmp_path / "a.m4s", request=lambda m, u, **kw: RespOK())
    assert dest.read_bytes() == b"audio-data"
