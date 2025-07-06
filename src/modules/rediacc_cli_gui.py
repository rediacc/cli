#!/usr/bin/env python3
"""
Rediacc Desktop - Tkinter-based graphical interface for Rediacc CLI tools
Provides a unified GUI for all CLI functionality without external dependencies
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import threading
import queue
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import subprocess
from datetime import datetime

# Import token manager
from token_manager import TokenManager

# Import platform utilities from core
from rediacc_cli_core import is_windows

# Import configuration loader
from config_loader import get

# Color schemes matching console project
THEMES = {
    'dark': {
        # Dark theme backgrounds (from console project)
        'bg_dark': '#0a0a0a',      # Main dark background
        'bg_light': '#1a1a1a',     # Secondary dark background
        'bg_hover': '#2a2a2a',     # Hover/active background
        
        # Text colors
        'fg_primary': '#fafafa',    # Primary text (dark theme)
        'fg_secondary': '#a1a1aa',  # Secondary text
        'fg_muted': '#71717a',      # Muted text
        
        # Brand colors (from console project)
        'primary': '#556b2f',       # Olive green (primary brand)
        'secondary': '#808000',     # Olive (secondary brand)
        'accent': '#7d9b49',        # Light olive green (accent)
        
        # Status colors (from console project)
        'success': '#51cf66',       # Green
        'error': '#ff6b6b',         # Red
        'warning': '#ffd43b',       # Yellow
        'info': '#74c0fc',          # Light blue
        
        # Special colors
        'header': '#4ecdc4',        # Teal (brand secondary)
        'border': '#27272a'         # Border color
    },
    'light': {
        # Light theme backgrounds
        'bg_dark': '#ffffff',       # Main light background
        'bg_light': '#f4f4f5',      # Secondary light background
        'bg_hover': '#e4e4e7',      # Hover/active background
        
        # Text colors
        'fg_primary': '#09090b',    # Primary text (light theme)
        'fg_secondary': '#52525b',  # Secondary text
        'fg_muted': '#a1a1aa',      # Muted text
        
        # Brand colors (same for both themes)
        'primary': '#556b2f',       # Olive green (primary brand)
        'secondary': '#808000',     # Olive (secondary brand)
        'accent': '#7d9b49',        # Light olive green (accent)
        
        # Status colors (same for both themes)
        'success': '#16a34a',       # Green (darker for light theme)
        'error': '#dc2626',         # Red (darker for light theme)
        'warning': '#ca8a04',       # Yellow (darker for light theme)
        'info': '#2563eb',          # Blue (darker for light theme)
        
        # Special colors
        'header': '#4ecdc4',        # Teal (brand secondary)
        'border': '#e4e4e7'         # Border color
    }
}

# Load theme preference from config file
def load_theme_preference():
    """Load theme preference from config file"""
    try:
        config_path = Path.home() / '.rediacc' / 'gui_config.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('theme', get('REDIACC_DEFAULT_THEME') or 'dark')
    except:
        pass
    return get('REDIACC_DEFAULT_THEME') or 'dark'

def save_theme_preference(theme: str):
    """Save theme preference to config file"""
    try:
        config_dir = Path.home() / '.rediacc'
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / 'gui_config.json'
        
        # Load existing config or create new
        config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        # Update theme
        config['theme'] = theme
        
        # Save config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except:
        pass

# Current theme - load from preference or default to dark
current_theme = load_theme_preference()
COLORS = THEMES[current_theme]

class ThreadSafeOutput:
    """Thread-safe output handler for GUI console"""
    def __init__(self, text_widget: scrolledtext.ScrolledText):
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.text_widget.after(100, self.process_queue)
    
    def write(self, text: str, color: str = None):
        """Queue text for thread-safe writing"""
        self.queue.put((text, color))
    
    def process_queue(self):
        """Process queued output"""
        try:
            while True:
                text, color = self.queue.get_nowait()
                self.text_widget.config(state='normal')
                if color:
                    tag_name = f"color_{color}"
                    self.text_widget.tag_config(tag_name, foreground=color)
                    self.text_widget.insert('end', text, tag_name)
                else:
                    self.text_widget.insert('end', text)
                self.text_widget.see('end')
                self.text_widget.config(state='disabled')
        except queue.Empty:
            pass
        finally:
            self.text_widget.after(100, self.process_queue)

class BaseWindow:
    """Base class for all GUI windows"""
    def __init__(self, root: tk.Tk, title: str = "Rediacc Desktop"):
        self.root = root
        self.root.title(title)
        self.current_theme = current_theme
        self.root.configure(bg=COLORS['bg_dark'])
        
        # Set window style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Center window on screen
        self.center_window()
        
        # Create a header frame for theme toggle
        self.header_frame = tk.Frame(self.root, bg=COLORS['bg_dark'], height=40)
        self.header_frame.pack(fill='x', side='top')
        self.header_frame.pack_propagate(False)
        
        # Add theme toggle button
        self.create_theme_toggle()
        
        # Set up proper window close handling
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind Escape key to close window
        self.root.bind('<Escape>', lambda e: self.on_closing())
    
    def configure_styles(self):
        """Configure ttk styles to match color scheme"""
        self.style.configure('TLabel', background=COLORS['bg_dark'], foreground=COLORS['fg_primary'])
        self.style.configure('TButton', background=COLORS['bg_light'], foreground=COLORS['fg_primary'])
        self.style.configure('TEntry', fieldbackground=COLORS['bg_light'], foreground=COLORS['fg_primary'], 
                           bordercolor=COLORS['border'], insertcolor=COLORS['fg_primary'])
        self.style.configure('TFrame', background=COLORS['bg_dark'])
        self.style.configure('Accent.TButton', background=COLORS['accent'], foreground=COLORS['fg_primary'])
        self.style.configure('TCombobox', fieldbackground=COLORS['bg_light'], foreground=COLORS['fg_primary'],
                           background=COLORS['bg_light'], bordercolor=COLORS['border'])
    
    def center_window(self, width: int = 800, height: int = 600):
        """Center window on screen"""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_theme_toggle(self):
        """Create theme toggle button in top right corner"""
        # Create theme label on the left
        theme_label = tk.Label(
            self.header_frame,
            text="Theme:",
            font=('Arial', 10),
            bg=COLORS['bg_dark'],
            fg=COLORS['fg_secondary']
        )
        theme_label.pack(side='left', padx=(10, 5), pady=8)
        
        # Create theme buttons frame
        theme_buttons_frame = tk.Frame(self.header_frame, bg=COLORS['bg_dark'])
        theme_buttons_frame.pack(side='left', pady=8)
        
        # Light theme button
        self.light_button = tk.Button(
            theme_buttons_frame,
            text="☀️ Light",
            font=('Arial', 10),
            bg=COLORS['bg_light'] if self.current_theme == 'light' else COLORS['bg_hover'],
            fg=COLORS['fg_primary'],
            activebackground=COLORS['accent'],
            activeforeground=COLORS['fg_primary'],
            bd=0,
            padx=10,
            pady=5,
            cursor='hand2',
            command=lambda: self.set_theme('light')
        )
        self.light_button.pack(side='left', padx=2)
        
        # Dark theme button
        self.dark_button = tk.Button(
            theme_buttons_frame,
            text="🌙 Dark",
            font=('Arial', 10),
            bg=COLORS['bg_light'] if self.current_theme == 'dark' else COLORS['bg_hover'],
            fg=COLORS['fg_primary'],
            activebackground=COLORS['accent'],
            activeforeground=COLORS['fg_primary'],
            bd=0,
            padx=10,
            pady=5,
            cursor='hand2',
            command=lambda: self.set_theme('dark')
        )
        self.dark_button.pack(side='left', padx=2)
        
        # Add branding on the right
        brand_label = tk.Label(
            self.header_frame,
            text="Rediacc Desktop",
            font=('Arial', 12, 'bold'),
            bg=COLORS['bg_dark'],
            fg=COLORS['primary']
        )
        brand_label.pack(side='right', padx=10, pady=8)
    
    def set_theme(self, theme: str):
        """Set the theme to light or dark"""
        if theme == self.current_theme:
            return
            
        global current_theme, COLORS
        current_theme = theme
        COLORS = THEMES[current_theme]
        self.current_theme = current_theme
        
        # Save theme preference
        save_theme_preference(theme)
        
        # Update theme buttons
        self.light_button.config(
            bg=COLORS['bg_light'] if theme == 'light' else COLORS['bg_hover']
        )
        self.dark_button.config(
            bg=COLORS['bg_light'] if theme == 'dark' else COLORS['bg_hover']
        )
        
        # Reapply styles
        self.apply_theme()
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        new_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.set_theme(new_theme)
    
    def apply_theme(self):
        """Apply current theme to all widgets"""
        # Update root window
        self.root.configure(bg=COLORS['bg_dark'])
        
        # Update header frame
        self.header_frame.configure(bg=COLORS['bg_dark'])
        
        # Update theme buttons
        self.light_button.configure(
            bg=COLORS['bg_light'] if self.current_theme == 'light' else COLORS['bg_hover'],
            fg=COLORS['fg_primary'],
            activebackground=COLORS['accent'],
            activeforeground=COLORS['fg_primary']
        )
        self.dark_button.configure(
            bg=COLORS['bg_light'] if self.current_theme == 'dark' else COLORS['bg_hover'],
            fg=COLORS['fg_primary'],
            activebackground=COLORS['accent'],
            activeforeground=COLORS['fg_primary']
        )
        
        # Update styles
        self.configure_styles()
        
        # Update all widgets recursively
        self.update_widget_colors(self.root)
    
    def update_widget_colors(self, widget):
        """Recursively update colors for all widgets"""
        # Skip ttk widgets as they use styles
        if isinstance(widget, (ttk.Button, ttk.Label, ttk.Entry, ttk.Frame, ttk.Combobox)):
            return
            
        # Update tk widgets
        if isinstance(widget, tk.Label):
            widget.configure(bg=COLORS['bg_dark'], fg=COLORS['fg_primary'])
        elif isinstance(widget, tk.LabelFrame):
            widget.configure(
                bg=COLORS['bg_dark'], 
                fg=COLORS['fg_secondary'],
                highlightbackground=COLORS['border'],
                highlightcolor=COLORS['border']
            )
        elif isinstance(widget, tk.Frame):
            widget.configure(bg=COLORS['bg_dark'])
        elif isinstance(widget, tk.Button):
            # Skip theme buttons as they have special styling
            if widget not in [getattr(self, 'light_button', None), getattr(self, 'dark_button', None)]:
                widget.configure(
                    bg=COLORS['bg_hover'], 
                    fg=COLORS['fg_primary'],
                    activebackground=COLORS['accent'],
                    activeforeground=COLORS['fg_primary']
                )
        elif isinstance(widget, tk.Text):
            widget.configure(
                bg=COLORS['bg_light'], 
                fg=COLORS['fg_primary'],
                insertbackground=COLORS['fg_primary'],
                selectbackground=COLORS['accent'],
                selectforeground=COLORS['fg_primary']
            )
        elif isinstance(widget, scrolledtext.ScrolledText):
            widget.configure(
                bg=COLORS['bg_light'], 
                fg=COLORS['fg_primary'],
                insertbackground=COLORS['fg_primary'],
                selectbackground=COLORS['accent'],
                selectforeground=COLORS['fg_primary']
            )
        
        # Recursively update children
        for child in widget.winfo_children():
            self.update_widget_colors(child)
    
    def on_closing(self):
        """Handle window close event"""
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        finally:
            import sys
            sys.exit(0)

class LoginWindow(BaseWindow):
    """Login window for authentication"""
    def __init__(self, on_login_success: Callable):
        super().__init__(tk.Tk(), "Rediacc Desktop - Login")
        self.on_login_success = on_login_success
        self.token_manager = TokenManager()
        self.center_window(450, 550)
        self.create_widgets()
        
        # Check if already authenticated
        if self.token_manager.get_token():
            self.show_logged_in_state()
    
    def create_widgets(self):
        """Create login form widgets"""
        # Content frame (below header)
        self.content_frame = tk.Frame(self.root, bg=COLORS['bg_dark'])
        self.content_frame.pack(fill='both', expand=True)
        
        # Title
        title = tk.Label(self.content_frame, text="Rediacc Desktop Login", 
                        font=('Arial', 18, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=(10, 20))
        
        # Main frame
        self.main_frame = ttk.Frame(self.content_frame)
        self.main_frame.pack(padx=40, pady=10, fill='both', expand=True)
        
        # Email field
        ttk.Label(self.main_frame, text="Email:").grid(row=0, column=0, sticky='w', pady=5)
        self.email_var = tk.StringVar()
        self.email_entry = ttk.Entry(self.main_frame, textvariable=self.email_var, width=30)
        self.email_entry.grid(row=0, column=1, pady=5, padx=10)
        
        # Password field
        ttk.Label(self.main_frame, text="Password:").grid(row=1, column=0, sticky='w', pady=5)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(self.main_frame, textvariable=self.password_var, show='*', width=30)
        self.password_entry.grid(row=1, column=1, pady=5, padx=10)
        
        # Session name field
        ttk.Label(self.main_frame, text="Session Name:").grid(row=2, column=0, sticky='w', pady=5)
        self.session_var = tk.StringVar(value="GUI Session")
        self.session_entry = ttk.Entry(self.main_frame, textvariable=self.session_var, width=30)
        self.session_entry.grid(row=2, column=1, pady=5, padx=10)
        
        # Advanced options (collapsible)
        self.advanced_frame = tk.LabelFrame(self.main_frame, text="Advanced Options",
                                          bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'],
                                          font=('Arial', 10, 'bold'))
        self.advanced_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Master password field
        ttk.Label(self.advanced_frame, text="Master Password:").grid(row=0, column=0, sticky='w', pady=5)
        self.master_password_var = tk.StringVar()
        self.master_password_entry = ttk.Entry(self.advanced_frame, textvariable=self.master_password_var, show='*', width=25)
        self.master_password_entry.grid(row=0, column=1, pady=5, padx=10)
        
        # 2FA field
        ttk.Label(self.advanced_frame, text="2FA Code:").grid(row=1, column=0, sticky='w', pady=5)
        self.tfa_var = tk.StringVar()
        self.tfa_entry = ttk.Entry(self.advanced_frame, textvariable=self.tfa_var, width=25)
        self.tfa_entry.grid(row=1, column=1, pady=5, padx=10)
        
        # API URL field
        ttk.Label(self.advanced_frame, text="API URL:").grid(row=2, column=0, sticky='w', pady=5)
        self.api_url_var = tk.StringVar(value=os.environ.get('REDIACC_API_URL', ''))
        self.api_url_entry = ttk.Entry(self.advanced_frame, textvariable=self.api_url_var, width=25)
        self.api_url_entry.grid(row=2, column=1, pady=5, padx=10)
        
        # Buttons
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        self.login_button = ttk.Button(self.button_frame, text="Login", 
                                      command=self.login, style='Accent.TButton')
        self.login_button.pack(side='left', padx=5)
        
        self.cancel_button = ttk.Button(self.button_frame, text="Cancel", 
                                       command=self.root.quit)
        self.cancel_button.pack(side='left', padx=5)
        
        # Status label
        self.status_label = tk.Label(self.content_frame, text="", 
                                   bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'])
        self.status_label.pack(pady=10)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())
    
    def show_logged_in_state(self):
        """Show logged in state with current user info"""
        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Show current user info
        auth_info = self.token_manager.get_auth_info()
        email = auth_info.get('email', 'Unknown')
        company = auth_info.get('company', 'Unknown')
        
        info_text = f"Currently logged in as:\n{email}\nCompany: {company}"
        info_label = tk.Label(self.main_frame, text=info_text,
                            bg=COLORS['bg_dark'], fg=COLORS['success'],
                            font=('Arial', 12))
        info_label.pack(pady=20)
        
        # Buttons
        continue_button = ttk.Button(self.main_frame, text="Continue with current session",
                                   command=self.continue_session, style='Accent.TButton')
        continue_button.pack(pady=10)
        
        logout_button = ttk.Button(self.main_frame, text="Logout and login again",
                                 command=self.logout_and_refresh)
        logout_button.pack(pady=5)
    
    def continue_session(self):
        """Continue with existing session"""
        self.root.withdraw()
        self.on_login_success(self.token_manager)
    
    def logout_and_refresh(self):
        """Logout and show login form again"""
        # Run logout command
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            subprocess.run([sys.executable, str(cli_path), 'logout'], check=True)
            self.token_manager = TokenManager()  # Reload token manager
            # Recreate widgets
            for widget in self.root.winfo_children():
                widget.destroy()
            # Recreate the header frame and theme toggle
            self.header_frame = tk.Frame(self.root, bg=COLORS['bg_dark'], height=40)
            self.header_frame.pack(fill='x', side='top')
            self.header_frame.pack_propagate(False)
            self.create_theme_toggle()
            # Now create widgets
            self.create_widgets()
            self.status_label.config(text="Logged out successfully", fg=COLORS['success'])
        except Exception as e:
            messagebox.showerror("Logout Error", str(e))
    
    def login(self):
        """Handle login action"""
        email = self.email_var.get()
        password = self.password_var.get()
        
        if not email or not password:
            messagebox.showerror("Error", "Email and password are required")
            return
        
        self.login_button.config(state='disabled')
        self.status_label.config(text="Logging in...", fg=COLORS['fg_secondary'])
        
        # Run login in thread
        thread = threading.Thread(target=self.perform_login, 
                                args=(email, password), daemon=True)
        thread.start()
    
    def perform_login(self, email: str, password: str):
        """Perform login in background thread"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            
            # Build command
            cmd = [sys.executable, str(cli_path), '--output', 'json', 'login',
                   '--email', email, '--password', password,
                   '--session-name', self.session_var.get()]
            
            # Add optional parameters
            if self.master_password_var.get():
                cmd.extend(['--master-password', self.master_password_var.get()])
            if self.tfa_var.get():
                cmd.extend(['--tfa-code', self.tfa_var.get()])
            
            # Set API URL if provided
            env = os.environ.copy()
            if self.api_url_var.get():
                env['REDIACC_API_URL'] = self.api_url_var.get()
            
            # Run login command
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                # Parse response
                response = json.loads(result.stdout)
                if response.get('success'):
                    self.root.after(0, self.login_success)
                else:
                    error = response.get('error', 'Unknown error')
                    self.root.after(0, self.login_error, error)
            else:
                # Try to parse error from JSON output
                try:
                    response = json.loads(result.stdout)
                    error = response.get('error', 'Login failed')
                except:
                    error = result.stderr or "Login failed"
                self.root.after(0, self.login_error, error)
                
        except Exception as e:
            self.root.after(0, self.login_error, str(e))
    
    def login_success(self):
        """Handle successful login"""
        self.status_label.config(text="Login successful!", fg=COLORS['success'])
        # Reload token manager to get new token
        self.token_manager = TokenManager()
        # Hide login window and show main window
        self.root.withdraw()
        self.on_login_success(self.token_manager)
    
    def login_error(self, error: str):
        """Handle login error"""
        self.login_button.config(state='normal')
        self.status_label.config(text=f"Error: {error}", fg=COLORS['error'])
        messagebox.showerror("Login Failed", error)

