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
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Tuple
import time
import datetime

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
        
        # Transfer tracking
        self.active_transfers = {}
        self.transfer_speed = 0
        self.transfer_start_time = None
        self.bytes_transferred = 0
        
        # Register for language changes
        i18n.register_observer(self.update_all_texts)
        
        # Create menu bar
        self.create_menu_bar()
        
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
        
        # Initial menu state update
        self.update_menu_states()
    
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
        self.menubar.add_cascade(label=i18n.get('file', 'File'), menu=self.file_menu, underline=0)
        
        # Edit Menu
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('edit', 'Edit'), menu=self.edit_menu, underline=0)
        
        # View Menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('view', 'View'), menu=self.view_menu, underline=0)
        
        # Tools Menu
        self.tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('tools', 'Tools'), menu=self.tools_menu, underline=0)
        
        # Connection Menu
        self.connection_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('connection', 'Connection'), menu=self.connection_menu, underline=0)
        
        # Help Menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=i18n.get('help', 'Help'), menu=self.help_menu, underline=0)
        
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
            label=i18n.get('new_session', 'New Session'),
            accelerator='Ctrl+N',
            command=lambda: messagebox.showinfo(i18n.get('info', 'Info'), i18n.get('not_implemented', 'Not implemented'))
        )
        
        self.file_menu.add_separator()
        
        # Preferences
        self.file_menu.add_command(
            label=i18n.get('preferences', 'Preferences'),
            accelerator='Ctrl+,',
            command=self.show_preferences
        )
        
        # Language submenu
        self.language_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label=i18n.get('language', 'Language'), menu=self.language_menu)
        self.populate_language_menu()
        
        self.file_menu.add_separator()
        
        # Logout
        self.file_menu.add_command(
            label=i18n.get('logout', 'Logout'),
            command=self.logout
        )
        
        # Exit
        self.file_menu.add_command(
            label=i18n.get('exit', 'Exit'),
            accelerator='Ctrl+Q',
            command=self.on_closing
        )
        
        # Bind accelerators
        self.root.bind_all('<Control-n>', lambda e: messagebox.showinfo(i18n.get('info', 'Info'), i18n.get('not_implemented', 'Not implemented')))
        self.root.bind_all('<Control-comma>', lambda e: self.show_preferences())
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
            label=i18n.get('cut', 'Cut'),
            accelerator='Ctrl+X',
            command=self.cut_selected
        )
        
        # Copy
        self.edit_menu.add_command(
            label=i18n.get('copy', 'Copy'),
            accelerator='Ctrl+C',
            command=self.copy_selected
        )
        
        # Paste
        self.edit_menu.add_command(
            label=i18n.get('paste', 'Paste'),
            accelerator='Ctrl+V',
            command=self.paste_files
        )
        
        # Select All
        self.edit_menu.add_command(
            label=i18n.get('select_all', 'Select All'),
            accelerator='Ctrl+A',
            command=self.select_all
        )
        
        self.edit_menu.add_separator()
        
        # Find
        self.edit_menu.add_command(
            label=i18n.get('find', 'Find...'),
            accelerator='Ctrl+F',
            command=self.focus_search
        )
        
        # Clear Filter
        self.edit_menu.add_command(
            label=i18n.get('clear_filter', 'Clear Filter'),
            accelerator='Escape',
            command=self.clear_search
        )
    
    def populate_view_menu(self):
        """Populate the View menu"""
        # Clear existing menu items
        self.view_menu.delete(0, tk.END)
        
        # Show Preview
        self.view_menu.add_checkbutton(
            label=i18n.get('show_preview', 'Show Preview'),
            accelerator='F3',
            variable=self.preview_var,
            command=self.toggle_preview
        )
        
        self.view_menu.add_separator()
        
        # View modes
        self.view_mode_var = tk.StringVar(value='split')
        
        self.view_menu.add_radiobutton(
            label=i18n.get('local_files_only', 'Local Files Only'),
            variable=self.view_mode_var,
            value='local',
            command=lambda: self.set_view_mode('local')
        )
        
        self.view_menu.add_radiobutton(
            label=i18n.get('remote_files_only', 'Remote Files Only'),
            variable=self.view_mode_var,
            value='remote',
            command=lambda: self.set_view_mode('remote')
        )
        
        self.view_menu.add_radiobutton(
            label=i18n.get('split_view', 'Split View'),
            variable=self.view_mode_var,
            value='split',
            command=lambda: self.set_view_mode('split')
        )
        
        self.view_menu.add_separator()
        
        # Refresh commands
        self.view_menu.add_command(
            label=i18n.get('refresh_local', 'Refresh Local'),
            accelerator='F5',
            command=self.refresh_local
        )
        
        self.view_menu.add_command(
            label=i18n.get('refresh_remote', 'Refresh Remote'),
            accelerator='Shift+F5',
            command=self.refresh_remote
        )
        
        self.view_menu.add_command(
            label=i18n.get('refresh_all', 'Refresh All'),
            accelerator='Ctrl+R',
            command=self.refresh_all
        )
        
        self.view_menu.add_separator()
        
        # Full Screen
        self.view_menu.add_checkbutton(
            label=i18n.get('full_screen', 'Full Screen'),
            accelerator='F11',
            variable=self.fullscreen_var,
            command=self.toggle_fullscreen
        )
        
        # Bind accelerators
        self.root.bind_all('<F3>', lambda e: self.toggle_preview())
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
            label=i18n.get('terminal', 'Terminal'),
            menu=terminal_menu
        )
        
        terminal_menu.add_command(
            label=i18n.get('repository_terminal', 'Repository Terminal'),
            command=self.open_repo_terminal
        )
        
        terminal_menu.add_command(
            label=i18n.get('machine_terminal', 'Machine Terminal'),
            command=self.open_machine_terminal
        )
        
        terminal_menu.add_command(
            label=i18n.get('quick_command', 'Quick Command...'),
            command=self.show_quick_command
        )
        
        # Plugin Manager
        self.tools_menu.add_command(
            label=i18n.get('plugin_manager', 'Plugin Manager'),
            accelerator='Ctrl+P',
            command=self.switch_to_plugin_tab
        )
        
        # File Sync
        self.tools_menu.add_command(
            label=i18n.get('file_sync', 'File Sync'),
            accelerator='Ctrl+S',
            command=self.switch_to_sync_tab
        )
        
        self.tools_menu.add_separator()
        
        # Transfer Options
        self.tools_menu.add_command(
            label=i18n.get('transfer_options', 'Transfer Options...'),
            command=self.show_transfer_options_wrapper
        )
        
        # Console
        self.tools_menu.add_command(
            label=i18n.get('console', 'Console'),
            accelerator='F12',
            command=self.show_console
        )
        
        # Bind accelerators
        self.root.bind_all('<Control-t>', lambda e: self.open_repo_terminal())
        self.root.bind_all('<Control-p>', lambda e: self.switch_to_plugin_tab())
        self.root.bind_all('<Control-s>', lambda e: self.switch_to_sync_tab())
        self.root.bind_all('<F12>', lambda e: self.show_console())
    
    def populate_connection_menu(self):
        """Populate the Connection menu"""
        # Clear existing menu items
        self.connection_menu.delete(0, tk.END)
        
        # Connect
        self.connection_menu.add_command(
            label=i18n.get('connect', 'Connect'),
            accelerator='Ctrl+Shift+C',
            command=self.connect,
            state='disabled'  # Will be managed by update_menu_states
        )
        
        # Disconnect
        self.connection_menu.add_command(
            label=i18n.get('disconnect', 'Disconnect'),
            accelerator='Ctrl+Shift+D',
            command=self.disconnect,
            state='disabled'  # Will be managed by update_menu_states
        )
        
        self.connection_menu.add_separator()
        
        # Recent Connections label
        self.connection_menu.add_command(
            label=i18n.get('recent_connections', 'Recent Connections:'),
            state='disabled'
        )
        
        # Recent connections will be added dynamically
        self.recent_connections_start_index = self.connection_menu.index(tk.END) + 1
        
        self.connection_menu.add_separator()
        
        # Manage Bookmarks
        self.connection_menu.add_command(
            label=i18n.get('manage_bookmarks', 'Manage Bookmarks...'),
            command=self.show_bookmarks_dialog
        )
        
        # Bookmark Current
        self.connection_menu.add_command(
            label=i18n.get('bookmark_current', 'Bookmark Current'),
            accelerator='Ctrl+B',
            command=self.bookmark_current
        )
        
        # Bind accelerators
        self.root.bind_all('<Control-Shift-C>', lambda e: self.connect())
        self.root.bind_all('<Control-Shift-D>', lambda e: self.disconnect())
        self.root.bind_all('<Control-b>', lambda e: self.bookmark_current())
    
    def populate_help_menu(self):
        """Populate the Help menu"""
        # Clear existing menu items
        self.help_menu.delete(0, tk.END)
        
        # Documentation
        self.help_menu.add_command(
            label=i18n.get('documentation', 'Documentation'),
            accelerator='F1',
            command=self.show_documentation
        )
        
        # Keyboard Shortcuts
        self.help_menu.add_command(
            label=i18n.get('keyboard_shortcuts', 'Keyboard Shortcuts'),
            command=self.show_keyboard_shortcuts
        )
        
        self.help_menu.add_separator()
        
        # Check for Updates
        self.help_menu.add_command(
            label=i18n.get('check_updates', 'Check for Updates...'),
            command=self.check_for_updates
        )
        
        # About
        self.help_menu.add_command(
            label=i18n.get('about', 'About Rediacc CLI'),
            command=self.show_about
        )
        
        # Bind accelerators
        self.root.bind_all('<F1>', lambda e: self.show_documentation())
    
    def create_widgets(self):
        """Create main window widgets"""
        # Create a clean toolbar frame - no more user info here
        toolbar_frame = tk.Frame(self.root)
        toolbar_frame.pack(fill='x', padx=5, pady=5)
        
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
        
        # Enhanced multi-section status bar - create BEFORE tabs
        self.create_status_bar()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Plugin Manager tab (first)
        self.plugin_frame = tk.Frame(self.notebook)
        self.notebook.add(self.plugin_frame, text=i18n.get('plugin_manager'))
        self.create_plugin_tab()
        
        # File Sync tab (second)
        self.sync_frame = tk.Frame(self.notebook)
        self.notebook.add(self.sync_frame, text=i18n.get('file_sync'))
        self.create_sync_tab()
        
        # File Browser tab (third)
        self.browser_frame = tk.Frame(self.notebook)
        self.notebook.add(self.browser_frame, text=i18n.get('file_browser', 'File Browser'))
        self.create_file_browser_tab()
    
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
        self.sync_options_frame = tk.LabelFrame(self.options_frame, text=i18n.get('sync_options', 'Sync Options'))
        self.sync_options_frame.pack(fill='x', padx=10, pady=5)
        
        # Use grid for sync options
        self.mirror_var = tk.BooleanVar()
        self.mirror_check = tk.Checkbutton(self.sync_options_frame, text=i18n.get('mirror_delete'),
                      variable=self.mirror_var,
                      command=self.on_mirror_changed)
        self.mirror_check.grid(row=0, column=0, padx=(20, 40), pady=5, sticky='w')
        
        self.verify_var = tk.BooleanVar()
        self.verify_check = tk.Checkbutton(self.sync_options_frame, text=i18n.get('verify_transfer'),
                      variable=self.verify_var)
        self.verify_check.grid(row=0, column=1, padx=(20, 40), pady=5, sticky='w')
        
        # Safety options sub-frame
        self.safety_options_frame = tk.LabelFrame(self.options_frame, text=i18n.get('safety_options', 'Safety Options'))
        self.safety_options_frame.pack(fill='x', padx=10, pady=5)
        
        self.confirm_var = tk.BooleanVar()
        self.confirm_check = tk.Checkbutton(self.safety_options_frame, text=i18n.get('preview_changes'),
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
        
        # Update menu states based on current tab
        self.update_menu_states()
        
        # If switching to File Browser tab (index 2), auto-connect
        if current_tab == 2 and hasattr(self, 'file_browser'):
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
    
    # Status Bar Update Methods
    
    def update_connection_status(self, connected: bool, info_dict: dict = None):
        """Update the connection status section"""
        if connected:
            if info_dict:
                team = info_dict.get('team', 'Unknown')
                machine = info_dict.get('machine', 'Unknown')
                repo = info_dict.get('repo', 'Unknown')
                status_text = f"🟢 Connected to {team}/{machine}/{repo}"
                tooltip = f"Team: {team}\nMachine: {machine}\nRepository: {repo}\nPath: {info_dict.get('path', '/')}"
            else:
                status_text = "🟢 Connected"
                tooltip = "Connected to remote"
            if self.connection_status_label:
                self.connection_status_label.config(text=status_text, fg='#2e7d32')
        else:
            if self.connection_status_label:
                self.connection_status_label.config(text="🔴 Not connected", fg='#c62828')
            tooltip = "Click to connect to a remote repository"
        
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
                              "Switch to the File Browser tab to connect.")
    
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
    
    def load_teams(self):
        """Load available teams"""
        self.update_activity_status()
        self.root.update()
        
        result = self.runner.run_cli_command(['--output', 'json', 'list', 'teams'])
        if result['success'] and result.get('data'):
            teams = [self._get_name(team, 'teamName', 'name') for team in result['data']]
            self.update_teams(teams)
        else:
            error_msg = result.get('error', i18n.get('failed_to_load_teams'))
            if not self._handle_api_error(error_msg):
                self.activity_status_label.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
    
    def on_team_changed(self):
        """Handle team selection change"""
        self.load_machines()
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
        # Update menu states
        self.update_menu_states()
    
    def on_machine_changed(self):
        """Handle machine selection change"""
        self.load_repositories()
        # Reset plugin tracking since selection changed
        self.plugins_loaded_for = None
        # Update menu states
        self.update_menu_states()
    
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
        # Update menu states
        self.update_menu_states()
    
    def update_teams(self, teams: list):
        """Update team dropdowns"""
        self.team_combo['values'] = teams
        if teams:
            self.team_combo.set(teams[0])
            self.on_team_changed()
        self.update_activity_status()
    
    def load_machines(self):
        """Load machines for selected team"""
        team = self.team_combo.get()
        if not team:
            return
        
        self.activity_status_label.config(text=i18n.get('loading_machines', team=team))
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
                self.activity_status_label.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
    
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
        self.update_activity_status()
    
    def load_repositories(self):
        """Load repositories for selected team/machine"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        if not team:
            return
        
        self.activity_status_label.config(text=i18n.get('loading_repositories', team=team))
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
                                self.activity_status_label.config(text=status_text, fg=COLOR_SUCCESS)
                                self.root.after(3000, lambda: self.update_activity_status())
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
                self.activity_status_label.config(text=f"{i18n.get('error')}: {error_msg}", fg=COLOR_ERROR)
    
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
        self.update_activity_status()
    
    def _launch_terminal(self, command: str, description: str):
        """Common method to launch terminal with given command"""
        import os
        cli_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
                self.root.after(0, lambda: self.update_activity_status())
        
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
        
        self.activity_status_label.config(text=i18n.get('loading_plugins'))
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
        
        self.activity_status_label.config(text=i18n.get('found_connections', count=len(connections)))
    
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
        self.activity_status_label.config(text=i18n.get('connecting_to', plugin=plugin))
        
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
            self.root.after(0, lambda: self.update_activity_status())
        
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
            self.activity_status_label.config(text=i18n.get('disconnecting', plugin=plugin_name))
            
            def disconnect():
                cmd = ['plugin', 'disconnect', '--connection-id', conn_id]
                result = self.runner.run_command(cmd)
                
                if result['success']:
                    self.root.after(0, lambda: messagebox.showinfo(i18n.get('success'), i18n.get('disconnected', plugin=plugin_name)))
                else:
                    error = result.get('error', i18n.get('disconnect_failed'))
                    self.root.after(0, lambda: messagebox.showerror(i18n.get('error'), error))
                
                self.root.after(0, self.refresh_connections)
                self.root.after(0, lambda: self.update_activity_status())
            
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
        self.activity_status_label.config(text=i18n.get('opened_in_browser', url=url))
    
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
        
        self.activity_status_label.config(text=i18n.get('copied_to_clipboard', url=url), fg=COLOR_SUCCESS)
        self.root.after(2000, lambda: self.activity_status_label.config(fg='black'))
    
    def auto_refresh_connections(self):
        """Auto-refresh connections every 5 seconds"""
        # Only refresh if plugin tab is active
        if self.notebook.index(self.notebook.select()) == 0:  # Plugin tab is index 0
            self.refresh_connections()
        
        # Schedule next refresh
        self.root.after(AUTO_REFRESH_INTERVAL, self.auto_refresh_connections)
    
    # Menu action methods
    def show_preferences(self):
        """Show preferences dialog (transfer options)"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.show_transfer_options()
    
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
        messagebox.showinfo(i18n.get('info', 'Info'), i18n.get('not_implemented', 'Not implemented'))
    
    def set_view_mode(self, mode):
        """Set view mode (local, remote, split)"""
        # TODO: Implement view mode switching
        messagebox.showinfo(i18n.get('info', 'Info'), f"View mode: {mode} - {i18n.get('not_implemented', 'Not implemented')}")
    
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
        messagebox.showinfo(i18n.get('info', 'Info'), i18n.get('not_implemented', 'Not implemented'))
    
    def switch_to_plugin_tab(self):
        """Switch to Plugin Manager tab"""
        if hasattr(self, 'notebook'):
            self.notebook.select(0)  # Plugin Manager is the first tab
    
    def switch_to_sync_tab(self):
        """Switch to File Sync tab"""
        if hasattr(self, 'notebook'):
            self.notebook.select(1)  # File Sync is the second tab
    
    def show_transfer_options_wrapper(self):
        """Show transfer options dialog"""
        if hasattr(self, 'file_browser') and self.file_browser:
            self.file_browser.show_transfer_options()
    
    def show_console(self):
        """Show debug console window"""
        console_window = tk.Toplevel(self.root)
        console_window.title(i18n.get('console', 'Console'))
        console_window.geometry('800x600')
        
        # Add a text widget for future console implementation
        text = tk.Text(console_window, bg='black', fg='white', font=('Consolas', 10))
        text.pack(fill='both', expand=True)
        text.insert('1.0', 'Debug console - Not implemented\n')
    
    def connect(self):
        """Connect action (placeholder)"""
        messagebox.showinfo(i18n.get('info', 'Info'), i18n.get('not_implemented', 'Not implemented'))
    
    def disconnect(self):
        """Disconnect action (placeholder)"""
        messagebox.showinfo(i18n.get('info', 'Info'), i18n.get('not_implemented', 'Not implemented'))
    
    def show_bookmarks_dialog(self):
        """Show bookmarks management dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(i18n.get('manage_bookmarks', 'Manage Bookmarks'))
        dialog.geometry('500x400')
        dialog.transient(self.root)
        
        label = tk.Label(dialog, text=i18n.get('not_implemented', 'Not implemented'))
        label.pack(pady=20)
    
    def bookmark_current(self):
        """Bookmark current connection"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not all([team, machine, repo]):
            messagebox.showerror(i18n.get('error'), i18n.get('select_team_machine_repo'))
            return
        
        # TODO: Implement bookmark saving
        messagebox.showinfo(i18n.get('info', 'Info'), 
                           f"Bookmarked: {team}/{machine}/{repo} - {i18n.get('not_implemented', 'Not implemented')}")
    
    def show_documentation(self):
        """Open documentation in web browser"""
        import webbrowser
        webbrowser.open('https://docs.rediacc.com')
    
    def show_keyboard_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(i18n.get('keyboard_shortcuts', 'Keyboard Shortcuts'))
        dialog.geometry('600x500')
        dialog.transient(self.root)
        
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
            ('Ctrl+P', 'Plugin Manager'),
            ('Ctrl+S', 'File Sync'),
            ('F12', 'Console'),
            ('', ''),
            ('Connection Menu:', ''),
            ('Ctrl+Shift+C', 'Connect'),
            ('Ctrl+Shift+D', 'Disconnect'),
            ('Ctrl+B', 'Bookmark Current'),
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
        messagebox.showinfo(i18n.get('check_updates', 'Check for Updates'), 
                           i18n.get('no_updates', 'You are running the latest version.'))
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""Rediacc CLI

