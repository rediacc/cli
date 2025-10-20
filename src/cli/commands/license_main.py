#!/usr/bin/env python3
"""
Rediacc CLI License - License management for offline and online scenarios
"""

import argparse
import json
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli._version import __version__
from cli.core.shared import colorize
from cli.core.api_client import client
from cli.core.telemetry import track_command, initialize_telemetry, shutdown_telemetry

def generate_hardware_id():
    """Generate hardware ID using SuperClient"""
    return client.get_hardware_id()

def request_license_from_server(hardware_id, base_url=None):
    """Request license from server using SuperClient"""
    return client.request_license(hardware_id, base_url)

def install_license_file(license_file, target_path=None):
    """Install license file to target directory"""
    if not os.path.exists(license_file):
        raise FileNotFoundError(f"License file not found: {license_file}")

    if not target_path:
        possible_paths = [
            ".", "./bin", "../middleware",
            "../middleware/bin/Debug/net8.0",
            "../middleware/bin/Release/net8.0",
        ]

        target_path = next(
            (path for path in possible_paths if os.path.exists(path) and os.path.isdir(path)),
            "."
        )

    os.makedirs(target_path, exist_ok=True)

    target_file = os.path.join(target_path, "license.lic")
    shutil.copy2(license_file, target_file)

    return target_file

def handle_generate_id(args):
    """Generate hardware ID for offline licensing"""
    output_format = getattr(args, 'output_format', 'text')

    try:
        if output_format != 'json':
            print(colorize("Generating hardware ID...", 'BLUE'))

        hardware_id = generate_hardware_id()
        output_file = args.output or 'hardware-id.txt'

        # Write to file
        with open(output_file, 'w') as f:
            f.write(hardware_id)

        if output_format == 'json':
            result = {
                "success": True,
                "hardware_id": hardware_id,
                "output_file": output_file
            }
            print(json.dumps(result))
        else:
            print(colorize("Hardware ID generated successfully!", 'GREEN'))
            print(colorize(f"Hardware ID: {hardware_id}", 'GREEN'))
            print(colorize(f"Saved to: {output_file}", 'GREEN'))
            print()
            print(colorize("Next steps:", 'BLUE'))
            print("1. Transfer this file to a machine with internet access")
            print(f"2. Run: rediacc license request --hardware-id {output_file}")
            print("3. Transfer the resulting license.lic back to this machine")
            print("4. Run: rediacc license install --file license.lic")
        return 0
    except Exception as e:
        error_msg = str(e)
        if output_format == 'json':
            print(json.dumps({"success": False, "error": error_msg}))
        else:
            print(colorize("Failed to generate hardware ID", 'RED'))
            print(colorize(error_msg, 'RED'))
        return 1

def handle_request(args):
    """Request license using hardware ID"""
    output_format = getattr(args, 'output_format', 'text')

    try:
        # Read hardware ID from file or use directly
        if os.path.isfile(args.hardware_id):
            with open(args.hardware_id, 'r', encoding='utf-8') as f:
                hardware_id = f.read().strip()
        else:
            hardware_id = args.hardware_id

        if output_format != 'json':
            print(colorize("Requesting license from server...", 'BLUE'))

        license_data = request_license_from_server(hardware_id, args.server_url)

        output_file = args.output or 'license.lic'
        with open(output_file, 'w') as f:
            lic_data = license_data.get('licenseData') or license_data.get('LicenseData')
            if not lic_data:
                raise Exception("License data not found in response")
            f.write(lic_data)

        if output_format == 'json':
            result = {
                "success": True,
                "license_key": license_data.get('licenseKey') or license_data.get('LicenseKey'),
                "expiration_date": license_data.get('expirationDate') or license_data.get('ExpirationDate'),
                "is_new_license": license_data.get('isNewLicense', license_data.get('IsNewLicense', False)),
                "output_file": output_file
            }
            print(json.dumps(result))
        else:
            print(colorize("License obtained successfully!", 'GREEN'))
            lic_key = license_data.get('licenseKey') or license_data.get('LicenseKey')
            exp_date = license_data.get('expirationDate') or license_data.get('ExpirationDate')
            is_new = license_data.get('isNewLicense', license_data.get('IsNewLicense', False))
            print(colorize(f"License Key: {lic_key}", 'GREEN'))
            print(colorize(f"Expires: {exp_date}", 'GREEN'))
            if is_new:
                print(colorize("This is a new license", 'BLUE'))
            print(colorize(f"Saved to: {output_file}", 'GREEN'))
        return 0
    except Exception as e:
        error = f"Failed to request license: {str(e)}"
        if output_format == 'json':
            print(json.dumps({"success": False, "error": error}))
        else:
            print(colorize(error, 'RED'))
        return 1

