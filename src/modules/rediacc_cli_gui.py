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

# Import internationalization
from i18n import i18n

# Import terminal detector
from terminal_detector import TerminalDetector

# Import logging configuration
from logging_config import get_logger



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
        # __file__ is in src/modules/, so we need to go up two levels to get to cli/
        # src/modules/rediacc_cli_gui.py -> src/ -> cli/
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
        
        self.sync_output.config(state='normal')  # Enable for clearing
        self.sync_output.delete(1.0, tk.END)
        self.sync_output.config(state='disabled')  # Disable again
        self.sync_button.config(state='disabled')
        self.status_bar.config(text=i18n.get('starting_sync', direction=i18n.get(direction)))
        
        def sync():
            cmd = ['sync', direction, '--team', team, '--machine', machine, 
                   '--repo', repo, '--local', local_path]
            
            if self.mirror_var.get():
                cmd.append('--mirror')
            if self.verify_var.get():
                cmd.append('--verify')
            if self.confirm_var.get():
                cmd.append('--confirm')
            
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
        self.status_bar.config(text=i18n.get('sync_completed'))
    
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
        
        # Update status bar
        current_text = self.status_bar.cget('text')
        if current_text == 'Ready' or current_text == 'جاهز' or current_text == 'Bereit':
            self.status_bar.config(text=i18n.get('ready'))
        
        # Update each tab's contents
        self.update_plugin_tab_texts()
        self.update_terminal_tab_texts()
        self.update_sync_tab_texts()
    
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