"""
Placeholder for the async Redis Streams consumer tests.

These are intentionally SKIPPED, not missing: the async ingestion pipeline
(POST -> Redis Stream -> consumer-group worker -> bulk index) is SignalOps
Milestone 1 and has not been built yet. Ingestion is currently synchronous
(app/main.py writes straight to OpenSearch), so there is no consumer, no
consumer group, and no dead-letter/redelivery behaviour to exercise.

When Milestone 1 lands, replace these skips with real tests for:
  * consumer-group claim on worker death (XAUTOCLAIM of pending entries)
  * batch flush by size and by interval
  * dead-letter stream after the retry cap
  * graceful-shutdown drain of in-flight batches
"""
import pytest

pytestmark = pytest.mark.skip(reason="Milestone 1 (Redis async ingestion) not yet implemented")


def test_consumer_group_redelivery_on_worker_death():
    ...


def test_dead_letter_after_retry_cap():
    ...


def test_batch_flush_by_size_and_interval():
    ...
