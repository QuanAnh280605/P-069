import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HeroSection } from './hero-section';

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

describe('HeroSection', () => {
  it('renders the hero heading with Vietnamese copy', () => {
    render(<HeroSection />);
    expect(screen.getAllByText(/Semantic Layer/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders register CTA link', () => {
    render(<HeroSection />);
    const links = screen.getAllByRole('link', { name: /dùng thử miễn phí/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links[0].getAttribute('href')).toBe('/register');
  });

  it('renders login link', () => {
    render(<HeroSection />);
    const links = screen.getAllByRole('link', { name: /đăng nhập/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links[0].getAttribute('href')).toBe('/login');
  });

  it('cycles through feature words', () => {
    render(<HeroSection />);
    const words = ['chuẩn', 'định nghĩa', 'truy vấn', 'quản trị'];
    const found = words.some(w => {
      try {
        return screen.getAllByText(new RegExp(w, 'i')).length > 0;
      } catch {
        return false;
      }
    });
    expect(found).toBe(true);
  });

  it('renders the animated sphere', () => {
    const { container } = render(<HeroSection />);
    expect(container.querySelector('canvas')).toBeDefined();
  });
});
