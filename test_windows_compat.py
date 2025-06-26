#!/usr/bin/env python3
"""
Test script to verify Windows compatibility for Rediacc CLI
This script checks if the platform detection and command abstractions work correctly
"""
import sys
import os

# Add CLI directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rediacc_cli_platform import (
    get_platform,
    is_windows,
    is_unix,
    get_null_device,
    get_temp_dir,
    get_home_dir,
    find_msys2_executable,
    get_rsync_command,
    convert_path_for_platform,
    prepare_rsync_paths,
    get_rsync_ssh_command
)


def test_platform_detection():
    """Test platform detection"""
    print("=== Platform Detection ===")
    print(f"Platform: {get_platform()}")
    print(f"Is Windows: {is_windows()}")
    print(f"Is Unix: {is_unix()}")
    print()


def test_path_handling():
    """Test path handling"""
    print("=== Path Handling ===")
    print(f"Null device: {get_null_device()}")
    print(f"Temp directory: {get_temp_dir()}")
    print(f"Home directory: {get_home_dir()}")
    print()
    
    # Test path conversions
    test_paths = [
        "/dev/null",
        "/tmp",
        "/mnt/c/Users/test",
        "C:\\Users\\test\\file.txt",
        "./relative/path",
        "user@host:/remote/path"
    ]
    
    print("Path conversions:")
    for path in test_paths:
        converted = convert_path_for_platform(path)
        print(f"  {path} -> {converted}")
    print()


def test_msys2_detection():
    """Test MSYS2 detection on Windows"""
    print("=== MSYS2 Detection ===")
    if is_windows():
        rsync_path = find_msys2_executable('rsync')
        ssh_path = find_msys2_executable('ssh')
        
        print(f"MSYS2 rsync: {rsync_path if rsync_path else 'Not found'}")
        print(f"MSYS2 ssh: {ssh_path if ssh_path else 'Not found'}")
        
        if not rsync_path:
            print("\nNOTE: rsync not found in MSYS2. Please install MSYS2 and the rsync package:")
            print("  1. Install MSYS2 from https://www.msys2.org/")
            print("  2. Run in MSYS2 terminal: pacman -S rsync openssh")
    else:
        print("Not on Windows - skipping MSYS2 detection")
    print()


def test_rsync_command():
    """Test rsync command generation"""
    print("=== Rsync Command ===")
    try:
        rsync_cmd = get_rsync_command()
        print(f"Rsync command: {rsync_cmd}")
    except RuntimeError as e:
        print(f"Error: {e}")
    print()


def test_rsync_paths():
    """Test rsync path preparation"""
    print("=== Rsync Path Preparation ===")
    test_cases = [
        ("C:\\Users\\test\\files", "user@host:/remote/path"),
        ("/home/user/files", "user@host:/remote/path"),
        ("user@host:/remote/source", "C:\\Users\\test\\backup"),
        ("./local/files/", "user@host:/remote/dest/"),
    ]
    
    for source, dest in test_cases:
        rsync_source, rsync_dest = prepare_rsync_paths(source, dest)
        print(f"  {source} -> {rsync_source}")
        print(f"  {dest} -> {rsync_dest}")
        print()


def test_ssh_command():
    """Test SSH command generation for rsync"""
    print("=== SSH Command for Rsync ===")
    ssh_opts = "-o StrictHostKeyChecking=no -i /tmp/key_file"
    try:
        ssh_cmd = get_rsync_ssh_command(ssh_opts)
        print(f"SSH command: {ssh_cmd}")
    except RuntimeError as e:
        print(f"Error: {e}")
    print()


def main():
    """Run all tests"""
    print("Rediacc CLI Windows Compatibility Test\n")
    
    test_platform_detection()
    test_path_handling()
    test_msys2_detection()
    test_rsync_command()
    test_rsync_paths()
    test_ssh_command()
    
    print("\nTest completed!")
    
    # Check if we're ready for Windows
    if is_windows():
        print("\n=== Windows Readiness Check ===")
        rsync_found = False
        ssh_found = False
        
        try:
            get_rsync_command()
            rsync_found = True
        except:
            pass
            
        try:
            find_msys2_executable('ssh')
            ssh_found = True
        except:
            pass
        
        if rsync_found and ssh_found:
            print("✓ System is ready for Rediacc CLI on Windows!")
        else:
            print("✗ Missing dependencies:")
            if not rsync_found:
                print("  - rsync not found")
            if not ssh_found:
                print("  - ssh not found")
            print("\nPlease install MSYS2 and required packages.")


if __name__ == "__main__":
    main()