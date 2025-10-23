#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI User Module - User account management operations
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from cli.core.shared import colorize
from cli.core.api_client import client
from cli.core.config import TokenManager, setup_logging, get_logger
from cli.core.telemetry import track_command
from cli.config import CLI_CONFIG_FILE


STATIC_SALT = 'Rd!@cc111$ecur3P@$$w0rd$@lt#H@$h'
TEST_ACTIVATION_CODE = os.getenv('REDIACC_TEST_ACTIVATION_CODE', '111111')


def pwd_hash(pwd):
    """Hash password with static salt"""
    salted_password = pwd + STATIC_SALT
    return "0x" + hashlib.sha256(salted_password.encode()).digest().hex()


def format_output(data, format_type, message=None, error=None):
    """Format output based on format type"""
    if format_type in ['json', 'json-full']:
        output = {'success': error is None, 'data': data}
        if message: output['message'] = message
        if error: output['error'] = error
        return json.dumps(output, indent=2)
    return colorize(f"Error: {error}", 'RED') if error else data if data else colorize(message, 'GREEN') if message else "No data available"


# Load CLI configuration
CLI_CONFIG_PATH = CLI_CONFIG_FILE
try:
    with open(CLI_CONFIG_PATH, 'r', encoding='utf-8') as f:
        cli_config = json.load(f)
        API_ENDPOINTS = cli_config.get('API_ENDPOINTS', {})
except Exception as e:
    print(colorize(f"Error loading CLI configuration from {CLI_CONFIG_PATH}: {e}", 'RED'))
    sys.exit(1)


