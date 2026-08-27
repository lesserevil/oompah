#!/usr/bin/env node
import { createInterface } from "node:readline";
import { createProvider } from "@earendil-works/pi-ai";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";

const PROTOCOL = "oompah-pi-ai-v1";
const MAX_FRAME_BYTES = 10 * 1024 * 1024;
let activeController = null;
let initialized = null;
let models = null;

function emit(value) { process.stdout.write(`${JSON.stringify(value)}\n`); }
function fail(id, code, message) { emit({ type: "error", id, code, message: String(message).slice(0, 2000) }); }
function normalizeTool(tool) {
  const fn = tool?.function;
  if (!fn || typeof fn.name !== "string") throw new Error("tool definition must use the OpenAI function shape");
  return { name: fn.name, description: String(fn.description || ""), parameters: fn.parameters || { type: "object", properties: {} } };
}
function normalizeMessage(message, toolNames) {
  const role = String(message?.role || "");
  const timestamp = Number(message?.timestamp || Date.now());
  if (role === "user") return { role, content: message.content ?? "", timestamp };
  if (role === "assistant") {
    const content = [];
    if (typeof message.content === "string" && message.content) content.push({ type: "text", text: message.content });
    for (const call of message.tool_calls || []) {
      const fn = call?.function || {}; let args = {};
      try { args = JSON.parse(fn.arguments || "{}"); } catch {}
      const id = String(call.id || ""), name = String(fn.name || "");
      if (id && name) { toolNames.set(id, name); content.push({ type: "toolCall", id, name, arguments: args }); }
    }
    return { role, content, api: message.api || "openai-completions", provider: message.provider || initialized.providerId, model: message.model || initialized.modelId, usage: message.usage || { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } }, stopReason: message.stopReason || (message.tool_calls?.length ? "toolUse" : "stop"), timestamp };
  }
  if (role === "tool") {
    const id = String(message.tool_call_id || "");
    return { role: "toolResult", toolCallId: id, toolName: String(message.name || toolNames.get(id) || "tool"), content: [{ type: "text", text: String(message.content || "") }], isError: Boolean(message.is_error), timestamp };
  }
  throw new Error(`unsupported message role ${JSON.stringify(role)}`);
}
async function initialize(command) {
  if (command.protocol !== PROTOCOL) throw new Error(`unsupported protocol ${JSON.stringify(command.protocol)}`);
  const providerId = String(command.provider || "").trim(), modelId = String(command.model || "").trim();
  if (!providerId || !modelId) throw new Error("provider and model are required");
  models = builtinModels();
  let model = models.getModel(providerId, modelId);
  if (!model && command.base_url) {
    const configuredModel = { id: modelId, name: command.model_name || modelId, api: "openai-completions", provider: providerId, baseUrl: String(command.base_url), reasoning: Boolean(command.reasoning), input: Array.isArray(command.input) ? command.input : ["text"], contextWindow: Number(command.context_window || 128000), maxTokens: Number(command.max_tokens || 16384), cost: command.cost || { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } };
    models.setProvider(createProvider({ id: providerId, name: command.provider_name || providerId, baseUrl: String(command.base_url), auth: { apiKey: { name: providerId, resolve: async () => undefined } }, models: [configuredModel], api: openAICompletionsApi() }));
    model = models.getModel(providerId, modelId);
  }
  const credential = command.credential;
  if (typeof credential === "string" && credential) await models.setRuntimeApiKey(providerId, credential);
  if (!model) throw new Error(`model not found: ${providerId}/${modelId}`);
  initialized = { providerId, modelId, model, thinking: command.thinking || "off", timeoutMs: Number(command.timeout_ms || 0) || undefined, maxRetries: Number.isInteger(command.max_retries) ? command.max_retries : 0 };
  emit({ type: "ready", id: command.id, protocol: PROTOCOL, model: { provider: model.provider, id: model.id, context_window: model.contextWindow, max_tokens: model.maxTokens, reasoning: model.reasoning, input: model.input, cost: model.cost } });
}
async function complete(command) {
  if (!initialized || !models) throw new Error("bridge is not initialized");
  if (activeController) throw new Error("a provider request is already active");
  const controller = new AbortController(); activeController = controller;
  try {
    const toolNames = new Map();
    const context = { systemPrompt: String(command.system_prompt || ""), messages: Array.isArray(command.messages) ? command.messages.map((m) => normalizeMessage(m, toolNames)) : [], tools: Array.isArray(command.tools) ? command.tools.map(normalizeTool) : [] };
    emit({ type: "provider_start", id: command.id });
    const stream = models.streamSimple(initialized.model, context, { reasoning: initialized.thinking, signal: controller.signal, timeoutMs: initialized.timeoutMs, maxRetries: initialized.maxRetries, maxTokens: Number(command.max_tokens || 0) || undefined, sessionId: command.session_id || undefined });
    let finalMessage = null;
    for await (const event of stream) {
      if (event.type === "text_delta") emit({ type: "text_delta", id: command.id, delta: event.delta, usage: event.partial?.usage });
      else if (event.type === "thinking_delta") emit({ type: "thinking_delta", id: command.id, delta: event.delta, usage: event.partial?.usage });
      else if (event.type === "toolcall_start") emit({ type: "toolcall_start", id: command.id, content_index: event.contentIndex, tool_call_id: event.id, tool_name: event.toolName });
      else if (event.type === "toolcall_delta") emit({ type: "toolcall_delta", id: command.id, content_index: event.contentIndex, delta: event.delta });
      else if (event.type === "toolcall_end") emit({ type: "toolcall_end", id: command.id, tool_call: event.toolCall });
      else if (event.type === "done" || event.type === "error") finalMessage = event.message || event.error || event.partial || null;
    }
    finalMessage = finalMessage || await stream.result();
    emit({ type: "done", id: command.id, message: finalMessage });
  } finally { if (activeController === controller) activeController = null; }
}
async function handle(command) {
  const id = command?.id;
  if (!command || typeof command !== "object") throw new Error("command must be an object");
  if (command.type === "initialize") return initialize(command);
  if (command.type === "complete") return complete(command);
  if (command.type === "abort") { activeController?.abort(); emit({ type: "aborted", id }); return; }
  if (command.type === "shutdown") { activeController?.abort(); emit({ type: "shutdown", id }); process.exitCode = 0; return; }
  throw new Error(`unknown command ${JSON.stringify(command.type)}`);
}
const reader = createInterface({ input: process.stdin, crlfDelay: Infinity });
reader.on("line", (line) => {
  if (Buffer.byteLength(line, "utf8") > MAX_FRAME_BYTES) { fail(undefined, "frame_too_large", "input frame exceeds 10 MiB"); return; }
  let command;
  try { command = JSON.parse(line); } catch { fail(undefined, "invalid_json", "input is not valid JSON"); return; }
  void handle(command).catch((error) => fail(command?.id, "bridge_error", error instanceof Error ? error.message : String(error)));
});
