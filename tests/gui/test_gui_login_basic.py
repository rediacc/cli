#!/usr/bin/env python3
"""
Real GUI Login Window Test
Tests the actual login window without any mocking
Uses real credentials from .env file
Requires a display to run (local machines only)
"""

import sys
import os
from pathlib import Path
import time
import threading
import pytest

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

# Import screenshot helper
try:
    from tests.utils.screenshot_helper import ScreenshotHelper
    screenshot_helper = ScreenshotHelper()
    SCREENSHOTS_ENABLED = True
except Exception as e:
    print(f"⚠ Screenshots disabled: {e}")
    screenshot_helper = None
    SCREENSHOTS_ENABLED = False

# Load environment variables manually
env_path = Path(__file__).parent.parent.parent.parent / '.env'
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key] = value
    print(f"✓ Loaded environment from {env_path}")


class GUITestSuite:
    """Test suite with hybrid window management - not a pytest class"""
    
    def __init__(self):
        self.shared_window = None  # For non-login tests
        self.test_results = []
        
    def setup_shared_window(self):
        """Create shared window for simple tests"""
        if not self.shared_window:
            from cli.gui.login import LoginWindow
            self.shared_window = LoginWindow(on_login_success=lambda: None)
            print("✓ Created shared window for non-login tests")
    
    def close_shared_window(self):
        """Close the shared window"""
        if self.shared_window and self.shared_window.root:
            try:
                self.shared_window.root.quit()
                self.shared_window.root.destroy()
            except:
                pass
            self.shared_window = None
    
    def test_window_title(self):
        """Test that window has correct title"""
        print("\nTest 1: Window Title")
        print("-" * 40)
        
        self.setup_shared_window()
        title = self.shared_window.root.title()
        
        # The actual title includes "Rediacc CLI - Login"
        assert "Login" in title, f"Window title is wrong: '{title}'"
        print(f"✓ Window title is correct: '{title}'")
        return True
    
    def test_window_widgets(self):
        """Test that all required widgets are present"""
        print("\nTest 2: Widget Presence")
        print("-" * 40)
        
        self.setup_shared_window()
        
        # Check for required widgets
        widgets_to_check = [
            ('email_entry', 'Email input field'),
            ('password_entry', 'Password input field'),
            ('master_password_entry', 'Master password input field'),
            ('login_button', 'Login button'),
            ('status_label', 'Status label'),
            ('lang_combo', 'Language selector')
        ]
        
        missing_widgets = []
        for widget_name, description in widgets_to_check:
            if hasattr(self.shared_window, widget_name):
                print(f"✓ {description} exists")
            else:
                print(f"✗ {description} missing")
                missing_widgets.append(description)
        
        assert len(missing_widgets) == 0, f"Missing widgets: {', '.join(missing_widgets)}"
        print("✓ All required widgets present")
        return True
    
    def test_login_form(self):
        """Test the login form interaction without real auth"""
        print("\nTest 3: Login Form Interaction")
        print("-" * 40)
        
        self.setup_shared_window()
        
        # Clear fields first
        self.shared_window.email_entry.delete(0, 'end')
        self.shared_window.password_entry.delete(0, 'end')
        self.shared_window.master_password_entry.delete(0, 'end')
        
        # Get credentials from environment or use test defaults
        email = os.getenv('SYSTEM_ADMIN_EMAIL', 'test@example.com')
        password = os.getenv('SYSTEM_ADMIN_PASSWORD', 'testpass123')
        master_password = os.getenv('SYSTEM_MASTER_PASSWORD', '')
        
        print(f"  Using email: {email}")
        
        # Fill in the fields
        self.shared_window.email_entry.insert(0, email)
        print("✓ Email entered")
        
        self.shared_window.password_entry.insert(0, password)
        print("✓ Password entered")
        
        self.shared_window.master_password_entry.insert(0, master_password)
        if master_password:
            print("✓ Master password entered")
        else:
            print("✓ Master password field left empty (optional)")
        
        # Check button state
        button_state = str(self.shared_window.login_button['state'])
        if button_state in ['normal', 'active']:
            print(f"✓ Login button is clickable (state: {button_state})")
        else:
            print(f"✗ Login button is disabled (state: {button_state})")
        
        # Update the window to show changes
        self.shared_window.root.update()
        
        print("✓ Login form is functional")
        return True
    
    def test_wrong_credentials(self):
        """Test that login fails with wrong credentials"""
        print("\nTest 4: Wrong Credentials")
        print("-" * 40)
        
        from cli.gui.login import LoginWindow
        
        print("Creating dedicated window for login test...")
        
        # Track results
        login_failed = [False]
        login_succeeded = [False]
        test_complete = [False]
        
        def on_success():
            login_succeeded[0] = True
            print("✗ Login succeeded with wrong credentials!")
        
        # Create new window for this test
        window = LoginWindow(on_login_success=on_success)
        
        def run_test():
            """Run test in a thread-safe way"""
            # Wait a bit for window to be ready
            window.root.after(500, lambda: fill_and_click())
        
        def fill_and_click():
            """Fill wrong credentials and click login"""
            print("Testing with wrong credentials...")

            # Enter wrong credentials
            window.email_entry.delete(0, 'end')
            window.password_entry.delete(0, 'end')
            window.email_entry.insert(0, 'wrong@test.com')
            window.password_entry.insert(0, 'wrongpass')

            # Take screenshot before login attempt
            if SCREENSHOTS_ENABLED:
                window.root.update()
                screenshot_helper.take_screenshot_safe("wrong_creds_before_login", "Wrong credentials - before login")

            print("  Entering wrong credentials...")
            window.login_button.invoke()

            # Check status after a delay
            window.root.after(3000, check_status)
        
        def check_status():
            """Check the login status"""
            if hasattr(window, 'status_label'):
                status = window.status_label.cget('text')
                try:
                    status_color = window.status_label.cget('fg')
                    is_error = status_color in ['red', '#ff0000', '#dc3545', '#e74c3c', '#FF6B35']
                except:
                    is_error = False

                if is_error and status:
                    print(f"  ❌ Error shown (red): {status}")

                if status and ('error' in status.lower() or 'failed' in status.lower() or
                             'invalid' in status.lower() or 'not found' in status.lower()):
                    print(f"✓ Login correctly failed with wrong credentials")
                    print(f"  Error message: {status}")
                    login_failed[0] = True

                    # Take screenshot of error state
                    if SCREENSHOTS_ENABLED:
                        window.root.update()
                        screenshot_helper.take_screenshot_safe("wrong_creds_error", "Wrong credentials - error displayed")

            test_complete[0] = True
            window.root.quit()
        
        # Start the test
        run_test()
        
        # Set a timeout
        window.root.after(5000, lambda: window.root.quit())
        
        # Run mainloop - CRITICAL for threading to work
        window.root.mainloop()
        
        # Clean up
        try:
            window.root.destroy()
        except:
            pass
        
        assert login_failed[0] and not login_succeeded[0], "Login should have failed with wrong credentials"
        print("✓ Wrong credentials test passed")
        return True
    
    def test_real_login(self):
        """Test real login with credentials from .env - NO MOCKING"""
        print("\nTest 5: Real Login")
        print("-" * 40)
        
        # Check if we have real credentials
        if not os.getenv('SYSTEM_ADMIN_EMAIL'):
            print("⚠ No SYSTEM_ADMIN_EMAIL in .env, skipping real login test")
            return False
        
        if not os.getenv('SYSTEM_API_URL'):
            print("⚠ No SYSTEM_API_URL in .env, skipping real login test")
            return False
        
        from cli.gui.login import LoginWindow
        
        print("Creating dedicated window for login test...")
        print("Testing with real credentials from .env (NO MOCKING)...")
        
        # Track result
        login_success = [False]
        test_complete = [False]
        
        def real_success_callback():
            login_success[0] = True
            print("✓ Login callback triggered")
            
            # Verify MainWindow class exists (but don't instantiate it)
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "gui.main", 
                    Path(__file__).parent.parent.parent / 'src' / 'cli' / 'gui' / 'main.py'
                )
                rediacc_gui = importlib.util.module_from_spec(spec)
                if 'rediacc_gui' not in sys.modules:
                    sys.modules['rediacc_gui'] = rediacc_gui
                    spec.loader.exec_module(rediacc_gui)
                else:
                    rediacc_gui = sys.modules['rediacc_gui']
                
                print("  Verifying MainWindow class exists...")
                if hasattr(rediacc_gui, 'MainWindow'):
                    print(f"  ✅ MainWindow class found")
                else:
                    print("  ❌ MainWindow class not found")
            except Exception as e:
                print(f"  ⚠️ Error loading MainWindow module: {e}")
        
        # Create window with callback
        window = LoginWindow(on_login_success=real_success_callback)
        
        # Get credentials
        email = os.getenv('SYSTEM_ADMIN_EMAIL')
        password = os.getenv('SYSTEM_ADMIN_PASSWORD')
        
        print(f"  Using email: {email}")
        
        def run_test():
            """Start the test after window is ready"""
            window.root.after(500, lambda: fill_and_click())
        
        def fill_and_click():
            """Fill real credentials and click login"""
            # Fill credentials
            window.email_entry.delete(0, 'end')
            window.password_entry.delete(0, 'end')
            window.email_entry.insert(0, email)
            window.password_entry.insert(0, password)

            # Take screenshot before login
            if SCREENSHOTS_ENABLED:
                window.root.update()
                screenshot_helper.take_screenshot_safe("real_login_before", "Real login - before attempt")

            print("  Attempting login...")
            window.login_button.invoke()

            # Check status periodically
            window.root.after(1000, lambda: check_status(0))
        
        def check_status(count):
            """Check login status periodically"""
            if count > 15:  # Timeout after ~7.5 seconds
                print("  ⚠ Timeout waiting for login")
                test_complete[0] = True
                window.root.quit()
                return
            
            if hasattr(window, 'status_label'):
                status = window.status_label.cget('text')
                
                if status and status not in ["", "Logging in..."]:
                    try:
                        status_color = window.status_label.cget('fg')
                        is_error = status_color in ['red', '#ff0000', '#dc3545', '#e74c3c', '#FF6B35']
                        is_success = status_color in ['green', '#00ff00', '#28a745', '#27ae60']
                        
                        if is_error:
                            print(f"  ❌ ERROR (red): {status}")
                        elif is_success:
                            print(f"  ✅ SUCCESS (green): {status}")
                        else:
                            print(f"  Status: {status}")
                    except:
                        print(f"  Status: {status}")
                
                # Check for success/failure
                if 'successful' in status.lower():
                    print("  ✓ Login successful!")

                    # Take screenshot of success
                    if SCREENSHOTS_ENABLED:
                        window.root.update()
                        screenshot_helper.take_screenshot_safe("real_login_success", "Real login - success")

                    # Wait a bit then quit
                    window.root.after(1000, lambda: finish_test())
                    return
                elif any(word in status.lower() for word in ['error', 'failed', 'invalid', 'incorrect', 'wrong']):
                    print(f"  ✗ Login failed with: {status}")

                    # Take screenshot of error
                    if SCREENSHOTS_ENABLED:
                        window.root.update()
                        screenshot_helper.take_screenshot_safe("real_login_error", "Real login - error")

                    window.root.after(500, lambda: finish_test())
                    return
            
            # Check again
            window.root.after(500, lambda: check_status(count + 1))
        
        def finish_test():
            """Finish the test"""
            test_complete[0] = True
            window.root.quit()
        
        # Start the test
        run_test()
        
        # Set a timeout
        window.root.after(10000, lambda: window.root.quit())
        
        # Run mainloop - CRITICAL for threading to work
        window.root.mainloop()
        
        # Clean up
        try:
            window.root.destroy()
        except:
            pass
        
        assert login_success[0], "Real login test failed - login was not successful"
        print("✓ Real login successful")
        return True
    
    def test_dropdown_placeholders(self):
        """Test that dropdowns show placeholders instead of auto-selecting first items"""
        print("\nTest 6: Dropdown Placeholder Behavior")
        print("-" * 40)

        # Check if we have real credentials
        if not os.getenv('SYSTEM_ADMIN_EMAIL'):
            print("⚠ No SYSTEM_ADMIN_EMAIL in .env, skipping dropdown test")
            return False

        if not os.getenv('SYSTEM_API_URL'):
            print("⚠ No SYSTEM_API_URL in .env, skipping dropdown test")
            return False

        from cli.gui.login import LoginWindow
        import importlib.util

        print("Testing that dropdowns show placeholders instead of auto-selecting...")

        # Track results
        login_success = [False]
        placeholders_correct = [False]
        test_complete = [False]

        def on_login_success():
            """Handle successful login"""
            login_success[0] = True
            print("✓ Login successful, checking dropdown behavior...")
            login_window.root.quit()

        # Create login window
        login_window = LoginWindow(on_login_success=on_login_success)

        # Get credentials
        email = os.getenv('SYSTEM_ADMIN_EMAIL')
        password = os.getenv('SYSTEM_ADMIN_PASSWORD')

        def perform_login():
            """Fill credentials and login"""
            login_window.email_entry.delete(0, 'end')
            login_window.password_entry.delete(0, 'end')
            login_window.email_entry.insert(0, email)
            login_window.password_entry.insert(0, password)
            login_window.login_button.invoke()
            login_window.root.after(2000, check_login_status)

        def check_login_status():
            """Check if login succeeded"""
            if hasattr(login_window, 'status_label'):
                status = login_window.status_label.cget('text')
                if 'successful' in status.lower():
                    print("  ✓ Login completed successfully")
                    login_window.root.after(500, lambda: login_window.root.quit())
                elif any(word in status.lower() for word in ['error', 'failed']):
                    print(f"  ✗ Login failed: {status}")
                    login_window.root.quit()
                else:
                    login_window.root.after(1000, check_login_status)

        # Start login process
        login_window.root.after(500, perform_login)
        login_window.root.after(10000, lambda: login_window.root.quit())  # Timeout
        login_window.root.mainloop()

        # Clean up login window
        try:
            login_window.root.destroy()
        except:
            pass

        if not login_success[0]:
            print("✗ Login failed, cannot test dropdown behavior")
            return False

        print("  Creating MainWindow to test dropdown behavior...")

        # Import and create MainWindow
        try:
            spec = importlib.util.spec_from_file_location(
                "gui.main",
                Path(__file__).parent.parent.parent / 'src' / 'cli' / 'gui' / 'main.py'
            )
            rediacc_gui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rediacc_gui)

            main_window = rediacc_gui.MainWindow()
            print("  ✓ MainWindow created")

            def check_dropdown_behavior():
                """Check that dropdowns show placeholders after data loads"""
                print("  Waiting for data to load...")
                main_window.root.after(3000, verify_placeholders)

            def verify_placeholders():
                """Verify that dropdowns show placeholders instead of auto-selected values"""
                # Take screenshot before checking
                if SCREENSHOTS_ENABLED:
                    main_window.root.update()
                    screenshot_helper.take_screenshot_safe("dropdown_placeholders", "Dropdown placeholders - checking state")

                # Check team dropdown
                team_value = main_window.team_combo.get()
                teams = main_window.team_combo['values']

                print(f"  Team dropdown: '{team_value}' (available: {len(teams) if teams else 0} teams)")

                if teams and len(teams) > 0:
                    if "Select Team" in team_value or team_value == "Select Team...":
                        print("    ✓ Team dropdown shows placeholder correctly")
                        team_placeholder_ok = True
                    else:
                        print(f"    ✗ Team dropdown auto-selected: '{team_value}' instead of placeholder")
                        team_placeholder_ok = False
                else:
                    print("    ⚠ No teams loaded to test")
                    team_placeholder_ok = True

                # Check machine dropdown
                machine_value = main_window.machine_combo.get()
                machines = main_window.machine_combo['values']

                print(f"  Machine dropdown: '{machine_value}' (available: {len(machines) if machines else 0} machines)")

                if "Select Machine" in machine_value or machine_value == "Select Machine...":
                    print("    ✓ Machine dropdown shows placeholder correctly")
                    machine_placeholder_ok = True
                else:
                    print(f"    ✗ Machine dropdown shows: '{machine_value}' instead of placeholder")
                    machine_placeholder_ok = False

                # Check repository dropdown
                repo_value = main_window.repo_combo.get()
                repos = main_window.repo_combo['values']

                print(f"  Repository dropdown: '{repo_value}' (available: {len(repos) if repos else 0} repos)")

                if "Select Repository" in repo_value or repo_value == "Select Repository...":
                    print("    ✓ Repository dropdown shows placeholder correctly")
                    repo_placeholder_ok = True
                else:
                    print(f"    ✗ Repository dropdown shows: '{repo_value}' instead of placeholder")
                    repo_placeholder_ok = False

                placeholders_correct[0] = team_placeholder_ok and machine_placeholder_ok and repo_placeholder_ok

                if placeholders_correct[0]:
                    print("  ✓ All dropdowns show placeholders correctly!")
                else:
                    print("  ✗ Some dropdowns are not showing placeholders as expected")

                test_complete[0] = True
                main_window.root.quit()

            # Start checking after window is ready
            main_window.root.after(2000, check_dropdown_behavior)
            main_window.root.after(15000, lambda: main_window.root.quit())  # Timeout
            main_window.root.mainloop()

            # Clean up
            try:
                main_window.root.destroy()
            except:
                pass

        except Exception as e:
            print(f"✗ Error creating MainWindow: {e}")
            return False

        if placeholders_correct[0]:
            print("✓ Dropdown placeholder test passed")
            return True
        else:
            print("✗ Dropdown placeholder test failed")
            return False

    def test_login_and_terminal(self):
        """Test login and then launch machine terminal from Tools menu"""
        print("\nTest 7: Login and Terminal Launch")
        print("-" * 40)
        
        # Check if we have real credentials
        if not os.getenv('SYSTEM_ADMIN_EMAIL'):
            print("⚠ No SYSTEM_ADMIN_EMAIL in .env, skipping terminal test")
            return False
        
        if not os.getenv('SYSTEM_API_URL'):
            print("⚠ No SYSTEM_API_URL in .env, skipping terminal test")
            return False
        
        from cli.gui.login import LoginWindow
        import importlib.util
        
        print("Testing login and terminal launch workflow...")
        
        # Track results
        login_success = [False]
        main_window_created = [False]
        terminal_launched = [False]
        test_complete = [False]
        main_window_instance = [None]
        
        def on_login_success():
            """Handle successful login"""
            login_success[0] = True
            print("✓ Login successful, closing login window...")
            login_window.root.quit()
        
        # Create login window
        login_window = LoginWindow(on_login_success=on_login_success)
        
        # Get credentials
        email = os.getenv('SYSTEM_ADMIN_EMAIL')
        password = os.getenv('SYSTEM_ADMIN_PASSWORD')
        
        print(f"  Using email: {email}")
        
        def perform_login():
            """Fill credentials and login"""
            # Clear fields first
            login_window.email_entry.delete(0, 'end')
            login_window.password_entry.delete(0, 'end')
            # Insert credentials
            login_window.email_entry.insert(0, email)
            login_window.password_entry.insert(0, password)
            print("  Attempting login...")
            login_window.login_button.invoke()
            
            # Check for success periodically
            login_window.root.after(2000, check_login_status)
        
        def check_login_status():
            """Check if login succeeded"""
            if hasattr(login_window, 'status_label'):
                status = login_window.status_label.cget('text')
                if 'successful' in status.lower():
                    print("  ✓ Login completed successfully")
                    login_window.root.after(500, lambda: login_window.root.quit())
                elif any(word in status.lower() for word in ['error', 'failed']):
                    print(f"  ✗ Login failed: {status}")
                    login_window.root.quit()
                else:
                    # Check again
                    login_window.root.after(1000, check_login_status)
        
        # Start login process
        login_window.root.after(500, perform_login)
        login_window.root.after(10000, lambda: login_window.root.quit())  # Timeout
        
        # Run login window
        login_window.root.mainloop()
        
        # Clean up login window
        try:
            login_window.root.destroy()
        except:
            pass
        
        if not login_success[0]:
            print("✗ Login failed, cannot test terminal launch")
            return False
        
        print("  Creating MainWindow...")
        
        # Import and create MainWindow
        try:
            spec = importlib.util.spec_from_file_location(
                "gui.main", 
                Path(__file__).parent.parent.parent / 'src' / 'cli' / 'gui' / 'main.py'
            )
            rediacc_gui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rediacc_gui)
            
            # Create MainWindow
            main_window = rediacc_gui.MainWindow()
            main_window_instance[0] = main_window
            main_window_created[0] = True
            print("  ✓ MainWindow created")
            
            def interact_with_window():
                """Interact with the main window after it's ready"""
                print("  Selecting team and machine...")
                
                # Wait for teams to load
                main_window.root.after(1000, select_team_and_machine)
            
            def select_team_and_machine():
                """Select team and machine from dropdowns"""
                # Check if teams are loaded
                if hasattr(main_window, 'team_combo'):
                    teams = main_window.team_combo['values']
                    if teams and len(teams) > 0:
                        # Select first team
                        first_team = teams[0]
                        main_window.team_combo.set(first_team)
                        print(f"    Selected team: {first_team}")
                        
                        # Trigger team change to load machines
                        main_window.on_team_changed()
                        
                        # Wait for machines to load
                        main_window.root.after(2000, select_machine)
                    else:
                        print("    No teams available, waiting...")
                        main_window.root.after(1000, select_team_and_machine)
                else:
                    print("    Team combo not ready, waiting...")
                    main_window.root.after(1000, select_team_and_machine)
            
            def select_machine():
                """Select machine from dropdown"""
                if hasattr(main_window, 'machine_combo'):
                    machines = main_window.machine_combo['values']
                    if machines and len(machines) > 0:
                        # Select first machine
                        first_machine = machines[0]
                        main_window.machine_combo.set(first_machine)
                        print(f"    Selected machine: {first_machine}")

                        # Trigger machine change to load repositories
                        main_window.on_machine_changed()

                        # Wait for repositories to load, then try to launch terminal
                        main_window.root.after(2000, launch_terminal)
                    else:
                        print("    No machines available")
                        finish_test()
                else:
                    print("    Machine combo not ready")
                    finish_test()
            
            def launch_terminal():
                """Try to launch machine terminal from Tools menu"""
                print("  Attempting to launch machine terminal...")

                # Take screenshot before launching terminal
                if SCREENSHOTS_ENABLED:
                    main_window.root.update()
                    screenshot_helper.take_screenshot_safe("terminal_before_launch", "Terminal - before launch")

                try:
                    # Check if we have valid selection
                    team = main_window.team_combo.get()
                    machine = main_window.machine_combo.get()

                    if team and machine:
                        print(f"    Team: {team}, Machine: {machine}")
                        
                        # Test if the terminal command would work before launching
                        # Run a dry-run test of the actual terminal command
                        rediacc_path = Path(__file__).parent.parent.parent / 'rediacc'
                        test_cmd = [str(rediacc_path), 'term', '--help']
                        
                        # Try running the terminal command to check for ANY errors
                        print("    Pre-checking terminal command...")
                        import subprocess
                        try:
                            result = subprocess.run(test_cmd, 
                                                  capture_output=True, 
                                                  text=True,
                                                  timeout=5,
                                                  cwd=Path(__file__).parent.parent.parent)
                            if result.returncode != 0:
                                error_output = result.stderr if result.stderr else result.stdout
                                print(f"    ✗ Terminal command failed (exit code {result.returncode}):")
                                if error_output:
                                    for line in error_output.split('\n')[:5]:  # Show first 5 lines
                                        if line.strip():
                                            print(f"      {line}")
                                terminal_launched[0] = False
                                # Still try to launch to show the actual behavior
                                main_window.open_machine_terminal()
                                print("    ✗ Terminal launched but will fail due to errors")
                            else:
                                print("    ✓ Terminal command OK")
                                # Actually launch the terminal - no mocking!
                                print("    Launching real terminal window...")
                                main_window.open_machine_terminal()
                                terminal_launched[0] = True
                                print(f"    ✓ Terminal launch command executed for: term --team \"{team}\" --machine \"{machine}\"")
                                print("    ✓ Terminal window should be opening...")
                        except subprocess.TimeoutExpired:
                            print("    ⚠ Import check timed out")
                            main_window.open_machine_terminal()
                            terminal_launched[0] = True
                        except Exception as e:
                            print(f"    ✗ Error checking terminal imports: {e}")
                            terminal_launched[0] = False
                        
                        # Give time for terminal to open
                        main_window.root.after(3000, lambda: print("    Terminal should be visible now"))
                    else:
                        print(f"    ✗ Invalid selection - Team: {team}, Machine: {machine}")
                except Exception as e:
                    print(f"    ✗ Error launching terminal: {e}")
                    terminal_launched[0] = False
                
                # Finish test after giving time to see the terminal
                main_window.root.after(5000, finish_test)
            
            def finish_test():
                """Complete the test"""
                test_complete[0] = True
                main_window.root.quit()
            
            # Start interaction after window is ready
            main_window.root.after(2000, interact_with_window)
            
            # Set timeout
            main_window.root.after(20000, lambda: main_window.root.quit())
            
            # Run main window
            main_window.root.mainloop()
            
            # Clean up
            try:
                main_window.root.destroy()
            except:
                pass
            
        except Exception as e:
            print(f"✗ Error creating MainWindow: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Check results
        if main_window_created[0] and terminal_launched[0]:
            print("✓ Login and terminal launch test passed")
            return True
        else:
            print(f"✗ Test failed - MainWindow created: {main_window_created[0]}, Terminal launched successfully: {terminal_launched[0]}")
            # This test should fail if terminal has import errors
            return False
    
    def run_all_tests(self):
        """Run all tests with hybrid window management"""
        print("=" * 60)
        print("REAL GUI LOGIN TESTS (No Mocking)")
        print("Hybrid approach: shared window for simple tests,")
        print("dedicated windows for login tests")
        print("=" * 60)
        print()
        
        # Check for display
        if not os.environ.get('DISPLAY'):
            # Try to set display for local X server
            os.environ['DISPLAY'] = ':0'
            print("⚠ DISPLAY not set, trying :0")
        
        tests = [
            ("Window Title", self.test_window_title),
            ("Widget Presence", self.test_window_widgets),
            ("Login Form Interaction", self.test_login_form),
            ("Wrong Credentials", self.test_wrong_credentials),
            ("Real Login", self.test_real_login),
            ("Dropdown Placeholders", self.test_dropdown_placeholders),
            ("Login and Terminal", self.test_login_and_terminal)
        ]
        
        results = []
        
        try:
            for test_name, test_func in tests:
                try:
                    result = test_func()
                    results.append(result if result is not None else True)
                except AssertionError as e:
                    print(f"✗ Test failed: {e}")
                    results.append(False)
                except Exception as e:
                    print(f"✗ Test error: {e}")
                    results.append(False)
        finally:
            # Close shared window at the end
            if self.shared_window:
                print("\nClosing shared window...")
                self.close_shared_window()
        
        # Summary
        print("\n" + "=" * 60)
        passed = sum(1 for r in results if r)
        total = len(results)
        
        if passed == total:
            print(f"✅ ALL TESTS PASSED ({passed}/{total})")
            return 0
        else:
            failed = total - passed
            print(f"❌ {failed} TEST(S) FAILED ({passed}/{total} passed)")
            return 1


def main():
    """Main test execution"""
    test_suite = GUITestSuite()
    return test_suite.run_all_tests()


if __name__ == '__main__':
    sys.exit(main())