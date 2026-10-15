import { setTimeout as delay } from 'node:timers/promises';

// All official Provider.infer calls pass here, including Host's background title requests.
// The official adapter is told not to retry internally; each admitted attempt is reserved first.
export function boundedProvider(provider, config, onUsage = () => {}) {
  let requests = 0, tokens = 0, unreported = 0;
  let nextAllowedAt = 0;
  const deadline = config.deadlineMs ?? Date.now() + config.wallMs;
  const requestTimeoutMs = config.requestTimeoutMs ?? Math.min(90_000, config.wallMs);
  if (!Number.isSafeInteger(requestTimeoutMs) || requestTimeoutMs <= 0
      || requestTimeoutMs > config.wallMs) throw Error('INVALID_REQUEST_TIMEOUT');
  const failure = (code, started, extra = {}) => onUsage({ ...usage(), failure: {
    code, elapsed_ms: Date.now() - started, ...extra } });
  const usage = () => ({ model_requests: requests, model_tokens: unreported === 0 ? tokens : null,
    observed_model_tokens: tokens, model_usage_complete: unreported === 0,
    unreported_model_requests: unreported, model_cost: null });
  return {
    models: () => provider.models(),
    ...(provider.count ? { count: (...args) => provider.count(...args) } : {}),
    ...(provider.registry ? { registry: provider.registry } : {}),
    usage,
    async *infer(request, options) {
      const started = Date.now();
      if (options.signal.aborted) {
        yield { type: 'error', reason: 'aborted', code: 'ABORTED', message: 'aborted', retryable: false };
        return;
      }
      if (nextAllowedAt > Date.now()) {
        const waitMs = nextAllowedAt - Date.now();
        if (Date.now() + waitMs >= deadline) {
          failure('WALL_TIME_EXHAUSTED', started);
          yield { type: 'error', reason: 'error', code: 'WALL_TIME_EXHAUSTED',
            message: 'WALL_TIME_EXHAUSTED', retryable: false };
          return;
        }
        try { await delay(waitMs, undefined, { signal: options.signal }); } catch {
          yield { type: 'error', reason: 'aborted', code: 'ABORTED', message: 'aborted', retryable: false };
          return;
        }
      }
      let code;
      if (!config.allowed) code = 'MODEL_CALLS_DISABLED';
      else if (Date.now() >= deadline) code = 'WALL_TIME_EXHAUSTED';
      else if (request.route !== config.route || request.model !== config.model) code = 'UNEXPECTED_MODEL';
      else if (!Number.isSafeInteger(request.sampling?.maxTokens) || request.sampling.maxTokens <= 0
               || request.sampling.maxTokens > config.maxTokens) code = 'OUTPUT_BUDGET_UNVERIFIED';
      else if (requests >= config.maxRequests) code = 'MODEL_REQUEST_BUDGET';
      else if (request.tools.some(tool => !config.toolNames.includes(tool.name))) code = 'UNEXPECTED_TOOL';
      if (code) {
        failure(code, started);
        onUsage({ ...usage(), blocked_reason: code,
          ...(code === 'UNEXPECTED_TOOL' ? { blocked_tools: request.tools.filter(t => !config.toolNames.includes(t.name)).map(t => t.name) } : {}) });
        yield { type: 'error', reason: 'error', code, message: code, retryable: false };
        return;
      }
      requests += 1;
      unreported += 1;
      onUsage(usage());
      const remaining = deadline - Date.now();
      const timeoutMs = Math.max(1, Math.min(requestTimeoutMs, remaining));
      const timer = AbortSignal.timeout(timeoutMs);
      const signal = AbortSignal.any([options.signal, timer]);
      const timeoutError = () => {
        const wallExpired = Date.now() >= deadline;
        failure(wallExpired ? 'WALL_TIME_EXHAUSTED' : 'MODEL_REQUEST_TIMEOUT', started,
          { timeout_ms: timeoutMs });
        return { type: 'error', reason: 'error', code: wallExpired ? 'WALL_TIME_EXHAUSTED' : 'TIMEOUT',
          message: wallExpired ? 'WALL_TIME_EXHAUSTED' : 'MODEL_REQUEST_TIMEOUT', retryable: !wallExpired };
      };
      let reported = false;
      try {
        for await (const event of provider.infer(request, { ...options, signal, retry: false })) {
          if (timer.aborted && !options.signal.aborted) { yield timeoutError(); return; }
          if (event.type === 'usage') {
            tokens += (event.tokens?.input ?? 0) + (event.tokens?.output ?? 0);
            if (!reported) { unreported -= 1; reported = true; }
            onUsage(usage());
          }
          if (event.type === 'error') {
            const codes = { RATE_LIMIT: 'MODEL_RATE_LIMIT', QUOTA: 'MODEL_QUOTA_EXHAUSTED',
              TIMEOUT: 'MODEL_REQUEST_TIMEOUT', AUTH: 'MODEL_AUTH_ERROR', TRANSPORT: 'MODEL_TRANSPORT_ERROR' };
            const retryAfterMs = Number.isSafeInteger(event.retryAfterMs) && event.retryAfterMs > 0
              ? event.retryAfterMs : 1000;
            if (event.code === 'RATE_LIMIT') nextAllowedAt = Date.now() + retryAfterMs;
            failure(codes[event.code] ?? 'MODEL_PROVIDER_ERROR', started,
              event.code === 'RATE_LIMIT' ? { retry_after_ms: retryAfterMs } : {});
            yield event;
            return;
          }
          yield event;
        }
        if (timer.aborted && !options.signal.aborted) yield timeoutError();
      } catch (error) {
        if (timer.aborted && !options.signal.aborted) { yield timeoutError(); return; }
        if (options.signal.aborted) {
          yield { type: 'error', reason: 'aborted', code: 'ABORTED', message: 'aborted', retryable: false };
          return;
        }
        // Never publish raw provider exception text or request data.
        failure('MODEL_TRANSPORT_ERROR', started);
        throw error;
      }
    },
  };
}
