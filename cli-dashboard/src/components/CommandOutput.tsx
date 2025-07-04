import React, { useEffect, useState, useRef } from 'react';
import { Typography, Spin, Alert } from 'antd';
import { useWebSocket } from '@/hooks/useWebSocket';
import { WebSocketMessage } from '@/types';

const { Text } = Typography;

interface CommandOutputProps {
  commandId: string;
  onComplete?: () => void;
}

const CommandOutput: React.FC<CommandOutputProps> = ({ commandId, onComplete }) => {
  const { onMessage, offMessage } = useWebSocket();
  const [output, setOutput] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const outputEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMessage = (message: WebSocketMessage) => {
      if (message.commandId !== commandId) return;

      switch (message.type) {
        case 'output':
          setOutput((prev) => [...prev, message.data]);
          break;
        case 'error':
          setError(message.data);
          break;
        case 'complete':
          setIsComplete(true);
          onComplete?.();
          break;
      }
    };

    onMessage(handleMessage);

    return () => {
      offMessage(handleMessage);
    };
  }, [commandId, onMessage, offMessage, onComplete]);

  useEffect(() => {
    // Auto-scroll to bottom
    outputEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [output]);

  if (error) {
    return (
      <Alert
        message="Command Failed"
        description={error}
        type="error"
        showIcon
      />
    );
  }

  return (
    <div
      className="command-output"
      style={{
        background: '#000',
        color: '#fff',
        padding: '12px',
        borderRadius: '4px',
        minHeight: '200px',
        maxHeight: '500px',
        overflow: 'auto',
      }}
    >
      {output.map((line, index) => (
        <div key={index}>{line}</div>
      ))}
      {!isComplete && (
        <div style={{ marginTop: '8px' }}>
          <Spin size="small" />
          <Text style={{ marginLeft: '8px', color: '#fff' }}>Running...</Text>
        </div>
      )}
      <div ref={outputEndRef} />
    </div>
  );
};

export default CommandOutput;