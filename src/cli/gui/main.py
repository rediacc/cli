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
import webbrowser
import argparse
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Tuple
import time
import datetime
import re
import urllib.request
import urllib.parse
import urllib.error

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import version from centralized location
from cli._version import __version__

# Import from consolidated core module
from core.config import (
    TokenManager,
    SubprocessRunner,
    i18n,
    TerminalDetector,
    get_logger,
    setup_logging,
    get_required,
    get,
    api_mutex
)
from core.api_client import client

# Import core functionality for SSH operations
from core.shared import (
    RepositoryConnection,
    colorize,
    setup_ssh_for_connection,
    is_windows
)

# Import GUI components
from gui.base import BaseWindow, create_tooltip
from gui.login import LoginWindow
from gui.file_browser import DualPaneFileBrowser
from gui.utilities import (
    check_token_validity, center_window,
    MAIN_WINDOW_DEFAULT_SIZE, COMBO_WIDTH_SMALL, COMBO_WIDTH_MEDIUM,
    COLUMN_WIDTH_NAME, COLUMN_WIDTH_SIZE, COLUMN_WIDTH_MODIFIED, COLUMN_WIDTH_TYPE,
    COLUMN_WIDTH_PLUGIN, COLUMN_WIDTH_URL, COLUMN_WIDTH_STATUS,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_INFO, AUTO_REFRESH_INTERVAL
)

