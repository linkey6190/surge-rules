# surge-rules

自维护的 Surge 远程规则集，由 GitHub Actions 每日构建。输出文件在 `rules/AI.list`。

当前内容：ChatGPT / Gemini 相关域名（包含登录验证、埋点上报、Google AI Studio、NotebookLM 等端点）。

- 不含 Apple Intelligence 域名（`icloud.com`、`apple-relay.*`、`guzzoni.apple.com` 等）
- 不含通用三方服务（stripe / auth0 / algolia / sentry / segment / intercom / launchdarkly / datadog / cloudflareinsights）
- 不收录 IP-CIDR、IP-ASN、PROCESS-NAME（iOS 无效且范围过宽）

## 使用

```
[Rule]
RULE-SET,https://raw.githubusercontent.com/linkey6190/surge-rules/main/rules/AI.list,AI,extended-matching,"update-interval=86400",no-resolve
```

`AI` 换成你自己的策略组名。这条规则要放在 Apple 通用规则集（如 AppleAll.list）之前，否则会被 `DOMAIN-SUFFIX,apple.com` / `icloud.com` 之类的宽泛规则抢先命中。

## 目录

```
build.py                     合并 + 过滤 + 校验 + 生成
sources.json                 上游清单、剔除名单、覆盖校验清单
rules/AI.list                生成物（不要手工编辑）
.github/workflows/build.yml  每日 03:20（UTC+8）构建并提交
```

## 上游

- `VPSDance/ai-proxy-rules` — openai / google-ai
- `blackmatrix7/ios_rule_script` — OpenAI / Gemini / BardAI

只保留 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD` 三类，其余一律丢弃；同类重复条目自动去重。

## 发布前校验

`build.py` 在写入前会做三项检查，任一失败即中止且不覆盖已有文件（Surge 继续使用上一次成功版本）：

1. 不得出现 Apple AI 域名
2. `sources.json` 的 `coverage` 清单里每个端点都必须被覆盖（ChatGPT 10 个、Gemini 14 个）
3. 规则条数相对上一版变动不得超过 ±30%

要新增覆盖点，改 `sources.json` 的 `coverage` 或 `sources`，提交后 Actions 会自动重建。

## 本地运行

```
python3 build.py
```

只依赖 Python 3 标准库。
