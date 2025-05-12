import asyncio
from typing import Dict, List, Type

from deputydev_core.services.diff.algo_runners.base_diff_algo_runner import (
    BaseDiffAlgoRunner,
)
from deputydev_core.services.diff.algo_runners.line_numbered_diff.runner import (
    LineNumberedDiffAlgoRunner,
)
from deputydev_core.services.diff.algo_runners.unified_diff.runner import (
    UnifiedDiffAlgoRunner,
)
from deputydev_core.services.diff.dataclasses.main import (
    DiffTypes,
    FileDiffApplicationRequest,
    FileDiffApplicationResponse,
)


class DiffApplicator:
    """
    This class is responsible for applying a diff to a file.
    """

    _diff_algo_runners: Dict[DiffTypes, Type[BaseDiffAlgoRunner]] = {
        DiffTypes.UDIFF: UnifiedDiffAlgoRunner,
        DiffTypes.LINE_NUMBERED: LineNumberedDiffAlgoRunner,
    }

    @classmethod
    async def apply_diff_to_file(cls, application_request: FileDiffApplicationRequest) -> FileDiffApplicationResponse:
        """
        Apply the given diff to the file specified in the application request.
        """
        diff_type = application_request.diff_data.type
        diff_algo_runner = cls._diff_algo_runners.get(diff_type)

        if not diff_algo_runner:
            raise ValueError(f"Unsupported diff type: {diff_type}")

        return await diff_algo_runner.apply_diff(
            file_path=application_request.file_path,
            repo_path=application_request.repo_path,
            current_content=application_request.current_content,
            diff_data=application_request.diff_data,
        )

    @classmethod
    async def bulk_apply_diff(
        cls, application_requests: List[FileDiffApplicationRequest]
    ) -> List[FileDiffApplicationResponse]:
        """
        Apply diffs to multiple files in bulk.
        """
        responses = asyncio.gather(*[cls.apply_diff_to_file(request) for request in application_requests])
        return await responses
