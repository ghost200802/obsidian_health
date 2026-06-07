# Local Knowledge Base Integration

Use this reference when the user asks specific nutrition, dietary, or health questions that can benefit from evidence-based knowledge retrieval from the local Obsidian vault.

## Overview

This Skill prefers the local Obsidian knowledge base in this workspace. The only reference layers for consultation are:

- `wiki/`: distilled concept, scenario, and practice pages
- `source/`: source pages that preserve context, provenance, and extraction notes

The goal is to answer with stable, reusable knowledge first, then use source pages to verify wording and context.

## Search Order

1. Search `wiki/` first.
2. Search `source/` second.
3. Do not search `Apple Notes/`, `raw/`, or other draft areas during consultation.

## Search Patterns

Use concise topic keywords. Examples:

- `胰岛素抵抗`
- `桥本氏甲状腺炎`
- `鱼油`
- `备孕营养`
- `减重平台期`
- `情绪性进食`

If the topic is broad, add a second narrowing term:

- `桥本氏甲状腺炎 补硒`
- `PCOS 饮食`
- `减重 NEAT`
- `高尿酸 饮食`

## How to Use Search Results

1. Prefer `wiki/` when the answer needs a clean, user-facing explanation.
2. Use `source/` to confirm details, context, and provenance.
3. If `wiki/` and `source/` disagree in wording, prefer the clearer and more conservative interpretation.
4. Do not quote long passages. Summarize and translate into plain Chinese.

## Fallback Rules When Nothing Is Found

If neither `wiki/` nor `source/` contains useful material:

1. Do not search `Apple Notes` as a fallback.
2. Do not imply the local knowledge base contains support when it does not.
3. Only answer with high-consensus, low-risk basics.
4. Do not give numeric targets, supplement doses, disease-specific plans, lab cutoff interpretation, or treatment claims without local support.
5. For high-risk topics, prefer advising offline medical care or a clinical nutrition department.
6. If useful, explicitly mark the topic as a knowledge gap that can later be added through the ingest workflow.

## Quality Control

1. Local search results are supplementary references, not medical advice.
2. Always apply the Safety First rules to any information retrieved locally.
3. Prefer pages that already have explicit `source` links.
4. When local support is missing, reduce confidence and shorten the answer rather than improvising.
5. When citing materials, say "根据本地知识库中的资料" rather than claiming certainty.

## Error Handling

If no good local materials are found:

1. Do not present the lack of local materials as a blocker.
2. Answer based on general knowledge using the Core Judgment Framework, but only at a conservative level.
3. Say: "这个主题我先按保守原则给你一个简短回答。如果你愿意，后续也可以把它补进本地知识库。"
4. Continue with normal consultation flow.
