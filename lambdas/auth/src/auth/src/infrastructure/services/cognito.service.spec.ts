import { calculateJwtExpiresInSeconds } from './cognito.service';

function unsignedJwt(payload: Record<string, unknown>): string {
  const encodedPayload = Buffer.from(JSON.stringify(payload)).toString(
    'base64url',
  );

  return `header.${encodedPayload}.signature`;
}

describe('calculateJwtExpiresInSeconds', () => {
  it('calculates remaining seconds from the JWT exp claim', () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-06-28T12:00:00Z'));

    const token = unsignedJwt({
      exp: Math.floor(Date.now() / 1000) + 3600,
    });

    expect(calculateJwtExpiresInSeconds(token)).toBe(3600);

    jest.useRealTimers();
  });

  it('returns zero for malformed or expired tokens', () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-06-28T12:00:00Z'));

    expect(calculateJwtExpiresInSeconds('invalid')).toBe(0);
    expect(
      calculateJwtExpiresInSeconds(
        unsignedJwt({ exp: Math.floor(Date.now() / 1000) - 1 }),
      ),
    ).toBe(0);

    jest.useRealTimers();
  });
});