def handle_install(args):
    """Install license file"""
    output_format = getattr(args, 'output_format', 'text')

    try:
        target_file = install_license_file(args.file, args.target)

        if output_format == 'json':
            result = {
                "success": True,
                "installed_to": target_file
            }
            print(json.dumps(result))
        else:
            print(colorize(f"License installed successfully to: {target_file}", 'GREEN'))
        return 0
    except Exception as e:
        error = f"Failed to install license: {str(e)}"
        if output_format == 'json':
            print(json.dumps({"success": False, "error": error}))
        else:
            print(colorize(error, 'RED'))
        return 1

@track_command('license')
def main():
    # Initialize telemetry
    initialize_telemetry()

    parser = argparse.ArgumentParser(
        prog='rediacc license',
        description='Rediacc CLI License - License management for offline and online scenarios',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate hardware ID for offline licensing:
    %(prog)s generate-id
    %(prog)s generate-id --output my-hardware-id.txt

  Request license from server:
    %(prog)s request --hardware-id hardware-id.txt
    %(prog)s request --hardware-id ABC123 --output my-license.lic
    %(prog)s request -i hardware-id.txt -s https://license.example.com

  Install license file:
    %(prog)s install --file license.lic
    %(prog)s install -f license.lic --target /opt/rediacc/middleware

Offline Licensing Workflow:
  1. On offline machine: rediacc license generate-id
  2. Transfer hardware-id.txt to online machine
  3. On online machine: rediacc license request -i hardware-id.txt
  4. Transfer license.lic back to offline machine
  5. On offline machine: rediacc license install -f license.lic

Online Licensing:
  If the machine has internet access, you can combine steps 1-2:
    rediacc license request -i $(rediacc license generate-id --output /dev/stdout)
"""
    )

    # Add output format argument (optional, for consistency with other commands)
    parser.add_argument('--output-format', choices=['text', 'json'], default='text',
                       help='Output format (default: text)')

    subparsers = parser.add_subparsers(dest='command', help='License commands')

    # Generate-ID subcommand
    generate_parser = subparsers.add_parser('generate-id',
                                           help='Generate hardware ID for offline licensing')
    generate_parser.add_argument('-o', '--output',
                                help='Output file (default: hardware-id.txt)')
    generate_parser.set_defaults(func=handle_generate_id)

    # Request subcommand
    request_parser = subparsers.add_parser('request',
                                          help='Request license using hardware ID')
    request_parser.add_argument('-i', '--hardware-id', required=True,
                               help='Hardware ID or file containing it')
    request_parser.add_argument('-o', '--output',
                               help='Output file (default: license.lic)')
    request_parser.add_argument('-s', '--server-url',
                               help='License server URL (optional)')
    request_parser.set_defaults(func=handle_request)

    # Install subcommand
    install_parser = subparsers.add_parser('install',
                                          help='Install license file')
    install_parser.add_argument('-f', '--file', required=True,
                               help='License file to install')
    install_parser.add_argument('-t', '--target',
                               help='Target directory (default: auto-detect)')
    install_parser.set_defaults(func=handle_install)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        result = args.func(args)
        sys.exit(result if result is not None else 0)
    except Exception as e:
        print(colorize(f"Error: {e}", 'RED'))
        sys.exit(1)
    finally:
        # Shutdown telemetry
        shutdown_telemetry()

if __name__ == '__main__':
    main()
