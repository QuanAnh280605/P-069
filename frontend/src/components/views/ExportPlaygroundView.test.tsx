import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api', () => ({
  exportSemanticLayerApi: vi.fn(),
}));

import { ExportPlaygroundView } from '@/components/views/ExportPlaygroundView';
import { exportSemanticLayerApi } from '@/lib/api';

const mockExportApi = vi.mocked(exportSemanticLayerApi);

describe('ExportPlaygroundView', () => {
  beforeEach(() => {
    mockExportApi.mockReset();
  });
  afterEach(() => cleanup());

  it('renders reference Export layout with header and format toggle pill buttons', async () => {
    mockExportApi.mockResolvedValue('version: 1\nsemantic_layer:\n  metrics: []');
    render(<ExportPlaygroundView dbId={3} />);

    // Header with title and description
    expect(screen.getByText('Export Playground')).toBeInTheDocument();
    expect(screen.getByText(/BI tools and semantic engines/i)).toBeInTheDocument();

    // Eyebrow text
    expect(screen.getByText('Publish')).toBeInTheDocument();

    // Action buttons
    expect(screen.getByRole('button', { name: /Copy/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Tải file/i })).toBeInTheDocument();

    // Format toggle as pill buttons (visible after content loads)
    await waitFor(() => {
      expect(screen.queryByText(/Đang tải/i)).not.toBeInTheDocument();
    });
    expect(screen.getAllByRole('button', { name: /YAML/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /JSON/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('fetches content from API and displays it', async () => {
    mockExportApi.mockResolvedValue('version: 1\nmetrics: []');
    render(<ExportPlaygroundView dbId={3} />);

    await waitFor(() => {
      expect(screen.getByText(/version: 1/)).toBeInTheDocument();
    });
    expect(mockExportApi).toHaveBeenCalledWith('3', 'yaml');
  });

  it('toggles format between YAML and JSON via pill buttons', async () => {
    mockExportApi.mockResolvedValueOnce('yaml-content').mockResolvedValueOnce('json-content');
    render(<ExportPlaygroundView dbId={3} />);

    await waitFor(() => {
      expect(screen.getByText(/yaml-content/)).toBeInTheDocument();
    });

    const jsonButtons = screen.getAllByRole('button', { name: /JSON/i });
    fireEvent.click(jsonButtons[jsonButtons.length - 1]);

    await waitFor(() => {
      expect(mockExportApi).toHaveBeenCalledWith('3', 'json');
    });
  });

  it('shows loading indicator while fetching', () => {
    mockExportApi.mockReturnValue(new Promise(() => {})); // Never resolves
    render(<ExportPlaygroundView dbId={3} />);

    expect(screen.getByText(/Đang tải export/i)).toBeInTheDocument();
  });

  it('shows error when API fails', async () => {
    mockExportApi.mockRejectedValue(new Error('Connection failed'));
    render(<ExportPlaygroundView dbId={3} />);

    await waitFor(() => {
      expect(screen.getByText(/Connection failed/i)).toBeInTheDocument();
    });
  });

  it('does not fetch when no dbId provided', () => {
    mockExportApi.mockClear();
    render(<ExportPlaygroundView dbId={null} />);
    expect(mockExportApi).not.toHaveBeenCalled();
  });
});
