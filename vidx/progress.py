"""
Progress Monitoring & Reporting System for VIDX
Implements a decoupled callback/observer architecture so both CLI terminal progress bars
and future graphical interfaces (GUI) can receive structured, real-time rendering updates.
"""
import re
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict, Any


@dataclass
class ProgressEvent:
    job_id: str
    worker_id: int
    status: str  # e.g., "STARTING", "EXTRACTING_SUBTITLES", "ENCODING_VIDEO", "COMPLETED", "ERROR"
    percent: float  # 0.0 to 100.0
    book: Optional[str] = None
    chapter: Optional[int] = None
    speed: Optional[str] = None
    fps: Optional[float] = None
    elapsed_sec: Optional[float] = None
    eta_sec: Optional[float] = None
    message: Optional[str] = None


class ProgressReporter:
    """
    Manages subscription and broadcasting of ProgressEvents to registered callbacks.
    GUI apps or CLI terminal observers subscribe to this reporter.
    """
    def __init__(self):
        self._subscribers: List[Callable[[ProgressEvent], None]] = []

    def subscribe(self, callback: Callable[[ProgressEvent], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ProgressEvent], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(self, event: ProgressEvent) -> None:
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                # Never let an observer exception crash the backend rendering pipeline
                pass


def parse_ffmpeg_progress_line(line: str, total_duration_sec: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Parses a single line of FFmpeg stdout/stderr output for encoding progress metrics.
    Example line: 'frame= 120 fps= 24.5 q=0.0 size= 1024kB time=00:00:05.00 bitrate=1677.7kbits/s speed= 2.0x'
    """
    # Check if this line contains time= progress
    time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)", line)
    if not time_match:
        return None
        
    hours = int(time_match.group(1))
    minutes = int(time_match.group(2))
    seconds = float(time_match.group(3))
    elapsed_sec = hours * 3600 + minutes * 60 + seconds
    
    fps_match = re.search(r"fps=\s*([\d\.]+)", line)
    fps = float(fps_match.group(1)) if fps_match else None
    
    speed_match = re.search(r"speed=\s*([\d\.]+)x?", line)
    speed_str = f"{speed_match.group(1)}x" if speed_match else None
    speed_val = float(speed_match.group(1)) if speed_match and float(speed_match.group(1)) > 0 else 1.0
    
    percent = 0.0
    eta_sec = None
    if total_duration_sec and total_duration_sec > 0:
        percent = min(100.0, max(0.0, (elapsed_sec / total_duration_sec) * 100.0))
        remaining_sec = max(0.0, total_duration_sec - elapsed_sec)
        eta_sec = round(remaining_sec / speed_val, 1)
        
    return {
        "elapsed_sec": elapsed_sec,
        "fps": fps,
        "speed": speed_str,
        "percent": round(percent, 1),
        "eta_sec": eta_sec,
    }


try:
    from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, SpinnerColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class TerminalProgressObserver:
    """
    CLI Terminal subscriber for ProgressReporter.
    Renders multi-worker concurrent progress bars using rich if available, or records status cleanly.
    """
    def __init__(self, total_jobs: int = 1, use_rich: bool = True):
        self.total_jobs = total_jobs
        self.use_rich = use_rich and RICH_AVAILABLE
        self.worker_tasks: Dict[int, Any] = {}
        self.last_event: Optional[ProgressEvent] = None
        self.progress: Optional[Any] = None
        self.completed_jobs = 0
        
        if self.use_rich:
            try:
                import sys
                if hasattr(sys.stdout, 'reconfigure'):
                    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                if hasattr(sys.stderr, 'reconfigure'):
                    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass

            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[worker]}"),
                TextColumn("[green]{task.fields[status]}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[yellow]{task.fields[metrics]}"),
                TimeRemainingColumn(),
            )
            self.master_task = self.progress.add_task(
                "[bold magenta]Overall Batch Queue",
                total=self.total_jobs,
                worker="[bold magenta][Master][/bold magenta]",
                status=f"[bold magenta]Completed 0/{self.total_jobs} Chapters[/bold magenta]",
                metrics="[bold white]0% Total[/bold white]"
            )

    def start(self) -> None:
        if self.progress:
            try:
                from rich.console import Console
                from rich.panel import Panel
                Console().print(Panel(
                    f"[bold cyan]VIDX Scripture Video Batch Processing Engine[/bold cyan]\n"
                    f"[white]Total Chapters in Queue: [bold yellow]{self.total_jobs}[/bold yellow] | "
                    f"Columns: [bold blue]Worker[/bold blue] • [bold green]Book/Ch [Status][/bold green] • "
                    f"[bold magenta]Progress[/bold magenta] • [bold yellow]Speed/FPS[/bold yellow] • [bold cyan]ETA[/bold cyan][/white]",
                    title="[bold green]⚡ LIVE BATCH MONITOR ⚡[/bold green]",
                    border_style="cyan"
                ))
            except Exception:
                pass
            self.progress.start()

    def stop(self) -> None:
        if self.progress:
            self.progress.stop()

    def on_progress(self, event: ProgressEvent) -> None:
        self.last_event = event
        if not self.use_rich or not self.progress:
            self.worker_tasks[event.worker_id] = event
            return
            
        if event.worker_id not in self.worker_tasks:
            self.worker_tasks[event.worker_id] = self.progress.add_task(
                f"Worker {event.worker_id}",
                total=100.0,
                worker=f"[bold blue][Worker {event.worker_id}][/bold blue]",
                status="Starting...",
                metrics=""
            )
            
        task_id = self.worker_tasks[event.worker_id]
        book_str = f"{event.book} " if event.book else ""
        ch_str = f"Ch {event.chapter:02d}" if event.chapter is not None and isinstance(event.chapter, int) else (f"Ch {event.chapter}" if event.chapter is not None else "")
        status_text = f"{book_str}{ch_str} [{event.status}]".strip()
        
        speed_str = event.speed or ""
        fps_str = f"{event.fps}fps" if event.fps else ""
        metrics_text = f"{speed_str} {fps_str}".strip()
        
        self.progress.update(
            task_id,
            completed=event.percent,
            status=status_text,
            metrics=metrics_text
        )
        
        if (event.status == "COMPLETED" and event.percent >= 100.0) or event.status == "ERROR":
            self.completed_jobs += 1
            pct = int((self.completed_jobs / self.total_jobs) * 100) if self.total_jobs > 0 else 100
            self.progress.update(
                self.master_task, 
                completed=self.completed_jobs,
                status=f"[bold magenta]Completed {self.completed_jobs}/{self.total_jobs} Chapters[/bold magenta]",
                metrics=f"[bold white]{pct}% Total[/bold white]"
            )