class MainWindow(BaseWindow):
    """Main application window"""
    def __init__(self, token_manager: TokenManager):
        super().__init__(tk.Tk(), "Rediacc Desktop")
        self.token_manager = token_manager
        self.center_window(1000, 700)
        self.create_widgets()
        self.current_view = None
    
    def create_widgets(self):
        """Create main window widgets"""
        # Content frame (below header)
        main_content = tk.Frame(self.root, bg=COLORS['bg_dark'])
        main_content.pack(fill='both', expand=True)
        
        # Top frame with user info
        self.create_top_frame(main_content)
        
        # Main content area with navigation
        self.create_main_content(main_content)
        
        # Status bar
        self.create_status_bar(main_content)
        
        # Menu bar (create after content_frame exists)
        self.create_menu()
    
    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root, bg=COLORS['bg_light'], fg=COLORS['fg_primary'])
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh", command=self.refresh_current_view)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Teams", command=lambda: self.show_view('teams'))
        view_menu.add_command(label="Machines", command=lambda: self.show_view('machines'))
        view_menu.add_command(label="Repositories", command=lambda: self.show_view('repositories'))
        view_menu.add_command(label="Queue", command=lambda: self.show_view('queue'))
        view_menu.add_separator()
        view_menu.add_command(label="Console Output", command=lambda: self.show_view('console'))
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Sync Files", command=self.show_sync_dialog)
        tools_menu.add_command(label="Terminal Access", command=self.show_terminal_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Vault Settings", command=self.show_vault_settings)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
    
    def create_top_frame(self, parent):
        """Create top frame with user info and logout"""
        self.top_frame = tk.Frame(parent, bg=COLORS['bg_light'], height=50)
        self.top_frame.pack(fill='x', padx=5, pady=5)
        
        # User info
        auth_info = self.token_manager.get_auth_info()
        user_text = f"User: {auth_info.get('email', 'Unknown')} | Company: {auth_info.get('company', 'Unknown')}"
        user_label = tk.Label(self.top_frame, text=user_text,
                            bg=COLORS['bg_light'], fg=COLORS['fg_secondary'])
        user_label.pack(side='left', padx=10)
        
        # Logout button
        logout_button = ttk.Button(self.top_frame, text="Logout", command=self.logout)
        logout_button.pack(side='right', padx=10)
    
    def create_main_content(self, parent):
        """Create main content area"""
        # Main paned window
        self.paned_window = ttk.PanedWindow(parent, orient='horizontal')
        self.paned_window.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left navigation panel
        self.nav_frame = tk.Frame(self.paned_window, bg=COLORS['bg_light'], width=200)
        self.paned_window.add(self.nav_frame, weight=1)
        
        # Navigation title
        nav_title = tk.Label(self.nav_frame, text="Navigation", 
                           font=('Arial', 14, 'bold'),
                           bg=COLORS['bg_light'], fg=COLORS['header'])
        nav_title.pack(pady=10)
        
        # Navigation buttons
        nav_items = [
            ("Teams", 'teams'),
            ("Regions", 'regions'),
            ("Bridges", 'bridges'),
            ("Machines", 'machines'),
            ("Repositories", 'repositories'),
            ("Storage", 'storage'),
            ("Schedules", 'schedules'),
            ("Queue", 'queue'),
            ("Users", 'users'),
            ("Permissions", 'permissions'),
            ("Console", 'console')
        ]
        
        for label, view in nav_items:
            btn = tk.Button(self.nav_frame, text=label,
                          bg=COLORS['bg_hover'], fg=COLORS['fg_primary'],
                          activebackground=COLORS['accent'],
                          activeforeground=COLORS['fg_primary'],
                          bd=0, pady=8, padx=10,
                          command=lambda v=view: self.show_view(v),
                          relief='flat', cursor='hand2')
            btn.pack(fill='x', padx=10, pady=2)
        
        # Right content area
        self.content_frame = tk.Frame(self.paned_window, bg=COLORS['bg_dark'])
        self.paned_window.add(self.content_frame, weight=4)
        
        # Welcome message
        welcome = tk.Label(self.content_frame, 
                         text="Welcome to Rediacc Desktop\nSelect an option from the navigation menu",
                         font=('Arial', 16),
                         bg=COLORS['bg_dark'], fg=COLORS['fg_primary'])
        welcome.pack(pady=50)
    
    def create_status_bar(self, parent):
        """Create status bar"""
        self.status_bar = tk.Label(parent, text="Ready", 
                                 bg=COLORS['bg_light'], fg=COLORS['fg_secondary'],
                                 anchor='w', padx=10, pady=5,
                                 relief='flat', bd=1)
        self.status_bar.pack(side='bottom', fill='x')
    
    def show_view(self, view_name: str):
        """Show a specific view in the content area"""
        # Clear current content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        self.current_view = view_name
        self.status_bar.config(text=f"Loading {view_name}...")
        
        # Create view based on type
        if view_name == 'console':
            self.show_console_view()
        elif view_name == 'teams':
            self.show_resource_list('teams')
        elif view_name == 'machines':
            self.show_resource_list('machines')
        elif view_name == 'repositories':
            self.show_resource_list('repositories')
        elif view_name == 'queue':
            self.show_queue_view()
        else:
            self.show_resource_list(view_name)
    
    def show_console_view(self):
        """Show console output view"""
        # Title
        title = tk.Label(self.content_frame, text="Console Output",
                       font=('Arial', 16, 'bold'),
                       bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Console output
        self.console_output = scrolledtext.ScrolledText(
            self.content_frame, wrap='word',
            bg=COLORS['bg_light'], fg=COLORS['fg_primary'],
            font=('Consolas', 10), insertbackground=COLORS['fg_primary'],
            selectbackground=COLORS['accent'], selectforeground=COLORS['fg_primary'])
        self.console_output.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Console input
        input_frame = ttk.Frame(self.content_frame)
        input_frame.pack(fill='x', padx=10, pady=5)
        
        self.console_input = ttk.Entry(input_frame, font=('Consolas', 10))
        self.console_input.pack(side='left', fill='x', expand=True)
        
        run_button = ttk.Button(input_frame, text="Run", 
                              command=self.run_console_command)
        run_button.pack(side='right', padx=5)
        
        # Bind Enter to run command
        self.console_input.bind('<Return>', lambda e: self.run_console_command())
        
        self.console_handler = ThreadSafeOutput(self.console_output)
        self.status_bar.config(text="Console ready")
        
        # Configure text tags for colors
        self.console_output.tag_config('info', foreground=COLORS['info'])
        self.console_output.tag_config('success', foreground=COLORS['success'])
        self.console_output.tag_config('warning', foreground=COLORS['warning'])
        self.console_output.tag_config('error', foreground=COLORS['error'])
    
    def show_resource_list(self, resource_type: str):
        """Show list view for a resource type"""
        # Title
        title = tk.Label(self.content_frame, text=resource_type.title(),
                       font=('Arial', 16, 'bold'),
                       bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Toolbar
        toolbar = ttk.Frame(self.content_frame)
        toolbar.pack(fill='x', padx=10, pady=5)
        
        # Add button
        add_button = ttk.Button(toolbar, text=f"Add {resource_type[:-1]}", 
                              command=lambda: self.show_add_dialog(resource_type))
        add_button.pack(side='left', padx=5)
        
        # Refresh button
        refresh_button = ttk.Button(toolbar, text="Refresh", 
                                  command=lambda: self.refresh_resource_list(resource_type))
        refresh_button.pack(side='left', padx=5)
        
        # Search
        search_label = ttk.Label(toolbar, text="Search:")
        search_label.pack(side='left', padx=(20, 5))
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side='left')
        search_entry.bind('<KeyRelease>', lambda e: self.filter_list())
        
        # List view
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview
        columns = self.get_columns_for_resource(resource_type)
        self.resource_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Configure columns
        self.resource_tree.heading('#0', text='Name')
        for col in columns:
            self.resource_tree.heading(col, text=col.replace('_', ' ').title())
            self.resource_tree.column(col, width=150)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.resource_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient='horizontal', command=self.resource_tree.xview)
        self.resource_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.resource_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Context menu
        self.create_context_menu(resource_type)
        
        # Load data
        self.refresh_resource_list(resource_type)
    
    def get_columns_for_resource(self, resource_type: str) -> List[str]:
        """Get column names for resource type"""
        columns_map = {
            'teams': ['member_count', 'machine_count', 'repo_count'],
            'machines': ['team', 'bridge', 'status'],
            'repositories': ['team', 'size', 'last_modified'],
            'bridges': ['region', 'status', 'machine_count'],
            'regions': ['bridge_count', 'status'],
            'users': ['email', 'company', 'activated'],
            'permissions': ['group', 'description'],
            'storage': ['team', 'size', 'type'],
            'schedules': ['team', 'next_run', 'status']
        }
        return columns_map.get(resource_type, ['status'])
    
    def create_context_menu(self, resource_type: str):
        """Create right-click context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="View Details", 
                                    command=lambda: self.view_resource_details(resource_type))
        self.context_menu.add_command(label="Edit", 
                                    command=lambda: self.edit_resource(resource_type))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", 
                                    command=lambda: self.delete_resource(resource_type))
        
        # Bind right-click
        self.resource_tree.bind('<Button-3>', self.show_context_menu)
    
    def show_context_menu(self, event):
        """Show context menu at cursor position"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def refresh_resource_list(self, resource_type: str):
        """Refresh resource list from API"""
        self.status_bar.config(text=f"Loading {resource_type}...")
        
        # Clear current items
        for item in self.resource_tree.get_children():
            self.resource_tree.delete(item)
        
        # Run in thread
        thread = threading.Thread(target=self.load_resource_data, 
                                args=(resource_type,), daemon=True)
        thread.start()
    
    def load_resource_data(self, resource_type: str):
        """Load resource data in background"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            # Build command
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'list', resource_type]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', [])
                    self.root.after(0, self.populate_resource_list, resource_type, data)
                else:
                    error = response.get('error', 'Failed to load data')
                    self.root.after(0, self.show_error, error)
            else:
                self.root.after(0, self.show_error, f"Failed to load {resource_type}")
                
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
    
    def populate_resource_list(self, resource_type: str, data: List[Dict]):
        """Populate resource list with data"""
        columns = self.get_columns_for_resource(resource_type)
        
        for item in data:
            # Get the name field
            name = (item.get('name') or item.get('teamName') or 
                   item.get('machineName') or item.get('repoName') or
                   item.get('bridgeName') or item.get('regionName') or
                   item.get('userEmail') or item.get('id', 'Unknown'))
            
            # Get column values
            values = []
            for col in columns:
                value = item.get(col, '')
                values.append(str(value))
            
            # Insert into tree
            self.resource_tree.insert('', 'end', text=name, values=values,
                                    tags=(json.dumps(item),))
        
        self.status_bar.config(text=f"Loaded {len(data)} {resource_type}")
    
    def filter_list(self):
        """Filter list based on search term"""
        search_term = self.search_var.get().lower()
        
        # Show all items if search is empty
        if not search_term:
            for item in self.resource_tree.get_children():
                self.resource_tree.item(item, open=True)
            return
        
        # Hide items that don't match
        for item in self.resource_tree.get_children():
            text = self.resource_tree.item(item)['text'].lower()
            values = [str(v).lower() for v in self.resource_tree.item(item)['values']]
            
            if search_term in text or any(search_term in v for v in values):
                self.resource_tree.item(item, open=True)
            else:
                self.resource_tree.detach(item)
    
    def show_queue_view(self):
        """Show queue management view"""
        # Title
        title = tk.Label(self.content_frame, text="Queue Management",
                       font=('Arial', 16, 'bold'),
                       bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Toolbar
        toolbar = ttk.Frame(self.content_frame)
        toolbar.pack(fill='x', padx=10, pady=5)
        
        # Add to queue button
        add_button = ttk.Button(toolbar, text="Add to Queue", 
                              command=self.show_queue_add_dialog)
        add_button.pack(side='left', padx=5)
        
        # Refresh button
        refresh_button = ttk.Button(toolbar, text="Refresh", 
                                  command=self.refresh_queue_list)
        refresh_button.pack(side='left', padx=5)
        
        # Status filter
        status_label = ttk.Label(toolbar, text="Status:")
        status_label.pack(side='left', padx=(20, 5))
        
        self.queue_status_var = tk.StringVar(value="ALL")
        status_combo = ttk.Combobox(toolbar, textvariable=self.queue_status_var,
                                   values=["ALL", "PENDING", "ASSIGNED", "PROCESSING", 
                                          "COMPLETED", "FAILED", "CANCELLED"],
                                   state='readonly', width=15)
        status_combo.pack(side='left')
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_queue_list())
        
        # Queue list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create treeview for queue items
        columns = ['task_id', 'status', 'function', 'machine', 'created', 'priority']
        self.queue_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Configure columns
        self.queue_tree.heading('#0', text='ID')
        self.queue_tree.column('#0', width=50)
        for col in columns:
            self.queue_tree.heading(col, text=col.replace('_', ' ').title())
            self.queue_tree.column(col, width=120)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.queue_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient='horizontal', command=self.queue_tree.xview)
        self.queue_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.queue_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Load queue data
        self.refresh_queue_list()
    
    def refresh_queue_list(self):
        """Refresh queue list"""
        self.status_bar.config(text="Loading queue items...")
        
        # Clear current items
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        
        # Run in thread
        thread = threading.Thread(target=self.load_queue_data, daemon=True)
        thread.start()
    
    def load_queue_data(self):
        """Load queue data in background"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            # Build command
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'queue', 'list']
            
            # Add status filter if not ALL
            status = self.queue_status_var.get()
            if status != "ALL":
                cmd.extend(['--status', status])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', [])
                    self.root.after(0, self.populate_queue_list, data)
                else:
                    error = response.get('error', 'Failed to load queue')
                    self.root.after(0, self.show_error, error)
                    
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
    
    def populate_queue_list(self, data: List[Dict]):
        """Populate queue list with data"""
        for idx, item in enumerate(data):
            # Extract relevant fields
            task_id = item.get('taskId', item.get('TaskId', ''))
            status = item.get('status', item.get('Status', ''))
            
            # Try to get function from vault data
            vault_data = {}
            try:
                vault_content = item.get('queueVault', item.get('QueueVault', ''))
                if vault_content:
                    vault_data = json.loads(vault_content)
            except:
                pass
            
            function = vault_data.get('function', 'Unknown')
            machine = item.get('machineName', item.get('MachineName', ''))
            created = item.get('createdTime', item.get('CreatedTime', ''))
            priority = item.get('priority', item.get('Priority', ''))
            
            # Color based on status
            tag = status.lower()
            
            # Insert into tree
            self.queue_tree.insert('', 'end', text=str(idx + 1),
                                 values=[task_id, status, function, machine, created, priority],
                                 tags=(tag, json.dumps(item)))
        
        # Configure tags for coloring
        self.queue_tree.tag_configure('completed', foreground=COLORS['success'])
        self.queue_tree.tag_configure('failed', foreground=COLORS['error'])
        self.queue_tree.tag_configure('cancelled', foreground=COLORS['warning'])
        self.queue_tree.tag_configure('processing', foreground=COLORS['accent'])
        
        self.status_bar.config(text=f"Loaded {len(data)} queue items")
    
    def show_add_dialog(self, resource_type: str):
        """Show dialog to add new resource"""
        dialog = ResourceDialog(self.root, self.token_manager, resource_type, 'create')
        self.root.wait_window(dialog.dialog)
        if dialog.success:
            self.refresh_resource_list(resource_type)
    
    def show_queue_add_dialog(self):
        """Show dialog to add item to queue"""
        dialog = QueueAddDialog(self.root, self.token_manager)
        self.root.wait_window(dialog.dialog)
        if dialog.success:
            self.refresh_queue_list()
    
    def view_resource_details(self, resource_type: str):
        """View details of selected resource"""
        selection = self.resource_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to view")
            return
        
        # Get item data
        item = self.resource_tree.item(selection[0])
        data = json.loads(item['tags'][0])
        
        # Show details dialog
        DetailsDialog(self.root, resource_type, data)
    
    def edit_resource(self, resource_type: str):
        """Edit selected resource"""
        selection = self.resource_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to edit")
            return
        
        # Get item data
        item = self.resource_tree.item(selection[0])
        data = json.loads(item['tags'][0])
        
        # Show edit dialog
        dialog = ResourceDialog(self.root, self.token_manager, resource_type, 'update', data)
        self.root.wait_window(dialog.dialog)
        if dialog.success:
            self.refresh_resource_list(resource_type)
    
    def delete_resource(self, resource_type: str):
        """Delete selected resource"""
        selection = self.resource_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to delete")
            return
        
        # Get item data
        item = self.resource_tree.item(selection[0])
        name = item['text']
        
        # Confirm deletion
        if messagebox.askyesno("Confirm Delete", 
                              f"Are you sure you want to delete {name}?"):
            # TODO: Implement deletion
            messagebox.showinfo("Not Implemented", "Delete functionality not yet implemented")
    
    def show_sync_dialog(self):
        """Show file sync dialog"""
        dialog = SyncDialog(self.root, self.token_manager)
    
    def show_terminal_dialog(self):
        """Show terminal access dialog"""
        dialog = TerminalDialog(self.root, self.token_manager)
    
    def show_vault_settings(self):
        """Show vault settings dialog"""
        dialog = VaultSettingsDialog(self.root, self.token_manager)
    
    def run_console_command(self):
        """Run command in console"""
        command = self.console_input.get()
        if not command:
            return
        
        self.console_input.delete(0, 'end')
        self.console_handler.write(f"$ {command}\n", COLORS['info'])
        
        # Parse and run command
        thread = threading.Thread(target=self.execute_console_command, 
                                args=(command,), daemon=True)
        thread.start()
    
    def execute_console_command(self, command: str):
        """Execute console command in background"""
        try:
            # Parse command - expect format: rediacc <command> <args>
            parts = command.split()
            if not parts or parts[0] not in ['rediacc', 'rediacc-cli']:
                self.console_handler.write("Command must start with 'rediacc'\n", COLORS['error'])
                return
            
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            # Build command
            cmd = [sys.executable, str(cli_path), '--token', token] + parts[1:]
            
            # Run command
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, text=True)
            
            # Stream output
            for line in process.stdout:
                self.console_handler.write(line)
            
            # Wait for completion
            process.wait()
            
            if process.returncode != 0:
                error = process.stderr.read()
                self.console_handler.write(error, COLORS['error'])
                
        except Exception as e:
            self.console_handler.write(f"Error: {str(e)}\n", COLORS['error'])
    
    def refresh_current_view(self):
        """Refresh the current view"""
        if self.current_view:
            self.show_view(self.current_view)
    
    def show_error(self, error: str):
        """Show error message"""
        self.status_bar.config(text=f"Error: {error}")
        messagebox.showerror("Error", error)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """Rediacc CLI GUI
Version 1.0

A graphical interface for Rediacc CLI tools.

Built with Python and Tkinter."""
        messagebox.showinfo("About", about_text)
    
    def logout(self):
        """Logout and return to login screen"""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to logout?"):
            # Run logout command
            try:
                cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
                subprocess.run([sys.executable, str(cli_path), 'logout'], check=True)
                
                # Close main window and show login
                self.root.destroy()
                login = LoginWindow(lambda tm: MainWindow(tm))
                login.root.mainloop()
            except Exception as e:
                messagebox.showerror("Logout Error", str(e))


