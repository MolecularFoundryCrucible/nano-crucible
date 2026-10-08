#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Printer job operations for the Crucible API.

Access via: client.print.barcode().
"""

import logging
from typing import Dict

from .base import BaseResource
from ..utils.identifiers import is_mfid

logger = logging.getLogger(__name__)


class PrintOperations(BaseResource):
    """Printer job operations.

    Access via: client.print.barcode().
    """

    def barcode(self, printer_id: str, mfid: str, name: str) -> Dict:
        """Publish a barcode print job and wait for a print result.

        The server waits briefly for the printer to confirm the job before
        responding; HTTP success alone does not mean the label printed.
        Check the returned 'status':

        - "ok": the printer confirmed success.
        - "error": the printer explicitly reported failure.
        - "timeout": no result arrived in time (likely offline, slow, or
          an unreachable/unknown printer_id).

        The server never validates that printer_id refers to a real,
        known printer -- it always attempts the publish. On "error" or
        "timeout", 'detail' may explain further using live printer-fleet
        status (e.g. the printer appears offline), checked only after the
        fact to help diagnose the failure, not to prevent the attempt.
        None does not mean the print is fine -- it means no extra
        diagnostic info was available.

        Not automatically retried on a transient 429/502/503/504: the
        server may have already published the job to MQTT (and the
        printer may have already printed it) by the time such a response
        arrives, so a client-side retry here could trigger a second,
        genuinely new print job and double-print the label.

        Args:
            printer_id: Target printer identifier, e.g. 'lab3-zebra'. Not
                validated against a known-printers list; a typo reaches
                the server and publishes regardless.
            mfid: MFID of the sample or tray to print.
            name: Human-readable label text. Any string, including empty.

        Returns:
            Dict: {job_id, printer_id, mfid, name, ts, status, detail}
        """
        if not is_mfid(mfid):
            raise ValueError("mfid must be an exact 26-character MFID.")

        result = self._request(
            'post', '/print/barcode', retry=False,
            json={'printer_id': printer_id, 'mfid': mfid, 'name': name},
        )
        if result.get('status') != 'ok':
            logger.warning(
                "Print job %s to %r did not confirm success (status=%s): %s",
                result.get('job_id'), printer_id, result.get('status'),
                result.get('detail') or 'no further detail',
            )
        return result
