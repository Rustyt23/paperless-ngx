import logging
import os
import re
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from fnmatch import filter
from pathlib import Path, PurePath
from threading import Event
from threading import Lock
from time import monotonic
from time import sleep
from typing import Final
from typing import Iterable
from typing import Iterator
from typing import Optional

from django import db
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from pikepdf import Pdf
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import Tag
from documents.parsers import is_file_ext_supported
from documents.tasks import consume_file
from documents.utils import copy_basic_file_stats
from paperless.config import GeneralConfig

try:
    from inotifyrecursive import INotify
    from inotifyrecursive import flags
except ImportError:  # pragma: no cover
    INotify = flags = None

logger = logging.getLogger("paperless.management.consumer")

READY_POLLS_REQUIRED: Final[int] = 2
SCANNER_INTERVAL_SECONDS: Final[float] = 5.0
PAGE_FRAGMENT_PATTERN = re.compile(r"__page-\d{5}\.pdf$", re.IGNORECASE)
MAX_WAIT_STEP: Final[float] = 0.5


def _tags_from_path(filepath: Path) -> list[int]:
    """
    Walk up the directory tree from filepath to CONSUMPTION_DIR
    and get or create Tag IDs for every directory.

    Returns set of Tag models
    """
    db.close_old_connections()
    tag_ids = set()
    path_parts = filepath.relative_to(settings.CONSUMPTION_DIR).parent.parts
    for part in path_parts:
        tag_ids.add(
            Tag.objects.get_or_create(name__iexact=part, defaults={"name": part})[0].pk,
        )

    return list(tag_ids)


def _is_ignored(filepath: Path) -> bool:
    """
    Checks if the given file should be ignored, based on configured
    patterns.

    Returns True if the file is ignored, False otherwise
    """
    filepath_relative = PurePath(filepath).relative_to(settings.CONSUMPTION_DIR)

    parts = []
    for part in filepath_relative.parts:
        if part != filepath_relative.name:
            part = part + "/"
        parts.append(part)

    for pattern in settings.CONSUMER_IGNORE_PATTERNS:
        if len(filter(parts, pattern)):
            return True

    return False


@dataclass
class FileState:
    size: int
    mtime: float
    stable_count: int = 1
    seen: bool = False


class ScanState(Enum):
    NEW = "new"
    BUSY = "busy"
    READY = "ready"


class ReadyFileTracker:
    def __init__(self) -> None:
        self._states: dict[Path, FileState] = {}
        self._lock = Lock()

    def begin_round(self) -> None:
        with self._lock:
            for state in self._states.values():
                state.seen = False

    def observe(self, path: Path) -> tuple[Optional[ScanState], Optional[os.stat_result]]:
        try:
            stat = path.stat()
        except FileNotFoundError:
            with self._lock:
                self._states.pop(path, None)
            return None, None

        with self._lock:
            state = self._states.get(path)
            if state is None:
                self._states[path] = FileState(
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    stable_count=1,
                    seen=True,
                )
                return ScanState.NEW, stat

            state.seen = True
            if state.size == stat.st_size and state.mtime == stat.st_mtime:
                state.stable_count += 1
                if state.stable_count >= READY_POLLS_REQUIRED:
                    del self._states[path]
                    return ScanState.READY, stat
                return ScanState.BUSY, stat

            state.size = stat.st_size
            state.mtime = stat.st_mtime
            state.stable_count = 1
            return ScanState.BUSY, stat

    def finalize_round(self, seen_paths: set[Path]) -> None:
        with self._lock:
            for path, state in list(self._states.items()):
                if path not in seen_paths and not state.seen:
                    del self._states[path]

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._states)


@dataclass
class ScanSummary:
    new: int = 0
    busy: int = 0
    skipped: int = 0
    ready: int = 0


