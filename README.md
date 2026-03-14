# Local Image Translation Engine

本仓库用于承载本地图片翻译引擎 MVP。

当前阶段目标：

- 先完成 engine 模块化骨架
- 统一配置、路径、运行产物目录
- 为后续 FastAPI、CLI、旧脚本迁移提供稳定落点

## 仓库结构

```text
app/
  api/          HTTP 接口层
  core/         核心模型、配置、主流程
  providers/    OCR / 翻译 / 擦字 provider
  render/       文本回填相关逻辑
  services/     任务目录、产物、锁、运行期状态
  utils/        通用工具
config/         配置文件
docs/adr/       架构决策记录
runs/           每次任务的输出与调试产物
samples/        测试样例
tests/          单元与集成测试
workflows/      ComfyUI 工作流模板
```

## 路径原则

- 不在业务代码中写机器绝对路径
- 所有仓库内资源路径从项目根目录统一派生
- 可变资源路径通过 `config/config.yaml` 配置
- 单次任务产物统一写入 `runs/YYYY-MM-DD/job_<id>/`

## 当前初始化范围

当前已完成：

- 项目骨架和目录约束
- FastAPI 基础接口
- fast 主链路迁移：OCR / 翻译 / mask / OpenCV inpaint / 文字回填
- HQ 模式骨架迁移：ComfyUI workflow 调用与降级状态

当前仍未完成：

- ComfyUI 工作流联调
- 超时保护与 `/render` 接口
- 更完整的日志、测试和结果证据
- 真正可中断的底层超时取消

## 启动骨架服务

安装依赖：

```bash
pip install -r requirements.txt
```

启动：

```bash
uvicorn app.api.main:app --reload
```

说明：

- 当前 API 已有 `/health`、`/process`、`/ocr`、`/erase`
- 当前 API 已有 `/health`、`/process`、`/ocr`、`/erase`、`/render`
- `fast` 模式主链路已经接入真实旧脚本逻辑
- `hq` 模式仍需结合你的真实 ComfyUI workflow 文件联调
- `/health` 会检查字体、workflow、ComfyUI 目录和本地服务可用性
- `runs/.../job_xxx/` 已包含 `result.json` 和 `logs.txt`
