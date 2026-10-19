#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset postprocessing pipelines and their runs.

Start a run with client.datasets.postprocess(); this namespace lists the
available pipelines and follows or reports on runs.
"""

from typing import Dict, List, Optional

from .base import BaseResource, ListResult
from ..constants import DEFAULT_LIMIT, POSTPROCESSING_RUN_STATUSES
from ..models import Pipeline, PostprocessingRun


class PostprocessingOperations(BaseResource):
    """Operations for postprocessing pipelines and runs.

    Access via: client.postprocessing.*
    """

    @staticmethod
    def _parse(data: dict) -> Dict:
        return PostprocessingRun(**data).model_dump()

    def pipelines(self) -> List[Dict]:
        """List the pipelines that can postprocess a dataset.

        Returns:
            List[Dict]: Pipeline records with name, description, and the JSON
                schema of the parameters each accepts.
        """
        raw = self._request('get', '/pipelines')
        return [Pipeline(**p).model_dump() for p in raw]

    def list(self, dataset_mfid: Optional[str] = None,
             pipeline: Optional[str] = None,
             status: Optional[str] = None,
             limit: int = DEFAULT_LIMIT, offset: int = 0,
             cursor: Optional[str] = None) -> List[Dict]:
        """List postprocessing runs on datasets the caller can read, newest first.

        Args:
            dataset_mfid: Only runs on this dataset.
            pipeline: Only runs of this pipeline.
            status: One of crucible.constants.POSTPROCESSING_RUN_STATUSES.
            limit: Maximum number of results (default 100).
            offset: Starting position in the full result set.
            cursor (str, optional): Continuation token from a previous
                result's next_cursor; the listing resumes there.

        Returns:
            List[Dict]: PostprocessingRun records.
        """
        params = self._choice_params(status=(status, POSTPROCESSING_RUN_STATUSES))
        if dataset_mfid is not None:
            params['dataset_mfid'] = dataset_mfid
        if pipeline is not None:
            params['pipeline'] = pipeline
        raw = self._paginate('/postprocessing_runs', params, limit, offset, cursor=cursor)
        return ListResult.like(raw, [self._parse(r) for r in raw])

    def get(self, run_id: int) -> Dict:
        """Get one postprocessing run. Requires read access to its dataset.

        Args:
            run_id: Integer id of the run.

        Returns:
            Dict: The PostprocessingRun record.
        """
        return self._parse(self._request('get', f'/postprocessing_runs/{run_id}'))

    def update(self, run_id: int, status: str, error: Optional[str] = None) -> Dict:
        """Report a run's progress. Requires edit access to its dataset.

        Meant for the workers that execute pipelines.

        Args:
            run_id: Integer id of the run.
            status: "running", "completed", or "failed".
            error: Error message for a failed run (at most 4000 characters).

        Returns:
            Dict: The updated PostprocessingRun record.

        Raises:
            HTTPError 409: The run already finished.
        """
        if status not in POSTPROCESSING_RUN_STATUSES[1:]:
            raise ValueError(
                f"status must be one of: {', '.join(POSTPROCESSING_RUN_STATUSES[1:])}.")
        body = {'status': status}
        if error is not None:
            body['error'] = error
        return self._parse(self._request('patch', f'/postprocessing_runs/{run_id}', json=body))
