import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

// Mock next/navigation
const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

// Mock @react-oauth/google
vi.mock('@react-oauth/google', () => ({
  GoogleLogin: ({ onSuccess, onError, ...props }: any) => (
    <button
      data-testid="google-login"
      onClick={() => onSuccess?.({ credential: 'mock-credential' })}
      {...props}
    >
      Google
    </button>
  ),
}));

// Mock useAuth
const mockLogin = vi.fn();
const mockRegister = vi.fn();
const mockLoginWithGoogle = vi.fn();
let mockToken: string | null = null;
let mockIsLoading = false;

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    token: mockToken,
    isLoading: mockIsLoading,
    login: mockLogin,
    register: mockRegister,
    loginWithGoogle: mockLoginWithGoogle,
  }),
}));

// Mock canvas for AnimatedSphere
beforeEach(() => {
  mockToken = null;
  mockIsLoading = false;
  mockPush.mockClear();
  mockReplace.mockClear();
  mockLogin.mockClear();
  mockRegister.mockClear();
  mockLoginWithGoogle.mockClear();

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
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

import { AuthForm } from './auth-form';

describe('AuthForm', () => {
  describe('Login mode', () => {
    it('renders login heading', () => {
      render(<AuthForm mode="login" />);
      expect(screen.getByRole('heading', { name: /chào mừng trở lại/i })).toBeDefined();
    });

    it('renders email and password fields', () => {
      render(<AuthForm mode="login" />);
      expect(screen.getByPlaceholderText('you@company.com')).toBeDefined();
      expect(screen.getByPlaceholderText('Nhập mật khẩu')).toBeDefined();
    });

    it('does not render name field', () => {
      render(<AuthForm mode="login" />);
      expect(screen.queryByPlaceholderText('Nguyễn Văn A')).toBeNull();
    });

    it('renders login button', () => {
      render(<AuthForm mode="login" />);
      expect(screen.getByRole('button', { name: /đăng nhập/i })).toBeDefined();
    });

    it('renders forgot password link', () => {
      render(<AuthForm mode="login" />);
      expect(screen.getByText(/quên mật khẩu/i)).toBeDefined();
    });

    it('renders register switch link', () => {
      render(<AuthForm mode="login" />);
      const link = screen.getByRole('link', { name: /tạo tài khoản mới/i });
      expect(link.getAttribute('href')).toBe('/register');
    });

    it('toggles password visibility', () => {
      render(<AuthForm mode="login" />);
      const passwordInput = screen.getByPlaceholderText('Nhập mật khẩu');
      expect(passwordInput.getAttribute('type')).toBe('password');

      const toggleButton = screen.getByLabelText('Show password');
      fireEvent.click(toggleButton);
      expect(passwordInput.getAttribute('type')).toBe('text');

      fireEvent.click(screen.getByLabelText('Hide password'));
      expect(passwordInput.getAttribute('type')).toBe('password');
    });

    it('calls login with email and password on submit', async () => {
      mockLogin.mockResolvedValue(true);
      render(<AuthForm mode="login" />);

      fireEvent.change(screen.getByPlaceholderText('you@company.com'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByPlaceholderText('Nhập mật khẩu'), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /đăng nhập/i }));

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123');
      });
    });

    it('redirects to /workspace when already authenticated', () => {
      mockToken = 'valid-jwt-token';
      mockIsLoading = false;
      render(<AuthForm mode="login" />);
      expect(screen.getByText(/đang chuyển hướng đến workspace/i)).toBeDefined();
      expect(mockReplace).toHaveBeenCalledWith('/workspace');
    });
  });

  describe('Register mode', () => {
    it('renders register heading', () => {
      render(<AuthForm mode="register" />);
      expect(screen.getByRole('heading', { name: /bắt đầu tạo tài khoản/i })).toBeDefined();
    });

    it('renders name, email, password, and confirm password fields', () => {
      render(<AuthForm mode="register" />);
      expect(screen.getByPlaceholderText('Nguyễn Văn A')).toBeDefined();
      expect(screen.getByPlaceholderText('you@company.com')).toBeDefined();
      expect(screen.getByPlaceholderText('Ít nhất 8 ký tự')).toBeDefined();
      expect(screen.getByPlaceholderText('Nhập lại mật khẩu')).toBeDefined();
    });

    it('renders register button', () => {
      render(<AuthForm mode="register" />);
      expect(screen.getByRole('button', { name: /tạo tài khoản/i })).toBeDefined();
    });

    it('does not render forgot password link', () => {
      render(<AuthForm mode="register" />);
      expect(screen.queryByText(/quên mật khẩu/i)).toBeNull();
    });

    it('renders login switch link', () => {
      render(<AuthForm mode="register" />);
      const link = screen.getByRole('link', { name: /đăng nhập/i });
      expect(link.getAttribute('href')).toBe('/login');
    });

    it('calls register with name, email, and password on submit', async () => {
      mockRegister.mockResolvedValue(true);
      render(<AuthForm mode="register" />);

      fireEvent.change(screen.getByPlaceholderText('Nguyễn Văn A'), {
        target: { value: 'Test User' },
      });
      fireEvent.change(screen.getByPlaceholderText('you@company.com'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByPlaceholderText('Ít nhất 8 ký tự'), {
        target: { value: 'password123' },
      });
      fireEvent.change(screen.getByPlaceholderText('Nhập lại mật khẩu'), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /tạo tài khoản/i }));

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith('Test User', 'test@example.com', 'password123');
      });
    });

    it('displays error when passwords do not match', async () => {
      render(<AuthForm mode="register" />);

      fireEvent.change(screen.getByPlaceholderText('Nguyễn Văn A'), {
        target: { value: 'Test User' },
      });
      fireEvent.change(screen.getByPlaceholderText('you@company.com'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByPlaceholderText('Ít nhất 8 ký tự'), {
        target: { value: 'password123' },
      });
      fireEvent.change(screen.getByPlaceholderText('Nhập lại mật khẩu'), {
        target: { value: 'different' },
      });
      fireEvent.click(screen.getByRole('button', { name: /tạo tài khoản/i }));

      await waitFor(() => {
        expect(screen.getByText(/mật khẩu xác nhận không khớp/i)).toBeDefined();
      });
    });

    it('displays error on login failure', async () => {
      mockLogin.mockRejectedValue(new Error('Login failed'));
      render(<AuthForm mode="login" />);

      fireEvent.change(screen.getByPlaceholderText('you@company.com'), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByPlaceholderText('Nhập mật khẩu'), {
        target: { value: 'wrong' },
      });
      fireEvent.click(screen.getByRole('button', { name: /đăng nhập/i }));

      await waitFor(() => {
        expect(screen.getByText(/login failed/i)).toBeDefined();
      });
    });

    it('calls loginWithGoogle on Google button click', async () => {
      mockLoginWithGoogle.mockResolvedValue(true);
      render(<AuthForm mode="login" />);

      fireEvent.click(screen.getByTestId('google-login'));

      await waitFor(() => {
        expect(mockLoginWithGoogle).toHaveBeenCalledWith('mock-credential');
      });
    });
  });
});
