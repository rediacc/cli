#!/usr/bin/env python3
"""WebSocket server for Rediacc CLI Dashboard integration."""

import asyncio
import json
import logging
import subprocess
import sys
import uuid
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol
import jwt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Active connections
connections: Dict[str, WebSocketServerProtocol] = {}
command_processes: Dict[str, subprocess.Popen] = {}

# JWT secret (should match the one used by the API)
JWT_SECRET = "your-jwt-secret-here"  # TODO: Load from config

async def authenticate_connection(websocket: WebSocketServerProtocol, path: str):
    """Authenticate WebSocket connection using JWT token."""
    try:
        # Get token from connection headers or query params
        auth_header = websocket.request_headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # Try to get from query params
            import urllib.parse
            query = urllib.parse.urlparse(path).query
            params = urllib.parse.parse_qs(query)
            token = params.get("token", [""])[0]
        
        if not token:
            await websocket.send(json.dumps({
                "type": "error",
                "data": "Authentication required"
            }))
            return None
        
        # Verify JWT token (simplified - should match your actual auth)
        try:
            # For now, just check if token exists
            # TODO: Implement proper JWT verification
            return token
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "data": "Invalid token"
            }))
            return None
            
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None

async def execute_command(websocket: WebSocketServerProtocol, command_data: dict):
    """Execute CLI command and stream output."""
    command_id = command_data.get("id", str(uuid.uuid4()))
    command = command_data.get("command", "")
    args = command_data.get("args", [])
    
    if not command:
        await websocket.send(json.dumps({
            "type": "error",
            "commandId": command_id,
            "data": "Command not specified"
        }))
        return
    
    # Build full command
    full_command = ["python3", "rediacc-cli"] + args
    
    logger.info(f"Executing command: {' '.join(full_command)}")
    
    try:
        # Start the process
        process = subprocess.Popen(
            full_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd="/home/muhammed/monorepo/cli"  # Ensure correct working directory
        )
        
        command_processes[command_id] = process
        
        # Send output line by line
        async def read_output():
            for line in iter(process.stdout.readline, ''):
                if line:
                    await websocket.send(json.dumps({
                        "type": "output",
                        "commandId": command_id,
                        "data": line.rstrip()
                    }))
                    await asyncio.sleep(0.01)  # Small delay to prevent flooding
        
        async def read_error():
            for line in iter(process.stderr.readline, ''):
                if line:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "commandId": command_id,
                        "data": line.rstrip()
                    }))
                    await asyncio.sleep(0.01)
        
        # Read both stdout and stderr concurrently
        await asyncio.gather(
            read_output(),
            read_error()
        )
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Send completion status
        await websocket.send(json.dumps({
            "type": "complete",
            "commandId": command_id,
            "data": {
                "returnCode": return_code,
                "success": return_code == 0
            }
        }))
        
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        await websocket.send(json.dumps({
            "type": "error",
            "commandId": command_id,
            "data": str(e)
        }))
    finally:
        # Clean up
        if command_id in command_processes:
            del command_processes[command_id]

async def handle_message(websocket: WebSocketServerProtocol, message: str):
    """Handle incoming WebSocket messages."""
    try:
        data = json.loads(message)
        message_type = data.get("type", "")
        
        if message_type == "execute":
            await execute_command(websocket, data)
        elif message_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "data": f"Unknown message type: {message_type}"
            }))
            
    except json.JSONDecodeError:
        await websocket.send(json.dumps({
            "type": "error",
            "data": "Invalid JSON"
        }))
    except Exception as e:
        logger.error(f"Message handling error: {e}")
        await websocket.send(json.dumps({
            "type": "error",
            "data": str(e)
        }))

async def websocket_handler(websocket: WebSocketServerProtocol, path: str):
    """Handle WebSocket connections."""
    connection_id = str(uuid.uuid4())
    
    try:
        # Authenticate connection
        token = await authenticate_connection(websocket, path)
        if not token:
            await websocket.close()
            return
        
        # Store connection
        connections[connection_id] = websocket
        logger.info(f"Client connected: {connection_id}")
        
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "connected",
            "data": {
                "connectionId": connection_id,
                "message": "Connected to Rediacc CLI WebSocket server"
            }
        }))
        
        # Handle messages
        async for message in websocket:
            await handle_message(websocket, message)
            
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        if connection_id in connections:
            del connections[connection_id]
        
        # Kill any running processes for this connection
        # (In a real implementation, track which processes belong to which connection)

async def main():
    """Start the WebSocket server."""
    host = "localhost"
    port = 8765
    
    logger.info(f"Starting WebSocket server on {host}:{port}")
    
    async with websockets.serve(websocket_handler, host, port):
        logger.info("WebSocket server started successfully")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)