const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('postforge_token');
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function login(email: string, password: string) {
  return apiFetch('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, password: string, name: string) {
  return apiFetch('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
}

export async function getMe() {
  return apiFetch('/api/v1/users/me');
}

export async function generateContent(topic: string, platforms: string[], tone: string) {
  return apiFetch('/api/v1/posts/generate', {
    method: 'POST',
    body: JSON.stringify({ topic, platforms, tone }),
  });
}

export async function getPosts() {
  return apiFetch('/api/v1/posts/');
}

export async function deletePost(id: string) {
  return apiFetch(`/api/v1/posts/${id}`, { method: 'DELETE' });
}

export async function getPlatforms() {
  return apiFetch('/api/v1/platforms/');
}

export async function connectPlatform(platform: string) {
  return apiFetch(`/api/v1/platforms/connect/${platform}`, { method: 'POST' });
}

export async function getSubscription() {
  return apiFetch('/api/v1/billing/subscription');
}
