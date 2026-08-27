import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import * as apiModule from '@/lib/api';
import WorkspacePage from './page';

const state = vi.hoisted(() => ({
  permissions: { can_manage_schema: false } as Record<string, boolean>,
}));

vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock('next/dynamic', () => ({
  default: (loader: () => Promise<React.ComponentType<any>>) => {
    function DynamicMock(props: { isOpen?: boolean }) {
      const [Comp, setComp] = React.useState<React.ComponentType<any> | null>(null);
      React.useEffect(() => {
        let active = true;
        loader().then((mod) => {
          if (active) setComp(() => mod);
        });
        return () => {
          active = false;
        };
      }, []);
      if (!Comp) return null;
      return React.createElement(Comp, props);
    }
    return DynamicMock;
  },
}));
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: { name: 'Tester' }, token: 'token', logout: vi.fn(), isLoading: false }),
}));
vi.mock('@/context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
}));
vi.mock('@/context/WorkspaceContext', () => ({
  useWorkspace: () => ({
    currentWorkspace: { id: 1 },
    permissions: state.permissions,
  }),
}));
vi.mock('@/components/views/AIStudioView', () => ({ AIStudioView: () => null }));
vi.mock('@/components/views/ExportPlaygroundView', () => ({
  ExportPlaygroundView: () => <div data-testid="export-playground-view" />,
}));
vi.mock('@/components/views/MetricsCatalogView', () => ({ MetricsCatalogView: () => null }));
vi.mock('@/components/views/MetricsDashboardView', () => ({
  MetricsDashboardView: () => <div data-testid="metrics-dashboard-view" />,
}));
vi.mock('@/components/modals/ConnectDbModal', () => ({
  ConnectDbModal: () => <div data-testid="dynamic-modal" />,
}));
vi.mock('@/components/workspace/WorkspaceApp', () => ({
  WorkspaceApp: (props: {
    onConnectDatabase?: () => void;
    onRemoveDatabase?: (id: string) => void;
    onSelectView?: (view: string) => void;
    children: React.ReactNode;
  }) => (
    <div>
      {props.onConnectDatabase && <button onClick={props.onConnectDatabase}>page-connect</button>}
      {props.onRemoveDatabase && <button onClick={() => props.onRemoveDatabase?.('1')}>page-delete</button>}
      {props.onSelectView && (
        <button onClick={() => props.onSelectView?.('dashboard')}>page-nav-dashboard</button>
      )}
      {props.onSelectView && (
        <button onClick={() => props.onSelectView?.('export')}>page-nav-export</button>
      )}
      {props.children}
    </div>
  ),
}));
vi.mock('@/lib/api', () => ({
  approveMetricsApi: vi.fn(),
  approveSingleMetricApi: vi.fn(),
  convertRawSchemaToLayer: vi.fn().mockImplementation((...args: any[]) => ({
    id: String(args[0]),
    db_name: args[1],
    db_type: args[2],
    semantic_db_id: args[6],
    source_type: 'live',
    metrics: [],
    tables: [],
    table_count: 0,
    is_loaded: true,
  })),
  createMetricApi: vi.fn(),
  deleteChatSessionApi: vi.fn(),
  deleteDatabaseApi: vi.fn(),
  deleteLayer: vi.fn(),
  deleteMetricApi: vi.fn(),
  getImportedSchema: vi.fn(),
  getLiveTargetDb: vi.fn().mockResolvedValue({
    id: 1,
    display_name: 'Test DB',
    dialect: 'postgresql',
    raw_schema: 'CREATE TABLE orders (id INT);',
    updated_at: '',
    semantic_db_id: 1,
  }),
  getSemanticCatalogApi: vi.fn().mockResolvedValue({
    db_id: 1,
    source_type: 'live',
    query_supported: true,
    tables: [],
    relationships: [],
  }),
  listChatSessionsApi: vi.fn().mockResolvedValue([]),
  listImportedSchemas: vi.fn().mockResolvedValue([]),
  listLiveTargetDbs: vi.fn().mockResolvedValue([]),
  listMetricsApi: vi.fn().mockResolvedValue([]),
  listNotificationsApi: vi.fn().mockResolvedValue({ items: [], unread_count: 0 }),
  streamNotifications: vi.fn().mockReturnValue(() => {}),
  markNotificationsReadApi: vi.fn().mockResolvedValue(undefined),
  markNotificationReadApi: vi.fn().mockResolvedValue(undefined),
  METRIC_WRITE_PERMISSION_MESSAGE: 'forbidden',
  updateChatSessionTitleApi: vi.fn(),
  updateMetricApi: vi.fn(),
}));

