import axios from 'axios';
import { User } from '@/types';

const API_BASE_URL = '/api';

export const authService = {
  async login(email: string, password: string): Promise<{ token: string; user: User }> {
    try {
      // First, create authentication request
      const response = await axios.post(`${API_BASE_URL}/CreateAuthenticationRequest`, {
        email,
        password,
        name: 'CLI Dashboard Session',
        requestedPermissions: null,
        tokenExpirationHours: 24,
      });

      if (response.data.success) {
        const token = response.data.token;
        const user: User = {
          email,
          permissions: response.data.permissions,
          company: response.data.company,
        };

        return { token, user };
      } else {
        throw new Error(response.data.message || 'Login failed');
      }
    } catch (error: any) {
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      throw new Error('Failed to connect to server');
    }
  },

  async logout(token: string): Promise<void> {
    try {
      await axios.post(
        `${API_BASE_URL}/DeleteUserRequest`,
        {},
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
    } catch (error) {
      console.error('Logout error:', error);
    }
  },

  async validateToken(token: string): Promise<boolean> {
    try {
      const response = await axios.get(`${API_BASE_URL}/GetUserCompany`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      return response.data.success;
    } catch (error) {
      return false;
    }
  },
};