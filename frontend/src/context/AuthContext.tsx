import React, { createContext, useState, ReactNode } from 'react';

interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  bio?: string;
  location?: string;
  website?: string;
  avatar_url?: string;
  is_active?: boolean;
  is_superuser?: boolean;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  login: (data: any) => Promise<void>;
  register: (data: any) => Promise<void>;
  logout: () => void;
  refetchUser: () => Promise<void>;
}

// Default local user for open-source version (no auth required)
const DEFAULT_USER: User = {
  id: 1,
  username: 'admin',
  email: 'admin@localhost',
  full_name: 'Local User',
  is_active: true,
  is_superuser: true,
};

export const AuthContext = createContext<AuthContextType>({
  isAuthenticated: true,
  isLoading: false,
  user: DEFAULT_USER,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  refetchUser: async () => {},
});

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user] = useState<User | null>(DEFAULT_USER);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: true,
        isLoading: false,
        user,
        login: async () => {},
        register: async () => {},
        logout: () => {},
        refetchUser: async () => {},
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