describe('WorkspacePage schema management', () => {
  afterEach(() => {
    cleanup();
    state.permissions = { can_manage_schema: false };
  });

  it.each(['admin', 'member'])('hides connection controls and callbacks for %s', async () => {
    render(<WorkspacePage />);

    await waitFor(() => expect(screen.queryByText('page-connect')).not.toBeInTheDocument());
    expect(screen.queryByText('page-delete')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Thêm kết nối Database' })).not.toBeInTheDocument();
  });

  it('exposes connection controls and callbacks to Data Lead', async () => {
    state.permissions = { can_manage_schema: true };
    render(<WorkspacePage />);

    fireEvent.click(await screen.findByText('page-connect'));
    expect(await screen.findByTestId('dynamic-modal')).toBeInTheDocument();
    expect(screen.getByText('page-delete')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Thêm kết nối Database' })).toBeInTheDocument();
  });
});

describe('WorkspacePage dashboard navigation', () => {
  afterEach(() => {
    cleanup();
    state.permissions = { can_manage_schema: false };
    vi.mocked(apiModule.listLiveTargetDbs).mockResolvedValue([]);
  });

  it('lazy-renders the Metrics Dashboard view when the dashboard tab is selected', async () => {
    vi.mocked(apiModule.listLiveTargetDbs).mockResolvedValue([
      {
        id: 1,
        display_name: 'Test DB',
        dialect: 'postgresql',
        updated_at: '',
        created_at: '',
        semantic_db_id: 1,
        table_count: 5,
      },
    ]);

    render(<WorkspacePage />);

    const dashboardNav = await screen.findByText('page-nav-dashboard');
    fireEvent.click(dashboardNav);

    const dashboardView = await screen.findByTestId('metrics-dashboard-view');
    expect(dashboardView).toBeInTheDocument();
  });
});

describe('WorkspacePage export guard', () => {
  afterEach(() => {
    cleanup();
    state.permissions = { can_manage_schema: false };
    vi.mocked(apiModule.listLiveTargetDbs).mockResolvedValue([]);
  });

  it('renders the Export Playground view for a role with can_export', async () => {
    state.permissions = { can_export: true };
    vi.mocked(apiModule.listLiveTargetDbs).mockResolvedValue([
      {
        id: 1,
        display_name: 'Test DB',
        dialect: 'postgresql',
        updated_at: '',
        created_at: '',
        semantic_db_id: 1,
        table_count: 5,
      },
    ]);

    render(<WorkspacePage />);

    const exportNav = await screen.findByText('page-nav-export');
    fireEvent.click(exportNav);

    const exportView = await screen.findByTestId('export-playground-view');
    expect(exportView).toBeInTheDocument();
  });

  it('does not render the Export Playground view without can_export', async () => {
    state.permissions = { can_export: false };
    vi.mocked(apiModule.listLiveTargetDbs).mockResolvedValue([
      {
        id: 1,
        display_name: 'Test DB',
        dialect: 'postgresql',
        updated_at: '',
        created_at: '',
        semantic_db_id: 1,
        table_count: 5,
      },
    ]);

    render(<WorkspacePage />);

    const exportNav = await screen.findByText('page-nav-export');
    fireEvent.click(exportNav);

    expect(screen.queryByTestId('export-playground-view')).not.toBeInTheDocument();
  });
});
