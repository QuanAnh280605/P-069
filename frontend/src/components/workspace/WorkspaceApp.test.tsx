import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceApp } from '@/components/workspace/WorkspaceApp';
import type { WorkspaceDatabase, ViewId } from '@/components/workspace/shared';

describe('WorkspaceApp', () => {
  afterEach(() => cleanup());
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
    activeDbId: 'db-1' as string | null,
    view: 'catalog' as ViewId,
    theme: 'light' as const,
    pendingCount: 3,
    collapsed: false,
    onSelectView: vi.fn(),
    onToggleCollapse: vi.fn(),
    onToggleTheme: vi.fn(),
    onSelectDatabase: vi.fn(),
    onRemoveDatabase: vi.fn(),
    onConnectDatabase: vi.fn(),
    onOpenSettings: vi.fn(),
    children: <div data-testid="main-content">Main Content</div>,
  };

  it('renders the workspace landmark with sidebar/main layout', () => {
    render(<WorkspaceApp {...defaultProps} />);

    const workspace = screen.getByRole('region', { name: /workspace/i });
    expect(workspace).toBeInTheDocument();
    expect(workspace).toHaveClass('flex', 'h-screen');

    expect(screen.getByRole('complementary')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('renders the selected view element with active state', () => {
    render(<WorkspaceApp {...defaultProps} view="catalog" />);

    const catalogButton = screen.getByRole('button', { name: /metrics catalog/i });
    expect(catalogButton).toHaveAttribute('aria-current', 'page');
  });

  it('renders the active database in sidebar data sources', () => {
    render(<WorkspaceApp {...defaultProps} />);

    expect(screen.getByText('Production DB')).toBeInTheDocument();
  });

  it('applies dark class to root when theme is dark', () => {
    render(<WorkspaceApp {...defaultProps} theme="dark" />);

    const workspace = screen.getByRole('region', { name: /workspace/i });
    expect(workspace).toHaveClass('dark');
  });

  it('does not apply dark class when theme is light', () => {
    render(<WorkspaceApp {...defaultProps} theme="light" />);

    const workspace = screen.getByRole('region', { name: /workspace/i });
    expect(workspace).not.toHaveClass('dark');
  });

  it('renders main children', () => {
    render(<WorkspaceApp {...defaultProps} />);

    expect(screen.getByTestId('main-content')).toBeInTheDocument();
  });
});

describe('WorkspaceApp route composition', () => {
  afterEach(() => cleanup());

  const databases: WorkspaceDatabase[] = [
    {
      id: 'prod-pg',
      name: 'Production Postgres',
      engine: 'postgresql',
      status: 'connected',
      tables: 42,
    },
    {
      id: 'analytics-sqlite',
      name: 'Analytics SQLite',
      engine: 'sqlite',
      status: 'idle',
      tables: 8,
    },
  ];

  const allViews: ViewId[] = ['ai-studio', 'catalog', 'explorer', 'export'];

  function buildProps(overrides: Partial<Parameters<typeof WorkspaceApp>[0]> = {}) {
    return {
      databases,
      activeDbId: 'prod-pg' as string | null,
      view: 'ai-studio' as ViewId,
      theme: 'light' as const,
      pendingCount: 0,
      collapsed: false,
      onSelectView: vi.fn(),
      onToggleCollapse: vi.fn(),
      onToggleTheme: vi.fn(),
      onSelectDatabase: vi.fn(),
      onRemoveDatabase: vi.fn(),
      onConnectDatabase: vi.fn(),
      onOpenSettings: vi.fn(),
      children: <div data-testid="view-content">Studio content</div>,
      ...overrides,
    };
  }

  it('marks exactly one sidebar nav button as active for each view', () => {
    for (const view of allViews) {
      const { unmount } = render(<WorkspaceApp {...buildProps({ view })} />);
      const nav = screen.getByRole('navigation');
      const buttons = within(nav).getAllByRole('button');

      const activeButtons = buttons.filter(
        (btn) => btn.getAttribute('aria-current') === 'page',
      );
      expect(activeButtons).toHaveLength(1);

      unmount();
    }
  });

  it('switches active sidebar nav when view prop changes from ai-studio to export', () => {
    const onSelectView = vi.fn();
    const { rerender } = render(
      <WorkspaceApp {...buildProps({ view: 'ai-studio', onSelectView })} />,
    );

    const nav = screen.getByRole('navigation');
    const studioBtn = within(nav).getByRole('button', { name: 'AI Studio' });
    expect(studioBtn).toHaveAttribute('aria-current', 'page');

    rerender(<WorkspaceApp {...buildProps({ view: 'export', onSelectView })} />);

    const exportBtn = within(nav).getByRole('button', { name: 'Export Playground' });
    expect(exportBtn).toHaveAttribute('aria-current', 'page');
    expect(studioBtn).not.toHaveAttribute('aria-current');
  });

  it('retains database selection when switching views', () => {
    const onSelectView = vi.fn();
    const onSelectDatabase = vi.fn();

    const { rerender } = render(
      <WorkspaceApp
        {...buildProps({
          view: 'ai-studio',
          activeDbId: 'prod-pg',
          onSelectView,
          onSelectDatabase,
        })}
      />,
    );

    expect(screen.getByText('Production Postgres')).toBeInTheDocument();
    const prodCard = screen.getByText('Production Postgres').closest('[data-active]');
    expect(prodCard).toHaveAttribute('data-active', 'true');

    rerender(
      <WorkspaceApp
        {...buildProps({
          view: 'explorer',
          activeDbId: 'prod-pg',
          onSelectView,
          onSelectDatabase,
        })}
      />,
    );

    const prodCardAfter = screen.getByText('Production Postgres').closest('[data-active]');
    expect(prodCardAfter).toHaveAttribute('data-active', 'true');
    expect(onSelectDatabase).not.toHaveBeenCalled();
  });

  it('calls onSelectView with the correct view id when each nav button is clicked', () => {
    const onSelectView = vi.fn();
    render(<WorkspaceApp {...buildProps({ onSelectView })} />);

    const nav = screen.getByRole('navigation');
    const buttons = within(nav).getAllByRole('button');

    fireEvent.click(buttons[0]);
    expect(onSelectView).toHaveBeenLastCalledWith('ai-studio');

    fireEvent.click(buttons[1]);
    expect(onSelectView).toHaveBeenLastCalledWith('catalog');

    fireEvent.click(buttons[2]);
    expect(onSelectView).toHaveBeenLastCalledWith('explorer');

    fireEvent.click(buttons[3]);
    expect(onSelectView).toHaveBeenLastCalledWith('export');

    expect(onSelectView).toHaveBeenCalledTimes(4);
  });

  it('renders only the provided children content for the active view', () => {
    const { rerender } = render(
      <WorkspaceApp {...buildProps({ view: 'ai-studio' })}>
        <div data-testid="studio-view">AI Studio View</div>
      </WorkspaceApp>,
    );
    expect(screen.getByTestId('studio-view')).toBeInTheDocument();
    expect(screen.queryByText('Export Playground View')).not.toBeInTheDocument();

    rerender(
      <WorkspaceApp {...buildProps({ view: 'export' })}>
        <div data-testid="export-view">Export Playground View</div>
      </WorkspaceApp>,
    );
    expect(screen.getByTestId('export-view')).toBeInTheDocument();
    expect(screen.queryByText('AI Studio View')).not.toBeInTheDocument();
  });
});
