import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock canvas for AnimatedSphere/Tetrahedron/Wave used in child components
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
  // Mock IntersectionObserver
  class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

import LandingPage from './page';

describe('Landing Page', () => {
  it('renders the landing page with navigation', () => {
    render(<LandingPage />);
    const navs = screen.getAllByRole('navigation');
    expect(navs.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Vietnamese hero heading', () => {
    render(<LandingPage />);
    expect(screen.getAllByText(/Semantic Layer/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders CTA buttons linking to register and login', () => {
    render(<LandingPage />);
    const registerLinks = screen.getAllByRole('link', { name: /dùng thử miễn phí/i });
    expect(registerLinks.length).toBeGreaterThanOrEqual(1);
    expect(registerLinks[0].getAttribute('href')).toBe('/register');
    const loginLinks = screen.getAllByRole('link', { name: /đăng nhập/i });
    expect(loginLinks.length).toBeGreaterThanOrEqual(1);
    expect(loginLinks[0].getAttribute('href')).toBe('/login');
  });

  it('renders all major sections by id', () => {
    const { container } = render(<LandingPage />);
    expect(container.querySelector('#features')).toBeDefined();
    expect(container.querySelector('#how-it-works')).toBeDefined();
    expect(container.querySelector('#integrations')).toBeDefined();
    expect(container.querySelector('#security')).toBeDefined();
    expect(container.querySelector('#pricing')).toBeDefined();
  });

  it('renders footer with brand name', () => {
    render(<LandingPage />);
    expect(screen.getAllByText(/AI Semantic Layer/i).length).toBeGreaterThanOrEqual(1);
  });
});
