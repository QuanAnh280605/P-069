import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import WorkspacePage from './page';

const state = vi.hoisted(() => ({
  permissions: { can_manage_schema: false } as Record<string, boolean>,
}));

vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock('next/dynamic', () => ({
  default: () => (props: { isOpen?: boolean }) =>
    props.isOpen ? <div data-testid="dynamic-modal" /> : null,
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
vi.mock('@/components/views/MetricsCatalogView', () => ({ MetricsCatalogView: () => null }));
vi.mock('@/components/workspace/WorkspaceApp', () => ({
  WorkspaceApp: (props: {
    onConnectDatabase?: () => void;
    onRemoveDatabase?: (id: string) => void;
    children: React.ReactNode;
  }) => (
    <div>
      {props.onConnectDatabase && <button onClick={props.onConnectDatabase}>page-connect</button>}
      {props.onRemoveDatabase && <button onClick={() => props.onRemoveDatabase?.('1')}>page-delete</button>}
      {props.children}
    </div>
  ),
}));
vi.mock('@/lib/api', () => ({
  approveMetricsApi: vi.fn(),
  approveSingleMetricApi: vi.fn(),
  convertRawSchemaToLayer: vi.fn(),
  createMetricApi: vi.fn(),
  deleteChatSessionApi: vi.fn(),
  deleteDatabaseApi: vi.fn(),
  deleteLayer: vi.fn(),
  deleteMetricApi: vi.fn(),
  getImportedSchema: vi.fn(),
  getLiveTargetDb: vi.fn(),
  getSemanticCatalogApi: vi.fn(),
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
    expect(screen.getByTestId('dynamic-modal')).toBeInTheDocument();
    expect(screen.getByText('page-delete')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Thêm kết nối Database' })).toBeInTheDocument();
  });
});
