import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, List, Tag, Typography, Space, Spin } from 'antd';
import {
  TeamOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  ScheduleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const { Title, Text } = Typography;

interface DashboardStats {
  teams: number;
  machines: number;
  repositories: number;
  schedules: number;
  queueItems: {
    pending: number;
    processing: number;
    completed: number;
    failed: number;
  };
}

const DashboardPage: React.FC = () => {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    teams: 0,
    machines: 0,
    repositories: 0,
    schedules: 0,
    queueItems: {
      pending: 0,
      processing: 0,
      completed: 0,
      failed: 0,
    },
  });
  const [recentActivity, setRecentActivity] = useState<any[]>([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      const headers = {
        Authorization: `Bearer ${token}`,
      };

      // Fetch teams
      const teamsResponse = await axios.post('/api/GetCompanyTeams', {}, { headers });
      const teams = teamsResponse.data.data || [];

      // Fetch data graph for comprehensive stats
      const dataGraphResponse = await axios.post('/api/GetCompanyDataGraphJson', {}, { headers });
      const dataGraph = dataGraphResponse.data.data || {};

      // Count resources
      const machines = dataGraph.teams?.reduce((acc: number, team: any) => 
        acc + (team.machines?.length || 0), 0) || 0;
      const repositories = dataGraph.teams?.reduce((acc: number, team: any) => 
        acc + (team.repositories?.length || 0), 0) || 0;
      const schedules = dataGraph.teams?.reduce((acc: number, team: any) => 
        acc + (team.schedules?.length || 0), 0) || 0;

      setStats({
        teams: teams.length,
        machines,
        repositories,
        schedules,
        queueItems: {
          pending: 0, // Would need queue API
          processing: 0,
          completed: 0,
          failed: 0,
        },
      });

      // Fetch recent activity (audit logs)
      try {
        const auditResponse = await axios.post(
          '/api/GetAuditLogs',
          { maxRecords: 10 },
          { headers }
        );
        setRecentActivity(auditResponse.data.data || []);
      } catch (error) {
        console.error('Failed to fetch audit logs:', error);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getActivityIcon = (action: string) => {
    if (action.includes('Create')) return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    if (action.includes('Update')) return <ClockCircleOutlined style={{ color: '#1890ff' }} />;
    if (action.includes('Delete')) return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
    return <CheckCircleOutlined />;
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Title level={2}>{t('dashboard.title')}</Title>
        <Text type="secondary">{t('dashboard.subtitle')}</Text>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('dashboard.stats.teams')}
              value={stats.teams}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('dashboard.stats.machines')}
              value={stats.machines}
              prefix={<CloudServerOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t('dashboard.stats.repositories')}
              value={stats.repositories}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Schedules"
              value={stats.schedules}
              prefix={<ScheduleOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Recent Activity">
            <List
              dataSource={recentActivity}
              renderItem={(item: any) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={getActivityIcon(item.action)}
                    title={
                      <Space>
                        <Text>{item.action}</Text>
                        <Tag>{item.entityType}</Tag>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={0}>
                        <Text type="secondary">{item.userEmail}</Text>
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {new Date(item.timestamp).toLocaleString()}
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
              locale={{ emptyText: 'No recent activity' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Queue Status">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text>Pending</Text>
                <Tag color="default">{stats.queueItems.pending}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text>Processing</Text>
                <Tag color="processing">{stats.queueItems.processing}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text>Completed</Text>
                <Tag color="success">{stats.queueItems.completed}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text>Failed</Text>
                <Tag color="error">{stats.queueItems.failed}</Tag>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  );
};

export default DashboardPage;