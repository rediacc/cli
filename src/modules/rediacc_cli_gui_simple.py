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

# Color schemes
THEMES = {
    'dark': {
        'bg_dark': '#1e1e1e',
        'bg_light': '#2d2d30',
        'bg_hover': '#3e3e42',
        'fg_primary': '#cccccc',
        'fg_secondary': '#969696',
        'accent': '#007acc',
        'success': '#4caf50',
        'error': '#f44336',
        'warning': '#ff9800',
        'border': '#464647',
        'header': '#ffffff'
    },
    'light': {
        'bg_dark': '#f3f3f3',
        'bg_light': '#ffffff',
        'bg_hover': '#e0e0e0',
        'fg_primary': '#1e1e1e',
        'fg_secondary': '#616161',
        'accent': '#0078d4',
        'success': '#4caf50',
        'error': '#d32f2f',
        'warning': '#f57c00',
        'border': '#d0d0d0',
        'header': '#000000'
    }
}

# Load theme preference
current_theme = 'dark'
COLORS = THEMES[current_theme]


class BaseWindow:
    """Base class for all GUI windows"""
    def __init__(self, root: tk.Tk, title: str = "Rediacc CLI Tools"):
        self.root = root
        self.root.title(title)
        self.root.configure(bg=COLORS['bg_dark'])
        
        # Set window style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Set up proper window close handling
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind Escape key to close window
        self.root.bind('<Escape>', lambda e: self.on_closing())
    
    def configure_styles(self):
        """Configure ttk styles to match color scheme"""
        self.style.configure('TLabel', background=COLORS['bg_dark'], foreground=COLORS['fg_primary'])
        self.style.configure('TButton', background=COLORS['bg_light'], foreground=COLORS['fg_primary'])
        self.style.configure('TEntry', fieldbackground=COLORS['bg_light'], foreground=COLORS['fg_primary'])
        self.style.configure('TCombobox', fieldbackground=COLORS['bg_light'], foreground=COLORS['fg_primary'])
        self.style.configure('TNotebook', background=COLORS['bg_dark'])
        self.style.configure('TNotebook.Tab', background=COLORS['bg_light'], foreground=COLORS['fg_primary'])
        self.style.map('TNotebook.Tab', background=[('selected', COLORS['accent'])])
    
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
        self.token_manager = TokenManager()
        self.center_window(400, 300)
        self.create_widgets()
    
    def create_widgets(self):
        """Create login form"""
        # Main frame
        main_frame = tk.Frame(self.root, bg=COLORS['bg_dark'])
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Title
        title = tk.Label(main_frame, text="Rediacc CLI Login",
                        font=('Arial', 16, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=20)
        
        # Email field
        tk.Label(main_frame, text="Email:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).pack(anchor='w', pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.pack(fill='x', pady=5)
        
        # Password field
        tk.Label(main_frame, text="Password:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).pack(anchor='w', pady=5)
        self.password_entry = ttk.Entry(main_frame, width=40, show='*')
        self.password_entry.pack(fill='x', pady=5)
        
        # Login button
        self.login_button = ttk.Button(main_frame, text="Login", command=self.login)
        self.login_button.pack(pady=20)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="",
                                   bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'])
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
        self.status_label.config(text="Logging in...", fg=COLORS['fg_secondary'])
        
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
                # Get token info
                token_result = runner.run_cli_command(['--output', 'json', 'me'])
                if token_result['success'] and token_result.get('data'):
                    data = token_result['data']
                    self.token_manager.save_token(
                        data.get('token', ''),
                        email=email,
                        company=data.get('company'),
                        vault_company=data.get('vaultCompany')
                    )
                
                self.root.after(0, self.login_success)
            else:
                error = result.get('error', 'Login failed')
                self.root.after(0, lambda: self.login_error(error))
        except Exception as e:
            self.root.after(0, lambda: self.login_error(str(e)))
    
    def login_success(self):
        """Handle successful login"""
        self.status_label.config(text="Login successful!", fg=COLORS['success'])
        self.root.withdraw()
        self.on_login_success(self.token_manager)
    
    def login_error(self, error: str):
        """Handle login error"""
        self.login_button.config(state='normal')
        self.status_label.config(text=f"Error: {error}", fg=COLORS['error'])


class MainWindow(BaseWindow):
    """Main window with Terminal and File Sync tools"""
    def __init__(self, token_manager: TokenManager):
        super().__init__(tk.Tk(), "Rediacc CLI Tools")
        self.token_manager = token_manager
        self.runner = SubprocessRunner()
        self.center_window(900, 600)
        self.create_widgets()
        
        # Load initial data
        self.load_teams()
    
    def create_widgets(self):
        """Create main window widgets"""
        # Top frame with user info and logout
        top_frame = tk.Frame(self.root, bg=COLORS['bg_light'])
        top_frame.pack(fill='x', padx=5, pady=5)
        
        # User info
        auth_info = self.token_manager.get_auth_info()
        user_text = f"User: {auth_info.get('email', 'Unknown')}"
        tk.Label(top_frame, text=user_text,
                bg=COLORS['bg_light'], fg=COLORS['fg_secondary']).pack(side='left', padx=10)
        
        # Logout button
        ttk.Button(top_frame, text="Logout", command=self.logout).pack(side='right', padx=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Terminal tab
        self.terminal_frame = tk.Frame(self.notebook, bg=COLORS['bg_dark'])
        self.notebook.add(self.terminal_frame, text="Terminal Access")
        self.create_terminal_tab()
        
        # File Sync tab
        self.sync_frame = tk.Frame(self.notebook, bg=COLORS['bg_dark'])
        self.notebook.add(self.sync_frame, text="File Sync")
        self.create_sync_tab()
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="Ready",
                                 bg=COLORS['bg_light'], fg=COLORS['fg_secondary'],
                                 anchor='w', padx=10)
        self.status_bar.pack(side='bottom', fill='x')
    
    def create_terminal_tab(self):
        """Create terminal access interface"""
        # Control frame
        control_frame = tk.Frame(self.terminal_frame, bg=COLORS['bg_dark'])
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Team selection
        tk.Label(control_frame, text="Team:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=0, column=0, sticky='w', padx=5)
        self.team_combo = ttk.Combobox(control_frame, width=30, state='readonly')
        self.team_combo.grid(row=0, column=1, padx=5, pady=5)
        self.team_combo.bind('<<ComboboxSelected>>', lambda e: self.load_machines())
        
        # Machine selection
        tk.Label(control_frame, text="Machine:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=1, column=0, sticky='w', padx=5)
        self.machine_combo = ttk.Combobox(control_frame, width=30, state='readonly')
        self.machine_combo.grid(row=1, column=1, padx=5, pady=5)
        self.machine_combo.bind('<<ComboboxSelected>>', lambda e: self.load_repositories())
        
        # Repository selection (optional)
        tk.Label(control_frame, text="Repository (optional):",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=2, column=0, sticky='w', padx=5)
        self.repo_combo = ttk.Combobox(control_frame, width=30, state='readonly')
        self.repo_combo.grid(row=2, column=1, padx=5, pady=5)
        
        # Command input
        tk.Label(control_frame, text="Command:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=3, column=0, sticky='w', padx=5)
        self.command_entry = ttk.Entry(control_frame, width=50)
        self.command_entry.grid(row=3, column=1, padx=5, pady=5, sticky='ew')
        
        # Buttons
        button_frame = tk.Frame(control_frame, bg=COLORS['bg_dark'])
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Execute Command",
                  command=self.execute_terminal_command).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Open Interactive Terminal",
                  command=self.open_terminal).pack(side='left', padx=5)
        
        # Output area
        output_frame = tk.Frame(self.terminal_frame, bg=COLORS['bg_dark'])
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(output_frame, text="Output:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).pack(anchor='w')
        
        self.terminal_output = scrolledtext.ScrolledText(output_frame, height=15,
                                                       bg=COLORS['bg_light'],
                                                       fg=COLORS['fg_primary'],
                                                       font=('Consolas', 10))
        self.terminal_output.pack(fill='both', expand=True, pady=5)
    
    def create_sync_tab(self):
        """Create file sync interface"""
        # Control frame
        control_frame = tk.Frame(self.sync_frame, bg=COLORS['bg_dark'])
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Sync direction
        tk.Label(control_frame, text="Direction:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=0, column=0, sticky='w', padx=5)
        self.sync_direction = tk.StringVar(value='upload')
        ttk.Radiobutton(control_frame, text="Upload", variable=self.sync_direction,
                       value='upload').grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(control_frame, text="Download", variable=self.sync_direction,
                       value='download').grid(row=0, column=2, sticky='w')
        
        # Team selection
        tk.Label(control_frame, text="Team:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=1, column=0, sticky='w', padx=5)
        self.sync_team_combo = ttk.Combobox(control_frame, width=30, state='readonly')
        self.sync_team_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        self.sync_team_combo.bind('<<ComboboxSelected>>', lambda e: self.load_sync_machines())
        
        # Machine selection
        tk.Label(control_frame, text="Machine:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=2, column=0, sticky='w', padx=5)
        self.sync_machine_combo = ttk.Combobox(control_frame, width=30, state='readonly')
        self.sync_machine_combo.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        self.sync_machine_combo.bind('<<ComboboxSelected>>', lambda e: self.load_sync_repositories())
        
        # Repository selection
        tk.Label(control_frame, text="Repository:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=3, column=0, sticky='w', padx=5)
        self.sync_repo_combo = ttk.Combobox(control_frame, width=30, state='readonly')
        self.sync_repo_combo.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        
        # Local path
        tk.Label(control_frame, text="Local Path:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).grid(row=4, column=0, sticky='w', padx=5)
        self.local_path_entry = ttk.Entry(control_frame, width=40)
        self.local_path_entry.grid(row=4, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(control_frame, text="Browse...",
                  command=self.browse_local_path).grid(row=4, column=2, padx=5)
        
        # Options
        options_frame = tk.LabelFrame(control_frame, text="Options",
                                    bg=COLORS['bg_dark'], fg=COLORS['fg_primary'])
        options_frame.grid(row=5, column=0, columnspan=3, padx=5, pady=10, sticky='ew')
        
        self.mirror_var = tk.BooleanVar()
        tk.Checkbutton(options_frame, text="Mirror (delete extra files)",
                      variable=self.mirror_var,
                      bg=COLORS['bg_dark'], fg=COLORS['fg_primary'],
                      selectcolor=COLORS['bg_light']).grid(row=0, column=0, sticky='w', padx=5)
        
        self.verify_var = tk.BooleanVar()
        tk.Checkbutton(options_frame, text="Verify after transfer",
                      variable=self.verify_var,
                      bg=COLORS['bg_dark'], fg=COLORS['fg_primary'],
                      selectcolor=COLORS['bg_light']).grid(row=0, column=1, sticky='w', padx=5)
        
        # Sync button
        self.sync_button = ttk.Button(control_frame, text="Start Sync",
                                    command=self.start_sync)
        self.sync_button.grid(row=6, column=0, columnspan=3, pady=10)
        
        # Output area
        output_frame = tk.Frame(self.sync_frame, bg=COLORS['bg_dark'])
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(output_frame, text="Output:",
                bg=COLORS['bg_dark'], fg=COLORS['fg_primary']).pack(anchor='w')
        
        self.sync_output = scrolledtext.ScrolledText(output_frame, height=15,
                                                    bg=COLORS['bg_light'],
                                                    fg=COLORS['fg_primary'],
                                                    font=('Consolas', 10))
        self.sync_output.pack(fill='both', expand=True, pady=5)
    
    def load_teams(self):
        """Load available teams"""
        self.status_bar.config(text="Loading teams...")
        
        def load():
            result = self.runner.run_cli_command(['--output', 'json', 'list', 'teams'])
            if result['success'] and result.get('data'):
                teams = [team['name'] for team in result['data']]
                self.root.after(0, lambda: self.update_teams(teams))
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
    def update_teams(self, teams: list):
        """Update team dropdowns"""
        self.team_combo['values'] = teams
        self.sync_team_combo['values'] = teams
        if teams:
            self.team_combo.set(teams[0])
            self.sync_team_combo.set(teams[0])
            self.load_machines()
            self.load_sync_machines()
        self.status_bar.config(text="Ready")
    
    def load_machines(self):
        """Load machines for selected team"""
        team = self.team_combo.get()
        if not team:
            return
        
        self.status_bar.config(text=f"Loading machines for {team}...")
        
        def load():
            result = self.runner.run_cli_command(['--output', 'json', 'list', 'machines', '--team', team])
            if result['success'] and result.get('data'):
                machines = [m['name'] for m in result['data']]
                self.root.after(0, lambda: self.update_machines(machines))
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
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
        
        def load():
            result = self.runner.run_cli_command(['--output', 'json', 'list', 'repositories', '--team', team])
            if result['success'] and result.get('data'):
                repos = [''] + [r['name'] for r in result['data']]  # Empty option for no repo
                self.root.after(0, lambda: self.update_repositories(repos))
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
    def update_repositories(self, repos: list):
        """Update repository dropdown"""
        self.repo_combo['values'] = repos
        self.repo_combo.set('')  # Default to no repository
        self.status_bar.config(text="Ready")
    
    def load_sync_machines(self):
        """Load machines for sync"""
        team = self.sync_team_combo.get()
        if not team:
            return
        
        def load():
            result = self.runner.run_cli_command(['--output', 'json', 'list', 'machines', '--team', team])
            if result['success'] and result.get('data'):
                machines = [m['name'] for m in result['data']]
                self.root.after(0, lambda: self.sync_machine_combo.config(values=machines))
                if machines:
                    self.root.after(0, lambda: self.sync_machine_combo.set(machines[0]))
                    self.root.after(0, self.load_sync_repositories)
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
    def load_sync_repositories(self):
        """Load repositories for sync"""
        team = self.sync_team_combo.get()
        if not team:
            return
        
        def load():
            result = self.runner.run_cli_command(['--output', 'json', 'list', 'repositories', '--team', team])
            if result['success'] and result.get('data'):
                repos = [r['name'] for r in result['data']]
                self.root.after(0, lambda: self.sync_repo_combo.config(values=repos))
                if repos:
                    self.root.after(0, lambda: self.sync_repo_combo.set(repos[0]))
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
    def execute_terminal_command(self):
        """Execute a terminal command"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        command = self.command_entry.get().strip()
        
        if not team or not machine or not command:
            messagebox.showerror("Error", "Please select team, machine and enter a command")
            return
        
        self.terminal_output.delete(1.0, tk.END)
        self.status_bar.config(text="Executing command...")
        
        def execute():
            cmd = ['term', '--team', team, '--machine', machine, '--command', command]
            if repo:
                cmd.extend(['--repo', repo])
            
            result = self.runner.run_command(cmd)
            output = result.get('output', '') + result.get('error', '')
            self.root.after(0, lambda: self.show_terminal_output(output))
        
        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()
    
    def show_terminal_output(self, output: str):
        """Display terminal output"""
        self.terminal_output.insert(tk.END, output)
        self.terminal_output.see(tk.END)
        self.status_bar.config(text="Command executed")
    
    def open_terminal(self):
        """Open interactive terminal in new window"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not team or not machine:
            messagebox.showerror("Error", "Please select team and machine")
            return
        
        # Build command
        cmd = ['./rediacc', 'term', '--team', team, '--machine', machine]
        if repo:
            cmd.extend(['--repo', repo])
        
        # Open in new terminal window
        if sys.platform == 'darwin':  # macOS
            subprocess.Popen(['open', '-a', 'Terminal', '--', 'bash', '-c', ' '.join(cmd)])
        elif sys.platform.startswith('linux'):
            # Try common terminal emulators
            for term in ['gnome-terminal', 'konsole', 'xterm', 'x-terminal-emulator']:
                try:
                    subprocess.Popen([term, '--', 'bash', '-c', ' '.join(cmd)])
                    break
                except:
                    continue
        else:
            messagebox.showinfo("Info", f"Run this command in a terminal:\n{' '.join(cmd)}")
    
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
        team = self.sync_team_combo.get()
        machine = self.sync_machine_combo.get()
        repo = self.sync_repo_combo.get()
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
            self.token_manager.clear_token()
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
    
    # Check if already authenticated
    token_manager = TokenManager()
    
    if token_manager.get_token():
        # Already authenticated, show main window
        main_window = MainWindow(token_manager)
        # Make the main loop check for interrupts periodically
        def check_interrupt():
            main_window.root.after(100, check_interrupt)
        main_window.root.after(100, check_interrupt)
        main_window.root.mainloop()
    else:
        # Show login window
        def on_login_success(tm):
            main_window = MainWindow(tm)
            # Make the main loop check for interrupts periodically
            def check_interrupt():
                main_window.root.after(100, check_interrupt)
            main_window.root.after(100, check_interrupt)
            main_window.root.mainloop()
        
        login_window = LoginWindow(on_login_success)
        # Make the main loop check for interrupts periodically
        def check_interrupt():
            login_window.root.after(100, check_interrupt)
        login_window.root.after(100, check_interrupt)
        login_window.root.mainloop()


if __name__ == "__main__":
    launch_gui()