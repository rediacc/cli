#!/usr/bin/env python3
"""
Internationalization (i18n) module for Rediacc CLI GUI
Supports multiple languages with easy translation management
"""

from typing import Dict, Optional
import json
import os
from pathlib import Path


class I18n:
    """Internationalization manager for GUI application"""
    
    # Available languages
    LANGUAGES = {
        'en': 'English',
        'de': 'Deutsch',
        'es': 'Español',
        'fr': 'Français',
        'ja': '日本語',
        'ar': 'العربية',
        'ru': 'Русский',
        'tr': 'Türkçe',
        'zh': '中文'
    }
    
    # Default language
    DEFAULT_LANGUAGE = 'en'
    
    def __init__(self):
        self.current_language = self.DEFAULT_LANGUAGE
        self.translations = self._load_translations()
        self._observers = []
    
    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """Load all translations"""
        return {
            'en': {
                # General
                'app_title': 'Rediacc CLI Tools',
                'ready': 'Ready',
                'error': 'Error',
                'success': 'Success',
                'confirm': 'Confirm',
                'cancel': 'Cancel',
                'yes': 'Yes',
                'no': 'No',
                'loading': 'Loading...',
                'logout': 'Logout',
                'language': 'Language',
                
                # Login window
                'login_title': 'Rediacc CLI - Login',
                'login_header': 'Rediacc CLI Login',
                'email': 'Email:',
                'password': 'Password:',
                'login': 'Login',
                'logging_in': 'Logging in...',
                'login_successful': 'Login successful!',
                'login_failed': 'Login failed',
                'please_enter_credentials': 'Please enter both email and password',
                
                # Main window
                'user': 'User:',
                'logout_confirm': 'Are you sure you want to logout?',
                'resource_selection': 'Resource Selection',
                'team': 'Team:',
                'machine': 'Machine:',
                'repository': 'Repository:',
                
                # Tabs
                'plugin_manager': 'Plugin Manager',
                'terminal_access': 'Terminal Access',
                'file_sync': 'File Sync',
                
                # Plugin Manager tab
                'plugin_management': 'Plugin Management',
                'available_plugins': 'Available Plugins',
                'refresh_plugins': 'Refresh Plugins',
                'connect_to_plugin': 'Connect to Plugin',
                'plugin': 'Plugin:',
                'local_port': 'Local Port',
                'auto_port': 'Auto (7111-9111)',
                'manual_port': 'Manual:',
                'connect': 'Connect',
                'active_connections': 'Active Connections',
                'open_in_browser': 'Open in Browser',
                'copy_url': 'Copy URL',
                'disconnect': 'Disconnect',
                'refresh_status': 'Refresh Status',
                'plugin_tip': 'Tip: Double-click to open URL • Ctrl+C to copy URL',
                'found_plugins': 'Found {count} plugins',
                'found_connections': 'Found {count} active connections',
                'connecting_to': 'Connecting to {plugin}...',
                'disconnecting': 'Disconnecting {plugin}...',
                'disconnect_confirm': 'Disconnect {plugin}?',
                'successfully_connected': 'Successfully connected to {plugin}',
                'access_at': 'Access at: {url}',
                'connection_failed': 'Connection failed',
                'disconnected': 'Disconnected {plugin}',
                'disconnect_failed': 'Disconnect failed',
                'opened_in_browser': 'Opened {url} in browser',
                'copied_to_clipboard': 'Copied {url} to clipboard',
                'port_error': 'Please enter a port number',
                'port_range_error': 'Port must be between 1024 and 65535',
                'invalid_port': 'Invalid port number',
                
                # Terminal tab
                'command': 'Command:',
                'execute_command': 'Execute Command',
                'open_repo_terminal': 'Open Interactive Repo Terminal',
                'open_machine_terminal': 'Open Interactive Machine Terminal',
                'output': 'Output:',
                'command_executed': 'Command executed',
                'executing_command': 'Executing command...',
                'terminal_instructions': 'To open {description}, run this command in a terminal window:',
                'or_from_any_directory': 'Or from any directory:',
                'launched_terminal': 'Launched terminal window...',
                'launched_wt': 'Launched in Windows Terminal...',
                'launched_wsl': 'Launched in new WSL window...',
                'could_not_launch': 'Note: Could not launch terminal automatically in WSL.',
                'select_all_fields': 'Please select team, machine, repository and enter a command',
                'select_team_machine_repo': 'Please select team, machine and repository',
                'select_team_machine': 'Please select team and machine',
                
                # File Sync tab
                'direction': 'Direction:',
                'upload': 'Upload',
                'download': 'Download',
                'local_path': 'Local Path:',
                'browse': 'Browse...',
                'options': 'Options',
                'mirror_delete': 'Mirror (delete extra files)',
                'verify_transfer': 'Verify after transfer',
                'preview_changes': 'Preview changes (--confirm)',
                'start_sync': 'Start Sync',
                'sync_completed': 'Sync completed',
                'starting_sync': 'Starting {direction}...',
                'fill_all_fields': 'Please fill in all fields',
                
                # Status messages
                'loading_teams': 'Loading teams...',
                'loading_machines': 'Loading machines for {team}...',
                'loading_repositories': 'Loading repositories for {team}...',
                'loading_plugins': 'Loading plugins...',
                'refreshing_connections': 'Refreshing connections...',
                'authentication_expired': 'Authentication expired. Please login again.',
                'session_expired': 'Your session has expired. Please login again.',
                
                # Error messages
                'failed_to_load_teams': 'Failed to load teams',
                'failed_to_load_machines': 'Failed to load machines',
                'failed_to_load_repositories': 'Failed to load repositories',
                'select_connection': 'Please select a connection to {action}',
                'select_all_plugin_fields': 'Please select all fields',
                
                # Window titles
                'an_interactive_repo_terminal': 'an interactive repository terminal',
                'an_interactive_machine_terminal': 'an interactive machine terminal',
            },
            
            'de': {
                # General
                'app_title': 'Rediacc CLI Werkzeuge',
                'ready': 'Bereit',
                'error': 'Fehler',
                'success': 'Erfolg',
                'confirm': 'Bestätigen',
                'cancel': 'Abbrechen',
                'yes': 'Ja',
                'no': 'Nein',
                'loading': 'Laden...',
                'logout': 'Abmelden',
                'language': 'Sprache',
                
                # Login window
                'login_title': 'Rediacc CLI - Anmeldung',
                'login_header': 'Rediacc CLI Anmeldung',
                'email': 'E-Mail:',
                'password': 'Passwort:',
                'login': 'Anmelden',
                'logging_in': 'Anmeldung läuft...',
                'login_successful': 'Anmeldung erfolgreich!',
                'login_failed': 'Anmeldung fehlgeschlagen',
                'please_enter_credentials': 'Bitte geben Sie E-Mail und Passwort ein',
                
                # Main window
                'user': 'Benutzer:',
                'logout_confirm': 'Möchten Sie sich wirklich abmelden?',
                'resource_selection': 'Ressourcenauswahl',
                'team': 'Team:',
                'machine': 'Maschine:',
                'repository': 'Repository:',
                
                # Tabs
                'plugin_manager': 'Plugin-Manager',
                'terminal_access': 'Terminal-Zugriff',
                'file_sync': 'Datei-Synchronisation',
                
                # Plugin Manager tab
                'plugin_management': 'Plugin-Verwaltung',
                'available_plugins': 'Verfügbare Plugins',
                'refresh_plugins': 'Plugins aktualisieren',
                'connect_to_plugin': 'Mit Plugin verbinden',
                'plugin': 'Plugin:',
                'local_port': 'Lokaler Port',
                'auto_port': 'Auto (7111-9111)',
                'manual_port': 'Manuell:',
                'connect': 'Verbinden',
                'active_connections': 'Aktive Verbindungen',
                'open_in_browser': 'Im Browser öffnen',
                'copy_url': 'URL kopieren',
                'disconnect': 'Trennen',
                'refresh_status': 'Status aktualisieren',
                'plugin_tip': 'Tipp: Doppelklick zum Öffnen der URL • Strg+C zum Kopieren der URL',
                'found_plugins': '{count} Plugins gefunden',
                'found_connections': '{count} aktive Verbindungen gefunden',
                'connecting_to': 'Verbinde mit {plugin}...',
                'disconnecting': 'Trenne {plugin}...',
                'disconnect_confirm': '{plugin} trennen?',
                'successfully_connected': 'Erfolgreich mit {plugin} verbunden',
                'access_at': 'Zugriff unter: {url}',
                'connection_failed': 'Verbindung fehlgeschlagen',
                'disconnected': '{plugin} getrennt',
                'disconnect_failed': 'Trennung fehlgeschlagen',
                'opened_in_browser': '{url} im Browser geöffnet',
                'copied_to_clipboard': '{url} in Zwischenablage kopiert',
                'port_error': 'Bitte geben Sie eine Portnummer ein',
                'port_range_error': 'Port muss zwischen 1024 und 65535 liegen',
                'invalid_port': 'Ungültige Portnummer',
                
                # Terminal tab
                'command': 'Befehl:',
                'execute_command': 'Befehl ausführen',
                'open_repo_terminal': 'Interaktives Repo-Terminal öffnen',
                'open_machine_terminal': 'Interaktives Maschinen-Terminal öffnen',
                'output': 'Ausgabe:',
                'command_executed': 'Befehl ausgeführt',
                'executing_command': 'Führe Befehl aus...',
                'terminal_instructions': 'Um {description} zu öffnen, führen Sie diesen Befehl in einem Terminal aus:',
                'or_from_any_directory': 'Oder aus einem beliebigen Verzeichnis:',
                'launched_terminal': 'Terminal-Fenster gestartet...',
                'launched_wt': 'In Windows Terminal gestartet...',
                'launched_wsl': 'In neuem WSL-Fenster gestartet...',
                'could_not_launch': 'Hinweis: Terminal konnte in WSL nicht automatisch gestartet werden.',
                'select_all_fields': 'Bitte wählen Sie Team, Maschine, Repository und geben Sie einen Befehl ein',
                'select_team_machine_repo': 'Bitte wählen Sie Team, Maschine und Repository',
                'select_team_machine': 'Bitte wählen Sie Team und Maschine',
                
                # File Sync tab
                'direction': 'Richtung:',
                'upload': 'Hochladen',
                'download': 'Herunterladen',
                'local_path': 'Lokaler Pfad:',
                'browse': 'Durchsuchen...',
                'options': 'Optionen',
                'mirror_delete': 'Spiegeln (zusätzliche Dateien löschen)',
                'verify_transfer': 'Nach Übertragung verifizieren',
                'preview_changes': 'Änderungen vorschauen (--confirm)',
                'start_sync': 'Synchronisation starten',
                'sync_completed': 'Synchronisation abgeschlossen',
                'starting_sync': 'Starte {direction}...',
                'fill_all_fields': 'Bitte füllen Sie alle Felder aus',
                
                # Status messages
                'loading_teams': 'Lade Teams...',
                'loading_machines': 'Lade Maschinen für {team}...',
                'loading_repositories': 'Lade Repositories für {team}...',
                'loading_plugins': 'Lade Plugins...',
                'refreshing_connections': 'Aktualisiere Verbindungen...',
                'authentication_expired': 'Authentifizierung abgelaufen. Bitte melden Sie sich erneut an.',
                'session_expired': 'Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.',
                
                # Error messages
                'failed_to_load_teams': 'Fehler beim Laden der Teams',
                'failed_to_load_machines': 'Fehler beim Laden der Maschinen',
                'failed_to_load_repositories': 'Fehler beim Laden der Repositories',
                'select_connection': 'Bitte wählen Sie eine Verbindung zum {action}',
                'select_all_plugin_fields': 'Bitte wählen Sie alle Felder',
                
                # Window titles
                'an_interactive_repo_terminal': 'ein interaktives Repository-Terminal',
                'an_interactive_machine_terminal': 'ein interaktives Maschinen-Terminal',
            },
            
            'es': {
                # General
                'app_title': 'Herramientas CLI de Rediacc',
                'ready': 'Listo',
                'error': 'Error',
                'success': 'Éxito',
                'confirm': 'Confirmar',
                'cancel': 'Cancelar',
                'yes': 'Sí',
                'no': 'No',
                'loading': 'Cargando...',
                'logout': 'Cerrar sesión',
                'language': 'Idioma',
                
                # Login window
                'login_title': 'Rediacc CLI - Iniciar sesión',
                'login_header': 'Inicio de sesión de Rediacc CLI',
                'email': 'Correo electrónico:',
                'password': 'Contraseña:',
                'login': 'Iniciar sesión',
                'logging_in': 'Iniciando sesión...',
                'login_successful': '¡Inicio de sesión exitoso!',
                'login_failed': 'Error al iniciar sesión',
                'please_enter_credentials': 'Por favor ingrese correo electrónico y contraseña',
                
                # Main window
                'user': 'Usuario:',
                'logout_confirm': '¿Está seguro de que desea cerrar sesión?',
                'resource_selection': 'Selección de recursos',
                'team': 'Equipo:',
                'machine': 'Máquina:',
                'repository': 'Repositorio:',
                
                # Tabs
                'plugin_manager': 'Gestor de plugins',
                'terminal_access': 'Acceso a terminal',
                'file_sync': 'Sincronización de archivos',
                
                # Plugin Manager tab
                'plugin_management': 'Gestión de plugins',
                'available_plugins': 'Plugins disponibles',
                'refresh_plugins': 'Actualizar plugins',
                'connect_to_plugin': 'Conectar al plugin',
                'plugin': 'Plugin:',
                'local_port': 'Puerto local',
                'auto_port': 'Auto (7111-9111)',
                'manual_port': 'Manual:',
                'connect': 'Conectar',
                'active_connections': 'Conexiones activas',
                'open_in_browser': 'Abrir en navegador',
                'copy_url': 'Copiar URL',
                'disconnect': 'Desconectar',
                'refresh_status': 'Actualizar estado',
                'plugin_tip': 'Consejo: Doble clic para abrir URL • Ctrl+C para copiar URL',
                'found_plugins': 'Se encontraron {count} plugins',
                'found_connections': 'Se encontraron {count} conexiones activas',
                'connecting_to': 'Conectando a {plugin}...',
                'disconnecting': 'Desconectando {plugin}...',
                'disconnect_confirm': '¿Desconectar {plugin}?',
                'successfully_connected': 'Conectado exitosamente a {plugin}',
                'access_at': 'Acceder en: {url}',
                'connection_failed': 'Conexión fallida',
                'disconnected': '{plugin} desconectado',
                'disconnect_failed': 'Error al desconectar',
                'opened_in_browser': '{url} abierto en navegador',
                'copied_to_clipboard': '{url} copiado al portapapeles',
                'port_error': 'Por favor ingrese un número de puerto',
                'port_range_error': 'El puerto debe estar entre 1024 y 65535',
                'invalid_port': 'Número de puerto inválido',
                
                # Terminal tab
                'command': 'Comando:',
                'execute_command': 'Ejecutar comando',
                'open_repo_terminal': 'Abrir terminal interactivo del repositorio',
                'open_machine_terminal': 'Abrir terminal interactivo de la máquina',
                'output': 'Salida:',
                'command_executed': 'Comando ejecutado',
                'executing_command': 'Ejecutando comando...',
                'terminal_instructions': 'Para abrir {description}, ejecute este comando en una ventana de terminal:',
                'or_from_any_directory': 'O desde cualquier directorio:',
                'launched_terminal': 'Ventana de terminal iniciada...',
                'launched_wt': 'Iniciado en Windows Terminal...',
                'launched_wsl': 'Iniciado en nueva ventana WSL...',
                'could_not_launch': 'Nota: No se pudo iniciar el terminal automáticamente en WSL.',
                'select_all_fields': 'Por favor seleccione equipo, máquina, repositorio e ingrese un comando',
                'select_team_machine_repo': 'Por favor seleccione equipo, máquina y repositorio',
                'select_team_machine': 'Por favor seleccione equipo y máquina',
                
                # File Sync tab
                'direction': 'Dirección:',
                'upload': 'Subir',
                'download': 'Descargar',
                'local_path': 'Ruta local:',
                'browse': 'Examinar...',
                'options': 'Opciones',
                'mirror_delete': 'Espejo (eliminar archivos adicionales)',
                'verify_transfer': 'Verificar después de la transferencia',
                'preview_changes': 'Vista previa de cambios (--confirm)',
                'start_sync': 'Iniciar sincronización',
                'sync_completed': 'Sincronización completada',
                'starting_sync': 'Iniciando {direction}...',
                'fill_all_fields': 'Por favor complete todos los campos',
                
                # Status messages
                'loading_teams': 'Cargando equipos...',
                'loading_machines': 'Cargando máquinas para {team}...',
                'loading_repositories': 'Cargando repositorios para {team}...',
                'loading_plugins': 'Cargando plugins...',
                'refreshing_connections': 'Actualizando conexiones...',
                'authentication_expired': 'Autenticación expirada. Por favor inicie sesión nuevamente.',
                'session_expired': 'Su sesión ha expirado. Por favor inicie sesión nuevamente.',
                
                # Error messages
                'failed_to_load_teams': 'Error al cargar equipos',
                'failed_to_load_machines': 'Error al cargar máquinas',
                'failed_to_load_repositories': 'Error al cargar repositorios',
                'select_connection': 'Por favor seleccione una conexión para {action}',
                'select_all_plugin_fields': 'Por favor seleccione todos los campos',
                
                # Window titles
                'an_interactive_repo_terminal': 'un terminal interactivo del repositorio',
                'an_interactive_machine_terminal': 'un terminal interactivo de la máquina',
            },
            
            'fr': {
                # General
                'app_title': 'Outils CLI Rediacc',
                'ready': 'Prêt',
                'error': 'Erreur',
                'success': 'Succès',
                'confirm': 'Confirmer',
                'cancel': 'Annuler',
                'yes': 'Oui',
                'no': 'Non',
                'loading': 'Chargement...',
                'logout': 'Déconnexion',
                'language': 'Langue',
                
                # Login window
                'login_title': 'Rediacc CLI - Connexion',
                'login_header': 'Connexion Rediacc CLI',
                'email': 'E-mail :',
                'password': 'Mot de passe :',
                'login': 'Se connecter',
                'logging_in': 'Connexion en cours...',
                'login_successful': 'Connexion réussie !',
                'login_failed': 'Échec de la connexion',
                'please_enter_credentials': 'Veuillez entrer l\'e-mail et le mot de passe',
                
                # Main window
                'user': 'Utilisateur :',
                'logout_confirm': 'Êtes-vous sûr de vouloir vous déconnecter ?',
                'resource_selection': 'Sélection des ressources',
                'team': 'Équipe :',
                'machine': 'Machine :',
                'repository': 'Dépôt :',
                
                # Tabs
                'plugin_manager': 'Gestionnaire de plugins',
                'terminal_access': 'Accès terminal',
                'file_sync': 'Synchronisation de fichiers',
                
                # Plugin Manager tab
                'plugin_management': 'Gestion des plugins',
                'available_plugins': 'Plugins disponibles',
                'refresh_plugins': 'Actualiser les plugins',
                'connect_to_plugin': 'Se connecter au plugin',
                'plugin': 'Plugin :',
                'local_port': 'Port local',
                'auto_port': 'Auto (7111-9111)',
                'manual_port': 'Manuel :',
                'connect': 'Connecter',
                'active_connections': 'Connexions actives',
                'open_in_browser': 'Ouvrir dans le navigateur',
                'copy_url': 'Copier l\'URL',
                'disconnect': 'Déconnecter',
                'refresh_status': 'Actualiser le statut',
                'plugin_tip': 'Astuce : Double-clic pour ouvrir l\'URL • Ctrl+C pour copier l\'URL',
                'found_plugins': '{count} plugins trouvés',
                'found_connections': '{count} connexions actives trouvées',
                'connecting_to': 'Connexion à {plugin}...',
                'disconnecting': 'Déconnexion de {plugin}...',
                'disconnect_confirm': 'Déconnecter {plugin} ?',
                'successfully_connected': 'Connecté avec succès à {plugin}',
                'access_at': 'Accéder à : {url}',
                'connection_failed': 'Échec de la connexion',
                'disconnected': '{plugin} déconnecté',
                'disconnect_failed': 'Échec de la déconnexion',
                'opened_in_browser': '{url} ouvert dans le navigateur',
                'copied_to_clipboard': '{url} copié dans le presse-papiers',
                'port_error': 'Veuillez entrer un numéro de port',
                'port_range_error': 'Le port doit être entre 1024 et 65535',
                'invalid_port': 'Numéro de port invalide',
                
                # Terminal tab
                'command': 'Commande :',
                'execute_command': 'Exécuter la commande',
                'open_repo_terminal': 'Ouvrir un terminal interactif du dépôt',
                'open_machine_terminal': 'Ouvrir un terminal interactif de la machine',
                'output': 'Sortie :',
                'command_executed': 'Commande exécutée',
                'executing_command': 'Exécution de la commande...',
                'terminal_instructions': 'Pour ouvrir {description}, exécutez cette commande dans une fenêtre de terminal :',
                'or_from_any_directory': 'Ou depuis n\'importe quel répertoire :',
                'launched_terminal': 'Fenêtre de terminal lancée...',
                'launched_wt': 'Lancé dans Windows Terminal...',
                'launched_wsl': 'Lancé dans une nouvelle fenêtre WSL...',
                'could_not_launch': 'Note : Impossible de lancer le terminal automatiquement dans WSL.',
                'select_all_fields': 'Veuillez sélectionner l\'équipe, la machine, le dépôt et entrer une commande',
                'select_team_machine_repo': 'Veuillez sélectionner l\'équipe, la machine et le dépôt',
                'select_team_machine': 'Veuillez sélectionner l\'équipe et la machine',
                
                # File Sync tab
                'direction': 'Direction :',
                'upload': 'Téléverser',
                'download': 'Télécharger',
                'local_path': 'Chemin local :',
                'browse': 'Parcourir...',
                'options': 'Options',
                'mirror_delete': 'Miroir (supprimer les fichiers supplémentaires)',
                'verify_transfer': 'Vérifier après le transfert',
                'preview_changes': 'Aperçu des modifications (--confirm)',
                'start_sync': 'Démarrer la synchronisation',
                'sync_completed': 'Synchronisation terminée',
                'starting_sync': 'Démarrage {direction}...',
                'fill_all_fields': 'Veuillez remplir tous les champs',
                
                # Status messages
                'loading_teams': 'Chargement des équipes...',
                'loading_machines': 'Chargement des machines pour {team}...',
                'loading_repositories': 'Chargement des dépôts pour {team}...',
                'loading_plugins': 'Chargement des plugins...',
                'refreshing_connections': 'Actualisation des connexions...',
                'authentication_expired': 'Authentification expirée. Veuillez vous reconnecter.',
                'session_expired': 'Votre session a expiré. Veuillez vous reconnecter.',
                
                # Error messages
                'failed_to_load_teams': 'Échec du chargement des équipes',
                'failed_to_load_machines': 'Échec du chargement des machines',
                'failed_to_load_repositories': 'Échec du chargement des dépôts',
                'select_connection': 'Veuillez sélectionner une connexion pour {action}',
                'select_all_plugin_fields': 'Veuillez sélectionner tous les champs',
                
                # Window titles
                'an_interactive_repo_terminal': 'un terminal interactif du dépôt',
                'an_interactive_machine_terminal': 'un terminal interactif de la machine',
            },
            
            'ja': {
                # General
                'app_title': 'Rediacc CLI ツール',
                'ready': '準備完了',
                'error': 'エラー',
                'success': '成功',
                'confirm': '確認',
                'cancel': 'キャンセル',
                'yes': 'はい',
                'no': 'いいえ',
                'loading': '読み込み中...',
                'logout': 'ログアウト',
                'language': '言語',
                
                # Login window
                'login_title': 'Rediacc CLI - ログイン',
                'login_header': 'Rediacc CLI ログイン',
                'email': 'メールアドレス：',
                'password': 'パスワード：',
                'login': 'ログイン',
                'logging_in': 'ログイン中...',
                'login_successful': 'ログイン成功！',
                'login_failed': 'ログイン失敗',
                'please_enter_credentials': 'メールアドレスとパスワードを入力してください',
                
                # Main window
                'user': 'ユーザー：',
                'logout_confirm': '本当にログアウトしますか？',
                'resource_selection': 'リソース選択',
                'team': 'チーム：',
                'machine': 'マシン：',
                'repository': 'リポジトリ：',
                
                # Tabs
                'plugin_manager': 'プラグインマネージャー',
                'terminal_access': 'ターミナルアクセス',
                'file_sync': 'ファイル同期',
                
                # Plugin Manager tab
                'plugin_management': 'プラグイン管理',
                'available_plugins': '利用可能なプラグイン',
                'refresh_plugins': 'プラグインを更新',
                'connect_to_plugin': 'プラグインに接続',
                'plugin': 'プラグイン：',
                'local_port': 'ローカルポート',
                'auto_port': '自動 (7111-9111)',
                'manual_port': '手動：',
                'connect': '接続',
                'active_connections': 'アクティブな接続',
                'open_in_browser': 'ブラウザで開く',
                'copy_url': 'URLをコピー',
                'disconnect': '切断',
                'refresh_status': 'ステータスを更新',
                'plugin_tip': 'ヒント：ダブルクリックでURLを開く • Ctrl+CでURLをコピー',
                'found_plugins': '{count}個のプラグインが見つかりました',
                'found_connections': '{count}個のアクティブな接続が見つかりました',
                'connecting_to': '{plugin}に接続中...',
                'disconnecting': '{plugin}を切断中...',
                'disconnect_confirm': '{plugin}を切断しますか？',
                'successfully_connected': '{plugin}への接続に成功しました',
                'access_at': 'アクセス先：{url}',
                'connection_failed': '接続失敗',
                'disconnected': '{plugin}が切断されました',
                'disconnect_failed': '切断失敗',
                'opened_in_browser': '{url}をブラウザで開きました',
                'copied_to_clipboard': '{url}をクリップボードにコピーしました',
                'port_error': 'ポート番号を入力してください',
                'port_range_error': 'ポートは1024から65535の間でなければなりません',
                'invalid_port': '無効なポート番号',
                
                # Terminal tab
                'command': 'コマンド：',
                'execute_command': 'コマンドを実行',
                'open_repo_terminal': 'インタラクティブリポジトリターミナルを開く',
                'open_machine_terminal': 'インタラクティブマシンターミナルを開く',
                'output': '出力：',
                'command_executed': 'コマンドが実行されました',
                'executing_command': 'コマンド実行中...',
                'terminal_instructions': '{description}を開くには、ターミナルウィンドウで次のコマンドを実行してください：',
                'or_from_any_directory': 'または任意のディレクトリから：',
                'launched_terminal': 'ターミナルウィンドウを起動しました...',
                'launched_wt': 'Windows Terminalで起動しました...',
                'launched_wsl': '新しいWSLウィンドウで起動しました...',
                'could_not_launch': '注：WSLでターミナルを自動的に起動できませんでした。',
                'select_all_fields': 'チーム、マシン、リポジトリを選択し、コマンドを入力してください',
                'select_team_machine_repo': 'チーム、マシン、リポジトリを選択してください',
                'select_team_machine': 'チームとマシンを選択してください',
                
                # File Sync tab
                'direction': '方向：',
                'upload': 'アップロード',
                'download': 'ダウンロード',
                'local_path': 'ローカルパス：',
                'browse': '参照...',
                'options': 'オプション',
                'mirror_delete': 'ミラー（追加ファイルを削除）',
                'verify_transfer': '転送後に検証',
                'preview_changes': '変更をプレビュー (--confirm)',
                'start_sync': '同期を開始',
                'sync_completed': '同期完了',
                'starting_sync': '{direction}を開始中...',
                'fill_all_fields': 'すべてのフィールドに入力してください',
                
                # Status messages
                'loading_teams': 'チームを読み込み中...',
                'loading_machines': '{team}のマシンを読み込み中...',
                'loading_repositories': '{team}のリポジトリを読み込み中...',
                'loading_plugins': 'プラグインを読み込み中...',
                'refreshing_connections': '接続を更新中...',
                'authentication_expired': '認証の有効期限が切れました。再度ログインしてください。',
                'session_expired': 'セッションの有効期限が切れました。再度ログインしてください。',
                
                # Error messages
                'failed_to_load_teams': 'チームの読み込みに失敗しました',
                'failed_to_load_machines': 'マシンの読み込みに失敗しました',
                'failed_to_load_repositories': 'リポジトリの読み込みに失敗しました',
                'select_connection': '{action}する接続を選択してください',
                'select_all_plugin_fields': 'すべてのフィールドを選択してください',
                
                # Window titles
                'an_interactive_repo_terminal': 'インタラクティブリポジトリターミナル',
                'an_interactive_machine_terminal': 'インタラクティブマシンターミナル',
            },
            
            'ar': {
                # General
                'app_title': 'أدوات Rediacc CLI',
                'ready': 'جاهز',
                'error': 'خطأ',
                'success': 'نجاح',
                'confirm': 'تأكيد',
                'cancel': 'إلغاء',
                'yes': 'نعم',
                'no': 'لا',
                'loading': 'جار التحميل...',
                'logout': 'تسجيل الخروج',
                'language': 'اللغة',
                
                # Login window
                'login_title': 'Rediacc CLI - تسجيل الدخول',
                'login_header': 'تسجيل دخول Rediacc CLI',
                'email': 'البريد الإلكتروني:',
                'password': 'كلمة المرور:',
                'login': 'تسجيل الدخول',
                'logging_in': 'جار تسجيل الدخول...',
                'login_successful': 'تم تسجيل الدخول بنجاح!',
                'login_failed': 'فشل تسجيل الدخول',
                'please_enter_credentials': 'الرجاء إدخال البريد الإلكتروني وكلمة المرور',
                
                # Main window
                'user': 'المستخدم:',
                'logout_confirm': 'هل أنت متأكد من تسجيل الخروج؟',
                'resource_selection': 'اختيار الموارد',
                'team': 'الفريق:',
                'machine': 'الجهاز:',
                'repository': 'المستودع:',
                
                # Tabs
                'plugin_manager': 'مدير الإضافات',
                'terminal_access': 'الوصول إلى المحطة الطرفية',
                'file_sync': 'مزامنة الملفات',
                
                # Plugin Manager tab
                'plugin_management': 'إدارة الإضافات',
                'available_plugins': 'الإضافات المتاحة',
                'refresh_plugins': 'تحديث الإضافات',
                'connect_to_plugin': 'الاتصال بالإضافة',
                'plugin': 'الإضافة:',
                'local_port': 'المنفذ المحلي',
                'auto_port': 'تلقائي (7111-9111)',
                'manual_port': 'يدوي:',
                'connect': 'اتصال',
                'active_connections': 'الاتصالات النشطة',
                'open_in_browser': 'فتح في المتصفح',
                'copy_url': 'نسخ الرابط',
                'disconnect': 'قطع الاتصال',
                'refresh_status': 'تحديث الحالة',
                'plugin_tip': 'نصيحة: انقر مرتين لفتح الرابط • Ctrl+C لنسخ الرابط',
                'found_plugins': 'تم العثور على {count} إضافة',
                'found_connections': 'تم العثور على {count} اتصال نشط',
                'connecting_to': 'جار الاتصال بـ {plugin}...',
                'disconnecting': 'جار قطع الاتصال بـ {plugin}...',
                'disconnect_confirm': 'قطع الاتصال بـ {plugin}؟',
                'successfully_connected': 'تم الاتصال بنجاح بـ {plugin}',
                'access_at': 'الوصول عبر: {url}',
                'connection_failed': 'فشل الاتصال',
                'disconnected': 'تم قطع الاتصال بـ {plugin}',
                'disconnect_failed': 'فشل قطع الاتصال',
                'opened_in_browser': 'تم فتح {url} في المتصفح',
                'copied_to_clipboard': 'تم نسخ {url} إلى الحافظة',
                'port_error': 'الرجاء إدخال رقم المنفذ',
                'port_range_error': 'يجب أن يكون المنفذ بين 1024 و 65535',
                'invalid_port': 'رقم منفذ غير صالح',
                
                # Terminal tab
                'command': 'الأمر:',
                'execute_command': 'تنفيذ الأمر',
                'open_repo_terminal': 'فتح محطة طرفية تفاعلية للمستودع',
                'open_machine_terminal': 'فتح محطة طرفية تفاعلية للجهاز',
                'output': 'المخرجات:',
                'command_executed': 'تم تنفيذ الأمر',
                'executing_command': 'جار تنفيذ الأمر...',
                'terminal_instructions': 'لفتح {description}، قم بتشغيل هذا الأمر في نافذة المحطة الطرفية:',
                'or_from_any_directory': 'أو من أي دليل:',
                'launched_terminal': 'تم تشغيل نافذة المحطة الطرفية...',
                'launched_wt': 'تم التشغيل في Windows Terminal...',
                'launched_wsl': 'تم التشغيل في نافذة WSL جديدة...',
                'could_not_launch': 'ملاحظة: لا يمكن تشغيل المحطة الطرفية تلقائيًا في WSL.',
                'select_all_fields': 'الرجاء اختيار الفريق والجهاز والمستودع وإدخال أمر',
                'select_team_machine_repo': 'الرجاء اختيار الفريق والجهاز والمستودع',
                'select_team_machine': 'الرجاء اختيار الفريق والجهاز',
                
                # File Sync tab
                'direction': 'الاتجاه:',
                'upload': 'رفع',
                'download': 'تحميل',
                'local_path': 'المسار المحلي:',
                'browse': 'استعراض...',
                'options': 'خيارات',
                'mirror_delete': 'مرآة (حذف الملفات الإضافية)',
                'verify_transfer': 'التحقق بعد النقل',
                'preview_changes': 'معاينة التغييرات (--confirm)',
                'start_sync': 'بدء المزامنة',
                'sync_completed': 'اكتملت المزامنة',
                'starting_sync': 'بدء {direction}...',
                'fill_all_fields': 'الرجاء ملء جميع الحقول',
                
                # Status messages
                'loading_teams': 'جار تحميل الفرق...',
                'loading_machines': 'جار تحميل الأجهزة لـ {team}...',
                'loading_repositories': 'جار تحميل المستودعات لـ {team}...',
                'loading_plugins': 'جار تحميل الإضافات...',
                'refreshing_connections': 'جار تحديث الاتصالات...',
                'authentication_expired': 'انتهت صلاحية المصادقة. الرجاء تسجيل الدخول مرة أخرى.',
                'session_expired': 'انتهت صلاحية جلستك. الرجاء تسجيل الدخول مرة أخرى.',
                
                # Error messages
                'failed_to_load_teams': 'فشل تحميل الفرق',
                'failed_to_load_machines': 'فشل تحميل الأجهزة',
                'failed_to_load_repositories': 'فشل تحميل المستودعات',
                'select_connection': 'الرجاء اختيار اتصال لـ {action}',
                'select_all_plugin_fields': 'الرجاء اختيار جميع الحقول',
                
                # Window titles
                'an_interactive_repo_terminal': 'محطة طرفية تفاعلية للمستودع',
                'an_interactive_machine_terminal': 'محطة طرفية تفاعلية للجهاز',
            },
            
            'ru': {
                # General
                'app_title': 'Инструменты Rediacc CLI',
                'ready': 'Готово',
                'error': 'Ошибка',
                'success': 'Успех',
                'confirm': 'Подтвердить',
                'cancel': 'Отмена',
                'yes': 'Да',
                'no': 'Нет',
                'loading': 'Загрузка...',
                'logout': 'Выход',
                'language': 'Язык',
                
                # Login window
                'login_title': 'Rediacc CLI - Вход',
                'login_header': 'Вход в Rediacc CLI',
                'email': 'Электронная почта:',
                'password': 'Пароль:',
                'login': 'Войти',
                'logging_in': 'Вход...',
                'login_successful': 'Вход выполнен успешно!',
                'login_failed': 'Ошибка входа',
                'please_enter_credentials': 'Пожалуйста, введите электронную почту и пароль',
                
                # Main window
                'user': 'Пользователь:',
                'logout_confirm': 'Вы уверены, что хотите выйти?',
                'resource_selection': 'Выбор ресурсов',
                'team': 'Команда:',
                'machine': 'Машина:',
                'repository': 'Репозиторий:',
                
                # Tabs
                'plugin_manager': 'Менеджер плагинов',
                'terminal_access': 'Доступ к терминалу',
                'file_sync': 'Синхронизация файлов',
                
                # Plugin Manager tab
                'plugin_management': 'Управление плагинами',
                'available_plugins': 'Доступные плагины',
                'refresh_plugins': 'Обновить плагины',
                'connect_to_plugin': 'Подключиться к плагину',
                'plugin': 'Плагин:',
                'local_port': 'Локальный порт',
                'auto_port': 'Авто (7111-9111)',
                'manual_port': 'Вручную:',
                'connect': 'Подключить',
                'active_connections': 'Активные подключения',
                'open_in_browser': 'Открыть в браузере',
                'copy_url': 'Копировать URL',
                'disconnect': 'Отключить',
                'refresh_status': 'Обновить статус',
                'plugin_tip': 'Совет: Дважды щелкните для открытия URL • Ctrl+C для копирования URL',
                'found_plugins': 'Найдено плагинов: {count}',
                'found_connections': 'Найдено активных подключений: {count}',
                'connecting_to': 'Подключение к {plugin}...',
                'disconnecting': 'Отключение {plugin}...',
                'disconnect_confirm': 'Отключить {plugin}?',
                'successfully_connected': 'Успешно подключено к {plugin}',
                'access_at': 'Доступ по адресу: {url}',
                'connection_failed': 'Ошибка подключения',
                'disconnected': '{plugin} отключен',
                'disconnect_failed': 'Ошибка отключения',
                'opened_in_browser': '{url} открыт в браузере',
                'copied_to_clipboard': '{url} скопирован в буфер обмена',
                'port_error': 'Пожалуйста, введите номер порта',
                'port_range_error': 'Порт должен быть между 1024 и 65535',
                'invalid_port': 'Недействительный номер порта',
                
                # Terminal tab
                'command': 'Команда:',
                'execute_command': 'Выполнить команду',
                'open_repo_terminal': 'Открыть интерактивный терминал репозитория',
                'open_machine_terminal': 'Открыть интерактивный терминал машины',
                'output': 'Вывод:',
                'command_executed': 'Команда выполнена',
                'executing_command': 'Выполнение команды...',
                'terminal_instructions': 'Чтобы открыть {description}, выполните эту команду в окне терминала:',
                'or_from_any_directory': 'Или из любого каталога:',
                'launched_terminal': 'Окно терминала запущено...',
                'launched_wt': 'Запущено в Windows Terminal...',
                'launched_wsl': 'Запущено в новом окне WSL...',
                'could_not_launch': 'Примечание: Не удалось автоматически запустить терминал в WSL.',
                'select_all_fields': 'Пожалуйста, выберите команду, машину, репозиторий и введите команду',
                'select_team_machine_repo': 'Пожалуйста, выберите команду, машину и репозиторий',
                'select_team_machine': 'Пожалуйста, выберите команду и машину',
                
                # File Sync tab
                'direction': 'Направление:',
                'upload': 'Загрузить',
                'download': 'Скачать',
                'local_path': 'Локальный путь:',
                'browse': 'Обзор...',
                'options': 'Параметры',
                'mirror_delete': 'Зеркало (удалить лишние файлы)',
                'verify_transfer': 'Проверить после передачи',
                'preview_changes': 'Предварительный просмотр изменений (--confirm)',
                'start_sync': 'Начать синхронизацию',
                'sync_completed': 'Синхронизация завершена',
                'starting_sync': 'Начало {direction}...',
                'fill_all_fields': 'Пожалуйста, заполните все поля',
                
                # Status messages
                'loading_teams': 'Загрузка команд...',
                'loading_machines': 'Загрузка машин для {team}...',
                'loading_repositories': 'Загрузка репозиториев для {team}...',
                'loading_plugins': 'Загрузка плагинов...',
                'refreshing_connections': 'Обновление подключений...',
                'authentication_expired': 'Аутентификация истекла. Пожалуйста, войдите снова.',
                'session_expired': 'Ваша сессия истекла. Пожалуйста, войдите снова.',
                
                # Error messages
                'failed_to_load_teams': 'Не удалось загрузить команды',
                'failed_to_load_machines': 'Не удалось загрузить машины',
                'failed_to_load_repositories': 'Не удалось загрузить репозитории',
                'select_connection': 'Пожалуйста, выберите подключение для {action}',
                'select_all_plugin_fields': 'Пожалуйста, выберите все поля',
                
                # Window titles
                'an_interactive_repo_terminal': 'интерактивный терминал репозитория',
                'an_interactive_machine_terminal': 'интерактивный терминал машины',
            },
            
            'tr': {
                # General
                'app_title': 'Rediacc CLI Araçları',
                'ready': 'Hazır',
                'error': 'Hata',
                'success': 'Başarılı',
                'confirm': 'Onayla',
                'cancel': 'İptal',
                'yes': 'Evet',
                'no': 'Hayır',
                'loading': 'Yükleniyor...',
                'logout': 'Çıkış',
                'language': 'Dil',
                
                # Login window
                'login_title': 'Rediacc CLI - Giriş',
                'login_header': 'Rediacc CLI Giriş',
                'email': 'E-posta:',
                'password': 'Şifre:',
                'login': 'Giriş Yap',
                'logging_in': 'Giriş yapılıyor...',
                'login_successful': 'Giriş başarılı!',
                'login_failed': 'Giriş başarısız',
                'please_enter_credentials': 'Lütfen e-posta ve şifre girin',
                
                # Main window
                'user': 'Kullanıcı:',
                'logout_confirm': 'Çıkış yapmak istediğinizden emin misiniz?',
                'resource_selection': 'Kaynak Seçimi',
                'team': 'Takım:',
                'machine': 'Makine:',
                'repository': 'Depo:',
                
                # Tabs
                'plugin_manager': 'Eklenti Yöneticisi',
                'terminal_access': 'Terminal Erişimi',
                'file_sync': 'Dosya Senkronizasyonu',
                
                # Plugin Manager tab
                'plugin_management': 'Eklenti Yönetimi',
                'available_plugins': 'Mevcut Eklentiler',
                'refresh_plugins': 'Eklentileri Yenile',
                'connect_to_plugin': 'Eklentiye Bağlan',
                'plugin': 'Eklenti:',
                'local_port': 'Yerel Port',
                'auto_port': 'Otomatik (7111-9111)',
                'manual_port': 'Manuel:',
                'connect': 'Bağlan',
                'active_connections': 'Aktif Bağlantılar',
                'open_in_browser': 'Tarayıcıda Aç',
                'copy_url': 'URL\'yi Kopyala',
                'disconnect': 'Bağlantıyı Kes',
                'refresh_status': 'Durumu Yenile',
                'plugin_tip': 'İpucu: URL\'yi açmak için çift tıklayın • URL\'yi kopyalamak için Ctrl+C',
                'found_plugins': '{count} eklenti bulundu',
                'found_connections': '{count} aktif bağlantı bulundu',
                'connecting_to': '{plugin} bağlanılıyor...',
                'disconnecting': '{plugin} bağlantısı kesiliyor...',
                'disconnect_confirm': '{plugin} bağlantısını kesmek istiyor musunuz?',
                'successfully_connected': '{plugin} başarıyla bağlandı',
                'access_at': 'Erişim adresi: {url}',
                'connection_failed': 'Bağlantı başarısız',
                'disconnected': '{plugin} bağlantısı kesildi',
                'disconnect_failed': 'Bağlantı kesme başarısız',
                'opened_in_browser': '{url} tarayıcıda açıldı',
                'copied_to_clipboard': '{url} panoya kopyalandı',
                'port_error': 'Lütfen bir port numarası girin',
                'port_range_error': 'Port 1024 ile 65535 arasında olmalıdır',
                'invalid_port': 'Geçersiz port numarası',
                
                # Terminal tab
                'command': 'Komut:',
                'execute_command': 'Komutu Çalıştır',
                'open_repo_terminal': 'Etkileşimli Depo Terminali Aç',
                'open_machine_terminal': 'Etkileşimli Makine Terminali Aç',
                'output': 'Çıktı:',
                'command_executed': 'Komut çalıştırıldı',
                'executing_command': 'Komut çalıştırılıyor...',
                'terminal_instructions': '{description} açmak için, terminal penceresinde bu komutu çalıştırın:',
                'or_from_any_directory': 'Veya herhangi bir dizinden:',
                'launched_terminal': 'Terminal penceresi başlatıldı...',
                'launched_wt': 'Windows Terminal\'de başlatıldı...',
                'launched_wsl': 'Yeni WSL penceresinde başlatıldı...',
                'could_not_launch': 'Not: WSL\'de terminal otomatik olarak başlatılamadı.',
                'select_all_fields': 'Lütfen takım, makine, depo seçin ve bir komut girin',
                'select_team_machine_repo': 'Lütfen takım, makine ve depo seçin',
                'select_team_machine': 'Lütfen takım ve makine seçin',
                
                # File Sync tab
                'direction': 'Yön:',
                'upload': 'Yükle',
                'download': 'İndir',
                'local_path': 'Yerel Yol:',
                'browse': 'Gözat...',
                'options': 'Seçenekler',
                'mirror_delete': 'Ayna (ekstra dosyaları sil)',
                'verify_transfer': 'Aktarımdan sonra doğrula',
                'preview_changes': 'Değişiklikleri önizle (--confirm)',
                'start_sync': 'Senkronizasyonu Başlat',
                'sync_completed': 'Senkronizasyon tamamlandı',
                'starting_sync': '{direction} başlatılıyor...',
                'fill_all_fields': 'Lütfen tüm alanları doldurun',
                
                # Status messages
                'loading_teams': 'Takımlar yükleniyor...',
                'loading_machines': '{team} için makineler yükleniyor...',
                'loading_repositories': '{team} için depolar yükleniyor...',
                'loading_plugins': 'Eklentiler yükleniyor...',
                'refreshing_connections': 'Bağlantılar yenileniyor...',
                'authentication_expired': 'Kimlik doğrulama süresi doldu. Lütfen tekrar giriş yapın.',
                'session_expired': 'Oturumunuzun süresi doldu. Lütfen tekrar giriş yapın.',
                
                # Error messages
                'failed_to_load_teams': 'Takımlar yüklenemedi',
                'failed_to_load_machines': 'Makineler yüklenemedi',
                'failed_to_load_repositories': 'Depolar yüklenemedi',
                'select_connection': '{action} için lütfen bir bağlantı seçin',
                'select_all_plugin_fields': 'Lütfen tüm alanları seçin',
                
                # Window titles
                'an_interactive_repo_terminal': 'etkileşimli depo terminali',
                'an_interactive_machine_terminal': 'etkileşimli makine terminali',
            },
            
            'zh': {
                # General
                'app_title': 'Rediacc CLI 工具',
                'ready': '就绪',
                'error': '错误',
                'success': '成功',
                'confirm': '确认',
                'cancel': '取消',
                'yes': '是',
                'no': '否',
                'loading': '加载中...',
                'logout': '登出',
                'language': '语言',
                
                # Login window
                'login_title': 'Rediacc CLI - 登录',
                'login_header': 'Rediacc CLI 登录',
                'email': '电子邮箱：',
                'password': '密码：',
                'login': '登录',
                'logging_in': '正在登录...',
                'login_successful': '登录成功！',
                'login_failed': '登录失败',
                'please_enter_credentials': '请输入电子邮箱和密码',
                
                # Main window
                'user': '用户：',
                'logout_confirm': '您确定要登出吗？',
                'resource_selection': '资源选择',
                'team': '团队：',
                'machine': '机器：',
                'repository': '仓库：',
                
                # Tabs
                'plugin_manager': '插件管理器',
                'terminal_access': '终端访问',
                'file_sync': '文件同步',
                
                # Plugin Manager tab
                'plugin_management': '插件管理',
                'available_plugins': '可用插件',
                'refresh_plugins': '刷新插件',
                'connect_to_plugin': '连接到插件',
                'plugin': '插件：',
                'local_port': '本地端口',
                'auto_port': '自动 (7111-9111)',
                'manual_port': '手动：',
                'connect': '连接',
                'active_connections': '活动连接',
                'open_in_browser': '在浏览器中打开',
                'copy_url': '复制URL',
                'disconnect': '断开连接',
                'refresh_status': '刷新状态',
                'plugin_tip': '提示：双击打开URL • Ctrl+C复制URL',
                'found_plugins': '找到 {count} 个插件',
                'found_connections': '找到 {count} 个活动连接',
                'connecting_to': '正在连接到 {plugin}...',
                'disconnecting': '正在断开 {plugin}...',
                'disconnect_confirm': '断开 {plugin} 连接？',
                'successfully_connected': '成功连接到 {plugin}',
                'access_at': '访问地址：{url}',
                'connection_failed': '连接失败',
                'disconnected': '{plugin} 已断开连接',
                'disconnect_failed': '断开连接失败',
                'opened_in_browser': '{url} 已在浏览器中打开',
                'copied_to_clipboard': '{url} 已复制到剪贴板',
                'port_error': '请输入端口号',
                'port_range_error': '端口必须在1024到65535之间',
                'invalid_port': '无效的端口号',
                
                # Terminal tab
                'command': '命令：',
                'execute_command': '执行命令',
                'open_repo_terminal': '打开交互式仓库终端',
                'open_machine_terminal': '打开交互式机器终端',
                'output': '输出：',
                'command_executed': '命令已执行',
                'executing_command': '正在执行命令...',
                'terminal_instructions': '要打开{description}，请在终端窗口中运行此命令：',
                'or_from_any_directory': '或从任何目录：',
                'launched_terminal': '终端窗口已启动...',
                'launched_wt': '已在Windows Terminal中启动...',
                'launched_wsl': '已在新的WSL窗口中启动...',
                'could_not_launch': '注意：无法在WSL中自动启动终端。',
                'select_all_fields': '请选择团队、机器、仓库并输入命令',
                'select_team_machine_repo': '请选择团队、机器和仓库',
                'select_team_machine': '请选择团队和机器',
                
                # File Sync tab
                'direction': '方向：',
                'upload': '上传',
                'download': '下载',
                'local_path': '本地路径：',
                'browse': '浏览...',
                'options': '选项',
                'mirror_delete': '镜像（删除额外文件）',
                'verify_transfer': '传输后验证',
                'preview_changes': '预览更改 (--confirm)',
                'start_sync': '开始同步',
                'sync_completed': '同步完成',
                'starting_sync': '正在开始{direction}...',
                'fill_all_fields': '请填写所有字段',
                
                # Status messages
                'loading_teams': '正在加载团队...',
                'loading_machines': '正在加载 {team} 的机器...',
                'loading_repositories': '正在加载 {team} 的仓库...',
                'loading_plugins': '正在加载插件...',
                'refreshing_connections': '正在刷新连接...',
                'authentication_expired': '身份验证已过期。请重新登录。',
                'session_expired': '您的会话已过期。请重新登录。',
                
                # Error messages
                'failed_to_load_teams': '加载团队失败',
                'failed_to_load_machines': '加载机器失败',
                'failed_to_load_repositories': '加载仓库失败',
                'select_connection': '请选择一个连接来{action}',
                'select_all_plugin_fields': '请选择所有字段',
                
                # Window titles
                'an_interactive_repo_terminal': '交互式仓库终端',
                'an_interactive_machine_terminal': '交互式机器终端',
            }
        }
    
    def get_language_config_path(self) -> Path:
        """Get the path to the language configuration file"""
        config_dir = Path.home() / '.rediacc'
        config_dir.mkdir(exist_ok=True)
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
    
    def get(self, key: str, **kwargs) -> str:
        """Get a translated string for the current language"""
        translation = self.translations.get(self.current_language, {}).get(key)
        if not translation:
            # Fallback to English
            translation = self.translations.get('en', {}).get(key, key)
        
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