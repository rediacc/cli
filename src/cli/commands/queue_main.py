#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rediacc CLI Queue Module - Queue management and bash function operations
"""

import argparse
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


def format_output(data, format_type, message=None, error=None):
    """Format output based on format type"""
    if format_type in ['json', 'json-full']:
        output = {'success': error is None, 'data': data}
        if message: output['message'] = message
        if error: output['error'] = error
        return json.dumps(output, indent=2)
    return colorize(f"Error: {error}", 'RED') if error else data if data else colorize(message, 'GREEN') if message else "No data available"


def format_table(headers, rows):
    """Format data as a table"""
    if not rows:
        return "No data"

    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    header_row = ' | '.join(str(h).ljust(w) for h, w in zip(headers, col_widths))
    separator = '-+-'.join('-' * w for w in col_widths)
    data_rows = [' | '.join(str(cell).ljust(w) for cell, w in zip(row, col_widths)) for row in rows]

    return '\n'.join([header_row, separator] + data_rows)


# Load CLI configuration
CLI_CONFIG_PATH = CLI_CONFIG_FILE
try:
    with open(CLI_CONFIG_PATH, 'r', encoding='utf-8') as f:
        cli_config = json.load(f)
        QUEUE_FUNCTIONS = cli_config.get('QUEUE_FUNCTIONS', {})
        API_ENDPOINTS = cli_config.get('API_ENDPOINTS', {})
        CLI_COMMANDS = cli_config.get('CLI_COMMANDS', {})
except Exception as e:
    print(colorize(f"Error loading CLI configuration from {CLI_CONFIG_PATH}: {e}", 'RED'))
    sys.exit(1)


def build_queue_vault_data(function_name, args):
    """Build vault data for queue item from function definition and arguments"""
    func_def = QUEUE_FUNCTIONS.get(function_name)
    if not func_def:
        return None

    params = {}
    for param_name, param_info in func_def.get('params', {}).items():
        value = getattr(args, param_name, param_info.get('default'))
        if value is not None or param_info.get('required', False):
            params[param_name] = value

    vault_data = {
        'type': 'bash_function',
        'function': function_name,
        'params': params,
        'description': args.description or func_def.get('description', ''),
        'priority': args.priority,
        'bridge': args.bridge
    }

    return json.dumps(vault_data)


def format_queue_trace(response, output_format):
    """Format queue trace response with multiple result sets"""
    if not response or 'resultSets' not in response:
        return format_output("No trace data available", output_format)

    resultSets = response.get('resultSets', [])
    if len(resultSets) < 2:
        return format_output("No trace data found", output_format)

    if output_format == 'json':
        # For JSON output, organize data into meaningful sections
        result = {
            'queue_item': {},
            'request_vault': {},
            'response_vault': {},
            'timeline': []
        }

        # Table 1 (index 1): Queue Item Details
        if len(resultSets) > 1 and resultSets[1].get('data'):
            item_data = resultSets[1]['data'][0] if resultSets[1]['data'] else {}
            result['queue_item'] = item_data

        # Table 2 (index 2): Request Vault
        if len(resultSets) > 2 and resultSets[2].get('data'):
            vault_data = resultSets[2]['data'][0] if resultSets[2]['data'] else {}
            result['request_vault'] = {
                'type': vault_data.get('VaultType', 'Request'),
                'version': vault_data.get('VaultVersion'),
                'content': vault_data.get('VaultContent'),
                'has_content': vault_data.get('HasContent', False)
            }

        # Table 3 (index 3): Response Vault
        if len(resultSets) > 3 and resultSets[3].get('data'):
            vault_data = resultSets[3]['data'][0] if resultSets[3]['data'] else {}
            result['response_vault'] = {
                'type': vault_data.get('VaultType', 'Response'),
                'version': vault_data.get('VaultVersion'),
                'content': vault_data.get('VaultContent'),
                'has_content': vault_data.get('HasContent', False)
            }

        # Table 4 (index 4): Timeline
        if len(resultSets) > 4 and resultSets[4].get('data'):
            result['timeline'] = resultSets[4]['data']

        return format_output(result, output_format)
    else:
        output_parts = []

        if len(resultSets) > 1 and resultSets[1].get('data') and resultSets[1]['data']:
            item_data = resultSets[1]['data'][0]
            output_parts.append(colorize("QUEUE ITEM DETAILS", 'HEADER'))
            output_parts.append("=" * 80)

            details = [
                ('Task ID', item_data.get('TaskId')),
                ('Status', item_data.get('Status')),
                ('Health Status', item_data.get('HealthStatus')),
                ('Created Time', item_data.get('CreatedTime')),
                ('Assigned Time', item_data.get('AssignedTime')),
                ('Last Heartbeat', item_data.get('LastHeartbeat')),
            ]

            if item_data.get('Priority') is not None:
                details.append(('Priority', f"{item_data.get('Priority')} ({item_data.get('PriorityLabel')})"))

            details.extend([
                ('Seconds to Assignment', item_data.get('SecondsToAssignment')),
                ('Processing Duration (seconds)', item_data.get('ProcessingDurationSeconds')),
                ('Total Duration (seconds)', item_data.get('TotalDurationSeconds')),
            ])

            details.extend([
                ('Company', f"{item_data.get('CompanyName')} (ID: {item_data.get('CompanyId')})"),
                ('Team', f"{item_data.get('TeamName')} (ID: {item_data.get('TeamId')})"),
                ('Region', f"{item_data.get('RegionName')} (ID: {item_data.get('RegionId')})"),
                ('Bridge', f"{item_data.get('BridgeName')} (ID: {item_data.get('BridgeId')})"),
                ('Machine', f"{item_data.get('MachineName')} (ID: {item_data.get('MachineId')})"),
            ])

            if item_data.get('IsStale'):
                details.append(('Warning', colorize('This queue item is STALE', 'YELLOW')))

            max_label_width = max(len(label) for label, _ in details)
            output_parts.extend(f"{label.ljust(max_label_width)} : {value}" for label, value in details if value is not None)

        if len(resultSets) > 2 and resultSets[2].get('data') and resultSets[2]['data']:
            vault_data = resultSets[2]['data'][0]
            if vault_data.get('HasContent'):
                output_parts.append("")
                output_parts.append(colorize("REQUEST VAULT", 'HEADER'))
                output_parts.append("=" * 80)
                output_parts.append(f"Version: {vault_data.get('VaultVersion', 'N/A')}")
                output_parts.append(f"Content:\n{vault_data.get('VaultContent', 'No content')}")

        if len(resultSets) > 3 and resultSets[3].get('data') and resultSets[3]['data']:
            vault_data = resultSets[3]['data'][0]
            if vault_data.get('HasContent'):
                output_parts.append("")
                output_parts.append(colorize("RESPONSE VAULT", 'HEADER'))
                output_parts.append("=" * 80)
                output_parts.append(f"Version: {vault_data.get('VaultVersion', 'N/A')}")
                output_parts.append(f"Content:\n{vault_data.get('VaultContent', 'No content')}")

        if len(resultSets) > 4 and resultSets[4].get('data'):
            timeline_data = resultSets[4]['data']
            if timeline_data:
                output_parts.append("")
                output_parts.append(colorize("TIMELINE", 'HEADER'))
                output_parts.append("=" * 80)

                headers = ['Event', 'Time', 'Details']
                rows = []
                for event in timeline_data:
                    rows.append([
                        event.get('EventName', 'N/A'),
                        event.get('EventTime', 'N/A'),
                        event.get('Details', '')
                    ])
                output_parts.append(format_table(headers, rows))

        return '\n'.join(output_parts) if output_parts else "No trace data available"


def extract_table_data(response, table_index=1):
    """Extract data from a specific table in the response"""
    if not response or 'resultSets' not in response:
        return []
    resultSets = response.get('resultSets', [])
    if len(resultSets) <= table_index:
        return []
    return resultSets[table_index].get('data', [])


class QueueHandler:
    """Handler for queue commands"""

    def __init__(self, client_instance, output_format='text'):
        self.client = client_instance
        self.output_format = output_format

    def _collect_function_params(self, args, func_def):
        """Collect and validate function parameters from args or prompt user"""
        for param_name, param_info in func_def.get('params', {}).items():
            if not hasattr(args, param_name):
                setattr(args, param_name, None)

            if param_info.get('required', False) and getattr(args, param_name) is None:
                if self.output_format in ['json', 'json-full']:
                    print(format_output(None, self.output_format, None, f"Missing required parameter: {param_name}"))
                    return False

                value = input(f"{param_info.get('help', param_name)}: ")
                setattr(args, param_name, value)
        return True

    def add_command(self, args):
        """Add a new queue item with a bash function"""
        func_def = QUEUE_FUNCTIONS.get(args.function)
        if not func_def:
            print(format_output(None, self.output_format, None, f"Unknown function: {args.function}"))
            return 1

        if not self._collect_function_params(args, func_def):
            return 1

        vault_data = build_queue_vault_data(args.function, args)
        if not vault_data:
            print(format_output(None, self.output_format, None, "Failed to build queue item data"))
            return 1

        response = self.client.token_request(
            "CreateQueueItem",
            {
                'teamName': args.team,
                'machineName': args.machine,
                'bridgeName': args.bridge,
                'queueVault': vault_data
            }
        )

        if response.get('error'):
            output = format_output(None, self.output_format, None, response['error'])
            print(output)
            return 1

        resultSets = response.get('resultSets', [])
        task_id = None
        if len(resultSets) > 1 and resultSets[1].get('data'):
            task_id = resultSets[1]['data'][0].get('taskId', resultSets[1]['data'][0].get('TaskId'))

        if self.output_format in ['json', 'json-full']:
            result = {
                'task_id': task_id,
                'function': args.function,
                'team': args.team,
                'machine': args.machine,
                'bridge': args.bridge
            }
            output = format_output(result, self.output_format, f"Successfully queued {args.function}")
            print(output)
        else:
            print(colorize(f"Successfully queued {args.function} for machine {args.machine}", 'GREEN'))
            if task_id:
                print(f"Task ID: {task_id}")

        return 0

    def list_functions_command(self, args):
        """List available queue functions"""
        if self.output_format in ['json', 'json-full']:
            result = {
                func_name: {
                    'description': func_def.get('description', ''),
                    'params': {
                        param_name: {
                            'type': param_info.get('type', 'string'),
                            'required': param_info.get('required', False),
                            'default': param_info.get('default', None),
                            'help': param_info.get('help', '')
                        }
                        for param_name, param_info in func_def.get('params', {}).items()
                    }
                }
                for func_name, func_def in QUEUE_FUNCTIONS.items()
            }
            print(format_output(result, self.output_format))
        else:
            print(colorize("Available Queue Functions", 'HEADER'))
            print("=" * 80)

            for func_name, func_def in sorted(QUEUE_FUNCTIONS.items()):
                print(f"\n{colorize(func_name, 'BLUE')}")
                print(f"  {func_def.get('description', 'No description available')}")

                params = func_def.get('params', {})
                if not params:
                    print("  No parameters required")
                    continue

                print("  Parameters:")
                for param_name, param_info in params.items():
                    required = "[required]" if param_info.get('required', False) else "[optional]"
                    default = f" (default: {param_info.get('default')})" if 'default' in param_info else ""
                    print(f"    - {param_name} {colorize(required, 'YELLOW')}{default}")
                    help_text = param_info.get('help', '')
                    if help_text:
                        print(f"      {help_text}")

        return 0

    def get_next_command(self, args):
        """Get next queue items for processing"""
        response = self.client.token_request(
            "GetQueueItemsNext",
            {'itemCount': args.count or 3}
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        data = extract_table_data(response, 1)
        print(format_output(data, self.output_format, "Successfully retrieved queue items"))
        return 0

    def list_command(self, args):
        """List queue items with filters"""
        params = {
            'teamName': args.team,
            'machineName': args.machine,
            'bridgeName': args.bridge,
            'status': args.status,
            'priority': args.priority,
            'minPriority': args.min_priority,
            'maxPriority': args.max_priority,
            'dateFrom': args.date_from,
            'dateTo': args.date_to,
            'taskId': args.task_id,
            'includeCompleted': args.include_completed,
            'includeCancelled': args.include_cancelled,
            'onlyStale': args.only_stale,
            'staleThresholdMinutes': args.stale_threshold,
            'maxRecords': args.max_records,
            'createdByUserEmail': getattr(args, 'created_by_user_email', None)
        }

        response = self.client.token_request("GetTeamQueueItems", params)

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        data = extract_table_data(response, 1)
        print(format_output(data, self.output_format, "Successfully retrieved queue items"))
        return 0

    def update_response_command(self, args):
        """Update queue item response vault"""
        vault_content = args.vault
        if args.vault_file:
            try:
                with open(args.vault_file, 'r') as f:
                    vault_content = f.read()
            except Exception as e:
                print(format_output(None, self.output_format, None, f"Failed to read vault file: {e}"))
                return 1

        response = self.client.token_request(
            "UpdateQueueItemResponse",
            {
                'taskId': args.task_id,
                'responseVault': vault_content
            }
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        print(format_output(None, self.output_format, "Successfully updated queue item response"))
        return 0

    def complete_command(self, args):
        """Mark queue item as complete"""
        vault_content = args.vault if hasattr(args, 'vault') else None
        if hasattr(args, 'vault_file') and args.vault_file:
            try:
                with open(args.vault_file, 'r') as f:
                    vault_content = f.read()
            except Exception as e:
                print(format_output(None, self.output_format, None, f"Failed to read vault file: {e}"))
                return 1

        response = self.client.token_request(
            "CompleteQueueItem",
            {
                'taskId': args.task_id,
                'responseVault': vault_content
            }
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        print(format_output(None, self.output_format, f"Successfully completed queue item {args.task_id}"))
        return 0

    def trace_command(self, args):
        """Trace queue item execution"""
        response = self.client.token_request(
            "TraceQueueItem",
            {'taskId': args.task_id}
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        result = format_queue_trace(response, self.output_format)
        print(result)
        return 0

    def cancel_command(self, args):
        """Cancel a queue item"""
        response = self.client.token_request(
            "CancelQueueItem",
            {'taskId': args.task_id}
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        print(format_output(None, self.output_format, f"Successfully cancelled queue item {args.task_id}"))
        return 0

    def retry_command(self, args):
        """Retry a queue item"""
        response = self.client.token_request(
            "RetryQueueItem",
            {'taskId': args.task_id}
        )

        if response.get('error'):
            print(format_output(None, self.output_format, None, response['error']))
            return 1

        print(format_output(None, self.output_format, f"Successfully retried queue item {args.task_id}"))
        return 0


def add_common_arguments(parser):
    """Add common arguments to parser"""
    parser.add_argument('--output', choices=['text', 'json', 'json-full'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')


@track_command('queue')
def main():
    """Main entry point for queue commands"""
    parser = argparse.ArgumentParser(
        description='Rediacc Queue Management - Manage queue items and bash function operations',
        prog='rediacc queue'
    )

    add_common_arguments(parser)

    subparsers = parser.add_subparsers(dest='subcommand', help='Queue subcommands')
    subparsers.required = True

    # Add subcommand
    add_parser = subparsers.add_parser('add', help='Add a new queue item with a bash function')
    add_parser.add_argument('function', help='Function name to queue')
    add_parser.add_argument('--team', required=True, help='Team name')
    add_parser.add_argument('--machine', required=True, help='Machine name')
    add_parser.add_argument('--bridge', help='Bridge name (optional)')
    add_parser.add_argument('--priority', type=int, default=3, help='Priority (1-5, default: 3)')
    add_parser.add_argument('--description', help='Custom description for the queue item')

    # Add dynamic parameters for all queue functions
    all_params = {}
    for func_def in QUEUE_FUNCTIONS.values():
        for param_name, param_info in func_def.get('params', {}).items():
            if param_name not in all_params or len(param_info.get('help', '')) > len(all_params[param_name]):
                all_params[param_name] = param_info.get('help', f'Parameter for function')

    for param_name, help_text in all_params.items():
        # Escape % for argparse (% is used for formatting in argparse help)
        escaped_help = help_text.replace('%', '%%')
        add_parser.add_argument(f'--{param_name}', help=escaped_help)

    # List functions subcommand
    list_funcs_parser = subparsers.add_parser('list-functions', help='List available queue functions')

    # Get next subcommand
    get_next_parser = subparsers.add_parser('get-next', help='Get next queue items for processing')
    get_next_parser.add_argument('--count', type=int, default=3, help='Number of items to retrieve (default: 3)')

    # List subcommand
    list_parser = subparsers.add_parser('list', help='List queue items with filters')
    list_parser.add_argument('--team', help='Filter by team name(s), comma-separated')
    list_parser.add_argument('--machine', help='Filter by specific machine name')
    list_parser.add_argument('--bridge', help='Filter by specific bridge name')
    list_parser.add_argument('--status', help='Filter by status(es), comma-separated (e.g., PENDING,PROCESSING)')
    list_parser.add_argument('--priority', type=int, help='Filter by specific priority (1-5)')
    list_parser.add_argument('--min-priority', type=int, help='Filter by minimum priority (1-5)')
    list_parser.add_argument('--max-priority', type=int, help='Filter by maximum priority (1-5)')
    list_parser.add_argument('--date-from', help='Filter by date range start (ISO format)')
    list_parser.add_argument('--date-to', help='Filter by date range end (ISO format)')
    list_parser.add_argument('--task-id', help='Search for specific task ID')
    list_parser.add_argument('--no-completed', dest='include_completed', action='store_false',
                           help='Exclude completed items (default: include)')
    list_parser.add_argument('--no-cancelled', dest='include_cancelled', action='store_false',
                           help='Exclude cancelled items (default: include)')
    list_parser.add_argument('--only-stale', action='store_true', help='Show only stale items')
    list_parser.add_argument('--stale-threshold', type=int, help='Custom stale threshold in minutes (default: 10)')
    list_parser.add_argument('--max-records', type=int, help='Maximum records to retrieve (default: 1000, max: 10000)')

    # Update response subcommand
    update_resp_parser = subparsers.add_parser('update-response', help='Update queue item response vault')
    update_resp_parser.add_argument('task_id', help='Task ID')
    update_resp_parser.add_argument('--vault', help='JSON vault data')
    update_resp_parser.add_argument('--vault-file', help='File containing JSON vault data')

    # Complete subcommand
    complete_parser = subparsers.add_parser('complete', help='Mark queue item as complete')
    complete_parser.add_argument('task_id', help='Task ID')
    complete_parser.add_argument('--vault', help='JSON vault data (optional)')
    complete_parser.add_argument('--vault-file', help='File containing JSON vault data (optional)')

    # Trace subcommand
    trace_parser = subparsers.add_parser('trace', help='Trace queue item execution')
    trace_parser.add_argument('task_id', help='Task ID to trace')

    # Cancel subcommand
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a queue item')
    cancel_parser.add_argument('task_id', help='Task ID to cancel')

    # Retry subcommand
    retry_parser = subparsers.add_parser('retry', help='Retry a queue item')
    retry_parser.add_argument('task_id', help='Task ID to retry')

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
    handler = QueueHandler(client_instance, args.output)

    # Route to appropriate command
    if args.subcommand == 'add':
        return handler.add_command(args)
    elif args.subcommand == 'list-functions':
        return handler.list_functions_command(args)
    elif args.subcommand == 'get-next':
        return handler.get_next_command(args)
    elif args.subcommand == 'list':
        return handler.list_command(args)
    elif args.subcommand == 'update-response':
        return handler.update_response_command(args)
    elif args.subcommand == 'complete':
        return handler.complete_command(args)
    elif args.subcommand == 'trace':
        return handler.trace_command(args)
    elif args.subcommand == 'cancel':
        return handler.cancel_command(args)
    elif args.subcommand == 'retry':
        return handler.retry_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
