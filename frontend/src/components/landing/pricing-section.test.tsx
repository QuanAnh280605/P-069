import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PricingSection } from './pricing-section';

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('PricingSection', () => {
  it('renders beta heading', () => {
    render(<PricingSection />);
    const headings = screen.getAllByText(/beta/i);
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it('renders free pricing with 0₫', () => {
    render(<PricingSection />);
    const prices = screen.getAllByText(/0₫/);
    expect(prices.length).toBeGreaterThanOrEqual(1);
  });

  it('renders beta features list', () => {
    render(<PricingSection />);
    expect(screen.getAllByText(/PostgreSQL/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Fernet/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/SELECT-only/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders CTA button', () => {
    render(<PricingSection />);
    const startFreeButtons = screen.getAllByText(/bắt đầu miễn phí/i);
    expect(startFreeButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('does not render monthly/annual toggle', () => {
    render(<PricingSection />);
    // The old pricing had a standalone "Tháng" label for the toggle.
    // The new pricing only has "/tháng" as a price suffix.
    const standaloneMonth = screen.queryByText(/^tháng$/i);
    expect(standaloneMonth).toBeNull();
    const standaloneYear = screen.queryByText(/^năm$/i);
    expect(standaloneYear).toBeNull();
  });

  it('does not render fake enterprise tier', () => {
    render(<PricingSection />);
    expect(screen.queryByText(/doanh nghiệp/i)).toBeNull();
    expect(screen.queryByText(/chuyên nghiệp/i)).toBeNull();
  });
});
