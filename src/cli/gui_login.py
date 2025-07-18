#!/usr/bin/env python3
"""
GUI Login Window

This module provides the login window functionality for the Rediacc CLI GUI
application, including authentication, 2FA support, and language selection.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Callable

from core import SubprocessRunner, i18n
from gui_base import BaseWindow
from gui_utilities import (
    LOGIN_WINDOW_SIZE, COMBO_WIDTH_SMALL, ENTRY_WIDTH_DEFAULT,
    COLOR_SUCCESS, COLOR_ERROR
)


class LoginWindow(BaseWindow):
    """Simple login window with authentication support"""
    
    def __init__(self, on_login_success: Callable):
        super().__init__(tk.Tk(), i18n.get('login_title'))
        self.on_login_success = on_login_success
        self.center_window(LOGIN_WINDOW_SIZE[0], LOGIN_WINDOW_SIZE[1])
        
        # Register for language changes
        i18n.register_observer(self.update_texts)
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create login form widgets"""
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Configure grid columns
        main_frame.columnconfigure(0, minsize=100)  # Label column
        main_frame.columnconfigure(1, weight=1)     # Entry column
        main_frame.columnconfigure(2, weight=0)     # Language selector column
        
        # Row 0: Language selector (right-aligned, columnspan=3)
        lang_frame = tk.Frame(main_frame)
        lang_frame.grid(row=0, column=0, columnspan=3, sticky='e', pady=(0, 10))
        
        self.lang_label = tk.Label(lang_frame, text=i18n.get('language') + ':')
        self.lang_label.pack(side='left', padx=5)
        
        self.lang_combo = ttk.Combobox(lang_frame, state='readonly', width=COMBO_WIDTH_SMALL)
        self.lang_combo['values'] = [i18n.get_language_name(code) for code in i18n.get_language_codes()]
        self.lang_combo.set(i18n.get_language_name(i18n.current_language))
        self.lang_combo.pack(side='left')
        self.lang_combo.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        # Row 1: Title (centered, columnspan=3)
        self.title_label = tk.Label(main_frame, text=i18n.get('login_header'),
                        font=('Arial', 16, 'bold'))
        self.title_label.grid(row=1, column=0, columnspan=3, pady=15)
        
        # Row 2: Email field
        self.email_label = tk.Label(main_frame, text=i18n.get('email'))
        self.email_label.grid(row=2, column=0, sticky='e', padx=(40, 20), pady=(5, 0))
        self.email_entry = ttk.Entry(main_frame, width=ENTRY_WIDTH_DEFAULT)
        self.email_entry.grid(row=2, column=1, sticky='ew', padx=(0, 40), pady=(5, 8))
        
        # Row 3: Password field
        self.password_label = tk.Label(main_frame, text=i18n.get('password'))
        self.password_label.grid(row=3, column=0, sticky='e', padx=(40, 20), pady=(5, 0))
        self.password_entry = ttk.Entry(main_frame, width=ENTRY_WIDTH_DEFAULT, show='*')
        self.password_entry.grid(row=3, column=1, sticky='ew', padx=(0, 40), pady=(5, 8))
        
        # Row 4: Master password field
        self.master_password_label = tk.Label(main_frame, text=i18n.get('master_password'))
        self.master_password_label.grid(row=4, column=0, sticky='e', padx=(40, 20), pady=(5, 0))
        self.master_password_entry = ttk.Entry(main_frame, width=ENTRY_WIDTH_DEFAULT, show='*')
        self.master_password_entry.grid(row=4, column=1, sticky='ew', padx=(0, 40), pady=(5, 8))
        
        # Row 5: 2FA code field (pre-allocated but initially hidden)
        self.tfa_frame = tk.Frame(main_frame)
        self.tfa_label = tk.Label(self.tfa_frame, text=i18n.get('tfa_code'), font=('Arial', 10, 'bold'))
        self.tfa_label.grid(row=0, column=0, sticky='e', padx=(0, 20), pady=(5, 0))
        self.tfa_entry = ttk.Entry(self.tfa_frame, width=ENTRY_WIDTH_DEFAULT, font=('Arial', 11))
        self.tfa_entry.grid(row=0, column=1, sticky='ew', pady=(5, 2))
        self.tfa_help = tk.Label(self.tfa_frame, text=i18n.get('tfa_help'), 
                                font=('Arial', 9), fg='gray')
        self.tfa_help.grid(row=1, column=1, sticky='w', pady=(0, 8))
        # Configure tfa_frame columns
        self.tfa_frame.columnconfigure(0, minsize=100)
        self.tfa_frame.columnconfigure(1, weight=1)
        # Don't grid the frame initially - it will be shown when 2FA is required
        
        # Row 6: Login button
        self.login_button = ttk.Button(main_frame, text=i18n.get('login'), command=self.login)
        self.login_button.grid(row=6, column=1, sticky='ew', pady=15)
        
        # Row 7: Status label with wrapping
        self.status_label = tk.Label(main_frame, text="", wraplength=400, justify='center')
        self.status_label.grid(row=7, column=0, columnspan=3, pady=(0, 10))
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())
        
        # Focus on email field
        self.email_entry.focus()
    
    def login(self):
        """Handle login process"""
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        master_password = self.master_password_entry.get()
        tfa_code = self.tfa_entry.get().strip() if hasattr(self, 'tfa_entry') else ""
        
        if not (email and password):
            messagebox.showerror(i18n.get('error'), i18n.get('please_enter_credentials'))
            return
        
        self.login_button.config(state='disabled')
        self.status_label.config(text=i18n.get('logging_in'))
        
        thread = threading.Thread(target=self._do_login, args=(email, password, master_password, tfa_code), daemon=True)
        thread.start()
    
    def _do_login(self, email: str, password: str, master_password: str, tfa_code: str = ""):
        """Perform login in background thread"""
        try:
            runner = SubprocessRunner()
            cmd = ['--output', 'json', 'login', '--email', email, '--password', password]
            
            if master_password.strip():
                cmd.extend(['--master-password', master_password])
            if tfa_code:
                cmd.extend(['--tfa-code', tfa_code])
            
            result = runner.run_cli_command(cmd)
            
            if result['success']:
                self.root.after(0, self.login_success)
            else:
                error = result.get('error', i18n.get('login_failed'))
                if '2FA_REQUIRED' in error:
                    self.root.after(0, self.show_2fa_field)
                else:
                    self.root.after(0, lambda: self.login_error(error))
        except Exception as e:
            self.root.after(0, lambda: self.login_error(str(e)))
    
    def login_success(self):
        """Handle successful login"""
        self.status_label.config(text=i18n.get('login_successful'), fg=COLOR_SUCCESS)
        # Unregister observer before closing
        i18n.unregister_observer(self.update_texts)
        self.root.withdraw()
        self.on_login_success()
    
    def login_error(self, error: str):
        """Handle login error"""
        self.login_button.config(state='normal')
        self.status_label.config(text=f"{i18n.get('error')}: {error}", fg=COLOR_ERROR)
    
    def show_2fa_field(self):
        """Show 2FA field when required"""
        # Grid the 2FA frame in row 5
        self.tfa_frame.grid(row=5, column=0, columnspan=2, sticky='ew', padx=(40, 40), pady=(5, 0))
        
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
        code = next((code for code in i18n.get_language_codes() 
                    if i18n.get_language_name(code) == selected_name), None)
        if code:
            i18n.set_language(code)
    
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