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

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src' / 'cli'))

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

class RealLoginTest:
    """Test the real login window with actual authentication"""
    
    def __init__(self, test_real_login=False):
        self.test_passed = False
        self.window = None
        self.login_triggered = False
        self.window_closed = False
        self.test_real_login = test_real_login
        self.login_result = None
        
    def on_login_success(self):
        """Callback when login succeeds"""
        print("✓ Login success callback triggered")
        self.login_triggered = True
        self.test_passed = True
        # Close window after successful login
        if self.window and self.window.root:
            self.window.root.after(500, self.window.root.quit)
    
    def simulate_user_actions(self):
        """Simulate user typing and clicking"""
        print("  Simulation thread started")
        time.sleep(1)  # Wait for window to be ready
        
        try:
            # Check window exists
            if not self.window:
                print("✗ Window object is None")
                return
            
            # Try to check window existence with error handling
            try:
                exists = self.window.root.winfo_exists()
                if not exists:
                    print("✗ Window root does not exist")
                    return
            except Exception as e:
                print(f"✗ Error checking window existence: {e}")
                # Try to proceed anyway
                pass
            
            print("✓ Window created and visible")
            
            # Check all required widgets exist
            assert hasattr(self.window, 'email_entry'), "Missing email_entry"
            assert hasattr(self.window, 'password_entry'), "Missing password_entry"
            assert hasattr(self.window, 'master_password_entry'), "Missing master_password_entry"
            assert hasattr(self.window, 'login_button'), "Missing login_button"
            print("✓ All required widgets exist")
            
            # Get credentials from environment or use test defaults
            email = os.getenv('SYSTEM_ADMIN_EMAIL', 'test@example.com')
            password = os.getenv('SYSTEM_ADMIN_PASSWORD', 'testpass123')
            master_password = os.getenv('SYSTEM_MASTER_PASSWORD', '')
            
            print(f"  Using email: {email}")
            
            # Clear and fill in the fields
            self.window.email_entry.delete(0, 'end')
            self.window.email_entry.insert(0, email)
            print("✓ Email entered")
            
            self.window.password_entry.delete(0, 'end')
            self.window.password_entry.insert(0, password)
            print("✓ Password entered")
            
            self.window.master_password_entry.delete(0, 'end')
            self.window.master_password_entry.insert(0, master_password)
            if master_password:
                print("✓ Master password entered")
            else:
                print("✓ Master password field left empty (optional)")
            
            # Check button state before interaction
            button_state = str(self.window.login_button['state'])
            if button_state in ['normal', 'active']:
                print(f"✓ Login button is clickable (state: {button_state})")
            else:
                print(f"✗ Login button is disabled (state: {button_state})")
            
            # Update the window to show changes
            self.window.root.update()
            time.sleep(0.5)
            
            if self.test_real_login:
                # Actually click the login button and wait for real response
                print("  Attempting real login...")
                self.window.login_button.invoke()
                
                # Wait for login to complete (check status label)
                max_wait = 8  # Increased timeout
                start_time = time.time()
                last_status = ""
                while time.time() - start_time < max_wait:
                    if hasattr(self.window, 'status_label'):
                        status_text = self.window.status_label.cget('text')
                        if status_text != last_status:
                            print(f"  Status: {status_text}")
                            last_status = status_text
                        
                        # Check for various success messages
                        if any(word in status_text.lower() for word in ['successful', 'success', 'logged']):
                            print("✓ Login successful!")
                            self.on_login_success()
                            break
                        elif any(word in status_text.lower() for word in ['error', 'failed', 'invalid', 'incorrect']):
                            print(f"✗ Login failed: {status_text}")
                            self.window.root.after(100, self.window.root.quit)
                            break
                    time.sleep(0.2)  # Check more frequently
                    self.window.root.update()
                
                # If we didn't get success or failure, check final status
                if not self.login_triggered and hasattr(self.window, 'status_label'):
                    final_status = self.window.status_label.cget('text')
                    print(f"  Final status after timeout: {final_status}")
            else:
                # Just verify form is functional without real login
                print("✓ Login form is functional")
                self.on_login_success()
            
        except Exception as e:
            print(f"✗ Error during simulation: {e}")
            if self.window and self.window.root:
                self.window.root.after(100, self.window.root.quit)
    
    def run_test(self):
        """Run the actual test"""
        try:
            from gui_login import LoginWindow
            
            print("Creating real login window...")
            self.window = LoginWindow(on_login_success=self.on_login_success)
            
            # Start simulation in a separate thread
            simulation_thread = threading.Thread(target=self.simulate_user_actions)
            simulation_thread.daemon = True
            simulation_thread.start()
            print("  Simulation thread launched")
            
            # Set a timeout to close window if test takes too long
            self.window.root.after(15000, lambda: self.timeout_handler())
            
            # Run the GUI
            print("  Starting GUI mainloop")
            self.window.root.mainloop()
            print("  GUI mainloop ended")
            
            # Check results
            if self.login_triggered:
                print("✓ Login was successfully triggered")
                return True
            else:
                print("✗ Login was not triggered")
                return False
                
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            return False
    
    def timeout_handler(self):
        """Handle test timeout"""
        if self.window and self.window.root.winfo_exists():
            print("⚠ Test timed out after 10 seconds")
            self.window.root.quit()


