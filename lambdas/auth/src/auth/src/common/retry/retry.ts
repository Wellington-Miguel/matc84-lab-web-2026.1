export interface RetryOptions {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  isRetryable: (error: unknown) => boolean;
  sleep?: (delayMs: number) => Promise<void>;
  random?: () => number;
}

export class RetryExhaustedError extends Error {
  constructor(
    public readonly cause: unknown,
    public readonly attempts: number,
  ) {
    super(`Operation failed after ${attempts} attempts`);
  }
}

export async function retryWithFullJitter<T>(
  operation: () => Promise<T>,
  options: RetryOptions,
): Promise<T> {
  const sleep =
    options.sleep ??
    ((delayMs: number) =>
      new Promise<void>((resolve) => setTimeout(resolve, delayMs)));
  const random = options.random ?? Math.random;

  for (let attempt = 1; attempt <= options.maxAttempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      const shouldRetry =
        attempt < options.maxAttempts && options.isRetryable(error);

      if (!shouldRetry) {
        throw new RetryExhaustedError(error, attempt);
      }

      const exponentialCap = Math.min(
        options.maxDelayMs,
        options.baseDelayMs * 2 ** (attempt - 1),
      );
      await sleep(Math.floor(random() * exponentialCap));
    }
  }

  throw new Error('Unreachable retry state');
}
