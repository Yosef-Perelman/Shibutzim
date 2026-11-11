import { describe, expect, it, vi } from 'vitest';

import { ApiClient, ApiError } from './apiClient';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function setup(response: Response | Error, token: string | null = 'token-1') {
  const fetchFn = vi.fn<typeof fetch>(async () => {
    if (response instanceof Error) throw response;
    return response;
  });
  const onUnauthorized = vi.fn();
  const client = new ApiClient({ getToken: () => token, onUnauthorized, fetchFn });
  return { client, fetchFn, onUnauthorized };
}

function lastRequest(fetchFn: ReturnType<typeof vi.fn<typeof fetch>>) {
  const [url, init] = fetchFn.mock.calls[0] ?? [];
  return { url: String(url), init: init ?? {} };
}

describe('ApiClient requests', () => {
  it('sends the bearer token when there is one', async () => {
    const { client, fetchFn } = setup(jsonResponse(200, []));
    await client.get('/api/shifts');
    const headers = new Headers(lastRequest(fetchFn).init.headers);
    expect(headers.get('Authorization')).toBe('Bearer token-1');
  });

  it('sends no Authorization header without a token', async () => {
    const { client, fetchFn } = setup(jsonResponse(200, {}), null);
    await client.get('/api/health');
    const headers = new Headers(lastRequest(fetchFn).init.headers);
    expect(headers.has('Authorization')).toBe(false);
  });

  it('sends a JSON body with its content type', async () => {
    const { client, fetchFn } = setup(jsonResponse(200, {}));
    await client.post('/api/auth/login', { email: 'a@b.c', password: 'x' });
    const { init } = lastRequest(fetchFn);
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(init.body).toBe('{"email":"a@b.c","password":"x"}');
  });

  it('builds the query string and skips undefined values', async () => {
    const { client, fetchFn } = setup(jsonResponse(200, []));
    await client.get('/api/availabilities', { week_start: '2026-11-15', user_id: undefined });
    expect(lastRequest(fetchFn).url).toBe('/api/availabilities?week_start=2026-11-15');
  });

  it('returns undefined for 204 No Content', async () => {
    const { client } = setup(new Response(null, { status: 204 }));
    await expect(client.delete('/api/schedules/2026-11-15/assignments/3')).resolves.toBeUndefined();
  });

  it('returns the parsed JSON on success', async () => {
    const { client } = setup(jsonResponse(200, { status: 'ok' }));
    await expect(client.get<{ status: string }>('/api/health')).resolves.toEqual({ status: 'ok' });
  });
});

describe('ApiClient errors', () => {
  it('turns the error shape into an ApiError with code, message and details', async () => {
    const body = {
      error: { code: 'shift_overlap', message: 'Dana already works Tue 07:00.', details: { a: 1 } },
    };
    const { client } = setup(jsonResponse(409, body));
    const error = await client.post('/api/x', {}).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: 'shift_overlap',
      message: 'Dana already works Tue 07:00.',
      details: { a: 1 },
    });
  });

  it('maps a failure that is not JSON to internal_error', async () => {
    const { client } = setup(new Response('<html>Bad gateway</html>', { status: 502 }));
    const error = await client.get('/api/x').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, code: 'internal_error' });
  });

  it('maps an unreachable server to network_error with status 0', async () => {
    const { client } = setup(new TypeError('Failed to fetch'));
    const error = await client.get('/api/x').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, code: 'network_error' });
  });

  it('calls onUnauthorized on 401 when a token was sent, and still throws', async () => {
    const body = { error: { code: 'token_expired', message: 'Your session expired.' } };
    const { client, onUnauthorized } = setup(jsonResponse(401, body));
    await expect(client.get('/api/auth/me')).rejects.toMatchObject({ code: 'token_expired' });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not call onUnauthorized for a 401 without a token (wrong password)', async () => {
    const body = { error: { code: 'invalid_credentials', message: 'Wrong email or password.' } };
    const { client, onUnauthorized } = setup(jsonResponse(401, body), null);
    await expect(client.post('/api/auth/login', {})).rejects.toMatchObject({
      code: 'invalid_credentials',
    });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
