from __future__ import annotations

import io
import json
import shutil
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import yaml

from app.config import Config
from app.services import speech_recognition as speech


VOCABULARY = (" ", "а", "б")


def make_wav_bytes(
    *,
    sample_rate: int = speech.SAMPLE_RATE,
    duration: float = 1.0,
    frequency: float = 440.0,
) -> bytes:
    count = int(sample_rate * duration)
    time = np.arange(count, dtype=np.float32) / sample_rate
    samples = (0.2 * np.sin(2 * np.pi * frequency * time) * 32767).astype(
        "<i2"
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(speech.CHANNELS)
        wav_file.setsampwidth(speech.SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    return buffer.getvalue()


def write_wav(path: Path, **kwargs) -> Path:
    path.write_bytes(make_wav_bytes(**kwargs))
    return path


def make_log_probs(labels: list[int], classes: int = 4) -> np.ndarray:
    values = np.full((len(labels), classes), -10.0, dtype=np.float32)
    for index, label in enumerate(labels):
        values[index, label] = 10.0
    return values


def write_gigaam_config(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump(
            {
                "preprocessor": {
                    "sample_rate": 16000,
                    "features": 64,
                    "n_fft": 400,
                    "win_length": 400,
                    "hop_length": 160,
                    "center": True,
                },
                "decoding": {"vocabulary": list(VOCABULARY)},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


def make_config(**values: str) -> Config:
    return Config.from_mapping(
        {"BOT_TOKEN": "123456:fake_token", **values}
    )


def test_load_gigaam_config(tmp_path: Path) -> None:
    path = write_gigaam_config(tmp_path / "v3_ctc.yaml")

    config = speech.load_gigaam_config(path)

    assert config.vocabulary == VOCABULARY
    assert config.sample_rate == 16000
    assert config.n_mels == 64
    assert config.n_fft == 400
    assert config.win_length == 400
    assert config.hop_length == 160
    assert config.center is True


def test_load_gigaam_config_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "v3_ctc.yaml"
    path.write_text(
        yaml.safe_dump({"decoding": {"vocabulary": [" ", "а"]}}),
        encoding="utf-8",
    )

    config = speech.load_gigaam_config(path)

    assert config.sample_rate == 16000
    assert config.n_mels == 64
    assert config.n_fft == 400
    assert config.win_length == 400
    assert config.hop_length == 160


@pytest.mark.parametrize(
    "content",
    [
        "not a mapping",
        yaml.safe_dump({"decoding": {}}),
        yaml.safe_dump({"decoding": {"vocabulary": []}}),
        yaml.safe_dump({"decoding": {"vocabulary": [1, 2]}}),
    ],
)
def test_load_gigaam_config_rejects_invalid_vocabulary(
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "v3_ctc.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(speech.RecognitionError):
        speech.load_gigaam_config(path)


def test_load_gigaam_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(speech.RecognitionError):
        speech.load_gigaam_config(tmp_path / "missing.yaml")


def test_feature_extractor_produces_expected_shape() -> None:
    config = speech.GigaAMConfig(
        vocabulary=VOCABULARY,
        sample_rate=16000,
        n_mels=64,
        n_fft=400,
        win_length=400,
        hop_length=160,
        center=True,
    )
    extractor = speech.GigaAMFeatureExtractor(config)
    waveform = (
        np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 0.2
    ).astype(np.float32)

    features, lengths = extractor(waveform)

    assert features.shape == (1, 64, 101)
    assert lengths.tolist() == [101]
    assert np.isfinite(features).all()


def test_feature_extractor_uses_gigaam_v3_window() -> None:
    config = speech.GigaAMConfig(
        vocabulary=VOCABULARY,
        sample_rate=16000,
        n_mels=64,
        n_fft=320,
        win_length=320,
        hop_length=160,
        center=False,
    )
    extractor = speech.GigaAMFeatureExtractor(config)
    waveform = np.zeros(16000, dtype=np.float32)

    features, lengths = extractor(waveform)

    assert features.shape == (1, 64, 99)
    assert lengths.tolist() == [99]


def test_feature_extractor_rejects_empty_audio() -> None:
    config = speech.GigaAMConfig(
        vocabulary=VOCABULARY,
        sample_rate=16000,
        n_mels=64,
        n_fft=400,
        win_length=400,
        hop_length=160,
        center=True,
    )
    extractor = speech.GigaAMFeatureExtractor(config)

    with pytest.raises(speech.RecognitionError):
        extractor(np.array([], dtype=np.float32))


def test_ctc_greedy_decode_collapses_repeats_and_blanks() -> None:
    log_probs = make_log_probs([1, 1, 3, 2, 3, 2])

    assert speech.ctc_greedy_decode(log_probs, 6, VOCABULARY) == "абб"


def test_ctc_greedy_decode_respects_encoded_length() -> None:
    log_probs = make_log_probs([1, 3, 2, 3, 2])

    assert speech.ctc_greedy_decode(log_probs, 3, VOCABULARY) == "аб"


def test_ctc_greedy_decode_accepts_batched_output() -> None:
    log_probs = make_log_probs([1, 3, 2]).reshape(1, 3, 4)

    assert speech.ctc_greedy_decode(log_probs, 3, VOCABULARY) == "аб"


def test_ctc_greedy_decode_returns_empty_text() -> None:
    log_probs = make_log_probs([3, 3, 3])

    assert speech.ctc_greedy_decode(log_probs, 3, VOCABULARY) == ""


def test_ctc_greedy_decode_rejects_unknown_token() -> None:
    log_probs = make_log_probs([1, 5], classes=6)

    with pytest.raises(speech.RecognitionError):
        speech.ctc_greedy_decode(log_probs, 2, VOCABULARY)


class FakeOnnxInput:
    def __init__(self, name: str, value_type: str) -> None:
        self.name = name
        self.type = value_type


class FakeOnnxSession:
    def __init__(self, log_probs: np.ndarray, lengths: np.ndarray) -> None:
        self.log_probs = log_probs
        self.lengths = lengths
        self.feeds: dict[str, np.ndarray] = {}

    def get_inputs(self) -> list[FakeOnnxInput]:
        return [
            FakeOnnxInput("features", "tensor(float)"),
            FakeOnnxInput("feature_lengths", "tensor(int64)"),
        ]

    def get_outputs(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(name="log_probs"),
            SimpleNamespace(name="encoded_lengths"),
        ]

    def run(self, names, feeds):
        self.feeds = dict(feeds)
        assert names == ["log_probs", "encoded_lengths"]
        assert self.feeds["features"].dtype == np.float32
        return [self.log_probs, self.lengths]


def test_gigaam_recognizer_uses_onnx_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "v3_ctc_int8.onnx"
    model_path.write_bytes(b"fake model")
    write_gigaam_config(tmp_path / "v3_ctc_int8.yaml")
    audio_path = write_wav(tmp_path / "circle.wav")
    log_probs = make_log_probs([1, 3, 2, 2]).reshape(1, 4, 4)
    lengths = np.array([[4]], dtype=np.int64)
    session = FakeOnnxSession(log_probs, lengths)
    monkeypatch.setattr(
        speech,
        "_create_onnx_session",
        lambda path: session,
    )

    recognizer = speech.GigaAMOnnxRecognizer(model_path)

    assert recognizer.transcribe(audio_path) == "аб"
    assert session.feeds["feature_lengths"].tolist() == [101]


def test_gigaam_recognizer_requires_model_file(tmp_path: Path) -> None:
    with pytest.raises(speech.RecognitionError):
        speech.GigaAMOnnxRecognizer(tmp_path / "missing.onnx")


def test_gigaam_recognizer_requires_config_file(tmp_path: Path) -> None:
    model_path = tmp_path / "v3_ctc_int8.onnx"
    model_path.write_bytes(b"fake model")

    with pytest.raises(speech.RecognitionError):
        speech.GigaAMOnnxRecognizer(model_path)


def test_vosk_recognizer_transcribes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "vosk"
    model_path.mkdir()
    audio_path = write_wav(tmp_path / "circle.wav")

    class FakeModel:
        def __init__(self, path: str) -> None:
            self.path = path

    class FakeKaldiRecognizer:
        def __init__(self, model: FakeModel, sample_rate: int) -> None:
            self.model = model
            self.sample_rate = sample_rate
            self.received = 0

        def AcceptWaveform(self, chunk: bytes) -> bool:
            self.received += len(chunk)
            return False

        def FinalResult(self) -> str:
            return json.dumps({"text": " привет "})

    fake_vosk = SimpleNamespace(
        Model=FakeModel,
        KaldiRecognizer=FakeKaldiRecognizer,
    )
    monkeypatch.setattr(speech, "_import_vosk", lambda: fake_vosk)

    recognizer = speech.VoskRecognizer(model_path)

    assert recognizer.transcribe(audio_path) == "привет"


def test_vosk_recognizer_requires_model(tmp_path: Path) -> None:
    with pytest.raises(speech.RecognitionError):
        speech.VoskRecognizer(tmp_path / "missing")


def test_vosk_recognizer_rejects_invalid_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "vosk"
    model_path.mkdir()
    audio_path = write_wav(tmp_path / "circle.wav")

    class FakeModel:
        def __init__(self, path: str) -> None:
            pass

    class FakeKaldiRecognizer:
        def __init__(self, model: FakeModel, sample_rate: int) -> None:
            pass

        def AcceptWaveform(self, chunk: bytes) -> bool:
            return False

        def FinalResult(self) -> str:
            return "not json"

    fake_vosk = SimpleNamespace(
        Model=FakeModel,
        KaldiRecognizer=FakeKaldiRecognizer,
    )
    monkeypatch.setattr(speech, "_import_vosk", lambda: fake_vosk)

    with pytest.raises(speech.RecognitionError):
        speech.VoskRecognizer(model_path).transcribe(audio_path)


class FakeRecognizer:
    def __init__(self, text: str = "привет") -> None:
        self.text = text
        self.audio_path: Path | None = None
        self.samples = 0

    def transcribe(self, audio_path: Path) -> str:
        self.audio_path = audio_path
        self.samples = speech._read_pcm16_wav(audio_path).size
        return self.text


def make_fake_bot(wav_bytes: bytes | None = None) -> MagicMock:
    bot = MagicMock()
    bot.get_file = AsyncMock(
        return_value=SimpleNamespace(file_path="voice/file.ogg")
    )

    async def download(file_path: str, destination: Path) -> None:
        Path(destination).write_bytes(wav_bytes or make_wav_bytes())

    bot.download_file = AsyncMock(side_effect=download)
    return bot


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is missing")
@pytest.mark.asyncio
async def test_service_downloads_extracts_and_recognizes(
    tmp_path: Path,
) -> None:
    recognizer = FakeRecognizer("текст поздравления")
    service = speech.SpeechRecognitionService(
        make_fake_bot(),
        recognizer,
        ffmpeg_path="ffmpeg",
        temp_dir=tmp_path / "work",
    )

    result = await service.recognize_file_id("file-id")

    assert result == "текст поздравления"
    assert recognizer.samples > 0
    assert list((tmp_path / "work").iterdir()) == []


@pytest.mark.asyncio
async def test_service_rejects_empty_file_id(tmp_path: Path) -> None:
    bot = make_fake_bot()
    service = speech.SpeechRecognitionService(
        bot,
        FakeRecognizer(),
        temp_dir=tmp_path / "work",
    )

    with pytest.raises(speech.RecognitionError):
        await service.recognize_file_id("  ")

    bot.get_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_wraps_download_error(tmp_path: Path) -> None:
    bot = make_fake_bot()
    bot.get_file = AsyncMock(side_effect=RuntimeError("telegram is down"))
    service = speech.SpeechRecognitionService(
        bot,
        FakeRecognizer(),
        temp_dir=tmp_path / "work",
    )

    with pytest.raises(speech.RecognitionError, match="download"):
        await service.recognize_file_id("file-id")

    assert list((tmp_path / "work").iterdir()) == []


@pytest.mark.asyncio
async def test_service_wraps_missing_ffmpeg(tmp_path: Path) -> None:
    service = speech.SpeechRecognitionService(
        make_fake_bot(),
        FakeRecognizer(),
        ffmpeg_path=tmp_path / "missing-ffmpeg",
        temp_dir=tmp_path / "work",
    )

    with pytest.raises(speech.RecognitionError):
        await service.recognize_file_id("file-id")

    assert list((tmp_path / "work").iterdir()) == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is missing")
@pytest.mark.asyncio
async def test_service_wraps_recognition_error(tmp_path: Path) -> None:
    class FailingRecognizer:
        def transcribe(self, audio_path: Path) -> str:
            raise RuntimeError("engine crashed")

    service = speech.SpeechRecognitionService(
        make_fake_bot(),
        FailingRecognizer(),
        ffmpeg_path="ffmpeg",
        temp_dir=tmp_path / "work",
    )

    with pytest.raises(speech.RecognitionError, match="recognition"):
        await service.recognize_file_id("file-id")

    assert list((tmp_path / "work").iterdir()) == []


def test_create_recognizer_requires_configured_paths() -> None:
    with pytest.raises(speech.RecognitionError):
        speech.create_recognizer(make_config())

    with pytest.raises(speech.RecognitionError):
        speech.create_recognizer(make_config(SPEECH_ENGINE="vosk"))


def test_create_recognizer_selects_gigaam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, object] = {}

    class DummyGigaAM:
        def __init__(self, model_path: str, config_path: str | None) -> None:
            created["model_path"] = model_path
            created["config_path"] = config_path

    monkeypatch.setattr(speech, "GigaAMOnnxRecognizer", DummyGigaAM)

    recognizer = speech.create_recognizer(
        make_config(
            SPEECH_ENGINE="gigaam",
            GIGAAM_MODEL_PATH="model.onnx",
            GIGAAM_CONFIG_PATH="model.yaml",
        )
    )

    assert isinstance(recognizer, DummyGigaAM)
    assert created == {
        "model_path": "model.onnx",
        "config_path": "model.yaml",
    }


def test_create_recognizer_selects_vosk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, object] = {}

    class DummyVosk:
        def __init__(self, model_path: str) -> None:
            created["model_path"] = model_path

    monkeypatch.setattr(speech, "VoskRecognizer", DummyVosk)

    recognizer = speech.create_recognizer(
        make_config(SPEECH_ENGINE="vosk", VOSK_MODEL_PATH="vosk")
    )

    assert isinstance(recognizer, DummyVosk)
    assert created == {"model_path": "vosk"}


def test_create_recognition_service_uses_injected_recognizer() -> None:
    recognizer = FakeRecognizer()

    service = speech.create_recognition_service(
        make_fake_bot(),
        make_config(FFMPEG_PATH="ffmpeg-custom"),
        recognizer=recognizer,
    )

    assert isinstance(service, speech.SpeechRecognitionService)
    assert service._recognizer is recognizer
    assert service._ffmpeg_path == "ffmpeg-custom"
