import { Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { UnauthorizedPage } from "../pages/UnauthorizedPage";

export function ProtectedRoute() {
  const { isAuthorized } = useAuth();
  return isAuthorized ? <Outlet /> : <UnauthorizedPage />;
}
