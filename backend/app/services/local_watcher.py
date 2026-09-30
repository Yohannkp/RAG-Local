from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config import settings
from app.services.local_search import index_local_files


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, changed: asyncio.Queue[str]):
        self._loop = loop
        self._changed = changed

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle_change(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle_change(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._handle_change(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._handle_change(event)
        destination = getattr(event, "dest_path", None)
        if destination:
            self._loop.call_soon_threadsafe(self._enqueue, destination)

    def _handle_change(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = event.src_path
        self._loop.call_soon_threadsafe(self._enqueue, path)

    def _enqueue(self, path: str) -> None:
        try:
            self._changed.put_nowait(path)
        except asyncio.QueueFull:
            pass


class LocalFileWatcher:
    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._task: asyncio.Task[None] | None = None
        self._changed: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        self._root: Path | None = None

    async def start(self) -> None:
        root = Path(settings.local_index_root).expanduser().resolve()
        if not root.is_dir():
            return
        loop = asyncio.get_running_loop()
        handler = _ChangeHandler(loop, self._changed)
        observer = await asyncio.to_thread(self._create_observer, handler, root)
        self._observer = observer
        self._root = root
        self._task = asyncio.create_task(self._consume())

    @staticmethod
    def _create_observer(handler: _ChangeHandler, root: Path) -> Observer:
        observer = Observer()
        observer.schedule(handler, str(root), recursive=True)
        observer.start()
        return observer

    async def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            await asyncio.to_thread(self._observer.join)
            self._observer = None
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _consume(self) -> None:
        while True:
            await self._changed.get()
            await asyncio.sleep(1.5)
            while not self._changed.empty():
                self._changed.get_nowait()
            if self._root:
                try:
                    await index_local_files(str(self._root))
                except Exception:
                    # Le prochain événement ou la prochaine question relancera la synchronisation.
                    continue


local_file_watcher = LocalFileWatcher()