// The only place that calls fetch. Components and stores go through this client (ui-rules).

export type QueryValue = string | number | boolean | null | undefined;
export type Query = Record<string, QueryValue>;

export const NETWORK_ERROR_MESSAGE =
  'Could not reach the server. Check your connection and try again.';
export const INTERNAL_ERROR_MESSAGE = 'Something went wrong on our side.';

/** The one error shape of the server: `{ "error": { code, message, details? } }`. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface ApiClientOptions {
  /** Empty in development: the Vite dev server proxies /api (plan 003, open question 6). */
  baseUrl?: string;
  getToken: () => string | null;
  /** Called when the server rejects a token the client sent (expired or invalid). */
  onUnauthorized: () => void;
  fetchFn?: typeof fetch;
}

interface RequestOptions {
  query?: Query;
  body?: unknown;
}

interface ErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isErrorBody(value: unknown): value is ErrorBody {
  if (!isRecord(value) || !isRecord(value.error)) return false;
  return typeof value.error.code === 'string' && typeof value.error.message === 'string';
}

function queryString(query: Query | undefined): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getToken: () => string | null;
  private readonly onUnauthorized: () => void;
  private readonly fetchFn: typeof fetch;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl ?? import.meta.env.VITE_API_URL ?? '';
    this.getToken = options.getToken;
    this.onUnauthorized = options.onUnauthorized;
    this.fetchFn = options.fetchFn ?? ((input, init) => fetch(input, init));
  }

  get<T>(path: string, query?: Query): Promise<T> {
    return this.request<T>('GET', path, { query });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, { body });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('PUT', path, { body });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('PATCH', path, { body });
  }

  delete<T = void>(path: string): Promise<T> {
    return this.request<T>('DELETE', path, {});
  }

  private async request<T>(method: string, path: string, options: RequestOptions): Promise<T> {
    const token = this.getToken();
    const headers = new Headers({ Accept: 'application/json' });
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const hasBody = options.body !== undefined;
    if (hasBody) headers.set('Content-Type', 'application/json');

    let response: Response;
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}${queryString(options.query)}`, {
        method,
        headers,
        body: hasBody ? JSON.stringify(options.body) : undefined,
      });
    } catch {
      throw new ApiError(0, 'network_error', NETWORK_ERROR_MESSAGE);
    }

    if (response.ok) {
      if (response.status === 204) return undefined as T;
      return (await response.json()) as T;
    }

    // A 401 on a request that carried a token means the session is over; a 401 without one is
    // just a wrong password and must not log anybody out.
    if (response.status === 401 && token) this.onUnauthorized();
    throw await toApiError(response);
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (isErrorBody(body)) {
      const { code, message, details } = body.error;
      return new ApiError(response.status, code, message, details);
    }
  } catch {
    // The body was not JSON (a proxy error page, for example): fall through.
  }
  return new ApiError(response.status, 'internal_error', INTERNAL_ERROR_MESSAGE);
}
