import {
  CaretRightIcon,
  ChatCenteredDotsIcon,
  GearIcon,
  InfoIcon,
  PencilSimpleLineIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAppStore } from "../../store/appStore";
import { FeedbackModal } from "../modals/FeedbackModal";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "../ui/sidebar/sidebar";

export function AppSidebar() {
  const sessions = useAppStore((s) => s.sessions);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const startNewSession = useAppStore((s) => s.startNewSession);
  const loadSession = useAppStore((s) => s.loadSession);
  const { isMobile, setOpenMobile } = useSidebar();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const [feedbackOpen, setFeedbackOpen] = useState(false);

  function closeOnMobile() {
    if (isMobile) setOpenMobile(false);
  }

  function handleNewChat() {
    startNewSession();
    navigate("/");
    closeOnMobile();
  }

  return (
    <>
      <Sidebar collapsible="icon">
        <SidebarContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={handleNewChat} tooltip="New Chat">
                <PencilSimpleLineIcon weight="bold" />
                <span>New Chat</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>

          <SidebarGroup className="group-data-[collapsible=icon]:hidden">
            <SidebarGroupLabel>Chats</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {sessions.map((session) => (
                  <SidebarMenuItem key={session.id}>
                    <SidebarMenuButton
                      isActive={session.id === currentSessionId && pathname === "/"}
                      onClick={() => {
                        loadSession(session.id);
                        navigate("/");
                        closeOnMobile();
                      }}
                    >
                      <span className="flex-1 truncate">{session.title}</span>
                      {session.id === currentSessionId && pathname === "/" && (
                        <CaretRightIcon weight="bold" />
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                tooltip="Share a feedback"
                onClick={() => {
                  setFeedbackOpen(true);
                  closeOnMobile();
                }}
              >
                <ChatCenteredDotsIcon weight="bold" />
                <span>Share a feedback</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Settings" isActive={pathname === "/settings"}>
                <Link to="/settings" onClick={closeOnMobile}>
                  <GearIcon weight="bold" />
                  <span>Settings</span>
                  {pathname === "/settings" && <CaretRightIcon weight="bold" className="ms-auto" />}
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Privacy Policy" isActive={pathname === "/policy"}>
                <Link to="/policy" onClick={closeOnMobile}>
                  <InfoIcon weight="bold" />
                  <span>Privacy Policy</span>
                  {pathname === "/policy" && <CaretRightIcon weight="bold" className="ms-auto" />}
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>

        <SidebarRail />
      </Sidebar>

      <FeedbackModal open={feedbackOpen} onOpenChange={setFeedbackOpen} />
    </>
  );
}
