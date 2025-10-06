#!/usr/bin/env python3
"""
Cross-platform screenshot helper for CI testing.
Works with Xvfb (Linux), Mesa3D (Windows), and native displays (macOS).
"""

import os
import sys
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any
from functools import wraps


class ScreenshotHelper:
    """Helper class for taking screenshots across different platforms and CI environments"""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the screenshot helper.

        Args:
            base_dir: Base directory for screenshots. Defaults to test-screenshots/
        """
        if base_dir is None:
            # Default to test-screenshots/ in the CLI directory
            self.base_dir = Path(__file__).parent.parent.parent / "test-screenshots"
        else:
            self.base_dir = Path(base_dir)

        # Create platform-specific subdirectory
        self.platform_name = self._get_platform_name()
        self.python_version = f"py{sys.version_info.major}.{sys.version_info.minor}"
        self.screenshot_dir = self.base_dir / f"{self.platform_name}-{self.python_version}"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Check if we're in a virtual display environment
        self.is_virtual_display = self._detect_virtual_display()

        print(f"📸 Screenshot helper initialized:")
        print(f"   Platform: {self.platform_name}")
        print(f"   Python: {self.python_version}")
        print(f"   Directory: {self.screenshot_dir}")
        print(f"   Virtual Display: {self.is_virtual_display}")

    def _get_platform_name(self) -> str:
        """Get a normalized platform name"""
        system = platform.system().lower()
        if system == 'linux':
            return 'ubuntu-latest' if 'ubuntu' in platform.platform().lower() else 'linux'
        elif system == 'darwin':
            return 'macos-latest'
        elif system == 'windows':
            return 'windows-latest'
        return system

    def _detect_virtual_display(self) -> bool:
        """Detect if we're running in a virtual display environment"""
        # Check for Xvfb on Linux
        if platform.system().lower() == 'linux':
            display = os.environ.get('DISPLAY', '')
            if display and ':' in display:
                # Check if Xvfb is running
                try:
                    import subprocess
                    result = subprocess.run(
                        ['ps', 'aux'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if 'Xvfb' in result.stdout or 'xvfb' in result.stdout:
                        return True
                except:
                    pass

        # Check for Mesa3D on Windows
        if platform.system().lower() == 'windows':
            if os.environ.get('MESA_GL_VERSION_OVERRIDE'):
                return True

        return False

    def take_screenshot(self, name: str, description: str = "") -> Optional[Path]:
        """
        Take a screenshot and save it with a descriptive name.

        Args:
            name: Base name for the screenshot file
            description: Optional description to print to console

        Returns:
            Path to the saved screenshot, or None if failed
        """
        try:
            import mss

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{name}.png"
            filepath = self.screenshot_dir / filename

            if description:
                print(f"📸 Taking screenshot: {description}")
            else:
                print(f"📸 Taking screenshot: {name}")

            # Take screenshot using mss
            with mss.mss() as sct:
                # Capture the first monitor (primary display)
                monitor = sct.monitors[1]  # Index 0 is all monitors combined
                screenshot = sct.grab(monitor)

                # Save to file
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))

            print(f"   ✓ Saved to: {filepath}")
            print(f"   Size: {filepath.stat().st_size} bytes")

            return filepath

        except ImportError:
            print("   ⚠ mss library not available, skipping screenshot")
            return None
        except Exception as e:
            print(f"   ✗ Failed to take screenshot: {e}")
            return None

    def take_screenshot_safe(self, name: str, description: str = "") -> Optional[Path]:
        """
        Take a screenshot without raising exceptions.
        Safe wrapper around take_screenshot().

        Args:
            name: Base name for the screenshot file
            description: Optional description to print to console

        Returns:
            Path to the saved screenshot, or None if failed
        """
        try:
            return self.take_screenshot(name, description)
        except Exception as e:
            print(f"   ⚠ Screenshot failed (non-fatal): {e}")
            return None


def create_screenshot_helper(base_dir: Optional[Path] = None) -> ScreenshotHelper:
    """
    Factory function to create a ScreenshotHelper instance.

    Args:
        base_dir: Base directory for screenshots. Defaults to test-screenshots/

    Returns:
        ScreenshotHelper instance
    """
    return ScreenshotHelper(base_dir)


# Convenience function for quick screenshots
def take_screenshot(name: str, description: str = "", base_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Quick function to take a screenshot without managing the helper instance.

    Args:
        name: Base name for the screenshot file
        description: Optional description to print to console
        base_dir: Base directory for screenshots. Defaults to test-screenshots/

    Returns:
        Path to the saved screenshot, or None if failed
    """
    helper = ScreenshotHelper(base_dir)
    return helper.take_screenshot_safe(name, description)


def screenshot_on_event(*events: str):
    """
    Decorator that takes screenshots before/after/on error of function execution.

    Args:
        *events: Events to screenshot on ('before', 'after', 'error')

    Example:
        @screenshot_on_event('before', 'after', 'error')
        def login(username, password):
            # login logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            helper = ScreenshotHelper()
            func_name = func.__name__

            # Before screenshot
            if 'before' in events:
                helper.take_screenshot_safe(
                    f"{func_name}_before",
                    f"Before {func_name}"
                )

            try:
                # Execute function
                result = func(*args, **kwargs)

                # After screenshot (success)
                if 'after' in events:
                    helper.take_screenshot_safe(
                        f"{func_name}_after",
                        f"After {func_name} (success)"
                    )

                return result

            except Exception as e:
                # Error screenshot
                if 'error' in events:
                    helper.take_screenshot_safe(
                        f"{func_name}_error",
                        f"Error in {func_name}: {str(e)[:50]}"
                    )
                raise

        return wrapper
    return decorator


def with_screenshots(name_prefix: str = ""):
    """
    Simpler decorator that takes before/after screenshots.

    Args:
        name_prefix: Optional prefix for screenshot names

    Example:
        @with_screenshots("login_flow")
        def perform_login(user, pwd):
            # login logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            helper = ScreenshotHelper()
            prefix = name_prefix or func.__name__

            # Before
            helper.take_screenshot_safe(f"{prefix}_before", f"Before {func.__name__}")

            # Execute
            result = func(*args, **kwargs)

            # After
            helper.take_screenshot_safe(f"{prefix}_after", f"After {func.__name__}")

            return result

        return wrapper
    return decorator


if __name__ == '__main__':
    # Test the screenshot helper
    print("Testing screenshot helper...")
    helper = ScreenshotHelper()
    result = helper.take_screenshot("test", "Test screenshot")
    if result:
        print(f"\n✓ Screenshot test successful: {result}")
    else:
        print("\n✗ Screenshot test failed")
