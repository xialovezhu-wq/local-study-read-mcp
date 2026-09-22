# 本地学习库只读 MCP

为数学、408、英语学习库提供受限读取工具。服务按学科根目录、冻结材料和版本绑定返回证据，区分原始资料、正式记录、事件和派生视图。它不负责替使用者作答或写入正式学习事实。

## 项目结构

- `src/study_read_mcp/`：MCP 服务和学科读取适配。
- `config/`：示例配置。
- `scripts/`：发行包与验证脚本。
- `tests/`：隔离测试。

## 运行

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-deps setuptools==80.9.0
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

配置 `STUDY_READ_MATH_ROOT`、`STUDY_READ_CS408_ROOT`、`STUDY_READ_ENGLISH_ROOT` 和 `STUDY_INTAKE_RUNTIME_ROOT` 为自己的目录后运行：

```sh
.venv/bin/python -m study_read_mcp --stdio --profile ordinary --subjects math,cs408,english
```

完整配置、工具边界和发行说明见 [技术文档](README.technical.md)。该仓库保存已有 MCP 实现；目前另有 [Study-Pro-Bridge](https://github.com/xialovezhu-wq/study-pro-bridge) 承担网页学习工作流桥接。两者是不同项目。

## 公开范围

只公开源码、配置模板和测试结构。真实学习库、对话、个人画像、凭据与运行状态应由使用者本机保管。公开不代表已经对当前机器重新部署或运行全部测试。
