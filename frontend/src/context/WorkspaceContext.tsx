'use client';

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { useAuth } from '@/context/AuthContext';
import { listWorkspacesApi, WorkspaceRole, WorkspaceSummary } from '@/lib/api';

interface WorkspaceContextValue {
  workspaces: WorkspaceSummary[];
  currentWorkspace: WorkspaceSummary | null;
  role: WorkspaceRole | null;
  permissions: Record<string, boolean>;
  isLoading: boolean;
  switchWorkspace: (id: number) => void;
  reloadWorkspaces: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const reloadWorkspaces = async () => {
    if (!token) {
      setWorkspaces([]);
      return;
    }
    setIsLoading(true);
    try {
      const items = await listWorkspacesApi();
      setWorkspaces(items);
      const stored = Number(window.localStorage.getItem('current_organization_id'));
      const selected = items.some((item) => item.id === stored) ? stored : items[0]?.id;
      if (selected) {
        setCurrentId(selected);
        window.localStorage.setItem('current_organization_id', String(selected));
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void reloadWorkspaces();
  }, [token]);

  const switchWorkspace = (id: number) => {
    setCurrentId(id);
    window.localStorage.setItem('current_organization_id', String(id));
  };

  const currentWorkspace = useMemo(
    () => workspaces.find((item) => item.id === currentId) || null,
    [currentId, workspaces],
  );

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        currentWorkspace,
        role: currentWorkspace?.role || null,
        permissions: currentWorkspace?.permissions || {},
        isLoading,
        switchWorkspace,
        reloadWorkspaces,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used within a WorkspaceProvider');
  return context;
}
