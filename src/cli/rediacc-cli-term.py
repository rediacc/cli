#!/usr/bin/env python3
import argparse
import subprocess
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rediacc_cli_core import (
    colorize, validate_cli_tool, RepositoryConnection,
    INTERIM_FOLDER_NAME, get_ssh_key_from_vault
)

from core import TokenManager, setup_logging, get_logger

# Load configuration
def load_config():
    """Load configuration from JSON file"""
    config_path = Path(__file__).parent.parent / 'config' / 'rediacc-cli-term-config.json'
    try: return json.load(open(config_path, 'r'))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load config file: {e}")
        return {"terminal_commands": {}, "messages": {}, "help_text": {}}

# Global config
CONFIG = load_config()
MESSAGES = CONFIG.get('messages', {})
def print_message(key, color='BLUE', **kwargs):
    """Print a message from config with color and formatting"""
    msg = MESSAGES.get(key, key)
    if kwargs: msg = msg.format(**kwargs)
    print(colorize(msg, color))

def setup_ssh_connection(ssh_key, host_entry, dev_mode=False):
    """Setup SSH connection with agent or fallback to temp files"""
    from rediacc_cli_core import (
        setup_ssh_agent_connection, cleanup_ssh_agent,
        setup_ssh_for_connection, cleanup_ssh_key
    )
    
    try:
        ssh_opts, agent_pid, known_hosts_file = setup_ssh_agent_connection(ssh_key, host_entry)
        print_message('ssh_agent_setup', pid=agent_pid)
        return ssh_opts, agent_pid, None, known_hosts_file
    except Exception as e:
        print_message('ssh_agent_failed', 'YELLOW', error=e)
        ssh_opts, ssh_key_file, known_hosts_file = setup_ssh_for_connection(ssh_key, host_entry)
        return ssh_opts, None, ssh_key_file, known_hosts_file

def cleanup_ssh(agent_pid, ssh_key_file, known_hosts_file, conn=None):
    """Cleanup SSH resources"""
    from rediacc_cli_core import cleanup_ssh_agent, cleanup_ssh_key
    if agent_pid: cleanup_ssh_agent(agent_pid, known_hosts_file)
    elif ssh_key_file: conn.cleanup_ssh(ssh_key_file, known_hosts_file) if conn else cleanup_ssh_key(ssh_key_file, known_hosts_file)

def get_config_value(*keys, default=''):
    """Get nested config value with default"""
    result = CONFIG
    for key in keys:
        if not isinstance(result, dict) or key not in result: return default
        result = result[key]
    return result


def connect_to_machine(args):
    print_message('connecting_machine', 'HEADER', machine=args.machine)
    
    from rediacc_cli_core import get_machine_info_with_team, get_machine_connection_info, validate_machine_accessibility, handle_ssh_exit_code
    
    print(MESSAGES.get('fetching_info', 'Fetching machine information...'))
    machine_info = get_machine_info_with_team(args.team, args.machine)
    connection_info = get_machine_connection_info(machine_info)
    validate_machine_accessibility(args.machine, args.team, connection_info['ip'])
    
    print(MESSAGES.get('retrieving_ssh_key', 'Retrieving SSH key...'))
    if not (ssh_key := get_ssh_key_from_vault(args.team)): print_message('ssh_key_not_found', 'RED', team=args.team); sys.exit(1)
    
    host_entry = None if args.dev else connection_info.get('host_entry')
    ssh_opts, agent_pid, ssh_key_file, known_hosts_file = setup_ssh_connection(ssh_key, host_entry, args.dev)
    
    try:
        ssh_cmd = ['ssh', '-tt', *ssh_opts.split(), f"{connection_info['user']}@{connection_info['ip']}"]
        universal_user = connection_info.get('universal_user', 'rediacc')
        universal_user_id = connection_info.get('universal_user_id')
        datastore_path = f"{connection_info['datastore']}/{universal_user_id}" if universal_user_id else connection_info['datastore']
        
        if args.command:
            full_command = f"sudo -u {universal_user} bash -c 'cd {datastore_path} 2>/dev/null; {args.command}'"
            ssh_cmd.append(full_command)
            print_message('executing_as_user', user=universal_user, command=args.command)
            print_message('working_directory', path=datastore_path)
        else:
            commands = CONFIG.get('machine_welcome', {}).get('commands', [])
            format_vars = {'machine': args.machine, 'ip': connection_info["ip"], 'user': connection_info["user"], 'universal_user': universal_user, 'datastore_path': datastore_path}
            welcome_lines = [cmd.format(**format_vars) for cmd in commands]
            ssh_cmd.append(f"sudo -u {universal_user} bash -c '{' && '.join(welcome_lines)}'")
            print_message('opening_terminal'); print_message('exit_instruction', 'YELLOW')
        
        result = subprocess.run(ssh_cmd)
        handle_ssh_exit_code(result.returncode, "machine")
            
    finally:
        cleanup_ssh(agent_pid, ssh_key_file, known_hosts_file)


