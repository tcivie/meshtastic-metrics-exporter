from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import CollectorRegistry


class MetricCleanupJob:
    def __init__(self, registry: CollectorRegistry):
        self.registry = registry
        self.scheduler = BackgroundScheduler()

    def start(self):
        """Start the cleanup job to run every hour"""
        self.scheduler.add_job(
            self.cleanup_unknown_metrics,
            'interval',
            minutes=10,
            next_run_time=datetime.now() + timedelta(minutes=1)  # First run after 1 minute
        )
        self.scheduler.start()

    def stop(self):
        """Stop the cleanup job"""
        self.scheduler.shutdown()

    def cleanup_unknown_metrics(self):
        """Remove metric entries with mostly 'Unknown' values from the metrics dictionary"""
        try:
            for collector, _ in list(self.registry._collector_to_names.items()):
                if hasattr(collector, '_metrics'):
                    labels_to_remove = []

                    # Identify label combinations to remove
                    for labels, _ in list(collector._metrics.items()):
                        unknown_count = sum(1 for label in labels if 'Unknown' in str(label))
                        if unknown_count >= 1:  # Threshold for "Unknown" values
                            labels_to_remove.append(labels)

                    # Remove identified label combinations
                    for labels in labels_to_remove:
                        try:
                            del collector._metrics[labels]
                            print(f"Removed metric entry with labels: {labels}")
                        except KeyError:
                            pass
                        except Exception as e:
                            print(f"Error removing metric entry: {e}")

        except Exception as e:
            print(f"Error during metric cleanup: {e}")
