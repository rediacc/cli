import React, { useState, useEffect } from 'react';
import {
  Table,
  Tag,
  Space,
  Button,
  Typography,
  Input,
  DatePicker,
  Select,
  Card,
  Tooltip,
  Modal,
} from 'antd';
import {
  PlayCircleOutlined,
  EyeOutlined,
  CopyOutlined,
  StarOutlined,
  StarFilled,
  DeleteOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Command } from '@/types';
import { message } from 'antd';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

const HistoryPage: React.FC = () => {
  const [commands, setCommands] = useState<Command[]>([]);
  const [filteredCommands, setFilteredCommands] = useState<Command[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [selectedCommand, setSelectedCommand] = useState<Command | null>(null);
  const [showOutputModal, setShowOutputModal] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null]>([null, null]);

  useEffect(() => {
    // Load command history from localStorage
    const savedCommands = localStorage.getItem('cli-command-history');
    if (savedCommands) {
      setCommands(JSON.parse(savedCommands));
    }

    const savedFavorites = localStorage.getItem('cli-favorites');
    if (savedFavorites) {
      setFavorites(new Set(JSON.parse(savedFavorites)));
    }
  }, []);

  useEffect(() => {
    // Apply filters
    let filtered = [...commands];

    if (searchText) {
      filtered = filtered.filter(
        (cmd) =>
          cmd.command.toLowerCase().includes(searchText.toLowerCase()) ||
          cmd.args.join(' ').toLowerCase().includes(searchText.toLowerCase())
      );
    }

    if (statusFilter !== 'all') {
      filtered = filtered.filter((cmd) => cmd.status === statusFilter);
    }

    if (dateRange[0] && dateRange[1]) {
      filtered = filtered.filter((cmd) => {
        const cmdDate = dayjs(cmd.timestamp);
        return cmdDate.isAfter(dateRange[0]) && cmdDate.isBefore(dateRange[1]);
      });
    }

    setFilteredCommands(filtered);
  }, [commands, searchText, statusFilter, dateRange]);

  const toggleFavorite = (commandId: string) => {
    const newFavorites = new Set(favorites);
    if (newFavorites.has(commandId)) {
      newFavorites.delete(commandId);
    } else {
      newFavorites.add(commandId);
    }
    setFavorites(newFavorites);
    localStorage.setItem('cli-favorites', JSON.stringify(Array.from(newFavorites)));
  };

  const copyCommand = (command: Command) => {
    const fullCommand = `${command.command} ${command.args.join(' ')}`;
    navigator.clipboard.writeText(fullCommand);
    message.success('Command copied to clipboard');
  };

  const rerunCommand = (command: Command) => {
    message.info('Re-run functionality will be implemented with WebSocket integration');
    // TODO: Implement re-run using WebSocket
  };

  const clearHistory = () => {
    Modal.confirm({
      title: 'Clear Command History',
      content: 'Are you sure you want to clear all command history?',
      onOk: () => {
        setCommands([]);
        localStorage.removeItem('cli-command-history');
        message.success('Command history cleared');
      },
    });
  };

  const getStatusTag = (status: Command['status']) => {
    const statusConfig = {
      pending: { color: 'default', text: 'Pending' },
      running: { color: 'processing', text: 'Running' },
      completed: { color: 'success', text: 'Completed' },
      failed: { color: 'error', text: 'Failed' },
    };
    const config = statusConfig[status];
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const columns = [
    {
      title: 'Command',
      dataIndex: 'command',
      key: 'command',
      render: (command: string, record: Command) => (
        <Space direction="vertical" size={0}>
          <Text strong style={{ fontFamily: 'monospace' }}>
            {command} {record.args.join(' ')}
          </Text>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {dayjs(record.timestamp).fromNow()}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: Command['status']) => getStatusTag(status),
    },
    {
      title: 'Duration',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (duration?: number) =>
        duration ? `${(duration / 1000).toFixed(2)}s` : '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 200,
      render: (_: any, record: Command) => (
        <Space>
          <Tooltip title="View Output">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => {
                setSelectedCommand(record);
                setShowOutputModal(true);
              }}
              disabled={!record.output && !record.error}
            />
          </Tooltip>
          <Tooltip title="Copy Command">
            <Button
              type="text"
              icon={<CopyOutlined />}
              onClick={() => copyCommand(record)}
            />
          </Tooltip>
          <Tooltip title="Re-run Command">
            <Button
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={() => rerunCommand(record)}
            />
          </Tooltip>
          <Tooltip title={favorites.has(record.id) ? 'Remove from Favorites' : 'Add to Favorites'}>
            <Button
              type="text"
              icon={favorites.has(record.id) ? <StarFilled /> : <StarOutlined />}
              onClick={() => toggleFavorite(record.id)}
              style={{
                color: favorites.has(record.id) ? '#faad14' : undefined,
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={2}>Command History</Title>
        <Text type="secondary">View and manage your CLI command history</Text>
      </div>

      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap>
            <Input
              placeholder="Search commands..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 300 }}
            />
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 150 }}
            >
              <Select.Option value="all">All Status</Select.Option>
              <Select.Option value="completed">Completed</Select.Option>
              <Select.Option value="failed">Failed</Select.Option>
              <Select.Option value="running">Running</Select.Option>
              <Select.Option value="pending">Pending</Select.Option>
            </Select>
            <RangePicker
              value={dateRange}
              onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null])}
            />
            <Button danger icon={<DeleteOutlined />} onClick={clearHistory}>
              Clear History
            </Button>
          </Space>

          <Table
            columns={columns}
            dataSource={filteredCommands}
            rowKey="id"
            pagination={{
              pageSize: 10,
              showTotal: (total) => `Total ${total} commands`,
            }}
          />
        </Space>
      </Card>

      <Modal
        title="Command Output"
        open={showOutputModal}
        onCancel={() => setShowOutputModal(false)}
        footer={null}
        width={800}
      >
        {selectedCommand && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Text type="secondary">Command:</Text>
              <Paragraph
                copyable
                style={{
                  fontFamily: 'monospace',
                  background: '#f5f5f5',
                  padding: '8px',
                  borderRadius: '4px',
                }}
              >
                {selectedCommand.command} {selectedCommand.args.join(' ')}
              </Paragraph>
            </div>
            {selectedCommand.output && (
              <div>
                <Text type="secondary">Output:</Text>
                <pre
                  style={{
                    background: '#f5f5f5',
                    padding: '12px',
                    borderRadius: '4px',
                    overflow: 'auto',
                    maxHeight: '400px',
                  }}
                >
                  {selectedCommand.output}
                </pre>
              </div>
            )}
            {selectedCommand.error && (
              <div>
                <Text type="secondary">Error:</Text>
                <pre
                  style={{
                    background: '#fff1f0',
                    color: '#ff4d4f',
                    padding: '12px',
                    borderRadius: '4px',
                    overflow: 'auto',
                    maxHeight: '400px',
                  }}
                >
                  {selectedCommand.error}
                </pre>
              </div>
            )}
          </Space>
        )}
      </Modal>
    </Space>
  );
};

export default HistoryPage;