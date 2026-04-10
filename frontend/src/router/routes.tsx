import { createBrowserRouter } from "react-router-dom";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { RootLayout } from "../layouts/RootLayout";
import { ChatPage } from "../pages/ChatPage";
import { ErrorPage } from "../pages/ErrorPage";
import { PolicyPage } from "../pages/PolicyPage";
import { SettingsPage } from "../pages/SettingsPage";

export const router = createBrowserRouter([
  {
    element: <ProtectedRoute />,
    errorElement: <ErrorPage />,
    children: [
      {
        element: <RootLayout />,
        errorElement: <ErrorPage />,
        children: [
          { index: true, element: <ChatPage /> },
          { path: "policy", element: <PolicyPage /> },
          { path: "settings", element: <SettingsPage /> },
        ],
      },
    ],
  },
]);