class MainWindow(BaseWindow):
    """Main window with Terminal and File Sync tools"""
    
    def __init__(self):
        title = i18n.get('app_title')
        if __version__ != 'dev':
            title += f' v{__version__}'
        super().__init__(tk.Tk(), title)
        self.logger = get_logger(__name__)
        self.runner = SubprocessRunner()
        
        # Use global API client instance
        self.api_client = client
        
        # Ensure config manager is set for token rotation
        from core.config import get_default_config_manager
        self.api_client.set_config_manager(get_default_config_manager())
        
        # Center window at default size
        self.center_window(MAIN_WINDOW_DEFAULT_SIZE[0], MAIN_WINDOW_DEFAULT_SIZE[1])
        
        # Initialize plugin tracking
        self.plugins_loaded_for = None
        self.available_plugins = []  # List of available plugins
        self.plugin_connections = {}  # Active plugin connections
        self.active_operations = set()  # Track ongoing operations to prevent multiple clicks
        
        # Track active popup menu
        self.active_popup_menu = None
        # Bind global click handler for closing popups
        self.root.bind_all('<Button-1>', self._handle_global_click, add='+')
        
        # Startup flag to prevent automatic connections
        self.is_starting_up = True
        
        # Track background threads for cleanup
        self.background_threads = []
        
        # Initialize machine data storage
        self.machines_data = {}
        
        # Initialize terminal detector
        self.terminal_detector = TerminalDetector()
        
        # Initialize menu state variables
        self.preview_var = tk.BooleanVar(value=False)
        self.fullscreen_var = tk.BooleanVar(value=False)
        
        # Status bar components
        self.status_bar_frame = None
        self.connection_status_frame = None
        self.activity_status_frame = None
        self.performance_status_frame = None
        self.user_status_frame = None
        
        # Status bar labels
        self.connection_status_label = None
        self.activity_status_label = None
        self.performance_status_label = None
        self.user_status_label = None
        self.session_timer_label = None
        
        # Activity animation
        self.activity_spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.activity_spinner_index = 0
        self.activity_animation_active = False
        self.activity_animation_id = None
        
        # Session tracking
        self.session_start_time = time.time()
        self.session_timer_id = None
        self.auto_refresh_timer_id = None
        
        # Transfer tracking
        self.active_transfers = {}
        self.transfer_speed = 0
        self.transfer_start_time = None
        self.bytes_transferred = 0
        
        # Register for language changes
        i18n.register_observer(self.update_all_texts)
        
        # Create widgets first (needed by menu bar)
        self.create_widgets()
        
        # Create menu bar after widgets
        self.create_menu_bar()
        
        # Schedule initial data load after mainloop starts to prevent blocking
        self.root.after(100, self.load_initial_data)
        
        # Start auto-refresh for plugin connections
        self.auto_refresh_connections()
        
        # Load plugins if we have a complete valid selection
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        has_valid_selection = (
            team and not self._is_placeholder_value(team, 'select_team') and
            machine and not self._is_placeholder_value(machine, 'select_machine') and
            repo and not self._is_placeholder_value(repo, 'select_repository')
        )
        
        if has_valid_selection:
            current_selection = (team, machine, repo)
            self.refresh_plugins()
            self.refresh_connections()
            self.plugins_loaded_for = current_selection
        
        # Initial menu state update
        self.update_menu_states()
        
        # Initialization complete, allow connections
        self.is_starting_up = False
    
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
    
    def _is_placeholder_value(self, combo_value: str, placeholder_key: str) -> bool:
        """Check if a combobox value is a placeholder (empty or translated placeholder text)
        
        Args:
            combo_value: Current value of the combobox
            placeholder_key: Translation key for the placeholder (e.g., 'select_team')
            
        Returns:
            True if the value is empty or a placeholder value
        """
        if not combo_value:
            return True
            
        # Get the current placeholder value
        current_placeholder = i18n.get(placeholder_key) or ''
        
        # Check if it matches the current placeholder
        if combo_value == current_placeholder:
            return True
            
        # Also check against all known language placeholders by checking translations directly
        # This handles cases where language was changed but combo still has old placeholder
        for lang_code in i18n.LANGUAGES:
            lang_placeholder = i18n.translations.get(lang_code, {}).get(placeholder_key)
            if lang_placeholder and combo_value == lang_placeholder:
                return True
                
        return False
    
    def _update_combo_placeholder(self, combo: ttk.Combobox, placeholder_key: str) -> None:
        """Update a combobox placeholder if it's currently showing a placeholder value
        
        Args:
            combo: The combobox to update
            placeholder_key: Translation key for the placeholder
        """
        if self._is_placeholder_value(combo.get(), placeholder_key):
            combo.set(i18n.get(placeholder_key) or '')
    
    def _get_name(self, item, *fields):
        """Get name from item trying multiple field names"""
        return next((item[field] for field in fields if field in item), '')
    
    def _handle_api_error(self, error_msg):
        """Handle API errors, especially authentication errors"""
        auth_errors = ['401', 'Not authenticated', 'Invalid request credential']
        if any(error in str(error_msg) for error in auth_errors):
            self.activity_status_label.config(text=i18n.get('authentication_expired'), fg=COLOR_ERROR)
            messagebox.showerror(i18n.get('error'), i18n.get('session_expired'))
            TokenManager.clear_token()
            self.root.destroy()
            launch_gui()
            return True
        return False
    
    def create_menu_bar(self):
        """Create the application menu bar"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        # File Menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('file'), menu=self.file_menu, underline=0)
        
        # Edit Menu
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('edit'), menu=self.edit_menu, underline=0)
        
        # View Menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('view'), menu=self.view_menu, underline=0)
        
        # Tools Menu
        self.tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('tools'), menu=self.tools_menu, underline=0)
        
        # Connection Menu
        self.connection_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('connection'), menu=self.connection_menu, underline=0)
        
        # Help Menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('help'), menu=self.help_menu, underline=0)
        
        # Populate menus
        self.populate_file_menu()
        self.populate_edit_menu()
        self.populate_view_menu()
        self.populate_tools_menu()
        self.populate_connection_menu()
        self.populate_help_menu()
    
    def populate_file_menu(self):
        """Populate the File menu"""
        # Clear existing menu items
        self.file_menu.delete(0, tk.END)
        
        # New Session
        self.file_menu.add_command(
            label=i18n.get('new_session'),
            accelerator='Ctrl+N',
            command=self.new_session
        )
        
        self.file_menu.add_separator()
        
        # Preferences
        self.file_menu.add_command(
            label=i18n.get('preferences'),
            accelerator='Ctrl+,',
            command=self.show_preferences
        )
        
        # Language submenu
        self.language_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label=i18n.get('language'), menu=self.language_menu)
        self.populate_language_menu()
        
        self.file_menu.add_separator()
        
        # Logout
        self.file_menu.add_command(
            label=i18n.get('logout'),
            accelerator='Ctrl+Shift+L',
            command=self.logout
        )
        
        # Exit
        self.file_menu.add_command(
            label=i18n.get('exit'),
            accelerator='Ctrl+Q',
            command=self.on_closing
        )
        
        # Bind accelerators
        self.root.bind_all('<Control-n>', lambda e: self.new_session())
        self.root.bind_all('<Control-comma>', lambda e: self.show_preferences())
        self.root.bind_all('<Control-Shift-L>', lambda e: self.logout())
        self.root.bind_all('<Control-q>', lambda e: self.on_closing())
    
    def populate_language_menu(self):
        """Populate the language submenu"""
        self.logger.debug(f"Populating language menu - current language: {i18n.current_language}")
        self.language_menu.delete(0, tk.END)
        current_lang = i18n.current_language
        
        for code in i18n.get_language_codes():
            name = i18n.get_language_name(code)
            # Add checkmark for current language
            label = f"✓ {name}" if code == current_lang else f"  {name}"
            self.logger.debug(f"Adding language menu item: {label} (code: {code})")
            self.language_menu.add_command(
                label=label,
                command=lambda c=code: self.change_language(c)
            )
    
    def populate_edit_menu(self):
        """Populate the Edit menu"""
        # Clear existing menu items
        self.edit_menu.delete(0, tk.END)
        
        # Cut
        self.edit_menu.add_command(
            label=i18n.get('cut'),
            accelerator='Ctrl+X',
            command=self.cut_selected
        )
        
        # Copy
        self.edit_menu.add_command(
            label=i18n.get('copy'),
            accelerator='Ctrl+C',
            command=self.copy_selected
        )
        
        # Paste
        self.edit_menu.add_command(
            label=i18n.get('paste'),
            accelerator='Ctrl+V',
            command=self.paste_files
        )
        
        # Select All
        self.edit_menu.add_command(
            label=i18n.get('select_all'),
            accelerator='Ctrl+A',
            command=self.select_all
        )
        
        self.edit_menu.add_separator()
        
        # Find
        self.edit_menu.add_command(
            label=i18n.get('find'),
            accelerator='Ctrl+F',
            command=self.focus_search
        )
        
        # Clear Filter
        self.edit_menu.add_command(
            label=i18n.get('clear_filter'),
            accelerator='Escape',
            command=self.clear_search
        )
    
    def populate_view_menu(self):
        """Populate the View menu"""
        # Clear existing menu items
        self.view_menu.delete(0, tk.END)
        
        # Show Preview
        self.view_menu.add_checkbutton(
            label=i18n.get('show_preview'),
            accelerator='F3',
            variable=self.preview_var,
            command=self.toggle_preview
        )
        
        self.view_menu.add_separator()
        
        # View modes
        self.view_mode_var = tk.StringVar(value='split')
        
        self.view_menu.add_radiobutton(
            label=i18n.get('local_files_only'),
            accelerator='Ctrl+1',
            variable=self.view_mode_var,
            value='local',
            command=lambda: self.set_view_mode('local')
        )
        
        self.view_menu.add_radiobutton(
            label=i18n.get('remote_files_only'),
            accelerator='Ctrl+2',
            variable=self.view_mode_var,
            value='remote',
            command=lambda: self.set_view_mode('remote')
        )
        
        self.view_menu.add_radiobutton(
            label=i18n.get('split_view'),
            accelerator='Ctrl+3',
            variable=self.view_mode_var,
            value='split',
            command=lambda: self.set_view_mode('split')
        )
        
        self.view_menu.add_separator()
        
        # Refresh commands
        self.view_menu.add_command(
            label=i18n.get('refresh_local'),
            accelerator='F5',
            command=self.refresh_local
        )
        
        self.view_menu.add_command(
            label=i18n.get('refresh_remote'),
            accelerator='Shift+F5',
            command=self.refresh_remote
        )
        
        self.view_menu.add_command(
            label=i18n.get('refresh_all'),
            accelerator='Ctrl+R',
            command=self.refresh_all
        )
        
        self.view_menu.add_separator()
        
        # Full Screen
        self.view_menu.add_checkbutton(
            label=i18n.get('full_screen'),
            accelerator='F11',
            variable=self.fullscreen_var,
            command=self.toggle_fullscreen
        )
        
        # Bind accelerators
        self.root.bind_all('<F3>', lambda e: self.toggle_preview())
        self.root.bind_all('<Control-1>', lambda e: self.set_view_mode('local'))
        self.root.bind_all('<Control-2>', lambda e: self.set_view_mode('remote'))
        self.root.bind_all('<Control-3>', lambda e: self.set_view_mode('split'))
        self.root.bind_all('<Shift-F5>', lambda e: self.refresh_remote())
        self.root.bind_all('<Control-r>', lambda e: self.refresh_all())
        self.root.bind_all('<F11>', lambda e: self.toggle_fullscreen())
    
    def populate_tools_menu(self):
        """Populate the Tools menu"""
        # Clear existing menu items
        self.tools_menu.delete(0, tk.END)
        
        # Terminal submenu
        terminal_menu = tk.Menu(self.tools_menu, tearoff=0)
        self.tools_menu.add_cascade(
            label=i18n.get('terminal'),
            menu=terminal_menu
        )
        
        terminal_menu.add_command(
            label=i18n.get('repository_terminal'),
            accelerator='Ctrl+T',
            command=self.open_repo_terminal
        )
        
        terminal_menu.add_command(
            label=i18n.get('machine_terminal'),
            accelerator='Ctrl+Shift+T',
            command=self.open_machine_terminal
        )
        
        terminal_menu.add_command(
            label=i18n.get('quick_command'),
            accelerator='Ctrl+K',
            command=self.show_quick_command
        )
        
        # File Sync
        self.tools_menu.add_command(
            label=i18n.get('file_sync'),
            accelerator='Ctrl+S',
            command=lambda: None  # No tab switching needed
        )
        
        self.tools_menu.add_separator()
        
        # Transfer Options
        self.tools_menu.add_command(
            label=i18n.get('transfer_options'),
            accelerator='Ctrl+Shift+O',
            command=self.show_transfer_options_wrapper
        )
        
        # Console
        self.tools_menu.add_command(
            label=i18n.get('console'),
            accelerator='F12',
            command=self.show_console
        )
        
        # Bind accelerators
        self.root.bind_all('<Control-t>', lambda e: self.open_repo_terminal())
        self.root.bind_all('<Control-Shift-T>', lambda e: self.open_machine_terminal())
        self.root.bind_all('<Control-k>', lambda e: self.show_quick_command())
        self.root.bind_all('<Control-s>', lambda e: None)  # No tab switching needed
        self.root.bind_all('<Control-Shift-O>', lambda e: self.show_transfer_options_wrapper())
        self.root.bind_all('<F12>', lambda e: self.show_console())
    
    def populate_plugins_menu(self):
        """Populate the Plugins menu with available plugins - DEPRECATED"""
        # This method is kept for compatibility but no longer used
        # All plugin functionality is now in the toolbar
        return
        
        # Get current selection
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        # Check if all required fields are selected
        has_selection = (team and not self._is_placeholder_value(team, 'select_team') and
                        machine and not self._is_placeholder_value(machine, 'select_machine') and
                        repo and not self._is_placeholder_value(repo, 'select_repository'))
        
        if not has_selection:
            # Add disabled message when no selection
            self.plugins_menu.add_command(
                label=i18n.get('select_repository_first'),
                state='disabled'
            )
            return
        
        # Add refresh command
        self.plugins_menu.add_command(
            label=i18n.get('refresh_plugins'),
            command=self.refresh_plugins_menu
        )
        self.plugins_menu.add_separator()
        
        # Get available plugins
        if hasattr(self, 'available_plugins') and self.available_plugins:
            for plugin in self.available_plugins:
                # Create submenu for each plugin
                plugin_submenu = tk.Menu(self.plugins_menu, tearoff=0)
                self.plugins_menu.add_cascade(label=plugin, menu=plugin_submenu)
                
                # Check if plugin is connected
                is_connected = self.is_plugin_connected(plugin)
                
                # Add submenu items
                plugin_submenu.add_command(
                    label=i18n.get('connect'),
                    command=lambda p=plugin: self.connect_plugin_from_menu(p),
                    state='disabled' if is_connected else 'normal'
                )
                
                if is_connected:
                    # Get connection info
                    conn_info = self.get_plugin_connection_info(plugin)
                    if conn_info:
                        plugin_submenu.add_command(
                            label=i18n.get('disconnect'),
                            command=lambda p=plugin, c=conn_info: self.disconnect_plugin_from_menu(p, c)
                        )
                        plugin_submenu.add_command(
                            label=i18n.get('copy_url'),
                            command=lambda url=conn_info['url']: self.copy_url_to_clipboard(url)
                        )
                        plugin_submenu.add_command(
                            label=i18n.get('open_in_browser'),
                            command=lambda url=conn_info['url']: webbrowser.open(url)
                        )
                    
                plugin_submenu.add_separator()
                plugin_submenu.add_command(
                    label=i18n.get('status') + ': ' + (i18n.get('connected') if is_connected else i18n.get('not_connected')),
                    state='disabled'
                )
        else:
            # No plugins available
            self.plugins_menu.add_command(
                label=i18n.get('no_plugins_available'),
                state='disabled'
            )
    
    def populate_connection_menu(self):
        """Populate the Connection menu"""
        # Clear existing menu items
        self.connection_menu.delete(0, tk.END)
        
        # Connect
        self.connection_menu.add_command(
            label=i18n.get('connect'),
            accelerator='Ctrl+Shift+C',
            command=self.connect,
            state='disabled'  # Will be managed by update_menu_states
        )
        
        # Disconnect
        self.connection_menu.add_command(
            label=i18n.get('disconnect'),
            accelerator='Ctrl+Shift+D',
            command=self.disconnect,
            state='disabled'  # Will be managed by update_menu_states
        )
        
        self.connection_menu.add_separator()
        
        # Recent Connections label
        self.connection_menu.add_command(
            label=i18n.get('recent_connections'),
            state='disabled'
        )
        
        # Recent connections will be added dynamically
        self.recent_connections_start_index = self.connection_menu.index(tk.END) + 1
        
        self.connection_menu.add_separator()
        
        # Bind accelerators
        self.root.bind_all('<Control-Shift-C>', lambda e: self.connect())
        self.root.bind_all('<Control-Shift-D>', lambda e: self.disconnect())
    
    def populate_help_menu(self):
        """Populate the Help menu"""
        # Clear existing menu items
        self.help_menu.delete(0, tk.END)
        
        # Documentation
        self.help_menu.add_command(
            label=i18n.get('documentation'),
            accelerator='F1',
            command=self.show_documentation
        )
        
        # Keyboard Shortcuts
        self.help_menu.add_command(
            label=i18n.get('keyboard_shortcuts'),
            accelerator='Ctrl+?',
            command=self.show_keyboard_shortcuts
        )
        
        self.help_menu.add_separator()
        
        # Check for Updates
        self.help_menu.add_command(
            label=i18n.get('check_updates'),
            accelerator='Ctrl+U',
            command=self.check_for_updates
        )
        
        # About
        self.help_menu.add_command(
            label=i18n.get('about'),
            accelerator='Ctrl+Shift+A',
            command=self.show_about
        )
        
        # Bind accelerators
        self.root.bind_all('<F1>', lambda e: self.show_documentation())
        self.root.bind_all('<Control-question>', lambda e: self.show_keyboard_shortcuts())
        self.root.bind_all('<Control-u>', lambda e: self.check_for_updates())
        self.root.bind_all('<Control-Shift-A>', lambda e: self.show_about())
    
    def create_widgets(self):
        """Create main window widgets"""
        # Create a clean toolbar frame - no more user info here
        toolbar_frame = tk.Frame(self.root)
        toolbar_frame.pack(fill='x', padx=5, pady=5)
        
        # Resource selection frame - two row layout
        self.resource_frame = tk.Frame(self.root)
        self.resource_frame.pack(fill='x', padx=10, pady=5)
        
        # Configure grid columns
        self.resource_frame.grid_columnconfigure(0, weight=1)  # Team column
        self.resource_frame.grid_columnconfigure(1, weight=1)  # Machine column
        self.resource_frame.grid_columnconfigure(2, weight=1)  # Repository column
        self.resource_frame.grid_columnconfigure(3, weight=0)  # Connect button (fixed width)
        self.resource_frame.grid_columnconfigure(4, weight=0)  # Status indicator (fixed width)
        
        # Row 1: Labels and Connect button
        self.team_label = tk.Label(self.resource_frame, text=i18n.get('team'), 
                                  font=('Arial', 9), fg='#666666')
        self.team_label.grid(row=0, column=0, sticky='w', padx=(5, 5), pady=(0, 2))
        
        self.machine_label = tk.Label(self.resource_frame, text=i18n.get('machine'), 
                                     font=('Arial', 9), fg='#666666')
        self.machine_label.grid(row=0, column=1, sticky='w', padx=(5, 5), pady=(0, 2))
        
        self.repo_label = tk.Label(self.resource_frame, text=i18n.get('repository'), 
                                  font=('Arial', 9), fg='#666666')
        self.repo_label.grid(row=0, column=2, sticky='w', padx=(5, 5), pady=(0, 2))
        
        # Connection status indicator (just the light) - moved to where Connect button was
        self.connection_indicator = tk.Label(self.resource_frame, text='○', font=('Arial', 14), fg='#999999')
        self.connection_indicator.grid(row=0, column=3, rowspan=2, padx=(10, 10))
        
        # Row 2: Dropdown combos
        self.team_combo = ttk.Combobox(self.resource_frame, state='readonly')
        self.team_combo.set(i18n.get('select_team'))
        self.team_combo.grid(row=1, column=0, sticky='ew', padx=(5, 5), pady=(0, 5))
        self.team_combo.bind('<<ComboboxSelected>>', lambda e: self.on_team_changed())
        create_tooltip(self.team_combo, i18n.get('team_tooltip'))
        
        self.machine_combo = ttk.Combobox(self.resource_frame, state='readonly')
        self.machine_combo.set(i18n.get('select_machine'))
        self.machine_combo.grid(row=1, column=1, sticky='ew', padx=(5, 5), pady=(0, 5))
        self.machine_combo.bind('<<ComboboxSelected>>', lambda e: self.on_machine_changed())
        create_tooltip(self.machine_combo, i18n.get('machine_tooltip'))
        
        self.repo_combo = ttk.Combobox(self.resource_frame, state='readonly')
        self.repo_combo.set(i18n.get('select_repository'))
        self.repo_combo.grid(row=1, column=2, sticky='ew', padx=(5, 5), pady=(0, 5))
        self.repo_combo.bind('<<ComboboxSelected>>', lambda e: self.on_repository_changed())
        create_tooltip(self.repo_combo, i18n.get('repo_tooltip'))
        
        # Hidden repo filter label (for backward compatibility)
        self.repo_filter_label = tk.Label(self.resource_frame, text="", font=('Arial', 9), fg='gray')
        
        # Plugin toolbar - create BEFORE status bar
        self.create_plugin_toolbar()
        
        # Enhanced multi-section status bar - create BEFORE content
        self.create_status_bar()
        
        # Create main content frame (no tabs needed)
        self.browser_frame = tk.Frame(self.root)
        self.browser_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create file browser directly
        self.create_file_browser_tab()
    
    def create_plugin_toolbar(self):
        """Create plugin quick access toolbar"""
        # Plugin toolbar frame
        self.plugin_toolbar_frame = tk.Frame(self.root, relief=tk.RIDGE, bd=1)
        self.plugin_toolbar_frame.pack(fill='x', padx=5, pady=(5, 0))
        
        # Inner frame for buttons with padding
        inner_frame = tk.Frame(self.plugin_toolbar_frame)
        inner_frame.pack(fill='x', padx=5, pady=5)
        
        # Label
        label = tk.Label(inner_frame, text=i18n.get('plugins') + ":", 
                        font=('Arial', 10, 'bold'))
        label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Plugin buttons container
        self.plugin_buttons_frame = tk.Frame(inner_frame)
        self.plugin_buttons_frame.pack(side=tk.LEFT, fill='x', expand=True)
        
        # Dictionary to store plugin buttons
        self.plugin_buttons = {}
        
        # Dictionary to store tooltips for cleanup
        self.plugin_tooltips = {}
        
        # Dictionary to track keyboard shortcuts
        self.plugin_shortcuts = {}
        
        # Initial message when no plugins available
        self.no_plugins_label = tk.Label(self.plugin_buttons_frame, 
                                       text=i18n.get('select_repository_for_plugins'),
                                       font=('Arial', 9), fg='gray')
        self.no_plugins_label.pack(side=tk.LEFT, padx=5)
        
        # Right side container for status and actions
        right_container = tk.Frame(inner_frame)
        right_container.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Status indicator
        self.plugin_status_label = tk.Label(right_container, 
                                          text=i18n.get('plugin_status_loading'),
                                          font=('Arial', 9), fg='gray')
        self.plugin_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Separator
        separator = tk.Frame(right_container, width=1, bg='#d0d0d0')
        separator.pack(side=tk.LEFT, fill='y', padx=5, pady=2)
        
        # Refresh plugins button (always visible)
        self.refresh_plugins_button = ttk.Button(right_container, 
                                               text=i18n.get('refresh'),
                                               command=self.refresh_plugins_toolbar,
                                               width=10)
        self.refresh_plugins_button.pack(side=tk.LEFT, padx=(5, 0))
        create_tooltip(self.refresh_plugins_button, i18n.get('refresh_plugins_tooltip'))
        
        # Initialize plugin connection count
        self.plugin_connection_count = 0
        self.update_plugin_status_label()
        
        # Bind Ctrl+0 for refresh all
        self.root.bind_all('<Control-Key-0>', lambda e: self.refresh_all_plugins())
    
    def update_plugin_status_label(self):
        """Update the plugin status label with connection count"""
        if not hasattr(self, 'plugin_status_label'):
            return
            
        total_plugins = len(self.available_plugins) if hasattr(self, 'available_plugins') else 0
        connected_count = len(self.plugin_connections) if hasattr(self, 'plugin_connections') else 0
        
        if total_plugins == 0:
            status_text = i18n.get('no_plugins_available')
            color = 'gray'
        elif connected_count == 0:
            status_text = i18n.get('plugin_status_none_connected', count=total_plugins)
            color = '#666666'
        elif connected_count == total_plugins:
            status_text = i18n.get('plugin_status_all_connected', count=total_plugins)
            color = '#006400'  # Dark green
        else:
            status_text = i18n.get('plugin_status_some_connected',
                connected=connected_count, total=total_plugins)
            color = '#FF8C00'  # Dark orange
        
        self.plugin_status_label.config(text=status_text, fg=color)
    
    def create_status_bar(self):
        """Create the enhanced multi-section status bar"""
        # Main status bar container
        self.status_bar_frame = tk.Frame(self.root, relief='sunken', bd=1, height=24)
        self.status_bar_frame.pack(fill='x', side='bottom', pady=(5, 0))
        self.status_bar_frame.pack_propagate(False)  # Fixed height
        
        # Section 1: Connection Status (30%)
        self.connection_status_frame = tk.Frame(self.status_bar_frame)
        self.connection_status_frame.pack(side='left', fill='x', expand=True, padx=(10, 20))
        
        self.connection_status_label = tk.Label(self.connection_status_frame, 
                                              text="🔴 Not connected",
                                              anchor='w')
        self.connection_status_label.pack(fill='x')
        self.connection_status_label.bind("<Button-1>", self.show_connection_details)
        self._create_tooltip(self.connection_status_label, "Click for connection details")
        
        # Separator 1
        separator1 = tk.Frame(self.status_bar_frame, width=1, bg='#d0d0d0')
        separator1.pack(side='left', fill='y', padx=5, pady=2)
        
        # Section 2: Activity Monitor (25%)
        self.activity_status_frame = tk.Frame(self.status_bar_frame)
        self.activity_status_frame.pack(side='left', fill='x', expand=True)
        
        self.activity_status_label = tk.Label(self.activity_status_frame,
                                            text="Ready",
                                            anchor='w')
        self.activity_status_label.pack(fill='x')
        self.activity_status_label.bind("<Button-1>", self.show_transfer_queue)
        self._create_tooltip(self.activity_status_label, "Click to view transfer queue")
        
        # Separator 2
        separator2 = tk.Frame(self.status_bar_frame, width=1, bg='#d0d0d0')
        separator2.pack(side='left', fill='y', padx=5, pady=2)
        
        # Section 3: Performance Metrics (25%)
        self.performance_status_frame = tk.Frame(self.status_bar_frame)
        self.performance_status_frame.pack(side='left', fill='x', expand=True)
        
        self.performance_status_label = tk.Label(self.performance_status_frame,
                                               text="💾 Calculating space...",
                                               anchor='w')
        self.performance_status_label.pack(fill='x')
        self.performance_status_label.bind("<Button-1>", self.toggle_performance_display)
        self._create_tooltip(self.performance_status_label, "Click to toggle display")
        
        # Separator 3
        separator3 = tk.Frame(self.status_bar_frame, width=1, bg='#d0d0d0')
        separator3.pack(side='left', fill='y', padx=5, pady=2)
        
        # Section 4: User Info (20%)
        self.user_status_frame = tk.Frame(self.status_bar_frame)
        self.user_status_frame.pack(side='right', fill='x', padx=(20, 10))
        
        # User info container
        user_container = tk.Frame(self.user_status_frame)
        user_container.pack(side='right')
        
        # Settings button
        self.settings_button = tk.Label(user_container, text="⚙️", cursor='hand2')
        self.settings_button.pack(side='right', padx=(5, 0))
        self.settings_button.bind("<Button-1>", self.open_preferences)
        self._create_tooltip(self.settings_button, "Settings")
        
        # User and timer
        auth_info = TokenManager.get_auth_info()
        email = auth_info.get('email', 'User')
        self.user_status_label = tk.Label(user_container, text=f"👤 {email} | ")
        self.user_status_label.pack(side='left')
        
        self.session_timer_label = tk.Label(user_container, text="⏱ 00:00:00")
        self.session_timer_label.pack(side='left')
        
        # Start session timer
        self.update_session_timer()
        
        # Schedule initial space calculation
        self.root.after(100, self.update_space_info)
    
    
    def create_file_browser_tab(self):
        """Create dual-pane file browser interface"""
        # Create instance of DualPaneFileBrowser
        self.file_browser = DualPaneFileBrowser(self.browser_frame, self)
    
    
    def on_connect_clicked(self):
        """Handle connect button click - redirects to file browser"""
        # This method is kept for compatibility
        # The actual connect button is now in the file browser's Transfer Actions section
        pass
    
    # Status Bar Update Methods
    
    def update_connection_status(self, connected: bool, info_dict: dict = None):
        """Update the connection status section"""
        if connected:
            # Update connection indicator
            self.connection_indicator.config(text='●', fg='#28a745')  # Green filled circle
            
            # Update Connect button in file browser if it exists
            if hasattr(self, 'file_browser') and hasattr(self.file_browser, 'connect_button'):
                self.file_browser.connect_button.config(text=i18n.get('disconnect'))
            
            if info_dict:
                team = info_dict.get('team', 'Unknown')
                machine = info_dict.get('machine', 'Unknown')
                repo = info_dict.get('repo', 'Unknown')
                
                # Update status bar
                status_text = f"🟢 Connected to {team}/{machine}/{repo}"
                tooltip = f"Team: {team}\nMachine: {machine}\nRepository: {repo}\nPath: {info_dict.get('path', '/')}"
            else:
                status_text = "🟢 Connected"
                tooltip = "Connected to remote"
            
            # Update status bar
            if self.connection_status_label:
                self.connection_status_label.config(text=status_text, fg='#2e7d32')
        else:
            # Update connection indicator
            self.connection_indicator.config(text='○', fg='#999999')  # Gray empty circle
            
            # Update Connect button in file browser if it exists
            if hasattr(self, 'file_browser') and hasattr(self.file_browser, 'connect_button'):
                self.file_browser.connect_button.config(text=i18n.get('connect'))
            
            # Update status bar
            if self.connection_status_label:
                self.connection_status_label.config(text="🔴 Not connected", fg='#c62828')
            
            tooltip = "Click Connect to establish connection"
        
        # Update tooltip
        if hasattr(self.connection_status_label, '_tooltip'):
            self.connection_status_label._tooltip.config(text=tooltip)
    
    def update_activity_status(self, operation: str = None, file_count: int = 0, size: int = 0):
        """Update the activity monitor section"""
        if operation:
            if operation == 'upload':
                icon = "↑"
            elif operation == 'download':
                icon = "↓"
            else:
                icon = "↔"
            
            if self.activity_animation_active:
                spinner = self.activity_spinner_chars[self.activity_spinner_index]
                status_text = f"{spinner} {icon} {file_count} files ({self._format_size(size)})"
            else:
                status_text = f"{icon} {file_count} files ({self._format_size(size)})"
        else:
            # Default status
            status_text = "Ready"
        
        if self.activity_status_label:
            self.activity_status_label.config(text=status_text)
    
    def update_performance_status(self, speed: float = None, space_info: dict = None):
        """Update the performance metrics section"""
        if speed is not None:
            # Show transfer speed during operations
            status_text = f"📊 {self._format_size(int(speed))}/s"
            if self.performance_status_label:
                self.performance_status_label.config(text=status_text)
        elif space_info:
            # Show space information when idle
            local_free = space_info.get('local_free', 0)
            remote_free = space_info.get('remote_free', 0)
            
            if hasattr(self, 'file_browser') and self.file_browser.ssh_connection and remote_free > 0:
                status_text = f"💾 Remote: {self._format_size(remote_free)} free"
            else:
                status_text = f"💾 Local: {self._format_size(local_free)} free"
            
            if self.performance_status_label:
                self.performance_status_label.config(text=status_text)
    
    def update_user_status(self, email: str = None, session_time: str = None):
        """Update the user info section"""
        if email:
            if self.user_status_label:
                self.user_status_label.config(text=f"👤 {email} | ")
        
        if session_time:
            if self.session_timer_label:
                self.session_timer_label.config(text=f"⏱ {session_time}")
    
    def update_session_timer(self):
        """Update the session timer every second"""
        # Safety check: ensure window still exists
        try:
            if not self.root.winfo_exists():
                return
        except:
            return
            
        elapsed = int(time.time() - self.session_start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        session_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.update_user_status(session_time=session_time)
        
        # Schedule next update
        self.session_timer_id = self.root.after(1000, self.update_session_timer)
    
    def start_activity_animation(self):
        """Start the activity spinner animation"""
        self.activity_animation_active = True
        self.animate_activity_spinner()
    
    def stop_activity_animation(self):
        """Stop the activity spinner animation"""
        self.activity_animation_active = False
        if self.activity_animation_id:
            self.root.after_cancel(self.activity_animation_id)
            self.activity_animation_id = None
    
    def animate_activity_spinner(self):
        """Animate the activity spinner"""
        # Safety check: ensure window still exists
        try:
            if not self.root.winfo_exists():
                return
        except:
            return
            
        if self.activity_animation_active:
            self.activity_spinner_index = (self.activity_spinner_index + 1) % len(self.activity_spinner_chars)
            # Trigger activity status update to show new spinner frame
            current_text = self.activity_status_label.cget('text')
            self.activity_status_label.config(text=current_text)  # Force refresh
            
            # Schedule next frame
            self.activity_animation_id = self.root.after(100, self.animate_activity_spinner)
    
    def update_space_info(self):
        """Update disk space information"""
        def get_space_info():
            try:
                # Get local disk space
                if sys.platform == 'win32':
                    import ctypes
                    free_bytes = ctypes.c_ulonglong(0)
                    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        ctypes.c_wchar_p("C:\\"),
                        ctypes.pointer(free_bytes), None, None
                    )
                    local_free = free_bytes.value
                else:
                    import os
                    stat = os.statvfs(os.path.expanduser("~"))
                    local_free = stat.f_bavail * stat.f_frsize
                
                return {'local_free': local_free, 'remote_free': 0}
            except Exception as e:
                self.logger.error(f"Error getting space info: {e}")
                return {'local_free': 0, 'remote_free': 0}
        
        # Update directly since we're in main thread
        space_info = get_space_info()
        self.update_performance_status(space_info=space_info)
        
        # Schedule next update in 30 seconds
        self.root.after(30000, self.update_space_info)
    
    # Click Actions for Status Bar
    
    def show_connection_details(self, event):
        """Show detailed connection information"""
        if hasattr(self, 'file_browser') and self.file_browser.ssh_connection:
            info = f"Connection Details:\n\n"
            info += f"Team: {self.team_combo.get()}\n"
            info += f"Machine: {self.machine_combo.get()}\n"
            info += f"Repository: {self.repo_combo.get()}\n"
            messagebox.showinfo("Connection Details", info)
        else:
            messagebox.showinfo("Not Connected", 
                              "No active connection.\n\n"
                              "Please connect to a repository first.")
    
    def show_transfer_queue(self, event):
        """Show transfer queue/history window"""
        messagebox.showinfo("Transfer Queue", 
                          "Transfer queue functionality will be implemented in a future update.")
    
    def toggle_performance_display(self, event):
        """Toggle between speed and space display"""
        current_text = self.performance_status_label.cget('text')
        if 'MB/s' in current_text or 'KB/s' in current_text or 'GB/s' in current_text:
            # Currently showing speed, switch to space
            self.update_space_info()
        else:
            # Currently showing space, will switch to speed on next transfer
            pass
    
    def open_preferences(self, event):
        """Open preferences/settings dialog"""
        messagebox.showinfo("Settings", 
                          "Settings dialog will be implemented in a future update.")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        # Simple tooltip implementation - store reference for updates
        widget._tooltip = type('Tooltip', (), {'text': text, 'config': lambda self, **kw: setattr(self, 'text', kw.get('text', self.text))})()
    
    def load_initial_data(self):
        """Load initial data after mainloop starts"""
        self.load_teams()
    
    def load_teams(self):
        """Load available teams"""
        self.update_activity_status()
        
        # Direct API call to get teams
        response = self.api_client.token_request('GetCompanyTeams', {})
        
        if response.get('error'):
            error_msg = response.get('error', i18n.get('failed_to_load_teams'))
            if not self._handle_api_error(error_msg):
                self.activity_status_label.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
        else:
            # Extract teams from resultSets - second table contains the actual data
            teams_data = []
            if response.get('resultSets') and len(response['resultSets']) > 1:
                teams_data = response['resultSets'][1].get('data', [])
            
            teams = [self._get_name(team, 'teamName', 'name') for team in teams_data]
            self.update_teams(teams)
    
    def on_team_changed(self):
        """Handle team selection change"""
        self.load_machines()
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
        # Disconnect file browser SSH connection since team changed
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.disconnect()
            # Update Connect button state
            self.file_browser.update_connect_button_state()
        # Update menu states
        self.update_menu_states()
    
    def on_machine_changed(self):
        """Handle machine selection change"""
        self.load_repositories()
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
        # Disconnect file browser SSH connection since machine changed
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.disconnect()
            # Update Connect button state
            self.file_browser.update_connect_button_state()
        # Update menu states
        self.update_menu_states()
    
    def on_repository_changed(self):
        """Handle repository selection change"""
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
        # Disconnect file browser SSH connection since repository changed
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.disconnect()
        
        # Check if we have valid selections (not placeholders)
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        has_valid_selection = (
            team and not self._is_placeholder_value(team, 'select_team') and
            machine and not self._is_placeholder_value(machine, 'select_machine') and
            repo and not self._is_placeholder_value(repo, 'select_repository')
        )
        
        if has_valid_selection:
            current_selection = (team, machine, repo)
            self.refresh_plugins()
            self.refresh_connections()
            # If we're on the file browser tab, reconnect immediately (but not during startup)
            if hasattr(self, 'file_browser') and not self.is_starting_up:
                # This will trigger auto-connect in the file browser
                self.file_browser.connect_if_needed()
            self.plugins_loaded_for = current_selection
        
        # Update Connect button state in file browser
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.update_connect_button_state()
        
        # Update menu states
        self.update_menu_states()
    
    def update_teams(self, teams: list):
        """Update team dropdowns"""
        self.team_combo['values'] = teams
        if teams:
            self.team_combo.set(teams[0])
            self.on_team_changed()
        else:
            self.team_combo.set(i18n.get('select_team'))
        self.update_activity_status()
    
    def load_machines(self):
        """Load machines for selected team"""
        team = self.team_combo.get()
        if not team or self._is_placeholder_value(team, 'select_team'):
            return
        
        self.activity_status_label.config(text=i18n.get('loading_machines', team=team))
        
        # Direct API call to get team machines
        response = self.api_client.token_request('GetTeamMachines', {'teamName': team})
        
        if response.get('error'):
            # Clear machine data on error
            self.machines_data = {}
            error_msg = response.get('error', i18n.get('failed_to_load_machines'))
            if not self._handle_api_error(error_msg):
                self.activity_status_label.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
        else:
            # Extract machines from resultSets - second table contains the actual data
            machines_data = []
            if response.get('resultSets') and len(response['resultSets']) > 1:
                machines_data = response['resultSets'][1].get('data', [])
            
            # Store full machine data with vault content
            self.machines_data = {m.get('machineName', ''): m for m in machines_data if m.get('machineName')}
            machines = [self._get_name(m, 'machineName', 'name') for m in machines_data]
            self.update_machines(machines)
    
    def update_machines(self, machines: list):
        """Update machine dropdown"""
        self.machine_combo['values'] = machines
        if machines:
            self.machine_combo.set(machines[0])
            self.load_repositories()
        else:
            # Set placeholder if no machines are available
            self.machine_combo.set(i18n.get('select_machine'))
            # Also clear repositories since no machine is selected
            self.update_repositories([])
        self.update_activity_status()
    
    def load_repositories(self):
        """Load repositories for selected team/machine"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        if not team or self._is_placeholder_value(team, 'select_team'):
            return
        
        self.activity_status_label.config(text=i18n.get('loading_repositories', team=team))
        
        # Direct API call to get team repositories
        response = self.api_client.token_request('GetTeamRepositories', {'teamName': team})
        
        if response.get('error'):
            error_msg = response.get('error', i18n.get('failed_to_load_repositories'))
            if not self._handle_api_error(error_msg):
                self.activity_status_label.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
        else:
            # Extract repositories from resultSets - second table contains the actual data
            all_repos = []
            if response.get('resultSets') and len(response['resultSets']) > 1:
                all_repos = response['resultSets'][1].get('data', [])
            
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
                                # In machine vaultStatus, the repository GUID is stored in the 'name' field
                                machine_repo_guids = []
                                for repo in result_data['repositories']:
                                    guid = repo.get('name')
                                    if guid:
                                        machine_repo_guids.append(guid)
                                        self.logger.debug(f"Found repository GUID in machine {machine}: {guid}")
                                
                                # Filter repositories to only those on this machine
                                filtered_repos = []
                                self.logger.debug(f"Filtering repositories for machine {machine}")
                                self.logger.debug(f"Machine repository GUIDs: {machine_repo_guids}")
                                
                                for repo in all_repos:
                                    repo_guid = repo.get('repoGuid') or repo.get('grandGuid')
                                    repo_name = self._get_name(repo, 'repositoryName', 'name', 'repoName')
                                    self.logger.debug(f"Checking repository '{repo_name}' with GUID: {repo_guid}")
                                    
                                    if repo_guid and repo_guid in machine_repo_guids:
                                        filtered_repos.append(repo)
                                        self.logger.debug(f"  -> Matched! Repository '{repo_name}' is on machine {machine}")
                                
                                # Use filtered list
                                if filtered_repos:
                                    repos = [self._get_name(r, 'repositoryName', 'name', 'repoName') for r in filtered_repos]
                                    self.update_repositories(repos)
                                    # Update status to show filtering is active
                                    self.repo_filter_label.config(text="(machine-specific)", fg=COLOR_SUCCESS)
                                    status_text = f"Showing {len(repos)} repositories for machine '{machine}'"
                                    self.activity_status_label.config(text=status_text, fg=COLOR_SUCCESS)
                                    self.root.after(3000, lambda: self.update_activity_status())
                                    return
                                else:
                                    self.logger.debug(f"No repositories matched for machine {machine}")
                                    # Fall through to show all repositories
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        # If parsing fails, fall back to showing all repos
                        self.logger.error(f"Failed to parse vaultStatus for machine {machine}: {e}")
                else:
                    self.logger.debug(f"Machine {machine} has no vaultStatus - showing all team repositories")
            
            # Fall back to showing all team repositories
            repos = [self._get_name(r, 'repositoryName', 'name', 'repoName') for r in all_repos]
            self.repo_filter_label.config(text="(all team repos)", fg='#666666')
            self.update_repositories(repos)
    
    def update_repositories(self, repos: list):
        """Update repository dropdown"""
        self.repo_combo['values'] = repos
        if repos:
            self.repo_combo.set(repos[0])
            # Trigger repository change event to load plugins
            self.on_repository_changed()
        else:
            self.repo_combo.set(i18n.get('select_repository'))
            # Clear the filter label when no repos
            self.repo_filter_label.config(text="")
            # Also trigger change event to clear plugins
            self.on_repository_changed()
        self.update_activity_status()
    
    def _launch_terminal(self, command: str, description: str):
        """Common method to launch terminal with given command"""
        import os
        # Go up 4 levels: main.py -> gui -> cli -> src -> cli (root)
        cli_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        rediacc_path = os.path.join(cli_dir, 'rediacc')
        simple_cmd = f'{rediacc_path} {command}'
        
        # Use terminal detector to find best method
        method = self.terminal_detector.detect()
        
        if not method:
            self.logger.error("No working terminal method detected")
            messagebox.showerror(i18n.get('error'), f"{i18n.get('could_not_launch')} - No terminal method available")
            return
        
        launch_func = self.terminal_detector.get_launch_function(method)
        if not launch_func:
            self.logger.warning(f"No launch function for method: {method}")
            messagebox.showerror(i18n.get('error'), i18n.get('could_not_launch'))
            return
        
        try:
            launch_func(cli_dir, command, description)
            self.activity_status_label.config(text=f"{i18n.get('launched_terminal')} ({method})")
        except Exception as e:
            self.logger.error(f"Failed to launch with {method}: {e}")
            messagebox.showerror(i18n.get('error'), i18n.get('could_not_launch'))
    
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
    
    # Plugin management methods
    def refresh_plugins(self):
        """Refresh available plugins for selected repository"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not all([team, machine, repo]):
            messagebox.showerror(i18n.get('error'), i18n.get('select_team_machine_repo'))
            return
        
        # Update the selection we're loading plugins for
        self.plugins_loaded_for = (team, machine, repo)
        
        self.activity_status_label.config(text=i18n.get('loading_plugins'))
        
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
            # Store available plugins
            self.available_plugins = plugins
            self.root.after(0, lambda: self.update_plugin_list(plugins))
            # Plugin menu removed - all functionality in toolbar
        
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
    
    def update_plugin_list(self, plugins: list):
        """Update available plugins list"""
        self.logger.debug(f"update_plugin_list called with {len(plugins)} plugins: {plugins}")
        
        # Plugins are now stored in self.available_plugins
        # The UI update is handled by update_plugin_toolbar
        
        # Update plugin toolbar if it exists
        if hasattr(self, 'plugin_toolbar_frame'):
            self.update_plugin_toolbar()
        
        status_msg = i18n.get('found_plugins', count=len(plugins))
        self.logger.debug(f"Setting status: '{status_msg}'")
        self.activity_status_label.config(text=status_msg)
    
    def refresh_connections(self):
        """Refresh active plugin connections"""
        self.activity_status_label.config(text=i18n.get('refreshing_connections'))
        
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
        """Update connections list - now only updates internal state"""
        # Update plugin connections dict
        self.plugin_connections = {}
        
        for conn in connections:
            # Only store active connections
            if conn['status'] == 'Active':
                url = f"http://localhost:{conn['port']}"
                self.plugin_connections[conn['plugin']] = {
                    'url': url,
                    'conn_id': conn['id']  # This is the actual 8-character connection ID
                }
        
        # Plugin menu removed - all updates handled by toolbar
        
        # Update toolbar button states if toolbar exists
        if hasattr(self, 'plugin_buttons'):
            for plugin_name in self.plugin_buttons:
                self.update_plugin_button_state(plugin_name)
        
        # Update plugin status label
        self.update_plugin_status_label()
        
        self.activity_status_label.config(text=i18n.get('found_connections', count=len(connections)))
    
    # Plugin tab methods removed - functionality moved to menu
    
    def connect_plugin(self):
        """Connect to selected plugin - deprecated, use connect_plugin_from_menu"""
        # This method is deprecated. Plugin connections are now handled via the menu
        pass
    
    def disconnect_plugin(self):
        """Disconnect selected plugin connection - deprecated, use disconnect_plugin_from_menu"""
        # This method is deprecated. Plugin disconnections are now handled via the menu
        pass
    
    def open_plugin_url(self):
        """Open plugin URL in browser - deprecated, functionality now in menu"""
        # This method is deprecated. URL opening is now handled via the menu
        pass
    
    def copy_plugin_url(self):
        """Copy plugin URL to clipboard - deprecated, functionality now in menu"""
        # This method is deprecated. URL copying is now handled via the menu
        pass
    
    def auto_refresh_connections(self):
        """Auto-refresh connections every 5 seconds"""
        # Safety check: ensure window still exists
        try:
            if not self.root.winfo_exists():
                return
        except:
            return
            
        # Always refresh connections to keep plugin menu updated
        # Check if we have a valid selection to refresh
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        has_valid_selection = (
            team and not self._is_placeholder_value(team, 'select_team') and
            machine and not self._is_placeholder_value(machine, 'select_machine') and
            repo and not self._is_placeholder_value(repo, 'select_repository')
        )
        
        if has_valid_selection:
            self.refresh_connections()
        
        # Schedule next refresh
        self.auto_refresh_timer_id = self.root.after(AUTO_REFRESH_INTERVAL, self.auto_refresh_connections)
    
    # Plugin menu helper methods
    def refresh_plugins_menu(self):
        """Refresh plugins - DEPRECATED, use refresh_plugins_toolbar"""
        self.refresh_plugins()
    
    def is_plugin_connected(self, plugin_name):
        """Check if a plugin is currently connected"""
        return plugin_name in self.plugin_connections
    
    def get_plugin_connection_info(self, plugin_name):
        """Get connection info for a plugin"""
        return self.plugin_connections.get(plugin_name)
    
    def update_plugin_toolbar(self):
        """Update the plugin toolbar with available plugins - now stable without recreating widgets"""
        current_plugins = set(self.available_plugins)
        existing_plugins = set(self.plugin_buttons.keys())
        
        # Update status label
        self.update_plugin_status_label()
        
        # Handle no plugins case
        if not current_plugins:
            # Remove all existing buttons
            for plugin_name in existing_plugins:
                # Clean up tooltip
                if plugin_name in self.plugin_tooltips:
                    old_tooltip = self.plugin_tooltips[plugin_name]
                    if hasattr(old_tooltip, 'tooltip') and old_tooltip.tooltip:
                        old_tooltip.tooltip.destroy()
                    del self.plugin_tooltips[plugin_name]
                
                # Clean up keyboard shortcuts
                if plugin_name in self.plugin_shortcuts:
                    for binding in self.plugin_shortcuts[plugin_name]:
                        try:
                            self.root.unbind_all(binding)
                        except:
                            pass
                    del self.plugin_shortcuts[plugin_name]
                
                # Destroy button
                self.plugin_buttons[plugin_name].destroy()
                del self.plugin_buttons[plugin_name]
            
            # Show no plugins message if not already shown
            if not hasattr(self, 'no_plugins_label') or not self.no_plugins_label.winfo_exists():
                self.no_plugins_label = tk.Label(self.plugin_buttons_frame, 
                                               text=i18n.get('no_plugins_available'),
                                               font=('Arial', 9), fg='gray')
                self.no_plugins_label.pack(side=tk.LEFT, padx=5)
            return
        
        # Remove no plugins label if it exists
        if hasattr(self, 'no_plugins_label') and self.no_plugins_label.winfo_exists():
            self.no_plugins_label.destroy()
        
        # Remove buttons for plugins that no longer exist
        for plugin_name in existing_plugins - current_plugins:
            # Clean up tooltip
            if plugin_name in self.plugin_tooltips:
                old_tooltip = self.plugin_tooltips[plugin_name]
                if hasattr(old_tooltip, 'tooltip') and old_tooltip.tooltip:
                    old_tooltip.tooltip.destroy()
                del self.plugin_tooltips[plugin_name]
            
            # Clean up keyboard shortcuts
            if plugin_name in self.plugin_shortcuts:
                for binding in self.plugin_shortcuts[plugin_name]:
                    try:
                        self.root.unbind_all(binding)
                    except:
                        pass
                del self.plugin_shortcuts[plugin_name]
            
            # Destroy button
            self.plugin_buttons[plugin_name].destroy()
            del self.plugin_buttons[plugin_name]
        
        # Add buttons for new plugins
        for i, plugin_name in enumerate(sorted(current_plugins)):
            if plugin_name not in existing_plugins:
                # Create plugin button
                btn = tk.Button(self.plugin_buttons_frame, 
                               text=plugin_name.capitalize(),
                               font=('Arial', 10),
                               relief=tk.RAISED,
                               bd=2,
                               padx=15,
                               pady=5,
                               cursor='hand2')
                btn.pack(side=tk.LEFT, padx=5)
                
                # Store button reference
                self.plugin_buttons[plugin_name] = btn
                
                # Bind click actions - now both show menu
                btn.bind('<Button-1>', lambda e, p=plugin_name: self.show_plugin_menu(e, p))
                btn.bind('<Button-3>', lambda e, p=plugin_name: self.show_plugin_menu(e, p))
                
                # Add keyboard shortcuts
                if i < 9:  # Only for first 9 plugins
                    # Track shortcuts for cleanup
                    shortcuts = []
                    
                    # Ctrl+1-9 for quick access
                    shortcut1 = f'<Control-Key-{i+1}>'
                    self.root.bind_all(shortcut1, lambda e, p=plugin_name: self.handle_plugin_shortcut(p))
                    shortcuts.append(shortcut1)
                    
                    # Ctrl+Shift+1-9 for disconnect
                    shortcut2 = f'<Control-Shift-Key-{i+1}>'
                    self.root.bind_all(shortcut2, lambda e, p=plugin_name: self.disconnect_plugin_shortcut(p))
                    shortcuts.append(shortcut2)
                    
                    self.plugin_shortcuts[plugin_name] = shortcuts
        
        # Update all button states
        for plugin_name in current_plugins:
            if plugin_name in self.plugin_buttons:
                self.update_plugin_button_state(plugin_name)
    
    def update_plugin_button_state(self, plugin_name):
        """Update the visual state of a plugin button"""
        if plugin_name not in self.plugin_buttons:
            return
            
        btn = self.plugin_buttons[plugin_name]
        
        # Clean up old tooltip if exists
        if plugin_name in self.plugin_tooltips:
            old_tooltip = self.plugin_tooltips[plugin_name]
            if hasattr(old_tooltip, 'tooltip') and old_tooltip.tooltip:
                old_tooltip.tooltip.destroy()
            # Unbind events from the old tooltip
            btn.unbind("<Enter>")
            btn.unbind("<Leave>")
            del self.plugin_tooltips[plugin_name]
        
        # Check if operation is in progress
        if plugin_name in self.active_operations:
            # Operation in progress - disabled state
            btn.config(state='disabled', bg='#CCCCCC', fg='#666666', text=f"⟳ {plugin_name.capitalize()}")
            self.plugin_tooltips[plugin_name] = create_tooltip(btn, i18n.get('operation_in_progress'))
            return
        
        # Enable button
        btn.config(state='normal')
        
        is_connected = self.is_plugin_connected(plugin_name)
        
        if is_connected:
            # Connected state - green
            btn.config(bg='#90EE90', fg='#006400', text=f"✓ {plugin_name.capitalize()}")
            conn_info = self.get_plugin_connection_info(plugin_name)
            if conn_info and 'url' in conn_info:
                # Build detailed tooltip
                tooltip_parts = [
                    i18n.get('enabled'),
                    f"URL: {conn_info['url']}",
                    f"Port: {conn_info.get('url', '').split(':')[-1] if ':' in conn_info.get('url', '') else 'N/A'}",
                    f"ID: {conn_info.get('conn_id', 'N/A')[:8]}",
                    "",
                    i18n.get('click_for_menu')
                ]
                self.plugin_tooltips[plugin_name] = create_tooltip(btn, '\n'.join(tooltip_parts))
        else:
            # Disconnected state - gray
            btn.config(bg='#F0F0F0', fg='#333333', text=plugin_name.capitalize())
            self.plugin_tooltips[plugin_name] = create_tooltip(btn, i18n.get('click_for_menu'))
    
    def show_plugin_menu(self, event, plugin_name):
        """Show plugin menu on button click"""
        # Check if operation is in progress
        if plugin_name in self.active_operations:
            return  # Don't show menu during operations
        
        # Show the context menu
        self.show_plugin_context_menu(event, plugin_name)
    
    def handle_plugin_shortcut(self, plugin_name):
        """Handle keyboard shortcut for plugin"""
        # Check if operation is in progress
        if plugin_name in self.active_operations:
            return
        
        # If connected, open URL; if not, connect
        if self.is_plugin_connected(plugin_name):
            conn_info = self.get_plugin_connection_info(plugin_name)
            if conn_info and 'url' in conn_info:
                webbrowser.open(conn_info['url'])
                self.activity_status_label.config(text=i18n.get('opened_in_browser', url=conn_info['url']))
        else:
            self.connect_plugin_from_toolbar(plugin_name)
    
    def _close_active_popup(self):
        """Close the currently active popup menu if any"""
        if self.active_popup_menu:
            try:
                self.active_popup_menu.unpost()
                self.active_popup_menu.destroy()
            except:
                pass  # Menu might already be destroyed
            self.active_popup_menu = None
    
    def _handle_global_click(self, event):
        """Handle global clicks to close popup menus"""
        # Check if we have an active popup menu
        if self.active_popup_menu:
            try:
                # Get the popup menu's position and size
                menu_x = self.active_popup_menu.winfo_x()
                menu_y = self.active_popup_menu.winfo_y()
                menu_width = self.active_popup_menu.winfo_width()
                menu_height = self.active_popup_menu.winfo_height()
                
                # Check if click is outside the menu
                if not (menu_x <= event.x_root <= menu_x + menu_width and
                        menu_y <= event.y_root <= menu_y + menu_height):
                    self._close_active_popup()
            except:
                # Menu might not be fully initialized or already destroyed
                self._close_active_popup()
    
    def show_plugin_context_menu(self, event, plugin_name):
        """Show context menu for plugin button"""
        # Close any existing popup menu
        self._close_active_popup()
        
        # Create new menu
        menu = tk.Menu(self.root, tearoff=0)
        self.active_popup_menu = menu
        
        is_connected = self.is_plugin_connected(plugin_name)
        
        if is_connected:
            conn_info = self.get_plugin_connection_info(plugin_name)
            menu.add_command(label=i18n.get('open_browser'),
                           command=lambda: webbrowser.open(conn_info['url']) if conn_info and 'url' in conn_info else None)
            menu.add_command(label=i18n.get('copy_url'),
                           command=lambda: self.copy_url_to_clipboard(conn_info['url']) if conn_info and 'url' in conn_info else None)
            menu.add_separator()
            menu.add_command(label=i18n.get('show_details'),
                           command=lambda: self.show_plugin_details(plugin_name, conn_info))
            menu.add_command(label=i18n.get('restart_plugin'),
                           command=lambda: self.restart_plugin(plugin_name))
            menu.add_command(label=i18n.get('view_logs'),
                           command=lambda: self.view_plugin_logs(plugin_name))
            menu.add_separator()
            menu.add_command(label=i18n.get('disable_plugin'),
                           command=lambda: self.disconnect_plugin_from_toolbar(plugin_name))
        else:
            menu.add_command(label=i18n.get('enable_plugin'),
                           command=lambda: self.connect_plugin_from_toolbar(plugin_name))
            menu.add_separator()
            menu.add_command(label=i18n.get('show_details'),
                           command=lambda: self.show_plugin_details(plugin_name, None))
        
        menu.add_separator()
        menu.add_command(label=i18n.get('refresh'),
                       command=self.refresh_plugins_toolbar)
        menu.add_command(label=i18n.get('refresh_all') + ' (Ctrl+0)',
                       command=self.refresh_all_plugins)
        
        # Show menu at cursor position
        menu.post(event.x_root, event.y_root)
    
    def lock_plugin_operation(self, plugin_name):
        """Lock plugin button during operation"""
        self.active_operations.add(plugin_name)
        self.update_plugin_button_state(plugin_name)
    
    def unlock_plugin_operation(self, plugin_name):
        """Unlock plugin button after operation"""
        self.active_operations.discard(plugin_name)
        self.update_plugin_button_state(plugin_name)
    
    def connect_plugin_from_toolbar(self, plugin_name):
        """Connect to a plugin from the toolbar"""
        # Lock the plugin during operation
        self.lock_plugin_operation(plugin_name)
        
        # Use existing connect method
        self.connect_plugin_from_menu(plugin_name)
    
    def disconnect_plugin_from_toolbar(self, plugin_name):
        """Disconnect a plugin from the toolbar"""
        conn_info = self.get_plugin_connection_info(plugin_name)
        if conn_info:
            # Lock the plugin during operation
            self.lock_plugin_operation(plugin_name)
            self.disconnect_plugin_from_menu(plugin_name, conn_info)
    
    def refresh_plugins_toolbar(self):
        """Refresh plugins from toolbar button"""
        # Store original button states for recovery
        original_states = {}
        for plugin_name, btn in self.plugin_buttons.items():
            original_states[plugin_name] = {
                'bg': btn.cget('bg'),
                'text': btn.cget('text'),
                'state': btn.cget('state')
            }
            # Show loading state
            btn.config(bg='#F0F0F0', text=f"⟳ {plugin_name.capitalize()}")
        
        # Set a timeout to recover button states if refresh fails
        def recover_button_states():
            try:
                if self.root.winfo_exists():
                    # Check if buttons are still in loading state
                    for plugin_name, btn in self.plugin_buttons.items():
                        if btn.winfo_exists() and "⟳" in btn.cget('text'):
                            # Restore original state
                            if plugin_name in original_states:
                                btn.config(**original_states[plugin_name])
                            else:
                                # Fallback to updating state normally
                                self.update_plugin_button_state(plugin_name)
            except:
                pass
        
        # Set recovery timeout (10 seconds)
        self.root.after(10000, recover_button_states)
        
        # Refresh plugins
        self.refresh_plugins()
        # The toolbar will be updated when plugins are loaded
    
    def connect_plugin_from_menu(self, plugin_name):
        """Connect to a plugin from the menu"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not all([team, machine, repo, plugin_name]):
            # Unlock if it was locked by connect_plugin_from_toolbar
            if plugin_name in self.active_operations:
                self.unlock_plugin_operation(plugin_name)
            return
        
        self.activity_status_label.config(text=i18n.get('enabling_plugin', plugin=plugin_name))
        
        def connect():
            # Build command
            cmd = ['plugin', 'connect', '--team', team, '--machine', machine, 
                   '--repo', repo, '--plugin', plugin_name]
            
            # Don't specify port, let it auto-assign
            
            result = self.runner.run_command(cmd)
            
            if result['success']:
                # Parse connection info from output
                output = result.get('output', '')
                # Look for "Local URL:" in output
                url = None
                for line in output.split('\n'):
                    if 'Local URL:' in line:
                        url = line.split('Local URL:')[1].strip()
                        break
                
                if url:
                    # Look for connection ID in output
                    conn_id = None
                    for line in output.split('\n'):
                        if 'Connection ID:' in line:
                            conn_id = line.split('Connection ID:')[1].strip()
                            break
                    
                    self.plugin_connections[plugin_name] = {
                        'url': url,
                        'conn_id': conn_id or f"{team}/{machine}/{repo}/{plugin_name}"
                    }
                
                # Safe UI update wrapper
                def safe_ui_update(func):
                    try:
                        if self.root.winfo_exists():
                            self.root.after(0, func)
                    except:
                        pass
                
                safe_ui_update(lambda: self.activity_status_label.config(
                    text=i18n.get('plugin_enabled', plugin=plugin_name)))
                # Plugin menu removed - toolbar updates automatically
                
                # Update toolbar button if it exists
                if hasattr(self, 'plugin_buttons') and plugin_name in self.plugin_buttons:
                    safe_ui_update(lambda p=plugin_name: self.update_plugin_button_state(p))
                
                # Refresh connections to get accurate status
                safe_ui_update(lambda: self.root.after(100, self.refresh_connections))
                
                # Unlock the plugin operation
                safe_ui_update(lambda: self.unlock_plugin_operation(plugin_name))
            else:
                error = result.get('error', i18n.get('connection_failed'))
                
                # Safe UI update wrapper
                def safe_ui_update(func):
                    try:
                        if self.root.winfo_exists():
                            self.root.after(0, func)
                    except:
                        pass
                
                safe_ui_update(lambda: messagebox.showerror(i18n.get('error'), error))
                safe_ui_update(lambda: self.activity_status_label.config(text=''))
                
                # Unlock the plugin operation on error
                safe_ui_update(lambda: self.unlock_plugin_operation(plugin_name))
        
        thread = threading.Thread(target=connect, daemon=True)
        thread.start()
    
    def disconnect_plugin_from_menu(self, plugin_name, conn_info):
        """Disconnect a plugin from the menu"""
        self.activity_status_label.config(text=i18n.get('disabling_plugin', plugin=plugin_name))
        
        def disconnect():
            # Use connection ID if available
            if 'conn_id' in conn_info:
                cmd = ['plugin', 'disconnect', '--connection-id', conn_info['conn_id']]
            else:
                # Fallback to disconnect by team/machine/repo/plugin
                team = self.team_combo.get()
                machine = self.machine_combo.get()
                repo = self.repo_combo.get()
                cmd = ['plugin', 'disconnect', '--team', team, '--machine', machine,
                       '--repo', repo, '--plugin', plugin_name]
            
            result = self.runner.run_command(cmd)
            
            # Safe UI update wrapper
            def safe_ui_update(func):
                try:
                    if self.root.winfo_exists():
                        self.root.after(0, func)
                except:
                    pass
            
            if result['success']:
                self.plugin_connections.pop(plugin_name, None)
                safe_ui_update(lambda: self.activity_status_label.config(
                    text=i18n.get('plugin_disabled', plugin=plugin_name)))
                # Plugin menu removed - toolbar updates automatically
                
                # Update toolbar button if it exists
                if hasattr(self, 'plugin_buttons') and plugin_name in self.plugin_buttons:
                    safe_ui_update(lambda p=plugin_name: self.update_plugin_button_state(p))
                
                # Refresh connections to update status
                safe_ui_update(lambda: self.root.after(100, self.refresh_connections))
                
                # Unlock the plugin operation
                safe_ui_update(lambda: self.unlock_plugin_operation(plugin_name))
            else:
                error = result.get('error', i18n.get('disconnect_failed'))
                safe_ui_update(lambda: messagebox.showerror(i18n.get('error'), error))
                
                # Unlock the plugin operation on error
                safe_ui_update(lambda: self.unlock_plugin_operation(plugin_name))
            
            safe_ui_update(lambda: self.activity_status_label.config(text=''))
        
        thread = threading.Thread(target=disconnect, daemon=True)
        thread.start()
    
    def disconnect_all_plugins(self):
        """Disconnect all active plugin connections"""
        if not self.plugin_connections:
            return True
        
        self.logger.info(f"Disconnecting {len(self.plugin_connections)} plugin connections...")
        
        # First, get all active connections from the plugin status
        try:
            cmd = ['plugin', 'status']
            result = self.runner.run_command(cmd, timeout=5)
            
            if result['success']:
                output = result.get('output', '')
                # Parse connection IDs from status output
                connection_ids = []
                for line in output.split('\n'):
                    # Look for lines with connection IDs (8-character hex)
                    parts = line.split()
                    if len(parts) > 0 and len(parts[0]) == 8 and all(c in '0123456789abcdef' for c in parts[0].lower()):
                        connection_ids.append(parts[0])
                
                # Disconnect each connection by ID
                for conn_id in connection_ids:
                    try:
                        disconnect_cmd = ['plugin', 'disconnect', '--connection-id', conn_id]
                        disconnect_result = self.runner.run_command(disconnect_cmd, timeout=5)
                        if disconnect_result['success']:
                            self.logger.info(f"Disconnected plugin connection: {conn_id}")
                        else:
                            self.logger.error(f"Failed to disconnect {conn_id}: {disconnect_result.get('error')}")
                    except Exception as e:
                        self.logger.error(f"Error disconnecting {conn_id}: {e}")
            
            # Also try to disconnect using our local tracking
            for plugin_name, conn_info in list(self.plugin_connections.items()):
                try:
                    if 'conn_id' in conn_info:
                        cmd = ['plugin', 'disconnect', '--connection-id', conn_info['conn_id']]
                        result = self.runner.run_command(cmd, timeout=5)
                        if result['success']:
                            self.logger.info(f"Disconnected plugin: {plugin_name}")
                except Exception as e:
                    self.logger.error(f"Error disconnecting plugin {plugin_name}: {e}")
            
            self.plugin_connections.clear()
            return True
            
        except Exception as e:
            self.logger.error(f"Error during plugin cleanup: {e}")
            return False
    
    def copy_url_to_clipboard(self, url):
        """Copy URL to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.activity_status_label.config(text=i18n.get('url_copied'), fg='green')
            
            # Safe delayed update
            def reset_color():
                try:
                    if self.root.winfo_exists():
                        self.activity_status_label.config(fg='black')
                except:
                    pass
            
            self.root.after(2000, reset_color)
        except Exception as e:
            self.logger.error(f"Error copying to clipboard: {e}")
    
    def show_plugin_details(self, plugin_name, conn_info):
        """Show detailed information about a plugin"""
        dialog = tk.Toplevel(self.root)
        dialog.title(i18n.get('plugin_details', plugin=plugin_name))
        dialog.geometry('400x300')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 400) // 2
        y = (dialog.winfo_screenheight() - 300) // 2
        dialog.geometry(f'400x300+{x}+{y}')
        
        # Create info frame
        info_frame = tk.Frame(dialog, padx=20, pady=20)
        info_frame.pack(fill='both', expand=True)
        
        # Plugin name
        tk.Label(info_frame, text=i18n.get('plugin_name'), 
                font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        tk.Label(info_frame, text=plugin_name.capitalize()).grid(row=0, column=1, sticky='w', pady=5)
        
        # Status
        is_connected = conn_info is not None
        status_text = i18n.get('connected') if is_connected else i18n.get('disconnected')
        status_color = 'green' if is_connected else 'red'
        tk.Label(info_frame, text=i18n.get('status'), 
                font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        tk.Label(info_frame, text=status_text, fg=status_color).grid(row=1, column=1, sticky='w', pady=5)
        
        if conn_info:
            # URL
            tk.Label(info_frame, text='URL:', 
                    font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
            tk.Label(info_frame, text=conn_info.get('url', 'N/A')).grid(row=2, column=1, sticky='w', pady=5)
            
            # Port
            port = conn_info.get('url', '').split(':')[-1] if ':' in conn_info.get('url', '') else 'N/A'
            tk.Label(info_frame, text=i18n.get('port'), 
                    font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
            tk.Label(info_frame, text=port).grid(row=3, column=1, sticky='w', pady=5)
            
            # Connection ID
            tk.Label(info_frame, text=i18n.get('connection_id'), 
                    font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=5)
            tk.Label(info_frame, text=conn_info.get('conn_id', 'N/A')).grid(row=4, column=1, sticky='w', pady=5)
        
        # Repository info
        tk.Label(info_frame, text=i18n.get('repository'), 
                font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='w', pady=5)
        tk.Label(info_frame, text=self.repo_combo.get()).grid(row=5, column=1, sticky='w', pady=5)
        
        # Machine
        tk.Label(info_frame, text=i18n.get('machine'), 
                font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky='w', pady=5)
        tk.Label(info_frame, text=self.machine_combo.get()).grid(row=6, column=1, sticky='w', pady=5)
        
        # Close button
        tk.Button(dialog, text=i18n.get('close'), 
                 command=dialog.destroy).pack(pady=10)
    
    def restart_plugin(self, plugin_name):
        """Restart a plugin by disconnecting and reconnecting"""
        self.activity_status_label.config(text=i18n.get('restarting_plugin', plugin=plugin_name))
        
        # Lock the plugin operation
        self.lock_plugin_operation(plugin_name)
        
        # First disconnect if connected
        conn_info = self.get_plugin_connection_info(plugin_name)
        if conn_info:
            # Use a flag to indicate this is a restart operation
            def restart_sequence():
                # Disconnect without locking (we already locked)
                team = self.team_combo.get()
                machine = self.machine_combo.get()
                repo = self.repo_combo.get()
                
                # Build disconnect command
                if 'conn_id' in conn_info:
                    cmd = ['plugin', 'disconnect', '--connection-id', conn_info['conn_id']]
                else:
                    cmd = ['plugin', 'disconnect', '--team', team, '--machine', machine,
                           '--repo', repo, '--plugin', plugin_name]
                
                result = self.runner.run_command(cmd)
                
                # Safe UI update wrapper
                def safe_ui_update(func):
                    try:
                        if self.root.winfo_exists():
                            self.root.after(0, func)
                    except:
                        pass
                
                if result['success']:
                    self.plugin_connections.pop(plugin_name, None)
                    # Update button state
                    if hasattr(self, 'plugin_buttons') and plugin_name in self.plugin_buttons:
                        safe_ui_update(lambda p=plugin_name: self.update_plugin_button_state(p))
                    
                    # Wait a bit then reconnect
                    safe_ui_update(lambda: self.root.after(1000, lambda: self.connect_plugin_from_menu(plugin_name)))
                else:
                    # Unlock on error
                    safe_ui_update(lambda: self.unlock_plugin_operation(plugin_name))
                    error = result.get('error', i18n.get('disconnect_failed'))
                    safe_ui_update(lambda: messagebox.showerror(i18n.get('error'), error))
            
            # Run restart sequence in thread
            thread = threading.Thread(target=restart_sequence, daemon=True)
            thread.start()
        else:
            # Just connect if not connected
            self.connect_plugin_from_menu(plugin_name)
    
    def view_plugin_logs(self, plugin_name):
        """View plugin container logs"""
        messagebox.showinfo(i18n.get('feature_not_available'), 
                           i18n.get('plugin_logs_not_implemented'))
    
    def refresh_all_plugins(self):
        """Refresh all plugins and connections"""
        self.refresh_plugins()
        self.refresh_connections()
    
    def disconnect_plugin_shortcut(self, plugin_name):
        """Disconnect a plugin via keyboard shortcut"""
        if self.is_plugin_connected(plugin_name):
            conn_info = self.get_plugin_connection_info(plugin_name)
            if conn_info:
                self.disconnect_plugin_from_toolbar(plugin_name)
    
    # Menu action methods
    def show_preferences(self):
        """Show preferences dialog (transfer options)"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.show_transfer_options()
    
    def new_session(self):
        """Launch a new GUI session in a separate window"""
        import subprocess
        import sys
        import os
        
        # Get the path to the current script
        script_path = os.path.abspath(__file__)
        
        # Launch a new instance of the GUI
        subprocess.Popen([sys.executable, script_path])
    
    def change_language(self, language_code):
        """Change the application language"""
        self.logger.debug(f"Changing language to: {language_code}")
        i18n.set_language(language_code)
        # Note: update_all_texts will be called automatically via the observer pattern
    
    def cut_selected(self):
        """Cut selected files in file browser"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.cut_selected()
    
    def copy_selected(self):
        """Copy selected files in file browser"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.copy_selected()
    
    def paste_files(self):
        """Paste files in file browser"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.paste_files()
    
    def select_all(self):
        """Select all files in file browser"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.select_all()
    
    def focus_search(self):
        """Focus search field in file browser"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.focus_search()
    
    def clear_search(self):
        """Clear search filter in file browser"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.clear_search()
    
    def toggle_preview(self):
        """Toggle file preview pane"""
        # TODO: Implement preview functionality
        self.preview_var.set(not self.preview_var.get())
        messagebox.showinfo(i18n.get('info'), i18n.get('not_implemented'))
    
    def set_view_mode(self, mode):
        """Set view mode (local, remote, split)"""
        # TODO: Implement view mode switching
        messagebox.showinfo(i18n.get('info'), f"View mode: {mode} - {i18n.get('not_implemented')}")
    
    def refresh_local(self):
        """Refresh local file list"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.refresh_local()
    
    def refresh_remote(self):
        """Refresh remote file list"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.refresh_remote()
    
    def refresh_all(self):
        """Refresh both local and remote file lists"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.refresh_all()
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        current_state = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current_state)
        self.fullscreen_var.set(not current_state)
    
    def show_quick_command(self):
        """Show quick command dialog"""
        messagebox.showinfo(i18n.get('info'), i18n.get('not_implemented'))
    
    def switch_to_plugin_tab(self):
        """Switch to Plugin Manager tab - deprecated, now using menu"""
        # Plugin Manager is now in the Tools > Plugins menu
        pass
    
    def show_transfer_options_wrapper(self):
        """Show transfer options dialog"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.show_transfer_options()
    
    def show_console(self):
        """Show debug console window"""
        console_window = tk.Toplevel(self.root)
        console_window.title(i18n.get('console'))
        center_window(console_window, 800, 600)
        
        # Add a text widget for future console implementation
        text = tk.Text(console_window, bg='black', fg='white', font=('Consolas', 10))
        text.pack(fill='both', expand=True)
        text.insert('1.0', 'Debug console - Not implemented\n')
    
    def connect(self):
        """Connect action (placeholder)"""
        messagebox.showinfo(i18n.get('info'), i18n.get('not_implemented'))
    
    def disconnect(self):
        """Disconnect action (placeholder)"""
        messagebox.showinfo(i18n.get('info'), i18n.get('not_implemented'))
    
    
    def show_documentation(self):
        """Open documentation in web browser"""
        webbrowser.open('https://www.rediacc.com/docs')
    
    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(i18n.get('keyboard_shortcuts'))
        dialog.transient(self.root)
        center_window(dialog, 600, 500)
        
        # Create scrollable frame
        scroll_frame = tk.Frame(dialog)
        scroll_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(scroll_frame)
        scrollbar.pack(side='right', fill='y')
        
        text = tk.Text(scroll_frame, yscrollcommand=scrollbar.set, wrap='word')
        text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=text.yview)
        
        # Add shortcuts
        shortcuts = [
            ('File Menu:', ''),
            ('Ctrl+N', 'New Session'),
            ('Ctrl+,', 'Preferences'),
            ('Ctrl+Q', 'Exit'),
            ('', ''),
            ('Edit Menu:', ''),
            ('Ctrl+X', 'Cut'),
            ('Ctrl+C', 'Copy'),
            ('Ctrl+V', 'Paste'),
            ('Ctrl+A', 'Select All'),
            ('Ctrl+F', 'Find'),
            ('Escape', 'Clear Filter'),
            ('', ''),
            ('View Menu:', ''),
            ('F3', 'Show Preview'),
            ('F5', 'Refresh Local'),
            ('Shift+F5', 'Refresh Remote'),
            ('Ctrl+R', 'Refresh All'),
            ('F11', 'Full Screen'),
            ('', ''),
            ('Tools Menu:', ''),
            ('Ctrl+T', 'Repository Terminal'),
            ('Ctrl+S', 'File Sync'),
            ('F12', 'Console'),
            ('', ''),
            ('Connection Menu:', ''),
            ('Ctrl+Shift+C', 'Connect'),
            ('Ctrl+Shift+D', 'Disconnect'),
            ('', ''),
            ('Help Menu:', ''),
            ('F1', 'Documentation')
        ]
        
        for shortcut, description in shortcuts:
            if shortcut:
                text.insert('end', f'{shortcut:<20}{description}\n')
            else:
                text.insert('end', '\n')
        
        text.config(state='disabled')
    
    def check_for_updates(self):
        """Check for application updates"""
        messagebox.showinfo(i18n.get('check_updates'), 
                           i18n.get('no_updates'))
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""Rediacc CLI

