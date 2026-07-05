import pytest
import wave
import struct
from pathlib import Path
from vidx.bumpers import get_media_duration, prepare_bumper_audio
from vidx.usfm_parser import TimingParser
from vidx.ffmpeg_builder import FFmpegBuilder


def create_dummy_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 44100):
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        n_samples = int(duration_sec * sample_rate)
        data = struct.pack("<" + ("h" * n_samples), *([0] * n_samples))
        wav_file.writeframes(data)


def test_get_media_duration(tmp_path):
    wav_path = tmp_path / "test_2sec.wav"
    create_dummy_wav(wav_path, duration_sec=2.5)
    dur = get_media_duration(str(wav_path))
    assert abs(dur - 2.5) < 0.1


def test_timing_parser_shift_timestamps():
    content = "\\c 1\n0.0\t2.0\ts1\n2.0\t4.5\t1a\n4.5\t8.0\t1b"
    parser = TimingParser(content)
    assert parser.entries[0]["start"] == 0.0
    assert parser.entries[0]["end"] == 2.0

    parser.shift_timestamps(5.0)
    assert parser.entries[0]["start"] == 5.0
    assert parser.entries[0]["end"] == 7.0
    assert parser.entries[1]["start"] == 7.0
    assert parser.entries[1]["end"] == 9.5
    assert parser.entries[2]["start"] == 9.5
    assert parser.entries[2]["end"] == 13.0


def test_prepare_bumper_audio(tmp_path):
    intro = tmp_path / "intro.wav"
    bible = tmp_path / "bible.wav"
    outro = tmp_path / "outro.wav"
    out_audio = tmp_path / "combined.wav"

    create_dummy_wav(intro, 2.0)
    create_dummy_wav(bible, 4.0)
    create_dummy_wav(outro, 3.0)

    success, intro_dur, total_dur = prepare_bumper_audio(
        main_audio=str(bible),
        output_audio=str(out_audio),
        intro_audio=str(intro),
        outro_audio=str(outro),
    )

    assert success
    assert out_audio.exists()
    assert abs(intro_dur - 2.0) < 0.1
    assert abs(total_dur - 9.0) < 0.1
    assert abs(get_media_duration(str(out_audio)) - 9.0) < 0.1


def test_ffmpeg_builder_with_title_card(tmp_path):
    audio_f = tmp_path / "audio.mp3"
    sub_f = tmp_path / "sub.ass"
    out_f = tmp_path / "out.mp4"
    title_img = tmp_path / "title.png"

    audio_f.write_text("dummy")
    sub_f.write_text("dummy")
    title_img.write_text("dummy")

    config = {"video": {"title_image": str(title_img), "title_duration": 5.0}}
    builder = FFmpegBuilder(config)
    cmd = builder.build_command(
        audio_file=audio_f,
        subtitle_file=sub_f,
        output_file=out_f,
        background_media=None,
    )

    cmd_str = " ".join(str(c) for c in cmd)
    assert str(title_img) in cmd_str
    assert "overlay" in cmd_str
    assert "between(t,0,5.0)" in cmd_str or "between(t,0,5)" in cmd_str


def test_convert_to_ass_with_bumpers_config(tmp_path):
    usfm = tmp_path / "test.SFM"
    usfm.write_text(
        "\\id GEN\n\\c 1\n\\s1 Title\n\\v 1 In beginning.", encoding="utf-8"
    )
    timing = tmp_path / "timing.txt"
    timing.write_text(
        "\\c 1\n\\level phrase\n\\separators .\n0.0\t2.0\ts1\n2.0\t4.0\t1a",
        encoding="utf-8",
    )
    intro = tmp_path / "intro.wav"
    create_dummy_wav(intro, 5.0)

    out_ass = tmp_path / "out.ass"
    from vidx.ass_generator import convert_to_ass

    config = {"bumpers": {"intro_audio": str(intro)}}
    success = convert_to_ass(usfm, timing, out_ass, config=config)
    assert success
    content = out_ass.read_text(encoding="utf-8")
    assert "0:00:05.00" in content


def test_prepare_bumper_audio_with_background_music(tmp_path):
    main_wav = tmp_path / "main.wav"
    bgm_wav = tmp_path / "bgm.wav"
    out_wav = tmp_path / "out_bgm.wav"

    create_dummy_wav(main_wav, duration_sec=4.0)
    create_dummy_wav(bgm_wav, duration_sec=1.0)

    success, intro_dur, total_dur = prepare_bumper_audio(
        main_audio=str(main_wav),
        output_audio=str(out_wav),
        background_music=str(bgm_wav),
        bg_music_volume=0.2,
    )

    assert success
    assert out_wav.exists()
    assert abs(total_dur - 4.0) < 0.2
    assert abs(get_media_duration(str(out_wav)) - 4.0) < 0.2
