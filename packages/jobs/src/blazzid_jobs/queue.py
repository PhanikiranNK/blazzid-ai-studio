"""Queue abstraction, Redis Streams implementation, in-memory test queue, and outbox dispatcher."""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import redis

from blazzid_jobs.repository import JobRepository

logger = logging.getLogger("blazzid.jobs.queue")


@dataclass(frozen=True)
class QueueMessage:
    """Represents a message received from the job queue."""

    message_id: str
    job_id: str
    event_type: str
    payload: dict[str, Any]


class JobQueue(ABC):
    """Abstract job queue interface."""

    @abstractmethod
    def publish(self, job_id: str, event_type: str, payload: dict[str, Any]) -> str:
        """Publish a message to the queue, returning the message identifier."""

    @abstractmethod
    def consume(self, timeout_ms: int = 1000) -> Optional[QueueMessage]:
        """Consume the next message from the queue, blocking up to timeout_ms."""

    @abstractmethod
    def ack(self, message_id: str) -> None:
        """Acknowledge successful receipt and completion of the message."""


class InMemoryJobQueue(JobQueue):
    """Hermetic thread-safe in-memory queue for offline unit testing."""

    def __init__(self) -> None:
        self._messages: list[QueueMessage] = []
        self._acked: list[str] = []

    def publish(self, job_id: str, event_type: str, payload: dict[str, Any]) -> str:
        msg_id = f"mem-{uuid.uuid4().hex[:12]}"
        msg = QueueMessage(
            message_id=msg_id,
            job_id=job_id,
            event_type=event_type,
            payload=payload,
        )
        self._messages.append(msg)
        return msg_id

    def consume(self, timeout_ms: int = 1000) -> Optional[QueueMessage]:
        if not self._messages:
            return None
        return self._messages.pop(0)

    def ack(self, message_id: str) -> None:
        self._acked.append(message_id)


class RedisJobQueue(JobQueue):
    """Production Redis Streams job queue with consumer group semantics."""

    def __init__(
        self,
        redis_client: Any,
        stream_key: str = "blazzid:jobs:stream",
        group_name: str = "blazzid:workers",
        consumer_name: Optional[str] = None,
        min_idle_time_ms: int = 30000,
    ) -> None:
        self.client = redis_client
        self.stream_key = stream_key
        self.group_name = group_name
        self.consumer_name = consumer_name or f"worker-{uuid.uuid4().hex[:8]}"
        self.min_idle_time_ms = min_idle_time_ms
        self._autoclaim_cursor = "0-0"

        # Initialize consumer group if not existing
        try:
            self.client.xgroup_create(self.stream_key, self.group_name, id="0", mkstream=True)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def publish(self, job_id: str, event_type: str, payload: dict[str, Any]) -> str:
        data = {
            "job_id": job_id,
            "event_type": event_type,
            "payload": json.dumps(payload),
        }
        msg_id = self.client.xadd(self.stream_key, data)
        return str(msg_id)

    def _parse_message(self, raw_msg_id: Any, raw_fields: Any) -> QueueMessage:
        msg_id_str = (
            raw_msg_id.decode("utf-8") if isinstance(raw_msg_id, bytes) else str(raw_msg_id)
        )
        fields: dict[str, str] = {}
        for k, v in raw_fields.items():
            key_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
            val_str = v.decode("utf-8") if isinstance(v, bytes) else str(v)
            fields[key_str] = val_str

        job_id = fields.get("job_id", "")
        event_type = fields.get("event_type", "job.queued")
        payload_json = fields.get("payload", "{}")
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}

        return QueueMessage(
            message_id=msg_id_str,
            job_id=job_id,
            event_type=event_type,
            payload=payload,
        )

    def consume(self, timeout_ms: int = 1000) -> Optional[QueueMessage]:
        try:
            # Reclaim abandoned pending messages from PEL via XAUTOCLAIM
            try:
                claimed: Any = self.client.xautoclaim(
                    self.stream_key,
                    self.group_name,
                    self.consumer_name,
                    min_idle_time=self.min_idle_time_ms,
                    start_id=self._autoclaim_cursor,
                    count=1,
                )
                if claimed and len(claimed) >= 2:
                    next_cursor, messages = claimed[0], claimed[1]
                    self._autoclaim_cursor = (
                        next_cursor.decode("utf-8")
                        if isinstance(next_cursor, bytes)
                        else str(next_cursor)
                    )
                    if messages:
                        raw_msg_id, raw_fields = messages[0]
                        return self._parse_message(raw_msg_id, raw_fields)
            except (redis.exceptions.ResponseError, AttributeError):
                # Fallback if xautoclaim unsupported
                pass
            except redis.exceptions.RedisError as err:
                logger.warning("Redis xautoclaim warning: %s", err)

            # Read new messages for this consumer group
            entries: Any = self.client.xreadgroup(
                self.group_name,
                self.consumer_name,
                {self.stream_key: ">"},
                count=1,
                block=timeout_ms,
            )
            if not entries:
                return None

            for _stream_name, messages in entries:
                for raw_msg_id, raw_fields in messages:
                    return self._parse_message(raw_msg_id, raw_fields)
        except redis.exceptions.RedisError as err:
            logger.warning("Redis consume error: %s", err)
            return None
        return None

    def ack(self, message_id: str) -> None:
        try:
            self.client.xack(self.stream_key, self.group_name, message_id)
        except redis.exceptions.RedisError as err:
            logger.warning("Redis xack error for %s: %s", message_id, err)


class OutboxDispatcher:
    """Dispatches durable outbox records to the target job queue."""

    def __init__(self, repository: JobRepository, queue: JobQueue) -> None:
        self.repository = repository
        self.queue = queue

    def dispatch_pending(self, batch_size: int = 50) -> int:
        """Poll pending outbox events and publish them to the queue."""
        events = self.repository.get_pending_outbox_events(limit=batch_size)
        dispatched_count = 0

        for event in events:
            try:
                self.queue.publish(
                    job_id=event.job_id,
                    event_type=event.event_type,
                    payload=event.payload,
                )
                self.repository.mark_outbox_published(event.event_id)
                dispatched_count += 1
            except Exception as err:
                logger.error("Failed to dispatch outbox event %s: %s", event.event_id, err)
                # Break to preserve chronological dispatch ordering
                break

        return dispatched_count
