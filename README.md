# AstrBot AI 敏感内容检测和撤回插件

一个轻量级的 AstrBot 插件，使用 AI 自动检测并撤回文本和图片中的违禁内容。

## 功能

**文本检测**
**图片检测**
**自动撤回**

## 快速开始

### 1. 安装插件

```bash
cd /path/to/astrbot/plugins
git clone https://github.com/zengweis/astrbot_plugin_censor
```

### 2. 配置 API

在 AstrBot 配置文件中添加（`config.yaml` 或 `config.yml`）：

```yaml
plugins:
  censor:
    nlp_api_key: "sk-your-openai-api-key"
```

### 3. 重启 AstrBot

插件会自动加载并开始监听消息。

## 配置说明

### 必需配置

```yaml
plugins:
  censor:
    nlp_api_url: "https://api.openai.com/v1/chat/completions"  
    nlp_api_key: "sk-xxx..."                                     
```




## 支持的内容类型

- 文本消息
- 图片（需要 URL 或本地路径）
- 混合消息（文本 + 图片）

## 检测内容

插件检测包括但不限于：

- 色情内容
- 暴力或恐怖内容
- 违法信息
- 诈骗或骚扰
- 仇恨言论

## 调试

### 查看日志

```bash
tail -f logs/astrbot.log | grep censor
```

### 常见错误

**Error: API 密钥未配置**
- 检查 `config.yaml` 中是否正确配置了 `nlp_api_key`

**Error: API 超时**
- 检查网络连接
- 检查 API 配额是否足够

**消息未被撤回**
- 某些平台可能不支持撤回功能
- 检查机器人是否有权限


## 相关链接

- [AstrBot 项目](https://github.com/AstrBotDevs/AstrBot)
- [OpenAI API 文档](https://platform.openai.com/docs)

## 许可证

MIT License

---

更多帮助，请提交 Issue 或查看代码中的注释。
