"""
Utilities for streaming logs to frontend
"""
import logging
import json
from typing import Generator
from fastapi.responses import StreamingResponse


class LogStreamer:
    """Captures logs and streams them to frontend via SSE"""

    def __init__(self):
        self.logs = []
        self.logger = logging.getLogger(__name__)

    def log(self, message: str, level: str = "INFO"):
        """Add a log message"""
        timestamp = self._get_timestamp()
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)
        # Also log to normal logger
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def get_logs(self) -> list:
        """Get all captured logs"""
        return self.logs.copy()

    def clear_logs(self):
        """Clear all logs"""
        self.logs = []


# Global log streamer instance
log_streamer = LogStreamer()


def create_log_streaming_response() -> StreamingResponse:
    """Create a streaming response for logs"""

    def generate() -> Generator[str, None, None]:
        # Send existing logs first
        for log_entry in log_streamer.get_logs():
            yield f"data: {json.dumps(log_entry)}\n\n"

        # Keep connection alive and send new logs as they come
        last_log_count = len(log_streamer.get_logs())
        import time
        while True:
            current_log_count = len(log_streamer.get_logs())
            if current_log_count > last_log_count:
                # Send new logs
                for i in range(last_log_count, current_log_count):
                    log_entry = log_streamer.get_logs()[i]
                    yield f"data: {json.dumps(log_entry)}\n\n"
                last_log_count = current_log_count
            time.sleep(0.1)  # Small delay to prevent busy waiting

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )