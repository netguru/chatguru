import { useEffect } from "react";
import { AUTH_TOKEN_KEY, useAuthStore } from "../store/authStore";

// Re-exported so consumers (e.g. UnauthorizedPage) can import AUTH_TOKEN_KEY
// from the same place as useAuth without coupling directly to authStore.
export { AUTH_TOKEN_KEY };

export function useAuth() {
  const isAuthorized = useAuthStore((s) => s.isAuthorized);
  const login = useAuthStore((s) => s.login);
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    function handleStorageChange(event: StorageEvent) {
      if (event.key !== AUTH_TOKEN_KEY) return;
      if (event.newValue) {
        login(event.newValue);
      } else {
        logout();
      }
    }

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [login, logout]);

  return { isAuthorized, login, logout };
}
