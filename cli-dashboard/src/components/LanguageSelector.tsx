import React from 'react';
import { Select, Space } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { supportedLanguages } from '@/i18n';

const LanguageSelector: React.FC = () => {
  const { i18n } = useTranslation();

  const handleLanguageChange = (value: string) => {
    i18n.changeLanguage(value);
  };

  return (
    <Space>
      <GlobalOutlined />
      <Select
        value={i18n.language}
        onChange={handleLanguageChange}
        style={{ width: 120 }}
        options={supportedLanguages.map(lang => ({
          value: lang.code,
          label: (
            <Space>
              <span>{lang.flag}</span>
              <span>{lang.name}</span>
            </Space>
          ),
        }))}
      />
    </Space>
  );
};

export default LanguageSelector;