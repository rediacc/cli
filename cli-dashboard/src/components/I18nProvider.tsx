import React from 'react';
import { useTranslation } from 'react-i18next';
import { message } from 'antd';

export const useI18nMessage = () => {
  const { t } = useTranslation();

  return {
    success: (key: string, interpolation?: any) => {
      message.success(t(key, interpolation));
    },
    error: (key: string, interpolation?: any) => {
      message.error(t(key, interpolation));
    },
    info: (key: string, interpolation?: any) => {
      message.info(t(key, interpolation));
    },
    warning: (key: string, interpolation?: any) => {
      message.warning(t(key, interpolation));
    },
  };
};