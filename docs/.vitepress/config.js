export default {
  title: 'AgentKit',
  description: 'Python SDK and CLI for building Agent applications on Volcengine',
  base: '/agentkit-sdk-python/',
  
  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }],
  ],

  themeConfig: {
    logo: '/logo.png',
    
    socialLinks: [
      { icon: 'github', link: 'https://github.com/volcengine/agentkit-sdk-python' },
    ],
    
    footer: {
      message: 'Released under the Apache-2.0 License.',
      copyright: 'Copyright © 2026 Volcengine',
    },
    
    search: {
      provider: 'local',
    },

    sidebar: {
      '/': [
        {
          text: '📖 概述',
          collapsed: false,
          items: [
            { text: 'AgentKit', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: 'Troubleshooting', link: '/content/1.introduction/4.troubleshooting' },
          ],
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: 'Harness', link: '/content/2.agentkit-cli/5.harness' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' },
            { text: 'Logging', link: '/content/2.agentkit-cli/4.logging' },
          ],
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Annotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' },
            { text: 'Agent Identity 与 OBO', link: '/agent_identity' },
          ],
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 快速开始', link: '/content/4.runtime/1.runtime_quickstart' },
            { text: 'Runtime 性能诊断', link: '/content/4.runtime/2.performance_diagnostics' },
          ],
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' },
          ],
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' },
          ],
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' },
          ],
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' },
          ],
        },
      ],
    },

    outline: {
      level: [2, 3],
      label: '目录',
    },

    docFooter: {
      prev: '上一页',
      next: '下一页',
    },

    lastUpdated: {
      text: '最后更新于',
      formatOptions: {
        dateStyle: 'short',
        timeStyle: 'medium',
      },
    },
  },

  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [{ text: '首页', link: '/' }],
      },
    },
    en: {
      label: 'English',
      lang: 'en-US',
      themeConfig: {
        nav: [{ text: 'Home', link: '/en/' }],
        sidebar: {
          '/en/': [
            {
              text: '📖 Overview',
              collapsed: false,
              items: [
                { text: 'AgentKit', link: '/en/content/1.introduction/1.overview' },
                { text: 'Installation', link: '/en/content/1.introduction/2.installation' },
                { text: 'Quick Start', link: '/en/content/1.introduction/3.quickstart' },
                { text: 'Troubleshooting', link: '/en/content/1.introduction/4.troubleshooting' },
              ],
            },
            {
              text: '⚡ CLI',
              collapsed: true,
              items: [
                { text: 'CLI Overview', link: '/en/content/2.agentkit-cli/1.overview' },
                { text: 'Commands', link: '/en/content/2.agentkit-cli/2.commands' },
                { text: 'Configuration', link: '/en/content/2.agentkit-cli/3.configurations' },
                { text: 'Logging', link: '/en/content/2.agentkit-cli/4.logging' },
              ],
            },
            {
              text: '🔧 SDK',
              collapsed: true,
              items: [
                { text: 'SDK Overview', link: '/en/content/3.agentkit-sdk/1.overview' },
                { text: 'Annotations', link: '/en/content/3.agentkit-sdk/2.annotation' },
                { text: 'Agent Identity and OBO', link: '/agent_identity' },
              ],
            },
            {
              text: '🚀 Runtime',
              collapsed: true,
              items: [
                { text: 'Runtime Quickstart', link: '/en/content/4.runtime/1.runtime_quickstart' },
              ],
            },
            {
              text: '🛠️ Tools',
              collapsed: true,
              items: [
                { text: 'Tools Quickstart', link: '/en/content/5.tools/1.sandbox_quickstart' },
              ],
            },
            {
              text: '💾 Memory',
              collapsed: true,
              items: [
                { text: 'Memory Quickstart', link: '/en/content/6.memory/1.memory_quickstart' },
              ],
            },
            {
              text: '📚 Knowledge',
              collapsed: true,
              items: [
                { text: 'Knowledge Quickstart', link: '/en/content/7.knowledge/1.knowledge_quickstart' },
              ],
            },
            {
              text: '🔌 MCP',
              collapsed: true,
              items: [
                { text: 'MCP Overview', link: '/en/content/8.mcp/1.overview' },
                { text: 'MCP Quickstart', link: '/en/content/8.mcp/2.mcp_quickstart' },
              ],
            },
          ],
        },
        outline: {
          level: [2, 3],
          label: 'On this page',
        },
        docFooter: {
          prev: 'Previous page',
          next: 'Next page',
        },
        lastUpdated: {
          text: 'Last updated at',
          formatOptions: {
            dateStyle: 'short',
            timeStyle: 'medium',
          },
        },
      },
    },
  },
}
