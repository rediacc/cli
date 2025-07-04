import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { message } from 'antd';
import { WebSocketMessage } from '@/types';
import { useAuth } from './useAuth';

interface WebSocketContextType {
  socket: Socket | null;
  connected: boolean;
  sendCommand: (command: string, args: string[]) => Promise<string>;
  onMessage: (callback: (message: WebSocketMessage) => void) => void;
  offMessage: (callback: (message: WebSocketMessage) => void) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, isAuthenticated } = useAuth();
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const messageCallbacks = new Set<(message: WebSocketMessage) => void>();

  useEffect(() => {
    if (!isAuthenticated || !token) {
      return;
    }

    const newSocket = io('http://localhost:8765', {
      auth: {
        token,
      },
      transports: ['websocket'],
    });

    newSocket.on('connect', () => {
      setConnected(true);
      message.success('Connected to CLI server');
    });

    newSocket.on('disconnect', () => {
      setConnected(false);
      message.warning('Disconnected from CLI server');
    });

    newSocket.on('message', (msg: WebSocketMessage) => {
      messageCallbacks.forEach(callback => callback(msg));
    });

    newSocket.on('error', (error: any) => {
      console.error('WebSocket error:', error);
      message.error('WebSocket connection error');
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [isAuthenticated, token]);

  const sendCommand = useCallback((command: string, args: string[]): Promise<string> => {
    return new Promise((resolve, reject) => {
      if (!socket || !connected) {
        reject(new Error('Not connected to CLI server'));
        return;
      }

      const commandId = `cmd-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      socket.emit('execute', {
        id: commandId,
        command,
        args,
      });

      resolve(commandId);
    });
  }, [socket, connected]);

  const onMessage = useCallback((callback: (message: WebSocketMessage) => void) => {
    messageCallbacks.add(callback);
  }, []);

  const offMessage = useCallback((callback: (message: WebSocketMessage) => void) => {
    messageCallbacks.delete(callback);
  }, []);

  return (
    <WebSocketContext.Provider
      value={{
        socket,
        connected,
        sendCommand,
        onMessage,
        offMessage,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};