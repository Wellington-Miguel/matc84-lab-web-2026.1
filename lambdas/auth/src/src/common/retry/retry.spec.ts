import { retryWithFullJitter } from './retry';

describe('retryWithFullJitter', () => {
  it('retries transient failures using exponential full jitter', async () => {
    const operation = jest
      .fn<Promise<string>, []>()
      .mockRejectedValueOnce(new Error('temporary'))
      .mockRejectedValueOnce(new Error('temporary'))
      .mockResolvedValue('ok');
    const sleep = jest.fn<Promise<void>, [number]>().mockResolvedValue();

    await expect(
      retryWithFullJitter(operation, {
        maxAttempts: 3,
        baseDelayMs: 100,
        maxDelayMs: 1000,
        isRetryable: () => true,
        random: () => 0.5,
        sleep,
      }),
    ).resolves.toBe('ok');

    expect(operation).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenNthCalledWith(1, 50);
    expect(sleep).toHaveBeenNthCalledWith(2, 100);
  });

  it('does not retry permanent failures', async () => {
    const operation = jest.fn().mockRejectedValue(new Error('permanent'));
    const sleep = jest.fn();

    await expect(
      retryWithFullJitter(operation, {
        maxAttempts: 3,
        baseDelayMs: 100,
        maxDelayMs: 1000,
        isRetryable: () => false,
        sleep,
      }),
    ).rejects.toMatchObject({ attempts: 1 });

    expect(operation).toHaveBeenCalledTimes(1);
    expect(sleep).not.toHaveBeenCalled();
  });
});
