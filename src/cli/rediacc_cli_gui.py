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
from typing import Callable, Optional, Dict, Any, List, Tuple
from datetime import datetime
import time
import stat
import shutil
import tempfile
import re

# Tooltip helper class
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.on_enter)
        widget.bind("<Leave>", self.on_leave)
    
    def on_enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, justify='left',
                        background="#ffffe0", relief='solid', borderwidth=1,
                        font=("Arial", "9", "normal"))
        label.pack()
    
    def on_leave(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

def create_tooltip(widget, text):
    return ToolTip(widget, text)

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



class BaseWindow:
    """Base class for all GUI windows"""
    def __init__(self, root: tk.Tk, title: str = None):
        self.root = root
        self.root.title(title or i18n.get('app_title'))
        
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
        super().__init__(tk.Tk(), i18n.get('login_title'))
        self.on_login_success = on_login_success
        self.center_window(450, 500)  # Increased size for 2FA field
        
        # Register for language changes
        i18n.register_observer(self.update_texts)
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create login form"""
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Language selector at top
        lang_frame = tk.Frame(main_frame)
        lang_frame.pack(fill='x', pady=(0, 10))
        
        self.lang_label = tk.Label(lang_frame, text=i18n.get('language') + ':')
        self.lang_label.pack(side='left', padx=5)
        
        self.lang_combo = ttk.Combobox(lang_frame, state='readonly', width=15)
        self.lang_combo['values'] = [i18n.get_language_name(code) for code in i18n.get_language_codes()]
        self.lang_combo.set(i18n.get_language_name(i18n.current_language))
        self.lang_combo.pack(side='left')
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        # Title with less padding to save space
        self.title_label = tk.Label(main_frame, text=i18n.get('login_header'),
                        font=('Arial', 16, 'bold'))
        self.title_label.pack(pady=15)
        
        # Email field
        self.email_label = tk.Label(main_frame, text=i18n.get('email'))
        self.email_label.pack(anchor='w', pady=(5, 0))
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.pack(fill='x', pady=(2, 8))
        
        # Password field
        self.password_label = tk.Label(main_frame, text=i18n.get('password'))
        self.password_label.pack(anchor='w', pady=(5, 0))
        self.password_entry = ttk.Entry(main_frame, width=40, show='*')
        self.password_entry.pack(fill='x', pady=(2, 8))
        
        # Master password field
        self.master_password_label = tk.Label(main_frame, text=i18n.get('master_password'))
        self.master_password_label.pack(anchor='w', pady=(5, 0))
        self.master_password_entry = ttk.Entry(main_frame, width=40, show='*')
        self.master_password_entry.pack(fill='x', pady=(2, 8))
        
        # 2FA code field (initially hidden)
        self.tfa_frame = tk.Frame(main_frame)
        self.tfa_label = tk.Label(self.tfa_frame, text=i18n.get('tfa_code'), font=('Arial', 10, 'bold'))
        self.tfa_label.pack(anchor='w', pady=(5, 0))
        self.tfa_entry = ttk.Entry(self.tfa_frame, width=40, font=('Arial', 11))
        self.tfa_entry.pack(fill='x', pady=(2, 2))
        self.tfa_help = tk.Label(self.tfa_frame, text=i18n.get('tfa_help'), 
                                font=('Arial', 9), fg='gray')
        self.tfa_help.pack(anchor='w', pady=(0, 8))
        # Don't pack the frame initially - it will be shown when 2FA is required
        
        # Login button
        self.login_button = ttk.Button(main_frame, text=i18n.get('login'), command=self.login)
        self.login_button.pack(pady=15)
        
        # Status label with wrapping
        self.status_label = tk.Label(main_frame, text="", wraplength=400, justify='center')
        self.status_label.pack(pady=(0, 10))
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())
        
        # Focus on email field
        self.email_entry.focus()
    
    def login(self):
        """Handle login"""
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        master_password = self.master_password_entry.get()
        tfa_code = self.tfa_entry.get().strip() if hasattr(self, 'tfa_entry') else ""
        
        if not email or not password:
            messagebox.showerror(i18n.get('error'), i18n.get('please_enter_credentials'))
            return
        
        self.login_button.config(state='disabled')
        self.status_label.config(text=i18n.get('logging_in'))
        
        # Run login in thread
        thread = threading.Thread(target=self._do_login, args=(email, password, master_password, tfa_code))
        thread.daemon = True
        thread.start()
    
    def _do_login(self, email: str, password: str, master_password: str, tfa_code: str = ""):
        """Perform login in background thread"""
        try:
            runner = SubprocessRunner()
            cmd = ['--output', 'json', 'login', '--email', email, '--password', password]
            
            # Only add master password if provided
            if master_password.strip():
                cmd.extend(['--master-password', master_password])
                
            # Add 2FA code if provided
            if tfa_code:
                cmd.extend(['--tfa-code', tfa_code])
            
            result = runner.run_cli_command(cmd)
            
            if result['success']:
                # Login successful - token is already saved by CLI
                self.root.after(0, self.login_success)
            else:
                error = result.get('error', i18n.get('login_failed'))
                # Check if 2FA is required
                if '2FA_REQUIRED' in error:
                    # Show 2FA field and update status
                    self.root.after(0, self.show_2fa_field)
                else:
                    self.root.after(0, lambda: self.login_error(error))
        except Exception as e:
            self.root.after(0, lambda: self.login_error(str(e)))
    
    def login_success(self):
        """Handle successful login"""
        self.status_label.config(text=i18n.get('login_successful'), fg='green')
        # Unregister observer before closing
        i18n.unregister_observer(self.update_texts)
        self.root.withdraw()
        self.on_login_success()
    
    def login_error(self, error: str):
        """Handle login error"""
        self.login_button.config(state='normal')
        self.status_label.config(text=f"{i18n.get('error')}: {error}", fg='red')
    
    def show_2fa_field(self):
        """Show 2FA field when required"""
        # Show the 2FA frame before the login button
        self.tfa_frame.pack(before=self.login_button, fill='x', pady=(5, 0))
        
        # Clear any previous 2FA code
        self.tfa_entry.delete(0, tk.END)
        
        # Update status and re-enable login button
        self.status_label.config(text=i18n.get('tfa_required'), 
                                fg='#FF6B35', font=('Arial', 10))
        self.login_button.config(state='normal')
        
        # Focus on 2FA field
        self.tfa_entry.focus()
        
        # Update window size if needed to accommodate the new field
        self.root.update_idletasks()  # Force layout update
    
    def on_language_changed(self, event):
        """Handle language selection change"""
        selected_name = self.lang_combo.get()
        # Find the language code for the selected name
        for code in i18n.get_language_codes():
            if i18n.get_language_name(code) == selected_name:
                i18n.set_language(code)
                break
    
    def update_texts(self):
        """Update all texts when language changes"""
        self.root.title(i18n.get('login_title'))
        self.lang_label.config(text=i18n.get('language') + ':')
        self.title_label.config(text=i18n.get('login_header'))
        self.email_label.config(text=i18n.get('email'))
        self.password_label.config(text=i18n.get('password'))
        self.master_password_label.config(text=i18n.get('master_password'))
        self.login_button.config(text=i18n.get('login'))
        
        # Update 2FA fields if they exist
        if hasattr(self, 'tfa_label'):
            self.tfa_label.config(text=i18n.get('tfa_code'))
        if hasattr(self, 'tfa_help'):
            self.tfa_help.config(text=i18n.get('tfa_help'))
        
        # Update status label if it has login-related text
        current_text = self.status_label.cget('text')
        if 'Logging in' in current_text or 'جار تسجيل الدخول' in current_text:
            self.status_label.config(text=i18n.get('logging_in'))
        elif 'Login successful' in current_text or 'تم تسجيل الدخول بنجاح' in current_text:
            self.status_label.config(text=i18n.get('login_successful'))


class MainWindow(BaseWindow):
    """Main window with Terminal and File Sync tools"""
    def __init__(self):
        super().__init__(tk.Tk(), i18n.get('app_title'))
        self.logger = get_logger(__name__)
        self.runner = SubprocessRunner()
        # Start maximized
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
            # If maximizing fails, use default size
            self.logger.warning(f"Could not maximize window: {e}")
            self.center_window(1024, 768)
        
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
            self.status_bar.config(text=i18n.get('authentication_expired'), fg='red')
            messagebox.showerror(i18n.get('error'), 
                               i18n.get('session_expired'))
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
        user_text = f"{i18n.get('user')} {auth_info.get('email', 'Unknown')}"
        self.user_label = tk.Label(top_frame, text=user_text)
        self.user_label.pack(side='left', padx=10)
        
        # Logout button
        self.logout_button = ttk.Button(top_frame, text=i18n.get('logout'), command=self.logout)
        self.logout_button.pack(side='right', padx=10)
        
        # Language selector
        self.lang_combo = ttk.Combobox(top_frame, state='readonly', width=15)
        self.lang_combo['values'] = [i18n.get_language_name(code) for code in i18n.get_language_codes()]
        self.lang_combo.set(i18n.get_language_name(i18n.current_language))
        self.lang_combo.pack(side='right', padx=5)
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        self.lang_label = tk.Label(top_frame, text=i18n.get('language') + ':')
        self.lang_label.pack(side='right')
        
        # Common selection frame
        self.common_frame = tk.LabelFrame(self.root, text=i18n.get('resource_selection'))
        self.common_frame.pack(fill='x', padx=10, pady=5)
        
        # Team selection
        team_frame = tk.Frame(self.common_frame)
        team_frame.pack(fill='x', padx=10, pady=5)
        self.team_label = tk.Label(team_frame, text=i18n.get('team'), width=12, anchor='w')
        self.team_label.pack(side='left', padx=5)
        self.team_combo = ttk.Combobox(team_frame, width=40, state='readonly')
        self.team_combo.pack(side='left', padx=5, fill='x', expand=True)
        self.team_combo.bind('<<ComboboxSelected>>', lambda e: self.on_team_changed())
        
        # Machine selection
        machine_frame = tk.Frame(self.common_frame)
        machine_frame.pack(fill='x', padx=10, pady=5)
        self.machine_label = tk.Label(machine_frame, text=i18n.get('machine'), width=12, anchor='w')
        self.machine_label.pack(side='left', padx=5)
        self.machine_combo = ttk.Combobox(machine_frame, width=40, state='readonly')
        self.machine_combo.pack(side='left', padx=5, fill='x', expand=True)
        self.machine_combo.bind('<<ComboboxSelected>>', lambda e: self.on_machine_changed())
        
        # Repository selection
        repo_frame = tk.Frame(self.common_frame)
        repo_frame.pack(fill='x', padx=10, pady=5)
        self.repo_label = tk.Label(repo_frame, text=i18n.get('repository'), width=12, anchor='w')
        self.repo_label.pack(side='left', padx=5)
        self.repo_combo = ttk.Combobox(repo_frame, width=40, state='readonly')
        self.repo_combo.pack(side='left', padx=5, fill='x', expand=True)
        self.repo_combo.bind('<<ComboboxSelected>>', lambda e: self.on_repository_changed())
        # Add a filter indicator label
        self.repo_filter_label = tk.Label(repo_frame, text="", font=('Arial', 9), fg='gray')
        self.repo_filter_label.pack(side='left', padx=5)
        
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
        
        # Status bar
        self.status_bar = tk.Label(self.root, text=i18n.get('ready'),
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
        self.terminal_command_label = tk.Label(command_frame, text=i18n.get('command'), width=12, anchor='w')
        self.terminal_command_label.pack(side='left', padx=5)
        self.command_entry = ttk.Entry(command_frame)
        self.command_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        # Buttons
        button_frame = tk.Frame(control_frame)
        button_frame.pack(pady=10)
        
        self.execute_cmd_button = ttk.Button(button_frame, text=i18n.get('execute_command'),
                  command=self.execute_terminal_command)
        self.execute_cmd_button.pack(side='left', padx=5)
        self.open_repo_term_button = ttk.Button(button_frame, text=i18n.get('open_repo_terminal'),
                  command=self.open_repo_terminal)
        self.open_repo_term_button.pack(side='left', padx=5)
        self.open_machine_term_button = ttk.Button(button_frame, text=i18n.get('open_machine_terminal'),
                  command=self.open_machine_terminal)
        self.open_machine_term_button.pack(side='left', padx=5)
        
        # Output area
        output_frame = tk.Frame(self.terminal_frame)
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.terminal_output_label = tk.Label(output_frame, text=i18n.get('output'))
        self.terminal_output_label.pack(anchor='w')
        
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
        self.sync_direction_label = tk.Label(direction_frame, text=i18n.get('direction'), width=12, anchor='w')
        self.sync_direction_label.pack(side='left', padx=5)
        self.sync_direction = tk.StringVar(value='upload')
        self.upload_radio = ttk.Radiobutton(direction_frame, text=i18n.get('upload'), variable=self.sync_direction,
                       value='upload')
        self.upload_radio.pack(side='left', padx=5)
        self.download_radio = ttk.Radiobutton(direction_frame, text=i18n.get('download'), variable=self.sync_direction,
                       value='download')
        self.download_radio.pack(side='left', padx=5)
        
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
        
        option_container = tk.Frame(self.options_frame)
        option_container.pack(pady=5)
        
        self.mirror_var = tk.BooleanVar()
        self.mirror_check = tk.Checkbutton(option_container, text=i18n.get('mirror_delete'),
                      variable=self.mirror_var,
                      command=self.on_mirror_changed)
        self.mirror_check.pack(side='left', padx=10)
        
        self.verify_var = tk.BooleanVar()
        self.verify_check = tk.Checkbutton(option_container, text=i18n.get('verify_transfer'),
                      variable=self.verify_var)
        self.verify_check.pack(side='left', padx=10)
        
        self.confirm_var = tk.BooleanVar()
        self.confirm_check = tk.Checkbutton(option_container, text=i18n.get('preview_changes'),
                      variable=self.confirm_var)
        self.confirm_check.pack(side='left', padx=10)
        
        # Sync button
        self.sync_button = ttk.Button(control_frame, text=i18n.get('start_sync'),
                                    command=self.start_sync)
        self.sync_button.pack(pady=10)
        
        # Output area
        output_frame = tk.Frame(self.sync_frame)
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.sync_output_label = tk.Label(output_frame, text=i18n.get('output'))
        self.sync_output_label.pack(anchor='w')
        
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
        self.plugin_management_frame = tk.LabelFrame(self.plugin_frame, text=i18n.get('plugin_management'))
        paned.add(self.plugin_management_frame, minsize=300)
        
        # Create two columns inside the plugin management frame
        columns_frame = tk.Frame(self.plugin_management_frame)
        columns_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left column - Available plugins
        left_column = tk.Frame(columns_frame)
        left_column.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Available plugins label
        self.available_plugins_label = tk.Label(left_column, text=i18n.get('available_plugins'), font=('Arial', 10, 'bold'))
        self.available_plugins_label.pack(anchor='w', pady=(0, 5))
        
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
        self.refresh_plugins_button = ttk.Button(left_column, text=i18n.get('refresh_plugins'),
                  command=self.refresh_plugins)
        self.refresh_plugins_button.pack(pady=(10, 0))
        
        # Right column - Connect to plugin
        right_column = tk.Frame(columns_frame)
        right_column.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Connect to plugin label
        self.connect_plugin_label = tk.Label(right_column, text=i18n.get('connect_to_plugin'), font=('Arial', 10, 'bold'))
        self.connect_plugin_label.pack(anchor='w', pady=(0, 5))
        
        # Plugin selection
        plugin_select_frame = tk.Frame(right_column)
        plugin_select_frame.pack(fill='x', pady=(10, 5))
        
        self.plugin_select_label = tk.Label(plugin_select_frame, text=i18n.get('plugin'), width=12, anchor='w')
        self.plugin_select_label.pack(side='left')
        self.plugin_combo = ttk.Combobox(plugin_select_frame, width=20, state='readonly')
        self.plugin_combo.pack(side='left', fill='x', expand=True)
        
        # Port selection frame
        self.port_frame = tk.LabelFrame(right_column, text=i18n.get('local_port'))
        self.port_frame.pack(fill='x', pady=5)
        
        # Port mode variable
        self.port_mode = tk.StringVar(value='auto')
        
        # Auto port radio button
        auto_frame = tk.Frame(self.port_frame)
        auto_frame.pack(fill='x', padx=10, pady=5)
        self.auto_port_radio = ttk.Radiobutton(auto_frame, text=i18n.get('auto_port'), 
                       variable=self.port_mode, value='auto',
                       command=self.on_port_mode_changed)
        self.auto_port_radio.pack(side='left')
        
        # Manual port radio button and entry
        manual_frame = tk.Frame(self.port_frame)
        manual_frame.pack(fill='x', padx=10, pady=5)
        self.manual_port_radio = ttk.Radiobutton(manual_frame, text=i18n.get('manual_port'), 
                       variable=self.port_mode, value='manual',
                       command=self.on_port_mode_changed)
        self.manual_port_radio.pack(side='left')
        
        # Port entry with validation
        vcmd = (self.root.register(self.validate_port), '%P')
        self.port_entry = ttk.Entry(manual_frame, width=10, 
                                   validate='key', validatecommand=vcmd)
        self.port_entry.pack(side='left', padx=5)
        self.port_entry.insert(0, "7111")
        self.port_entry.config(state='disabled')  # Initially disabled
        
        # Connect button
        self.connect_button = ttk.Button(right_column, text=i18n.get('connect'),
                                       command=self.connect_plugin)
        self.connect_button.pack(pady=(10, 10))
        
        # Middle section - Active connections
        self.connections_frame = tk.LabelFrame(self.plugin_frame, text=i18n.get('active_connections'))
        paned.add(self.connections_frame, minsize=200)
        
        # Treeview for connections
        tree_frame = tk.Frame(self.connections_frame)
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
                self.status_bar.config(text=f"{i18n.get('error')}: {error_msg}", fg='red')
    
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
                self.status_bar.config(text=f"{i18n.get('error')}: {error_msg}", fg='red')
    
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
                                self.repo_filter_label.config(text="(machine-specific)", fg='green')
                                status_text = f"Showing {len(repos)} repositories for machine '{machine}'"
                                self.status_bar.config(text=status_text, fg='green')
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
                self.status_bar.config(text=f"{i18n.get('error')}: {error_msg}", fg='red')
    
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
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        command = self.command_entry.get().strip()
        
        if not team or not machine or not repo or not command:
            messagebox.showerror(i18n.get('error'), i18n.get('select_all_fields'))
            return
        
        self.terminal_output.config(state='normal')  # Enable for clearing
        self.terminal_output.delete(1.0, tk.END)
        self.terminal_output.config(state='disabled')  # Disable again
        self.status_bar.config(text=i18n.get('executing_command'))
        
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
        self.status_bar.config(text=i18n.get('command_executed'))
    
    

    def _launch_terminal(self, command: str, description: str):
        """Common method to launch terminal with given command"""
        # Build command with full path
        import os
        # __file__ is in src/cli/, so we need to go up two levels to get to cli/
        # src/cli/rediacc-cli-gui.py -> src/ -> cli/
        cli_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Build the simple command for display
        rediacc_path = os.path.join(cli_dir, 'rediacc')
        simple_cmd = f'{rediacc_path} {command}'
        
        # Show command in output area
        self.terminal_output.config(state='normal')  # Enable for writing
        self.terminal_output.delete(1.0, tk.END)
        self.terminal_output.insert(tk.END, i18n.get('terminal_instructions', description=description) + "\n\n")
        self.terminal_output.insert(tk.END, simple_cmd + "\n\n")
        self.terminal_output.insert(tk.END, i18n.get('or_from_any_directory') + "\n\n")
        self.terminal_output.insert(tk.END, f'cd {cli_dir} && {simple_cmd}\n\n')
        self.terminal_output.config(state='disabled')  # Disable again
        
        # Use terminal detector to find best method
        method = self.terminal_detector.detect()
        
        if method:
            launch_func = self.terminal_detector.get_launch_function(method)
            if launch_func:
                try:
                    # Launch using detected method
                    launch_func(cli_dir, command, description)
                    self.terminal_output.config(state='normal')
                    self.terminal_output.insert(tk.END, f"\n{i18n.get('launched_terminal')} ({method})\n")
                    self.terminal_output.config(state='disabled')
                except Exception as e:
                    self.logger.error(f"Failed to launch with {method}: {e}")
                    self.terminal_output.config(state='normal')
                    self.terminal_output.insert(tk.END, f"\n{i18n.get('could_not_launch')}\n")
                    self.terminal_output.config(state='disabled')
            else:
                self.logger.warning(f"No launch function for method: {method}")
                self.terminal_output.config(state='normal')
                self.terminal_output.insert(tk.END, f"\n{i18n.get('could_not_launch')}\n")
                self.terminal_output.config(state='disabled')
        else:
            self.logger.error("No working terminal method detected")
            self.terminal_output.config(state='normal')
            self.terminal_output.insert(tk.END, f"\n{i18n.get('could_not_launch')} - No terminal method available\n")
            self.terminal_output.config(state='disabled')
    
    def open_repo_terminal(self):
        """Open interactive repository terminal in new window"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        repo = self.repo_combo.get()
        
        if not team or not machine or not repo:
            messagebox.showerror(i18n.get('error'), i18n.get('select_team_machine_repo'))
            return
        
        command = f'term --team "{team}" --machine "{machine}" --repo "{repo}"'
        self._launch_terminal(command, i18n.get('an_interactive_repo_terminal'))
    
    def open_machine_terminal(self):
        """Open interactive machine terminal in new window (without repository)"""
        team = self.team_combo.get()
        machine = self.machine_combo.get()
        
        if not team or not machine:
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
            messagebox.showerror(i18n.get('error'), i18n.get('fill_all_fields'))
            return
        
        # Show sync progress dialog
        self.show_sync_progress(direction, team, machine, repo, local_path)
    
    def show_sync_progress(self, direction: str, team: str, machine: str, repo: str, local_path: str):
        """Show sync progress dialog"""
        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title(i18n.get('sync_progress', 'Sync Progress'))
        progress_dialog.geometry('700x600')
        progress_dialog.transient(self.root)
        
        # Center the dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() - 700) // 2
        y = (progress_dialog.winfo_screenheight() - 600) // 2
        progress_dialog.geometry(f'700x600+{x}+{y}')
        
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
                               font=('Arial', 10), fg='blue' if self.confirm_var.get() else 'black')
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
        output_text = scrolledtext.ScrolledText(output_frame, wrap='word', 
                                               font=('Consolas', 9))
        output_text.pack(fill='both', expand=True, padx=5, pady=5)
        
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
                progress_dialog.after(0, lambda: status_label.config(text=msg, fg='red'))
                progress_dialog.after(0, lambda: close_button.config(state='normal'))
                progress_dialog.after(0, lambda: progress_dialog.protocol('WM_DELETE_WINDOW', progress_dialog.destroy))
                progress_dialog.after(0, progress_bar.stop)
            finally:
                # Re-enable sync button
                self.root.after(0, lambda: self.sync_button.config(state='normal'))
                self.root.after(0, lambda: self.status_bar.config(text=i18n.get('ready')))
        
        thread = threading.Thread(target=do_sync)
        thread.daemon = True
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
        
        thread = threading.Thread(target=load)
        thread.daemon = True
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
        
        self.status_bar.config(text=i18n.get('found_connections', count=len(connections)))
    
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
                url = None
                for line in output.split('\n'):
                    if 'Local URL:' in line:
                        url = line.split('Local URL:')[1].strip()
                        break
                
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
        
        thread = threading.Thread(target=connect)
        thread.daemon = True
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
            
            thread = threading.Thread(target=disconnect)
            thread.daemon = True
            thread.start()
    
    def open_plugin_url(self):
        """Open plugin URL in browser"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror(i18n.get('error'), i18n.get('select_connection', action=i18n.get('open_in_browser').lower()))
            return
        
        item = self.connections_tree.item(selection[0])
        url = item['values'][1]  # URL is second column
        
        # Open URL in default browser
        import webbrowser
        webbrowser.open(url)
        
        self.status_bar.config(text=i18n.get('opened_in_browser', url=url))
    
    def copy_plugin_url(self):
        """Copy plugin URL to clipboard"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showerror(i18n.get('error'), i18n.get('select_connection', action=i18n.get('copy_url').lower()))
            return
        
        item = self.connections_tree.item(selection[0])
        url = item['values'][1]  # URL is second column
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.root.update()  # Required on Windows
        
        # Show confirmation in status bar
        self.status_bar.config(text=i18n.get('copied_to_clipboard', url=url), fg='green')
        
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
        if current_text == 'Ready' or current_text == 'جاهز' or current_text == 'Bereit':
            self.status_bar.config(text=i18n.get('ready'))
        
        # Update each tab's contents
        self.update_plugin_tab_texts()
        self.update_terminal_tab_texts()
        self.update_sync_tab_texts()
        self.update_file_browser_tab_texts()
    
    def update_plugin_tab_texts(self):
        """Update all texts in plugin tab"""
        self.plugin_management_frame.config(text=i18n.get('plugin_management'))
        self.available_plugins_label.config(text=i18n.get('available_plugins'))
        self.refresh_plugins_button.config(text=i18n.get('refresh_plugins'))
        self.connect_plugin_label.config(text=i18n.get('connect_to_plugin'))
        self.plugin_select_label.config(text=i18n.get('plugin'))
        self.port_frame.config(text=i18n.get('local_port'))
        self.auto_port_radio.config(text=i18n.get('auto_port'))
        self.manual_port_radio.config(text=i18n.get('manual_port'))
        self.connect_button.config(text=i18n.get('connect'))
        self.connections_frame.config(text=i18n.get('active_connections'))
        self.open_browser_button.config(text=i18n.get('open_in_browser'))
        self.copy_url_button.config(text=i18n.get('copy_url'))
        self.disconnect_button.config(text=i18n.get('disconnect'))
        self.refresh_status_button.config(text=i18n.get('refresh_status'))
        self.plugin_info_label.config(text=i18n.get('plugin_tip'))
    
    def update_terminal_tab_texts(self):
        """Update all texts in terminal tab"""
        self.terminal_command_label.config(text=i18n.get('command'))
        self.execute_cmd_button.config(text=i18n.get('execute_command'))
        self.open_repo_term_button.config(text=i18n.get('open_repo_terminal'))
        self.open_machine_term_button.config(text=i18n.get('open_machine_terminal'))
        self.terminal_output_label.config(text=i18n.get('output'))
    
    def update_sync_tab_texts(self):
        """Update all texts in sync tab"""
        self.sync_direction_label.config(text=i18n.get('direction'))
        self.upload_radio.config(text=i18n.get('upload'))
        self.download_radio.config(text=i18n.get('download'))
        self.local_path_label.config(text=i18n.get('local_path'))
        self.browse_button.config(text=i18n.get('browse'))
        self.options_frame.config(text=i18n.get('options'))
        self.mirror_check.config(text=i18n.get('mirror_delete'))
        self.verify_check.config(text=i18n.get('verify_transfer'))
        self.confirm_check.config(text=i18n.get('preview_changes'))
        self.sync_button.config(text=i18n.get('start_sync'))
        self.sync_output_label.config(text=i18n.get('output'))
    
    def update_file_browser_tab_texts(self):
        """Update all texts in file browser tab"""
        if hasattr(self, 'file_browser'):
            self.file_browser.update_texts()
    
    def create_file_browser_tab(self):
        """Create dual-pane file browser interface"""
        # Create instance of DualPaneFileBrowser
        self.file_browser = DualPaneFileBrowser(self.browser_frame, self)


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
        
        self.create_widgets()
        self.setup_drag_drop()
        self.setup_keyboard_shortcuts()
        self.refresh_local()
    
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
        
        # After all panes are added, configure transfer pane width limiting
        def limit_transfer_pane_width(event=None):
            try:
                # Get current sash positions
                sash_0 = self.paned_window.sash_coord(0)[0]  # Left edge of transfer pane
                sash_1 = self.paned_window.sash_coord(1)[0]  # Right edge of transfer pane
                
                # Calculate transfer pane width
                transfer_width = sash_1 - sash_0
                
                # Limit maximum width to 180 pixels
                max_width = 180
                if transfer_width > max_width:
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
        
        # Preview pane
        self.preview_frame = tk.LabelFrame(self.preview_container, text=i18n.get('file_preview', 'File Preview'))
        self.preview_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Preview controls
        preview_controls = tk.Frame(self.preview_frame)
        preview_controls.pack(fill='x', padx=5, pady=5)
        
        self.preview_filename_label = tk.Label(preview_controls, text='', font=('Arial', 10, 'bold'))
        self.preview_filename_label.pack(side='left', padx=5)
        
        self.preview_close_button = ttk.Button(preview_controls, text='×', width=3,
                                             command=self.hide_preview)
        self.preview_close_button.pack(side='right')
        
        # Preview content
        preview_scroll_frame = tk.Frame(self.preview_frame)
        preview_scroll_frame.pack(fill='both', expand=True, padx=5, pady=(0, 5))
        
        self.preview_text = scrolledtext.ScrolledText(preview_scroll_frame, height=10, 
                                                     font=('Consolas', 9), wrap='none')
        self.preview_text.pack(fill='both', expand=True)
        self.preview_text.config(state='disabled')
        
        # Horizontal scrollbar for preview
        preview_hsb = ttk.Scrollbar(preview_scroll_frame, orient='horizontal', 
                                   command=self.preview_text.xview)
        preview_hsb.pack(fill='x')
        self.preview_text.config(xscrollcommand=preview_hsb.set)
        
        # Status bar (at the very bottom)
        self.status_frame = tk.Frame(main_frame)
        self.status_frame.pack(fill='x', side='bottom', pady=(5, 0))
        
        self.status_label = tk.Label(self.status_frame, text=i18n.get('ready', 'Ready'), anchor='w')
        self.status_label.pack(side='left', fill='x', expand=True)
        
        # Preview toggle button in status bar
        self.preview_toggle_button = ttk.Button(self.status_frame, 
                                              text=i18n.get('show_preview', 'Show Preview'),
                                              command=self.toggle_preview)
        self.preview_toggle_button.pack(side='right', padx=5)
    
    def create_local_pane(self):
        """Create the local file browser pane"""
        # Container frame
        self.local_frame = tk.LabelFrame(self.paned_window, text=i18n.get('local_files', 'Local Files'))
        self.paned_window.add(self.local_frame, minsize=400)
        
        # Path navigation frame
        nav_frame = tk.Frame(self.local_frame)
        nav_frame.pack(fill='x', padx=5, pady=5)
        
        # Navigation buttons with tooltips
        self.local_up_button = ttk.Button(nav_frame, text='↑', width=3,
                                         command=self.navigate_local_up)
        self.local_up_button.pack(side='left', padx=2)
        create_tooltip(self.local_up_button, i18n.get('navigate_up_tooltip', 'Navigate to parent folder'))
        
        self.local_home_button = ttk.Button(nav_frame, text='🏠', width=3,
                                           command=self.navigate_local_home)
        self.local_home_button.pack(side='left', padx=2)
        create_tooltip(self.local_home_button, i18n.get('navigate_home_tooltip', 'Go to home directory'))
        
        self.local_refresh_button = ttk.Button(nav_frame, text='↻', width=3,
                                              command=self.refresh_local)
        self.local_refresh_button.pack(side='left', padx=2)
        create_tooltip(self.local_refresh_button, i18n.get('refresh_tooltip', 'Refresh file list'))
        
        # Path entry
        self.local_path_var = tk.StringVar(value=str(self.local_current_path))
        self.local_path_entry = ttk.Entry(nav_frame, textvariable=self.local_path_var, state='readonly')
        self.local_path_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        # Search frame
        search_frame = tk.Frame(self.local_frame)
        search_frame.pack(fill='x', padx=5, pady=(5, 0))
        
        self.local_search_label = tk.Label(search_frame, text=i18n.get('search', 'Search:'))
        self.local_search_label.pack(side='left', padx=5)
        
        self.local_search_var = tk.StringVar()
        self.local_search_entry = ttk.Entry(search_frame, textvariable=self.local_search_var)
        self.local_search_entry.pack(side='left', fill='x', expand=True, padx=5)
        # Use trace to update on every keystroke
        self.local_search_var.trace('w', lambda *args: self.on_local_search_changed())
        
        self.local_clear_button = ttk.Button(search_frame, text=i18n.get('clear', 'Clear'), 
                                           command=self.clear_local_search)
        self.local_clear_button.pack(side='left', padx=5)
        
        # File list with scrollbar
        list_frame = tk.Frame(self.local_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=(0, 5))
        
        # Create Treeview
        columns = ('size', 'modified', 'type')
        self.local_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Define columns
        self.local_tree.heading('#0', text='Name', command=lambda: self.sort_local('name'))
        self.local_tree.heading('size', text='Size', command=lambda: self.sort_local('size'))
        self.local_tree.heading('modified', text='Modified', command=lambda: self.sort_local('modified'))
        self.local_tree.heading('type', text='Type', command=lambda: self.sort_local('type'))
        
        # Column widths
        self.local_tree.column('#0', width=250)
        self.local_tree.column('size', width=80)
        self.local_tree.column('modified', width=150)
        self.local_tree.column('type', width=80)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.local_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient='horizontal', command=self.local_tree.xview)
        self.local_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.local_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
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
        # Container frame for buttons
        self.transfer_frame = tk.Frame(self.paned_window, bg='#f0f0f0')
        # Add with constraints - minsize prevents it from being too small
        self.paned_window.add(self.transfer_frame, minsize=120, width=140)
        
        # Add title
        title_label = tk.Label(self.transfer_frame, text=i18n.get('transfer_actions', 'Transfer Actions'),
                              font=('Arial', 10, 'bold'), bg='#f0f0f0')
        title_label.pack(pady=(10, 5))
        
        # Center buttons vertically
        button_container = tk.Frame(self.transfer_frame, bg='#f0f0f0')
        button_container.place(relx=0.5, rely=0.5, anchor='center')
        
        # Upload button
        self.upload_button = ttk.Button(button_container, text=i18n.get('upload_arrow', 'Upload →'), 
                                       command=self.upload_selected, state='disabled',
                                       width=15)
        self.upload_button.pack(pady=10)
        create_tooltip(self.upload_button, i18n.get('upload_tooltip', 'Upload selected files to remote'))
        
        # Download button
        self.download_button = ttk.Button(button_container, text=i18n.get('download_arrow', '← Download'), 
                                         command=self.download_selected, state='disabled',
                                         width=15)
        self.download_button.pack(pady=10)
        create_tooltip(self.download_button, i18n.get('download_tooltip', 'Download selected files from remote'))
        
        # Options button
        self.options_button = ttk.Button(button_container, text=i18n.get('options', 'Options'), 
                                       command=self.show_transfer_options,
                                       width=15)
        self.options_button.pack(pady=10)
        create_tooltip(self.options_button, i18n.get('options_tooltip', 'Configure transfer options'))
        
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
        conn_frame.pack(fill='x', padx=5, pady=5)
        
        self.conn_status_label = tk.Label(conn_frame, text=i18n.get('not_connected', 'Not connected'), fg='red')
        self.conn_status_label.pack(side='left')
        
        self.connect_button = ttk.Button(conn_frame, text=i18n.get('connect', 'Connect'), command=self.connect_remote)
        self.connect_button.pack(side='right')
        
        # Path navigation frame
        nav_frame = tk.Frame(self.remote_frame)
        nav_frame.pack(fill='x', padx=5, pady=5)
        
        # Navigation buttons
        self.remote_up_button = ttk.Button(nav_frame, text='↑', width=3,
                                          command=self.navigate_remote_up, state='disabled')
        self.remote_up_button.pack(side='left', padx=2)
        create_tooltip(self.remote_up_button, i18n.get('navigate_up_tooltip', 'Navigate to parent folder'))
        
        self.remote_home_button = ttk.Button(nav_frame, text='🏠', width=3,
                                            command=self.navigate_remote_home, state='disabled')
        self.remote_home_button.pack(side='left', padx=2)
        create_tooltip(self.remote_home_button, i18n.get('navigate_home_tooltip', 'Go to home directory'))
        
        self.remote_refresh_button = ttk.Button(nav_frame, text='↻', width=3,
                                               command=self.refresh_remote, state='disabled')
        self.remote_refresh_button.pack(side='left', padx=2)
        create_tooltip(self.remote_refresh_button, i18n.get('refresh_tooltip', 'Refresh file list'))
        
        # Path entry
        self.remote_path_var = tk.StringVar(value=self.remote_current_path)
        self.remote_path_entry = ttk.Entry(nav_frame, textvariable=self.remote_path_var, state='readonly')
        self.remote_path_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        # Search frame
        search_frame = tk.Frame(self.remote_frame)
        search_frame.pack(fill='x', padx=5, pady=(5, 0))
        
        self.remote_search_label = tk.Label(search_frame, text=i18n.get('search', 'Search:'))
        self.remote_search_label.pack(side='left', padx=5)
        
        self.remote_search_var = tk.StringVar()
        self.remote_search_entry = ttk.Entry(search_frame, textvariable=self.remote_search_var, state='disabled')
        self.remote_search_entry.pack(side='left', fill='x', expand=True, padx=5)
        # Use trace to update on every keystroke
        self.remote_search_var.trace('w', lambda *args: self.on_remote_search_changed())
        
        self.remote_clear_button = ttk.Button(search_frame, text=i18n.get('clear', 'Clear'), 
                                            command=self.clear_remote_search, state='disabled')
        self.remote_clear_button.pack(side='left', padx=5)
        
        # File list with scrollbar
        list_frame = tk.Frame(self.remote_frame)
        list_frame.pack(fill='both', expand=True, padx=5, pady=(0, 5))
        
        # Create Treeview
        columns = ('size', 'modified', 'type')
        self.remote_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Define columns
        self.remote_tree.heading('#0', text='Name', command=lambda: self.sort_remote('name'))
        self.remote_tree.heading('size', text='Size', command=lambda: self.sort_remote('size'))
        self.remote_tree.heading('modified', text='Modified', command=lambda: self.sort_remote('modified'))
        self.remote_tree.heading('type', text='Type', command=lambda: self.sort_remote('type'))
        
        # Column widths
        self.remote_tree.column('#0', width=250)
        self.remote_tree.column('size', width=80)
        self.remote_tree.column('modified', width=150)
        self.remote_tree.column('type', width=80)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.remote_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient='horizontal', command=self.remote_tree.xview)
        self.remote_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.remote_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.remote_tree.bind('<Double-Button-1>', self.on_remote_double_click)
        self.remote_tree.bind('<<TreeviewSelect>>', self.on_remote_selection_changed)
        self.remote_tree.bind('<Button-3>', self.show_remote_context_menu)  # Right-click
        self.remote_tree.bind('<space>', lambda e: self.preview_selected_file('remote'))  # Space to preview
        
        # Configure for multi-select
        self.remote_tree.configure(selectmode='extended')
    
    def format_size(self, size: int) -> str:
        """Format file size for display"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def format_time(self, timestamp: float) -> str:
        """Format timestamp for display"""
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    
    def refresh_local(self):
        """Refresh local file list"""
        try:
            # List directory contents
            self.local_files = []
            for path in self.local_current_path.iterdir():
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
            self.logger.error(f"Error refreshing local files: {e}")
            messagebox.showerror(i18n.get('error', 'Error'), 
                               i18n.get('failed_list_local', f'Failed to list local directory: {str(e)}'))
    
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
        
        # Add items to tree
        for item in sorted_files:
            size_text = '' if item['is_dir'] else self.format_size(item['size'])
            modified_text = self.format_time(item['modified'])
            
            # Insert with folder/file icon
            icon = '📁 ' if item['is_dir'] else '📄 '
            self.local_tree.insert('', 'end', text=icon + item['name'],
                                  values=(size_text, modified_text, item['type']),
                                  tags=('dir' if item['is_dir'] else 'file',))
        
        # Update path display
        self.local_path_var.set(str(self.local_current_path))
        
        # Update status with filter info
        status_text = i18n.get('local_items', 'Local: {count} items').format(count=len(sorted_files))
        if self.local_filter:
            status_text += f" ({i18n.get('filtered', 'filtered')})"
        self.status_label.config(text=status_text)
    
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
        self.conn_status_label.config(text=i18n.get('connecting', 'Connecting...'), fg='orange')
        
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
        
        thread = threading.Thread(target=do_connect)
        thread.daemon = True
        thread.start()
    
    def on_remote_connected(self):
        """Handle successful remote connection"""
        self.conn_status_label.config(text=i18n.get('connected', 'Connected'), fg='green')
        self.connect_button.config(text=i18n.get('disconnect', 'Disconnect'), state='normal')
        self.connect_button.config(command=self.disconnect_remote)
        
        # Enable remote controls
        self.remote_up_button.config(state='normal')
        self.remote_home_button.config(state='normal')
        self.remote_refresh_button.config(state='normal')
        self.remote_path_entry.config(state='readonly')
        self.remote_search_entry.config(state='normal')
        self.remote_clear_button.config(state='normal')
        
        # Refresh remote file list
        self.refresh_remote()
    
    def on_remote_connect_failed(self, error: str):
        """Handle failed remote connection"""
        self.conn_status_label.config(text=i18n.get('not_connected', 'Not connected'), fg='red')
        self.connect_button.config(state='normal')
        messagebox.showerror(i18n.get('connection_failed', 'Connection Failed'), 
                           i18n.get('failed_connect_remote', f'Failed to connect to remote: {error}'))
    
    def disconnect_remote(self):
        """Disconnect from remote repository"""
        if self.ssh_connection:
            # Clean up SSH connection
            if hasattr(self.ssh_connection, 'cleanup_ssh'):
                self.ssh_connection.cleanup_ssh(getattr(self.ssh_connection, 'ssh_key_file', None),
                                               getattr(self.ssh_connection, 'known_hosts_file', None))
            self.ssh_connection = None
        
        # Clear remote tree
        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)
        
        # Update UI
        self.conn_status_label.config(text=i18n.get('not_connected', 'Not connected'), fg='red')
        self.connect_button.config(text=i18n.get('connect', 'Connect'), command=self.connect_remote)
        
        # Disable remote controls
        self.remote_up_button.config(state='disabled')
        self.remote_home_button.config(state='disabled')
        self.remote_refresh_button.config(state='disabled')
        self.remote_path_entry.config(state='readonly')
        self.remote_search_entry.config(state='disabled')
        self.remote_clear_button.config(state='disabled')
        
        # Clear search
        self.remote_search_var.set('')
        self.remote_filter = ''
        
        # Clear selection and disable transfer buttons
        self.remote_selected = []
        self.update_transfer_buttons()
    
    def execute_remote_command(self, command: str) -> Tuple[bool, str]:
        """Execute command on remote via SSH"""
        if not self.ssh_connection:
            return False, "Not connected"
        
        try:
            # Set up SSH if needed
            ssh_opts, ssh_key_file, known_hosts_file = self.ssh_connection.setup_ssh()
            
            # Build SSH command
            ssh_cmd = ['ssh'] + ssh_opts.split() + [self.ssh_connection.ssh_destination]
            
            # Add sudo if we have universal_user
            universal_user = self.ssh_connection.connection_info.get('universal_user')
            if universal_user:
                ssh_cmd.extend(['sudo', '-u', universal_user])
            
            # Add the actual command
            ssh_cmd.append(command)
            
            # Execute
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
    
    def parse_ls_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse ls -la output into file information"""
        files = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if not line or line.startswith('total'):
                continue
            
            # Parse ls -la output format
            # Example: drwxr-xr-x 2 user group 4096 Dec 15 10:30 dirname
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            
            perms = parts[0]
            size = int(parts[4]) if parts[4].isdigit() else 0
            name = parts[8]
            
            # Handle symbolic links
            if perms.startswith('l') and ' -> ' in name:
                # Extract link name (before ->)
                name = name.split(' -> ')[0]
            
            # Skip . and ..
            if name in ['.', '..']:
                continue
            
            # Determine if directory or link to directory
            is_dir = perms.startswith('d') or perms.startswith('l')
            
            # Parse modification time
            try:
                # Try to parse the date
                month = parts[5]
                day = parts[6]
                time_or_year = parts[7]
                
                # For now, use current time as approximation
                # TODO: Proper date parsing
                modified = time.time()
            except:
                modified = time.time()
            
            files.append({
                'name': name,
                'is_dir': is_dir,
                'size': size,
                'modified': modified,
                'type': i18n.get('folder', 'Folder') if is_dir else i18n.get('file', 'File'),
                'perms': perms
            })
        
        return files
    
    def refresh_remote(self):
        """Refresh remote file list"""
        if not self.ssh_connection:
            return
        
        self.status_label.config(text=i18n.get('loading_remote_files', 'Loading remote files...'))
        
        def do_refresh():
            try:
                # Execute ls command
                success, output = self.execute_remote_command(f'ls -la "{self.remote_current_path}"')
                
                if success:
                    files = self.parse_ls_output(output)
                    self.parent.after(0, lambda: self.update_remote_tree(files))
                else:
                    self.parent.after(0, lambda: messagebox.showerror(i18n.get('error', 'Error'), 
                                                                     i18n.get('failed_list_remote', f'Failed to list remote directory: {output}')))
                    
            except Exception as e:
                self.logger.error(f"Error refreshing remote files: {e}")
                self.parent.after(0, lambda: messagebox.showerror(i18n.get('error', 'Error'), 
                                                                 i18n.get('failed_refresh_remote', f'Failed to refresh remote: {str(e)}')))
        
        thread = threading.Thread(target=do_refresh)
        thread.daemon = True
        thread.start()
    
    def update_remote_tree(self, files: List[Dict[str, Any]]):
        """Update remote tree with file list"""
        # Store files for sorting
        self.remote_files = files
        # Display sorted files
        self.display_remote_files()
    
    def on_remote_search_changed(self):
        """Handle remote search text change"""
        self.remote_filter = self.remote_search_var.get().lower()
        self.display_remote_files()
    
    def clear_remote_search(self):
        """Clear remote search filter"""
        self.remote_search_var.set('')
        self.remote_filter = ''
        self.display_remote_files()
    
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
        
        # Add items to tree
        for item in sorted_files:
            size_text = '' if item['is_dir'] else self.format_size(item['size'])
            modified_text = self.format_time(item['modified'])
            
            # Insert with folder/file icon
            icon = '📁 ' if item['is_dir'] else '📄 '
            self.remote_tree.insert('', 'end', text=icon + item['name'],
                                   values=(size_text, modified_text, item['type']),
                                   tags=('dir' if item['is_dir'] else 'file',))
        
        # Update path display
        self.remote_path_var.set(self.remote_current_path)
        
        # Update status with filter info
        status_text = i18n.get('remote_items', 'Remote: {count} items').format(count=len(sorted_files))
        if self.remote_filter:
            status_text += f" ({i18n.get('filtered', 'filtered')})"
        self.status_label.config(text=status_text)
    
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
        for col in ['name', 'size', 'modified', 'type']:
            if col == 'name':
                header = i18n.get('name', 'Name')
            else:
                header = i18n.get(col, col.capitalize())
            
            if col == column:
                # Add sort indicator
                indicator = ' ▼' if self.remote_sort_reverse else ' ▲'
                header += indicator
            
            if col == 'name':
                self.remote_tree.heading('#0', text=header)
            else:
                self.remote_tree.heading(col, text=header)
        
        # Re-sort and display files
        self.display_remote_files()
    
    def update_transfer_buttons(self):
        """Update transfer button states based on selections"""
        # Enable upload if local items selected and connected
        can_upload = bool(self.local_selected and self.ssh_connection)
        self.upload_button.config(state='normal' if can_upload else 'disabled')
        
        # Enable download if remote items selected and connected
        can_download = bool(self.remote_selected and self.ssh_connection)
        self.download_button.config(state='normal' if can_download else 'disabled')
    
    def get_selected_paths(self, tree: ttk.Treeview, base_path) -> List[Tuple[str, bool]]:
        """Get selected file paths from tree"""
        paths = []
        for item_id in tree.selection():
            item = tree.item(item_id)
            name = item['text'][2:]  # Remove icon
            is_dir = 'dir' in item['tags']
            
            if isinstance(base_path, Path):
                full_path = base_path / name
            else:
                # Remote path
                full_path = base_path.rstrip('/') + '/' + name
            
            paths.append((str(full_path), is_dir))
        
        return paths
    
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
                                    import re
                                    match = re.search(r'(\d+)%', line)
                                    if match:
                                        percent = int(match.group(1))
                                        progress_callback(percent, line.strip())
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
    
    def show_transfer_progress(self, direction: str, paths: List[Tuple[str, bool]]):
        """Show transfer progress dialog"""
        # Create progress dialog
        progress_dialog = tk.Toplevel(self.parent)
        progress_dialog.title(i18n.get('transfer_progress', 'Transfer Progress'))
        progress_dialog.geometry('600x500')
        progress_dialog.transient(self.parent)
        
        # Center the dialog
        progress_dialog.update_idletasks()
        x = (progress_dialog.winfo_screenwidth() - 600) // 2
        y = (progress_dialog.winfo_screenheight() - 500) // 2
        progress_dialog.geometry(f'600x500+{x}+{y}')
        
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
                               font=('Arial', 10), fg='blue' if self.transfer_options.get('dry_run', False) else 'black')
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
        details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap='word', 
                                                font=('Consolas', 9))
        details_text.pack(fill='both', expand=True, padx=5, pady=5)
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
                    text=msg, fg='green' if success else 'red'
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
                    text=i18n.get('transfer_error', f'Error: {str(e)}'), fg='red'
                ))
                progress_dialog.after(0, lambda: close_button.config(state='normal'))
                progress_dialog.after(0, lambda: progress_dialog.protocol('WM_DELETE_WINDOW', progress_dialog.destroy))
                self.parent.after(0, lambda: self.on_transfer_complete(str(e), False))
        
        thread = threading.Thread(target=do_transfer)
        thread.daemon = True
        thread.start()
    
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
    
    def on_transfer_complete(self, message: str, success: bool):
        """Handle transfer completion"""
        # Re-enable buttons
        self.update_transfer_buttons()
        
        # Update status
        self.status_label.config(text=message)
        
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
            self.conn_status_label.config(text=i18n.get('connected', 'Connected'))
            self.connect_button.config(text=i18n.get('disconnect', 'Disconnect'))
        else:
            self.conn_status_label.config(text=i18n.get('not_connected', 'Not connected'))
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
        
        # Update transfer options button
        if hasattr(self, 'options_button'):
            self.options_button.config(text=i18n.get('options', 'Options'))
        
        # Update search labels and buttons
        if hasattr(self, 'local_search_label'):
            self.local_search_label.config(text=i18n.get('search', 'Search:'))
            self.local_clear_button.config(text=i18n.get('clear', 'Clear'))
            self.remote_search_label.config(text=i18n.get('search', 'Search:'))
            self.remote_clear_button.config(text=i18n.get('clear', 'Clear'))
    
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
            # Highlight drop target
            if pane == 'local':
                self.local_frame.config(relief='solid', borderwidth=2)
            else:
                self.remote_frame.config(relief='solid', borderwidth=2)
    
    def on_drag_leave(self, event, pane):
        """Handle drag leave to remove feedback"""
        # Remove highlight
        if pane == 'local':
            self.local_frame.config(relief='groove', borderwidth=2)
        else:
            self.remote_frame.config(relief='groove', borderwidth=2)
    
    def handle_drop(self, source: str, target: str):
        """Handle file drop between panes"""
        if not self.ssh_connection:
            messagebox.showwarning(i18n.get('warning', 'Warning'),
                                 i18n.get('connect_first', 'Please connect to remote first'))
            return
        
        # Get selected files from source
        if source == 'local' and target == 'remote':
            # Upload operation
            paths = self.get_selected_paths(self.local_tree, self.local_current_path)
            if paths:
                # Confirm operation
                file_list = '\n'.join([f"{'[DIR] ' if is_dir else ''}{Path(p).name}" for p, is_dir in paths])
                if messagebox.askyesno(i18n.get('confirm_upload', 'Confirm Upload'),
                                     i18n.get('drag_upload_confirm', f'Upload these files to {self.remote_current_path}?\n\n{file_list}')):
                    self.show_transfer_progress('upload', paths)
        
        elif source == 'remote' and target == 'local':
            # Download operation
            paths = self.get_selected_paths(self.remote_tree, self.remote_current_path)
            if paths:
                # Confirm operation
                file_list = '\n'.join([f"{'[DIR] ' if is_dir else ''}{Path(p).name}" for p, is_dir in paths])
                if messagebox.askyesno(i18n.get('confirm_download', 'Confirm Download'),
                                     i18n.get('drag_download_confirm', f'Download these files to {self.local_current_path}?\n\n{file_list}')):
                    self.show_transfer_progress('download', paths)
    
    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts"""
        # F5 - Refresh
        self.parent.bind_all('<F5>', lambda e: self.refresh_all())
        
        # Ctrl+A - Select all in focused pane
        self.parent.bind_all('<Control-a>', lambda e: self.select_all())
        
        # Delete - Delete selected files (with confirmation)
        self.parent.bind_all('<Delete>', lambda e: self.delete_selected())
        
        # Ctrl+X - Cut (prepare for move)
        self.parent.bind_all('<Control-x>', lambda e: self.cut_selected())
        
        # Ctrl+C - Copy (prepare for copy)
        self.parent.bind_all('<Control-c>', lambda e: self.copy_selected())
        
        # Ctrl+V - Paste (execute move/copy)
        self.parent.bind_all('<Control-v>', lambda e: self.paste_files())
        
        # F2 - Rename
        self.parent.bind_all('<F2>', lambda e: self.rename_selected())
        
        # Ctrl+F - Focus search
        self.parent.bind_all('<Control-f>', lambda e: self.focus_search())
        
        # Escape - Clear search
        self.parent.bind_all('<Escape>', lambda e: self.clear_search())
    
    def refresh_all(self):
        """Refresh both panes"""
        self.refresh_local()
        if self.ssh_connection:
            self.refresh_remote()
    
    def select_all(self):
        """Select all items in focused pane"""
        # Determine which tree has focus
        focused = self.parent.focus_get()
        
        if focused == self.local_tree or focused in [self.local_search_entry, self.local_path_entry]:
            # Select all in local tree
            self.local_tree.selection_set(self.local_tree.get_children())
        elif focused == self.remote_tree or focused in [self.remote_search_entry, self.remote_path_entry]:
            # Select all in remote tree
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
            # Calculate half of the current vertical space
            self.vertical_paned.update_idletasks()
            total_height = self.vertical_paned.winfo_height()
            
            # Get the height of the main panes (first child)
            try:
                # Get current height of the horizontal container
                main_panes_height = self.vertical_paned.panes()[0].winfo_height()
                # Calculate preview height as approximately half of main panes
                preview_height = main_panes_height // 2
                # Ensure minimum height
                preview_height = max(150, min(preview_height, 300))
            except:
                # Fallback to a reasonable default
                preview_height = 200
            
            # Add preview container to vertical paned window
            self.vertical_paned.add(self.preview_container, minsize=150, height=preview_height)
            self.preview_visible = True
            self.preview_toggle_button.config(text=i18n.get('hide_preview', 'Hide Preview'))
    
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
            if stat_info.st_size > 1024 * 1024:  # 1MB limit
                self.preview_text.insert(1.0, i18n.get('file_too_large', 
                    f'File too large for preview ({self.format_size(stat_info.st_size)})'))
                self.preview_text.config(state='disabled')
                return
            
            # Try to read as text
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    # Read first 1000 lines
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 1000:
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
                        if file_size > 1024 * 1024:  # 1MB limit
                            self.parent.after(0, lambda: self.update_preview_content(
                                i18n.get('file_too_large', f'File too large for preview ({self.format_size(file_size)})')
                            ))
                            return
                    except:
                        pass
                
                # Use head command to get first 1000 lines
                success, output = self.execute_remote_command(
                    f'head -n 1000 "{remote_path}" 2>/dev/null || echo "[File not readable]"'
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
        
        thread = threading.Thread(target=load_remote)
        thread.daemon = True
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
        dialog.geometry('700x700')
        dialog.transient(self.parent)
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 700) // 2
        y = (dialog.winfo_screenheight() - 700) // 2
        dialog.geometry(f'700x700+{x}+{y}')
        
        # Make it modal
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
        
        self.exclude_text = tk.Text(text_frame, height=6, wrap='word')
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


def launch_gui():
    """Launch the simplified GUI application"""
    logger = get_logger(__name__)
    logger.info("Starting Rediacc CLI GUI...")
    import signal
    
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
    token_valid = False
    logger.debug("Checking authentication status...")
    
    try:
        is_authenticated = TokenManager.is_authenticated()
        logger.debug(f"TokenManager.is_authenticated(): {is_authenticated}")
    except Exception as e:
        logger.error(f"Error checking authentication: {e}")
        import traceback
        traceback.print_exc()
        is_authenticated = False
    
    if is_authenticated:
        logger.debug("Testing token validity with API call...")
        # Test if the token is still valid by making a simple API call
        try:
            runner = SubprocessRunner()
            logger.debug("Creating SubprocessRunner...")
            result = runner.run_cli_command(['--output', 'json', 'list', 'teams'])
            logger.debug(f"API call result: {result}")
            token_valid = result.get('success', False)
            if not token_valid:
                logger.debug(f"Token validation failed. Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.debug(f"Exception during token validation: {e}")
            import traceback
            traceback.print_exc()
            token_valid = False
        
        # If token is invalid, clear it
        if not token_valid:
            logger.debug("Clearing invalid token...")
            try:
                TokenManager.clear_token()
            except Exception as e:
                logger.error(f"Error clearing token: {e}")
                import traceback
                traceback.print_exc()
    
    try:
        if token_valid:
            # Token is valid, show main window
            logger.debug("Token is valid, launching main window...")
            main_window = MainWindow()
            main_window.root.mainloop()
        else:
            # Show login window
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