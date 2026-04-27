import { Outlet } from "react-router-dom";
import { AppSidebar } from "../components/sidebar/AppSidebar";
import { SourcesSidebar } from "../components/sidebar/SourcesSidebar";
import { usePersistedHistory } from "../hooks/usePersistedHistory";
import { SidebarInset, SidebarProvider } from "../components/ui/sidebar/sidebar";
import { Header } from "./Header";

export function RootLayout() {
  usePersistedHistory();

  return (
    <SidebarProvider className="flex-col h-svh">
      <Header />
      <div className="flex flex-1 min-h-0">
        <AppSidebar />
        <SidebarInset className="bg-surface-base">
          <Outlet />
        </SidebarInset>
        <SourcesSidebar />
      </div>
    </SidebarProvider>
  );
}
