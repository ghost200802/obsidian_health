---
type: concept
created: 2026-06-02
updated: 2026-06-02
tags: [知识管理, 工具, 笔记, 知识库]
---

# Obsidian 知识库

## 定义

Obsidian 是一款基于本地 Markdown 文件的知识库工具，支持双向链接、图谱视图、PDF 内嵌等功能。在 [[LLM-Wiki知识管理]] 方法论中，Obsidian 作为本地知识库工作区，承载 [[Raw层]] 和 [[Wiki层]] 的所有内容。

## 核心功能

- **双向链接**：使用 `[[]]` 语法创建知识节点间的关联
- **图谱视图**：可视化展示知识网络结构
- **PDF 内嵌**：支持 `![[file.pdf#page=N]]` 语法直接嵌入 PDF 页面
- **Local REST API**：通过 API 接口实现 Agent 对知识库的读写操作
- **模板系统**：支持标准化知识页面创建

## 在 LLM Wiki 中的角色

- **[[Raw层]] 容器**：存储原始资料（PDF、网页存档等），只读不可修改
- **[[Wiki层]] 容器**：存储编译后的结构化知识页面
- **图谱可视化**：通过关系图谱直观展示知识网络的完整性

## 相关概念

- [[LLM-Wiki知识管理]] - 以 Obsidian 为基础的知识管理方法论
- [[Raw层]] - Obsidian 中的原始资料目录
- [[Wiki层]] - Obsidian 中的知识沉淀目录

## 来源

- [[Obsidian-Codex知识库|知乎：我用Obsidian + Codex搭了一个会持续进化的AI知识库]]