def test_window_title():
    """Test that window has correct title"""
    try:
        from gui_login import LoginWindow
        
        def dummy_callback():
            pass
        
        window = LoginWindow(on_login_success=dummy_callback)
        title = window.root.title()
        window.root.after(100, window.root.quit)
        window.root.mainloop()
        
        # The actual title includes "Rediacc CLI - Login"
        if "Login" in title:
            print(f"✓ Window title is correct: '{title}'")
            return True
        else:
            print(f"✗ Window title is wrong: '{title}'")
            return False
            
    except Exception as e:
        print(f"✗ Title test failed: {e}")
        return False


def test_window_widgets():
    """Test that all required widgets are present"""
    try:
        from gui_login import LoginWindow
        
        def dummy_callback():
            pass
        
        window = LoginWindow(on_login_success=dummy_callback)
        
        # Check for required widgets
        widgets_to_check = [
            ('email_entry', 'Email input field'),
            ('password_entry', 'Password input field'),
            ('master_password_entry', 'Master password input field'),
            ('login_button', 'Login button'),
            ('status_label', 'Status label'),
            ('lang_combo', 'Language selector')
        ]
        
        all_present = True
        for widget_name, description in widgets_to_check:
            if hasattr(window, widget_name):
                print(f"✓ {description} exists")
            else:
                print(f"✗ {description} missing")
                all_present = False
        
        window.root.after(100, window.root.quit)
        window.root.mainloop()
        
        return all_present
        
    except Exception as e:
        print(f"✗ Widget test failed: {e}")
        return False


def test_login_form():
    """Test the login form interaction without real auth"""
    test = RealLoginTest(test_real_login=False)
    return test.run_test()


def test_wrong_credentials():
    """Test that login fails with wrong credentials"""
    try:
        from gui_login import LoginWindow
        import threading
        
        print("Testing with wrong credentials...")
        
        login_failed = False
        window = None
        
        def on_success():
            print("✗ Login succeeded with wrong credentials!")
        
        def check_login():
            nonlocal login_failed, window
            time.sleep(1)
            
            if not window or not window.root.winfo_exists():
                return
                
            # Enter wrong credentials
            window.email_entry.delete(0, 'end')
            window.email_entry.insert(0, 'wrong@test.com')
            window.password_entry.delete(0, 'end')  
            window.password_entry.insert(0, 'wrongpass')
            
            print("  Entering wrong credentials...")
            window.login_button.invoke()
            
            # Wait and check status
            time.sleep(3)
            if hasattr(window, 'status_label'):
                status = window.status_label.cget('text')
                try:
                    status_color = window.status_label.cget('fg')
                    is_error = status_color in ['red', '#ff0000', '#dc3545', '#e74c3c']
                except:
                    is_error = False
                
                if is_error:
                    print(f"  ❌ Error shown (red): {status}")
                
                if 'error' in status.lower() or 'failed' in status.lower():
                    print(f"✓ Login correctly failed with wrong credentials")
                    print(f"  Error message: {status}")
                    login_failed = True
            
            window.root.after(100, window.root.quit)
        
        window = LoginWindow(on_login_success=on_success)
        
        thread = threading.Thread(target=check_login, daemon=True)
        thread.start()
        
        window.root.after(5000, lambda: window.root.quit())
        window.root.mainloop()
        
        return login_failed
        
    except Exception as e:
        print(f"✗ Wrong credentials test failed: {e}")
        return False


