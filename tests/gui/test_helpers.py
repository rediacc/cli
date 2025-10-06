#!/usr/bin/env python3
"""
GUI Test Helpers
Reusable utilities for GUI testing to reduce code duplication
"""

import sys
import threading
from pathlib import Path
from typing import Optional, Callable, Any
from contextlib import contextmanager

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

# Import screenshot helper if available
try:
    from tests.utils.screenshot_helper import ScreenshotHelper
    screenshot_helper = ScreenshotHelper()
    SCREENSHOTS_ENABLED = True
except Exception as e:
    print(f"⚠ Screenshots disabled: {e}")
    screenshot_helper = None
    SCREENSHOTS_ENABLED = False


class WindowTestContext:
    """Context manager for window lifecycle management"""

    def __init__(self, window_class, *args, **kwargs):
        """
        Initialize window test context.

        Args:
            window_class: The window class to instantiate
            *args: Positional arguments for window class
            **kwargs: Keyword arguments for window class
        """
        self.window_class = window_class
        self.args = args
        self.kwargs = kwargs
        self.window = None
        self.test_complete = [False]
        self.result = [None]

    def __enter__(self):
        """Create and return the window"""
        self.window = self.window_class(*self.args, **self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up the window"""
        if self.window and hasattr(self.window, 'root'):
            try:
                self.window.root.quit()
                self.window.root.destroy()
            except:
                pass
        return False

    def run_async(self, test_func: Callable):
        """
        Run a test function asynchronously with the window.

        Args:
            test_func: Function to run with the window
        """
        def run_in_thread():
            try:
                test_func(self.window, self)
            except Exception as e:
                print(f"Test error: {e}")
                self.result[0] = str(e)
            finally:
                self.test_complete[0] = True

        # Start test in thread
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        # Run mainloop
        if self.window and hasattr(self.window, 'root'):
            self.window.root.mainloop()

        return self.result[0]


class LoginTestHelper:
    """Helper for login flow operations"""

    @staticmethod
    def fill_credentials(window, email: str, password: str, take_screenshot: bool = True):
        """
        Fill login credentials in the window.

        Args:
            window: The login window instance
            email: Email address
            password: Password
            take_screenshot: Whether to take a screenshot before submission
        """
        window.email_entry.delete(0, 'end')
        window.password_entry.delete(0, 'end')
        window.email_entry.insert(0, email)
        window.password_entry.insert(0, password)

        if take_screenshot and SCREENSHOTS_ENABLED:
            window.root.update()
            screenshot_helper.take_screenshot_safe(
                f"login_filled_{email.split('@')[0]}",
                f"Login form filled with {email}"
            )

    @staticmethod
    def submit_login(window, take_screenshot_before: bool = True):
        """
        Submit the login form.

        Args:
            window: The login window instance
            take_screenshot_before: Whether to take a screenshot before clicking
        """
        if take_screenshot_before and SCREENSHOTS_ENABLED:
            window.root.update()
            screenshot_helper.take_screenshot_safe("login_before_submit", "Before login submission")

        window.login_button.invoke()

    @staticmethod
    def wait_for_status(window,
                        check_func: Callable[[str], bool],
                        max_checks: int = 15,
                        interval_ms: int = 500,
                        on_success: Optional[Callable] = None,
                        on_timeout: Optional[Callable] = None,
                        take_screenshot_on_success: bool = True):
        """
        Wait for a status condition to be met.

        Args:
            window: The window instance
            check_func: Function that takes status string and returns True if condition met
            max_checks: Maximum number of checks before timeout
            interval_ms: Interval between checks in milliseconds
            on_success: Callback when condition is met
            on_timeout: Callback on timeout
            take_screenshot_on_success: Whether to screenshot on success
        """
        check_count = [0]

        def check_status():
            if check_count[0] >= max_checks:
                print(f"  ⚠ Status check timed out after {max_checks} attempts")
                if on_timeout:
                    on_timeout()
                else:
                    window.root.quit()
                return

            check_count[0] += 1

            if hasattr(window, 'status_label'):
                status = window.status_label.cget('text')

                if check_func(status):
                    print(f"  ✓ Status condition met: {status}")

                    if take_screenshot_on_success and SCREENSHOTS_ENABLED:
                        window.root.update()
                        screenshot_helper.take_screenshot_safe("status_success", f"Status: {status}")

                    if on_success:
                        on_success(status)
                    else:
                        window.root.quit()
                    return

            # Check again after interval
            window.root.after(interval_ms, check_status)

        # Start checking
        window.root.after(interval_ms, check_status)

    @staticmethod
    def perform_login_flow(window, email: str, password: str,
                          expected_success: bool = True,
                          screenshot_prefix: str = "login"):
        """
        Perform complete login flow.

        Args:
            window: The login window instance
            email: Email address
            password: Password
            expected_success: Whether login is expected to succeed
            screenshot_prefix: Prefix for screenshot filenames
        """
        # Fill credentials
        LoginTestHelper.fill_credentials(window, email, password)

        # Submit
        LoginTestHelper.submit_login(window)

        # Define success check
        def is_success(status):
            return 'successful' in status.lower()

        def is_error(status):
            return any(word in status.lower() for word in
                      ['error', 'failed', 'invalid', 'incorrect', 'wrong'])

        def check_condition(status):
            if expected_success:
                return is_success(status)
            else:
                return is_error(status)

        # Wait for result
        LoginTestHelper.wait_for_status(
            window,
            check_condition,
            take_screenshot_on_success=True
        )


def take_screenshot_safe(name: str, description: str = ""):
    """
    Safely take a screenshot without raising exceptions.

    Args:
        name: Name for the screenshot file
        description: Optional description
    """
    if SCREENSHOTS_ENABLED:
        screenshot_helper.take_screenshot_safe(name, description)


def wait_and_quit(window, delay_ms: int = 1000):
    """
    Wait for specified delay then quit the window.

    Args:
        window: Window instance
        delay_ms: Delay in milliseconds before quitting
    """
    def quit_window():
        window.root.quit()

    window.root.after(delay_ms, quit_window)


@contextmanager
def screenshot_on_error(name_prefix: str = "error"):
    """
    Context manager that takes a screenshot if an exception occurs.

    Args:
        name_prefix: Prefix for error screenshot filename
    """
    try:
        yield
    except Exception as e:
        if SCREENSHOTS_ENABLED:
            screenshot_helper.take_screenshot_safe(
                f"{name_prefix}_exception",
                f"Exception occurred: {str(e)[:100]}"
            )
        raise
