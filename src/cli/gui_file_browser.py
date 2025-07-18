#!/usr/bin/env python3
"""
GUI File Browser

This module provides a dual-pane file browser with local and remote file management
capabilities, including file transfer, preview, and advanced options.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import subprocess
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, TYPE_CHECKING
import tempfile
import shutil
import re
import time
import datetime

if TYPE_CHECKING:
    from rediacc_gui import MainWindow

# Import core functionality
from core import get_logger, i18n
from rediacc_cli_core import (
    RepositoryConnection,
    colorize,
    setup_ssh_for_connection,
    is_windows
)

# Import GUI components
from gui_base import create_tooltip
from gui_utilities import (
    format_size, format_time, parse_ls_output,
    COMBO_WIDTH_SMALL, COMBO_WIDTH_MEDIUM, COLUMN_WIDTH_NAME, COLUMN_WIDTH_SIZE,
    COLUMN_WIDTH_MODIFIED, COLUMN_WIDTH_TYPE, COLOR_SUCCESS, COLOR_ERROR,
    COLOR_INFO, PREVIEW_SIZE_LIMIT, PREVIEW_LINE_LIMIT
)


class DualPaneFileBrowser:
    """Dual-pane file browser for local and remote file management"""
    
    def __init__(self, parent: tk.Frame, main_window: 'MainWindow'):
        self.parent = parent
        self.main_window = main_window
        self.logger = get_logger(__name__)
        
        # Current paths
        self.local_current_path = Path.home()
        self.remote_current_path = '/'
        
        # SSH connection info
        self.ssh_connection = None
        
        # Selected items
        self.local_selected = []
        self.remote_selected = []
        
        # Sorting state
        self.local_sort_column = 'name'
        self.local_sort_reverse = False
        self.remote_sort_column = 'name'
        self.remote_sort_reverse = False
        
        # File data cache for sorting
        self.local_files = []
        self.remote_files = []
        
        # Search filters
        self.local_filter = ''
        self.remote_filter = ''
        
        # Initialize search variables early to prevent access errors
        self.local_search_var = tk.StringVar()
        self.remote_search_var = tk.StringVar()
        
        # Transfer options
        self.transfer_options = {
            'preserve_timestamps': True,
            'preserve_permissions': True,
            'compress': True,
            'exclude_patterns': [],
            'bandwidth_limit': 0,  # KB/s, 0 = unlimited
            'skip_newer': False,
            'delete_after': False,
            'dry_run': False
        }
        
        # Clipboard for copy/cut operations
        self.clipboard_operation = None
        self.clipboard_files = []
        
        # Transfer tracking (keep for file browser functionality)
        self.transfer_speed = 0
        self.transfer_start_time = None
        self.bytes_transferred = 0
        
        self.create_widgets()
        self.setup_drag_drop()
        self.setup_keyboard_shortcuts()
        # Note: refresh_local() is now called at the end of create_widgets()
    
    def create_widgets(self):
        """Create the dual-pane browser interface"""
        # Main container
        main_frame = tk.Frame(self.parent)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create vertical paned window for main content and preview
        self.vertical_paned = tk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.vertical_paned.pack(fill='both', expand=True)
        
        # Container for horizontal panes
        horizontal_container = tk.Frame(self.vertical_paned)
        self.vertical_paned.add(horizontal_container, minsize=300)
        
        # Horizontal paned window for side-by-side panes
        self.paned_window = tk.PanedWindow(horizontal_container, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill='both', expand=True)
        
        # Create local pane
        self.create_local_pane()
        
        # Create middle frame for transfer buttons
        self.create_transfer_buttons_pane()
        
        # Create remote pane
        self.create_remote_pane()
        
        # Set initial pane ratios to 45%/10%/45%
        def set_initial_pane_ratios():
            try:
                self.paned_window.update_idletasks()
                total_width = self.paned_window.winfo_width()
                if total_width > 1:
                    # Calculate positions for 45%/10%/45% split
                    left_width = int(total_width * 0.45)
                    center_width = 160  # Fixed width for transfer pane
                    self.paned_window.sash_place(0, left_width, 0)
                    self.paned_window.sash_place(1, left_width + center_width, 0)
            except:
                pass
        
        # Schedule initial ratio setup
        self.paned_window.after(100, set_initial_pane_ratios)
        
        # After all panes are added, configure transfer pane width limiting
        def limit_transfer_pane_width(event=None):
            try:
                # Get current sash positions
                sash_0 = self.paned_window.sash_coord(0)[0]  # Left edge of transfer pane
                sash_1 = self.paned_window.sash_coord(1)[0]  # Right edge of transfer pane
                
                # Calculate transfer pane width
                transfer_width = sash_1 - sash_0
                
                # Limit to exactly 160 pixels
                max_width = 160
                if transfer_width != max_width:
                    # Adjust sash position to limit width
                    center = (sash_0 + sash_1) // 2
                    self.paned_window.sash_place(0, center - max_width // 2, 0)
                    self.paned_window.sash_place(1, center + max_width // 2, 0)
            except:
                pass  # Ignore errors during initialization
        
        # Bind to sash movement
        self.paned_window.bind('<B1-Motion>', limit_transfer_pane_width)
        self.paned_window.bind('<ButtonRelease-1>', limit_transfer_pane_width)
        
        # Create preview container for vertical paned window
        self.preview_container = tk.Frame(self.vertical_paned)
        self.preview_visible = False
        
        # Preview pane with improved padding
        self.preview_frame = tk.LabelFrame(self.preview_container, text=i18n.get('file_preview', 'File Preview'))
        self.preview_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Preview controls with grid layout
        preview_controls = tk.Frame(self.preview_frame)
        preview_controls.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(1, weight=1)
        
        # Configure preview controls grid
        preview_controls.grid_columnconfigure(0, weight=1)
        
        self.preview_filename_label = tk.Label(preview_controls, text='', font=('Arial', 10, 'bold'))
        self.preview_filename_label.grid(row=0, column=0, sticky='w', padx=5)
        
        self.preview_close_button = ttk.Button(preview_controls, text='×', width=3,
                                             command=self.hide_preview)
        self.preview_close_button.grid(row=0, column=1, sticky='e')
        
        # Preview content
        preview_scroll_frame = tk.Frame(self.preview_frame)
        preview_scroll_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=(0, 5))
        
        self.preview_text = scrolledtext.ScrolledText(preview_scroll_frame, height=10, 
                                                     font=('Consolas', 9), wrap='none')
        self.preview_text.pack(fill='both', expand=True)
        self.preview_text.config(state='disabled')
        
        # Horizontal scrollbar for preview
        preview_hsb = ttk.Scrollbar(preview_scroll_frame, orient='horizontal', 
                                   command=self.preview_text.xview)
        preview_hsb.pack(fill='x')
        self.preview_text.config(xscrollcommand=preview_hsb.set)
        
        # Status bar is now in the main window
    
        # Create preview toggle button in the paned window area
        preview_button_frame = tk.Frame(main_frame)
        preview_button_frame.pack(fill='x', pady=(5, 0))
        
        self.preview_toggle_button = ttk.Button(preview_button_frame, 
                                              text=i18n.get('show_preview', 'Show Preview'),
                                              command=self.toggle_preview)
        self.preview_toggle_button.pack(side='right', padx=5)
        
        # Now that all widgets are created, refresh the local directory
        self.refresh_local()
    
    def create_local_pane(self):
        """Create the local file browser pane"""
        # Container frame
        self.local_frame = tk.LabelFrame(self.paned_window, text=i18n.get('local_files', 'Local Files'))
        self.paned_window.add(self.local_frame, minsize=400)
        
        # Navigation frame using grid
        nav_frame = tk.Frame(self.local_frame)
        nav_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        self.local_frame.grid_columnconfigure(0, weight=1)
        
        # Configure nav_frame columns
        nav_frame.grid_columnconfigure(3, weight=1)  # Path entry column expands
        
        # Navigation buttons with consistent width and spacing
        self.local_up_button = ttk.Button(nav_frame, text='↑', width=4,
                                         command=self.navigate_local_up)
        self.local_up_button.grid(row=0, column=0, padx=(0, 5))
        create_tooltip(self.local_up_button, i18n.get('navigate_up_tooltip', 'Navigate to parent folder'))
        
        self.local_home_button = ttk.Button(nav_frame, text='🏠', width=4,
                                           command=self.navigate_local_home)
        self.local_home_button.grid(row=0, column=1, padx=(0, 5))
        create_tooltip(self.local_home_button, i18n.get('navigate_home_tooltip', 'Go to home directory'))
        
        # Path entry
        self.local_path_var = tk.StringVar(value=str(self.local_current_path))
        self.local_path_entry = ttk.Entry(nav_frame, textvariable=self.local_path_var, state='readonly')
        self.local_path_entry.grid(row=0, column=2, sticky='ew', padx=5)
        
        # Search frame using grid
        search_frame = tk.Frame(self.local_frame)
        search_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=(0, 5))
        search_frame.grid_columnconfigure(1, weight=1)  # Search entry column expands
        
        self.local_search_label = tk.Label(search_frame, text=i18n.get('search', 'Search:'))
        self.local_search_label.grid(row=0, column=0, padx=5)
        
        # Note: self.local_search_var is already initialized in __init__
        self.local_search_entry = ttk.Entry(search_frame, textvariable=self.local_search_var)
        self.local_search_entry.grid(row=0, column=1, sticky='ew', padx=5)
        # Use trace to update on every keystroke
        self.local_search_var.trace('w', lambda *args: self.on_local_search_changed())
        
        self.local_clear_button = ttk.Button(search_frame, text=i18n.get('clear', 'Clear'), 
                                           command=self.clear_local_search)
        self.local_clear_button.grid(row=0, column=2, padx=5)
        
        # File list with scrollbar (no extra padding)
        list_frame = tk.Frame(self.local_frame)
        list_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=(0, 5))
        self.local_frame.grid_rowconfigure(2, weight=1)
        
        # Create Treeview
        columns = ('size', 'modified', 'type')
        # Style for treeview if not already set
        if not hasattr(self.main_window, '_treeview_style_set'):
            style = ttk.Style()
            style.configure('Treeview', padding=(2,2,2,2))
            self.main_window._treeview_style_set = True
        
        self.local_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Configure alternating row colors
        self.local_tree.tag_configure('odd', background='#f5f5f5')
        self.local_tree.tag_configure('even', background='white')
        
        # Define columns
        self.local_tree.heading('#0', text='Name', command=lambda: self.sort_local('name'))
        self.local_tree.heading('size', text='Size', command=lambda: self.sort_local('size'))
        self.local_tree.heading('modified', text='Modified', command=lambda: self.sort_local('modified'))
        self.local_tree.heading('type', text='Type', command=lambda: self.sort_local('type'))
        
        # Column widths
        self.local_tree.column('#0', width=COLUMN_WIDTH_NAME)
        self.local_tree.column('size', width=COLUMN_WIDTH_SIZE)
        self.local_tree.column('modified', width=COLUMN_WIDTH_MODIFIED)
        self.local_tree.column('type', width=COLUMN_WIDTH_TYPE)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.local_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient='horizontal', command=self.local_tree.xview)
        self.local_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout with no padding
        self.local_tree.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)
        vsb.grid(row=0, column=1, sticky='ns', padx=0, pady=0)
        hsb.grid(row=1, column=0, sticky='ew', padx=0, pady=0)
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.local_tree.bind('<Double-Button-1>', self.on_local_double_click)
        self.local_tree.bind('<<TreeviewSelect>>', self.on_local_selection_changed)
        self.local_tree.bind('<Button-3>', self.show_local_context_menu)  # Right-click
        self.local_tree.bind('<space>', lambda e: self.preview_selected_file('local'))  # Space to preview
        
        # Configure for multi-select
        self.local_tree.configure(selectmode='extended')
    
    def create_transfer_buttons_pane(self):
        """Create the middle pane with transfer buttons"""
        # Container frame for buttons with exact width
        self.transfer_frame = tk.Frame(self.paned_window, bg='#f0f0f0')
        # Add with constraints - set exact width of 160
        self.paned_window.add(self.transfer_frame, minsize=160, width=160)
        
        # Add title
        title_label = tk.Label(self.transfer_frame, text=i18n.get('transfer_actions', 'Transfer Actions'),
                              font=('Arial', 10, 'bold'), bg='#f0f0f0')
        title_label.pack(pady=(10, 5))
        
        # Button container with proper spacing
        button_container = tk.Frame(self.transfer_frame, bg='#f0f0f0')
        button_container.pack(expand=True)
        
        # Upload button
        self.upload_button = ttk.Button(button_container, text=i18n.get('upload_arrow', 'Upload →'), 
                                       command=self.upload_selected, state='disabled',
                                       width=COMBO_WIDTH_SMALL)
        self.upload_button.pack(pady=(0, 20))
        create_tooltip(self.upload_button, i18n.get('upload_tooltip', 'Upload selected files to remote'))
        
        # Download button
        self.download_button = ttk.Button(button_container, text=i18n.get('download_arrow', '← Download'), 
                                         command=self.download_selected, state='disabled',
                                         width=COMBO_WIDTH_SMALL)
        self.download_button.pack(pady=(0, 20))
        create_tooltip(self.download_button, i18n.get('download_tooltip', 'Download selected files from remote'))
        
        # Options button removed - use Tools menu instead
        
        # Add visual separator lines with slightly darker color
        separator_style = {'bg': '#d0d0d0', 'width': 2}
        left_sep = tk.Frame(self.transfer_frame, **separator_style)
        left_sep.place(x=0, y=0, relheight=1)
        right_sep = tk.Frame(self.transfer_frame, **separator_style)
        right_sep.place(relx=1, x=-2, y=0, relheight=1)
        
        # Add hover effect instructions
        info_label = tk.Label(self.transfer_frame, 
                            text=i18n.get('select_files_to_transfer', 'Select files to transfer'),
                            font=('Arial', 8), fg='gray', bg='#f0f0f0')
        info_label.pack(side='bottom', pady=10)
    
    def create_remote_pane(self):
        """Create the remote file browser pane"""
        # Container frame
        self.remote_frame = tk.LabelFrame(self.paned_window, text=i18n.get('remote_files', 'Remote Files'))
        self.paned_window.add(self.remote_frame, minsize=400)
        
        # Connection status
        conn_frame = tk.Frame(self.remote_frame)
        conn_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        self.remote_frame.grid_columnconfigure(0, weight=1)
        
        # Connection status now shown in main status bar
        
        self.connect_button = ttk.Button(conn_frame, text=i18n.get('connect', 'Connect'), command=self.connect_remote)
        self.connect_button.pack(side='right')
        
        # Navigation frame using grid
        nav_frame = tk.Frame(self.remote_frame)
        nav_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        nav_frame.grid_columnconfigure(3, weight=1)  # Path entry column expands
        
        # Navigation buttons with consistent width and spacing
        self.remote_up_button = ttk.Button(nav_frame, text='↑', width=4,
                                          command=self.navigate_remote_up, state='disabled')
        self.remote_up_button.grid(row=0, column=0, padx=(0, 5))
        create_tooltip(self.remote_up_button, i18n.get('navigate_up_tooltip', 'Navigate to parent folder'))
        
        self.remote_home_button = ttk.Button(nav_frame, text='🏠', width=4,
                                            command=self.navigate_remote_home, state='disabled')
        self.remote_home_button.grid(row=0, column=1, padx=(0, 5))
        create_tooltip(self.remote_home_button, i18n.get('navigate_home_tooltip', 'Go to home directory'))
        
        # Path entry
        self.remote_path_var = tk.StringVar(value=self.remote_current_path)
        self.remote_path_entry = ttk.Entry(nav_frame, textvariable=self.remote_path_var, state='readonly')
        self.remote_path_entry.grid(row=0, column=2, sticky='ew', padx=5)
        
        # Search frame using grid
        search_frame = tk.Frame(self.remote_frame)
        search_frame.grid(row=2, column=0, sticky='ew', padx=5, pady=(0, 5))
        search_frame.grid_columnconfigure(1, weight=1)  # Search entry column expands
        
        self.remote_search_label = tk.Label(search_frame, text=i18n.get('search', 'Search:'))
        self.remote_search_label.grid(row=0, column=0, padx=5)
        
        # Note: self.remote_search_var is already initialized in __init__
        self.remote_search_entry = ttk.Entry(search_frame, textvariable=self.remote_search_var, state='disabled')
        self.remote_search_entry.grid(row=0, column=1, sticky='ew', padx=5)
        # Use trace to update on every keystroke
        self.remote_search_var.trace('w', lambda *args: self.on_remote_search_changed())
        
        self.remote_clear_button = ttk.Button(search_frame, text=i18n.get('clear', 'Clear'), 
                                            command=self.clear_remote_search, state='disabled')
        self.remote_clear_button.grid(row=0, column=2, padx=5)
        
        # File list with scrollbar (no extra padding)
        list_frame = tk.Frame(self.remote_frame)
        list_frame.grid(row=3, column=0, sticky='nsew', padx=5, pady=(0, 5))
        self.remote_frame.grid_rowconfigure(3, weight=1)
        
        # Create Treeview
        columns = ('size', 'modified', 'type')
        self.remote_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Configure alternating row colors
        self.remote_tree.tag_configure('odd', background='#f5f5f5')
        self.remote_tree.tag_configure('even', background='white')
        
        # Define columns
        self.remote_tree.heading('#0', text='Name', command=lambda: self.sort_remote('name'))
        self.remote_tree.heading('size', text='Size', command=lambda: self.sort_remote('size'))
        self.remote_tree.heading('modified', text='Modified', command=lambda: self.sort_remote('modified'))
        self.remote_tree.heading('type', text='Type', command=lambda: self.sort_remote('type'))
        
        # Column widths
        self.remote_tree.column('#0', width=COLUMN_WIDTH_NAME)
        self.remote_tree.column('size', width=COLUMN_WIDTH_SIZE)
        self.remote_tree.column('modified', width=COLUMN_WIDTH_MODIFIED)
        self.remote_tree.column('type', width=COLUMN_WIDTH_TYPE)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.remote_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient='horizontal', command=self.remote_tree.xview)
        self.remote_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout with no padding
        self.remote_tree.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)
        vsb.grid(row=0, column=1, sticky='ns', padx=0, pady=0)
        hsb.grid(row=1, column=0, sticky='ew', padx=0, pady=0)
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.remote_tree.bind('<Double-Button-1>', self.on_remote_double_click)
        self.remote_tree.bind('<<TreeviewSelect>>', self.on_remote_selection_changed)
        self.remote_tree.bind('<Button-3>', self.show_remote_context_menu)  # Right-click
        self.remote_tree.bind('<space>', lambda e: self.preview_selected_file('remote'))  # Space to preview
        
        # Configure for multi-select
        self.remote_tree.configure(selectmode='extended')
    
    # Local operations
    def refresh_local(self):
        """Refresh local file list"""
        try:
            # Log current path for debugging
            self.logger.debug(f"Refreshing local directory: {self.local_current_path}")
            
            # Ensure path exists and is accessible
            if not self.local_current_path.exists():
                self.logger.error(f"Path does not exist: {self.local_current_path}")
                self.local_current_path = Path.home()
                if hasattr(self, 'local_path_var') and self.local_path_var:
                    self.local_path_var.set(str(self.local_current_path))
            
            if not self.local_current_path.is_dir():
                self.logger.error(f"Path is not a directory: {self.local_current_path}")
                self.local_current_path = Path.home()
                if hasattr(self, 'local_path_var') and self.local_path_var:
                    self.local_path_var.set(str(self.local_current_path))
            
            # List directory contents
            self.local_files = []
            try:
                paths = list(self.local_current_path.iterdir())
            except Exception as e:
                self.logger.error(f"Failed to list directory {self.local_current_path}: {e}")
                # Try home directory as fallback
                self.local_current_path = Path.home()
                if hasattr(self, 'local_path_var') and self.local_path_var:
                    self.local_path_var.set(str(self.local_current_path))
                paths = list(self.local_current_path.iterdir())
            
            for path in paths:
                try:
                    stat_info = path.stat()
                    self.local_files.append({
                        'name': path.name,
                        'path': path,
                        'is_dir': path.is_dir(),
                        'size': stat_info.st_size if not path.is_dir() else 0,
                        'modified': stat_info.st_mtime,
                        'type': i18n.get('folder', 'Folder') if path.is_dir() else i18n.get('file', 'File')
                    })
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue
            
            # Display sorted files
            self.display_local_files()
            
        except Exception as e:
            import traceback
            self.logger.error(f"Error refreshing local files: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = f"Failed to list local directory: {str(e)}"
            # Add more context about what was being accessed
            if 'attribute' in str(e):
                error_msg += "\n\nThis appears to be an initialization issue. Please report this error."
            messagebox.showerror(i18n.get('error', 'Error'), error_msg)
    
    def on_local_search_changed(self):
        """Handle local search text change"""
        self.local_filter = self.local_search_var.get().lower()
        self.display_local_files()
    
    def clear_local_search(self):
        """Clear local search filter"""
        self.local_search_var.set('')
        self.local_filter = ''
        self.display_local_files()
    
    def display_local_files(self):
        """Display local files with current sorting and filtering"""
        # Check if tree widget exists
        if not hasattr(self, 'local_tree') or not self.local_tree:
            return
            
        # Clear existing items
        for item in self.local_tree.get_children():
            self.local_tree.delete(item)
        
        # Filter files
        filtered_files = []
        for file in self.local_files:
            if self.local_filter:
                # Check if filter matches filename (case-insensitive)
                if self.local_filter not in file['name'].lower():
                    continue
            filtered_files.append(file)
        
        # Sort files
        sorted_files = filtered_files.copy()
        
        # Define sort keys
        if self.local_sort_column == 'name':
            sort_key = lambda x: (not x['is_dir'], x['name'].lower())
        elif self.local_sort_column == 'size':
            sort_key = lambda x: (not x['is_dir'], x['size'])
        elif self.local_sort_column == 'modified':
            sort_key = lambda x: (not x['is_dir'], x['modified'])
        elif self.local_sort_column == 'type':
            sort_key = lambda x: (x['type'], x['name'].lower())
        else:
            sort_key = lambda x: (not x['is_dir'], x['name'].lower())
        
        sorted_files.sort(key=sort_key, reverse=self.local_sort_reverse)
        
        # Add items to tree with alternating row colors
        for index, item in enumerate(sorted_files):
            size_text = '' if item['is_dir'] else format_size(item['size'])
            modified_text = format_time(item['modified'])
            
            # Determine tags for file type and row color
            file_type = 'dir' if item['is_dir'] else 'file'
            row_color = 'even' if index % 2 == 0 else 'odd'
            tags = (file_type, row_color)
            
            # Insert with folder/file icon
            icon = '📁 ' if item['is_dir'] else '📄 '
            self.local_tree.insert('', 'end', text=icon + item['name'],
                                  values=(size_text, modified_text, item['type']),
                                  tags=tags)
        
        # Update path display
        if hasattr(self, 'local_path_var') and self.local_path_var:
            self.local_path_var.set(str(self.local_current_path))
        
        # Update status with filter info
        status_text = i18n.get('local_items', 'Local: {count} items').format(count=len(sorted_files))
        if self.local_filter:
            status_text += f" ({i18n.get('filtered', 'filtered')})"
        # Update activity status to show current state
        self.main_window.update_activity_status()
    
    def navigate_local_up(self):
        """Navigate to parent directory in local pane"""
        parent = self.local_current_path.parent
        if parent != self.local_current_path:
            self.local_current_path = parent
            self.refresh_local()
    
    def navigate_local_home(self):
        """Navigate to home directory in local pane"""
        self.local_current_path = Path.home()
        self.refresh_local()
    
    def navigate_local_to_path(self):
        """Navigate to path entered in local path entry"""
        try:
            path = Path(self.local_path_var.get())
            if path.exists() and path.is_dir():
                self.local_current_path = path
                self.refresh_local()
            else:
                messagebox.showerror(i18n.get('error', 'Error'), 
                                   i18n.get('invalid_directory', 'Invalid directory path'))
        except Exception as e:
            messagebox.showerror(i18n.get('error', 'Error'), 
                               i18n.get('invalid_path', f'Invalid path: {str(e)}'))
    
    def on_local_double_click(self, event):
        """Handle double-click on local file/folder"""
        selection = self.local_tree.selection()
        if selection:
            item = self.local_tree.item(selection[0])
            if 'dir' in item['tags']:
                # Navigate into directory
                dir_name = item['text'][2:]  # Remove icon
                self.local_current_path = self.local_current_path / dir_name
                self.refresh_local()
    
    def on_local_selection_changed(self, event):
        """Handle selection change in local pane"""
        self.local_selected = self.local_tree.selection()
        self.update_transfer_buttons()
    
    def sort_local(self, column: str):
        """Sort local file list by column"""
        # Toggle sort direction if same column
        if column == self.local_sort_column:
            self.local_sort_reverse = not self.local_sort_reverse
        else:
            self.local_sort_column = column
            self.local_sort_reverse = False
        
        # Update column headers to show sort indicator
        for col in ['name', 'size', 'modified', 'type']:
            if col == 'name':
                header = i18n.get('name', 'Name')
            else:
                header = i18n.get(col, col.capitalize())
            
            if col == column:
                # Add sort indicator
                indicator = ' ▼' if self.local_sort_reverse else ' ▲'
                header += indicator
            
            if col == 'name':
                self.local_tree.heading('#0', text=header)
            else:
                self.local_tree.heading(col, text=header)
        
        # Re-sort and display files
        self.display_local_files()
    
    # Remote operations
    def connect_remote(self):
        """Connect to remote repository"""
        team = self.main_window.team_combo.get()
        machine = self.main_window.machine_combo.get()
        repo = self.main_window.repo_combo.get()
        
        if not all([team, machine, repo]):
            messagebox.showerror(i18n.get('error', 'Error'), 
                               i18n.get('select_team_machine_repo', 'Please select team, machine, and repository first'))
            return
        
        self.connect_button.config(state='disabled')
        # Update connection status to connecting
        self.main_window.connection_status_label.config(text="🟡 Connecting...", fg='#f57c00')
        
        def do_connect():
            try:
                # Create repository connection
                self.ssh_connection = RepositoryConnection(team, machine, repo)
                self.ssh_connection.connect()
                
                # Get repository mount path
                self.remote_current_path = self.ssh_connection.repo_paths['mount_path']
                
                # Update UI
                self.parent.after(0, self.on_remote_connected)
                
            except Exception as e:
                self.logger.error(f"Failed to connect: {e}")
                self.parent.after(0, lambda: self.on_remote_connect_failed(str(e)))
        
        thread = threading.Thread(target=do_connect, daemon=True)
        thread.start()
    
    def on_remote_connected(self):
        """Handle successful remote connection"""
        # Update connection status
        info_dict = {
            'team': getattr(self.ssh_connection, 'team', 'Unknown'),
            'machine': getattr(self.ssh_connection, 'machine', 'Unknown'),
            'repo': getattr(self.ssh_connection, 'repository', 'Unknown'),
            'path': self.remote_current_path
        }
        self.main_window.update_connection_status(True, info_dict)
        self.connect_button.config(text=i18n.get('disconnect', 'Disconnect'), state='normal')
        self.connect_button.config(command=self.disconnect_remote)
        
        # Enable remote controls
        self.remote_up_button.config(state='normal')
        self.remote_home_button.config(state='normal')
        # Refresh button removed - use menu instead
        self.remote_path_entry.config(state='readonly')
        self.remote_search_entry.config(state='normal')
        self.remote_clear_button.config(state='normal')
        
        # Refresh remote file list
        self.refresh_remote()
    
    def on_remote_connect_failed(self, error: str):
        """Handle failed remote connection"""
        self.main_window.update_connection_status(False)
        self.connect_button.config(state='normal')
        messagebox.showerror(i18n.get('connection_failed', 'Connection Failed'), 
                           i18n.get('failed_connect_remote', f'Failed to connect to remote: {error}'))
    
    def disconnect_remote(self):
        """Disconnect from remote repository"""
        if self.ssh_connection:
            if hasattr(self.ssh_connection, 'cleanup_ssh'):
                self.ssh_connection.cleanup_ssh(getattr(self.ssh_connection, 'ssh_key_file', None),
                                               getattr(self.ssh_connection, 'known_hosts_file', None))
            self.ssh_connection = None
        
        # Clear remote tree
        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)
        
        # Update UI
        self.main_window.update_connection_status(False)
        self.connect_button.config(text=i18n.get('connect', 'Connect'), command=self.connect_remote)
        
        # Disable remote controls
        remote_controls = [
            self.remote_up_button, self.remote_home_button,
            self.remote_search_entry, self.remote_clear_button
        ]
        for control in remote_controls:
            control.config(state='disabled')
        self.remote_path_entry.config(state='readonly')
        
        # Clear state
        self.remote_search_var.set('')
        self.remote_filter = ''
        self.remote_selected = []
        self.update_transfer_buttons()
    
    def execute_remote_command(self, command: str) -> Tuple[bool, str]:
        """Execute command on remote via SSH"""
        if not self.ssh_connection:
            return False, "Not connected"
        
        try:
            ssh_opts, ssh_key_file, known_hosts_file = self.ssh_connection.setup_ssh()
            
            # Build SSH command
            ssh_cmd = ['ssh'] + ssh_opts.split() + [self.ssh_connection.ssh_destination]
            
            # Add sudo if we have universal_user
            universal_user = self.ssh_connection.connection_info.get('universal_user')
            if universal_user:
                ssh_cmd.extend(['sudo', '-u', universal_user])
            
            ssh_cmd.append(command)
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            
            # Store SSH files for cleanup
            self.ssh_connection.ssh_key_file = ssh_key_file
            self.ssh_connection.known_hosts_file = known_hosts_file
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr or f"Command failed with code {result.returncode}"
            
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def refresh_remote(self):
        """Refresh remote file list"""
        if not self.ssh_connection:
            return
        
        self.main_window.activity_status_label.config(text="Loading remote files...")
        
        def do_refresh():
            try:
                # Execute ls command
                success, output = self.execute_remote_command(f'ls -la "{self.remote_current_path}"')
                
                if success:
                    files = parse_ls_output(output)
                    self.parent.after(0, lambda: self.update_remote_tree(files))
                else:
                    self.parent.after(0, lambda: messagebox.showerror(i18n.get('error', 'Error'), 
                                                                     i18n.get('failed_list_remote', f'Failed to list remote directory: {output}')))
                    
            except Exception as e:
                self.logger.error(f"Error refreshing remote files: {e}")
                self.parent.after(0, lambda: messagebox.showerror(i18n.get('error', 'Error'), 
                                                                 i18n.get('failed_refresh_remote', f'Failed to refresh remote: {str(e)}')))
        
        thread = threading.Thread(target=do_refresh, daemon=True)
        thread.start()
    
    def update_remote_tree(self, files: List[Dict[str, Any]]):
        """Update remote tree with file list"""
        self.remote_files = files
        self.display_remote_files()
    
    def on_remote_search_changed(self):
        """Handle remote search text change"""
        self.remote_filter = self.remote_search_var.get().lower()
        self.display_remote_files()
    
    def clear_remote_search(self):
        """Clear remote search filter"""
        self.remote_search_var.set('')
        self.on_remote_search_changed()
    
    def display_remote_files(self):
        """Display remote files with current sorting and filtering"""
        # Clear existing items
        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)
        
        # Filter files
        filtered_files = []
        for file in self.remote_files:
            if self.remote_filter:
                # Check if filter matches filename (case-insensitive)
                if self.remote_filter not in file['name'].lower():
                    continue
            filtered_files.append(file)
        
        # Sort files
        sorted_files = filtered_files.copy()
        
        # Define sort keys
        if self.remote_sort_column == 'name':
            sort_key = lambda x: (not x['is_dir'], x['name'].lower())
        elif self.remote_sort_column == 'size':
            sort_key = lambda x: (not x['is_dir'], x['size'])
        elif self.remote_sort_column == 'modified':
            sort_key = lambda x: (not x['is_dir'], x['modified'])
        elif self.remote_sort_column == 'type':
            sort_key = lambda x: (x['type'], x['name'].lower())
        else:
            sort_key = lambda x: (not x['is_dir'], x['name'].lower())
        
        sorted_files.sort(key=sort_key, reverse=self.remote_sort_reverse)
        
        # Add items to tree with alternating row colors
        for index, item in enumerate(sorted_files):
            size_text = '' if item['is_dir'] else format_size(item['size'])
            modified_text = format_time(item['modified'])
            
            # Determine tags for file type and row color
            file_type = 'dir' if item['is_dir'] else 'file'
            row_color = 'even' if index % 2 == 0 else 'odd'
            tags = (file_type, row_color)
            
            # Insert with folder/file icon
            icon = '📁 ' if item['is_dir'] else '📄 '
            self.remote_tree.insert('', 'end', text=icon + item['name'],
                                   values=(size_text, modified_text, item['type']),
                                   tags=tags)
        
        # Update path display
        self.remote_path_var.set(self.remote_current_path)
        
        # Update status with filter info
        status_text = i18n.get('remote_items', 'Remote: {count} items').format(count=len(sorted_files))
        if self.remote_filter:
            status_text += f" ({i18n.get('filtered', 'filtered')})"
        # Update activity status
        self.main_window.update_activity_status()
    
    def navigate_remote_up(self):
        """Navigate to parent directory in remote pane"""
        if self.remote_current_path != '/':
            # Get parent path
            parent = '/'.join(self.remote_current_path.rstrip('/').split('/')[:-1])
            if not parent:
                parent = '/'
            self.remote_current_path = parent
            self.refresh_remote()
    
    def navigate_remote_home(self):
        """Navigate to repository root in remote pane"""
        if self.ssh_connection:
            self.remote_current_path = self.ssh_connection.repo_paths['mount_path']
            self.refresh_remote()
    
    def navigate_remote_to_path(self):
        """Navigate to path entered in remote path entry"""
        path = self.remote_path_var.get()
        if path:
            self.remote_current_path = path
            self.refresh_remote()
    
    def on_remote_double_click(self, event):
        """Handle double-click on remote file/folder"""
        selection = self.remote_tree.selection()
        if selection:
            item = self.remote_tree.item(selection[0])
            if 'dir' in item['tags']:
                # Navigate into directory
                dir_name = item['text'][2:]  # Remove icon
                if self.remote_current_path.endswith('/'):
                    self.remote_current_path = self.remote_current_path + dir_name
                else:
                    self.remote_current_path = self.remote_current_path + '/' + dir_name
                self.refresh_remote()
    
    def on_remote_selection_changed(self, event):
        """Handle selection change in remote pane"""
        self.remote_selected = self.remote_tree.selection()
        self.update_transfer_buttons()
    
    def sort_remote(self, column: str):
        """Sort remote file list by column"""
        # Toggle sort direction if same column
        if column == self.remote_sort_column:
            self.remote_sort_reverse = not self.remote_sort_reverse
        else:
            self.remote_sort_column = column
            self.remote_sort_reverse = False
        
        # Update column headers to show sort indicator
        indicator = ' ▼' if self.remote_sort_reverse else ' ▲'
        for col in ['name', 'size', 'modified', 'type']:
            header = i18n.get(col, col.capitalize()) if col != 'name' else i18n.get('name', 'Name')
            if col == column:
                header += indicator
            
            target = '#0' if col == 'name' else col
            self.remote_tree.heading(target, text=header)
        
        # Re-sort and display files
        self.display_remote_files()
    
    def update_transfer_buttons(self):
        """Update transfer button states based on selections"""
        self.upload_button.config(state='normal' if self.local_selected and self.ssh_connection else 'disabled')
        self.download_button.config(state='normal' if self.remote_selected and self.ssh_connection else 'disabled')
    
    def get_selected_paths(self, tree: ttk.Treeview, base_path) -> List[Tuple[str, bool]]:
        """Get selected file paths from tree"""
        return [(str(base_path / item['text'][2:] if isinstance(base_path, Path) 
                    else f"{base_path.rstrip('/')}/{item['text'][2:]}"),
                'dir' in item['tags'])
                for item_id in tree.selection()
                for item in [tree.item(item_id)]]
    
    def perform_selective_rsync(self, local_paths: List[Tuple[str, bool]], remote_base: str, 
                                direction: str = 'upload', progress_callback=None) -> Tuple[bool, str]:
        """Perform selective rsync transfer for specific files/folders"""
        try:
            # Get rsync command based on platform
            rsync_cmd = 'rsync'
            if is_windows():
                # Try to find rsync in MSYS2
                msys2_paths = ['C:\\msys64\\usr\\bin', 'C:\\msys2\\usr\\bin']
                for path in msys2_paths:
                    rsync_path = os.path.join(path, 'rsync.exe')
                    if os.path.exists(rsync_path):
                        rsync_cmd = rsync_path
                        break
            
            # Set up SSH
            ssh_opts, ssh_key_file, known_hosts_file = self.ssh_connection.setup_ssh()
            
            # Build SSH command
            ssh_cmd = f'ssh {ssh_opts}'
            
            # Get universal user if available
            universal_user = self.ssh_connection.connection_info.get('universal_user')
            
            success_count = 0
            error_messages = []
            
            for local_path, is_dir in local_paths:
                try:
                    # Build rsync command
                    cmd = [rsync_cmd, '-av', '--progress']
                    
                    # Apply transfer options
                    cmd = self.apply_transfer_options(cmd)
                    
                    # Add SSH command
                    cmd.extend(['-e', ssh_cmd])
                    
                    # Add sudo if needed
                    if universal_user:
                        cmd.extend(['--rsync-path', f'sudo -u {universal_user} rsync'])
                    
                    if direction == 'upload':
                        # Ensure trailing slash for directories
                        source = local_path
                        if is_dir and not source.endswith('/'):
                            source += '/'
                        
                        # Build destination
                        dest = f"{self.ssh_connection.ssh_destination}:{remote_base}"
                        if not remote_base.endswith('/'):
                            dest += '/'
                        
                        # For single file, preserve the filename
                        if not is_dir:
                            # Add the filename to destination
                            filename = os.path.basename(local_path)
                            dest = f"{self.ssh_connection.ssh_destination}:{remote_base}/{filename}"
                        
                        cmd.extend([source, dest])
                    else:  # download
                        # Build source
                        source = f"{self.ssh_connection.ssh_destination}:{local_path}"
                        if is_dir and not source.endswith('/'):
                            source += '/'
                        
                        # Build destination
                        dest = str(self.local_current_path)
                        if is_windows():
                            # Convert Windows path for rsync
                            dest = dest.replace('\\', '/')
                            if ':' in dest:
                                drive = dest[0].lower()
                                dest = f'/{drive}/{dest[3:]}'
                        
                        if not dest.endswith('/'):
                            dest += '/'
                        
                        # For single file download, preserve filename
                        if not is_dir:
                            filename = os.path.basename(local_path)
                            if is_windows():
                                dest_file = os.path.join(str(self.local_current_path), filename)
                                dest_file = dest_file.replace('\\', '/')
                                if ':' in dest_file:
                                    drive = dest_file[0].lower()
                                    dest = f'/{drive}/{dest_file[3:]}'
                                else:
                                    dest = dest_file
                            else:
                                dest = os.path.join(str(self.local_current_path), filename)
                        
                        cmd.extend([source, dest])
                    
                    # Run rsync
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                             text=True, bufsize=1)
                    
                    # Process output for progress
                    for line in process.stdout:
                        if progress_callback:
                            # Parse progress: "1,234,567  45%  123.45MB/s    0:00:10"
                            # Also handle: "xfr#1, to-chk=0/1"
                            if '%' in line:
                                try:
                                    # Find percentage in line
                                    match = re.search(r'(\d+)%', line)
                                    if match:
                                        percent = int(match.group(1))
                                        progress_callback(percent, line.strip())
                                        
                                        # Extract speed info for status bar
                                        speed_match = re.search(r'([\d.]+[KMG]?B/s)', line)
                                        if speed_match:
                                            speed_str = speed_match.group(1)
                                            # Convert to bytes/sec
                                            if speed_str.endswith('KB/s'):
                                                speed = float(speed_str[:-4]) * 1024
                                            elif speed_str.endswith('MB/s'):
                                                speed = float(speed_str[:-4]) * 1024 * 1024
                                            elif speed_str.endswith('GB/s'):
                                                speed = float(speed_str[:-4]) * 1024 * 1024 * 1024
                                            else:
                                                speed = float(speed_str[:-3])
                                            
                                            # Update performance status bar
                                            self.parent.after(0, lambda s=speed: self.main_window.update_performance_status(speed=s))
                                except:
                                    pass
                    
                    # Wait for completion
                    process.wait()
                    
                    if process.returncode == 0:
                        success_count += 1
                    else:
                        stderr = process.stderr.read()
                        error_messages.append(f"{os.path.basename(local_path)}: {stderr}")
                    
                except Exception as e:
                    error_messages.append(f"{os.path.basename(local_path)}: {str(e)}")
            
            # Clean up SSH files
            if ssh_key_file and os.path.exists(ssh_key_file):
                os.unlink(ssh_key_file)
            if known_hosts_file and os.path.exists(known_hosts_file):
                os.unlink(known_hosts_file)
            
            # Return results
            if success_count == len(local_paths):
                return True, f"Successfully transferred {success_count} items"
            elif success_count > 0:
                return False, f"Transferred {success_count}/{len(local_paths)} items. Errors: " + "; ".join(error_messages)
            else:
                return False, "Transfer failed: " + "; ".join(error_messages)
                
        except Exception as e:
            return False, f"Transfer error: {str(e)}"
    
    def upload_selected(self):
        """Upload selected local files to remote"""
        if not self.ssh_connection:
            return
        
        local_paths = self.get_selected_paths(self.local_tree, self.local_current_path)
        if not local_paths:
            return
        
        # Confirm operation
        file_list = '\n'.join([f"{'[DIR] ' if is_dir else ''}{Path(p).name}" for p, is_dir in local_paths])
        if not messagebox.askyesno(i18n.get('confirm_upload', 'Confirm Upload'),
                                  i18n.get('upload_confirm_message', 'Upload the following to {path}:\n\n{files}').format(path=self.remote_current_path, files=file_list)):
            return
        
        # Show progress dialog
        self.show_transfer_progress('upload', local_paths)
    
    def download_selected(self):
        """Download selected remote files to local"""
        if not self.ssh_connection:
            return
        
        remote_paths = self.get_selected_paths(self.remote_tree, self.remote_current_path)
        if not remote_paths:
            return
        
        # Confirm operation
        file_list = '\n'.join([f"{'[DIR] ' if is_dir else ''}{Path(p).name}" for p, is_dir in remote_paths])
        if not messagebox.askyesno(i18n.get('confirm_download', 'Confirm Download'),
                                  i18n.get('download_confirm_message', f'Download the following to {self.local_current_path}:\n\n{file_list}')):
            return
        
        # Show progress dialog
        self.show_transfer_progress('download', remote_paths)
    
    def show_transfer_progress(self, direction: str, paths: List[Tuple[str, bool]]):
        """Show transfer progress dialog"""
        # Create progress dialog
        progress_dialog = tk.Toplevel(self.parent)
        progress_dialog.title(i18n.get('transfer_progress', 'Transfer Progress'))
        # Use 0.4 * screen dimensions for progress dialog
        screen_width = progress_dialog.winfo_screenwidth()
        screen_height = progress_dialog.winfo_screenheight()
        dialog_width = int(screen_width * 0.4)
        dialog_height = int(screen_height * 0.4)
        
        progress_dialog.transient(self.parent)
        
        # Center the dialog
        progress_dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        progress_dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
        
        # Set minimum size
        progress_dialog.minsize(400, 350)
        
        # Make dialog resizable
        progress_dialog.resizable(True, True)
        
        # Prevent closing during transfer
        progress_dialog.protocol('WM_DELETE_WINDOW', lambda: None)
        
        # Main container that expands
        main_container = tk.Frame(progress_dialog)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Status label
        status_text = i18n.get('preparing_transfer', 'Preparing transfer...')
        if self.transfer_options.get('dry_run', False):
            status_text = i18n.get('dry_run_mode', 'DRY RUN MODE - ') + status_text
        status_label = tk.Label(main_container, text=status_text,
                               font=('Arial', 10), fg=COLOR_INFO if self.transfer_options.get('dry_run', False) else 'black')
        status_label.pack(pady=(0, 10))
        
        # Overall progress
        overall_frame = tk.LabelFrame(main_container, text=i18n.get('overall_progress', 'Overall Progress'))
        overall_frame.pack(fill='x', pady=(0, 10))
        
        # Progress bar container for proper resizing
        progress_container = tk.Frame(overall_frame)
        progress_container.pack(fill='x', padx=10, pady=10)
        
        overall_progress = ttk.Progressbar(progress_container, mode='determinate')
        overall_progress.pack(fill='x', expand=True)
        
        overall_label = tk.Label(overall_frame, text='0 / 0')
        overall_label.pack()
        
        # Current file progress
        file_frame = tk.LabelFrame(main_container, text=i18n.get('current_file', 'Current File'))
        file_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        file_label = tk.Label(file_frame, text='', font=('Arial', 9), wraplength=500)
        file_label.pack(pady=5, padx=10)
        
        # Update wraplength when dialog resizes
        def update_wraplength(event=None):
            new_width = progress_dialog.winfo_width() - 100  # Leave some margin
            if new_width > 100:  # Sanity check
                file_label.config(wraplength=new_width)
        
        progress_dialog.bind('<Configure>', update_wraplength)
        
        # Progress bar container
        file_progress_container = tk.Frame(file_frame)
        file_progress_container.pack(fill='x', padx=10, pady=5)
        
        file_progress = ttk.Progressbar(file_progress_container, mode='determinate')
        file_progress.pack(fill='x', expand=True)
        
        speed_label = tk.Label(file_frame, text='', font=('Arial', 9))
        speed_label.pack(pady=5)
        
        # Details frame for showing transfer log
        details_frame = tk.LabelFrame(main_container, text=i18n.get('details', 'Details'))
        details_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Create scrolled text for details
        details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap='none', 
                                                font=('Consolas', 9))
        details_text.pack(fill='both', expand=True)
        details_text.config(state='disabled')
        
        # Function to add log entry
        def add_log(message: str, color: str = 'black'):
            details_text.config(state='normal')
            details_text.insert(tk.END, f"{message}\n")
            # Auto-scroll to bottom
            details_text.see(tk.END)
            details_text.config(state='disabled')
        
        # Buttons
        button_frame = tk.Frame(main_container)
        button_frame.pack(fill='x', pady=(0, 5))
        
        cancel_button = ttk.Button(button_frame, text=i18n.get('cancel', 'Cancel'), 
                                  state='disabled')  # TODO: Implement cancel
        cancel_button.pack(side='left', padx=5)
        
        close_button = ttk.Button(button_frame, text=i18n.get('close', 'Close'),
                                 state='disabled', command=progress_dialog.destroy)
        close_button.pack(side='left', padx=5)
        
        # Disable main window buttons
        self.upload_button.config(state='disabled')
        self.download_button.config(state='disabled')
        
        # Initialize transfer tracking
        self.transfer_start_time = time.time()
        self.bytes_transferred = 0
        
        # Calculate total size
        total_size = 0
        for path, is_dir in paths:
            try:
                if is_dir:
                    # Estimate directory size (rough)
                    total_size += 1000000  # 1MB estimate per directory
                else:
                    total_size += os.path.getsize(path) if direction == 'upload' else 1000000
            except:
                pass
        
        # Update status bar for transfer start
        # Update status bar for transfer start
        self.main_window.start_activity_animation()
        self.main_window.update_activity_status(direction, len(paths), total_size)
        
        # Transfer thread
        def do_transfer():
            try:
                completed = 0
                total = len(paths)
                
                def update_file_progress(percent, info):
                    """Update current file progress"""
                    try:
                        progress_dialog.after(0, lambda: file_progress.config(value=percent))
                        progress_dialog.after(0, lambda: speed_label.config(text=info))
                    except:
                        # Dialog might be closed
                        pass
                
                # Process each file
                for i, (path, is_dir) in enumerate(paths):
                    filename = os.path.basename(path)
                    progress_dialog.after(0, lambda f=filename: file_label.config(text=f))
                    progress_dialog.after(0, lambda: file_progress.config(value=0))
                    
                    # Perform transfer for this file
                    if direction == 'upload':
                        success, msg = self.perform_selective_rsync(
                            [(path, is_dir)], self.remote_current_path, 
                            'upload', update_file_progress
                        )
                    else:
                        success, msg = self.perform_selective_rsync(
                            [(path, is_dir)], str(self.local_current_path), 
                            'download', update_file_progress
                        )
                    
                    if success:
                        completed += 1
                        progress_dialog.after(0, lambda m=f"✓ {filename}": add_log(m, 'green'))
                    else:
                        progress_dialog.after(0, lambda m=f"✗ {filename}: {msg}": add_log(m, 'red'))
                    
                    # Update overall progress
                    overall_percent = ((i + 1) / total) * 100
                    progress_dialog.after(0, lambda p=overall_percent: overall_progress.config(value=p))
                    progress_dialog.after(0, lambda c=completed, t=total: overall_label.config(
                        text=f'{c} / {t} ' + i18n.get('completed', 'completed')
                    ))
                
                # Transfer complete
                if completed == total:
                    msg = i18n.get('all_transfers_successful', f'All {total} transfers completed successfully!')
                    success = True
                else:
                    msg = i18n.get('some_transfers_failed', f'{completed}/{total} transfers completed successfully')
                    success = False
                
                progress_dialog.after(0, lambda: status_label.config(
                    text=msg, fg=COLOR_SUCCESS if success else 'red'
                ))
                progress_dialog.after(0, lambda: close_button.config(state='normal'))
                progress_dialog.after(0, lambda: progress_dialog.protocol('WM_DELETE_WINDOW', progress_dialog.destroy))
                
                # Update main window
                self.parent.after(0, lambda: self.on_transfer_complete(msg, success))
                
                # Refresh file lists after successful transfer
                if success:
                    if direction == 'upload':
                        self.parent.after(0, self.refresh_remote)
                    else:
                        self.parent.after(0, self.refresh_local)
                
            except Exception as e:
                self.logger.error(f"Transfer error: {e}")
                progress_dialog.after(0, lambda: status_label.config(
                    text=i18n.get('transfer_error', f'Error: {str(e)}'), fg=COLOR_ERROR
                ))
                progress_dialog.after(0, lambda: close_button.config(state='normal'))
                progress_dialog.after(0, lambda: progress_dialog.protocol('WM_DELETE_WINDOW', progress_dialog.destroy))
                self.parent.after(0, lambda: self.on_transfer_complete(str(e), False))
                
                # Reset status bar on error
                # Reset status bar
                self.parent.after(0, self.main_window.stop_activity_animation)
                self.parent.after(0, self.main_window.update_activity_status)
        
        thread = threading.Thread(target=do_transfer, daemon=True)
        thread.start()
    
    def on_transfer_complete(self, message: str, success: bool):
        """Handle transfer completion"""
        # Re-enable buttons
        self.update_transfer_buttons()
        
        # Update status
        # Activity status will be updated after transfer
        
        # Show message
        if success:
            messagebox.showinfo(i18n.get('transfer_complete', 'Transfer Complete'), message)
            # Refresh both panes
            self.refresh_local()
            if self.ssh_connection:
                self.refresh_remote()
        else:
            messagebox.showerror(i18n.get('transfer_failed', 'Transfer Failed'), message)
    
    def show_local_context_menu(self, event):
        """Show context menu for local files"""
        # Select item under cursor if not already selected
        item = self.local_tree.identify_row(event.y)
        if item and item not in self.local_tree.selection():
            self.local_tree.selection_set(item)
        
        if self.local_tree.selection():
            menu = tk.Menu(self.parent, tearoff=0)
            
            # Check if selection is a file
            item = self.local_tree.item(self.local_tree.selection()[0])
            is_file = 'file' in item['tags']
            
            if is_file:
                menu.add_command(label=i18n.get('preview', 'Preview'), 
                               command=lambda: self.preview_selected_file('local'))
                menu.add_separator()
            
            menu.add_command(label=i18n.get('upload', 'Upload'), command=self.upload_selected,
                           state='normal' if self.ssh_connection else 'disabled')
            menu.add_separator()
            menu.add_command(label=i18n.get('refresh', 'Refresh'), command=self.refresh_local)
            
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
    
    def show_remote_context_menu(self, event):
        """Show context menu for remote files"""
        # Select item under cursor if not already selected
        item = self.remote_tree.identify_row(event.y)
        if item and item not in self.remote_tree.selection():
            self.remote_tree.selection_set(item)
        
        if self.remote_tree.selection():
            menu = tk.Menu(self.parent, tearoff=0)
            
            # Check if selection is a file
            item = self.remote_tree.item(self.remote_tree.selection()[0])
            is_file = 'file' in item['tags']
            
            if is_file:
                menu.add_command(label=i18n.get('preview', 'Preview'), 
                               command=lambda: self.preview_selected_file('remote'))
                menu.add_separator()
            
            menu.add_command(label=i18n.get('download', 'Download'), command=self.download_selected)
            menu.add_separator()
            menu.add_command(label=i18n.get('refresh', 'Refresh'), command=self.refresh_remote)
            
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
    
    def setup_drag_drop(self):
        """Set up drag and drop functionality"""
        # Variables for drag state
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.dragging = False
        self.drag_source = None
        
        # Bind drag events for local tree
        self.local_tree.bind('<Button-1>', self.on_drag_start)
        self.local_tree.bind('<B1-Motion>', self.on_drag_motion)
        self.local_tree.bind('<ButtonRelease-1>', self.on_drag_release)
        
        # Bind drag events for remote tree
        self.remote_tree.bind('<Button-1>', self.on_drag_start)
        self.remote_tree.bind('<B1-Motion>', self.on_drag_motion)
        self.remote_tree.bind('<ButtonRelease-1>', self.on_drag_release)
        
        # Configure drop targets
        self.local_tree.bind('<Enter>', lambda e: self.on_drag_enter(e, 'local'))
        self.local_tree.bind('<Leave>', lambda e: self.on_drag_leave(e, 'local'))
        self.remote_tree.bind('<Enter>', lambda e: self.on_drag_enter(e, 'remote'))
        self.remote_tree.bind('<Leave>', lambda e: self.on_drag_leave(e, 'remote'))
    
    def on_drag_start(self, event):
        """Handle drag start"""
        # Check if we clicked on a selected item
        widget = event.widget
        item = widget.identify_row(event.y)
        
        if item and item in widget.selection():
            # Store drag start position
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.dragging = False
            
            # Identify source tree
            if widget == self.local_tree:
                self.drag_source = 'local'
            elif widget == self.remote_tree:
                self.drag_source = 'remote'
        else:
            # Not starting a drag
            self.drag_source = None
    
    def on_drag_motion(self, event):
        """Handle drag motion"""
        if not self.dragging:
            # Check if we've moved enough to start dragging
            if abs(event.x - self.drag_start_x) > 5 or abs(event.y - self.drag_start_y) > 5:
                self.dragging = True
                # Change cursor to indicate dragging
                self.parent.config(cursor='hand2')
    
    def on_drag_release(self, event):
        """Handle drag release (drop)"""
        if not self.dragging:
            # Not a drag operation, just a click
            self.drag_source = None
            return
        
        # Reset cursor
        self.parent.config(cursor='')
        
        # Get the widget under the cursor
        x, y = self.parent.winfo_pointerxy()
        target_widget = self.parent.winfo_containing(x, y)
        
        # Determine if we're dropping on a valid target
        target = None
        if target_widget == self.local_tree and self.drag_source == 'remote':
            target = 'local'
        elif target_widget == self.remote_tree and self.drag_source == 'local':
            target = 'remote'
        
        if target:
            # Valid drop target
            self.handle_drop(self.drag_source, target)
        
        # Reset drag state
        self.dragging = False
        self.drag_source = None
    
    def on_drag_enter(self, event, pane):
        """Handle drag enter for drop feedback"""
        if self.dragging and self.drag_source and self.drag_source != pane:
            frame = self.local_frame if pane == 'local' else self.remote_frame
            frame.config(relief='solid', borderwidth=2)
    
    def on_drag_leave(self, event, pane):
        """Handle drag leave to remove feedback"""
        frame = self.local_frame if pane == 'local' else self.remote_frame
        frame.config(relief='groove', borderwidth=2)
    
    def handle_drop(self, source: str, target: str):
        """Handle file drop between panes"""
        if not self.ssh_connection:
            messagebox.showwarning(i18n.get('warning', 'Warning'),
                                 i18n.get('connect_first', 'Please connect to remote first'))
            return
        
        # Map source/target to operation and trees
        operations = {
            ('local', 'remote'): ('upload', self.local_tree, self.local_current_path),
            ('remote', 'local'): ('download', self.remote_tree, self.remote_current_path)
        }
        
        operation_info = operations.get((source, target))
        if not operation_info:
            return
        
        operation, tree, base_path = operation_info
        paths = self.get_selected_paths(tree, base_path)
        
        if paths:
            file_list = '\n'.join([f"{'[DIR] ' if is_dir else ''}{Path(p).name}" for p, is_dir in paths])
            dest_path = self.remote_current_path if operation == 'upload' else self.local_current_path
            
            confirm_key = f'confirm_{operation}'
            message_key = f'drag_{operation}_confirm'
            
            if messagebox.askyesno(i18n.get(confirm_key, f'Confirm {operation.title()}'),
                                 i18n.get(message_key, f'{operation.title()} these files to {dest_path}?\n\n{file_list}')):
                self.show_transfer_progress(operation, paths)
    
    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts"""
        shortcuts = [
            ('<F5>', self.refresh_all),
            ('<Control-a>', self.select_all),
            ('<Delete>', self.delete_selected),
            ('<Control-x>', self.cut_selected),
            ('<Control-c>', self.copy_selected),
            ('<Control-v>', self.paste_files),
            ('<F2>', self.rename_selected),
            ('<Control-f>', self.focus_search),
            ('<Escape>', self.clear_search)
        ]
        
        for key, func in shortcuts:
            self.parent.bind_all(key, lambda e, f=func: f())
    
    def refresh_all(self):
        """Refresh both panes"""
        self.refresh_local()
        if self.ssh_connection:
            self.refresh_remote()
    
    def select_all(self):
        """Select all items in focused pane"""
        focused = self.parent.focus_get()
        
        local_widgets = [self.local_tree, self.local_search_entry, self.local_path_entry]
        remote_widgets = [self.remote_tree, self.remote_search_entry, self.remote_path_entry]
        
        if focused in local_widgets:
            self.local_tree.selection_set(self.local_tree.get_children())
        elif focused in remote_widgets:
            self.remote_tree.selection_set(self.remote_tree.get_children())
    
    def delete_selected(self):
        """Delete selected files (not implemented - would be dangerous)"""
        messagebox.showinfo(i18n.get('not_implemented', 'Not Implemented'),
                          i18n.get('delete_not_implemented', 'Delete functionality is not implemented for safety reasons.'))
    
    def cut_selected(self):
        """Mark selected files for move (not implemented)"""
        self.clipboard_operation = 'cut'
        self.clipboard_files = self.get_current_selection()
        if self.clipboard_files:
            messagebox.showinfo(i18n.get('cut', 'Cut'),
                              i18n.get('files_cut', f'{len(self.clipboard_files)} files marked for move'))
    
    def copy_selected(self):
        """Mark selected files for copy (not implemented)"""
        self.clipboard_operation = 'copy'
        self.clipboard_files = self.get_current_selection()
        if self.clipboard_files:
            messagebox.showinfo(i18n.get('copy', 'Copy'),
                              i18n.get('files_copied', f'{len(self.clipboard_files)} files marked for copy'))
    
    def paste_files(self):
        """Paste files (not implemented)"""
        if hasattr(self, 'clipboard_files') and self.clipboard_files:
            messagebox.showinfo(i18n.get('not_implemented', 'Not Implemented'),
                              i18n.get('paste_not_implemented', 'Paste functionality is not implemented yet.'))
    
    def get_current_selection(self):
        """Get currently selected files from focused pane"""
        focused = self.parent.focus_get()
        
        if focused == self.local_tree or focused in [self.local_search_entry, self.local_path_entry]:
            return self.get_selected_paths(self.local_tree, self.local_current_path)
        elif focused == self.remote_tree or focused in [self.remote_search_entry, self.remote_path_entry]:
            if self.ssh_connection:
                return self.get_selected_paths(self.remote_tree, self.remote_current_path)
        return []
    
    def rename_selected(self):
        """Rename selected file (not implemented)"""
        messagebox.showinfo(i18n.get('not_implemented', 'Not Implemented'),
                          i18n.get('rename_not_implemented', 'Rename functionality is not implemented yet.'))
    
    def focus_search(self):
        """Focus the search box of the active pane"""
        focused = self.parent.focus_get()
        
        if focused == self.remote_tree or focused in [self.remote_search_entry, self.remote_path_entry]:
            if self.remote_search_entry['state'] == 'normal':
                self.remote_search_entry.focus()
                self.remote_search_entry.selection_range(0, 'end')
        else:
            # Default to local search
            self.local_search_entry.focus()
            self.local_search_entry.selection_range(0, 'end')
    
    def clear_search(self):
        """Clear search in active pane"""
        focused = self.parent.focus_get()
        
        if focused == self.remote_search_entry:
            self.clear_remote_search()
        elif focused == self.local_search_entry:
            self.clear_local_search()
    
    def toggle_preview(self):
        """Toggle preview pane visibility"""
        if self.preview_visible:
            self.hide_preview()
        else:
            self.show_preview()
    
    def show_preview(self):
        """Show the preview pane"""
        if not self.preview_visible:
            # Calculate 35% of the total vertical space
            self.vertical_paned.update_idletasks()
            total_height = self.vertical_paned.winfo_height()
            
            # Calculate preview height as exactly 35% of total height
            preview_height = int(total_height * 0.35)
            # Ensure minimum height
            preview_height = max(150, preview_height)
            
            # Add preview container to vertical paned window
            self.vertical_paned.add(self.preview_container, minsize=150, height=preview_height)
            self.preview_visible = True
            self.preview_toggle_button.config(text=i18n.get('hide_preview', 'Hide Preview'))
            
            # Adjust the pane to maintain the 35% ratio
            def adjust_preview_pane():
                try:
                    self.vertical_paned.update_idletasks()
                    total_height = self.vertical_paned.winfo_height()
                    if total_height > 1:
                        # Set sash position to ensure preview takes 35% of space
                        main_height = int(total_height * 0.65)
                        self.vertical_paned.sash_place(0, 0, main_height)
                except:
                    pass
            
            # Schedule the adjustment
            self.vertical_paned.after(50, adjust_preview_pane)
    
    def hide_preview(self):
        """Hide the preview pane"""
        if self.preview_visible:
            # Remove preview container from vertical paned window
            self.vertical_paned.remove(self.preview_container)
            self.preview_visible = False
            self.preview_toggle_button.config(text=i18n.get('show_preview', 'Show Preview'))
    
    def preview_selected_file(self, source: str):
        """Preview the selected file"""
        # Get selected item
        if source == 'local':
            tree = self.local_tree
            base_path = self.local_current_path
        else:
            tree = self.remote_tree
            base_path = self.remote_current_path
            if not self.ssh_connection:
                return
        
        selection = tree.selection()
        if not selection:
            return
        
        item = tree.item(selection[0])
        if 'dir' in item['tags']:
            # Don't preview directories
            return
        
        filename = item['text'][2:]  # Remove icon
        
        # Show preview pane if hidden
        if not self.preview_visible:
            self.show_preview()
        
        # Update filename label
        self.preview_filename_label.config(text=filename)
        
        # Clear previous content
        self.preview_text.config(state='normal')
        self.preview_text.delete(1.0, tk.END)
        
        # Load file content
        if source == 'local':
            self.preview_local_file(base_path / filename)
        else:
            self.preview_remote_file(f"{base_path}/{filename}", filename)
    
    def preview_local_file(self, file_path: Path):
        """Preview a local file"""
        try:
            # Check file size
            stat_info = file_path.stat()
            if stat_info.st_size > PREVIEW_SIZE_LIMIT:  # 1MB limit
                self.preview_text.insert(1.0, i18n.get('file_too_large', 
                    f'File too large for preview ({format_size(stat_info.st_size)})'))
                self.preview_text.config(state='disabled')
                return
            
            # Try to read as text
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    # Read first 1000 lines
                    lines = []
                    for i, line in enumerate(f):
                        if i >= PREVIEW_LINE_LIMIT:
                            lines.append('\n... (truncated) ...')
                            break
                        lines.append(line.rstrip('\n'))
                    
                    content = '\n'.join(lines)
                    self.preview_text.insert(1.0, content)
            except Exception as e:
                self.preview_text.insert(1.0, i18n.get('preview_error', f'Error reading file: {str(e)}'))
        
        except Exception as e:
            self.preview_text.insert(1.0, i18n.get('preview_error', f'Error: {str(e)}'))
        
        finally:
            self.preview_text.config(state='disabled')
    
    def preview_remote_file(self, remote_path: str, filename: str):
        """Preview a remote file"""
        self.preview_text.insert(1.0, i18n.get('loading_preview', 'Loading preview...'))
        self.preview_text.config(state='disabled')
        
        def load_remote():
            try:
                # First check file size
                success, size_output = self.execute_remote_command(
                    f'stat -c %s "{remote_path}" 2>/dev/null || echo "0"'
                )
                
                if success:
                    try:
                        file_size = int(size_output.strip())
                        if file_size > PREVIEW_SIZE_LIMIT:  # 1MB limit
                            self.parent.after(0, lambda: self.update_preview_content(
                                i18n.get('file_too_large', f'File too large for preview ({format_size(file_size)})')
                            ))
                            return
                    except:
                        pass
                
                # Use head command to get first 1000 lines
                success, output = self.execute_remote_command(
                    f'head -n {PREVIEW_LINE_LIMIT} "{remote_path}" 2>/dev/null || echo "[File not readable]"'
                )
                
                if success:
                    # Update preview in UI thread
                    self.parent.after(0, lambda: self.update_preview_content(output))
                else:
                    self.parent.after(0, lambda: self.update_preview_content(
                        i18n.get('preview_error', f'Error loading preview: {output}')))
            
            except Exception as e:
                self.parent.after(0, lambda: self.update_preview_content(
                    i18n.get('preview_error', f'Error: {str(e)}')))
        
        thread = threading.Thread(target=load_remote, daemon=True)
        thread.start()
    
    def update_preview_content(self, content: str):
        """Update preview content in UI thread"""
        self.preview_text.config(state='normal')
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, content)
        self.preview_text.config(state='disabled')
    
    def show_transfer_options(self):
        """Show transfer options dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(i18n.get('transfer_options', 'Transfer Options'))
        dialog.transient(self.parent)
        
        # Center and make modal
        dialog.update_idletasks()
        width, height = 700, 700
        x = (dialog.winfo_screenwidth() - width) // 2
        y = (dialog.winfo_screenheight() - height) // 2
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        dialog.grab_set()
        
        # Main container with scrollbar
        container = tk.Frame(dialog)
        container.pack(fill='both', expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        # Create window in canvas
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Configure canvas scrolling
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Make the canvas window expand with the canvas
        def configure_canvas(event):
            # Update the canvas window to fill the canvas width
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        canvas.bind('<Configure>', configure_canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mouse wheel to canvas and all child widgets
        canvas.bind_all("<MouseWheel>", on_mousewheel)  # Windows
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))  # Linux
        
        # File Handling Options
        file_frame = tk.LabelFrame(scrollable_frame, text=i18n.get('file_handling', 'File Handling'))
        file_frame.pack(fill='x', padx=10, pady=10, expand=False)
        
        # Preserve timestamps
        self.preserve_time_var = tk.BooleanVar(value=self.transfer_options['preserve_timestamps'])
        preserve_time_check = tk.Checkbutton(file_frame, 
                                           text=i18n.get('preserve_timestamps', 'Preserve modification times'),
                                           variable=self.preserve_time_var)
        preserve_time_check.pack(anchor='w', padx=10, pady=5)
        
        # Preserve permissions
        self.preserve_perm_var = tk.BooleanVar(value=self.transfer_options['preserve_permissions'])
        preserve_perm_check = tk.Checkbutton(file_frame, 
                                           text=i18n.get('preserve_permissions', 'Preserve file permissions'),
                                           variable=self.preserve_perm_var)
        preserve_perm_check.pack(anchor='w', padx=10, pady=5)
        
        # Skip newer files
        self.skip_newer_var = tk.BooleanVar(value=self.transfer_options['skip_newer'])
        skip_newer_check = tk.Checkbutton(file_frame, 
                                         text=i18n.get('skip_newer', 'Skip files that are newer on receiver'),
                                         variable=self.skip_newer_var)
        skip_newer_check.pack(anchor='w', padx=10, pady=5)
        
        # Delete after transfer
        self.delete_after_var = tk.BooleanVar(value=self.transfer_options['delete_after'])
        delete_after_check = tk.Checkbutton(file_frame, 
                                          text=i18n.get('delete_after', 'Delete source files after successful transfer'),
                                          variable=self.delete_after_var)
        delete_after_check.pack(anchor='w', padx=10, pady=5)
        
        # Performance Options
        perf_frame = tk.LabelFrame(scrollable_frame, text=i18n.get('performance', 'Performance'))
        perf_frame.pack(fill='x', padx=10, pady=10, expand=False)
        
        # Compression
        self.compress_var = tk.BooleanVar(value=self.transfer_options['compress'])
        compress_check = tk.Checkbutton(perf_frame, 
                                      text=i18n.get('compress', 'Compress data during transfer'),
                                      variable=self.compress_var)
        compress_check.pack(anchor='w', padx=10, pady=5)
        
        # Bandwidth limit
        bw_frame = tk.Frame(perf_frame)
        bw_frame.pack(fill='x', padx=10, pady=5)
        
        bw_label = tk.Label(bw_frame, text=i18n.get('bandwidth_limit', 'Bandwidth limit:')).pack(side='left')
        
        self.bw_limit_var = tk.StringVar(value=str(self.transfer_options['bandwidth_limit']))
        
        # Validation command for numeric input
        vcmd = (dialog.register(self.validate_bandwidth), '%P')
        bw_entry = ttk.Entry(bw_frame, textvariable=self.bw_limit_var, width=10,
                           validate='key', validatecommand=vcmd)
        bw_entry.pack(side='left', padx=10)
        
        bw_help = tk.Label(bw_frame, text=i18n.get('bw_help', 'KB/s (0 = unlimited)'), font=('Arial', 9))
        bw_help.pack(side='left')
        
        # Exclude Patterns
        exclude_frame = tk.LabelFrame(scrollable_frame, text=i18n.get('exclude_patterns', 'Exclude Patterns'))
        exclude_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        exclude_info = tk.Label(exclude_frame, 
                              text=i18n.get('exclude_info', 'Enter patterns to exclude (one per line):'),
                              font=('Arial', 9))
        exclude_info.pack(anchor='w', padx=10, pady=5)
        
        # Create text widget with frame for better resizing
        text_frame = tk.Frame(exclude_frame)
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.exclude_text = tk.Text(text_frame, height=6, wrap='none')
        exclude_scroll = ttk.Scrollbar(text_frame, command=self.exclude_text.yview)
        self.exclude_text.configure(yscrollcommand=exclude_scroll.set)
        
        self.exclude_text.pack(side='left', fill='both', expand=True)
        exclude_scroll.pack(side='right', fill='y')
        
        # Load existing patterns
        if self.transfer_options['exclude_patterns']:
            self.exclude_text.insert(1.0, '\n'.join(self.transfer_options['exclude_patterns']))
        
        # Common excludes
        common_frame = tk.Frame(exclude_frame)
        common_frame.pack(fill='x', padx=10, pady=5)
        
        common_label = tk.Label(common_frame, text=i18n.get('common_excludes', 'Common:'), font=('Arial', 9))
        common_label.pack(side='left')
        
        common_patterns = ['.git', '*.tmp', '*.log', '__pycache__', 'node_modules']
        for pattern in common_patterns:
            btn = ttk.Button(common_frame, text=pattern, width=12,
                           command=lambda p=pattern: self.add_exclude_pattern(p))
            btn.pack(side='left', padx=2)
        
        # Test Mode
        test_frame = tk.LabelFrame(scrollable_frame, text=i18n.get('test_mode', 'Test Mode'))
        test_frame.pack(fill='x', padx=10, pady=10, expand=False)
        
        self.dry_run_var = tk.BooleanVar(value=self.transfer_options['dry_run'])
        dry_run_check = tk.Checkbutton(test_frame, 
                                      text=i18n.get('dry_run', 'Dry run (show what would be transferred without doing it)'),
                                      variable=self.dry_run_var)
        dry_run_check.pack(anchor='w', padx=10, pady=5)
        
        # Buttons - use fill='x' for proper centering
        button_frame = tk.Frame(scrollable_frame)
        button_frame.pack(fill='x', pady=20)
        
        save_button = ttk.Button(button_frame, text=i18n.get('save', 'Save'), 
                               command=lambda: self.save_transfer_options(dialog))
        save_button.pack(side='left', padx=5)
        
        cancel_button = ttk.Button(button_frame, text=i18n.get('cancel', 'Cancel'), 
                                 command=dialog.destroy)
        cancel_button.pack(side='left', padx=5)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Clean up mouse wheel binding when dialog closes
        def on_dialog_close():
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        # Set minimum size for dialog
        dialog.minsize(500, 400)
        
        # Make dialog properly resizable
        dialog.resizable(True, True)
    
    def add_exclude_pattern(self, pattern: str):
        """Add pattern to exclude list"""
        current = self.exclude_text.get(1.0, tk.END).strip()
        if current:
            self.exclude_text.insert(tk.END, f'\n{pattern}')
        else:
            self.exclude_text.insert(1.0, pattern)
    
    def save_transfer_options(self, dialog):
        """Save transfer options and close dialog"""
        # Update options
        self.transfer_options['preserve_timestamps'] = self.preserve_time_var.get()
        self.transfer_options['preserve_permissions'] = self.preserve_perm_var.get()
        self.transfer_options['compress'] = self.compress_var.get()
        self.transfer_options['skip_newer'] = self.skip_newer_var.get()
        self.transfer_options['delete_after'] = self.delete_after_var.get()
        self.transfer_options['dry_run'] = self.dry_run_var.get()
        
        # Parse bandwidth limit
        try:
            bw = int(self.bw_limit_var.get())
            self.transfer_options['bandwidth_limit'] = max(0, bw)
        except ValueError:
            self.transfer_options['bandwidth_limit'] = 0
        
        # Parse exclude patterns
        patterns = self.exclude_text.get(1.0, tk.END).strip().split('\n')
        self.transfer_options['exclude_patterns'] = [p.strip() for p in patterns if p.strip()]
        
        # Show confirmation
        messagebox.showinfo(i18n.get('success', 'Success'), 
                          i18n.get('options_saved', 'Transfer options saved'))
        
        dialog.destroy()
    
    def validate_bandwidth(self, value):
        """Validate bandwidth input - allow only positive integers"""
        if value == '':
            return True
        try:
            int_value = int(value)
            return int_value >= 0
        except ValueError:
            return False
    
    def apply_transfer_options(self, rsync_cmd: list) -> list:
        """Apply transfer options to rsync command"""
        # Preserve options
        if self.transfer_options['preserve_timestamps']:
            if '-t' not in rsync_cmd:
                rsync_cmd.append('-t')
        
        if self.transfer_options['preserve_permissions']:
            if '-p' not in rsync_cmd:
                rsync_cmd.append('-p')
        
        # Compression
        if self.transfer_options['compress']:
            if '-z' not in rsync_cmd:
                rsync_cmd.append('-z')
        
        # Skip newer
        if self.transfer_options['skip_newer']:
            rsync_cmd.append('--update')
        
        # Delete after
        if self.transfer_options['delete_after']:
            rsync_cmd.append('--remove-source-files')
        
        # Bandwidth limit
        if self.transfer_options['bandwidth_limit'] > 0:
            rsync_cmd.extend(['--bwlimit', str(self.transfer_options['bandwidth_limit'])])
        
        # Exclude patterns
        for pattern in self.transfer_options['exclude_patterns']:
            rsync_cmd.extend(['--exclude', pattern])
        
        # Dry run
        if self.transfer_options['dry_run']:
            rsync_cmd.append('--dry-run')
        
        return rsync_cmd
    
    def update_texts(self):
        """Update all UI texts for internationalization"""
        # Update frame titles
        self.local_frame.config(text=i18n.get('local_files', 'Local Files'))
        self.remote_frame.config(text=i18n.get('remote_files', 'Remote Files'))
        
        # Update buttons
        self.upload_button.config(text=i18n.get('upload_arrow', 'Upload →'))
        self.download_button.config(text=i18n.get('download_arrow', '← Download'))
        
        # Update connection status
        if self.ssh_connection:
            # Connection status already updated in on_remote_connected
            self.connect_button.config(text=i18n.get('disconnect', 'Disconnect'))
        else:
            # Connection status already updated in disconnect_remote
            self.connect_button.config(text=i18n.get('connect', 'Connect'))
        
        # Update column headings
        self.local_tree.heading('#0', text=i18n.get('name', 'Name'))
        self.local_tree.heading('size', text=i18n.get('size', 'Size'))
        self.local_tree.heading('modified', text=i18n.get('modified', 'Modified'))
        self.local_tree.heading('type', text=i18n.get('type', 'Type'))
        
        self.remote_tree.heading('#0', text=i18n.get('name', 'Name'))
        self.remote_tree.heading('size', text=i18n.get('size', 'Size'))
        self.remote_tree.heading('modified', text=i18n.get('modified', 'Modified'))
        self.remote_tree.heading('type', text=i18n.get('type', 'Type'))
        
        # Update preview pane
        if hasattr(self, 'preview_frame'):
            self.preview_frame.config(text=i18n.get('file_preview', 'File Preview'))
            self.preview_toggle_button.config(text=i18n.get('hide_preview' if self.preview_visible else 'show_preview', 
                                                           'Hide Preview' if self.preview_visible else 'Show Preview'))
        
        # Options button removed - using menu instead
        
        # Update search labels and buttons
        if hasattr(self, 'local_search_label'):
            self.local_search_label.config(text=i18n.get('search', 'Search:'))
            self.local_clear_button.config(text=i18n.get('clear', 'Clear'))
            self.remote_search_label.config(text=i18n.get('search', 'Search:'))
            self.remote_clear_button.config(text=i18n.get('clear', 'Clear'))
    
