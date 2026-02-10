# AgentKit 文档

本目录包含 AgentKit SDK 和 CLI 的完整文档。

## 本地开发

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run docs:dev
```

访问 `http://localhost:5173` 查看文档站点。
### 构建生产版本

```bash
npm run docs:build
```

构建结果位于 `.vitepress/dist` 目录。

### 预览生产版本

```bash
npm run docs:preview
```

## 目录结构

```
docs/
├── .vitepress/          # VitePress 配置
│   └── config.js        # 站点配置文件
├── content/             # 文档内容
│   ├── 1.introduction/  # 入门指南
│   ├── 2.agentkit-sdk/  # SDK 文档
│   └── 3.agentkit-cli/  # CLI 文档
├── public/              # 静态资源
│   └── images/          # 图片文件
├── index.md             # 首页
└── package.json         # 项目配置
```

## 文档规范

- 所有 Markdown 文件使用中文编写
- 代码示例使用英文注释
- 图片存放在 `public/images/` 目录
- 使用相对路径引用图片：`![描述](../../public/images/xxx.png)`
