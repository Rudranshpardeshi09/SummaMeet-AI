const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem('auth_token');
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'API Request Failed');
  }

  // Handle 204 No Content
  if (res.status === 204) return null;
  
  return res.json();
}