class ConsumeScanner:
    def __init__(self, directory: Path, recursive: bool, stop_flag: Event) -> None:
        self.directory = directory
        self.recursive = recursive
        self.stop_flag = stop_flag
        self._tracker = ReadyFileTracker()
        self._processing: set[Path] = set()
        self._processing_lock = Lock()
        self._ignored_paths: set[Path] = set()
        self._ignored_lock = Lock()
        self._event_paths: set[Path] = set()
        self._event_lock = Lock()
        self._wake_event = Event()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._staging_root = settings.SCRATCH_DIR / "consume" / "staging"
        self._failed_root = settings.SCRATCH_DIR / "consume" / "failed"
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._failed_root.mkdir(parents=True, exist_ok=True)

    def note_event(self, path: Path) -> None:
        try:
            path = path.resolve()
        except FileNotFoundError:
            return

        if not self._is_within_directory(path):
            return

        with self._event_lock:
            self._event_paths.add(path)
        self._wake_event.set()

    def has_pending(self) -> bool:
        return self._tracker.has_pending()

    def scan_once(self) -> None:
        events = self._drain_event_paths()
        summary = ScanSummary()
        ready_items: list[tuple[Path, os.stat_result]] = []
        seen_paths: set[Path] = set()

        self._tracker.begin_round()

        for candidate in self._iter_candidate_files(events):
            seen_paths.add(candidate)

            if self._is_marked_ignored(candidate):
                summary.skipped += 1
                continue

            if self._is_processing(candidate):
                summary.busy += 1
                continue

            if _is_ignored(candidate):
                summary.skipped += 1
                continue

            state, stat = self._tracker.observe(candidate)
            if state is None or stat is None:
                summary.skipped += 1
                continue

            if state is ScanState.NEW:
                summary.new += 1
            elif state is ScanState.BUSY:
                summary.busy += 1
            elif state is ScanState.READY:
                summary.ready += 1
                ready_items.append((candidate, stat))

        self._tracker.finalize_round(seen_paths)
        self._prune_ignored(seen_paths)

        for path, stat in ready_items:
            self._submit_for_processing(path, stat)

        logger.debug(
            "Consume scanner tick: new=%d busy=%d skipped=%d ready=%d",
            summary.new,
            summary.busy,
            summary.skipped,
            summary.ready,
        )

    def run_loop(self, interval: float) -> None:
        while not self.stop_flag.is_set():
            self.scan_once()
            if self.stop_flag.is_set():
                break
            self._wait_for_next_scan(interval)

    def stop(self) -> None:
        self._wake_event.set()
        self._executor.shutdown(wait=True)

    def _wait_for_next_scan(self, timeout: float) -> None:
        deadline = monotonic() + timeout
        while not self.stop_flag.is_set():
            remaining = deadline - monotonic()
            if remaining <= 0:
                return
            step = min(remaining, MAX_WAIT_STEP)
            if self._wake_event.wait(step):
                self._wake_event.clear()
                return

    def _submit_for_processing(self, path: Path, stat: os.stat_result) -> None:
        with self._processing_lock:
            self._processing.add(path)
        self._executor.submit(self._ingest_ready_file, path, stat)

    def _is_processing(self, path: Path) -> bool:
        with self._processing_lock:
            return path in self._processing

    def _is_marked_ignored(self, path: Path) -> bool:
        with self._ignored_lock:
            return path in self._ignored_paths

    def _mark_ignored(self, path: Path) -> None:
        with self._ignored_lock:
            self._ignored_paths.add(path)

    def _prune_ignored(self, active_paths: set[Path]) -> None:
        with self._ignored_lock:
            self._ignored_paths.intersection_update(active_paths)

    def _drain_event_paths(self) -> set[Path]:
        with self._event_lock:
            paths = set(self._event_paths)
            self._event_paths.clear()
        return paths

    def _is_within_directory(self, path: Path) -> bool:
        try:
            path.relative_to(self.directory)
            return True
        except ValueError:
            return False

    def _iter_candidate_files(self, event_paths: set[Path]) -> Iterator[Path]:
        seen: set[Path] = set()

        for path in event_paths:
            yield from self._expand_path(path, seen)

        for file_path in self._walk_directory():
            if file_path in seen:
                continue
            yield file_path

    def _expand_path(self, path: Path, seen: set[Path]) -> Iterable[Path]:
        if path in seen:
            return []

        if path.is_dir():
            files: list[Path] = []
            for root, _, filenames in os.walk(path):
                current_dir = Path(root)
                for filename in filenames:
                    candidate = current_dir / filename
                    if candidate in seen:
                        continue
                    if candidate.is_file():
                        seen.add(candidate)
                        files.append(candidate)
            return files

        if path.is_file():
            seen.add(path)
            return [path]

        return []

    def _walk_directory(self) -> Iterator[Path]:
        for dirpath, dirnames, filenames in os.walk(self.directory):
            current_dir = Path(dirpath)
            dirnames[:] = [
                d
                for d in dirnames
                if not _is_ignored(current_dir / d)
            ]
            for filename in filenames:
                yield current_dir / filename

            if not self.recursive:
                break

    def _ingest_ready_file(self, path: Path, stat: os.stat_result) -> None:
        start_time = monotonic()
        tag_ids: Optional[list[int]] = None
        job_dir: Optional[Path] = None
        staged_path: Optional[Path] = None
        page_count = 0
        split_result_count = 0

        try:
            if not path.exists() or not path.is_file():
                logger.debug("Not consuming file %s: File has moved.", path)
                return

            if not is_file_ext_supported(path.suffix):
                logger.warning(
                    "Not consuming file %s: Unknown file extension.",
                    path,
                )
                self._mark_ignored(path)
                return

            if settings.CONSUMER_SUBDIRS_AS_TAGS:
                try:
                    tag_ids = _tags_from_path(path)
                except Exception:
                    logger.exception("Error creating tags from path")

            job_dir = self._create_job_dir()
            staged_path = job_dir / path.name
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), staged_path)

            final_paths = [staged_path]
            if staged_path.suffix.lower() == ".pdf":
                page_count = self._get_page_count(staged_path)
                if self._should_split_file(path.name, page_count):
                    final_paths = self._split_pdf(staged_path, job_dir)
                split_result_count = len(final_paths)
            else:
                split_result_count = 1

            for final_path in final_paths:
                try:
                    consume_file.delay(
                        ConsumableDocument(
                            source=DocumentSource.ConsumeFolder,
                            original_file=final_path,
                        ),
                        DocumentMetadataOverrides(tag_ids=tag_ids),
                    )
                except Exception:
                    logger.exception("Error while consuming document")

            duration = monotonic() - start_time
            logger.info(
                "Consume pickup path=%s size=%d pages=%d split=%d duration=%.2fs",
                path,
                stat.st_size,
                page_count,
                split_result_count or len(final_paths),
                duration,
            )
        except Exception:
            logger.exception("Error while preparing %s for consumption", path)
            if job_dir:
                self._move_job_to_failed(job_dir)
        finally:
            with self._processing_lock:
                self._processing.discard(path)

    def _create_job_dir(self) -> Path:
        job_dir = self._staging_root / uuid.uuid4().hex
        job_dir.mkdir(parents=True, exist_ok=False)
        return job_dir

    def _get_page_count(self, pdf_path: Path) -> int:
        try:
            with Pdf.open(pdf_path) as pdf:
                return len(pdf.pages)
        except Exception:
            logger.exception("Failed to read PDF metadata for %s", pdf_path)
            raise

    def _should_split_file(self, original_name: str, page_count: int) -> bool:
        if page_count <= 1:
            return False
        if PAGE_FRAGMENT_PATTERN.search(original_name):
            return False
        try:
            return GeneralConfig().split_pdf_on_upload
        except Exception:
            logger.exception("Unable to determine split configuration")
            return False

    def _split_pdf(self, pdf_path: Path, job_dir: Path) -> list[Path]:
        output_paths: list[Path] = []
        base_name = pdf_path.stem

        try:
            with Pdf.open(pdf_path) as input_pdf:
                for index, page in enumerate(input_pdf.pages, start=1):
                    new_name = f"{base_name}__page-{index:05d}.pdf"
                    output_path = job_dir / new_name
                    output_pdf = Pdf.new()
                    output_pdf.pages.append(page)
                    output_pdf.save(str(output_path))
                    copy_basic_file_stats(pdf_path, output_path)
                    output_paths.append(output_path)
        finally:
            pdf_path.unlink(missing_ok=True)

        return output_paths

    def _move_job_to_failed(self, job_dir: Path) -> None:
        try:
            target = self._failed_root / job_dir.name
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(job_dir), target)
        except Exception:
            logger.exception("Failed moving %s to failed directory", job_dir)


