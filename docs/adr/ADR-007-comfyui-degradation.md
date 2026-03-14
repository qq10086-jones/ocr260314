# ADR-007 ComfyUI 熔断降级

## 状态

Accepted

## 决策

ComfyUI provider 内部维护连续失败计数，并在达到阈值后自动降级至 OpenCV 模式。

## 理由

- HQ 模式依赖外部本地服务，稳定性天然弱于 OpenCV
- 降级逻辑可低成本提升主链路可用性
- 能满足 MVP 对鲁棒性的最低要求

## 放弃方案

- 引入外部熔断框架
- 为 provider 额外抽象复杂 circuit breaker 层

## 复审时机

- HQ 模式验收后
- 失败模式与恢复机制有新增真实问题时
