#!/usr/bin/env python3
"""
GUI Base Classes

This module provides base classes and common GUI components for the Rediacc
CLI GUI application, including tooltip functionality and window management.
"""

import tkinter as tk
import sys
from core import i18n
from gui_utilities import (
    COLOR_TOOLTIP_BG, BORDER_WIDTH_THIN, FONT_FAMILY_DEFAULT,
    FONT_SIZE_SMALL, FONT_STYLE_NORMAL
)


# ===== TOOLTIP CLASS =====

class ToolTip:
    """Tooltip widget for displaying help text on hover"""
    
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.on_enter)
        widget.bind("<Leave>", self.on_leave)
    
    def on_enter(self, event=None):
        """Show tooltip when mouse enters widget"""
        x, y, *_ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, justify='left',
                        background=COLOR_TOOLTIP_BG, relief='solid', borderwidth=BORDER_WIDTH_THIN,
                        font=(FONT_FAMILY_DEFAULT, str(FONT_SIZE_SMALL), FONT_STYLE_NORMAL))
        label.pack()
    
    def on_leave(self, event=None):
        """Hide tooltip when mouse leaves widget"""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def create_tooltip(widget, text):
    """Create a tooltip for a widget"""
    return ToolTip(widget, text)


# ===== BASE WINDOW CLASS =====

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
        # First set the geometry to ensure proper size
        self.root.geometry(f'{width}x{height}')
        
        # Force update to calculate actual window size
        self.root.update_idletasks()
        
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate centered position
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set final geometry with position
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Force another update to ensure proper placement
        self.root.update_idletasks()
    
    def refresh_window(self):
        """Force window to refresh its display"""
        self.root.update_idletasks()
        self.root.update()
    
    def on_closing(self):
        """Handle window close event"""
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        sys.exit(0)