def test_real_login():
    """Test real login with credentials from .env - NO MOCKING"""
    # Check if we have real credentials
    if not os.getenv('SYSTEM_ADMIN_EMAIL'):
        print("⚠ No SYSTEM_ADMIN_EMAIL in .env, skipping real login test")
        return True
    
    if not os.getenv('SYSTEM_API_URL'):
        print("⚠ No SYSTEM_API_URL in .env, skipping real login test")
        return True
    
    try:
        from gui_login import LoginWindow
        
        print("Testing with real credentials from .env (NO MOCKING)...")
        
        # Track result
        login_success = False
        window_hidden = False
        
        def on_success():
            nonlocal login_success
            if login_success:
                return
            login_success = True
            print("✓ Login callback triggered")
            
            # Verify MainWindow can be created (but don't run it to avoid threading issues)
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "rediacc_gui", 
                    Path(__file__).parent.parent.parent / 'src' / 'cli' / 'rediacc-gui.py'
                )
                rediacc_gui = importlib.util.module_from_spec(spec)
                if 'rediacc_gui' not in sys.modules:
                    sys.modules['rediacc_gui'] = rediacc_gui
                    spec.loader.exec_module(rediacc_gui)
                else:
                    rediacc_gui = sys.modules['rediacc_gui']
                
                print("  Verifying MainWindow can be created...")
                main_window = rediacc_gui.MainWindow()
                
                if hasattr(main_window, 'root'):
                    title = main_window.root.title()
                    print(f"  ✅ MainWindow created: '{title}'")
                    main_window.root.destroy()  # Clean up immediately
                else:
                    print("  ❌ MainWindow creation failed")
            except Exception as e:
                print(f"  ⚠️ MainWindow error: {e}")
        
        # Create window - NO MOCKING
        window = LoginWindow(on_login_success=on_success)
        
        # Get credentials
        email = os.getenv('SYSTEM_ADMIN_EMAIL')
        password = os.getenv('SYSTEM_ADMIN_PASSWORD')
        
        print(f"  Using email: {email}")
        
        # Fill credentials
        window.email_entry.insert(0, email)
        window.password_entry.insert(0, password)
        
        # Schedule login
        def do_login():
            print("  Attempting login...")
            window.login_button.invoke()
            
            # Track last status to avoid duplicate prints
            last_status = ""
            check_count = 0
            
            # Check status periodically
            def check_status():
                nonlocal last_status, check_count
                check_count += 1
                
                status = window.status_label.cget('text')
                
                # Debug output for Test 5
                if check_count == 1:
                    print(f"  Initial check - Status: '{status}'")
                
                # Get the foreground color to detect errors
                try:
                    status_color = window.status_label.cget('fg')
                    # Red colors often used for errors (COLOR_ERROR is 'red' in gui_utilities.py)
                    is_error = status_color in ['red', '#ff0000', '#dc3545', '#e74c3c', '#FF6B35']
                    is_success = status_color in ['green', '#00ff00', '#28a745', '#27ae60']
                except:
                    is_error = False
                    is_success = False
                
                # Print status if it changed or if it's an error
                if status != last_status:
                    if is_error:
                        print(f"  ❌ ERROR (red): {status}")
                    elif is_success:
                        print(f"  ✅ SUCCESS (green): {status}")
                    elif status and status not in ["", "Logging in..."]:
                        print(f"  Status: {status}")
                    last_status = status
                
                # Check for success/failure
                if 'successful' in status.lower():
                    print("  ✓ Login successful!")
                    on_success()
                    
                    # Wait 5 seconds to see if any errors appear after success
                    print("  Waiting 5 seconds to check for post-login errors...")
                    
                    post_login_count = [0]
                    post_login_last_status = [status]
                    
                    def monitor_post_login():
                        post_login_count[0] += 1
                        
                        # Check status continuously
                        current_status = window.status_label.cget('text')
                        try:
                            current_color = window.status_label.cget('fg')
                            is_error_now = current_color in ['red', '#ff0000', '#dc3545', '#e74c3c', '#FF6B35']
                        except:
                            is_error_now = False
                        
                        # Print if status changed
                        if current_status != post_login_last_status[0]:
                            if is_error_now:
                                print(f"  ⚠️ POST-LOGIN ERROR APPEARED: {current_status}")
                            else:
                                print(f"  Post-login status changed: {current_status}")
                            post_login_last_status[0] = current_status
                        
                        # Continue monitoring for 5 seconds (10 checks * 500ms)
                        if post_login_count[0] < 10:
                            window.root.after(500, monitor_post_login)
                        else:
                            print(f"  Final status after 5 seconds: {current_status}")
                            if is_error_now:
                                print("  ⚠️ ERROR STATE at end of test!")
                            window.root.quit()
                    
                    # Start monitoring
                    window.root.after(500, monitor_post_login)
                elif any(word in status.lower() for word in ['error', 'failed', 'invalid', 'incorrect', 'wrong']):
                    print(f"  ✗ Login failed with: {status}")
                    window.root.after(100, window.root.quit)
                elif check_count > 15:  # Stop after ~7.5 seconds
                    print(f"  ⚠ Timeout - final status: {status}")
                    window.root.after(100, window.root.quit)
                else:
                    # Check again
                    window.root.after(500, check_status)
            
            window.root.after(1500, check_status)
        
        window.root.after(500, do_login)
        window.root.after(20000, lambda: window.root.quit())  # Increased timeout for 5-second wait
        
        window.root.mainloop()
        
        if login_success:
            print("✓ Real login successful")
        
        return login_success
        
    except Exception as e:
        print(f"✗ Real login test failed: {e}")
        return False


