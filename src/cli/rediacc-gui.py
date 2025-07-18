#!/usr/bin/env python3
"""
Rediacc GUI - Main Application

This module provides the main window class and application entry point for the
Rediacc CLI GUI application, including plugin management, terminal access,
and file synchronization tools.
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
from typing import Callable, Optional, Dict, Any, List, Tuple
import time

# Import from consolidated core module
from core import (
    TokenManager,
    SubprocessRunner,
    i18n,
    TerminalDetector,
    get_logger
)

# Import core functionality for SSH operations
from rediacc_cli_core import (
    RepositoryConnection,
    colorize,
    setup_ssh_for_connection,
    is_windows
)

# Import GUI components
from gui_base import BaseWindow
from gui_login import LoginWindow
from gui_file_browser import DualPaneFileBrowser
from gui_utilities import (
    check_token_validity,
    MAIN_WINDOW_DEFAULT_SIZE, COMBO_WIDTH_SMALL, COMBO_WIDTH_MEDIUM,
    COLUMN_WIDTH_NAME, COLUMN_WIDTH_SIZE, COLUMN_WIDTH_MODIFIED, COLUMN_WIDTH_TYPE,
    COLUMN_WIDTH_PLUGIN, COLUMN_WIDTH_URL, COLUMN_WIDTH_STATUS,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_INFO, AUTO_REFRESH_INTERVAL
)


class MainWindow(BaseWindow):
    """Main window with Terminal and File Sync tools"""
    
    def __init__(self):
        super().__init__(tk.Tk(), i18n.get('app_title'))
        self.logger = get_logger(__name__)
        self.runner = SubprocessRunner()
        # Start maximized
        self._maximize_window()
        
        # Initialize plugin tracking
        self.plugins_loaded_for = None
        
        # Initialize machine data storage
        self.machines_data = {}
        
        # Initialize terminal detector
        self.terminal_detector = TerminalDetector()
        
        # Register for language changes
        i18n.register_observer(self.update_all_texts)
        
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
    
    def _maximize_window(self):
        """Maximize window using platform-specific methods"""
        self.root.update_idletasks()
        try:
            if is_windows():
                self.root.state('zoomed')
            else:
                # For Linux/Mac, try different methods
                try:
                    self.root.attributes('-zoomed', True)
                except tk.TclError:
                    # Fallback: maximize using screen dimensions
                    width = self.root.winfo_screenwidth()
                    height = self.root.winfo_screenheight()
                    self.root.geometry(f'{width}x{height}+0+0')
        except Exception as e:
            self.logger.warning(f"Could not maximize window: {e}")
            self.center_window(MAIN_WINDOW_DEFAULT_SIZE[0], MAIN_WINDOW_DEFAULT_SIZE[1])
    
    def _get_name(self, item, *fields):
        """Get name from item trying multiple field names"""
        return next((item[field] for field in fields if field in item), '')
    
    def _handle_api_error(self, error_msg):
        """Handle API errors, especially authentication errors"""
        auth_errors = ['401', 'Not authenticated', 'Invalid request credential']
        if any(error in str(error_msg) for error in auth_errors):
            self.status_bar.config(text=i18n.get('authentication_expired'), fg=COLOR_ERROR)
            messagebox.showerror(i18n.get('error'), i18n.get('session_expired'))
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
        user_text = f"{i18n.get('user')} {auth_info.get('email', 'Unknown')}"
        self.user_label = tk.Label(top_frame, text=user_text)
        self.user_label.pack(side='left', padx=10)
        
        # Logout button
        self.logout_button = ttk.Button(top_frame, text=i18n.get('logout'), command=self.logout)
        self.logout_button.pack(side='right', padx=10)
        
        # Language selector
        self.lang_combo = ttk.Combobox(top_frame, state='readonly', width=COMBO_WIDTH_SMALL)
        self.lang_combo['values'] = [i18n.get_language_name(code) for code in i18n.get_language_codes()]
        self.lang_combo.set(i18n.get_language_name(i18n.current_language))
        self.lang_combo.pack(side='right', padx=5)
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        self.lang_label = tk.Label(top_frame, text=i18n.get('language') + ':')
        self.lang_label.pack(side='right')
        
        # Common selection frame
        self.common_frame = tk.LabelFrame(self.root, text=i18n.get('resource_selection'))
        self.common_frame.pack(fill='x', padx=10, pady=5)
        
        # Configure grid columns for common_frame
        self.common_frame.grid_columnconfigure(0, minsize=120)  # Label column with minimum width
        self.common_frame.grid_columnconfigure(1, weight=1)     # Combobox column expands
        self.common_frame.grid_columnconfigure(2, minsize=100)  # Filter indicator column
        
        # Team selection
        self.team_label = tk.Label(self.common_frame, text=i18n.get('team'), anchor='e')
        self.team_label.grid(row=0, column=0, sticky='e', padx=(20, 10), pady=(8, 8))
        self.team_combo = ttk.Combobox(self.common_frame, state='readonly')
        self.team_combo.grid(row=0, column=1, sticky='ew', padx=(0, 10), pady=(8, 8))
        self.team_combo.bind('<<ComboboxSelected>>', lambda e: self.on_team_changed())
        
        # Machine selection
        self.machine_label = tk.Label(self.common_frame, text=i18n.get('machine'), anchor='e')
        self.machine_label.grid(row=1, column=0, sticky='e', padx=(20, 10), pady=(8, 8))
        self.machine_combo = ttk.Combobox(self.common_frame, state='readonly')
        self.machine_combo.grid(row=1, column=1, sticky='ew', padx=(0, 10), pady=(8, 8))
        self.machine_combo.bind('<<ComboboxSelected>>', lambda e: self.on_machine_changed())
        
        # Repository selection
        self.repo_label = tk.Label(self.common_frame, text=i18n.get('repository'), anchor='e')
        self.repo_label.grid(row=2, column=0, sticky='e', padx=(20, 10), pady=(8, 8))
        self.repo_combo = ttk.Combobox(self.common_frame, state='readonly')
        self.repo_combo.grid(row=2, column=1, sticky='ew', padx=(0, 10), pady=(8, 8))
        self.repo_combo.bind('<<ComboboxSelected>>', lambda e: self.on_repository_changed())
        # Add a filter indicator label
        self.repo_filter_label = tk.Label(self.common_frame, text="", font=('Arial', 9), fg='gray')
        self.repo_filter_label.grid(row=2, column=2, sticky='w', padx=(0, 10), pady=(8, 8))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Plugin Manager tab (first)
        self.plugin_frame = tk.Frame(self.notebook)
        self.notebook.add(self.plugin_frame, text=i18n.get('plugin_manager'))
        self.create_plugin_tab()
        
        # Terminal tab (second)
        self.terminal_frame = tk.Frame(self.notebook)
        self.notebook.add(self.terminal_frame, text=i18n.get('terminal_access'))
        self.create_terminal_tab()
        
        # File Sync tab (third)
        self.sync_frame = tk.Frame(self.notebook)
        self.notebook.add(self.sync_frame, text=i18n.get('file_sync'))
        self.create_sync_tab()
        
        # File Browser tab (fourth)
        self.browser_frame = tk.Frame(self.notebook)
        self.notebook.add(self.browser_frame, text=i18n.get('file_browser', 'File Browser'))
        self.create_file_browser_tab()
        
        # Status bar with frame wrapper
        status_frame = tk.Frame(self.root, relief='sunken', bd=1)
        status_frame.pack(side='bottom', fill='x')
        self.status_bar = tk.Label(status_frame, text=i18n.get('ready'),
                                 bd=0, anchor='w')
        self.status_bar.pack(side='left', fill='x', expand=True, padx=(10,5), pady=(2,2))
    
    def create_terminal_tab(self):
        """Create terminal access interface"""
        # Control frame
        control_frame = tk.Frame(self.terminal_frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Command input - using grid layout
        command_frame = tk.Frame(control_frame)
        command_frame.pack(fill='x', pady=5)
        command_frame.grid_columnconfigure(0, minsize=100)
        command_frame.grid_columnconfigure(1, weight=1)
        
        self.terminal_command_label = tk.Label(command_frame, text=i18n.get('command'), anchor='e')
        self.terminal_command_label.grid(row=0, column=0, sticky='e', padx=(0, 5))
        self.command_entry = ttk.Entry(command_frame)
        self.command_entry.grid(row=0, column=1, sticky='ew', padx=(0, 5))
        
        # Buttons with separator
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=10)
        
        # Execute button
        self.execute_cmd_button = ttk.Button(button_frame, text=i18n.get('execute_command'),
                  command=self.execute_terminal_command)
        self.execute_cmd_button.pack(side='left', padx=(0, 15))
        
        # Separator
        separator = tk.Frame(button_frame, bg='#cccccc', width=2)
        separator.pack(side='left', fill='y', padx=(0, 15))
        
        # Terminal buttons
        self.open_repo_term_button = ttk.Button(button_frame, text=i18n.get('open_repo_terminal'),
                  command=self.open_repo_terminal)
        self.open_repo_term_button.pack(side='left', padx=(0, 15))
        self.open_machine_term_button = ttk.Button(button_frame, text=i18n.get('open_machine_terminal'),
                  command=self.open_machine_terminal)
        self.open_machine_term_button.pack(side='left')
        
        # Output area
        output_frame = tk.Frame(self.terminal_frame)
        output_frame.pack(fill='both', expand=True)
        
        self.terminal_output_label = tk.Label(output_frame, text=i18n.get('output'))
        self.terminal_output_label.pack(anchor='w')
        
        self.terminal_output = scrolledtext.ScrolledText(output_frame, height=15,
                                                       font=('Consolas', 10), wrap='none')
        self.terminal_output.pack(fill='both', expand=True)
        self.terminal_output.config(state='disabled')  # Make it read-only
    
    def create_sync_tab(self):
        """Create file sync interface"""
        # Control frame
        control_frame = tk.Frame(self.sync_frame)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        # Sync direction
        direction_frame = tk.Frame(control_frame)
        direction_frame.pack(fill='x', pady=5)
        self.sync_direction_label = tk.Label(direction_frame, text=i18n.get('direction'), width=12, anchor='w')
        self.sync_direction_label.pack(side='left', padx=5)
        self.sync_direction = tk.StringVar(value='upload')
        self.upload_radio = ttk.Radiobutton(direction_frame, text=i18n.get('upload'), variable=self.sync_direction,
                       value='upload')
        self.upload_radio.pack(side='left', padx=(0, 30))
        self.download_radio = ttk.Radiobutton(direction_frame, text=i18n.get('download'), variable=self.sync_direction,
                       value='download')
        self.download_radio.pack(side='left', padx=(0, 30))
        
        # Local path
        path_frame = tk.Frame(control_frame)
        path_frame.pack(fill='x', pady=5)
        self.local_path_label = tk.Label(path_frame, text=i18n.get('local_path'), width=12, anchor='w')
        self.local_path_label.pack(side='left', padx=5)
        self.local_path_entry = ttk.Entry(path_frame)
        self.local_path_entry.pack(side='left', padx=5, fill='x', expand=True)
        self.browse_button = ttk.Button(path_frame, text=i18n.get('browse'),
                  command=self.browse_local_path)
        self.browse_button.pack(side='left', padx=5)
        
        # Options
        self.options_frame = tk.LabelFrame(control_frame, text=i18n.get('options'))
        self.options_frame.pack(fill='x', pady=10)
        
        # Sync options sub-frame
        sync_options_frame = tk.LabelFrame(self.options_frame, text="Sync Options")
        sync_options_frame.pack(fill='x', padx=10, pady=5)
        
        # Use grid for sync options
        self.mirror_var = tk.BooleanVar()
        self.mirror_check = tk.Checkbutton(sync_options_frame, text=i18n.get('mirror_delete'),
                      variable=self.mirror_var,
                      command=self.on_mirror_changed)
        self.mirror_check.grid(row=0, column=0, padx=(20, 40), pady=5, sticky='w')
        
        self.verify_var = tk.BooleanVar()
        self.verify_check = tk.Checkbutton(sync_options_frame, text=i18n.get('verify_transfer'),
                      variable=self.verify_var)
        self.verify_check.grid(row=0, column=1, padx=(20, 40), pady=5, sticky='w')
        
        # Safety options sub-frame
        safety_options_frame = tk.LabelFrame(self.options_frame, text="Safety Options")
        safety_options_frame.pack(fill='x', padx=10, pady=5)
        
        self.confirm_var = tk.BooleanVar()
        self.confirm_check = tk.Checkbutton(safety_options_frame, text=i18n.get('preview_changes'),
                      variable=self.confirm_var)
        self.confirm_check.grid(row=0, column=0, padx=(20, 40), pady=5, sticky='w')
        
        # Sync button
        self.sync_button = ttk.Button(control_frame, text=i18n.get('start_sync'),
                                    command=self.start_sync, width=25)
        self.sync_button.pack(pady=(20, 10))
        
        # Output area
        output_frame = tk.Frame(self.sync_frame)
        output_frame.pack(fill='both', expand=True)
        
        self.sync_output_label = tk.Label(output_frame, text=i18n.get('output'))
        self.sync_output_label.pack(anchor='w')
        
        self.sync_output = scrolledtext.ScrolledText(output_frame, height=15,
                                                    font=('Consolas', 10), wrap='none')
        self.sync_output.pack(fill='both', expand=True)
        self.sync_output.config(state='disabled')  # Make it read-only
    
    def create_plugin_tab(self):
        """Create plugin manager interface"""
        # Main container with paned window
        paned = tk.PanedWindow(self.plugin_frame, orient=tk.VERTICAL)
        paned.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Top section - Plugin Management
        self.plugin_management_frame = tk.LabelFrame(self.plugin_frame, text=i18n.get('plugin_management'))
        paned.add(self.plugin_management_frame, minsize=300)
        
        # Create two columns inside the plugin management frame using grid
        columns_frame = tk.Frame(self.plugin_management_frame)
        columns_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
        # Configure the plugin management frame to expand the columns frame
        self.plugin_management_frame.grid_rowconfigure(0, weight=1)
        self.plugin_management_frame.grid_columnconfigure(0, weight=1)
        
        # Configure columns frame weights: 0.45, 0.1, 0.45
        columns_frame.grid_columnconfigure(0, weight=45)  # Left column
        columns_frame.grid_columnconfigure(1, weight=10)  # Spacer
        columns_frame.grid_columnconfigure(2, weight=45)  # Right column
        columns_frame.grid_rowconfigure(0, weight=1)
        
        # Left column - Available plugins
        left_column = tk.Frame(columns_frame)
        left_column.grid(row=0, column=0, sticky='nsew')
        
        # Configure left column to expand
        left_column.grid_rowconfigure(1, weight=1)
        left_column.grid_columnconfigure(0, weight=1)
        
        # Available plugins label
        self.available_plugins_label = tk.Label(left_column, text=i18n.get('available_plugins'), font=('Arial', 10, 'bold'))
        self.available_plugins_label.grid(row=0, column=0, sticky='w', pady=(0, 5))
        
        # Available plugins listbox with scrollbar
        list_frame = tk.Frame(left_column)
        list_frame.grid(row=1, column=0, sticky='nsew')
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        self.plugin_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.plugin_listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar.config(command=self.plugin_listbox.yview)
        
        # Bind selection event to update combo box
        self.plugin_listbox.bind('<<ListboxSelect>>', self.on_plugin_selected)
        
        # Refresh button
        self.refresh_plugins_button = ttk.Button(left_column, text=i18n.get('refresh_plugins'),
                  command=self.refresh_plugins)
        self.refresh_plugins_button.grid(row=2, column=0, pady=(10, 0))
        
        # Spacer column
        spacer = tk.Frame(columns_frame, width=20)
        spacer.grid(row=0, column=1, sticky='ns')
        
        # Right column - Connect to plugin
        right_column = tk.Frame(columns_frame)
        right_column.grid(row=0, column=2, sticky='nsew')
        
        # Configure right column
        right_column.grid_columnconfigure(0, weight=1)
        
        # Connect to plugin label
        self.connect_plugin_label = tk.Label(right_column, text=i18n.get('connect_to_plugin'), font=('Arial', 10, 'bold'))
        self.connect_plugin_label.grid(row=0, column=0, sticky='w', pady=(0, 5))
        
        # Plugin selection
        plugin_select_frame = tk.Frame(right_column)
        plugin_select_frame.grid(row=1, column=0, sticky='ew', pady=(10, 5))
        plugin_select_frame.grid_columnconfigure(1, weight=1)
        
        self.plugin_select_label = tk.Label(plugin_select_frame, text=i18n.get('plugin'), width=12, anchor='w')
        self.plugin_select_label.grid(row=0, column=0, sticky='w')
        self.plugin_combo = ttk.Combobox(plugin_select_frame, width=COMBO_WIDTH_MEDIUM, state='readonly')
        self.plugin_combo.grid(row=0, column=1, sticky='ew', padx=(5, 0))
        
        # Port selection frame
        self.port_frame = tk.LabelFrame(right_column, text=i18n.get('local_port'))
        self.port_frame.grid(row=2, column=0, sticky='ew', pady=5)
        
        # Configure port frame interior grid
        self.port_frame.grid_columnconfigure(0, weight=1)
        self.port_frame.grid_columnconfigure(1, weight=1)
        
        # Port mode variable
        self.port_mode = tk.StringVar(value='auto')
        
        # Auto port radio button (spans both columns)
        self.auto_port_radio = ttk.Radiobutton(self.port_frame, text=i18n.get('auto_port'), 
                       variable=self.port_mode, value='auto',
                       command=self.on_port_mode_changed)
        self.auto_port_radio.grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=(5, 0))
        
        # Manual port radio button
        self.manual_port_radio = ttk.Radiobutton(self.port_frame, text=i18n.get('manual_port'), 
                       variable=self.port_mode, value='manual',
                       command=self.on_port_mode_changed)
        self.manual_port_radio.grid(row=1, column=0, sticky='w', padx=10, pady=(0, 5))
        
        # Port entry with validation
        vcmd = (self.root.register(self.validate_port), '%P')
        self.port_entry = ttk.Entry(self.port_frame, width=10, 
                                   validate='key', validatecommand=vcmd)
        self.port_entry.grid(row=1, column=1, sticky='w', padx=(5, 10), pady=(0, 5))
        self.port_entry.insert(0, "7111")
        self.port_entry.config(state='disabled')  # Initially disabled
        
        # Connect button
        self.connect_button = ttk.Button(right_column, text=i18n.get('connect'),
                                       command=self.connect_plugin, width=20)
        self.connect_button.grid(row=3, column=0, pady=(20, 10))
        
        # Middle section - Active connections
        self.connections_frame = tk.LabelFrame(self.plugin_frame, text=i18n.get('active_connections'))
        paned.add(self.connections_frame, minsize=200)
        
        # Treeview for connections
        tree_frame = tk.Frame(self.connections_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview with columns
        columns = ('Plugin', 'URL', 'Status')
        # Style for treeview
        style = ttk.Style()
        style.configure('Treeview', padding=(2,2,2,2))
        
        self.connections_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', height=6)
        
        # Configure alternating row colors
        self.connections_tree.tag_configure('odd', background='#f5f5f5')
        self.connections_tree.tag_configure('even', background='white')
        
        # Define column headings
        self.connections_tree.heading('#0', text='ID')
        self.connections_tree.heading('Plugin', text='Plugin')
        self.connections_tree.heading('URL', text='URL')
        self.connections_tree.heading('Status', text='Status')
        
        # Column widths
        self.connections_tree.column('#0', width=COLUMN_WIDTH_SIZE)
        self.connections_tree.column('Plugin', width=COLUMN_WIDTH_PLUGIN)
        self.connections_tree.column('URL', width=COLUMN_WIDTH_URL)
        self.connections_tree.column('Status', width=COLUMN_WIDTH_STATUS)
        
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
        action_frame = tk.Frame(self.connections_frame)
        action_frame.pack(pady=5)
        
        # Create buttons with references so we can enable/disable them
        self.open_browser_button = ttk.Button(action_frame, text=i18n.get('open_in_browser'),
                                            command=self.open_plugin_url, state='disabled')
        self.open_browser_button.pack(side='left', padx=5)
        
        self.copy_url_button = ttk.Button(action_frame, text=i18n.get('copy_url'),
                                         command=self.copy_plugin_url, state='disabled')
        self.copy_url_button.pack(side='left', padx=5)
        
        self.disconnect_button = ttk.Button(action_frame, text=i18n.get('disconnect'),
                                          command=self.disconnect_plugin, state='disabled')
        self.disconnect_button.pack(side='left', padx=5)
        
        # Refresh button is always enabled
        self.refresh_status_button = ttk.Button(action_frame, text=i18n.get('refresh_status'),
                  command=self.refresh_connections)
        self.refresh_status_button.pack(side='left', padx=5)
        
        # Info label about shortcuts
        self.plugin_info_label = tk.Label(self.connections_frame, 
                            text=i18n.get('plugin_tip'),
                            font=('Arial', 9), fg='gray')
        self.plugin_info_label.pack(pady=(0, 5))
    
    def create_file_browser_tab(self):
        """Create dual-pane file browser interface"""
        # Create instance of DualPaneFileBrowser
        self.file_browser = DualPaneFileBrowser(self.browser_frame, self)
    
    def on_tab_changed(self, event):
        """Handle tab change event"""
        # Get the currently selected tab
        current_tab = self.notebook.index(self.notebook.select())
        
        # If switching to File Browser tab (index 3), auto-connect
        if current_tab == 3 and hasattr(self, 'file_browser'):
            if self.file_browser.ssh_connection is None:
                # Only connect if we have team, machine, and repo selected
                if all([self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get()]):
                    self.file_browser.connect_remote()
        
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
        self.status_bar.config(text=i18n.get('loading_teams'))
        self.root.update()
        
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'teams'])
        if result['success'] and result.get('data'):
            teams = [self._get_name(team, 'teamName', 'name') for team in result['data']]
            self.update_teams(teams)
        else:
            error_msg = result.get('error', i18n.get('failed_to_load_teams'))
            if not self._handle_api_error(error_msg):
                self.status_bar.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
    
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
        # Always refresh plugins when repository changes (not just when on plugin tab)
        current_selection = (self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get())
        if all(current_selection):
            self.refresh_plugins()
            # Only refresh connections if on plugin tab to avoid unnecessary API calls
            if self.notebook.index(self.notebook.select()) == 0:
                self.refresh_connections()
            self.plugins_loaded_for = current_selection
    
    def update_teams(self, teams: list):
        """Update team dropdowns"""
        self.team_combo['values'] = teams
        if teams:
            self.team_combo.set(teams[0])
            self.on_team_changed()
        self.status_bar.config(text=i18n.get('ready'))
    
    def load_machines(self):
        """Load machines for selected team"""
        team = self.team_combo.get()
        if not team:
            return
        
        self.status_bar.config(text=i18n.get('loading_machines', team=team))
        self.root.update()
        
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'team-machines', team])
        if result['success'] and result.get('data'):
            # Store full machine data with vault content
            self.machines_data = {m.get('machineName', ''): m for m in result['data'] if m.get('machineName')}
            machines = [self._get_name(m, 'machineName', 'name') for m in result['data']]
            self.update_machines(machines)
        else:
            # Clear machine data on error
            self.machines_data = {}
            error_msg = result.get('error', i18n.get('failed_to_load_machines'))
            if not self._handle_api_error(error_msg):
                self.status_bar.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
    
    def update_machines(self, machines: list):
        """Update machine dropdown"""
        self.machine_combo['values'] = machines
        if machines:
            self.machine_combo.set(machines[0])
            self.load_repositories()
        else:
            # Clear the combo box if no machines are available
            self.machine_combo.set('')
            # Also clear repositories since no machine is selected
            self.update_repositories([])
        self.status_bar.config(text=i18n.get('ready'))
    
    def load_repositories(self):
        """Load repositories for selected team/machine"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        if not team:
            return
        
        self.status_bar.config(text=i18n.get('loading_repositories', team=team))
        self.root.update()
        
        # Get all team repositories
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'team-repositories', team])
        if result['success'] and result.get('data'):
            all_repos = result['data']
            
            # Try to filter by machine if we have vaultStatus data
            if machine and machine in self.machines_data:
                machine_data = self.machines_data[machine]
                self.logger.debug(f"Machine data keys for {machine}: {sorted(machine_data.keys())}")
                self.logger.debug(f"vaultStatus present: {'vaultStatus' in machine_data}")
                if machine_data.get('vaultStatus'):
                    try:
                        # Parse the nested JSON structure
                        vault_status = json.loads(machine_data['vaultStatus'])
                        if vault_status.get('status') == 'completed' and vault_status.get('result'):
                            result_data = json.loads(vault_status['result'])
                            if result_data.get('repositories'):
                                # Get repository GUIDs from vaultStatus
                                machine_repo_guids = [repo.get('name', '') for repo in result_data['repositories']]
                                
                                # Filter repositories to only those on this machine
                                filtered_repos = []
                                for repo in all_repos:
                                    if repo.get('repoGuid') in machine_repo_guids:
                                        filtered_repos.append(repo)
                                
                                # Use filtered list
                                repos = [self._get_name(r, 'repositoryName', 'name', 'repoName') for r in filtered_repos]
                                self.update_repositories(repos)
                                # Update status to show filtering is active
                                self.repo_filter_label.config(text="(machine-specific)", fg=COLOR_SUCCESS)
                                status_text = f"Showing {len(repos)} repositories for machine '{machine}'"
                                self.status_bar.config(text=status_text, fg=COLOR_SUCCESS)
                                self.root.after(3000, lambda: self.status_bar.config(text=i18n.get('ready'), fg='black'))
                                return
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        # If parsing fails, fall back to showing all repos
                        self.logger.error(f"Failed to parse vaultStatus for machine {machine}: {e}")
            
            # Fall back to showing all team repositories
            repos = [self._get_name(r, 'repositoryName', 'name', 'repoName') for r in all_repos]
            self.repo_filter_label.config(text="(all team repos)", fg='#666666')
            self.update_repositories(repos)
        else:
            error_msg = result.get('error', i18n.get('failed_to_load_repositories'))
            if not self._handle_api_error(error_msg):
                self.status_bar.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
    
    def update_repositories(self, repos: list):
        """Update repository dropdown"""
        self.repo_combo['values'] = repos
        if repos:
            self.repo_combo.set(repos[0])
            # Trigger repository change event to load plugins
            self.on_repository_changed()
        else:
            # Clear the combo box if no repositories are available
            self.repo_combo.set('')
            # Clear the filter label when no repos
            self.repo_filter_label.config(text="")
            # Also trigger change event to clear plugins
            self.on_repository_changed()
        self.status_bar.config(text=i18n.get('ready'))
    
    def execute_terminal_command(self):
        """Execute a terminal command"""
        team, machine, repo = self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get()
        command = self.command_entry.get().strip()
        
        if not all([team, machine, repo, command]):
            messagebox.showerror(i18n.get('error'), i18n.get('select_all_fields'))
            return
        
        self.terminal_output.config(state='normal')
        self.terminal_output.delete(1.0, tk.END)
        self.terminal_output.config(state='disabled')
        self.status_bar.config(text=i18n.get('executing_command'))
        
        def execute():
            cmd = ['term', '--team', team, '--machine', machine, '--repo', repo, '--command', command]
            result = self.runner.run_command(cmd)
            output = result.get('output', '') + result.get('error', '')
            
            auth_errors = ['401', 'Not authenticated', 'Invalid request credential']
            if any(error in output for error in auth_errors):
                self.root.after(0, lambda: self._handle_api_error(output))
            else:
                self.root.after(0, lambda: self.show_terminal_output(output))
        
        thread = threading.Thread(target=execute, daemon=True)
        thread.start()
    
    def show_terminal_output(self, output: str):
        """Display terminal output"""
        self.terminal_output.config(state='normal')
        self.terminal_output.insert(tk.END, output)
        self.terminal_output.see(tk.END)
        self.terminal_output.config(state='disabled')
        self.status_bar.config(text=i18n.get('command_executed'))
    
    def _launch_terminal(self, command: str, description: str):
        """Common method to launch terminal with given command"""
        import os
        cli_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rediacc_path = os.path.join(cli_dir, 'rediacc')
        simple_cmd = f'{rediacc_path} {command}'
        
        # Show command in output area
        self.terminal_output.config(state='normal')
        self.terminal_output.delete(1.0, tk.END)
        lines = [
            i18n.get('terminal_instructions', description=description) + "\n\n",
            simple_cmd + "\n\n",
            i18n.get('or_from_any_directory') + "\n\n",
            f'cd {cli_dir} && {simple_cmd}\n\n'
        ]
        self.terminal_output.insert(tk.END, ''.join(lines))
        self.terminal_output.config(state='disabled')
        
        # Use terminal detector to find best method
        method = self.terminal_detector.detect()
        
        def update_output(text):
            self.terminal_output.config(state='normal')
            self.terminal_output.insert(tk.END, text)
            self.terminal_output.config(state='disabled')
        
        if not method:
            self.logger.error("No working terminal method detected")
            update_output(f"\n{i18n.get('could_not_launch')} - No terminal method available\n")
            return
        
        launch_func = self.terminal_detector.get_launch_function(method)
        if not launch_func:
            self.logger.warning(f"No launch function for method: {method}")
            update_output(f"\n{i18n.get('could_not_launch')}\n")
            return
        
        try:
            launch_func(cli_dir, command, description)
            update_output(f"\n{i18n.get('launched_terminal')} ({method})\n")
        except Exception as e:
            self.logger.error(f"Failed to launch with {method}: {e}")
            update_output(f"\n{i18n.get('could_not_launch')}\n")
    
    def open_repo_terminal(self):
        """Open interactive repository terminal in new window"""
        team, machine, repo = self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get()
        
        if not all([team, machine, repo]):
            messagebox.showerror(i18n.get('error'), i18n.get('select_team_machine_repo'))
            return
        
        command = f'term --team "{team}" --machine "{machine}" --repo "{repo}"'
        self._launch_terminal(command, i18n.get('an_interactive_repo_terminal'))
    
    def open_machine_terminal(self):
        """Open interactive machine terminal in new window (without repository)"""
        team, machine = self.team_combo.get(), self.machine_combo.get()
        
        if not (team and machine):
            messagebox.showerror(i18n.get('error'), i18n.get('select_team_machine'))
            return
        
        command = f'term --team "{team}" --machine "{machine}"'
        self._launch_terminal(command, i18n.get('an_interactive_machine_terminal'))
    
    def on_mirror_changed(self):
        """Handle mirror checkbox change"""
        if self.mirror_var.get():
            # When mirror is enabled, force confirm on and disable the checkbox
            self.confirm_var.set(True)
            self.confirm_check.config(state='disabled')
        else:
            # When mirror is disabled, re-enable the confirm checkbox
            self.confirm_check.config(state='normal')
    
    def browse_local_path(self):
        """Browse for local directory"""
        path = filedialog.askdirectory()
        if path:
            self.local_path_entry.delete(0, tk.END)
            self.local_path_entry.insert(0, path)
    
    def start_sync(self):
        """Start file synchronization"""
        direction = self.sync_direction.get()
        team, machine, repo = self.team_combo.get(), self.machine_combo.get(), self.repo_combo.get()
        local_path = self.local_path_entry.get().strip()
        
        if not all([team, machine, repo, local_path]):
            messagebox.showerror(i18n.get('error'), i18n.get('fill_all_fields'))
            return
        
        self.show_sync_progress(direction, team, machine, repo, local_path)
    
    def show_sync_progress(self, direction: str, team: str, machine: str, repo: str, local_path: str):
        """Show sync progress dialog"""
        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(i18n.get('sync_progress', 'Sync Progress'))
        # Use 0.4 * screen dimensions for progress dialog
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        dialog_width = int(screen_width * 0.4)
        dialog_height = int(screen_height * 0.4)
        
        progress_dialog.transient(self.root)
        
        # Center the dialog
        progress_dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        progress_dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
        
        # Set minimum size
        progress_dialog.minsize(500, 400)
        
        # Make dialog resizable
        progress_dialog.resizable(True, True)
        
        # Prevent closing during sync
        progress_dialog.protocol('WM_DELETE_WINDOW', lambda: None)
        
        # Main container
        main_container = tk.Frame(progress_dialog)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Status label
        status_text = i18n.get('preparing_sync', f'Preparing {direction}...')
        if self.confirm_var.get():
            status_text = i18n.get('preview_mode', 'PREVIEW MODE - ') + status_text
        status_label = tk.Label(main_container, text=status_text,
                               font=('Arial', 10), fg=COLOR_INFO if self.confirm_var.get() else 'black')
        status_label.pack(pady=(0, 10))
        
        # Sync details frame
        details_frame = tk.LabelFrame(main_container, text=i18n.get('sync_details', 'Sync Details'))
        details_frame.pack(fill='x', pady=(0, 10))
        
        details_text = f"{i18n.get('direction', 'Direction')}: {i18n.get(direction, direction)}\n"
        details_text += f"{i18n.get('team', 'Team')}: {team}\n"
        details_text += f"{i18n.get('machine', 'Machine')}: {machine}\n"
        details_text += f"{i18n.get('repository', 'Repository')}: {repo}\n"
        details_text += f"{i18n.get('local_path', 'Local Path')}: {local_path}\n"
        details_text += f"\n{i18n.get('options', 'Options')}:\n"
        if self.mirror_var.get():
            details_text += f"  • {i18n.get('mirror_delete', 'Mirror mode')}\n"
        if self.verify_var.get():
            details_text += f"  • {i18n.get('verify_transfer', 'Verify mode')}\n"
        if self.confirm_var.get():
            details_text += f"  • {i18n.get('preview_changes', 'Preview mode')}\n"
        
        details_label = tk.Label(details_frame, text=details_text, justify='left', 
                               font=('Arial', 9))
        details_label.pack(padx=10, pady=10)
        
        # Progress frame
        progress_frame = tk.LabelFrame(main_container, text=i18n.get('progress', 'Progress'))
        progress_frame.pack(fill='x', pady=(0, 10))
        
        # Progress bar (indeterminate since rsync doesn't give percentage for whole sync)
        progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        progress_bar.pack(fill='x', padx=10, pady=10)
        progress_bar.start(10)  # Start animation
        
        current_file_label = tk.Label(progress_frame, text='', font=('Arial', 9))
        current_file_label.pack(pady=(0, 10))
        
        # Output frame
        output_frame = tk.LabelFrame(main_container, text=i18n.get('output', 'Output'))
        output_frame.pack(fill='both', expand=True)
        
        # Create scrolled text for output
        output_text = scrolledtext.ScrolledText(output_frame, wrap='none', 
                                               font=('Consolas', 9))
        output_text.pack(fill='both', expand=True)
        
        # Buttons
        button_frame = tk.Frame(main_container)
        button_frame.pack(fill='x', pady=(10, 0))
        
        cancel_button = ttk.Button(button_frame, text=i18n.get('cancel', 'Cancel'), 
                                  state='disabled')  # TODO: Implement cancel
        cancel_button.pack(side='left', padx=5)
        
        close_button = ttk.Button(button_frame, text=i18n.get('close', 'Close'),
                                 state='disabled', command=progress_dialog.destroy)
        close_button.pack(side='left', padx=5)
        
        # Disable sync button during operation
        self.sync_button.config(state='disabled')
        
        # Sync thread
        def do_sync():
            try:
                cmd = ['sync', direction, '--team', team, '--machine', machine, 
                       '--repo', repo, '--local', local_path]
                
                if self.mirror_var.get():
                    cmd.append('--mirror')
                if self.verify_var.get():
                    cmd.append('--verify')
                if self.confirm_var.get():
                    cmd.append('--confirm')
                
                # Function to update output
                def update_output(text: str):
                    progress_dialog.after(0, lambda: output_text.insert(tk.END, text))
                    progress_dialog.after(0, lambda: output_text.see(tk.END))
                    
                    # Try to extract current file from rsync output
                    if ' -> ' in text or 'building file list' in text or 'sending incremental' in text:
                        progress_dialog.after(0, lambda t=text: current_file_label.config(text=t.strip()[:80] + '...' if len(t.strip()) > 80 else t.strip()))
                
                # Run command with streaming output
                result = self.runner.run_command_streaming(cmd, update_output)
                
                # Stop progress animation
                progress_dialog.after(0, progress_bar.stop)
                
                # Determine success
                success = result.get('success', False)
                if success:
                    msg = i18n.get('sync_completed_successfully', 'Sync completed successfully!')
                    color = 'green'
                else:
                    msg = i18n.get('sync_failed', 'Sync failed!')
                    if result.get('error'):
                        msg += f"\n{result.get('error')}"
                    color = 'red'
                
                progress_dialog.after(0, lambda: status_label.config(text=msg, fg=color))
                progress_dialog.after(0, lambda: close_button.config(state='normal'))
                progress_dialog.after(0, lambda: progress_dialog.protocol('WM_DELETE_WINDOW', progress_dialog.destroy))
                
            except Exception as e:
                msg = i18n.get('sync_error', f'Error: {str(e)}')
                progress_dialog.after(0, lambda: update_output(f"\n{msg}\n"))
                progress_dialog.after(0, lambda: status_label.config(text=msg, fg=COLOR_ERROR))
                progress_dialog.after(0, lambda: close_button.config(state='normal'))
                progress_dialog.after(0, lambda: progress_dialog.protocol('WM_DELETE_WINDOW', progress_dialog.destroy))
                progress_dialog.after(0, progress_bar.stop)
            finally:
                # Re-enable sync button
                self.root.after(0, lambda: self.sync_button.config(state='normal'))
                self.root.after(0, lambda: self.status_bar.config(text=i18n.get('ready')))
        
        thread = threading.Thread(target=do_sync, daemon=True)
        thread.start()
    
    # Plugin management methods
    def refresh_plugins(self):
        """Refresh available plugins for selected repository"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not all([team, machine, repo]):
            messagebox.showerror(i18n.get('error'), i18n.get('select_team_machine_repo'))
            return
        
        self.status_bar.config(text=i18n.get('loading_plugins'))
        self.plugin_listbox.delete(0, tk.END)
        self.plugin_combo['values'] = []
        
        def load():
            cmd = ['plugin', 'list', '--team', team, '--machine', machine, '--repo', repo]
            self.logger.debug(f"Executing plugin list command: {' '.join(cmd)}")
            
            result = self.runner.run_command(cmd)
            self.logger.debug(f"Command success: {result.get('success')}")
            self.logger.debug(f"Return code: {result.get('returncode')}")
            self.logger.debug(f"Error output: {result.get('error', 'None')}")
            
            output = result.get('output', '')
            self.logger.debug(f"Output length: {len(output)}")
            self.logger.debug(f"Raw output:\n{output}")
            
            # Parse plugin names from output
            plugins = []
            in_plugins_section = False
            line_num = 0
            for line in output.split('\n'):
                line_num += 1
                self.logger.debug(f"Parsing line {line_num}: '{line}'")
                
                if 'Available plugins:' in line:
                    self.logger.debug(f"Found plugins section at line {line_num}")
                    in_plugins_section = True
                elif in_plugins_section and '•' in line:
                    # Extract plugin name from bullet point
                    plugin_name = line.split('•')[1].split('(')[0].strip()
                    self.logger.debug(f"Found plugin: '{plugin_name}' from line: '{line}'")
                    plugins.append(plugin_name)
                elif 'Plugin container status:' in line:
                    self.logger.debug(f"Found container status section at line {line_num}, stopping")
                    break
            
            self.logger.debug(f"Final plugins list: {plugins}")
            self.root.after(0, lambda: self.update_plugin_list(plugins))
        
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
    
    def update_plugin_list(self, plugins: list):
        """Update plugin listbox and combo"""
        self.logger.debug(f"update_plugin_list called with {len(plugins)} plugins: {plugins}")
        
        self.plugin_listbox.delete(0, tk.END)
        for plugin in plugins:
            self.logger.debug(f"Adding plugin to listbox: '{plugin}'")
            self.plugin_listbox.insert(tk.END, plugin)
        
        self.plugin_combo['values'] = plugins
        if plugins:
            self.logger.debug(f"Setting combo default to: '{plugins[0]}'")
            self.plugin_combo.set(plugins[0])
        else:
            self.logger.debug(f"No plugins to set in combo")
            # Clear the combo box if no plugins are available
            self.plugin_combo.set('')
        
        status_msg = i18n.get('found_plugins', count=len(plugins))
        self.logger.debug(f"Setting status: '{status_msg}'")
        self.status_bar.config(text=status_msg)
    
    def refresh_connections(self):
        """Refresh active plugin connections"""
        self.status_bar.config(text=i18n.get('refreshing_connections'))
        
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
        
        thread = threading.Thread(target=load, daemon=True)
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
        
        # Add new items with alternating row colors
        row_index = 0
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
            
            # Determine tags based on status and row index
            status = 'green' if conn['status'] == 'Active' else 'red'
            row_type = 'even' if row_index % 2 == 0 else 'odd'
            tags = (f"{status}_{row_type}",)
            
            url = f"http://localhost:{conn['port']}"
            item = self.connections_tree.insert('', 'end', 
                                              text=conn['id'],
                                              values=(conn['plugin'], url, conn['status']),
                                              tags=tags)
            new_items[conn['id']] = item
            row_index += 1
        
        # Configure tag colors
        self.connections_tree.tag_configure('green', foreground='green')
        self.connections_tree.tag_configure('red', foreground='red')
        self.connections_tree.tag_configure('green_odd', foreground='green', background='#f5f5f5')
        self.connections_tree.tag_configure('red_odd', foreground='red', background='#f5f5f5')
        self.connections_tree.tag_configure('green_even', foreground='green', background='white')
        self.connections_tree.tag_configure('red_even', foreground='red', background='white')
        
        # Re-select previously selected items if they still exist
        for conn_id in selected_ids:
            if conn_id in new_items:
                self.connections_tree.selection_add(new_items[conn_id])
        
        # Update button states based on selection
        self.on_connection_selected(None)
        
        self.status_bar.config(text=i18n.get('found_connections', count=len(connections)))
    
    def on_plugin_selected(self, event):
        """Handle plugin selection from listbox"""
        selection = event.widget.curselection()
        if selection:
            plugin_name = self.plugin_listbox.get(selection[0])
            self.plugin_combo.set(plugin_name)
    
    def on_port_mode_changed(self):
        """Handle port mode radio button change"""
        is_auto = self.port_mode.get() == 'auto'
        self.port_entry.config(state='disabled' if is_auto else 'normal')
        if not is_auto:
            self.port_entry.focus()
    
    def validate_port(self, value):
        """Validate port number input"""
        if not value:
            return True
        try:
            return 1 <= int(value) <= 65535
        except ValueError:
            return False
    
    def on_connection_selected(self, event):
        """Handle connection selection in treeview"""
        has_selection = bool(self.connections_tree.selection())
        state = 'normal' if has_selection else 'disabled'
        
        for button in [self.open_browser_button, self.copy_url_button, self.disconnect_button]:
            button.config(state=state)
    
    def connect_plugin(self):
        """Connect to selected plugin"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        plugin = self.plugin_combo.get()
        
        if not all([team, machine, repo, plugin]):
            messagebox.showerror(i18n.get('error'), i18n.get('select_all_plugin_fields'))
            return
        
        self.connect_button.config(state='disabled')
        self.status_bar.config(text=i18n.get('connecting_to', plugin=plugin))
        
        def connect():
            cmd = ['plugin', 'connect', '--team', team, '--machine', machine, 
                   '--repo', repo, '--plugin', plugin]
            
            # Add port if manual mode
            if self.port_mode.get() == 'manual':
                port_text = self.port_entry.get().strip()
                if not port_text:
                    self.root.after(0, lambda: messagebox.showerror(i18n.get('error'), i18n.get('port_error')))
                    self.root.after(0, lambda: self.connect_button.config(state='normal'))
                    return
                try:
                    port = int(port_text)
                    if not (1024 <= port <= 65535):
                        self.root.after(0, lambda: messagebox.showerror(i18n.get('error'), i18n.get('port_range_error')))
                        self.root.after(0, lambda: self.connect_button.config(state='normal'))
                        return
                    cmd.extend(['--port', str(port)])
                except ValueError:
                    self.root.after(0, lambda: messagebox.showerror(i18n.get('error'), i18n.get('invalid_port')))
                    self.root.after(0, lambda: self.connect_button.config(state='normal'))
                    return
            
            result = self.runner.run_command(cmd)
            output = result.get('output', '')
            
            if result['success']:
                # Extract URL from output
                url = next((line.split('Local URL:')[1].strip() 
                           for line in output.split('\n') 
                           if 'Local URL:' in line), None)
                
                msg = i18n.get('successfully_connected', plugin=plugin)
                if url:
                    msg += f"\n\n{i18n.get('access_at', url=url)}"
                
                self.root.after(0, lambda: messagebox.showinfo(i18n.get('success'), msg))
                self.root.after(0, self.refresh_connections)
            else:
                error = result.get('error', i18n.get('connection_failed'))
                self.root.after(0, lambda: messagebox.showerror(i18n.get('error'), error))
            
            self.root.after(0, lambda: self.connect_button.config(state='normal'))
            self.root.after(0, lambda: self.status_bar.config(text="Ready"))
        
        thread = threading.Thread(target=connect, daemon=True)
        thread.start()
    
    def disconnect_plugin(self):
        """Disconnect selected plugin connection"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror(i18n.get('error'), i18n.get('select_connection', action=i18n.get('disconnect').lower()))
            return
        
        item = self.connections_tree.item(selection[0])
        conn_id = item['text']
        plugin_name = item['values'][0]
        
        if messagebox.askyesno(i18n.get('confirm'), i18n.get('disconnect_confirm', plugin=plugin_name)):
            self.status_bar.config(text=i18n.get('disconnecting', plugin=plugin_name))
            
            def disconnect():
                cmd = ['plugin', 'disconnect', '--connection-id', conn_id]
                result = self.runner.run_command(cmd)
                
                if result['success']:
                    self.root.after(0, lambda: messagebox.showinfo(i18n.get('success'), i18n.get('disconnected', plugin=plugin_name)))
                else:
                    error = result.get('error', i18n.get('disconnect_failed'))
                    self.root.after(0, lambda: messagebox.showerror(i18n.get('error'), error))
                
                self.root.after(0, self.refresh_connections)
                self.root.after(0, lambda: self.status_bar.config(text="Ready"))
            
            thread = threading.Thread(target=disconnect, daemon=True)
            thread.start()
    
    def open_plugin_url(self):
        """Open plugin URL in browser"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror(i18n.get('error'), i18n.get('select_connection', action=i18n.get('open_in_browser').lower()))
            return
        
        url = self.connections_tree.item(selection[0])['values'][1]  # URL is second column
        
        import webbrowser
        webbrowser.open(url)
        self.status_bar.config(text=i18n.get('opened_in_browser', url=url))
    
    def copy_plugin_url(self):
        """Copy plugin URL to clipboard"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror(i18n.get('error'), i18n.get('select_connection', action=i18n.get('copy_url').lower()))
            return
        
        url = self.connections_tree.item(selection[0])['values'][1]  # URL is second column
        
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.root.update()  # Required on Windows
        
        self.status_bar.config(text=i18n.get('copied_to_clipboard', url=url), fg=COLOR_SUCCESS)
        self.root.after(2000, lambda: self.status_bar.config(fg='black'))
    
    def auto_refresh_connections(self):
        """Auto-refresh connections every 5 seconds"""
        # Only refresh if plugin tab is active
        if self.notebook.index(self.notebook.select()) == 0:  # Plugin tab is index 0
            self.refresh_connections()
        
        # Schedule next refresh
        self.root.after(AUTO_REFRESH_INTERVAL, self.auto_refresh_connections)
    
    def logout(self):
        """Logout and return to login screen"""
        if messagebox.askyesno(i18n.get('logout'), i18n.get('logout_confirm')):
            # Unregister observer before closing
            i18n.unregister_observer(self.update_all_texts)
            TokenManager.clear_token()
            self.root.destroy()
            launch_gui()
    
    def on_language_changed(self, event):
        """Handle language selection change"""
        selected_name = self.lang_combo.get()
        # Find the language code for the selected name
        for code in i18n.get_language_codes():
            if i18n.get_language_name(code) == selected_name:
                i18n.set_language(code)
                break
    
    def update_all_texts(self):
        """Update all texts when language changes"""
        # Update window title
        self.root.title(i18n.get('app_title'))
        
        # Update top frame
        auth_info = TokenManager.get_auth_info()
        self.user_label.config(text=f"{i18n.get('user')} {auth_info.get('email', 'Unknown')}")
        self.logout_button.config(text=i18n.get('logout'))
        self.lang_label.config(text=i18n.get('language') + ':')
        
        # Update resource selection frame
        self.common_frame.config(text=i18n.get('resource_selection'))
        self.team_label.config(text=i18n.get('team'))
        self.machine_label.config(text=i18n.get('machine'))
        self.repo_label.config(text=i18n.get('repository'))
        
        # Update notebook tabs
        self.notebook.tab(0, text=i18n.get('plugin_manager'))
        self.notebook.tab(1, text=i18n.get('terminal_access'))
        self.notebook.tab(2, text=i18n.get('file_sync'))
        self.notebook.tab(3, text=i18n.get('file_browser', 'File Browser'))
        
        # Update status bar
        current_text = self.status_bar.cget('text')
        if current_text in ['Ready', 'جاهز', 'Bereit']:
            self.status_bar.config(text=i18n.get('ready'))
        
        # Update each tab's contents
        self.update_plugin_tab_texts()
        self.update_terminal_tab_texts()
        self.update_sync_tab_texts()
        self.update_file_browser_tab_texts()
    
    def update_plugin_tab_texts(self):
        """Update all texts in plugin tab"""
        updates = [
            (self.plugin_management_frame, 'plugin_management'),
            (self.available_plugins_label, 'available_plugins'),
            (self.refresh_plugins_button, 'refresh_plugins'),
            (self.connect_plugin_label, 'connect_to_plugin'),
            (self.plugin_select_label, 'plugin'),
            (self.port_frame, 'local_port'),
            (self.auto_port_radio, 'auto_port'),
            (self.manual_port_radio, 'manual_port'),
            (self.connect_button, 'connect'),
            (self.connections_frame, 'active_connections'),
            (self.open_browser_button, 'open_in_browser'),
            (self.copy_url_button, 'copy_url'),
            (self.disconnect_button, 'disconnect'),
            (self.refresh_status_button, 'refresh_status'),
            (self.plugin_info_label, 'plugin_tip')
        ]
        for widget, key in updates:
            widget.config(text=i18n.get(key))
    
    def update_terminal_tab_texts(self):
        """Update all texts in terminal tab"""
        updates = [
            (self.terminal_command_label, 'command'),
            (self.execute_cmd_button, 'execute_command'),
            (self.open_repo_term_button, 'open_repo_terminal'),
            (self.open_machine_term_button, 'open_machine_terminal'),
            (self.terminal_output_label, 'output')
        ]
        for widget, key in updates:
            widget.config(text=i18n.get(key))
    
    def update_sync_tab_texts(self):
        """Update all texts in sync tab"""
        updates = [
            (self.sync_direction_label, 'direction'),
            (self.upload_radio, 'upload'),
            (self.download_radio, 'download'),
            (self.local_path_label, 'local_path'),
            (self.browse_button, 'browse'),
            (self.options_frame, 'options'),
            (self.mirror_check, 'mirror_delete'),
            (self.verify_check, 'verify_transfer'),
            (self.confirm_check, 'preview_changes'),
            (self.sync_button, 'start_sync'),
            (self.sync_output_label, 'output')
        ]
        for widget, key in updates:
            widget.config(text=i18n.get(key))
    
    def update_file_browser_tab_texts(self):
        """Update all texts in file browser tab"""
        if hasattr(self, 'file_browser'):
            self.file_browser.update_texts()


# ===== MAIN EXECUTION =====

def launch_gui():
    """Launch the simplified GUI application"""
    logger = get_logger(__name__)
    logger.info("Starting Rediacc CLI GUI...")
    
    try:
        # Load saved language preference
        logger.debug("Loading language preferences...")
        saved_language = i18n.load_language_preference()
        i18n.set_language(saved_language)
        logger.debug(f"Language set to: {saved_language}")
    except Exception as e:
        logger.debug(f"Error loading language preferences: {e}")
        import traceback
        traceback.print_exc()
    
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
    token_valid = check_token_validity()
    
    try:
        if token_valid:
            logger.debug("Token is valid, launching main window...")
            main_window = MainWindow()
            main_window.root.mainloop()
        else:
            logger.debug("No valid token, showing login window...")
            def on_login_success():
                logger.debug("Login successful, launching main window...")
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
    except Exception as e:
        logger.error(f"Critical error in main execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    launch_gui()