class UserHandler:
    """Handler for user management commands"""

    def __init__(self, client_instance, output_format='text'):
        self.client = client_instance
        self.output_format = output_format

    def activate_command(self, args):
        """Activate a user account"""
        # Prompt for password if not provided
        if not hasattr(args, 'password') or not args.password:
            args.password = getpass.getpass("Password for user account: ")

        # Use provided code or default test code
        activation_code = args.code if hasattr(args, 'code') and args.code else TEST_ACTIVATION_CODE

        params = {
            'activationCode': activation_code
        }

        # Note: Uses credentials-based auth (no token required)
        response = self.client.auth_request(
            "ActivateUserAccount",
            args.email,
            pwd_hash(args.password),
            params
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        success_msg = f"Successfully activated user: {args.email}"
        if self.output_format == 'json':
            result = {'email': args.email, 'activated': True}
            print(format_output(result, self.output_format, success_msg))
        else:
            print(colorize(success_msg, 'GREEN'))
        return 0

    def deactivate_command(self, args):
        """Deactivate a user account"""
        # Confirmation check
        if not args.force:
            confirm = input(f"Are you sure you want to deactivate user '{args.email}'? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("Deactivation cancelled.")
                return 0

        params = {'userEmail': args.email}

        response = self.client.token_request("UpdateUserToDeactivated", params)

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        success_msg = f"Successfully deactivated user: {args.email}"
        if self.output_format == 'json':
            result = {'email': args.email, 'deactivated': True}
            print(format_output(result, self.output_format, success_msg))
        else:
            print(colorize(success_msg, 'GREEN'))
        return 0

    def update_email_command(self, args):
        """Update a user's email address"""
        params = {
            'currentUserEmail': args.current_email,
            'newUserEmail': args.new_email
        }

        response = self.client.token_request("UpdateUserEmail", params)

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        success_msg = f"Successfully updated user email: {args.current_email} → {args.new_email}"
        if self.output_format == 'json':
            result = {
                'old_email': args.current_email,
                'new_email': args.new_email,
                'updated': True
            }
            print(format_output(result, self.output_format, success_msg))
        else:
            print(colorize(success_msg, 'GREEN'))
        return 0

    def update_password_command(self, args):
        """Update a user's password"""
        # Prompt for new password if not provided
        if not hasattr(args, 'new_password') or not args.new_password:
            args.new_password = getpass.getpass("New password: ")
            confirm_password = getpass.getpass("Confirm new password: ")
            if args.new_password != confirm_password:
                print(format_output(None, self.output_format, None, "Passwords do not match"))
                return 1

        params = {'newUserHash': pwd_hash(args.new_password)}

        response = self.client.token_request("UpdateUserPassword", params)

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        success_msg = "Successfully updated password"
        if self.output_format == 'json':
            result = {'updated': True}
            print(format_output(result, self.output_format, success_msg))
        else:
            print(colorize(success_msg, 'GREEN'))
        return 0

    def update_tfa_command(self, args):
        """Enable or disable two-factor authentication"""
        # Prompt for password if not provided
        if not hasattr(args, 'password') or not args.password:
            args.password = getpass.getpass("Current password: ")

        # Convert enable argument to boolean
        if isinstance(args.enable, str):
            enable_bool = args.enable.lower() in ['1', 'true', 'yes']
        else:
            enable_bool = bool(args.enable)

        params = {
            'userHash': pwd_hash(args.password),
            'enable': enable_bool
        }

        # Add current code if disabling TFA
        if not enable_bool and hasattr(args, 'current_code') and args.current_code:
            params['currentCode'] = args.current_code

        response = self.client.token_request("UpdateUserTFA", params)

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        action = "enabled" if enable_bool else "disabled"
        success_msg = f"Successfully {action} two-factor authentication"
        if self.output_format == 'json':
            result = {'tfa_enabled': enable_bool, 'updated': True}
            print(format_output(result, self.output_format, success_msg))
        else:
            print(colorize(success_msg, 'GREEN'))
        return 0


def add_common_arguments(parser):
    """Add common arguments to parser"""
    parser.add_argument('--output', choices=['text', 'json', 'json-full'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')


@track_command('user')
def main():
    """Main entry point for user commands"""
    parser = argparse.ArgumentParser(
        description='Rediacc User Management - Manage user accounts',
        prog='rediacc user'
    )

    add_common_arguments(parser)

    subparsers = parser.add_subparsers(dest='subcommand', help='User subcommands')
    subparsers.required = True

    # Activate subcommand
    activate_parser = subparsers.add_parser('activate', help='Activate a user account')
    activate_parser.add_argument('email', help='User email address')
    activate_parser.add_argument('--code', help='Activation code (default: 111111)')
    activate_parser.add_argument('--password', help='User password')

    # Deactivate subcommand
    deactivate_parser = subparsers.add_parser('deactivate', help='Deactivate a user account')
    deactivate_parser.add_argument('email', help='User email address')
    deactivate_parser.add_argument('--force', action='store_true', help='Skip confirmation')

    # Update email subcommand
    update_email_parser = subparsers.add_parser('update-email', help="Change a user's email address")
    update_email_parser.add_argument('current_email', help='Current user email')
    update_email_parser.add_argument('new_email', help='New user email')

    # Update password subcommand
    update_password_parser = subparsers.add_parser('update-password', help="Update user's password")
    update_password_parser.add_argument('--new-password', help='New password (will prompt if not provided)')

    # Update TFA subcommand
    update_tfa_parser = subparsers.add_parser('update-tfa', help='Enable or disable two-factor authentication')
    update_tfa_parser.add_argument('enable', help='Enable (1/true/yes) or disable (0/false/no) TFA')
    update_tfa_parser.add_argument('--password', help='Current password for verification')
    update_tfa_parser.add_argument('--current-code', help='Current TFA code (required when disabling)')

    args = parser.parse_args()

    # Initialize logging
    if args.verbose:
        os.environ['REDIACC_VERBOSE'] = '1'
    setup_logging(verbose=args.verbose)

    # Initialize token manager
    token_mgr = TokenManager()
    token_mgr.load_vault_info_from_config()

    # Client is a singleton - just use it directly
    client_instance = client

    # Create handler
    handler = UserHandler(client_instance, args.output)

    # Route to appropriate command
    if args.subcommand == 'activate':
        return handler.activate_command(args)
    elif args.subcommand == 'deactivate':
        return handler.deactivate_command(args)
    elif args.subcommand == 'update-email':
        return handler.update_email_command(args)
    elif args.subcommand == 'update-password':
        return handler.update_password_command(args)
    elif args.subcommand == 'update-tfa':
        return handler.update_tfa_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
