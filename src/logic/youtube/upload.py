from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import aiofiles
from aiogram.types.input_file import InputFile

from src.core.youtube.models import YoutubeDownloadProgressSnapshot

type UploadProgressCallback = Callable[[YoutubeDownloadProgressSnapshot], Awaitable[None]]


class ProgressFSInputFile(InputFile):
    def __init__(
        self,
        path: Path,
        *,
        progress_callback: UploadProgressCallback | None = None,
        chunk_size: int = 64 * 1024,
    ) -> None:
        super().__init__(filename=path.name, chunk_size=chunk_size)
        self._path = path
        self._progress_callback = progress_callback
        self._total_size_bytes = path.stat().st_size

    async def read(self, bot: object) -> AsyncGenerator[bytes]:
        _ = bot
        uploaded_bytes = 0

        async with aiofiles.open(self._path, "rb") as file_handle:
            while chunk := await file_handle.read(self.chunk_size):
                uploaded_bytes += len(chunk)
                if self._progress_callback is not None:
                    await self._progress_callback(
                        YoutubeDownloadProgressSnapshot(
                            status="uploading",
                            phase="upload",
                            downloaded_bytes=uploaded_bytes,
                            total_bytes=self._total_size_bytes,
                            filename=self.filename,
                        )
                    )
                yield chunk
