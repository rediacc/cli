import React, { useState, useEffect } from 'react';
import { Form, Select, Input, Button, Card, Space, Typography, Divider, Modal, Spin, Alert } from 'antd';
import { PlayCircleOutlined, SaveOutlined, CopyOutlined } from '@ant-design/icons';
import { useWebSocket } from '@/hooks/useWebSocket';
import { message } from 'antd';
import CommandOutput from '@/components/CommandOutput';
import { commandDefinitions } from '@/utils/commandDefinitions';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

const CommandBuilderPage: React.FC = () => {
  const [form] = Form.useForm();
  const { connected, sendCommand } = useWebSocket();
  const [selectedCommand, setSelectedCommand] = useState<string>('');
  const [selectedSubcommand, setSelectedSubcommand] = useState<string>('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [showOutput, setShowOutput] = useState(false);
  const [currentCommandId, setCurrentCommandId] = useState<string>('');

  const handleCommandChange = (value: string) => {
    setSelectedCommand(value);
    setSelectedSubcommand('');
    form.resetFields();
    form.setFieldValue('command', value);
  };

  const handleSubcommandChange = (value: string) => {
    setSelectedSubcommand(value);
    form.setFieldValue('subcommand', value);
  };

  const buildCommandString = (values: any): { command: string; args: string[] } => {
    const parts = ['rediacc'];
    const args: string[] = [];

    if (values.command) {
      args.push(values.command);
    }
    if (values.subcommand) {
      args.push(values.subcommand);
    }

    // Add positional arguments
    const commandDef = commandDefinitions[values.command];
    const params = values.subcommand 
      ? commandDef?.subcommands?.[values.subcommand]?.params 
      : commandDef?.params;

    if (params) {
      params.forEach(param => {
        const value = values[param.name];
        if (value !== undefined && value !== '') {
          if (param.name.startsWith('--')) {
            args.push(param.name);
            if (param.type !== 'boolean') {
              args.push(String(value));
            }
          } else {
            args.push(String(value));
          }
        }
      });
    }

    return { command: parts.join(' '), args };
  };

  const handleExecute = async () => {
    try {
      const values = await form.validateFields();
      const { command, args } = buildCommandString(values);

      if (!connected) {
        message.error('Not connected to CLI server');
        return;
      }

      setIsExecuting(true);
      setShowOutput(true);

      const commandId = await sendCommand(command, args);
      setCurrentCommandId(commandId);
    } catch (error) {
      console.error('Validation failed:', error);
      message.error('Please fill in all required fields');
    }
  };

  const handleCopyCommand = () => {
    const values = form.getFieldsValue();
    const { command, args } = buildCommandString(values);
    const fullCommand = `${command} ${args.join(' ')}`;
    
    navigator.clipboard.writeText(fullCommand);
    message.success('Command copied to clipboard');
  };

  const renderFormFields = () => {
    if (!selectedCommand) return null;

    const commandDef = commandDefinitions[selectedCommand];
    if (!commandDef) return null;

    const params = selectedSubcommand 
      ? commandDef.subcommands?.[selectedSubcommand]?.params 
      : commandDef.params;

    if (!params || params.length === 0) return null;

    return params.map((param) => (
      <Form.Item
        key={param.name}
        name={param.name}
        label={param.name}
        rules={[
          {
            required: param.required,
            message: `Please provide ${param.name}`,
          },
        ]}
        help={param.help}
      >
        {param.type === 'select' && param.choices ? (
          <Select placeholder={`Select ${param.name}`}>
            {param.choices.map((choice) => (
              <Option key={choice} value={choice}>
                {choice}
              </Option>
            ))}
          </Select>
        ) : param.type === 'boolean' ? (
          <Select placeholder={`Select ${param.name}`}>
            <Option value={true}>Yes</Option>
            <Option value={false}>No</Option>
          </Select>
        ) : param.type === 'number' ? (
          <Input type="number" placeholder={param.help} />
        ) : (
          <Input placeholder={param.help} />
        )}
      </Form.Item>
    ));
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={2}>Command Builder</Title>
        <Text type="secondary">Build and execute CLI commands visually</Text>
      </div>

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleExecute}
        >
          <Form.Item
            name="command"
            label="Command"
            rules={[{ required: true, message: 'Please select a command' }]}
          >
            <Select
              placeholder="Select a command"
              onChange={handleCommandChange}
              size="large"
            >
              {Object.keys(commandDefinitions).map((cmd) => (
                <Option key={cmd} value={cmd}>
                  {cmd} - {commandDefinitions[cmd].description}
                </Option>
              ))}
            </Select>
          </Form.Item>

          {selectedCommand && commandDefinitions[selectedCommand]?.subcommands && (
            <Form.Item
              name="subcommand"
              label="Subcommand"
              rules={[{ required: true, message: 'Please select a subcommand' }]}
            >
              <Select
                placeholder="Select a subcommand"
                onChange={handleSubcommandChange}
                size="large"
              >
                {Object.entries(commandDefinitions[selectedCommand].subcommands).map(
                  ([sub, def]) => (
                    <Option key={sub} value={sub}>
                      {sub} - {def.description}
                    </Option>
                  )
                )}
              </Select>
            </Form.Item>
          )}

          {renderFormFields()}

          <Divider />

          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleExecute}
              loading={isExecuting}
              disabled={!connected}
              size="large"
            >
              Execute
            </Button>
            <Button
              icon={<CopyOutlined />}
              onClick={handleCopyCommand}
              size="large"
            >
              Copy Command
            </Button>
            <Button
              icon={<SaveOutlined />}
              size="large"
              disabled
            >
              Save as Favorite
            </Button>
          </Space>

          {!connected && (
            <Alert
              message="Not connected to CLI server"
              description="Please ensure the CLI WebSocket server is running"
              type="warning"
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
        </Form>
      </Card>

      {showOutput && (
        <Card title="Command Output">
          <CommandOutput
            commandId={currentCommandId}
            onComplete={() => setIsExecuting(false)}
          />
        </Card>
      )}
    </Space>
  );
};

export default CommandBuilderPage;