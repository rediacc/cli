#!/usr/bin/env python3
"""
API Mutex - Ensures only one process makes API calls at a time
"""
import os
import sys
import time
import errno
from pathlib import Path
from contextlib import contextmanager
from config_path import get_config_dir, get_api_lock_file

# Try to import fcntl (Unix/Linux/MSYS2)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Try to import msvcrt (Windows)
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

class APIMutex:
    """Simple file-based mutex for API calls"""
    
    def __init__(self, lock_file: Path = None):
        if lock_file is None:
            # Use centralized lock file path
            lock_file = get_api_lock_file()
        
        self.lock_file = str(lock_file)
    
    @contextmanager
    def acquire(self, timeout: float = 30.0):
        """Acquire exclusive lock for API call"""
        start_time = time.time()
        lock_fd = None
        
        try:
            # Open or create lock file
            lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY)
            
            # Try to acquire exclusive lock with timeout
            while True:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    
                    # Check timeout
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire API lock after {timeout}s")
                    
                    # Brief sleep before retry
                    time.sleep(0.05)
            
            # Lock acquired, yield control
            yield
            
        finally:
            # Release lock and close file
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except:
                    pass
                try:
                    os.close(lock_fd)
                except:
                    pass

# For Windows compatibility when fcntl is not available
if not HAS_FCNTL and HAS_MSVCRT:
    class APIMutexWindows:
        """Windows-compatible mutex using msvcrt"""
        
        def __init__(self, lock_file: Path = None):
            if lock_file is None:
                # Use centralized lock file path
                lock_file = get_api_lock_file()
            
            self.lock_file = str(lock_file)
        
        @contextmanager
        def acquire(self, timeout: float = 30.0):
            """Acquire exclusive lock for API call on Windows"""
            start_time = time.time()
            file_handle = None
            
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.lock_file), exist_ok=True)
                
                # Try to open/create the lock file
                while True:
                    try:
                        # Open file in binary write mode
                        file_handle = open(self.lock_file, 'wb')
                        
                        # Try to acquire exclusive lock
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except IOError:
                        # Lock is held by another process
                        if file_handle:
                            file_handle.close()
                            file_handle = None
                        
                        # Check timeout
                        if time.time() - start_time > timeout:
                            raise TimeoutError(f"Could not acquire API lock after {timeout}s")
                        
                        # Brief sleep before retry
                        time.sleep(0.05)
                
                # Lock acquired, yield control
                yield
                
            finally:
                # Release lock and close file
                if file_handle:
                    try:
                        # Unlock the file
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                    try:
                        file_handle.close()
                    except:
                        pass

# Create the appropriate mutex instance based on platform capabilities
if HAS_FCNTL:
    # Use fcntl-based locking (Unix/Linux/MSYS2 with POSIX support)
    api_mutex = APIMutex()
elif HAS_MSVCRT:
    # Use msvcrt-based locking (Native Windows)
    api_mutex = APIMutexWindows()
else:
    # Fallback: No locking available
    class APIMutexNoOp:
        """No-op mutex when no locking mechanism is available"""
        def __init__(self, lock_file: Path = None):
            pass
        
        @contextmanager
        def acquire(self, timeout: float = 30.0):
            yield
    
    api_mutex = APIMutexNoOp()
    print("Warning: No file locking mechanism available", file=sys.stderr)