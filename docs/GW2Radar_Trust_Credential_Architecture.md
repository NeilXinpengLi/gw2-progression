# GW2Radar / AegisRadar 信任体系与 API Key 安全架构设计

> 版本：v1.0 Trust & Credential Security Architecture  
> 适用系统：GW2Radar / AegisRadar / AetherTwin / EnvConsole  
> 目标：构建 BYOK（Bring Your Own Key）安全体系 + 用户信任体系 + 企业级 Credential 管理架构

---

## 1. 核心问题定义

在当前系统中，最大阻力不是功能，而是：

> 用户是否愿意把 API Key 交给系统。

用户担忧集中在三点：

```text
1. Key 是否被存储
2. Key 是否被滥用
3. Key 是否可控 / 可撤销
```

---

## 2. 总体架构设计（Trust Layer）

## 2.1 三层信任模型

```text
Layer 3: External Trust
Layer 2: System Security
Layer 1: User Trust UI
```

---

## 3. API Key 使用模式

### Mode A：Session-only

- 不存储 Key
- 内存使用
- 请求后释放

### Mode B：Encrypted Persistent

- AES 加密存储
- 支持 weekly report

### Mode C：Team Workspace

- Admin 管理
- 成员不可见 Key

---

## 4. Credential Center

Provider 分类：

- GW2 API
- LLM Providers
- Search Providers
- Commerce Providers
- Internal Tools

---

## 5. Key 安全设计

原则：

- 不记录 Key
- 不进日志
- 不进 URL
- 不进前端存储

推荐：

- session memory
- encrypted DB
- KMS

Fingerprint：

- SHA256(key)

---

## 6. 权限解释 UI

用户必须看到：

- 访问 account / wallet / bank / inventory / tradingpost
- 不访问密码 / 邮箱

---

## 7. Cost Control

- budget limit
- daily limit
- fallback provider

---

## 8. Team Workspace

- Admin 控制 Key
- Member 不可见 Key
- audit log

---

## 9. GW2Radar 流程

Input Key → Permission Explain → Mode Select → Analyze → Report → Optional Save

---

## 10. AegisRadar 扩展

- LLM Key
- Search Key
- Map Key
- Commerce Key

---

## 11. 安全增强

- audit log
- key rotation
- revoke
- encrypted storage

---

## 12. 结论

BYOK + 信任体系 = 垂直智能产品商业化基础
