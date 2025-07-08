#!/usr/bin/env python3
"""
Simplified Rediacc CLI GUI - Terminal and File Sync Tools Only
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import queue
import json
import os
import sys
import signal
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from datetime import datetime

# Import TokenManager for authentication
from token_manager import TokenManager

# Import subprocess runner for CLI commands
from subprocess_runner import SubprocessRunner



class BaseWindow:
    """Base class for all GUI windows"""
    def __init__(self, root: tk.Tk, title: str = "Rediacc CLI Tools"):
        self.root = root
        self.root.title(title)
        
        # Set up proper window close handling
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind Escape key to close window
        self.root.bind('<Escape>', lambda e: self.on_closing())
    
    def center_window(self, width: int = 800, height: int = 600):
        """Center window on screen"""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def on_closing(self):
        """Handle window close event"""
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        finally:
            sys.exit(0)


class LoginWindow(BaseWindow):
    """Simple login window"""
    def __init__(self, on_login_success: Callable):
        super().__init__(tk.Tk(), "Rediacc CLI - Login")
        self.on_login_success = on_login_success
        self.center_window(400, 300)
        self.create_widgets()
    
    def create_widgets(self):
        """Create login form"""
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Title
        title = tk.Label(main_frame, text="Rediacc CLI Login",
                        font=('Arial', 16, 'bold'))
        title.pack(pady=20)
        
        # Email field
        tk.Label(main_frame, text="Email:").pack(anchor='w', pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.pack(fill='x', pady=5)
        
        # Password field
        tk.Label(main_frame, text="Password:").pack(anchor='w', pady=5)
        self.password_entry = ttk.Entry(main_frame, width=40, show='*')
        self.password_entry.pack(fill='x', pady=5)
        
        # Login button
        self.login_button = ttk.Button(main_frame, text="Login", command=self.login)
        self.login_button.pack(pady=20)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="")
        self.status_label.pack()
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())
        
        # Focus on email field
        self.email_entry.focus()
    
    def login(self):
        """Handle login"""
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        
        if not email or not password:
            messagebox.showerror("Error", "Please enter both email and password")
            return
        
        self.login_button.config(state='disabled')
        self.status_label.config(text="Logging in...")
        
        # Run login in thread
        thread = threading.Thread(target=self._do_login, args=(email, password))
        thread.daemon = True
        thread.start()
    
    def _do_login(self, email: str, password: str):
        """Perform login in background thread"""
        try:
            runner = SubprocessRunner()
            result = runner.run_cli_command(['--output', 'json', 'login', '--email', email, '--password', password])
            
            if result['success']:
                # Login successful - token is already saved by CLI
                self.root.after(0, self.login_success)
            else:
                error = result.get('error', 'Login failed')
                self.root.after(0, lambda: self.login_error(error))
        except Exception as e:
            self.root.after(0, lambda: self.login_error(str(e)))
    
    def login_success(self):
        """Handle successful login"""
        self.status_label.config(text="Login successful!", fg='green')
        self.root.withdraw()
        self.on_login_success()
    
    def login_error(self, error: str):
        """Handle login error"""
        self.login_button.config(state='normal')
        self.status_label.config(text=f"Error: {error}", fg='red')


class MainWindow(BaseWindow):
    """Main window with Terminal and File Sync tools"""
    def __init__(self):
        super().__init__(tk.Tk(), "Rediacc CLI Tools")
        self.runner = SubprocessRunner()
        self.center_window(900, 600)
        self.create_widgets()
        
        # Load initial data
        self.load_teams()
    
    def _get_name(self, item, *fields):
        """Get name from item trying multiple field names"""
        for field in fields:
            if field in item:
                return item[field]
        return ''
    
    def _handle_api_error(self, error_msg):
        """Handle API errors, especially authentication errors"""
        # Check if it's an authentication error
        if '401' in str(error_msg) or 'Not authenticated' in error_msg or 'Invalid request credential' in error_msg:
            self.status_bar.config(text="Authentication expired. Please login again.", fg='red')
            messagebox.showerror("Authentication Error", 
                               "Your session has expired. Please login again.")
            # Clear token and restart GUI
            TokenManager.clear_token()
            self.root.destroy()
            launch_gui()
            return True
        return False
    
    def create_widgets(self):
        """Create main window widgets"""
        # Top frame with user info and logout
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill='x', padx=5, pady=5)
        
        # User info
        auth_info = TokenManager.get_auth_info()
        user_text = f"User: {auth_info.get('email', 'Unknown')}"
        tk.Label(top_frame, text=user_text).pack(side='left', padx=10)
        
        # Logout button
        ttk.Button(top_frame, text="Logout", command=self.logout).pack(side='right', padx=10)
        
        # Common selection frame
        common_frame = tk.LabelFrame(self.root, text="Resource Selection")
        common_frame.pack(fill='x', padx=10, pady=5)
        
        # Team selection
        team_frame = tk.Frame(common_frame)
        team_frame.pack(fill='x', padx=10, pady=5)
        tk.Label(team_frame, text="Team:", width=12, anchor='w').pack(side='left', padx=5)
        self.team_combo = ttk.Combobox(team_frame, width=40, state='readonly')
        self.team_combo.pack(side='left', padx=5, fill='x', expand=True)
        self.team_combo.bind('<<ComboboxSelected>>', lambda e: self.on_team_changed())
        
        # Machine selection
        machine_frame = tk.Frame(common_frame)
        machine_frame.pack(fill='x', padx=10, pady=5)
        tk.Label(machine_frame, text="Machine:", width=12, anchor='w').pack(side='left', padx=5)
        self.machine_combo = ttk.Combobox(machine_frame, width=40, state='readonly')
        self.machine_combo.pack(side='left', padx=5, fill='x', expand=True)
        self.machine_combo.bind('<<ComboboxSelected>>', lambda e: self.on_machine_changed())
        
        # Repository selection
        repo_frame = tk.Frame(common_frame)
        repo_frame.pack(fill='x', padx=10, pady=5)
        tk.Label(repo_frame, text="Repository:", width=12, anchor='w').pack(side='left', padx=5)
        self.repo_combo = ttk.Combobox(repo_frame, width=40, state='readonly')
        self.repo_combo.pack(side='left', padx=5, fill='x', expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Terminal tab
        self.terminal_frame = tk.Frame(self.notebook)
        self.notebook.add(self.terminal_frame, text="Terminal Access")
        self.create_terminal_tab()
        
        # File Sync tab
        self.sync_frame = tk.Frame(self.notebook)
        self.notebook.add(self.sync_frame, text="File Sync")
        self.create_sync_tab()
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="Ready",
                                 anchor='w', padx=10)
        self.status_bar.pack(side='bottom', fill='x')
    
    def create_terminal_tab(self):
        """Create terminal access interface"""
        # Control frame
        control_frame = tk.Frame(self.terminal_frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Command input
        command_frame = tk.Frame(control_frame)
        command_frame.pack(fill='x', pady=5)
        tk.Label(command_frame, text="Command:", width=12, anchor='w').pack(side='left', padx=5)
        self.command_entry = ttk.Entry(command_frame)
        self.command_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        # Buttons
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Execute Command",
                  command=self.execute_terminal_command).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Open Interactive Repo Terminal",
                  command=self.open_repo_terminal).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Open Interactive Machine Terminal",
                  command=self.open_machine_terminal).pack(side='left', padx=5)
        
        # Output area
        output_frame = tk.Frame(self.terminal_frame)
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(output_frame, text="Output:").pack(anchor='w')
        
        self.terminal_output = scrolledtext.ScrolledText(output_frame, height=15,
                                                       font=('Consolas', 10))
        self.terminal_output.pack(fill='both', expand=True, pady=5)
    
    def create_sync_tab(self):
        """Create file sync interface"""
        # Control frame
        control_frame = tk.Frame(self.sync_frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Sync direction
        direction_frame = tk.Frame(control_frame)
        direction_frame.pack(fill='x', pady=5)
        tk.Label(direction_frame, text="Direction:", width=12, anchor='w').pack(side='left', padx=5)
        self.sync_direction = tk.StringVar(value='upload')
        ttk.Radiobutton(direction_frame, text="Upload", variable=self.sync_direction,
                       value='upload').pack(side='left', padx=5)
        ttk.Radiobutton(direction_frame, text="Download", variable=self.sync_direction,
                       value='download').pack(side='left', padx=5)
        
        # Local path
        path_frame = tk.Frame(control_frame)
        path_frame.pack(fill='x', pady=5)
        tk.Label(path_frame, text="Local Path:", width=12, anchor='w').pack(side='left', padx=5)
        self.local_path_entry = ttk.Entry(path_frame)
        self.local_path_entry.pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(path_frame, text="Browse...",
                  command=self.browse_local_path).pack(side='left', padx=5)
        
        # Options
        options_frame = tk.LabelFrame(control_frame, text="Options")
        options_frame.pack(fill='x', pady=10)
        
        option_container = tk.Frame(options_frame)
        option_container.pack(pady=5)
        
        self.mirror_var = tk.BooleanVar()
        tk.Checkbutton(option_container, text="Mirror (delete extra files)",
                      variable=self.mirror_var).pack(side='left', padx=10)
        
        self.verify_var = tk.BooleanVar()
        tk.Checkbutton(option_container, text="Verify after transfer",
                      variable=self.verify_var).pack(side='left', padx=10)
        
        # Sync button
        self.sync_button = ttk.Button(control_frame, text="Start Sync",
                                    command=self.start_sync)
        self.sync_button.pack(pady=10)
        
        # Output area
        output_frame = tk.Frame(self.sync_frame)
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(output_frame, text="Output:").pack(anchor='w')
        
        self.sync_output = scrolledtext.ScrolledText(output_frame, height=15,
                                                    font=('Consolas', 10))
        self.sync_output.pack(fill='both', expand=True, pady=5)
    
    def load_teams(self):
        """Load available teams"""
        self.status_bar.config(text="Loading teams...")
        self.root.update()
        
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'teams'])
        if result['success'] and result.get('data'):
            teams = [self._get_name(team, 'teamName', 'name') for team in result['data']]
            self.update_teams(teams)
        else:
            error_msg = result.get('error', 'Failed to load teams')
            if not self._handle_api_error(error_msg):
                self.status_bar.config(text=f"Error: {error_msg}", fg='red')
    
    def on_team_changed(self):
        """Handle team selection change"""
        self.load_machines()
    
    def on_machine_changed(self):
        """Handle machine selection change"""
        self.load_repositories()
    
    def update_teams(self, teams: list):
        """Update team dropdowns"""
        self.team_combo['values'] = teams
        if teams:
            self.team_combo.set(teams[0])
            self.on_team_changed()
        self.status_bar.config(text="Ready")
    
    def load_machines(self):
        """Load machines for selected team"""
        team = self.team_combo.get()
        if not team:
            return
        
        self.status_bar.config(text=f"Loading machines for {team}...")
        self.root.update()
        
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'team-machines', team])
        if result['success'] and result.get('data'):
            machines = [self._get_name(m, 'machineName', 'name') for m in result['data']]
            self.update_machines(machines)
        else:
            error_msg = result.get('error', 'Failed to load machines')
            if not self._handle_api_error(error_msg):
                self.status_bar.config(text=f"Error: {error_msg}", fg='red')
    
    def update_machines(self, machines: list):
        """Update machine dropdown"""
        self.machine_combo['values'] = machines
        if machines:
            self.machine_combo.set(machines[0])
            self.load_repositories()
        self.status_bar.config(text="Ready")
    
    def load_repositories(self):
        """Load repositories for selected team"""
        team = self.team_combo.get()
        if not team:
            return
        
        self.status_bar.config(text=f"Loading repositories for {team}...")
        self.root.update()
        
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'team-repositories', team])
        if result['success'] and result.get('data'):
            repos = [self._get_name(r, 'repositoryName', 'name', 'repoName') for r in result['data']]
            self.update_repositories(repos)
        else:
            error_msg = result.get('error', 'Failed to load repositories')
            if not self._handle_api_error(error_msg):
                self.status_bar.config(text=f"Error: {error_msg}", fg='red')
    
    def update_repositories(self, repos: list):
        """Update repository dropdown"""
        self.repo_combo['values'] = repos
        if repos:
            self.repo_combo.set(repos[0])
        self.status_bar.config(text="Ready")
    
    
    def execute_terminal_command(self):
        """Execute a terminal command"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        command = self.command_entry.get().strip()
        
        if not team or not machine or not repo or not command:
            messagebox.showerror("Error", "Please select team, machine, repository and enter a command")
            return
        
        self.terminal_output.delete(1.0, tk.END)
        self.status_bar.config(text="Executing command...")
        
        def execute():
            cmd = ['term', '--team', team, '--machine', machine, '--repo', repo, '--command', command]
            
            result = self.runner.run_command(cmd)
            output = result.get('output', '') + result.get('error', '')
            # Check for authentication errors in output
            if '401' in output or 'Not authenticated' in output or 'Invalid request credential' in output:
                self.root.after(0, lambda: self._handle_api_error(output))
            else:
                self.root.after(0, lambda: self.show_terminal_output(output))
        
        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()
    
    def show_terminal_output(self, output: str):
        """Display terminal output"""
        self.terminal_output.insert(tk.END, output)
        self.terminal_output.see(tk.END)
        self.status_bar.config(text="Command executed")
    
    def _launch_terminal(self, command: str, description: str):
        """Common method to launch terminal with given command"""
        # Build command with full path
        import os
        cli_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rediacc_path = os.path.join(os.path.dirname(cli_dir), 'rediacc')
        
        # Build full command with absolute path
        simple_cmd = f'{rediacc_path} {command}'
        
        # Show command in output area
        self.terminal_output.delete(1.0, tk.END)
        self.terminal_output.insert(tk.END, f"To open {description}, run this command in a terminal window:\n\n")
        self.terminal_output.insert(tk.END, simple_cmd + "\n\n")
        self.terminal_output.insert(tk.END, "Or from any directory:\n\n")
        self.terminal_output.insert(tk.END, f'cd {cli_dir} && {simple_cmd}\n\n')
        
        # Try to launch terminal, but don't worry if it fails
        try:
            # Check if running in WSL
            is_wsl = False
            try:
                with open('/proc/version', 'r') as f:
                    is_wsl = 'microsoft' in f.read().lower()
            except:
                pass
            
            if sys.platform == 'darwin':  # macOS
                cmd_str = f'cd {cli_dir} && {simple_cmd}'
                subprocess.Popen(['open', '-a', 'Terminal', '--', 'bash', '-c', cmd_str])
            elif is_wsl:
                # For WSL, try to open in Windows Terminal
                
                # Try Windows Terminal first
                try:
                    # Build the command as a list to avoid shell escaping issues
                    # We'll create a script that Windows Terminal can execute
                    import tempfile
                    
                    # Create a temporary script file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                        script_content = f'''#!/bin/bash
