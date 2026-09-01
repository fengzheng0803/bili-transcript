"""音频下载与 ffmpeg 命令构造/执行（规格 §3 ⑥）。"""
import shutil
import subprocess
from pathlib import Path

from bili_api import AudioStreamInfo, BiliApiError, HEADERS, LOGIN_HINT
from http_util import request_with_retry


def pick_best_audio(streams: list[AudioStreamInfo]) -> AudioStreamInfo:
    """选最高码率的音频流。"""
    if not streams:
        raise BiliApiError("该视频没有可下载的音频流")
    return max(streams, key=lambda s: s.bandwidth)


def _resolve_exe(name: str, dep_dir: Path) -> str:
    """优先 dep_dir/bin，其次系统 PATH；都没有则提示运行 setup.sh。"""
    local = dep_dir / "bin" / name
    if local.is_file():
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    raise BiliApiError(f"~/bilibili-dep/bin 和系统 PATH 都找不到 {name}，运行 setup.sh")


def run_ffmpeg(cmd: list[str], dep_dir: Path) -> subprocess.CompletedProcess:
    """执行 ffmpeg/ffprobe 命令，argv[0] 替换为解析后的可执行文件路径。"""
    real = [_resolve_exe(cmd[0], dep_dir), *cmd[1:]]
    return subprocess.run(real, check=True, capture_output=True, text=True)


def build_extract_audio_cmd(src: Path, dst: Path) -> list[str]:
    """容器转换抽取音轨（无重编码）。"""
    return ["ffmpeg", "-y", "-i", str(src), "-vn", "-c", "copy", str(dst)]


def build_probe_cmd(src: Path) -> list[str]:
    return ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(src)]


def build_slice_cmd(src: Path, out_pattern: Path, seconds: int = 600) -> list[str]:
    """按固定时长切片为 mp3（云转写上传用）。"""
    return ["ffmpeg", "-y", "-i", str(src), "-f", "segment",
            "-segment_time", str(seconds), "-acodec", "libmp3lame", str(out_pattern)]


def download_audio(url: str, dest: Path, request=request_with_retry,
                   headers=HEADERS) -> Path:
    resp = request("GET", url, headers=headers)
    if resp.status_code == 403:
        raise BiliApiError(LOGIN_HINT)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest
