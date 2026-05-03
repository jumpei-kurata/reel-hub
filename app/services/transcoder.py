import asyncio

import imageio_ffmpeg


async def to_h264_mp4(input_path: str, output_path: str) -> None:
    """入力動画をH.264 MP4に変換する（HEVC/MOV等のInstagram非対応フォーマット対策）"""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-y",
        output_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"動画変換エラー: {stderr.decode(errors='replace')[-500:]}")