class Handler(FileSystemEventHandler):
    def __init__(self, scanner: ConsumeScanner) -> None:
        super().__init__()
        self._scanner = scanner

    def on_created(self, event):  # noqa: D401
        self._scanner.note_event(Path(event.src_path))

    def on_moved(self, event):  # noqa: D401
        self._scanner.note_event(Path(event.dest_path))

    def on_modified(self, event):  # noqa: D401
        self._scanner.note_event(Path(event.src_path))


class Command(BaseCommand):
    """
    Consume files from the configured directory.
    """

    stop_flag = Event()
    testing_timeout_s: Final[float] = 0.5
    testing_timeout_ms: Final[float] = testing_timeout_s * 1000.0

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            default=settings.CONSUMPTION_DIR,
            nargs="?",
            help="The consumption directory.",
        )
        parser.add_argument("--oneshot", action="store_true", help="Run only once.")
        parser.add_argument(
            "--testing",
            action="store_true",
            help="Flag used only for unit testing",
            default=False,
        )

    def handle(self, *args, **options):
        directory = options["directory"]
        watch_recursive = settings.CONSUMER_RECURSIVE

        if not directory:
            raise CommandError("CONSUMPTION_DIR does not appear to be set.")

        directory = Path(directory).resolve()

        if not directory.is_dir():
            raise CommandError(f"Consumption directory {directory} does not exist")

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

        scanner = ConsumeScanner(directory, True, self.stop_flag)

        if options["oneshot"]:
            for _ in range(READY_POLLS_REQUIRED):
                scanner.scan_once()
                if not scanner.has_pending():
                    break
                sleep(self.testing_timeout_s if options["testing"] else 0.1)
            scanner.stop()
            return

        watcher_thread = self._start_watcher(directory, watch_recursive, scanner, options["testing"])
        try:
            interval = self.testing_timeout_s if options["testing"] else SCANNER_INTERVAL_SECONDS
            try:
                scanner.run_loop(interval)
            except KeyboardInterrupt:
                logger.info("Received interrupt, stopping consumer")
        finally:
            self.stop_flag.set()
            if watcher_thread:
                watcher_thread.join()
            scanner.stop()
            self.stop_flag.clear()

        logger.debug("Consumer exiting.")

    def _start_watcher(self, directory: Path, recursive: bool, scanner: ConsumeScanner, is_testing: bool):
        from threading import Thread

        thread = Thread(
            target=self._watch_directory,
            args=(directory, recursive, scanner, is_testing),
            daemon=True,
        )
        thread.start()
        return thread

    def _watch_directory(self, directory: Path, recursive: bool, scanner: ConsumeScanner, is_testing: bool) -> None:
        if settings.CONSUMER_POLLING == 0 and INotify:
            self._run_inotify(directory, recursive, scanner, is_testing)
        else:
            if INotify is None and settings.CONSUMER_POLLING == 0:  # pragma: no cover
                logger.warning("Using polling as INotify import failed")
            self._run_watchdog(directory, recursive, scanner, is_testing)

    def _run_watchdog(self, directory: Path, recursive: bool, scanner: ConsumeScanner, is_testing: bool) -> None:
        logger.info(f"Polling directory for changes: {directory}")

        polling_interval = settings.CONSUMER_POLLING
        if polling_interval == 0:  # pragma: no cover
            polling_interval = 10

        observer = PollingObserver(timeout=polling_interval)
        observer.schedule(Handler(scanner), directory, recursive=recursive)
        observer.start()
        try:
            while not self.stop_flag.wait(self.testing_timeout_s if is_testing else 1.0):
                pass
        finally:
            observer.stop()
            observer.join()

    def _run_inotify(self, directory: Path, recursive: bool, scanner: ConsumeScanner, is_testing: bool) -> None:
        logger.info(f"Using inotify to watch directory for changes: {directory}")

        inotify = INotify()
        inotify_flags = flags.CLOSE_WRITE | flags.MOVED_TO | flags.MODIFY | flags.CREATE
        if recursive:
            inotify.add_watch_recursive(directory, inotify_flags)
        else:
            inotify.add_watch(directory, inotify_flags)

        try:
            while not self.stop_flag.is_set():
                timeout_ms = int(self.testing_timeout_ms if is_testing else SCANNER_INTERVAL_SECONDS * 1000)
                events = inotify.read(timeout=timeout_ms)
                for event in events:
                    path = inotify.get_path(event.wd) if recursive else directory
                    target = Path(path) / event.name
                    scanner.note_event(target)
        finally:
            inotify.close()
