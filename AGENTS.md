# 技能与插件更新

本仓库通过同一个 Git 仓库向 Codex 和 Claude Code 分发插件。更新技能时，必须同时保证对应 harness 能检测到插件更新。

## Codex

- 新增、修改或删除 `plugins/skills/skills/` 下的技能文件时，必须同步更新 `plugins/skills/.codex-plugin/plugin.json` 的 `version`，并与技能变更一并提交。技能文件包括 `SKILL.md`、参考文档、脚本、资源和 `agents/openai.yaml`。
- 常规更新保留基础版本，使用新的 UTC 时间戳替换唯一的 `+codex.<YYYYMMDDHHMMSS>` 后缀。可用时使用 `plugin-creator` 的 `update_plugin_cachebuster.py`；确认最终版本与发布前不同。
- 保持 `.agents/plugins/marketplace.json` 的插件来源指向实际插件目录，使同步取得新的清单和技能内容。

## Claude Code

- 保持 `.claude-plugin/marketplace.json` 中的 Git 源及提交 SHA 更新检测策略。插件条目和根目录的 `.claude-plugin/plugin.json`（若存在）均不设置固定 `version`。
- 保持 `.claude/settings.json` 中此 marketplace 的 `autoUpdate: true`，以及 `README.md` 声明的各技能 harness 可见范围。

## 提交前校验

- 检查技能变更是否附带 Codex 插件版本更新，并确认两个 marketplace 的来源路径、技能路径和更新标识有效。
- 运行修改涉及的技能校验、Codex 插件清单校验和 `claude plugin validate .`；有脚本或行为变更时运行相关现有检查。
- 区分“更新可被检测”与“客户端已加载更新”。远程发布需要推送提交并等待或执行 marketplace 刷新；本地目录安装需要重新安装插件。仅在实际验证客户端已加载后，才能宣称新版本已生效。