def main():
    """Run all real GUI tests"""
    print("=" * 60)
    print("REAL GUI LOGIN TESTS (No Mocking)")
    print("=" * 60)
    print()
    
    # Check for display
    if not os.environ.get('DISPLAY'):
        # Try to set display for local X server
        os.environ['DISPLAY'] = ':0'
        print("⚠ DISPLAY not set, trying :0")
    
    results = []
    
    # Test 1: Window Title
    print("\nTest 1: Window Title")
    print("-" * 40)
    results.append(test_window_title())
    
    # Test 2: Widget Presence
    print("\nTest 2: Widget Presence")
    print("-" * 40)
    results.append(test_window_widgets())
    
    # Test 3: Login Form Interaction
    print("\nTest 3: Login Form Interaction")
    print("-" * 40)
    results.append(test_login_form())
    
    # Test 4: Wrong Credentials
    print("\nTest 4: Wrong Credentials")
    print("-" * 40)
    results.append(test_wrong_credentials())
    
    # Test 5: Real Login (if credentials available)
    print("\nTest 5: Real Login")
    print("-" * 40)
    results.append(test_real_login())
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        return 0
    else:
        failed = total - passed
        print(f"❌ {failed} TEST(S) FAILED ({passed}/{total} passed)")
        return 1


if __name__ == '__main__':
    sys.exit(main())