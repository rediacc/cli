#!/usr/bin/env python3
"""
Internationalization (i18n) module for Rediacc CLI GUI
Supports multiple languages with easy translation management
"""

from typing import Dict, Optional
import json
import os
from pathlib import Path
from config_path import get_config_dir


class I18n:
    """Internationalization manager for GUI application"""
    
    def __init__(self):
        # Load configuration from JSON file
        self._load_config()
        self.current_language = self.DEFAULT_LANGUAGE
        self._observers = []
    
    def _load_config(self):
        """Load languages and translations from JSON configuration file"""
        config_path = Path(__file__).parent.parent / 'config' / 'rediacc-gui.json'
        
        if not config_path.exists():
            raise FileNotFoundError(f"Translation configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.LANGUAGES = config.get('languages', {})
            self.DEFAULT_LANGUAGE = config.get('default_language', 'en')
            self.translations = config.get('translations', {})
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in translation configuration: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load translation configuration: {e}")
    
    
    def get_language_config_path(self) -> Path:
        """Get the path to the language configuration file"""
        # Use centralized config directory
        config_dir = get_config_dir()
        return config_dir / 'language_preference.json'
    
    def load_language_preference(self) -> str:
        """Load the saved language preference"""
        config_path = self.get_language_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    lang = data.get('language', self.DEFAULT_LANGUAGE)
                    if lang in self.LANGUAGES:
                        return lang
            except:
                pass
        return self.DEFAULT_LANGUAGE
    
    def save_language_preference(self, language: str):
        """Save the language preference"""
        if language not in self.LANGUAGES:
            return
        
        config_path = self.get_language_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({'language': language}, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def set_language(self, language: str):
        """Set the current language"""
        if language in self.LANGUAGES:
            self.current_language = language
            self.save_language_preference(language)
            self._notify_observers()
    
    def get(self, key: str, fallback: str = None, **kwargs) -> str:
        """Get a translated string for the current language
        
        Args:
            key: The translation key
            fallback: Optional fallback value if key not found
            **kwargs: Format arguments for the translation string
        """
        translation = self.translations.get(self.current_language, {}).get(key)
        if not translation:
            # Fallback to English
            translation = self.translations.get('en', {}).get(key)
            if not translation:
                # Use provided fallback or key as last resort
                translation = fallback if fallback is not None else key
        
        # Format with provided arguments
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except:
                pass
        
        return translation
    
    def register_observer(self, callback):
        """Register a callback to be called when language changes"""
        self._observers.append(callback)
    
    def unregister_observer(self, callback):
        """Unregister a language change callback"""
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self):
        """Notify all observers of language change"""
        for callback in self._observers:
            try:
                callback()
            except:
                pass
    
    def get_language_name(self, code: str) -> str:
        """Get the display name for a language code"""
        return self.LANGUAGES.get(code, code)
    
    def get_language_codes(self) -> list:
        """Get list of available language codes"""
        return list(self.LANGUAGES.keys())
    
    def get_language_names(self) -> list:
        """Get list of language display names"""
        return list(self.LANGUAGES.values())


# Singleton instance
i18n = I18n()