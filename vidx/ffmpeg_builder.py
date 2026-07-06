"""
FFmpeg Command Builder & Runner
Constructs and executes FFmpeg command lines for compositing audio, background video/image,
and Advanced SubStation Alpha (.ass) subtitles into final MP4 video files.
"""

import subprocess
from pathlib import Path


class FFmpegBuilder:
    """Builds and executes FFmpeg commands for Scripture video rendering."""

    _cached_gpu_codec = None

    @classmethod
    def detect_best_video_codec(cls, requested_codec="auto") -> str:
        """
        Detect and return the best available video encoder.
        If requested_codec is not 'auto', returns requested_codec directly.
        Otherwise, tests GPU encoders in priority order: NVIDIA -> Intel -> AMD -> Apple -> CPU fallback.
        """
        if requested_codec and str(requested_codec).lower() != "auto":
            return requested_codec

        if cls._cached_gpu_codec is not None:
            return cls._cached_gpu_codec

        candidates = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"]
        for enc in candidates:
            try:
                res = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "nullsrc=s=256x256:d=0.1",
                        "-c:v",
                        enc,
                        "-f",
                        "null",
                        "-",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if res.returncode == 0:
                    cls._cached_gpu_codec = enc
                    return enc
            except Exception:
                pass

        cls._cached_gpu_codec = "libx264"
        return "libx264"

    def __init__(self, config=None):
        self.config = config or {}

    def _clean_filter_path(self, path):
        """
        Format path for FFmpeg filter strings on Windows/Linux.
        Converts backslashes to forward slashes and escapes Windows drive colons (C:/ -> C\\:/).
        """
        p = str(Path(path).resolve()).replace("\\", "/")
        if len(p) > 1 and p[1] == ":":
            p = p[0] + "\\:" + p[2:]
        return p

    def _get_audio_duration(self, audio_file, duration=None):
        if duration is not None:
            return float(duration)
        try:
            import mutagen

            audio_meta = mutagen.File(audio_file)
            if (
                audio_meta
                and audio_meta.info
                and getattr(audio_meta.info, "length", None)
            ):
                return float(audio_meta.info.length)
        except Exception:
            pass
        try:
            res = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(audio_file),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if res.returncode == 0 and res.stdout.strip():
                return float(res.stdout.strip())
        except Exception:
            pass
        return None

    def build_command(
        self,
        audio_file,
        subtitle_file,
        output_file,
        background_media=None,
        duration=None,
        watermark=None,
    ):
        """
        Construct a list of command arguments for running subprocess.Popen / run.
        """
        video_cfg = self.config.get("video", {})
        audio_cfg = self.config.get("audio", {})

        res_str = video_cfg.get("resolution", "1920x1080")
        if "x" in res_str:
            res_x, res_y = map(int, res_str.split("x"))
        else:
            res_x, res_y = 1920, 1080

        bg_media = background_media or video_cfg.get("background_media", "")
        if not bg_media or not Path(bg_media).exists():
            # If no background media provided, generate a black/color background source using lavfi
            bg_input = [
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={res_x}x{res_y}:r={video_cfg.get('fps', 24)}",
            ]
            is_image = False
        else:
            bg_path = Path(bg_media)
            ext = bg_path.suffix.lower()
            is_image = ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]

            if is_image:
                bg_input = [
                    "-loop",
                    "1",
                    "-framerate",
                    str(video_cfg.get("fps", 24)),
                    "-i",
                    str(bg_path),
                ]
            else:
                if video_cfg.get("loop_background", True):
                    bg_input = ["-stream_loop", "-1", "-i", str(bg_path)]
                else:
                    bg_input = ["-i", str(bg_path)]

        cmd = ["ffmpeg", "-y"]
        cmd.extend(bg_input)
        cmd.extend(["-i", str(Path(audio_file))])

        # Build video filter chain: scaling/padding -> subtitle overlay
        scaling_mode = video_cfg.get("scaling_mode", "pad").lower()
        if scaling_mode == "crop":
            scale_filter = f"scale={res_x}:{res_y}:force_original_aspect_ratio=increase,crop={res_x}:{res_y}"
        elif scaling_mode == "stretch":
            scale_filter = f"scale={res_x}:{res_y}"
        else:  # default 'pad'
            scale_filter = f"scale={res_x}:{res_y}:force_original_aspect_ratio=decrease,pad={res_x}:{res_y}:(ow-iw)/2:(oh-ih)/2"

        sub_path_clean = self._clean_filter_path(subtitle_file)

        title_image = video_cfg.get("title_image") or self.config.get(
            "bumpers", {}
        ).get("title_image")
        title_duration = float(
            video_cfg.get("title_duration")
            or self.config.get("bumpers", {}).get("title_duration")
            or 3.0
        )
        outro_image = video_cfg.get("outro_image") or self.config.get(
            "bumpers", {}
        ).get("outro_image")
        outro_start = float(
            video_cfg.get("outro_start")
            or self.config.get("bumpers", {}).get("outro_start")
            or 0.0
        )

        # Audio fade transitions
        fade_in = float(audio_cfg.get("fade_in_sec", 0.0) or 0.0)
        fade_out = float(audio_cfg.get("fade_out_sec", 0.0) or 0.0)
        af_list = []
        if fade_in > 0:
            af_list.append(f"afade=t=in:ss=0:d={fade_in}")
        if fade_out > 0:
            total_dur = self._get_audio_duration(audio_file, duration) or 300.0
            if total_dur > fade_out:
                st = max(0.0, float(total_dur) - fade_out)
                af_list.append(f"afade=t=out:st={st:.3f}:d={fade_out}")

        wm_cfg = (
            watermark
            or video_cfg.get("watermark")
            or video_cfg.get("logo")
            or self.config.get("watermark")
            or self.config.get("logo")
            or {}
        )
        wm_img = (
            wm_cfg.get("image")
            if isinstance(wm_cfg, dict)
            else (wm_cfg if isinstance(wm_cfg, str) else None)
        )

        if title_image or outro_image or wm_img:
            fc_parts = [f"[0:v]{scale_filter}[bg]"]
            curr_v = "[bg]"
            next_idx = 2
            if title_image:
                cmd.extend(["-i", str(Path(title_image))])
                fc_parts.append(
                    f"[{next_idx}:v]scale={res_x}:{res_y}:force_original_aspect_ratio=decrease,pad={res_x}:{res_y}:(ow-iw)/2:(oh-ih)/2[title]"
                )
                fc_parts.append(
                    f"{curr_v}[title]overlay=0:0:enable='between(t,0,{title_duration})'[v_in]"
                )
                curr_v = "[v_in]"
                next_idx += 1
            if outro_image and outro_start > 0:
                cmd.extend(["-i", str(Path(outro_image))])
                fc_parts.append(
                    f"[{next_idx}:v]scale={res_x}:{res_y}:force_original_aspect_ratio=decrease,pad={res_x}:{res_y}:(ow-iw)/2:(oh-ih)/2[outro]"
                )
                fc_parts.append(
                    f"{curr_v}[outro]overlay=0:0:enable='gte(t,{outro_start})'[v_out]"
                )
                curr_v = "[v_out]"
                next_idx += 1
            if wm_img:
                cmd.extend(["-i", str(Path(wm_img))])
                wm_pos = (
                    wm_cfg.get("position", "top-right")
                    if isinstance(wm_cfg, dict)
                    else "top-right"
                )
                wm_margin = wm_cfg.get("margin", 30) if isinstance(wm_cfg, dict) else 30
                if wm_pos == "top-left":
                    xy_str = f"{wm_margin}:{wm_margin}"
                elif wm_pos == "top-right":
                    xy_str = f"W-w-{wm_margin}:{wm_margin}"
                elif wm_pos == "bottom-left":
                    xy_str = f"{wm_margin}:H-h-{wm_margin}"
                elif wm_pos == "bottom-right":
                    xy_str = f"W-w-{wm_margin}:H-h-{wm_margin}"
                else:
                    xy_str = wm_pos

                logo_vf_list = []
                wm_scale = wm_cfg.get("scale") if isinstance(wm_cfg, dict) else None
                if wm_scale is not None:
                    if isinstance(wm_scale, float) and 0 < wm_scale <= 1.0:
                        w_px = int(res_x * wm_scale)
                        logo_vf_list.append(f"scale={w_px}:-1")
                    elif isinstance(wm_scale, int) and wm_scale > 0:
                        logo_vf_list.append(f"scale={wm_scale}:-1")
                wm_opacity = (
                    wm_cfg.get("opacity", 1.0) if isinstance(wm_cfg, dict) else 1.0
                )
                if wm_opacity is not None and float(wm_opacity) < 1.0:
                    logo_vf_list.append(
                        f"format=rgba,colorchannelmixer=aa={float(wm_opacity)}"
                    )

                wm_stream = f"[{next_idx}:v]"
                if logo_vf_list:
                    fc_parts.append(f"[{next_idx}:v]{','.join(logo_vf_list)}[logo]")
                    wm_stream = "[logo]"

                fc_parts.append(f"{curr_v}{wm_stream}overlay={xy_str}[v_wm]")
                curr_v = "[v_wm]"
                next_idx += 1

            fc_parts.append(f"{curr_v}ass='{sub_path_clean}'[v]")
            if af_list:
                fc_parts.append(f"[1:a]{','.join(af_list)}[a]")
                cmd.extend(
                    [
                        "-filter_complex",
                        ";".join(fc_parts),
                        "-map",
                        "[v]",
                        "-map",
                        "[a]",
                    ]
                )
            else:
                cmd.extend(
                    [
                        "-filter_complex",
                        ";".join(fc_parts),
                        "-map",
                        "[v]",
                        "-map",
                        "1:a",
                    ]
                )
        else:
            vf_chain = f"{scale_filter},ass='{sub_path_clean}'"
            cmd.extend(["-vf", vf_chain])
            if af_list:
                cmd.extend(["-af", ",".join(af_list)])

        # Video encoding settings
        codec_req = video_cfg.get("codec", "libx264")
        codec = self.detect_best_video_codec(codec_req)
        preset = video_cfg.get("preset", "fast")
        crf = str(video_cfg.get("crf", 23))

        cmd.extend(
            [
                "-c:v",
                codec,
                "-preset",
                preset,
                "-crf",
                crf,
                "-pix_fmt",
                "yuv420p",  # Ensure maximum media player compatibility
            ]
        )

        # Audio encoding settings
        a_codec = audio_cfg.get("codec", "aac")
        a_bitrate = audio_cfg.get("bitrate", "192k")

        cmd.extend(
            [
                "-c:a",
                a_codec,
                "-b:a",
                a_bitrate,
                "-ar",
                str(audio_cfg.get("sample_rate", 48000)),
            ]
        )

        # Duration control: match shortest stream (audio) unless explicit duration provided
        if duration is not None:
            cmd.extend(["-t", str(duration)])
        else:
            cmd.append("-shortest")

        cmd.append(str(Path(output_file)))
        return cmd

    def render(
        self,
        audio_file,
        subtitle_file,
        output_file,
        background_media=None,
        duration=None,
        progress_callback=None,
        job_id="default",
        worker_id=0,
        book=None,
        chapter=None,
        watermark=None,
    ):
        """
        Execute the FFmpeg render synchronously. Returns (success, stdout/stderr message).
        If progress_callback is provided, emits ProgressEvent objects during rendering.
        """
        cmd = self.build_command(
            audio_file, subtitle_file, output_file, background_media, duration, watermark=watermark
        )
        if not progress_callback:
            try:
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                return True, res.stderr or "Success"
            except subprocess.CalledProcessError as e:
                return False, f"FFmpeg error (code {e.returncode}):\n{e.stderr}"
            except Exception as e:
                return False, f"Execution error: {str(e)}"

        from .progress import ProgressEvent, parse_ffmpeg_progress_line

        # Determine total duration for percentage calculation if not explicitly provided
        total_dur = self._get_audio_duration(audio_file, duration)

        try:
            progress_callback(
                ProgressEvent(
                    job_id=str(job_id),
                    worker_id=int(worker_id),
                    status="ENCODING_VIDEO",
                    percent=0.0,
                    book=book,
                    chapter=chapter,
                    message="Starting FFmpeg encoding...",
                )
            )

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            output_lines = []
            while True:
                line = process.stdout.readline() if process.stdout else ""
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line)
                    metrics = parse_ffmpeg_progress_line(
                        line, total_duration_sec=total_dur
                    )
                    if metrics:
                        progress_callback(
                            ProgressEvent(
                                job_id=str(job_id),
                                worker_id=int(worker_id),
                                status="ENCODING_VIDEO",
                                percent=metrics["percent"],
                                book=book,
                                chapter=chapter,
                                speed=metrics["speed"],
                                fps=metrics["fps"],
                                elapsed_sec=metrics["elapsed_sec"],
                                eta_sec=metrics["eta_sec"],
                            )
                        )

            returncode = process.poll()
            if returncode == 0:
                progress_callback(
                    ProgressEvent(
                        job_id=str(job_id),
                        worker_id=int(worker_id),
                        status="COMPLETED",
                        percent=100.0,
                        book=book,
                        chapter=chapter,
                        message="Render completed successfully.",
                    )
                )
                return True, "".join(output_lines)
            else:
                progress_callback(
                    ProgressEvent(
                        job_id=str(job_id),
                        worker_id=int(worker_id),
                        status="ERROR",
                        percent=0.0,
                        book=book,
                        chapter=chapter,
                        message=f"FFmpeg exited with code {returncode}",
                    )
                )
                return (
                    False,
                    f"FFmpeg error (code {returncode}):\n{''.join(output_lines)}",
                )
        except Exception as e:
            progress_callback(
                ProgressEvent(
                    job_id=str(job_id),
                    worker_id=int(worker_id),
                    status="ERROR",
                    percent=0.0,
                    book=book,
                    chapter=chapter,
                    message=str(e),
                )
            )
            return False, f"Execution error: {str(e)}"
