#!/usr/bin/env python3

import tkinter as tk
import sys
import os

# Add parent directory to path for imports if running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import i18n
from gui.utilities import (
    COLOR_TOOLTIP_BG, BORDER_WIDTH_THIN, FONT_FAMILY_DEFAULT,
    FONT_SIZE_SMALL, FONT_STYLE_NORMAL
)


# ===== TOOLTIP CLASS =====

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.on_enter)
        widget.bind("<Leave>", self.on_leave)
    
    def on_enter(self, event=None):
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
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def create_tooltip(widget, text):
    return ToolTip(widget, text)


# ===== BASE WINDOW CLASS =====

class BaseWindow:
    def __init__(self, root: tk.Tk, title: str = None):
        self.root = root
        self.root.title(title or i18n.get('app_title'))
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Escape>', lambda e: self.on_closing())
    
    def center_window(self, width: int = 800, height: int = 600):
        self.root.geometry(f'{width}x{height}')
        self.root.update_idletasks()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        self.root.update_idletasks()
    
    def refresh_window(self):
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