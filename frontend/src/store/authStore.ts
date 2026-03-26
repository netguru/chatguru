import { create } from "zustand";

export const AUTH_TOKEN_KEY = "token";

interface AuthState {
  isAuthorized: boolean;
  login: (token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthorized: Boolean(localStorage.getItem(AUTH_TOKEN_KEY)),

  login: (token) => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    set({ isAuthorized: true });
  },

  logout: () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    set({ isAuthorized: false });
  },
}));