def connect_to_terminal(args):
    print_message('connecting_repository', 'HEADER', repo=args.repo, machine=args.machine)
    
    from rediacc_cli_core import validate_machine_accessibility, handle_ssh_exit_code
    
    conn = RepositoryConnection(args.team, args.machine, args.repo); conn.connect()
    validate_machine_accessibility(args.machine, args.team, conn.connection_info['ip'], args.repo)
    
    original_host_entry = conn.connection_info.get('host_entry') if args.dev else None
    if args.dev: conn.connection_info['host_entry'] = None
    if not (ssh_key := get_ssh_key_from_vault(args.team)): print_message('ssh_key_not_found', 'RED', team=args.team); sys.exit(1)
    
    host_entry = None if args.dev else conn.connection_info.get('host_entry')
    
    # Try agent first, then fallback to conn.setup_ssh()
    try:
        from rediacc_cli_core import setup_ssh_agent_connection
        ssh_opts, agent_pid, known_hosts_file = setup_ssh_agent_connection(ssh_key, host_entry)
        print_message('ssh_agent_setup', pid=agent_pid)
        ssh_key_file = None
    except Exception as e:
        print_message('ssh_agent_failed', 'YELLOW', error=e)
        ssh_opts, ssh_key_file, known_hosts_file = conn.setup_ssh()
        agent_pid = None
    
    if args.dev and original_host_entry is not None: conn.connection_info['host_entry'] = original_host_entry
    
    try:
        repo_paths = conn.repo_paths
        docker_socket = repo_paths['docker_socket']
        docker_host = f"unix://{docker_socket}"
        repo_mount_path = repo_paths['mount_path']
        
        env_template = CONFIG.get('environment_exports', {})
        env_format_vars = {'repo_mount_path': repo_mount_path, 'docker_host': docker_host, 'docker_folder': repo_paths['docker_folder'], 'docker_socket': docker_socket, 'docker_data': repo_paths['docker_data'], 'docker_exec': repo_paths['docker_exec']}
        env_exports = '\n'.join(f'export {key}=\'{value.format(**env_format_vars)}\'' for key, value in env_template.items()) + '\n'
        
        cd_logic = get_config_value('cd_logic', 'basic')
        
        if args.command: ssh_env_setup = env_exports + cd_logic
        else:
            extended_cd_logic = get_config_value('cd_logic', 'extended')
            bash_funcs = CONFIG.get('bash_functions', {})
            ps1_prompt = CONFIG.get('ps1_prompt', '').format(repo=args.repo)
            commands = CONFIG.get('repository_welcome', {}).get('commands', [])
            welcome_lines = [cmd.format(repo=args.repo) for cmd in commands]
            functions = '\n\n'.join(bash_funcs.values())
            exports = 'export -f enter_container\nexport -f logs\nexport -f status'
            
            ssh_env_setup = f"""{env_exports}export PS1='{ps1_prompt}'\n{extended_cd_logic}\n\n{functions}\n\n{exports}\n\n{chr(10).join(welcome_lines)}\n"""
        
        universal_user = conn.connection_info.get('universal_user', 'rediacc')
        ssh_cmd = ['ssh', '-tt', *ssh_opts.split(), conn.ssh_destination]
        escaped_env = ssh_env_setup.replace("'", "'\"'\"'")
        
        if args.command:
            full_command = escaped_env + args.command
            print_message('executing_command', command=args.command)
        else:
            print_message('opening_terminal'); print_message('exit_instruction', 'YELLOW')
            full_command = escaped_env + "exec bash -l"
        
        ssh_cmd.append(f"sudo -u {universal_user} bash -c '{full_command}'")
        result = subprocess.run(ssh_cmd)
        handle_ssh_exit_code(result.returncode, "repository terminal")
            
    finally:
        cleanup_ssh(agent_pid, ssh_key_file, known_hosts_file, conn)

def main():
    help_config = CONFIG.get('help_text', {})
    sections = []
    
    examples = ["Examples:"]
    for example in help_config.get('examples', {}).values():
        examples.extend([f"  {example.get('title', '')}", f"    {example.get('command', '')}", ""])
    sections.append('\n'.join(examples))
    
    if repo_env := help_config.get('repository_env_vars', {}):
        env_section = [repo_env.get('title', ''), f"  {repo_env.get('subtitle', '')}"]
        env_section.extend(f"    {var:<15} - {desc}" for var, desc in repo_env.get('vars', {}).items())
        sections.append('\n'.join(env_section))
    
    if machine_info := help_config.get('machine_only_info', {}):
        machine_section = [machine_info.get('title', '')]
        machine_section.extend(f"  {point}" for point in machine_info.get('points', []))
        sections.append('\n'.join(machine_section))
    
    epilog_text = '\n\n'.join(sections)
    
    parser = argparse.ArgumentParser(
        description=help_config.get('description', 'Rediacc CLI Terminal'),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_text
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging output')
    parser.add_argument('--token', help='Authentication token (GUID)')
    parser.add_argument('--team', help='Team name')
    parser.add_argument('--machine', help='Target machine name')
    parser.add_argument('--repo', help='Target repository name (optional - if not specified, connects to machine only)')
    parser.add_argument('--command', help='Command to execute (interactive shell if not specified)')
    parser.add_argument('--dev', action='store_true', help='Development mode - relaxes SSH host key checking')
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    logger = get_logger(__name__)
    
    if args.verbose: logger.debug("Rediacc CLI Term starting up"); logger.debug(f"Arguments: {vars(args)}")
    if not (args.team and args.machine): parser.error("--team and --machine are required in CLI mode")
    
    if args.token: os.environ['REDIACC_TOKEN'] = args.token
    elif not TokenManager.get_token(): parser.error("No authentication token available. Please login first.")
    
    validate_cli_tool()
    (connect_to_terminal if args.repo else connect_to_machine)(args)

if __name__ == '__main__':
    main()