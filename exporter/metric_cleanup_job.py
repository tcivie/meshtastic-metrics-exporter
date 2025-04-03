import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import CollectorRegistry


class TrackedMetricsDict(dict):
    """A dictionary that tracks updates for metrics"""

    def __init__(self, collector, metric_tracker, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._collector = collector
        self._metric_tracker = metric_tracker

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._metric_tracker.update_metric_timestamp(self._collector, key)


class MetricTrackingRegistry(CollectorRegistry):
    """Extended CollectorRegistry that tracks metric updates"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._metric_tracker = MetricCleanupJob(self)
        self._metric_tracker.start()

    def register(self, collector):
        """Override register to add update tracking to collectors"""
        super().register(collector)
        if hasattr(collector, '_metrics'):
            # Replace the metrics dict with our tracking version
            tracked_dict = TrackedMetricsDict(
                collector,
                self._metric_tracker,
                collector._metrics
            )
            collector._metrics = tracked_dict

    def __del__(self):
        """Ensure cleanup job is stopped when registry is destroyed"""
        if hasattr(self, '_metric_tracker'):
            self._metric_tracker.stop()

class MetricCleanupJob:
    def __init__(self, registry: CollectorRegistry):
        self.registry = registry
        self.scheduler = BackgroundScheduler()
        self.last_updates: Dict[Tuple[Any, Any], datetime] = {}

    def start(self):
        """Start the cleanup job to run every hour"""
        self.scheduler.add_job(
            self.cleanup_stale_metrics,
            'interval',
            minutes=int(os.getenv('METRIC_CLEANUP_INTERVAL', 60)),
            next_run_time=datetime.now() + timedelta(minutes=1)
        )
        self.scheduler.start()

    def stop(self):
        """Stop the cleanup job"""
        self.scheduler.shutdown()

    def update_metric_timestamp(self, collector, labels):
        """Update the last modification time for a metric"""
        metric_key = (collector, labels)
        self.last_updates[metric_key] = datetime.now()

    def cleanup_stale_metrics(self):
        """Remove metric entries that haven't been updated in 24 hours"""
        try:
            current_time = datetime.now()
            stale_threshold = current_time - timedelta(hours=24)

            for collector, _ in list(self.registry._collector_to_names.items()):
                if hasattr(collector, '_metrics'):
                    labels_to_remove = []

                    for labels, _ in list(collector._metrics.items()):
                        metric_key = (collector, labels)
                        last_update = self.last_updates.get(metric_key)

                        if last_update is None or last_update < stale_threshold:
                            labels_to_remove.append(labels)

                    for labels in labels_to_remove:
                        try:
                            del collector._metrics[labels]
                            metric_key = (collector, labels)
                            self.last_updates.pop(metric_key, None)
                            logging.debug(f"Removed stale metric entry with labels: {labels}")
                        except KeyError:
                            pass
                        except Exception as e:
                            logging.warning(f"Error removing metric entry: {e}")

        except Exception as e:
            logging.warning(f"Error during metric cleanup: {e}")
