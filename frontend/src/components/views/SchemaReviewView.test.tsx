import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as apiModule from '@/lib/api';
import { type SchemaReview, type SchemaReviewRelationship } from '@/lib/api';
import { SchemaReviewView } from '@/components/views/SchemaReviewView';

function makeRelationship(overrides: Partial<SchemaReviewRelationship> = {}): SchemaReviewRelationship {
  return {
    relationship_id: 9,
    from_entity_id: 1,
    to_entity_id: 2,
    from_table_name: 'orders',
    to_table_name: 'customers',
    column_pairs: [{ from_column_id: 1, to_column_id: 2, from_column_name: 'id', to_column_name: 'id' }],
    business_name: 'Đơn thuộc khách',
    description: 'desc',
    ai_business_name: null,
    ai_description: null,
    validation_status: 'valid',
    review_status: 'pending_review',
    ambiguous_target_groups: [],
    ...overrides,
  };
}

function makeReview(overrides: Partial<SchemaReview> = {}): SchemaReview {
  return {
    db_id: 5,
    status: 'pending_review',
    pending_tables: 0,
    pending_columns: 0,
    pending_relationships: 1,
    tables: [],
    relationships: [makeRelationship()],
    ...overrides,
  };
}

describe('SchemaReviewView relationships', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    vi.spyOn(apiModule, 'getSchemaReviewApi').mockResolvedValue(makeReview());
    vi.spyOn(apiModule, 'updateRelationshipReviewApi').mockResolvedValue(makeRelationship());
    vi.spyOn(apiModule, 'approveSchemaReviewApi').mockResolvedValue({
      db_id: 5,
      approved_tables: 0,
      approved_columns: 0,
      approved_relationships: 1,
      pending_tables: 0,
      pending_columns: 0,
      pending_relationships: 0,
      status: 'approved',
    });
    vi.spyOn(apiModule, 'updateTableReviewApi').mockResolvedValue({ message: 'ok', review_status: 'pending_review' });
    vi.spyOn(apiModule, 'updateColumnReviewApi').mockResolvedValue({ message: 'ok', review_status: 'pending_review' });
  });

  it('renders relationships and counts them in the approve-all total', async () => {
    render(<SchemaReviewView dbId={5} canManageSchema canApproveSchema />);

    await waitFor(() => expect(screen.getByText('orders.id → customers.id')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Duyệt toàn bộ \(1\)/i })).toBeInTheDocument();
  });

  it('counts a relationship draft in the unsaved-changes banner', async () => {
    render(<SchemaReviewView dbId={5} canManageSchema canApproveSchema />);

    await waitFor(() => expect(screen.getByLabelText('Tên nghiệp vụ')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Tên nghiệp vụ'), { target: { value: 'Quan hệ đơn khách' } });

    expect(screen.getByText(/1 chỉnh sửa chưa được lưu/i)).toBeInTheDocument();
  });

  it('saves a relationship edit via the relationship API', async () => {
    render(<SchemaReviewView dbId={5} canManageSchema canApproveSchema />);

    await waitFor(() => expect(screen.getByLabelText('Tên nghiệp vụ')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Tên nghiệp vụ'), { target: { value: 'Quan hệ đơn khách' } });
    fireEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(() => {
      expect(apiModule.updateRelationshipReviewApi).toHaveBeenCalledWith('5', 9, 'Quan hệ đơn khách', 'desc');
    });
  });

  it('approves a single relationship with relationship_ids', async () => {
    render(<SchemaReviewView dbId={5} canManageSchema canApproveSchema />);

    await waitFor(() => expect(screen.getByRole('button', { name: /Duyệt quan hệ này/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Duyệt quan hệ này/i }));

    await waitFor(() => {
      expect(apiModule.approveSchemaReviewApi).toHaveBeenCalledWith('5', undefined, [9]);
    });
  });

  it('hides edit and approve controls without schema permissions', async () => {
    render(<SchemaReviewView dbId={5} canManageSchema={false} canApproveSchema={false} />);

    await waitFor(() => expect(screen.getByLabelText('Tên nghiệp vụ')).toBeInTheDocument());
    expect(screen.getByLabelText('Tên nghiệp vụ')).toBeDisabled();
    expect(screen.getByRole('button', { name: /Duyệt quan hệ này/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Duyệt toàn bộ/i })).toBeDisabled();
  });

  it('surfaces a load API error with an aria-live status region', async () => {
    vi.spyOn(apiModule, 'getSchemaReviewApi').mockRejectedValue(new apiModule.SemanticApiError(500, 'Lỗi tải'));
    render(<SchemaReviewView dbId={5} canManageSchema canApproveSchema />);

    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent('Lỗi tải');
  });
});