class ResourceDialog:
    """Dialog for creating/updating resources"""
    def __init__(self, parent, token_manager: TokenManager, resource_type: str, 
                 mode: str = 'create', data: Dict = None):
        self.parent = parent
        self.token_manager = token_manager
        self.resource_type = resource_type
        self.mode = mode
        self.data = data or {}
        self.success = False
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"{mode.title()} {resource_type[:-1].title()}")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("500x400")
        self.center_dialog()
        
        self.create_widgets()
    
    def center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"500x400+{x}+{y}")
    
    def create_widgets(self):
        """Create dialog widgets based on resource type"""
        # Title
        title = tk.Label(self.dialog, 
                        text=f"{self.mode.title()} {self.resource_type[:-1].title()}",
                        font=('Arial', 14, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Form frame
        form_frame = ttk.Frame(self.dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        # Create form fields based on resource type
        self.fields = {}
        self.create_form_fields(form_frame)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        save_button = ttk.Button(button_frame, text="Save", 
                               command=self.save, style='Accent.TButton')
        save_button.pack(side='left', padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", 
                                 command=self.dialog.destroy)
        cancel_button.pack(side='left', padx=5)
    
    def create_form_fields(self, parent):
        """Create form fields based on resource type"""
        fields_map = {
            'teams': [('name', 'Team Name', 'entry')],
            'machines': [
                ('name', 'Machine Name', 'entry'),
                ('team', 'Team', 'combo_teams'),
                ('bridge', 'Bridge', 'combo_bridges')
            ],
            'repositories': [
                ('name', 'Repository Name', 'entry'),
                ('team', 'Team', 'combo_teams')
            ],
            'bridges': [
                ('name', 'Bridge Name', 'entry'),
                ('region', 'Region', 'combo_regions')
            ],
            'regions': [('name', 'Region Name', 'entry')],
            'users': [
                ('email', 'Email', 'entry'),
                ('password', 'Password', 'password')
            ]
        }
        
        fields = fields_map.get(self.resource_type, [('name', 'Name', 'entry')])
        
        for idx, (field_name, label, field_type) in enumerate(fields):
            # Label
            ttk.Label(parent, text=f"{label}:").grid(row=idx, column=0, 
                                                     sticky='w', pady=5)
            
            # Field
            if field_type == 'entry':
                field = ttk.Entry(parent, width=30)
                if self.mode == 'update' and field_name in self.data:
                    field.insert(0, self.data[field_name])
            elif field_type == 'password':
                field = ttk.Entry(parent, width=30, show='*')
            elif field_type.startswith('combo_'):
                field = ttk.Combobox(parent, width=28, state='readonly')
                self.load_combo_values(field, field_type)
                if self.mode == 'update' and field_name in self.data:
                    field.set(self.data[field_name])
            
            field.grid(row=idx, column=1, pady=5, padx=10)
            self.fields[field_name] = field
    
    def load_combo_values(self, combo: ttk.Combobox, field_type: str):
        """Load values for combo box"""
        # Extract resource type from field_type (e.g., 'combo_teams' -> 'teams')
        resource = field_type.split('_')[1]
        
        # Load values in background
        thread = threading.Thread(target=self.fetch_combo_values, 
                                args=(combo, resource), daemon=True)
        thread.start()
    
    def fetch_combo_values(self, combo: ttk.Combobox, resource: str):
        """Fetch combo values from API"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'list', resource]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', [])
                    names = [item.get('name', item.get(f'{resource[:-1]}Name', '')) 
                            for item in data]
                    self.dialog.after(0, lambda: combo.config(values=names))
                    
        except Exception:
            pass  # Silently fail - user can still type manually
    
    def save(self):
        """Save the resource"""
        # Collect values
        values = {}
        for field_name, field in self.fields.items():
            values[field_name] = field.get()
        
        # Validate required fields
        if not all(values.values()):
            messagebox.showerror("Validation Error", "All fields are required")
            return
        
        # Build command
        cli_path = Path(__file__).parent / 'rediacc-cli'
        token = self.token_manager.get_token()
        
        if self.mode == 'create':
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'create', self.resource_type[:-1]]
        else:
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'update', self.resource_type[:-1]]
        
        # Add parameters
        for field_name, value in values.items():
            cmd.extend([f'--{field_name}', value])
        
        # Run command
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    self.success = True
                    messagebox.showinfo("Success", 
                                      f"{self.resource_type[:-1].title()} {self.mode}d successfully")
                    self.dialog.destroy()
                else:
                    error = response.get('error', 'Operation failed')
                    messagebox.showerror("Error", error)
            else:
                messagebox.showerror("Error", "Operation failed")
                
        except Exception as e:
            messagebox.showerror("Error", str(e))


class QueueAddDialog:
    """Dialog for adding items to queue"""
    def __init__(self, parent, token_manager: TokenManager):
        self.parent = parent
        self.token_manager = token_manager
        self.success = False
        self.functions = {}
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add to Queue")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Make dialog larger for queue functions
        self.dialog.geometry("600x500")
        self.center_dialog()
        
        self.create_widgets()
        self.load_functions()
    
    def center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 600) // 2
        y = (self.dialog.winfo_screenheight() - 500) // 2
        self.dialog.geometry(f"600x500+{x}+{y}")
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Title
        title = tk.Label(self.dialog, text="Add Item to Queue",
                        font=('Arial', 14, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Form frame
        form_frame = ttk.Frame(self.dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        # Function selection
        ttk.Label(form_frame, text="Function:").grid(row=0, column=0, sticky='w', pady=5)
        self.function_var = tk.StringVar()
        self.function_combo = ttk.Combobox(form_frame, textvariable=self.function_var,
                                         width=40, state='readonly')
        self.function_combo.grid(row=0, column=1, pady=5, padx=10)
        self.function_combo.bind('<<ComboboxSelected>>', self.on_function_selected)
        
        # Function description
        self.desc_label = tk.Label(form_frame, text="", wraplength=400,
                                 bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'],
                                 justify='left')
        self.desc_label.grid(row=1, column=0, columnspan=2, pady=10)
        
        # Basic parameters
        ttk.Label(form_frame, text="Team:").grid(row=2, column=0, sticky='w', pady=5)
        self.team_combo = ttk.Combobox(form_frame, width=40, state='readonly')
        self.team_combo.grid(row=2, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Machine:").grid(row=3, column=0, sticky='w', pady=5)
        self.machine_combo = ttk.Combobox(form_frame, width=40, state='readonly')
        self.machine_combo.grid(row=3, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Bridge:").grid(row=4, column=0, sticky='w', pady=5)
        self.bridge_combo = ttk.Combobox(form_frame, width=40, state='readonly')
        self.bridge_combo.grid(row=4, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Priority:").grid(row=5, column=0, sticky='w', pady=5)
        self.priority_var = tk.StringVar(value="3")
        priority_scale = tk.Scale(form_frame, from_=1, to=5, orient='horizontal',
                                variable=self.priority_var, length=200,
                                bg=COLORS['bg_dark'], fg=COLORS['fg_primary'])
        priority_scale.grid(row=5, column=1, pady=5, padx=10, sticky='w')
        
        # Dynamic parameters frame
        self.params_frame = ttk.LabelFrame(form_frame, text="Function Parameters")
        self.params_frame.grid(row=6, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        self.add_button = ttk.Button(button_frame, text="Add to Queue", 
                                   command=self.add_to_queue, style='Accent.TButton')
        self.add_button.pack(side='left', padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", 
                                 command=self.dialog.destroy)
        cancel_button.pack(side='left', padx=5)
        
        # Load teams and bridges
        self.load_teams()
        self.load_bridges()
    
    def load_functions(self):
        """Load available queue functions"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'queue', 'list-functions']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    self.functions = response.get('data', {})
                    function_names = list(self.functions.keys())
                    self.function_combo.config(values=function_names)
                    if function_names:
                        self.function_combo.set(function_names[0])
                        self.on_function_selected()
                        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load functions: {str(e)}")
    
    def on_function_selected(self, event=None):
        """Handle function selection"""
        func_name = self.function_var.get()
        if func_name in self.functions:
            func_info = self.functions[func_name]
            
            # Update description
            self.desc_label.config(text=func_info.get('description', ''))
            
            # Clear existing parameter fields
            for widget in self.params_frame.winfo_children():
                widget.destroy()
            
            # Create parameter fields
            self.param_fields = {}
            params = func_info.get('params', {})
            
            for idx, (param_name, param_info) in enumerate(params.items()):
                # Label
                label_text = param_name.replace('_', ' ').title()
                if param_info.get('required'):
                    label_text += " *"
                
                ttk.Label(self.params_frame, text=f"{label_text}:").grid(
                    row=idx, column=0, sticky='w', pady=2, padx=5)
                
                # Field
                field = ttk.Entry(self.params_frame, width=30)
                field.grid(row=idx, column=1, pady=2, padx=5)
                
                # Help text
                help_text = param_info.get('help', '')
                if help_text:
                    help_label = tk.Label(self.params_frame, text=help_text,
                                        bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'],
                                        font=('Arial', 8))
                    help_label.grid(row=idx, column=2, sticky='w', padx=5)
                
                # Default value
                if 'default' in param_info:
                    field.insert(0, str(param_info['default']))
                
                self.param_fields[param_name] = field
    
    def load_teams(self):
        """Load teams for combo box"""
        thread = threading.Thread(target=self._fetch_teams, daemon=True)
        thread.start()
    
    def _fetch_teams(self):
        """Fetch teams in background"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'list', 'teams']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', [])
                    names = [item.get('name', item.get('teamName', '')) 
                            for item in data]
                    self.dialog.after(0, lambda: self.team_combo.config(values=names))
                    if names:
                        self.dialog.after(0, lambda: self.team_combo.set(names[0]))
                        self.dialog.after(0, self.on_team_selected)
                        
        except Exception:
            pass
    
    def on_team_selected(self, event=None):
        """Handle team selection - load machines for that team"""
        team = self.team_combo.get()
        if team:
            thread = threading.Thread(target=self._fetch_machines, 
                                    args=(team,), daemon=True)
            thread.start()
    
    def _fetch_machines(self, team: str):
        """Fetch machines for team"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'list', 'machines', '--team', team]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', [])
                    names = [item.get('name', item.get('machineName', '')) 
                            for item in data]
                    self.dialog.after(0, lambda: self.machine_combo.config(values=names))
                    if names:
                        self.dialog.after(0, lambda: self.machine_combo.set(names[0]))
                        
        except Exception:
            pass
    
    def load_bridges(self):
        """Load bridges for combo box"""
        thread = threading.Thread(target=self._fetch_bridges, daemon=True)
        thread.start()
    
    def _fetch_bridges(self):
        """Fetch bridges in background"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            cmd = [sys.executable, str(cli_path), '--token', token, 
                   '--output', 'json', 'list', 'bridges']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', [])
                    names = [item.get('name', item.get('bridgeName', '')) 
                            for item in data]
                    self.dialog.after(0, lambda: self.bridge_combo.config(values=names))
                    if names:
                        self.dialog.after(0, lambda: self.bridge_combo.set(names[0]))
                        
        except Exception:
            pass
    
    def add_to_queue(self):
        """Add item to queue"""
        # Validate required fields
        if not all([self.function_var.get(), self.team_combo.get(), 
                   self.machine_combo.get(), self.bridge_combo.get()]):
            messagebox.showerror("Validation Error", 
                               "Function, Team, Machine, and Bridge are required")
            return
        
        # Build command
        cli_path = Path(__file__).parent / 'rediacc-cli'
        token = self.token_manager.get_token()
        
        cmd = [sys.executable, str(cli_path), '--token', token, 
               '--output', 'json', 'queue', 'add',
               '--function', self.function_var.get(),
               '--team', self.team_combo.get(),
               '--machine', self.machine_combo.get(),
               '--bridge', self.bridge_combo.get(),
               '--priority', self.priority_var.get()]
        
        # Add function parameters
        for param_name, field in self.param_fields.items():
            value = field.get()
            if value:  # Only add non-empty values
                cmd.extend([f'--{param_name.replace("_", "-")}', value])
        
        # Run command
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    self.success = True
                    task_id = response.get('data', {}).get('task_id', 'Unknown')
                    messagebox.showinfo("Success", 
                                      f"Added to queue successfully\nTask ID: {task_id}")
                    self.dialog.destroy()
                else:
                    error = response.get('error', 'Failed to add to queue')
                    messagebox.showerror("Error", error)
            else:
                messagebox.showerror("Error", "Failed to add to queue")
                
        except Exception as e:
            messagebox.showerror("Error", str(e))


class DetailsDialog:
    """Dialog for viewing resource details"""
    def __init__(self, parent, resource_type: str, data: Dict):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"{resource_type[:-1].title()} Details")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Make dialog larger
        self.dialog.geometry("600x400")
        self.center_dialog()
        
        # Create scrolled text widget
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.text = scrolledtext.ScrolledText(text_frame, wrap='word',
                                            bg=COLORS['bg_light'], 
                                            fg=COLORS['fg_primary'],
                                            font=('Consolas', 10),
                                            insertbackground=COLORS['fg_primary'],
                                            selectbackground=COLORS['accent'],
                                            selectforeground=COLORS['fg_primary'])
        self.text.pack(fill='both', expand=True)
        
        # Format and display data
        formatted = json.dumps(data, indent=2)
        self.text.insert('1.0', formatted)
        self.text.config(state='disabled')
        
        # Close button
        close_button = ttk.Button(self.dialog, text="Close", 
                                command=self.dialog.destroy)
        close_button.pack(pady=10)
    
    def center_dialog(self):
        """Center dialog on screen"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 600) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"600x400+{x}+{y}")


class SyncDialog:
    """Dialog for file synchronization"""
    def __init__(self, parent, token_manager: TokenManager):
        self.parent = parent
        self.token_manager = token_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("File Synchronization")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.geometry("700x500")
        self.center_dialog()
        
        self.create_widgets()
    
    def center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 700) // 2
        y = (self.dialog.winfo_screenheight() - 500) // 2
        self.dialog.geometry(f"700x500+{x}+{y}")
    
    def create_widgets(self):
        """Create sync dialog widgets"""
        # Title
        title = tk.Label(self.dialog, text="File Synchronization",
                        font=('Arial', 16, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Main frame
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(padx=20, pady=10, fill='both', expand=True)
        
        # Direction selection
        direction_frame = ttk.LabelFrame(main_frame, text="Sync Direction")
        direction_frame.pack(fill='x', pady=10)
        
        self.direction_var = tk.StringVar(value="download")
        ttk.Radiobutton(direction_frame, text="Download (Remote → Local)", 
                       variable=self.direction_var, value="download").pack(anchor='w', padx=10)
        ttk.Radiobutton(direction_frame, text="Upload (Local → Remote)", 
                       variable=self.direction_var, value="upload").pack(anchor='w', padx=10)
        
        # Source/Destination
        paths_frame = ttk.Frame(main_frame)
        paths_frame.pack(fill='x', pady=10)
        
        # Local path
        ttk.Label(paths_frame, text="Local Path:").grid(row=0, column=0, sticky='w', pady=5)
        self.local_path_var = tk.StringVar()
        local_entry = ttk.Entry(paths_frame, textvariable=self.local_path_var, width=40)
        local_entry.grid(row=0, column=1, pady=5, padx=5)
        browse_button = ttk.Button(paths_frame, text="Browse", 
                                 command=self.browse_local_path)
        browse_button.grid(row=0, column=2, pady=5)
        
        # Remote settings
        ttk.Label(paths_frame, text="Machine:").grid(row=1, column=0, sticky='w', pady=5)
        self.machine_combo = ttk.Combobox(paths_frame, width=38, state='readonly')
        self.machine_combo.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(paths_frame, text="Repository:").grid(row=2, column=0, sticky='w', pady=5)
        self.repo_combo = ttk.Combobox(paths_frame, width=38, state='readonly')
        self.repo_combo.grid(row=2, column=1, pady=5, padx=5)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options")
        options_frame.pack(fill='x', pady=10)
        
        self.verify_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Verify mode (checksum comparison)", 
                       variable=self.verify_var).pack(anchor='w', padx=10)
        
        self.mirror_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Mirror mode (delete extra files)", 
                       variable=self.mirror_var).pack(anchor='w', padx=10)
        
        self.dev_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Development mode (relaxed SSH)", 
                       variable=self.dev_var).pack(anchor='w', padx=10)
        
        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        progress_label = tk.Label(main_frame, textvariable=self.progress_var,
                                bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'])
        progress_label.pack(pady=10)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        self.sync_button = ttk.Button(button_frame, text="Start Sync", 
                                    command=self.start_sync, style='Accent.TButton')
        self.sync_button.pack(side='left', padx=5)
        
        close_button = ttk.Button(button_frame, text="Close", 
                                command=self.dialog.destroy)
        close_button.pack(side='left', padx=5)
        
        # Load machines
        self.load_machines()
    
    def browse_local_path(self):
        """Browse for local directory"""
        path = filedialog.askdirectory(parent=self.dialog, 
                                      title="Select Local Directory")
        if path:
            self.local_path_var.set(path)
    
    def load_machines(self):
        """Load machines list"""
        # Implementation similar to other combo loading
        pass
    
    def start_sync(self):
        """Start synchronization"""
        # Validate inputs
        if not all([self.local_path_var.get(), self.machine_combo.get(), 
                   self.repo_combo.get()]):
            messagebox.showerror("Validation Error", "All fields are required")
            return
        
        self.sync_button.config(state='disabled')
        self.progress_var.set("Starting synchronization...")
        
        # Run sync in thread
        thread = threading.Thread(target=self.perform_sync, daemon=True)
        thread.start()
    
    def perform_sync(self):
        """Perform sync operation"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli-sync'
            token = self.token_manager.get_token()
            
            # Build command
            cmd = [sys.executable, str(cli_path), 
                   self.direction_var.get(),
                   '--local', self.local_path_var.get(),
                   '--machine', self.machine_combo.get(),
                   '--repo', self.repo_combo.get()]
            
            # Add options
            if self.verify_var.get():
                cmd.append('--verify')
            if self.mirror_var.get():
                cmd.append('--mirror')
            if self.dev_var.get():
                cmd.append('--dev')
            
            # Set token in environment
            env = os.environ.copy()
            env['REDIACC_TOKEN'] = token
            
            # Run sync
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, text=True, env=env)
            
            # Monitor output
            for line in process.stdout:
                self.dialog.after(0, self.update_progress, line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.dialog.after(0, self.sync_complete)
            else:
                error = process.stderr.read()
                self.dialog.after(0, self.sync_error, error)
                
        except Exception as e:
            self.dialog.after(0, self.sync_error, str(e))
    
    def update_progress(self, message: str):
        """Update progress message"""
        self.progress_var.set(message)
    
    def sync_complete(self):
        """Handle sync completion"""
        self.sync_button.config(state='normal')
        self.progress_var.set("Synchronization completed successfully")
        messagebox.showinfo("Success", "File synchronization completed")
    
    def sync_error(self, error: str):
        """Handle sync error"""
        self.sync_button.config(state='normal')
        self.progress_var.set("Synchronization failed")
        messagebox.showerror("Sync Error", error)


class TerminalDialog:
    """Dialog for terminal access"""
    def __init__(self, parent, token_manager: TokenManager):
        self.parent = parent
        self.token_manager = token_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Terminal Access")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.geometry("500x300")
        self.center_dialog()
        
        self.create_widgets()
    
    def center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 300) // 2
        self.dialog.geometry(f"500x300+{x}+{y}")
    
    def create_widgets(self):
        """Create terminal dialog widgets"""
        # Title
        title = tk.Label(self.dialog, text="Terminal Access",
                        font=('Arial', 16, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Info
        info = tk.Label(self.dialog, 
                       text="Connect to a machine via SSH terminal",
                       bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'])
        info.pack(pady=5)
        
        # Form
        form_frame = ttk.Frame(self.dialog)
        form_frame.pack(padx=20, pady=20)
        
        ttk.Label(form_frame, text="Machine:").grid(row=0, column=0, sticky='w', pady=5)
        self.machine_combo = ttk.Combobox(form_frame, width=30, state='readonly')
        self.machine_combo.grid(row=0, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Repository:").grid(row=1, column=0, sticky='w', pady=5)
        self.repo_combo = ttk.Combobox(form_frame, width=30, state='readonly')
        self.repo_combo.grid(row=1, column=1, pady=5, padx=10)
        
        # Command field (optional)
        ttk.Label(form_frame, text="Command:").grid(row=2, column=0, sticky='w', pady=5)
        self.command_var = tk.StringVar()
        command_entry = ttk.Entry(form_frame, textvariable=self.command_var, width=30)
        command_entry.grid(row=2, column=1, pady=5, padx=10)
        
        # Options
        self.dev_var = tk.BooleanVar()
        dev_check = ttk.Checkbutton(form_frame, text="Development mode", 
                                   variable=self.dev_var)
        dev_check.grid(row=3, column=1, sticky='w', pady=5, padx=10)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=20)
        
        connect_button = ttk.Button(button_frame, text="Connect", 
                                  command=self.connect, style='Accent.TButton')
        connect_button.pack(side='left', padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", 
                                 command=self.dialog.destroy)
        cancel_button.pack(side='left', padx=5)
        
        # Note
        note = tk.Label(self.dialog, 
                       text="Note: This will open a new terminal window",
                       bg=COLORS['bg_dark'], fg=COLORS['warning'],
                       font=('Arial', 9))
        note.pack(pady=10)
    
    def connect(self):
        """Connect to terminal"""
        machine = self.machine_combo.get()
        if not machine:
            messagebox.showerror("Error", "Please select a machine")
            return
        
        # Build command
        cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli-term'
        
        cmd = [sys.executable, str(cli_path), '--machine', machine]
        
        if self.repo_combo.get():
            cmd.extend(['--repo', self.repo_combo.get()])
        
        if self.command_var.get():
            cmd.extend(['--command', self.command_var.get()])
        
        if self.dev_var.get():
            cmd.append('--dev')
        
        # Set token in environment
        env = os.environ.copy()
        env['REDIACC_TOKEN'] = self.token_manager.get_token()
        
        try:
            # Open in new terminal window
            if is_windows():
                # Windows: open in new cmd window
                subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k'] + cmd, env=env)
            else:
                # Linux/Mac: try common terminal emulators
                terminals = ['gnome-terminal', 'xterm', 'konsole', 'terminal']
                for term in terminals:
                    try:
                        if term == 'gnome-terminal':
                            subprocess.Popen([term, '--'] + cmd, env=env)
                        else:
                            subprocess.Popen([term, '-e'] + cmd, env=env)
                        break
                    except FileNotFoundError:
                        continue
            
            messagebox.showinfo("Success", "Terminal opened in new window")
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open terminal: {str(e)}")


class VaultSettingsDialog:
    """Dialog for vault settings and password management"""
    def __init__(self, parent, token_manager: TokenManager):
        self.parent = parent
        self.token_manager = token_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Vault Settings")
        self.dialog.configure(bg=COLORS['bg_dark'])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.geometry("500x400")
        self.center_dialog()
        
        self.create_widgets()
        self.check_vault_status()
    
    def center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"500x400+{x}+{y}")
    
    def create_widgets(self):
        """Create vault settings widgets"""
        # Title
        title = tk.Label(self.dialog, text="Vault Settings",
                        font=('Arial', 16, 'bold'),
                        bg=COLORS['bg_dark'], fg=COLORS['header'])
        title.pack(pady=10)
        
        # Status frame
        status_frame = ttk.LabelFrame(self.dialog, text="Vault Status")
        status_frame.pack(padx=20, pady=10, fill='x')
        
        self.status_text = tk.Text(status_frame, height=8, width=50,
                                 bg=COLORS['bg_light'], fg=COLORS['fg_primary'],
                                 font=('Consolas', 10))
        self.status_text.pack(padx=10, pady=10)
        
        # Password frame
        password_frame = ttk.LabelFrame(self.dialog, text="Master Password")
        password_frame.pack(padx=20, pady=10, fill='x')
        
        # Password status
        self.password_status = tk.Label(password_frame, text="Checking...",
                                      bg=COLORS['bg_dark'], fg=COLORS['fg_secondary'])
        self.password_status.pack(pady=5)
        
        # Password buttons
        button_frame = ttk.Frame(password_frame)
        button_frame.pack(pady=10)
        
        self.set_password_button = ttk.Button(button_frame, text="Set Password",
                                            command=self.set_password)
        self.set_password_button.pack(side='left', padx=5)
        
        self.clear_password_button = ttk.Button(button_frame, text="Clear Password",
                                              command=self.clear_password)
        self.clear_password_button.pack(side='left', padx=5)
        
        # Close button
        close_button = ttk.Button(self.dialog, text="Close",
                                command=self.dialog.destroy)
        close_button.pack(pady=20)
    
    def check_vault_status(self):
        """Check vault encryption status"""
        try:
            cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
            token = self.token_manager.get_token()
            
            cmd = [sys.executable, str(cli_path), '--token', token,
                   '--output', 'json', 'vault', 'status']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get('success'):
                    data = response.get('data', {})
                    self.update_status_display(data)
                    
        except Exception as e:
            self.status_text.insert('1.0', f"Error checking status: {str(e)}")
    
    def update_status_display(self, data: Dict):
        """Update status display"""
        self.status_text.delete('1.0', 'end')
        
        status_lines = [
            f"Cryptography Library: {'Available' if data.get('crypto_available') else 'Not Available'}",
            f"Company: {data.get('company', 'Not set')}",
            f"Vault Encryption: {'Required' if data.get('vault_encryption_enabled') else 'Not Required'}",
            f"Master Password: {'Set' if data.get('master_password_set') else 'Not Set'}",
        ]
        
        self.status_text.insert('1.0', '\n'.join(status_lines))
        
        # Update password status
        if data.get('vault_encryption_enabled'):
            if data.get('master_password_set'):
                self.password_status.config(text="Master password is set",
                                          fg=COLORS['success'])
                self.set_password_button.config(text="Change Password")
            else:
                self.password_status.config(text="Master password not set",
                                          fg=COLORS['warning'])
        else:
            self.password_status.config(text="Vault encryption not enabled",
                                      fg=COLORS['fg_secondary'])
            self.set_password_button.config(state='disabled')
            self.clear_password_button.config(state='disabled')
    
    def set_password(self):
        """Set or change master password"""
        # Create password dialog
        pwd_dialog = tk.Toplevel(self.dialog)
        pwd_dialog.title("Set Master Password")
        pwd_dialog.configure(bg=COLORS['bg_dark'])
        pwd_dialog.transient(self.dialog)
        pwd_dialog.grab_set()
        
        # Center dialog
        pwd_dialog.geometry("400x200")
        pwd_dialog.update_idletasks()
        x = (pwd_dialog.winfo_screenwidth() - 400) // 2
        y = (pwd_dialog.winfo_screenheight() - 200) // 2
        pwd_dialog.geometry(f"400x200+{x}+{y}")
        
        # Create fields
        ttk.Label(pwd_dialog, text="Enter Master Password:").pack(pady=10)
        
        password_var = tk.StringVar()
        password_entry = ttk.Entry(pwd_dialog, textvariable=password_var, show='*', width=30)
        password_entry.pack(pady=5)
        password_entry.focus()
        
        ttk.Label(pwd_dialog, text="Confirm Password:").pack(pady=5)
        
        confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(pwd_dialog, textvariable=confirm_var, show='*', width=30)
        confirm_entry.pack(pady=5)
        
        def save_password():
            if password_var.get() != confirm_var.get():
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            if not password_var.get():
                messagebox.showerror("Error", "Password cannot be empty")
                return
            
            # Save password via CLI
            try:
                cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
                token = self.token_manager.get_token()
                
                # Use stdin to pass password securely
                cmd = [sys.executable, str(cli_path), '--token', token,
                       '--output', 'json', 'vault', 'set-password']
                
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True)
                
                # Send password twice (for confirmation)
                stdin_data = f"{password_var.get()}\n{confirm_var.get()}\n"
                stdout, stderr = process.communicate(input=stdin_data)
                
                if process.returncode == 0:
                    response = json.loads(stdout)
                    if response.get('success'):
                        messagebox.showinfo("Success", "Master password set successfully")
                        pwd_dialog.destroy()
                        self.check_vault_status()
                    else:
                        error = response.get('error', 'Failed to set password')
                        messagebox.showerror("Error", error)
                else:
                    messagebox.showerror("Error", "Failed to set password")
                    
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        # Buttons
        button_frame = ttk.Frame(pwd_dialog)
        button_frame.pack(pady=20)
        
        save_button = ttk.Button(button_frame, text="Save", command=save_password)
        save_button.pack(side='left', padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=pwd_dialog.destroy)
        cancel_button.pack(side='left', padx=5)
        
        # Bind Enter to save
        pwd_dialog.bind('<Return>', lambda e: save_password())
    
    def clear_password(self):
        """Clear master password from memory"""
        if messagebox.askyesno("Confirm", "Clear master password from memory?"):
            try:
                cli_path = Path(__file__).parent.parent / 'cli' / 'rediacc-cli'
                token = self.token_manager.get_token()
                
                cmd = [sys.executable, str(cli_path), '--token', token,
                       '--output', 'json', 'vault', 'clear-password']
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    messagebox.showinfo("Success", "Master password cleared")
                    self.check_vault_status()
                    
            except Exception as e:
                messagebox.showerror("Error", str(e))


def launch_gui():
    """Launch the GUI application"""
    import signal
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal. Closing GUI...")
        try:
            # Try to close any open windows
            import tkinter as tk
            for widget in tk._default_root.winfo_children() if tk._default_root else []:
                widget.destroy()
            if tk._default_root:
                tk._default_root.quit()
                tk._default_root.destroy()
        except:
            pass
        finally:
            import sys
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