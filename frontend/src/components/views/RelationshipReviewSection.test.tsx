import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';

import * as apiModule from '@/lib/api';
import { type SchemaReviewRelationship } from '@/lib/api';
import {
  RelationshipReviewSection,
  relationshipKey,
  type Draft,
  type DraftMap,
} from '@/components/views/RelationshipReviewSection';

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

const saveRowSpy = vi.fn();
const saveErrorSpy = vi.fn();
const approveSpy = vi.fn();

function Harness({
  relationships,
  canManageSchema = true,
  canApproveSchema = true,
  dirtyKey,
  approving = null,
}: {
  relationships: SchemaReviewRelationship[];
  canManageSchema?: boolean;
  canApproveSchema?: boolean;
  dirtyKey?: string;
  approving?: string | null;
}) {
  const [drafts, setDrafts] = useState<DraftMap>(() =>
    Object.fromEntries(
      relationships.map((rel) => [
        relationshipKey(rel),
        { business_name: rel.business_name, description: rel.description ?? '' },
      ]),
    ),
  );
  const patch = (key: string, value: Partial<Draft>) =>
    setDrafts((current) => ({ ...current, [key]: { ...current[key], ...value } }));
  const isDirty = (key: string) => (dirtyKey ? key === dirtyKey : false);
  const saveRow = async (key: string, save: (draft: Draft) => Promise<unknown>) => {
    saveRowSpy(key);
    try {
      await save(drafts[key]);
    } catch (caught) {
      saveErrorSpy(caught);
    }
  };
  return (
    <RelationshipReviewSection
      dbId={5}
      relationships={relationships}
      drafts={drafts}
      isDirty={isDirty}
      patch={patch}
      savingKey={null}
      saveRow={saveRow}
      approving={approving}
      canManageSchema={canManageSchema}
      canApproveSchema={canApproveSchema}
      onApproveRelationship={approveSpy}
    />
  );
}

describe('RelationshipReviewSection', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    saveRowSpy.mockClear();
    saveErrorSpy.mockClear();
    approveSpy.mockClear();
  });

  beforeEach(() => {
    vi.spyOn(apiModule, 'updateRelationshipReviewApi').mockResolvedValue(
      makeRelationship({ review_status: 'pending_review' }),
    );
  });

  it('renders physical path, business label, validity and review badges', () => {
    render(<Harness relationships={[makeRelationship()]} />);

    expect(screen.getByText('orders.id → customers.id')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Đơn thuộc khách')).toBeInTheDocument();
    expect(screen.getByText('Chờ review')).toBeInTheDocument();
    expect(screen.getByText('Hợp lệ (kỹ thuật)')).toBeInTheDocument();
  });

  it('edits and saves a relationship, keeping it pending', async () => {
    render(<Harness relationships={[makeRelationship()]} dirtyKey="r:9" />);

    const input = screen.getByLabelText('Tên nghiệp vụ');
    fireEvent.change(input, { target: { value: 'Quan hệ đơn khách' } });

    fireEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(() => {
      expect(apiModule.updateRelationshipReviewApi).toHaveBeenCalledWith('5', 9, 'Quan hệ đơn khách', 'desc');
    });
    expect(saveRowSpy).toHaveBeenCalledWith('r:9');
  });

  it('approves a relationship via the explicit approve control', () => {
    render(<Harness relationships={[makeRelationship()]} />);

    fireEvent.click(screen.getByRole('button', { name: /Duyệt quan hệ này/i }));

    expect(approveSpy).toHaveBeenCalledWith(9);
  });

  it('shows an ambiguity warning with an aria-live status region', () => {
    const rel = makeRelationship({
      ambiguous_target_groups: [
        { target_entity_id: 2, candidate_relationship_ids: [[1, 2], [3, 4]] },
      ],
    });
    render(<Harness relationships={[rel]} />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent(/nhóm đường join không rõ ràng/i);
    expect(status).toHaveTextContent(/Bảng đích #2/i);
  });

  it('disables approval for technically invalid relationships', () => {
    render(<Harness relationships={[makeRelationship({ validation_status: 'invalid' })]} />);

    expect(screen.getByText('Không hợp lệ (kỹ thuật)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Duyệt quan hệ này/i })).toBeDisabled();
  });

  it('hides edit and approve controls without schema permissions', () => {
    render(<Harness relationships={[makeRelationship()]} canManageSchema={false} canApproveSchema={false} />);

    expect(screen.getByLabelText('Tên nghiệp vụ')).toBeDisabled();
    expect(screen.getByRole('button', { name: /Duyệt quan hệ này/i })).toBeDisabled();
  });

  it('surfaces a relationship save API error to the parent via saveRow rejection', async () => {
    vi.spyOn(apiModule, 'updateRelationshipReviewApi').mockRejectedValue(
      new apiModule.SemanticApiError(500, 'Lỗi máy chủ'),
    );
    render(<Harness relationships={[makeRelationship()]} dirtyKey="r:9" />);

    fireEvent.change(screen.getByLabelText('Tên nghiệp vụ'), { target: { value: 'X' } });
    fireEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(() => {
      expect(apiModule.updateRelationshipReviewApi).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(saveErrorSpy).toHaveBeenCalled();
    });
  });
});
