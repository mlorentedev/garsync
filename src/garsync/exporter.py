import logging
from typing import TextIO

from garsync.models import SyncResult

logger = logging.getLogger(__name__)


class JSONExporter:
    @staticmethod
    def export(result: SyncResult, output: TextIO) -> None:
        """Export the sync result to the provided file object or stdout."""
        try:
            # Output using pydantic's JSON generation
            output.write(result.model_dump_json(indent=2))
            output.write("\n")
            logger.info("Successfully exported sync result.")
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            raise
