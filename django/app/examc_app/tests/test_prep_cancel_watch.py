from unittest.mock import patch

from django.test import SimpleTestCase

from examc_app.tasks import watch_cancel


class WatchCancelTests(SimpleTestCase):
    """The watcher of the cancel request, used by the steps of the final generation that run in a transaction."""

    def test_event_is_set_once_the_cancel_is_requested(self):
        calls = []

        def should_cancel():
            calls.append(1)
            return len(calls) >= 3

        with patch("examc_app.tasks.CANCEL_POLL_SECONDS", 0.01), watch_cancel(should_cancel) as cancelled:
            self.assertTrue(cancelled.wait(timeout=5))

    def test_event_is_not_set_without_cancel(self):
        with patch("examc_app.tasks.CANCEL_POLL_SECONDS", 0.01), watch_cancel(lambda: False) as cancelled:
            self.assertFalse(cancelled.wait(timeout=0.2))

    def test_the_thread_stops_with_the_block(self):
        calls = []

        def should_cancel():
            calls.append(1)
            return False

        with patch("examc_app.tasks.CANCEL_POLL_SECONDS", 0.01), watch_cancel(should_cancel):
            pass

        polled = len(calls)
        import time
        time.sleep(0.1)
        self.assertEqual(len(calls), polled)