cd {cli_dir}
{simple_cmd}
'''
                        f.write(script_content)
                        script_path = f.name
                    
                    # Make script executable
                    os.chmod(script_path, 0o755)
                    
                    # Launch Windows Terminal with the script
                    wt_cmd = f'wt.exe new-tab wsl.exe {script_path}'
                    subprocess.Popen(['cmd.exe', '/c', wt_cmd], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                    self.terminal_output.insert(tk.END, f"\nLaunched in Windows Terminal...\n")
                    
                    # Clean up script after a delay
                    def cleanup_script():
                        import time
                        time.sleep(2)
                        try:
                            os.unlink(script_path)
                        except:
                            pass
                    
                    cleanup_thread = threading.Thread(target=cleanup_script)
                    cleanup_thread.daemon = True
                    cleanup_thread.start()
                except:
                    # Try PowerShell as fallback
                    try:
                        ps_cmd = f'start wsl bash -c "cd {cli_dir} && {simple_cmd}; read -p \'Press Enter to close...\'"'
                        subprocess.Popen(['powershell.exe', '-Command', ps_cmd], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        self.terminal_output.insert(tk.END, f"\nLaunched in new WSL window...\n")
                    except:
                        # Last resort: use cmd.exe directly
                        try:
                            cmd_cmd = f'start cmd /c wsl bash -c "cd {cli_dir} && {simple_cmd}; read -p \'Press Enter to close...\'"'
                            subprocess.Popen(['cmd.exe', '/c', cmd_cmd], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                            self.terminal_output.insert(tk.END, f"\nLaunched in new window...\n")
                        except:
                            self.terminal_output.insert(tk.END, f"\nNote: Could not launch terminal automatically in WSL.\n")
            elif sys.platform.startswith('linux'):
                # Regular Linux
                cmd_str = f'cd {cli_dir} && {simple_cmd}; echo "Press Enter to close..."; read'
                
                terminals = [
                    ['gnome-terminal', '--', 'bash', '-c', cmd_str],
                    ['konsole', '-e', 'bash', '-c', cmd_str],
                    ['xfce4-terminal', '-e', f'bash -c "{cmd_str}"'],
                    ['mate-terminal', '-e', f'bash -c "{cmd_str}"'],
                    ['terminator', '-e', f'bash -c "{cmd_str}"'],
                ]
                
                for term_cmd in terminals:
                    try:
                        subprocess.Popen(term_cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        self.terminal_output.insert(tk.END, f"\nLaunched terminal window...\n")
                        break
                    except:
                        continue
        except Exception as e:
            # If terminal launch fails, the command is already shown in the output area
            pass
    
    def open_repo_terminal(self):
        """Open interactive repository terminal in new window"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not team or not machine or not repo:
            messagebox.showerror("Error", "Please select team, machine and repository")
            return
        
        command = f'term --team "{team}" --machine "{machine}" --repo "{repo}"'
        self._launch_terminal(command, "an interactive repository terminal")
    
    def open_machine_terminal(self):
        """Open interactive machine terminal in new window (without repository)"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        
        if not team or not machine:
            messagebox.showerror("Error", "Please select team and machine")
            return
        
        command = f'term --team "{team}" --machine "{machine}"'
        self._launch_terminal(command, "an interactive machine terminal")
    
    def browse_local_path(self):
        """Browse for local directory"""
        if self.sync_direction.get() == 'upload':
            path = filedialog.askdirectory()
        else:
            path = filedialog.askdirectory()
        
        if path:
            self.local_path_entry.delete(0, tk.END)
            self.local_path_entry.insert(0, path)
    
    def start_sync(self):
        """Start file synchronization"""
        direction = self.sync_direction.get()
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        local_path = self.local_path_entry.get().strip()
        
        if not all([team, machine, repo, local_path]):
            messagebox.showerror("Error", "Please fill in all fields")
            return
        
        self.sync_output.delete(1.0, tk.END)
        self.sync_button.config(state='disabled')
        self.status_bar.config(text=f"Starting {direction}...")
        
        def sync():
            cmd = ['sync', direction, '--team', team, '--machine', machine, 
                   '--repo', repo, '--local', local_path]
            
            if self.mirror_var.get():
                cmd.extend(['--mirror', '--confirm'])
            if self.verify_var.get():
                cmd.append('--verify')
            
            result = self.runner.run_command(cmd)
            output = result.get('output', '') + result.get('error', '')
            self.root.after(0, lambda: self.show_sync_output(output))
        
        thread = threading.Thread(target=sync)
        thread.daemon = True
        thread.start()
    
    def show_sync_output(self, output: str):
        """Display sync output"""
        self.sync_output.insert(tk.END, output)
        self.sync_output.see(tk.END)
        self.sync_button.config(state='normal')
        self.status_bar.config(text="Sync completed")
    
    def logout(self):
        """Logout and return to login screen"""
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            TokenManager.clear_token()
            self.root.destroy()
            launch_gui()


def launch_gui():
    """Launch the simplified GUI application"""
    import signal
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal. Closing GUI...")
        try:
            import tkinter as tk
            for widget in tk._default_root.winfo_children() if tk._default_root else []:
                widget.destroy()
            if tk._default_root:
                tk._default_root.quit()
                tk._default_root.destroy()
        except:
            pass
        finally:
            sys.exit(0)
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check if already authenticated and token is valid
    token_valid = False
    if TokenManager.is_authenticated():
        # Test if the token is still valid by making a simple API call
        try:
            runner = SubprocessRunner()
            result = runner.run_cli_command(['--output', 'json', 'list', 'teams'])
            token_valid = result.get('success', False)
        except:
            token_valid = False
        
        # If token is invalid, clear it
        if not token_valid:
            TokenManager.clear_token()
    
    if token_valid:
        # Token is valid, show main window
        main_window = MainWindow()
        main_window.root.mainloop()
    else:
        # Show login window
        def on_login_success():
            main_window = MainWindow()
            main_window.root.mainloop()
        
        login_window = LoginWindow(on_login_success)
        # Make the main loop check for interrupts periodically
        def check_interrupt():
            try:
                login_window.root.after(100, check_interrupt)
            except:
                pass
        check_interrupt()
        login_window.root.mainloop()


if __name__ == "__main__":
    launch_gui()