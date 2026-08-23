import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceSidebar } from '@/components/workspace/WorkspaceSidebar';
import type { WorkspaceDatabase, ViewId } from '@/components/workspace/shared';

const workspaceState = vi.hoisted(() => ({
  role: 'admin',
  permissions: {
    can_manage_members: true,
    can_manage_invitations: true,
    can_manage_schema: false,
  } as Record<string, boolean>,
}));

vi.mock('@/context/WorkspaceContext', () => ({
  useWorkspace: () => ({
    workspaces: [],
    currentWorkspace: { id: 1, name: 'Risk Analytics', role: workspaceState.role },
    role: workspaceState.role,
    permissions: workspaceState.permissions,
    switchWorkspace: vi.fn(),
  }),
}));

describe('WorkspaceSidebar', () => {
  afterEach(() => {
    cleanup();
    workspaceState.role = 'admin';
    workspaceState.permissions = {
      can_manage_members: true,
      can_manage_invitations: true,
      can_manage_schema: false,
    };
  });

  const mockDatabases: WorkspaceDatabase[] = [
    {
      id: 'db-1',
      name: 'Production DB',
      engine: 'postgresql',
      status: 'connected',
      tables: 24,
    },
    {
      id: 'db-2',
      name: 'Analytics SQLite',
      engine: 'sqlite',
      status: 'idle',
      tables: 8,
    },
  ];

  const defaultProps = {
    databases: mockDatabases,
    activeDbId: 'db-1',
    view: 'catalog' as ViewId,
    theme: 'light' as const,
    pendingCount: 3,
    collapsed: false,
    canChat: true,
    onSelectView: vi.fn(),
    onToggleCollapse: vi.fn(),
    onToggleTheme: vi.fn(),
    onSelectDatabase: vi.fn(),
    onRemoveDatabase: vi.fn(),
    onConnectDatabase: vi.fn(),
    onOpenSettings: vi.fn(),
  };

  describe('navigation order and labels', () => {
    it('renders nav items in reference order: AI Studio, Metrics Catalog, Metric Explorer, Export Playground', () => {
      render(<WorkspaceSidebar {...defaultProps} />);

      const nav = screen.getByRole('navigation');
      const buttons = within(nav).getAllByRole('button');

      expect(buttons[0]).toHaveTextContent('AI Studio');
      expect(buttons[1]).toHaveTextContent('Metrics Catalog');
      expect(buttons[2]).toHaveTextContent('Metric Explorer');
      expect(buttons[3]).toHaveTextContent('Export Playground');
    });
  });

  describe('expanded layout', () => {
    it('renders sidebar at 288px width (w-72)', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={false} />);

      const sidebar = screen.getByRole('complementary');
      expect(sidebar).toHaveClass('w-72');
    });

    it('shows the brand header with collapse button', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={false} />);

      expect(screen.getByText('S206')).toBeInTheDocument();
      expect(screen.getByText('SEMANTIC')).toBeInTheDocument();
      expect(screen.getByLabelText('Collapse sidebar')).toBeInTheDocument();
    });

    it('shows data sources section with database cards', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={false} />);

      expect(screen.getByText('Data Sources')).toBeInTheDocument();
      expect(screen.getByText('Production DB')).toBeInTheDocument();
      expect(screen.getByText('Analytics SQLite')).toBeInTheDocument();
    });

    it('shows footer with settings button', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={false} />);

      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    it('renders footer with inline flex layout matching reference', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={false} />);

      const footer = screen.getByText('Settings').closest('[class*="border-t"]');
      expect(footer).toHaveClass('flex');
      expect(footer).toHaveClass('items-center');
      expect(footer).toHaveClass('justify-between');
    });

    it('preserves userName and logout in footer when provided', () => {
      const onLogout = vi.fn();
      render(<WorkspaceSidebar {...defaultProps} userName="alice" onLogout={onLogout} collapsed={false} />);

      expect(screen.getByText('alice')).toBeInTheDocument();
      expect(screen.getByTitle('Đăng xuất')).toBeInTheDocument();
    });
  });

  it('renders workspace management only for a role with management permissions', () => {
    const onOpenWorkspaceManagement = vi.fn();
    const { rerender } = render(
      <WorkspaceSidebar {...defaultProps} onOpenWorkspaceManagement={onOpenWorkspaceManagement} />,
    );
    fireEvent.click(screen.getByLabelText('Manage workspace'));
    expect(onOpenWorkspaceManagement).toHaveBeenCalledOnce();

    workspaceState.permissions = { can_manage_members: false, can_manage_invitations: false };
    rerender(<WorkspaceSidebar {...defaultProps} onOpenWorkspaceManagement={onOpenWorkspaceManagement} />);
    expect(screen.queryByLabelText('Manage workspace')).not.toBeInTheDocument();
  });

  it('hides AI Studio navigation when the workspace has no chat capability', () => {
    render(<WorkspaceSidebar {...defaultProps} canChat={false} />);

    expect(screen.queryByRole('button', { name: 'AI Studio' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Metrics Catalog/ })).toBeInTheDocument();
  });

  it('labels the restricted chat mode as Data Assistant', () => {
    render(<WorkspaceSidebar {...defaultProps} chatMode="data_assistant" />);

    expect(screen.getByRole('button', { name: 'Data Assistant' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'AI Studio' })).not.toBeInTheDocument();
  });

  describe('collapsed layout', () => {
    it('renders collapsed rail at 50px width (w-14)', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={true} />);

      const sidebar = screen.getByRole('complementary');
      expect(sidebar).toHaveClass('w-14');
    });

    it('shows expand button instead of brand', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={true} />);

      expect(screen.getByLabelText('Expand sidebar')).toBeInTheDocument();
      expect(screen.queryByText('SemanticLayer')).not.toBeInTheDocument();
    });

    it('shows expand button with rotated chevron icon', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={true} />);

      const expandBtn = screen.getByLabelText('Expand sidebar');
      const icon = expandBtn.querySelector('svg');
      expect(icon).toHaveClass('rotate-180');
    });

    it('renders icon-only nav items without labels', () => {
      render(<WorkspaceSidebar {...defaultProps} collapsed={true} />);

      const nav = screen.getByRole('navigation');
      const buttons = within(nav).getAllByRole('button');

      expect(buttons).toHaveLength(5);
      expect(buttons[0]).toHaveAttribute('aria-label', 'AI Studio');
      expect(buttons[1]).toHaveAttribute('aria-label', 'Metrics Catalog');
      expect(buttons[2]).toHaveAttribute('aria-label', 'Metric Explorer');
      expect(buttons[3]).toHaveAttribute('aria-label', 'Export Playground');
      expect(buttons[4]).toHaveAttribute('aria-label', 'Mở lịch sử trò chuyện');
    });
  });

  describe('selected view behavior', () => {
    it('marks the active view with aria-current="page"', () => {
      render(<WorkspaceSidebar {...defaultProps} view="explorer" />);

      const nav = screen.getByRole('navigation');
      const explorerButton = within(nav).getByRole('button', { name: 'Metric Explorer' });
      expect(explorerButton).toHaveAttribute('aria-current', 'page');
    });

    it('does not mark inactive views', () => {
      render(<WorkspaceSidebar {...defaultProps} view="explorer" />);

      const nav = screen.getByRole('navigation');
      const studioButton = within(nav).getByRole('button', { name: 'AI Studio' });
      expect(studioButton).not.toHaveAttribute('aria-current');
    });
  });

  describe('selected connection behavior', () => {
    it('highlights the active database card', () => {
      render(<WorkspaceSidebar {...defaultProps} activeDbId="db-1" />);

      const activeCard = screen.getByText('Production DB').closest('[data-active]');
      expect(activeCard).toHaveAttribute('data-active', 'true');
    });

    it('shows connected status dot for connected databases', () => {
      render(<WorkspaceSidebar {...defaultProps} />);

      const dots = screen.getAllByTestId('db-status-dot');
      expect(dots[0]).toHaveClass('bg-emerald-500');
    });
  });

  describe('pending metric badge', () => {
    it('shows pending count badge on catalog nav item when pending > 0', () => {
      render(<WorkspaceSidebar {...defaultProps} pendingCount={5} />);

      const nav = screen.getByRole('navigation');
      const catalogButton = within(nav).getByRole('button', { name: /Metrics Catalog/ });
      expect(within(catalogButton).getByText('5')).toBeInTheDocument();
    });

    it('does not show badge when pending count is 0', () => {
      render(<WorkspaceSidebar {...defaultProps} pendingCount={0} />);

      const nav = screen.getByRole('navigation');
      const catalogButton = within(nav).getByRole('button', { name: /Metrics Catalog/ });
      expect(within(catalogButton).queryByText('0')).not.toBeInTheDocument();
    });
  });

  describe('settings and connect triggers', () => {
    it('calls onOpenSettings when settings button is clicked', () => {
      const onOpenSettings = vi.fn();
      render(<WorkspaceSidebar {...defaultProps} onOpenSettings={onOpenSettings} />);

      fireEvent.click(screen.getByText('Settings'));
      expect(onOpenSettings).toHaveBeenCalledTimes(1);
    });

    it('calls onConnectDatabase when connect button is clicked', () => {
      workspaceState.role = 'data_lead';
      workspaceState.permissions = { can_manage_schema: true };
      const onConnectDatabase = vi.fn();
      render(<WorkspaceSidebar {...defaultProps} onConnectDatabase={onConnectDatabase} />);

      fireEvent.click(screen.getByLabelText('Connect database'));
      expect(onConnectDatabase).toHaveBeenCalledTimes(1);
    });

    it.each([
      ['admin', false],
      ['member', false],
      ['data_lead', true],
    ])('shows schema controls for %s only when can_manage_schema is %s', (role, canManageSchema) => {
      workspaceState.role = role;
      workspaceState.permissions = { can_manage_schema: canManageSchema };
      const onConnectDatabase = vi.fn();
      const onRemoveDatabase = vi.fn();

      render(
        <WorkspaceSidebar
          {...defaultProps}
          onConnectDatabase={onConnectDatabase}
          onRemoveDatabase={onRemoveDatabase}
        />,
      );

      if (canManageSchema) {
        fireEvent.click(screen.getByLabelText('Connect database'));
        fireEvent.click(screen.getByLabelText('Remove Production DB'));
        expect(onConnectDatabase).toHaveBeenCalledOnce();
        expect(onRemoveDatabase).toHaveBeenCalledWith('db-1');
      } else {
        expect(screen.queryByLabelText('Connect database')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Remove Production DB')).not.toBeInTheDocument();
        expect(onConnectDatabase).not.toHaveBeenCalled();
        expect(onRemoveDatabase).not.toHaveBeenCalled();
      }
    });
  });

  describe('theme toggle', () => {
    it('calls onToggleTheme when theme button is clicked', () => {
      const onToggleTheme = vi.fn();
      render(<WorkspaceSidebar {...defaultProps} onToggleTheme={onToggleTheme} />);

      fireEvent.click(screen.getByLabelText('Toggle theme'));
      expect(onToggleTheme).toHaveBeenCalledTimes(1);
    });
  });

  describe('chat history integration', () => {
    const mockChatSessions = [
      {
        id: 'chat-1',
        db_id: 1,
        title: 'Doanh thu Q1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 5,
      },
    ];

    it('renders chat history section when canChat is true', () => {
      render(
        <WorkspaceSidebar
          {...defaultProps}
          canChat={true}
          chatSessions={mockChatSessions}
          activeChatSessionId="chat-1"
        />,
      );

      expect(screen.getByText('Lịch sử trò chuyện')).toBeInTheDocument();
      expect(screen.getByText('Doanh thu Q1')).toBeInTheDocument();
    });

    it('calls onSelectChatSession when clicking a chat item', () => {
      const onSelectChatSession = vi.fn();
      render(
        <WorkspaceSidebar
          {...defaultProps}
          canChat={true}
          chatSessions={mockChatSessions}
          activeChatSessionId="chat-1"
          onSelectChatSession={onSelectChatSession}
        />,
      );

      fireEvent.click(screen.getByText('Doanh thu Q1'));
      expect(onSelectChatSession).toHaveBeenCalledWith('chat-1');
    });

    it('opens chat history from the collapsed rail when canChat is true', () => {
      const onSelectView = vi.fn();
      const onToggleCollapse = vi.fn();
      render(
        <WorkspaceSidebar
          {...defaultProps}
          collapsed={true}
          canChat={true}
          chatSessions={mockChatSessions}
          onSelectView={onSelectView}
          onToggleCollapse={onToggleCollapse}
        />,
      );

      const historyBtn = screen.getByLabelText('Mở lịch sử trò chuyện');
      expect(historyBtn).toBeInTheDocument();
      fireEvent.click(historyBtn);
      expect(onSelectView).toHaveBeenCalledWith('ai-studio');
      expect(onToggleCollapse).toHaveBeenCalledTimes(1);
    });
  });

  describe('chat history integration', () => {
    const mockChatSessions = [
      {
        id: 'chat-1',
        db_id: 1,
        title: 'Doanh thu Q1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 5,
      },
    ];

    it('renders chat history section when canChat is true', () => {
      render(
        <WorkspaceSidebar
          {...defaultProps}
          canChat={true}
          chatSessions={mockChatSessions}
          activeChatSessionId="chat-1"
        />,
      );

      expect(screen.getByText('Lịch sử trò chuyện')).toBeInTheDocument();
      expect(screen.getByText('Doanh thu Q1')).toBeInTheDocument();
    });

    it('calls onSelectChatSession when clicking a chat item', () => {
      const onSelectChatSession = vi.fn();
      render(
        <WorkspaceSidebar
          {...defaultProps}
          canChat={true}
          chatSessions={mockChatSessions}
          activeChatSessionId="chat-1"
          onSelectChatSession={onSelectChatSession}
        />,
      );

      fireEvent.click(screen.getByText('Doanh thu Q1'));
      expect(onSelectChatSession).toHaveBeenCalledWith('chat-1');
    });

    it('opens chat history from the collapsed rail when canChat is true', () => {
      const onSelectView = vi.fn();
      const onToggleCollapse = vi.fn();
      render(
        <WorkspaceSidebar
          {...defaultProps}
          collapsed={true}
          canChat={true}
          chatSessions={mockChatSessions}
          onSelectView={onSelectView}
          onToggleCollapse={onToggleCollapse}
        />,
      );

      const historyBtn = screen.getByLabelText('Mở lịch sử trò chuyện');
      expect(historyBtn).toBeInTheDocument();
      fireEvent.click(historyBtn);
      expect(onSelectView).toHaveBeenCalledWith('ai-studio');
      expect(onToggleCollapse).toHaveBeenCalledTimes(1);
    });
  });
});
