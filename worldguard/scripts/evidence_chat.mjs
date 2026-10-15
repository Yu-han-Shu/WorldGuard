// Single bounded completion. Credentials never leave this process except Authorization to the fixed provider.
import { readFileSync } from 'node:fs';

let key = '';
const fail = error => process.stdout.write(JSON.stringify({ error }));
try {
  const options = JSON.parse(readFileSync(process.argv[2], 'utf8').replace(/^\uFEFF/, ''));
  const credential = JSON.parse(readFileSync(options.credentials, 'utf8').replace(/^\uFEFF/, ''));
  if (credential.base_url !== 'https://api.kimi.com/coding/v1' || credential.model !== 'kimi-for-coding' || !credential.api_key)
    throw new Error('CHAT_MODEL_UNAVAILABLE');
  key = credential.api_key;
  if (!Number.isInteger(options.max_tokens) || options.max_tokens < 1 || options.max_tokens > 1600 ||
      !Number.isInteger(options.timeout_ms) || options.timeout_ms < 1 || options.timeout_ms > 60000)
    throw new Error('CHAT_MODEL_UNAVAILABLE');
  const response = await fetch('https://api.kimi.com/coding/v1/chat/completions', {
    method: 'POST', redirect: 'error', signal: AbortSignal.timeout(options.timeout_ms),
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}`,
      'User-Agent': 'WorldGuard/1.0 (Agnes-Harness)' },
    body: JSON.stringify({ model: 'kimi-for-coding', messages: options.messages,
      max_tokens: options.max_tokens, stream: false, thinking: { type: 'disabled' } }),
  });
  if (!response.ok) {
    await response.body?.cancel();
    throw new Error([401, 403].includes(response.status) ? 'CHAT_AUTH' : response.status === 429 ? 'CHAT_RATE_LIMIT' : 'CHAT_PROVIDER_ERROR');
  }
  const reader = response.body.getReader();
  const chunks = []; let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 1000000) { await reader.cancel(); throw new Error('CHAT_INVALID_RESPONSE'); }
    chunks.push(value);
  }
  const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const content = data.choices?.[0]?.message?.content;
  if (typeof content !== 'string' || data.choices?.[0]?.finish_reason !== 'stop') throw new Error('CHAT_INVALID_RESPONSE');
  const parsed = JSON.parse(content.trim().replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, ''));
  // Defense in depth: never return provider credentials, even if a malformed upstream response includes them.
  if (typeof parsed.answer === 'string') parsed.answer = parsed.answer.split(key).join('[已隐藏]').replace(/sk-[A-Za-z0-9_-]{16,}/g, '[已隐藏]');
  const usage = Object.fromEntries(Object.entries(data.usage || {}).filter(([k, v]) =>
    ['prompt_tokens', 'completion_tokens', 'total_tokens'].includes(k) && Number.isInteger(v) && v >= 0));
  process.stdout.write(JSON.stringify({ answer: parsed.answer, evidence_ids: parsed.evidence_ids, usage }));
} catch (error) {
  const allowed = ['CHAT_MODEL_UNAVAILABLE', 'CHAT_AUTH', 'CHAT_RATE_LIMIT', 'CHAT_PROVIDER_ERROR', 'CHAT_INVALID_RESPONSE'];
  fail(error.name === 'TimeoutError' || error.name === 'AbortError' ? 'CHAT_TIMEOUT' : allowed.includes(error.message) ? error.message : 'CHAT_PROVIDER_ERROR');
}
