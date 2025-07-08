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
        self.center_window(1024, 768)
        
        # Initialize plugin tracking
        self.plugins_loaded_for = None
        
        self.create_widgets()
        
        # Load initial data
        self.load_teams()
        
        # Start auto-refresh for plugin connections
        self.auto_refresh_connections()
        
        # If Plugin Manager tab is active (index 0), load plugins
        if self.notebook.index(self.notebook.select()) == 0:
            current_selection = (self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get())
            if all(current_selection):
                self.refresh_plugins()
                self.refresh_connections()
                self.plugins_loaded_for = current_selection
    
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
        self.repo_combo.bind('<<ComboboxSelected>>', lambda e: self.on_repository_changed())
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Plugin Manager tab (first)
        self.plugin_frame = tk.Frame(self.notebook)
        self.notebook.add(self.plugin_frame, text="Plugin Manager")
        self.create_plugin_tab()
        
        # Terminal tab (second)
        self.terminal_frame = tk.Frame(self.notebook)
        self.notebook.add(self.terminal_frame, text="Terminal Access")
        self.create_terminal_tab()
        
        # File Sync tab (third)
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
        self.terminal_output.config(state='disabled')  # Make it read-only
    
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
        self.sync_output.config(state='disabled')  # Make it read-only
    
    def create_plugin_tab(self):
        """Create plugin manager interface"""
        # Main container with paned window
        paned = tk.PanedWindow(self.plugin_frame, orient=tk.VERTICAL)
        paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Top section - Plugin Management
        plugin_management_frame = tk.LabelFrame(self.plugin_frame, text="Plugin Management")
        paned.add(plugin_management_frame, minsize=300)
        
        # Create two columns inside the plugin management frame
        columns_frame = tk.Frame(plugin_management_frame)
        columns_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left column - Available plugins
        left_column = tk.Frame(columns_frame)
        left_column.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Available plugins label
        tk.Label(left_column, text="Available Plugins", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        
        # Available plugins listbox with scrollbar
        list_frame = tk.Frame(left_column)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.plugin_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=8)
        self.plugin_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.plugin_listbox.yview)
        
        # Bind selection event to update combo box
        self.plugin_listbox.bind('<<ListboxSelect>>', self.on_plugin_selected)
        
        # Refresh button
        ttk.Button(left_column, text="Refresh Plugins",
                  command=self.refresh_plugins).pack(pady=(10, 0))
        
        # Right column - Connect to plugin
        right_column = tk.Frame(columns_frame)
        right_column.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Connect to plugin label
        tk.Label(right_column, text="Connect to Plugin", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        
        # Plugin selection
        plugin_select_frame = tk.Frame(right_column)
        plugin_select_frame.pack(fill='x', pady=(10, 5))
        
        tk.Label(plugin_select_frame, text="Plugin:", width=12, anchor='w').pack(side='left')
        self.plugin_combo = ttk.Combobox(plugin_select_frame, width=20, state='readonly')
        self.plugin_combo.pack(side='left', fill='x', expand=True)
        
        # Port selection frame
        port_frame = tk.LabelFrame(right_column, text="Local Port")
        port_frame.pack(fill='x', pady=5)
        
        # Port mode variable
        self.port_mode = tk.StringVar(value='auto')
        
        # Auto port radio button
        auto_frame = tk.Frame(port_frame)
        auto_frame.pack(fill='x', padx=10, pady=5)
        ttk.Radiobutton(auto_frame, text="Auto (7111-9111)", 
                       variable=self.port_mode, value='auto',
                       command=self.on_port_mode_changed).pack(side='left')
        
        # Manual port radio button and entry
        manual_frame = tk.Frame(port_frame)
        manual_frame.pack(fill='x', padx=10, pady=5)
        ttk.Radiobutton(manual_frame, text="Manual:", 
                       variable=self.port_mode, value='manual',
                       command=self.on_port_mode_changed).pack(side='left')
        
        # Port entry with validation
        vcmd = (self.root.register(self.validate_port), '%P')
        self.port_entry = ttk.Entry(manual_frame, width=10, 
                                   validate='key', validatecommand=vcmd)
        self.port_entry.pack(side='left', padx=5)
        self.port_entry.insert(0, "7111")
        self.port_entry.config(state='disabled')  # Initially disabled
        
        # Connect button
        self.connect_button = ttk.Button(right_column, text="Connect",
                                       command=self.connect_plugin)
        self.connect_button.pack(pady=(10, 10))
        
        # Middle section - Active connections
        connections_frame = tk.LabelFrame(self.plugin_frame, text="Active Connections")
        paned.add(connections_frame, minsize=200)
        
        # Treeview for connections
        tree_frame = tk.Frame(connections_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview with columns
        columns = ('Plugin', 'URL', 'Status')
        self.connections_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', height=6)
        
        # Define column headings
        self.connections_tree.heading('#0', text='ID')
        self.connections_tree.heading('Plugin', text='Plugin')
        self.connections_tree.heading('URL', text='URL')
        self.connections_tree.heading('Status', text='Status')
        
        # Column widths
        self.connections_tree.column('#0', width=80)
        self.connections_tree.column('Plugin', width=120)
        self.connections_tree.column('URL', width=200)
        self.connections_tree.column('Status', width=80)
        
        # Scrollbar for treeview
        tree_scroll = tk.Scrollbar(tree_frame)
        tree_scroll.pack(side='right', fill='y')
        self.connections_tree.pack(side='left', fill='both', expand=True)
        tree_scroll.config(command=self.connections_tree.yview)
        self.connections_tree.config(yscrollcommand=tree_scroll.set)
        
        # Bind double-click to open URL
        self.connections_tree.bind('<Double-Button-1>', lambda e: self.open_plugin_url())
        
        # Bind Ctrl+C to copy URL
        self.connections_tree.bind('<Control-c>', lambda e: self.copy_plugin_url())
        
        # Bind selection change to update button states
        self.connections_tree.bind('<<TreeviewSelect>>', self.on_connection_selected)
        
        # Connection action buttons
        action_frame = tk.Frame(connections_frame)
        action_frame.pack(pady=5)
        
        # Create buttons with references so we can enable/disable them
        self.open_browser_button = ttk.Button(action_frame, text="Open in Browser",
                                            command=self.open_plugin_url, state='disabled')
        self.open_browser_button.pack(side='left', padx=5)
        
        self.copy_url_button = ttk.Button(action_frame, text="Copy URL",
                                         command=self.copy_plugin_url, state='disabled')
        self.copy_url_button.pack(side='left', padx=5)
        
        self.disconnect_button = ttk.Button(action_frame, text="Disconnect",
                                          command=self.disconnect_plugin, state='disabled')
        self.disconnect_button.pack(side='left', padx=5)
        
        # Refresh button is always enabled
        ttk.Button(action_frame, text="Refresh Status",
                  command=self.refresh_connections).pack(side='left', padx=5)
        
        # Info label about shortcuts
        info_label = tk.Label(connections_frame, 
                            text="Tip: Double-click to open URL • Ctrl+C to copy URL",
                            font=('Arial', 9), fg='gray')
        info_label.pack(pady=(0, 5))
    
    def on_tab_changed(self, event):
        """Handle tab change event"""
        # Get the currently selected tab
        current_tab = self.notebook.index(self.notebook.select())
        
        # If switching to Plugin Manager tab (index 0)
        if current_tab == 0:
            # Check if we need to refresh plugins
            current_selection = (self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get())
            
            # Only refresh if selection has changed or plugins never loaded
            if current_selection != self.plugins_loaded_for and all(current_selection):
                self.refresh_plugins()
                self.refresh_connections()
                self.plugins_loaded_for = current_selection
    
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
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
    
    def on_machine_changed(self):
        """Handle machine selection change"""
        self.load_repositories()
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
    
    def on_repository_changed(self):
        """Handle repository selection change"""
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
        # If on plugin tab, refresh immediately
        if self.notebook.index(self.notebook.select()) == 0:
            current_selection = (self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get())
            if all(current_selection):
                self.refresh_plugins()
                self.refresh_connections()
                self.plugins_loaded_for = current_selection
    
    def on_plugin_selected(self, event):
        """Handle plugin selection from listbox"""
        selection = event.widget.curselection()
        if selection:
            plugin_name = self.plugin_listbox.get(selection[0])
            self.plugin_combo.set(plugin_name)
    
    def on_port_mode_changed(self):
        """Handle port mode radio button change"""
        if self.port_mode.get() == 'auto':
            self.port_entry.config(state='disabled')
        else:
            self.port_entry.config(state='normal')
            self.port_entry.focus()
    
    def validate_port(self, value):
        """Validate port number input"""
        if value == "":
            return True
        try:
            port = int(value)
            # Valid port range is 1-65535
            return 1 <= port <= 65535
        except ValueError:
            return False
    
    def on_connection_selected(self, event):
        """Handle connection selection in treeview"""
        selection = self.connections_tree.selection()
        if selection:
            # Enable buttons when something is selected
            self.open_browser_button.config(state='normal')
            self.copy_url_button.config(state='normal')
            self.disconnect_button.config(state='normal')
        else:
            # Disable buttons when nothing is selected
            self.open_browser_button.config(state='disabled')
            self.copy_url_button.config(state='disabled')
            self.disconnect_button.config(state='disabled')
    
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
        
        self.terminal_output.config(state='normal')  # Enable for clearing
        self.terminal_output.delete(1.0, tk.END)
        self.terminal_output.config(state='disabled')  # Disable again
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
        self.terminal_output.config(state='normal')  # Enable for writing
        self.terminal_output.insert(tk.END, output)
        self.terminal_output.see(tk.END)
        self.terminal_output.config(state='disabled')  # Disable again
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
        self.terminal_output.config(state='normal')  # Enable for writing
        self.terminal_output.delete(1.0, tk.END)
        self.terminal_output.insert(tk.END, f"To open {description}, run this command in a terminal window:\n\n")
        self.terminal_output.insert(tk.END, simple_cmd + "\n\n")
        self.terminal_output.insert(tk.END, "Or from any directory:\n\n")
        self.terminal_output.insert(tk.END, f'cd {cli_dir} && {simple_cmd}\n\n')
        self.terminal_output.config(state='disabled')  # Disable again
        
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
                    self.terminal_output.config(state='normal')
                    self.terminal_output.insert(tk.END, f"\nLaunched in Windows Terminal...\n")
                    self.terminal_output.config(state='disabled')
                    
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
                        self.terminal_output.config(state='normal')
                        self.terminal_output.insert(tk.END, f"\nLaunched in new WSL window...\n")
                        self.terminal_output.config(state='disabled')
                    except:
                        # Last resort: use cmd.exe directly
                        try:
                            cmd_cmd = f'start cmd /c wsl bash -c "cd {cli_dir} && {simple_cmd}; read -p \'Press Enter to close...\'"'
                            subprocess.Popen(['cmd.exe', '/c', cmd_cmd], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                            self.terminal_output.config(state='normal')
                            self.terminal_output.insert(tk.END, f"\nLaunched in new window...\n")
                            self.terminal_output.config(state='disabled')
                        except:
                            self.terminal_output.config(state='normal')
                            self.terminal_output.insert(tk.END, f"\nNote: Could not launch terminal automatically in WSL.\n")
                            self.terminal_output.config(state='disabled')
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
                        self.terminal_output.config(state='normal')
                        self.terminal_output.insert(tk.END, f"\nLaunched terminal window...\n")
                        self.terminal_output.config(state='disabled')
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
        
        self.sync_output.config(state='normal')  # Enable for clearing
        self.sync_output.delete(1.0, tk.END)
        self.sync_output.config(state='disabled')  # Disable again
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
        self.sync_output.config(state='normal')  # Enable for writing
        self.sync_output.insert(tk.END, output)
        self.sync_output.see(tk.END)
        self.sync_output.config(state='disabled')  # Disable again
        self.sync_button.config(state='normal')
        self.status_bar.config(text="Sync completed")
    
    # Plugin management methods
    def refresh_plugins(self):
        """Refresh available plugins for selected repository"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not all([team, machine, repo]):
            messagebox.showerror("Error", "Please select team, machine and repository")
            return
        
        self.status_bar.config(text="Loading plugins...")
        self.plugin_listbox.delete(0, tk.END)
        self.plugin_combo['values'] = []
        
        def load():
            cmd = ['plugin', 'list', '--team', team, '--machine', machine, '--repo', repo]
            result = self.runner.run_command(cmd)
            output = result.get('output', '')
            
            # Parse plugin names from output
            plugins = []
            in_plugins_section = False
            for line in output.split('\n'):
                if 'Available plugins:' in line:
                    in_plugins_section = True
                elif in_plugins_section and '•' in line:
                    # Extract plugin name from bullet point
                    plugin_name = line.split('•')[1].split('(')[0].strip()
                    plugins.append(plugin_name)
                elif 'Plugin container status:' in line:
                    break
            
            self.root.after(0, lambda: self.update_plugin_list(plugins))
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
    def update_plugin_list(self, plugins: list):
        """Update plugin listbox and combo"""
        self.plugin_listbox.delete(0, tk.END)
        for plugin in plugins:
            self.plugin_listbox.insert(tk.END, plugin)
        
        self.plugin_combo['values'] = plugins
        if plugins:
            self.plugin_combo.set(plugins[0])
        
        self.status_bar.config(text=f"Found {len(plugins)} plugins")
    
    def refresh_connections(self):
        """Refresh active plugin connections"""
        self.status_bar.config(text="Refreshing connections...")
        
        def load():
            cmd = ['plugin', 'status']
            result = self.runner.run_command(cmd)
            output = result.get('output', '')
            
            # Parse connections from output
            connections = []
            for line in output.split('\n'):
                # Skip header lines
                if line and not any(x in line for x in ['Active Plugin Connections', '====', '----', 'ID ', 'Total connections:']):
                    parts = line.split()
                    if len(parts) >= 6:  # ID, Plugin, Repository, Machine, Port, Status
                        connections.append({
                            'id': parts[0],
                            'plugin': parts[1],
                            'repo': parts[2],
                            'machine': parts[3],
                            'port': parts[4],
                            'status': parts[5]
                        })
            
            self.root.after(0, lambda: self.update_connections_tree(connections))
        
        thread = threading.Thread(target=load)
        thread.daemon = True
        thread.start()
    
    def update_connections_tree(self, connections: list):
        """Update connections treeview"""
        # Save current selection
        selected_ids = []
        for item in self.connections_tree.selection():
            selected_ids.append(self.connections_tree.item(item)['text'])
        
        # Clear existing items
        for item in self.connections_tree.get_children():
            self.connections_tree.delete(item)
        
        # Track new items for re-selection
        new_items = {}
        
        # Add new items
        for conn in connections:
            # Filter by current selection if applicable
            team = self.team_combo.get()
            machine = self.machine_combo.get()
            repo = self.repo_combo.get()
            
            # Only show connections for current machine/repo if selected
            if machine and conn['machine'] != machine:
                continue
            if repo and conn['repo'] != repo:
                continue
            
            status_color = 'green' if conn['status'] == 'Active' else 'red'
            url = f"http://localhost:{conn['port']}"
            item = self.connections_tree.insert('', 'end', 
                                              text=conn['id'],
                                              values=(conn['plugin'], url, conn['status']),
                                              tags=(status_color,))
            new_items[conn['id']] = item
        
        # Configure tag colors
        self.connections_tree.tag_configure('green', foreground='green')
        self.connections_tree.tag_configure('red', foreground='red')
        
        # Re-select previously selected items if they still exist
        for conn_id in selected_ids:
            if conn_id in new_items:
                self.connections_tree.selection_add(new_items[conn_id])
        
        # Update button states based on selection
        self.on_connection_selected(None)
        
        self.status_bar.config(text=f"Found {len(connections)} active connections")
    
    def connect_plugin(self):
        """Connect to selected plugin"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        plugin = self.plugin_combo.get()
        
        if not all([team, machine, repo, plugin]):
            messagebox.showerror("Error", "Please select all fields")
            return
        
        self.connect_button.config(state='disabled')
        self.status_bar.config(text=f"Connecting to {plugin}...")
        
        def connect():
            cmd = ['plugin', 'connect', '--team', team, '--machine', machine, 
                   '--repo', repo, '--plugin', plugin]
            
            # Add port if manual mode
            if self.port_mode.get() == 'manual':
                port_text = self.port_entry.get().strip()
                if not port_text:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Please enter a port number"))
                    self.root.after(0, lambda: self.connect_button.config(state='normal'))
                    return
                try:
                    port = int(port_text)
                    if not (1024 <= port <= 65535):
                        self.root.after(0, lambda: messagebox.showerror("Error", "Port must be between 1024 and 65535"))
                        self.root.after(0, lambda: self.connect_button.config(state='normal'))
                        return
                    cmd.extend(['--port', str(port)])
                except ValueError:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Invalid port number"))
                    self.root.after(0, lambda: self.connect_button.config(state='normal'))
                    return
            
            result = self.runner.run_command(cmd)
            output = result.get('output', '')
            
            if result['success']:
                # Extract URL from output
                url = None
                for line in output.split('\n'):
                    if 'Local URL:' in line:
                        url = line.split('Local URL:')[1].strip()
                        break
                
                msg = f"Successfully connected to {plugin}"
                if url:
                    msg += f"\n\nAccess at: {url}"
                
                self.root.after(0, lambda: messagebox.showinfo("Success", msg))
                self.root.after(0, self.refresh_connections)
            else:
                error = result.get('error', 'Connection failed')
                self.root.after(0, lambda: messagebox.showerror("Error", error))
            
            self.root.after(0, lambda: self.connect_button.config(state='normal'))
            self.root.after(0, lambda: self.status_bar.config(text="Ready"))
        
        thread = threading.Thread(target=connect)
        thread.daemon = True
        thread.start()
    
    def disconnect_plugin(self):
        """Disconnect selected plugin connection"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a connection to disconnect")
            return
        
        item = self.connections_tree.item(selection[0])
        conn_id = item['text']
        plugin_name = item['values'][0]
        
        if messagebox.askyesno("Confirm", f"Disconnect {plugin_name}?"):
            self.status_bar.config(text=f"Disconnecting {plugin_name}...")
            
            def disconnect():
                cmd = ['plugin', 'disconnect', '--connection-id', conn_id]
                result = self.runner.run_command(cmd)
                
                if result['success']:
                    self.root.after(0, lambda: messagebox.showinfo("Success", f"Disconnected {plugin_name}"))
                else:
                    error = result.get('error', 'Disconnect failed')
                    self.root.after(0, lambda: messagebox.showerror("Error", error))
                
                self.root.after(0, self.refresh_connections)
                self.root.after(0, lambda: self.status_bar.config(text="Ready"))
            
            thread = threading.Thread(target=disconnect)
            thread.daemon = True
            thread.start()
    
    def open_plugin_url(self):
        """Open plugin URL in browser"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a connection to open")
            return
        
        item = self.connections_tree.item(selection[0])
        url = item['values'][1]  # URL is second column
        
        # Open URL in default browser
        import webbrowser
        webbrowser.open(url)
        
        self.status_bar.config(text=f"Opened {url} in browser")
    
    def copy_plugin_url(self):
        """Copy plugin URL to clipboard"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a connection to copy URL")
            return
        
        item = self.connections_tree.item(selection[0])
        url = item['values'][1]  # URL is second column
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.root.update()  # Required on Windows
        
        # Show confirmation in status bar
        self.status_bar.config(text=f"Copied {url} to clipboard", fg='green')
        
        # Reset status bar color after 2 seconds
        self.root.after(2000, lambda: self.status_bar.config(fg='black'))
    
    def auto_refresh_connections(self):
        """Auto-refresh connections every 5 seconds"""
        # Only refresh if plugin tab is active
        if self.notebook.index(self.notebook.select()) == 0:  # Plugin tab is index 0
            self.refresh_connections()
        
        # Schedule next refresh
        self.root.after(5000, self.auto_refresh_connections)
    
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