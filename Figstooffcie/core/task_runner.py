from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from core.files import expand_image_inputs
from core.models import FileTaskResult, ModuleRunRequest, RunContext


class BatchTaskRunner:
    def run_batch(
        self,
        module_service,
        request: ModuleRunRequest,
        context: RunContext,
        progress_callback=None,
        log_callback=None,
    ) -> list[FileTaskResult]:
        input_files = expand_image_inputs(request.input_paths)
        module_service.validate_inputs(input_files)
        request.output_dir.mkdir(parents=True, exist_ok=True)

        total = len(input_files)
        done = 0
        results: list[FileTaskResult] = []
        used_output_paths: set[Path] = set()
        output_lock = Lock()

        def log(message: str) -> None:
            if log_callback is not None:
                log_callback(message)
            else:
                context.log(message)

        log(f"开始处理，共 {total} 张图片。")
        if progress_callback is not None:
            progress_callback(0, total)

        def run_one(input_path: Path) -> FileTaskResult:
            output_path = self._reserve_output_path(
                input_path=input_path,
                output_dir=request.output_dir,
                extension=module_service.manifest.output_extension,
                overwrite=request.overwrite_existing,
                used_output_paths=used_output_paths,
                lock=output_lock,
            )
            try:
                log(f"处理中：{input_path.name}")
                module_service.run_single(input_path, output_path, context)
            except Exception as exc:
                return FileTaskResult(
                    input_path=input_path,
                    success=False,
                    output_path=output_path,
                    error=str(exc),
                )
            return FileTaskResult(
                input_path=input_path,
                success=True,
                output_path=output_path,
                message=f"已生成：{output_path.name}",
            )

        if request.max_workers <= 1:
            for input_path in input_files:
                result = run_one(input_path)
                results.append(result)
                done += 1
                log(self._format_result_message(result))
                if progress_callback is not None:
                    progress_callback(done, total)
            return results

        with ThreadPoolExecutor(max_workers=request.max_workers) as executor:
            future_map = {executor.submit(run_one, path): path for path in input_files}
            for future in as_completed(future_map):
                result = future.result()
                results.append(result)
                done += 1
                log(self._format_result_message(result))
                if progress_callback is not None:
                    progress_callback(done, total)

        results.sort(key=lambda item: item.input_path.name.lower())
        return results

    def _reserve_output_path(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        extension: str,
        overwrite: bool,
        used_output_paths: set[Path],
        lock: Lock,
    ) -> Path:
        base_name = input_path.stem
        candidate = output_dir / f"{base_name}{extension}"
        with lock:
            if overwrite:
                used_output_paths.add(candidate)
                return candidate

            index = 1
            while candidate in used_output_paths or candidate.exists():
                candidate = output_dir / f"{base_name}_{index}{extension}"
                index += 1
            used_output_paths.add(candidate)
            return candidate

    def _format_result_message(self, result: FileTaskResult) -> str:
        if result.success:
            return f"完成：{result.input_path.name} -> {result.output_path}"
        return f"失败：{result.input_path.name} -> {result.error}"
