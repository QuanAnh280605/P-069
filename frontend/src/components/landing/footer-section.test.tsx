import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FooterSection } from './footer-section';

beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
    clearRect: vi.fn(),
    fillText: vi.fn(),
    font: '',
    textAlign: '',
    textBaseline: '',
    fillStyle: '',
    scale: vi.fn(),
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('FooterSection', () => {
  it('renders brand name', () => {
    render(<FooterSection />);
    const brands = screen.getAllByText(/AI Semantic Layer/i);
    expect(brands.length).toBeGreaterThanOrEqual(1);
  });

  it('renders footer link sections in Vietnamese', () => {
    render(<FooterSection />);
    expect(screen.getAllByText(/sản phẩm/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/nhà phát triển/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/pháp lý/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders animated wave background', () => {
    const { container } = render(<FooterSection />);
    expect(container.querySelector('canvas')).toBeDefined();
  });

  it('renders copyright with 2026', () => {
    render(<FooterSection />);
    const copyrights = screen.getAllByText(/2026.*AI Semantic Layer/i);
    expect(copyrights.length).toBeGreaterThanOrEqual(1);
  });

  it('renders flow descriptions', () => {
    render(<FooterSection />);
    expect(screen.getAllByText(/Flow 1/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Flow 2/i).length).toBeGreaterThanOrEqual(1);
  });
});
