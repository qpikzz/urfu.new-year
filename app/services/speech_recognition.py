"""Speech recognition pipeline for circle moderation (INFRA 5.1-5.2)."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from app.config import Config

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SAMPLE_WIDTH_BYTES = 2
CHANNELS = 1
DEFAULT_N_MELS = 64
VOSK_CHUNK_FRAMES = 4000


class SpeechEngine(StrEnum):
    GIGAAM = "gigaam"
    VOSK = "vosk"


class RecognitionError(RuntimeError):
    """Raised when a circle cannot be downloaded, converted or recognized."""


@runtime_checkable
class Recognizer(Protocol):
    """Synchronous speech recognizer run in a worker thread."""

    def transcribe(self, audio_path: Path) -> str:
        """Return recognized text for a 16 kHz mono PCM WAV file."""


@dataclass(frozen=True, slots=True)
class GigaAMConfig:
    vocabulary: tuple[str, ...]
    sample_rate: int
    n_mels: int
    n_fft: int
    win_length: int
    hop_length: int
    center: bool


def load_gigaam_config(path: str | Path) -> GigaAMConfig:
    """Load the configuration written by ``GigaAM.to_onnx``."""
    config_path = Path(path)
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RecognitionError("PyYAML is required for GigaAM") from exc

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecognitionError("GigaAM config file is unavailable") from exc
    except yaml.YAMLError as exc:
        raise RecognitionError("GigaAM config file is invalid") from exc

    if not isinstance(raw, dict):
        raise RecognitionError("GigaAM config must be a mapping")

    preprocessor = raw.get("preprocessor") or {}
    decoding = raw.get("decoding") or {}
    if not isinstance(preprocessor, dict):
        preprocessor = {}
    if not isinstance(decoding, dict):
        decoding = {}

    vocabulary = decoding.get("vocabulary")
    if (
        not isinstance(vocabulary, list)
        or not vocabulary
        or not all(isinstance(token, str) for token in vocabulary)
    ):
        raise RecognitionError(
            "GigaAM config must contain a charwise CTC vocabulary"
        )

    sample_rate = _positive_int(preprocessor, "sample_rate", SAMPLE_RATE)
    n_mels = _positive_int(preprocessor, "features", DEFAULT_N_MELS)
    hop_length = _positive_int(
        preprocessor,
        "hop_length",
        max(1, sample_rate // 100),
    )
    win_length = _positive_int(
        preprocessor,
        "win_length",
        max(1, sample_rate // 40),
    )
    n_fft = _positive_int(preprocessor, "n_fft", max(1, sample_rate // 40))
    center = bool(preprocessor.get("center", True))

    return GigaAMConfig(
        vocabulary=tuple(vocabulary),
        sample_rate=sample_rate,
        n_mels=n_mels,
        n_fft=n_fft,
        win_length=win_length,
        hop_length=hop_length,
        center=center,
    )


def _positive_int(values: dict[str, Any], key: str, default: int) -> int:
    raw = values.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RecognitionError(f"GigaAM config value {key} must be an integer") from exc
    if value <= 0:
        raise RecognitionError(f"GigaAM config value {key} must be positive")
    return value


def _hz_to_mel(frequency: float) -> float:
    return 2595.0 * np.log10(1.0 + frequency / 700.0)


def _mel_to_hz(mel: float | np.ndarray) -> float | np.ndarray:
    return 700.0 * (10.0 ** (np.asarray(mel) / 2595.0) - 1.0)


def _mel_filterbank(
    n_mels: int,
    n_fft: int,
    sample_rate: int,
) -> np.ndarray:
    """Build the HTK mel filterbank used by torchaudio's MelSpectrogram."""
    n_freqs = n_fft // 2 + 1
    all_freqs = np.linspace(0.0, sample_rate // 2, n_freqs)
    mel_points = np.linspace(
        _hz_to_mel(0.0),
        _hz_to_mel(sample_rate / 2),
        n_mels + 2,
    )
    hz_points = _mel_to_hz(mel_points)
    differences = hz_points[1:] - hz_points[:-1]
    slopes = hz_points[None, :] - all_freqs[:, None]
    down = -slopes[:, :-2] / differences[:-1]
    up = slopes[:, 2:] / differences[1:]
    return np.maximum(0.0, np.minimum(down, up)).astype(np.float32)


class GigaAMFeatureExtractor:
    """Log-mel features compatible with GigaAM's ONNX input."""

    def __init__(self, config: GigaAMConfig) -> None:
        self._config = config
        self._window = np.hanning(config.win_length + 1)[:-1].astype(
            np.float32
        )
        self._mel = _mel_filterbank(
            config.n_mels,
            config.n_fft,
            config.sample_rate,
        )

    def __call__(self, waveform: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        signal = np.asarray(waveform, dtype=np.float32).reshape(-1)
        if signal.size == 0:
            raise RecognitionError("Audio stream is empty")

        config = self._config
        if config.center:
            pad = config.n_fft // 2
            if signal.size <= pad:
                raise RecognitionError("Audio stream is too short")
            signal = np.pad(signal, (pad, pad), mode="reflect")

        if signal.size < config.win_length:
            signal = np.pad(
                signal,
                (0, config.win_length - signal.size),
                mode="constant",
            )

        frames = np.lib.stride_tricks.sliding_window_view(
            signal,
            config.win_length,
        )[:: config.hop_length]
        if frames.size == 0:
            raise RecognitionError("Audio stream is too short")

        spectrum = np.fft.rfft(
            frames * self._window,
            n=config.n_fft,
            axis=1,
        )
        power = spectrum.real**2 + spectrum.imag**2
        mel = power @ self._mel
        log_mel = np.log(np.clip(mel, 1e-9, 1e9))
        features = np.ascontiguousarray(
            log_mel.T[None, :, :].astype(np.float32)
        )
        lengths = np.array([features.shape[2]], dtype=np.int64)
        return features, lengths


def _read_pcm16_wav(path: Path) -> np.ndarray:
    try:
        with wave.open(str(path), "rb") as wav_file:
            if wav_file.getnchannels() != CHANNELS:
                raise RecognitionError("Audio must be mono")
            if wav_file.getframerate() != SAMPLE_RATE:
                raise RecognitionError("Audio must have a 16 kHz sample rate")
            if wav_file.getsampwidth() != SAMPLE_WIDTH_BYTES:
                raise RecognitionError("Audio must be signed 16-bit PCM")
            frames = wav_file.readframes(wav_file.getnframes())
    except (OSError, wave.Error) as exc:
        raise RecognitionError("Audio file is invalid") from exc

    if not frames:
        raise RecognitionError("Audio stream is empty")
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def ctc_greedy_decode(
    log_probs: np.ndarray,
    encoded_length: int,
    vocabulary: Sequence[str],
) -> str:
    """Collapse CTC output into text using the GigaAM vocabulary."""
    if log_probs.ndim == 3:
        log_probs = log_probs[0]
    if log_probs.ndim != 2:
        raise RecognitionError("CTC output must be two-dimensional")

    time_steps = min(int(encoded_length), log_probs.shape[0])
    if time_steps <= 0:
        return ""

    labels = np.argmax(log_probs[:time_steps], axis=-1)
    blank_id = len(vocabulary)
    previous: int | None = None
    tokens: list[str] = []
    for token_id in labels.tolist():
        if token_id == previous:
            continue
        previous = token_id
        if token_id == blank_id:
            continue
        if not 0 <= token_id < len(vocabulary):
            raise RecognitionError("CTC output contains an unknown token")
        tokens.append(vocabulary[token_id])
    return "".join(tokens).strip()


def _create_onnx_session(path: str) -> Any:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 3
    return ort.InferenceSession(
        path,
        providers=["CPUExecutionProvider"],
        sess_options=options,
    )


def _session_input_dtype(session: Any) -> np.dtype[Any]:
    type_map = {
        "tensor(float16)": np.dtype(np.float16),
        "tensor(float)": np.dtype(np.float32),
        "tensor(double)": np.dtype(np.float64),
    }
    for session_input in session.get_inputs():
        dtype = type_map.get(session_input.type)
        if dtype is not None:
            return dtype
    return np.dtype(np.float32)


class GigaAMOnnxRecognizer:
    """Primary GigaAM v3 CTC recognizer running on ONNX Runtime CPU."""

    def __init__(
        self,
        model_path: str | Path,
        config_path: str | Path | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        if not self._model_path.is_file():
            raise RecognitionError("GigaAM ONNX model is unavailable")

        self._config_path = (
            Path(config_path)
            if config_path is not None
            else self._model_path.with_suffix(".yaml")
        )
        self._config = load_gigaam_config(self._config_path)
        self._extractor = GigaAMFeatureExtractor(self._config)
        self._session = _create_onnx_session(str(self._model_path))
        session_inputs = self._session.get_inputs()
        if len(session_inputs) < 2:
            raise RecognitionError("GigaAM ONNX model has an unexpected input")
        self._input_names = tuple(item.name for item in session_inputs[:2])
        self._output_names = tuple(
            item.name for item in self._session.get_outputs()
        )

    def transcribe(self, audio_path: Path) -> str:
        waveform = _read_pcm16_wav(audio_path)
        features, lengths = self._extractor(waveform)
        dtype = _session_input_dtype(self._session)
        outputs = self._session.run(
            list(self._output_names),
            {
                self._input_names[0]: features.astype(dtype),
                self._input_names[1]: lengths,
            },
        )
        if len(outputs) < 2:
            raise RecognitionError("GigaAM ONNX model returned no lengths")

        encoded_lengths = np.asarray(outputs[1]).reshape(-1)
        if encoded_lengths.size == 0:
            raise RecognitionError("GigaAM ONNX model returned no lengths")
        return ctc_greedy_decode(
            np.asarray(outputs[0]),
            int(encoded_lengths[0]),
            self._config.vocabulary,
        )


def _import_vosk() -> Any:
    try:
        import vosk
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RecognitionError("Vosk is not installed") from exc
    return vosk


class VoskRecognizer:
    """Fallback Vosk small recognizer."""

    def __init__(self, model_path: str | Path) -> None:
        path = Path(model_path)
        if not path.exists():
            raise RecognitionError("Vosk model is unavailable")

        vosk = _import_vosk()
        try:
            self._model = vosk.Model(str(path))
        except Exception as exc:
            raise RecognitionError("Vosk model could not be loaded") from exc
        self._vosk = vosk

    def transcribe(self, audio_path: Path) -> str:
        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                if wav_file.getnchannels() != CHANNELS:
                    raise RecognitionError("Audio must be mono")
                if wav_file.getframerate() != SAMPLE_RATE:
                    raise RecognitionError("Audio must have a 16 kHz sample rate")
                if wav_file.getsampwidth() != SAMPLE_WIDTH_BYTES:
                    raise RecognitionError("Audio must be signed 16-bit PCM")

                recognizer = self._vosk.KaldiRecognizer(
                    self._model,
                    SAMPLE_RATE,
                )
                while True:
                    chunk = wav_file.readframes(VOSK_CHUNK_FRAMES)
                    if not chunk:
                        break
                    recognizer.AcceptWaveform(chunk)
        except (OSError, wave.Error) as exc:
            raise RecognitionError("Audio file is invalid") from exc

        try:
            result = json.loads(recognizer.FinalResult())
        except (TypeError, ValueError) as exc:
            raise RecognitionError("Vosk returned an invalid result") from exc
        if not isinstance(result, dict):
            raise RecognitionError("Vosk returned an invalid result")
        return str(result.get("text", "")).strip()


class SpeechRecognitionService:
    """Download a circle, extract its audio and recognize speech."""

    def __init__(
        self,
        bot: Any,
        recognizer: Recognizer,
        *,
        ffmpeg_path: str | Path = "ffmpeg",
        temp_dir: str | Path | None = None,
    ) -> None:
        self._bot = bot
        self._recognizer = recognizer
        self._ffmpeg_path = str(ffmpeg_path)
        self._temp_dir = Path(temp_dir) if temp_dir is not None else None

    async def recognize_file_id(self, file_id: str) -> str:
        if not isinstance(file_id, str) or not file_id.strip():
            raise RecognitionError("Telegram file_id is empty")

        try:
            if self._temp_dir is not None:
                self._temp_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory(
                prefix="urfu27bot-",
                dir=self._temp_dir,
            ) as raw_dir:
                work_dir = Path(raw_dir)
                source_path = work_dir / "circle.bin"
                audio_path = work_dir / "circle.wav"

                await self._download(file_id, source_path)
                await self._extract_audio(source_path, audio_path)
                try:
                    text = await asyncio.to_thread(
                        self._recognizer.transcribe,
                        audio_path,
                    )
                except RecognitionError:
                    raise
                except Exception as exc:
                    raise RecognitionError(
                        "Speech recognition failed"
                    ) from exc

                logger.info("Speech recognized: chars=%s", len(text))
                return text
        except OSError as exc:
            raise RecognitionError("Temporary audio storage failed") from exc

    async def _download(self, file_id: str, destination: Path) -> None:
        try:
            telegram_file = await self._bot.get_file(file_id)
            file_path = telegram_file.file_path
            if not file_path:
                raise RecognitionError("Telegram returned no file path")
            await self._bot.download_file(file_path, destination=destination)
        except RecognitionError:
            raise
        except Exception as exc:
            raise RecognitionError("Failed to download the circle") from exc

    async def _extract_audio(
        self,
        source_path: Path,
        audio_path: Path,
    ) -> None:
        command = (
            self._ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            str(CHANNELS),
            "-ar",
            str(SAMPLE_RATE),
            "-acodec",
            "pcm_s16le",
            "-f",
            "wav",
            str(audio_path),
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise RecognitionError("ffmpeg is unavailable") from exc

        _, error = await process.communicate()
        if process.returncode != 0:
            logger.error(
                "ffmpeg audio extraction failed: code=%s",
                process.returncode,
            )
            raise RecognitionError("ffmpeg failed to extract audio")
        if error:
            logger.debug("ffmpeg diagnostics were produced")


def create_recognizer(config: Config) -> Recognizer:
    """Create the configured speech recognizer."""
    engine = config.speech_engine.strip().lower()
    if engine == SpeechEngine.GIGAAM:
        if not config.gigaam_model_path:
            raise RecognitionError("GIGAAM_MODEL_PATH is required")
        return GigaAMOnnxRecognizer(
            config.gigaam_model_path,
            config.gigaam_config_path,
        )
    if engine == SpeechEngine.VOSK:
        if not config.vosk_model_path:
            raise RecognitionError("VOSK_MODEL_PATH is required")
        return VoskRecognizer(config.vosk_model_path)
    raise RecognitionError("Unsupported speech engine")


def create_recognition_service(
    bot: Any,
    config: Config,
    *,
    recognizer: Recognizer | None = None,
    temp_dir: str | Path | None = None,
) -> SpeechRecognitionService:
    """Build the full recognition service from configuration."""
    return SpeechRecognitionService(
        bot,
        recognizer if recognizer is not None else create_recognizer(config),
        ffmpeg_path=config.ffmpeg_path,
        temp_dir=temp_dir,
    )


__all__ = [
    "CHANNELS",
    "GigaAMConfig",
    "GigaAMFeatureExtractor",
    "GigaAMOnnxRecognizer",
    "RecognitionError",
    "Recognizer",
    "SAMPLE_RATE",
    "SpeechEngine",
    "SpeechRecognitionService",
    "VoskRecognizer",
    "create_recognition_service",
    "create_recognizer",
    "ctc_greedy_decode",
    "load_gigaam_config",
]
