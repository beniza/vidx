"""
FFmpeg Command Builder & Runner
Constructs and executes FFmpeg command lines for compositing audio, background video/image,
and Advanced SubStation Alpha (.ass) subtitles into final MP4 video files.
"""
import subprocess
from pathlib import Path


class FFmpegBuilder:
    """Builds and executes FFmpeg commands for Scripture video rendering."""
    
    def __init__(self, config=None):
        self.config = config or {}
        
    def _clean_filter_path(self, path):
        """
        Format path for FFmpeg filter strings on Windows/Linux.
        Converts backslashes to forward slashes and escapes Windows drive colons (C:/ -> C\\:/).
        """
        p = str(Path(path).resolve()).replace('\\', '/')
        if len(p) > 1 and p[1] == ':':
            p = p[0] + '\\:' + p[2:]
        return p
        
    def build_command(self, audio_file, subtitle_file, output_file, background_media=None, duration=None):
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
            bg_input = ["-f", "lavfi", "-i", f"color=c=black:s={res_x}x{res_y}:r={video_cfg.get('fps', 24)}"]
            is_image = False
        else:
            bg_path = Path(bg_media)
            ext = bg_path.suffix.lower()
            is_image = ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
            
            if is_image:
                bg_input = ["-loop", "1", "-framerate", str(video_cfg.get("fps", 24)), "-i", str(bg_path)]
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
        vf_chain = f"{scale_filter},ass='{sub_path_clean}'"
        
        cmd.extend(["-vf", vf_chain])
        
        # Video encoding settings
        codec = video_cfg.get("codec", "libx264")
        preset = video_cfg.get("preset", "fast")
        crf = str(video_cfg.get("crf", 23))
        
        cmd.extend([
            "-c:v", codec,
            "-preset", preset,
            "-crf", crf,
            "-pix_fmt", "yuv420p"  # Ensure maximum media player compatibility
        ])
        
        # Audio encoding settings
        a_codec = audio_cfg.get("codec", "aac")
        a_bitrate = audio_cfg.get("bitrate", "192k")
        
        cmd.extend([
            "-c:a", a_codec,
            "-b:a", a_bitrate,
            "-ar", str(audio_cfg.get("sample_rate", 48000))
        ])
        
        # Duration control: match shortest stream (audio) unless explicit duration provided
        if duration is not None:
            cmd.extend(["-t", str(duration)])
        else:
            cmd.append("-shortest")
            
        cmd.append(str(Path(output_file)))
        return cmd
        
    def render(self, audio_file, subtitle_file, output_file, background_media=None, duration=None,
               progress_callback=None, job_id="default", worker_id=0, book=None, chapter=None):
        """
        Execute the FFmpeg render synchronously. Returns (success, stdout/stderr message).
        If progress_callback is provided, emits ProgressEvent objects during rendering.
        """
        cmd = self.build_command(audio_file, subtitle_file, output_file, background_media, duration)
        if not progress_callback:
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                return True, res.stderr or "Success"
            except subprocess.CalledProcessError as e:
                return False, f"FFmpeg error (code {e.returncode}):\n{e.stderr}"
            except Exception as e:
                return False, f"Execution error: {str(e)}"
                
        from .progress import ProgressEvent, parse_ffmpeg_progress_line
        
        # Determine total duration for percentage calculation if not explicitly provided
        total_dur = duration
        if not total_dur:
            try:
                import mutagen
                audio_meta = mutagen.File(audio_file)
                if audio_meta and audio_meta.info:
                    total_dur = getattr(audio_meta.info, 'length', None)
            except Exception:
                pass
                
        try:
            progress_callback(ProgressEvent(
                job_id=str(job_id), worker_id=int(worker_id), status="ENCODING_VIDEO",
                percent=0.0, book=book, chapter=chapter, message="Starting FFmpeg encoding..."
            ))
            
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True
            )
            output_lines = []
            while True:
                line = process.stdout.readline() if process.stdout else ""
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line)
                    metrics = parse_ffmpeg_progress_line(line, total_duration_sec=total_dur)
                    if metrics:
                        progress_callback(ProgressEvent(
                            job_id=str(job_id),
                            worker_id=int(worker_id),
                            status="ENCODING_VIDEO",
                            percent=metrics["percent"],
                            book=book,
                            chapter=chapter,
                            speed=metrics["speed"],
                            fps=metrics["fps"],
                            elapsed_sec=metrics["elapsed_sec"],
                            eta_sec=metrics["eta_sec"]
                        ))
            
            returncode = process.poll()
            if returncode == 0:
                progress_callback(ProgressEvent(
                    job_id=str(job_id), worker_id=int(worker_id), status="COMPLETED",
                    percent=100.0, book=book, chapter=chapter, message="Render completed successfully."
                ))
                return True, "".join(output_lines)
            else:
                progress_callback(ProgressEvent(
                    job_id=str(job_id), worker_id=int(worker_id), status="ERROR",
                    percent=0.0, book=book, chapter=chapter, message=f"FFmpeg exited with code {returncode}"
                ))
                return False, f"FFmpeg error (code {returncode}):\n{''.join(output_lines)}"
        except Exception as e:
            progress_callback(ProgressEvent(
                job_id=str(job_id), worker_id=int(worker_id), status="ERROR",
                percent=0.0, book=book, chapter=chapter, message=str(e)
            ))
            return False, f"Execution error: {str(e)}"
