---
id: TASK-328
title: '[backend:orchestrator] Model azure/anthropic/claude-opus-4-7 not available
  in provider inference-api.nvidia.com (available: aws/anthropic/bedrock-claude-3-5-haiku-v1,
  aws/anthropic/bedrock-claude-3...'
status: Done
assignee: []
created_date: 2026-04-29 01:47
updated_date: 2026-04-29 02:02
labels:
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-zlz_2-veg
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-veg
  target_branch: null
  url: null
  created_at: '2026-04-29T01:47:38Z'
  updated_at: '2026-04-29T02:02:34Z'
  closed_at: '2026-04-29T02:02:34Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Model azure/anthropic/claude-opus-4-7 not available in provider inference-api.nvidia.com (available: aws/anthropic/bedrock-claude-3-5-haiku-v1, aws/anthropic/bedrock-claude-3-7-sonnet-v1, aws/anthropic/bedrock-claude-opus-4-1-v1, aws/anthropic/bedrock-claude-opus-4-6, aws/anthropic/bedrock-claude-sonnet-4-5-v1, aws/anthropic/bedrock-claude-sonnet-4-6, aws/anthropic/claude-haiku-4-5-v1, aws/anthropic/claude-opus-4-5, aws/anthropic/us.anthropic.claude-sonnet-4-v1, azure/anthropic/claude-haiku-4-5, azure/anthropic/claude-opus-4-5, azure/anthropic/claude-opus-4-6, azure/anthropic/claude-sonnet-4-5, azure/anthropic/claude-sonnet-4-6, azure/openai/gpt-4, azure/openai/gpt-4.1, azure/openai/gpt-4.1-mini, azure/openai/gpt-4o, azure/openai/gpt-4o-mini, azure/openai/gpt-5, azure/openai/gpt-5-chat, azure/openai/gpt-5-mini, azure/openai/gpt-5-nano, azure/openai/gpt-5.1, azure/openai/gpt-5.1-chat, azure/openai/gpt-5.1-codex, azure/openai/gpt-5.1-codex-max, azure/openai/gpt-5.1-codex-mini, azure/openai/gpt-5.2, azure/openai/gpt-5.2-chat, azure/openai/gpt-5.2-codex, azure/openai/gpt-5.3-chat, azure/openai/gpt-5.3-codex, azure/openai/o1, azure/openai/o3, azure/openai/o3-mini, azure/openai/o4-mini, azure/openai/text-embedding-3-large, azure/openai/text-embedding-3-small, azure/openai/text-embedding-ada-002, fake-openai-endpoint, fusion-fake-llm, gcp/google/gemini-2.5-flash, gcp/google/gemini-2.5-flash-lite, gcp/google/gemini-2.5-pro, gcp/google/gemini-3-flash-preview, gcp/google/gemini-3-pro, gcp/google/gemini-3-pro-image-preview, gcp/google/gemini-3-pro-preview, gcp/google/gemini-3.1-flash-lite-preview, gcp/google/gemini-3.1-pro-preview, gcp/google/multimodalembedding, gcp/google/veo-3.0-generate-001, gcp/google/veo-3.1-generate-001, nvcf/meta/llama-3.1-70b-instruct, nvcf/meta/llama-3.2-1b-instruct, nvcf/meta/llama-3.3-70b-instruct, nvcf/nvidia/llama-3.2-nemoretriever-300m-embed-v2, nvcf/nvidia/llama-3.2-nemoretriever-500m-rerank-v2, nvcf/nvidia/llama-3.2-nv-embedqa-1b-v2, nvcf/nvidia/llama-3.2-nv-rerankqa-1b-v2, nvcf/nvidia/llama-3.3-nemotron-super-49b-v1, nvcf/nvidia/llama-3.3-nemotron-super-49b-v1.5, nvcf/nvidia/nemotron-nano-12b-v2-vl, nvcf/nvidia/nemotron-nano-31b-v3, nvcf/openai/gpt-oss-120b, nvidia/meta/llama-3.1-70b-instruct, nvidia/meta/llama-3.1-70b-instruct-bugnemo, nvidia/meta/llama-3.1-8b-instruct, nvidia/meta/llama-3.2-1b-instruct, nvidia/meta/llama-3.3-70b-instruct, nvidia/nvidia/Nemotron-3-Nano-30B-A3B, nvidia/nvidia/llama-3.1-nemoguard-8b-content-safety, nvidia/nvidia/llama-3.1-nemoguard-8b-topic-control, nvidia/nvidia/llama-3.1-nemotron-ultra-253b-v1, nvidia/nvidia/llama-3.2-nemoretriever-300m-embed-v2, nvidia/nvidia/llama-3.2-nemoretriever-500m-rerank-v2, nvidia/nvidia/llama-3.2-nv-embedqa-1b-v2, nvidia/nvidia/llama-3.2-nv-embedqa-1b-v2-bugnemo, nvidia/nvidia/llama-3.2-nv-rerankqa-1b-v2, nvidia/nvidia/llama-3.3-nemotron-super-49b-v1, nvidia/nvidia/llama-3.3-nemotron-super-49b-v1.5, nvidia/nvidia/llama-embed-nemotron-8b, nvidia/nvidia/nemotron-3-super-preview, nvidia/nvidia/nemotron-3-super-rc-nim, nvidia/nvidia/nemotron-nano-12b-v2-vl, nvidia/nvidia/nemotron-nano-30b-v3, nvidia/nvidia/nemotron-nano-31b-v3, nvidia/nvidia/nemotron-nano-9b-v2, nvidia/openai/gpt-oss-120b, nvidia/openai/gpt-oss-20b, nvidia/qwen/qwen-235b, nvidia/qwen/qwen3-embedding-0.6b, nvidia/qwen/qwen3-next-80b-a3b-instruct, nvidia/qwen/qwen3-reranker-0.6b, nvidia_dynamo/nvidia/nemotron-nano-30b-a3b-omni, nvidia_dynamo/nvidia/nvidia-nemotron-3-nano-30b-a3b, openai/openai/gpt-3.5-turbo, openai/openai/gpt-5-codex, openai/openai/gpt-5-mini, openai/openai/gpt-5-nano, openai/openai/gpt-5.1, openai/openai/gpt-5.1-codex, openai/openai/gpt-5.2, openai/openai/gpt-5.2-codex, openai/openai/gpt-5.3-codex, openai/openai/gpt-5.4, perplexity/perplexity/sonar, perplexity/perplexity/sonar-deep-research, perplexity/perplexity/sonar-pro, perplexity/perplexity/sonar-reasoning-pro, us/azure/openai/gpt-4.1, us/azure/openai/gpt-4.1-mini, us/azure/openai/gpt-4.1-nano, us/azure/openai/gpt-4o-mini, us/azure/openai/gpt-5, us/azure/openai/gpt-5-mini, us/azure/openai/gpt-5-nano, us/azure/openai/gpt-5.1, us/azure/openai/gpt-5.2, us/azure/openai/o1, us/azure/openai/o3-mini, us/azure/openai/o4-mini, us/azure/openai/text-embedding-3-large, us/azure/openai/text-embedding-3-small, us/azure/openai/text-embedding-ada-002)
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
