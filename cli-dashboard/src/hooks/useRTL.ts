import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfigProvider } from 'antd';

export const useRTL = () => {
  const { i18n } = useTranslation();

  useEffect(() => {
    const isRTL = i18n.language === 'ar';
    
    // Set document direction
    document.documentElement.dir = isRTL ? 'rtl' : 'ltr';
    
    // Set Ant Design direction
    ConfigProvider.config({
      direction: isRTL ? 'rtl' : 'ltr',
    });
  }, [i18n.language]);

  return i18n.language === 'ar';
};