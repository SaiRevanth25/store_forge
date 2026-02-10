import { Outlet } from 'react-router';
import { AuthProvider } from '../contexts/AuthContext';

export const AuthWrapper = () => {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
};