Version: 1.0.0

© 2024 Rediacc

{i18n.get('about_description', 'A powerful file management and synchronization tool.')}"""
        
        messagebox.showinfo(i18n.get('about', 'About Rediacc CLI'), about_text)
    
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
        self.logger.debug(f"Setting window title to: '{new_title}'")
        self.root.title(new_title)
        
        # Update user status in status bar
        auth_info = TokenManager.get_auth_info()
        self.user_status_label.config(text=f"{i18n.get('user', 'User')}: {auth_info.get('email', 'Unknown')}")
        
        # Update menu bar
        self.populate_language_menu()  # Update language submenu checkmarks
        self.update_menu_texts()
        
        # Update resource selection frame
        self.common_frame.config(text=i18n.get('resource_selection'))
        self.team_label.config(text=i18n.get('team'))
        self.machine_label.config(text=i18n.get('machine'))
        self.repo_label.config(text=i18n.get('repository'))
        
        # Update notebook tabs
        self.notebook.tab(0, text=i18n.get('plugin_manager'))
        self.notebook.tab(1, text=i18n.get('file_sync'))
        self.notebook.tab(2, text=i18n.get('file_browser', 'File Browser'))
        
        # Update status bar
        current_text = self.activity_status_label.cget('text')
        if current_text in ['Ready', 'جاهز', 'Bereit']:
            self.update_activity_status()
        
        # Update each tab's contents
        self.update_plugin_tab_texts()
        self.update_sync_tab_texts()
        self.update_file_browser_tab_texts()
        
        # Update LabelFrame texts that might have been missed
        if hasattr(self, 'sync_options_frame'):
            self.sync_options_frame.config(text=i18n.get('sync_options', 'Sync Options'))
        if hasattr(self, 'safety_options_frame'):
            self.safety_options_frame.config(text=i18n.get('safety_options', 'Safety Options'))
    
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
        file_browser_active = hasattr(self, 'file_browser') and self.file_browser and \
                            self.notebook.index(self.notebook.select()) == 2
        
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
        self.connection_menu.entryconfig(6, state='normal' if has_full_selection else 'disabled')  # Bookmark Current
        
        # Update recent connections
        self.update_recent_connections()
    
    def update_recent_connections(self):
        """Update the recent connections list in the Connection menu"""
        # Remove old recent connection items
        try:
            menu_length = self.connection_menu.index(tk.END)
            # Delete items between the separator and "Manage Bookmarks"
            for i in range(self.recent_connections_start_index, menu_length - 2):
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
                label=i18n.get('no_recent_connections', 'No recent connections'),
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
        
        # Update LabelFrame texts
        self.sync_options_frame.config(text=i18n.get('sync_options', 'Sync Options'))
        self.safety_options_frame.config(text=i18n.get('safety_options', 'Safety Options'))
    
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