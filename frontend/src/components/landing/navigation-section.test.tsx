import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NavigationSection } from './navigation-section';

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('NavigationSection', () => {
  it('renders the brand name', () => {
    render(<NavigationSection />);
    expect(screen.getByText('SemanticLayer')).toBeDefined();
  });

  it('renders navigation links with Vietnamese labels', () => {
    render(<NavigationSection />);
    const featureLinks = screen.getAllByText(/tính năng/i);
    expect(featureLinks.length).toBeGreaterThanOrEqual(1);
    const howItWorksLinks = screen.getAllByText(/cách hoạt động/i);
    expect(howItWorksLinks.length).toBeGreaterThanOrEqual(1);
    const securityLinks = screen.getAllByText(/bảo mật/i);
    expect(securityLinks.length).toBeGreaterThanOrEqual(1);
    const betaLinks = screen.getAllByText(/beta/i);
    expect(betaLinks.length).toBeGreaterThanOrEqual(1);
  });

  it('renders login and register links', () => {
    render(<NavigationSection />);
    const loginLinks = screen.getAllByRole('link', { name: /đăng nhập/i });
    expect(loginLinks.length).toBeGreaterThanOrEqual(1);
    expect(loginLinks[0].getAttribute('href')).toBe('/login');
    const registerLinks = screen.getAllByRole('link', { name: /dùng thử miễn phí/i });
    expect(registerLinks.length).toBeGreaterThanOrEqual(1);
    expect(registerLinks[0].getAttribute('href')).toBe('/register');
  });

  it('toggles mobile menu', () => {
    render(<NavigationSection />);
    const menuButtons = screen.getAllByRole('button', { name: /toggle menu/i });
    expect(menuButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(menuButtons[0]);
    const featureLinks = screen.getAllByText(/tính năng/i);
    expect(featureLinks.length).toBeGreaterThan(1);
  });
});