Version: 1.0.0

© 2024 Rediacc

{i18n.get('about_description')}"""
        
        messagebox.showinfo(i18n.get('about'), about_text)
    
    def logout(self):
        """Logout and return to login screen"""
        if messagebox.askyesno(i18n.get('logout'), i18n.get('logout_confirm')):
            # Unregister observer before closing
            i18n.unregister_observer(self.update_all_texts)
            TokenManager.clear_token()
            self.root.destroy()
            launch_gui()
    
    def update_all_texts(self):
        """Update all texts when language changes"""
        self.logger.debug(f"update_all_texts called - current language: {i18n.current_language}")
        
        # Log a sample translation to verify it's working
        test_key = 'file'
        test_value = i18n.get(test_key)
        self.logger.debug(f"Test translation - key: '{test_key}', value: '{test_value}'")
        
        # Update window title
        new_title = i18n.get('app_title')
        if __version__ != 'dev':
            new_title += f' v{__version__}'
        self.logger.debug(f"Setting window title to: '{new_title}'")
        self.root.title(new_title)
        
        # Update user status in status bar
        auth_info = TokenManager.get_auth_info()
        self.user_status_label.config(text=f"{i18n.get('user')}: {auth_info.get('email', 'Unknown')}")
        
        # Update menu bar
        self.populate_language_menu()  # Update language submenu checkmarks
        self.update_menu_texts()
        
        # Update resource selection placeholders
        self._update_combo_placeholder(self.team_combo, 'select_team')
        self._update_combo_placeholder(self.machine_combo, 'select_machine')
        self._update_combo_placeholder(self.repo_combo, 'select_repository')
        
        # Update labels
        self.team_label.config(text=i18n.get('team'))
        self.machine_label.config(text=i18n.get('machine'))
        self.repo_label.config(text=i18n.get('repository'))
        
        # Update Connect button text in file browser
        if hasattr(self, 'file_browser') and hasattr(self.file_browser, 'connect_button'):
            if self.file_browser.ssh_connection:
                self.file_browser.connect_button.config(text=i18n.get('disconnect'))
            else:
                self.file_browser.connect_button.config(text=i18n.get('connect'))
        
        
        # Update status bar
        current_text = self.activity_status_label.cget('text')
        if current_text in ['Ready', 'جاهز', 'Bereit']:
            self.update_activity_status()
        
        # Update each tab's contents
        self.update_file_browser_tab_texts()
    
    def update_menu_texts(self):
        """Update all menu item texts"""
        self.logger.debug("Updating menu texts - recreating entire menu bar")
        
        # Store current state of boolean vars before recreating menus
        preview_state = self.preview_var.get() if hasattr(self, 'preview_var') else False
        fullscreen_state = self.fullscreen_var.get() if hasattr(self, 'fullscreen_var') else False
        
        # Completely remove the old menu bar
        self.root.config(menu=None)
        
        # Destroy the old menu bar to ensure complete cleanup
        if hasattr(self, 'menubar'):
            try:
                self.menubar.destroy()
            except:
                pass
        
        # Recreate the entire menu bar from scratch
        self.create_menu_bar()
        
        # Restore boolean var states
        if hasattr(self, 'preview_var'):
            self.preview_var.set(preview_state)
        if hasattr(self, 'fullscreen_var'):
            self.fullscreen_var.set(fullscreen_state)
        
        # Force complete GUI update
        self.root.update_idletasks()
        self.root.update()
    
    def update_menu_states(self):
        """Update menu item states based on current application state"""
        # Check if we have a valid selection
        has_team = bool(self.team_combo.get())
        has_machine = bool(self.machine_combo.get())
        has_repo = bool(self.repo_combo.get())
        has_full_selection = has_team and has_machine and has_repo
        
        # Update Edit menu states
        file_browser_active = hasattr(self, 'file_browser') and self.file_browser
        
        self.edit_menu.entryconfig(0, state='normal' if file_browser_active else 'disabled')  # Cut
        self.edit_menu.entryconfig(1, state='normal' if file_browser_active else 'disabled')  # Copy
        self.edit_menu.entryconfig(2, state='normal' if file_browser_active else 'disabled')  # Paste
        self.edit_menu.entryconfig(3, state='normal' if file_browser_active else 'disabled')  # Select All
        self.edit_menu.entryconfig(5, state='normal' if file_browser_active else 'disabled')  # Find
        self.edit_menu.entryconfig(6, state='normal' if file_browser_active else 'disabled')  # Clear Filter
        
        # Update View menu states
        self.view_menu.entryconfig(0, state='normal' if file_browser_active else 'disabled')  # Show Preview
        self.view_menu.entryconfig(2, state='normal' if file_browser_active else 'disabled')  # Local Files Only
        self.view_menu.entryconfig(3, state='normal' if file_browser_active else 'disabled')  # Remote Files Only
        self.view_menu.entryconfig(4, state='normal' if file_browser_active else 'disabled')  # Split View
        self.view_menu.entryconfig(6, state='normal' if file_browser_active else 'disabled')  # Refresh Local
        self.view_menu.entryconfig(7, state='normal' if file_browser_active else 'disabled')  # Refresh Remote
        self.view_menu.entryconfig(8, state='normal' if file_browser_active else 'disabled')  # Refresh All
        
        # Update Tools menu states
        terminal_submenu = self.tools_menu.nametowidget(self.tools_menu.entryconfig(0, 'menu')[-1])
        terminal_submenu.entryconfig(0, state='normal' if has_full_selection else 'disabled')  # Repository Terminal
        terminal_submenu.entryconfig(1, state='normal' if has_machine else 'disabled')  # Machine Terminal
        
        # Update Connection menu states
        # TODO: Implement connection state tracking
        self.connection_menu.entryconfig(0, state='disabled')  # Connect - will be enabled when disconnected
        self.connection_menu.entryconfig(1, state='disabled')  # Disconnect - will be enabled when connected
        
        # Update recent connections
        self.update_recent_connections()
        
        # Plugin menu removed - toolbar handles all plugin UI
    
    def update_recent_connections(self):
        """Update the recent connections list in the Connection menu"""
        # Remove old recent connection items
        try:
            menu_length = self.connection_menu.index(tk.END)
            # Delete items after the separator
            for i in range(self.recent_connections_start_index, menu_length):
                try:
                    self.connection_menu.delete(self.recent_connections_start_index)
                except:
                    break
        except:
            pass
        
        # TODO: Get actual recent connections from storage
        # For now, just show placeholder
        recent_connections = []  # This should be loaded from persistent storage
        
        if recent_connections:
            for i, conn in enumerate(recent_connections[:5]):  # Show last 5 connections
                self.connection_menu.insert(
                    self.recent_connections_start_index + i,
                    'command',
                    label=conn,
                    command=lambda c=conn: self.connect_to_recent(c)
                )
        else:
            # Show "No recent connections" as disabled item
            self.connection_menu.insert(
                self.recent_connections_start_index,
                'command',
                label=i18n.get('no_recent_connections'),
                state='disabled'
            )
    
    def connect_to_recent(self, connection_string):
        """Connect to a recent connection"""
        # Parse connection string (format: "Team/Machine/Repo")
        parts = connection_string.split('/')
        if len(parts) == 3:
            team, machine, repo = parts
            self.team_combo.set(team)
            self.on_team_changed()
            self.machine_combo.set(machine)
            self.on_machine_changed()
            self.repo_combo.set(repo)
            self.on_repository_changed()
    
    # Plugin tab texts update method removed - plugin manager is now in Tools menu
    # def update_plugin_tab_texts(self):
    #     pass
    
    
    def update_file_browser_tab_texts(self):
        """Update all texts in file browser tab"""
        if hasattr(self, 'file_browser'):
            self.file_browser.update_texts()
    
    def on_closing(self):
        """Override base class on_closing to perform cleanup"""
        self.logger.info("Application closing, performing cleanup...")
        
        # Check if there are active plugin connections
        if self.plugin_connections:
            # Build list of active connections
            active_list = []
            for plugin_name, conn_info in self.plugin_connections.items():
                if 'url' in conn_info:
                    active_list.append(f"• {plugin_name} ({conn_info['url']})")
                else:
                    active_list.append(f"• {plugin_name}")
            
            active_connections_str = '\n'.join(active_list[:5])  # Show first 5
            if len(active_list) > 5:
                active_connections_str += f"\n... and {len(active_list) - 5} more"
            
            message = i18n.get('active_plugins_warning',
                                 count=len(self.plugin_connections),
                                 connections=active_connections_str
                             )
            
            response = messagebox.askyesnocancel(
                i18n.get('confirm_exit'),
                message,
                icon='warning'
            )
            
            if response is None:  # Cancel
                return
            elif response:  # Yes - disconnect and exit
                # Show progress dialog
                progress_window = tk.Toplevel(self.root)
                progress_window.title(i18n.get('closing'))
                progress_window.geometry('300x100')
                progress_window.transient(self.root)
                progress_window.grab_set()
                
                # Center the progress window
                progress_window.update_idletasks()
                x = (progress_window.winfo_screenwidth() - 300) // 2
                y = (progress_window.winfo_screenheight() - 100) // 2
                progress_window.geometry(f'300x100+{x}+{y}')
                
                ttk.Label(progress_window, 
                         text=i18n.get('disconnecting_plugins'),
                         font=('TkDefaultFont', 10)).pack(pady=20)
                progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
                progress_bar.pack(pady=10, padx=20, fill='x')
                progress_bar.start()
                
                self.root.update()
                
                # Disconnect all plugins
                self.disconnect_all_plugins()
                
                progress_window.destroy()
        
        # Disconnect file browser SSH connection
        if hasattr(self, 'file_browser') and self.file_browser:
            self.logger.info("Disconnecting file browser SSH connection...")
            self.file_browser.disconnect()
        
        # Cancel any background operations
        self.logger.info("Canceling background operations...")
        # The threads are daemon threads, so they'll be terminated automatically
        
        # Cancel timers
        if self.session_timer_id:
            self.root.after_cancel(self.session_timer_id)
            self.session_timer_id = None
            self.logger.debug("Canceled session timer")
        
        if self.auto_refresh_timer_id:
            self.root.after_cancel(self.auto_refresh_timer_id)
            self.auto_refresh_timer_id = None
            self.logger.debug("Canceled auto-refresh timer")
            
        if self.activity_animation_id:
            self.root.after_cancel(self.activity_animation_id)
            self.activity_animation_id = None
            self.logger.debug("Canceled activity animation timer")
        
        self.logger.info("Cleanup complete, exiting application")
        
        # Call parent class on_closing
        super().on_closing()


# ===== MAIN EXECUTION =====

def launch_gui():
    """Launch the simplified GUI application"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Rediacc CLI GUI Application')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    args = parser.parse_args()
    
    # Check for verbose flag from either command line or environment
    verbose = args.verbose or os.environ.get('REDIACC_VERBOSE', '').lower() in ('1', 'true', 'yes')
    
    # Set up logging before creating any logger instances
    setup_logging(verbose=verbose)
    
    # Now create logger after logging is configured
    logger = get_logger(__name__)
    logger.info("Starting Rediacc CLI GUI...")
    logger.debug(f"Verbose logging enabled: {verbose}")
    
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
    
    # Variable to track the main window instance
    main_window_instance = None
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal. Closing GUI...")
        try:
            # If we have a main window instance, call its on_closing method
            if main_window_instance and hasattr(main_window_instance, 'on_closing'):
                main_window_instance.on_closing()
            else:
                # Fallback to basic cleanup
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
            main_window_instance = MainWindow()
            main_window_instance.root.mainloop()
        else:
            logger.debug("No valid token, showing login window...")
            def on_login_success():
                logger.debug("Login successful, closing login window...")
                login_window.root.quit()  # Stop the login window's mainloop
            
            login_window = LoginWindow(on_login_success)
            # Make the main loop check for interrupts periodically
            def check_interrupt():
                try:
                    login_window.root.after(100, check_interrupt)
                except:
                    pass
            check_interrupt()
            login_window.root.mainloop()
            
            # After login window closes, destroy it and create main window
            logger.debug("Login window closed, launching main window...")
            login_window.root.destroy()
            main_window_instance = MainWindow()
            main_window_instance.root.mainloop()
    except Exception as e:
        logger.error(f"Critical error in main execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    launch_gui()