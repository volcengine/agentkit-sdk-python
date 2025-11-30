export default {
  title: 'AgentKit',
  description: 'Python SDK and CLI for building Agent applications on Volcengine',
  base: '/agentkit-sdk-python/',

  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }]
  ],
  
  themeConfig: {
    logo: '/logo.png',
    
    nav: [
      { text: '首页', link: '/' }
    ],
    
    sidebar: {
      '/content/1.introduction/': [
        {
          text: '📖 概述',
          collapsed: false,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      
      '/content/2.agentkit-cli/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: false,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      
      '/content/3.agentkit-sdk/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: false,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      
      '/content/4.runtime/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: false,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      '/content/5.tools/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: false,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      '/content/6.memory/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: false,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      '/content/7.knowledge/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: false,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: true,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ],
      '/content/8.mcp/': [
        {
          text: '📖 概述',
          collapsed: true,
          items: [
            { text: 'AgentKit 概述', link: '/content/1.introduction/1.overview' },
            { text: '安装指南', link: '/content/1.introduction/2.installation' },
            { text: '快速开始', link: '/content/1.introduction/3.quickstart' },
            { text: '常见问题', link: '/content/1.introduction/4.troubleshooting' }
          ]
        },
        {
          text: '⚡ CLI',
          collapsed: true,
          items: [
            { text: 'CLI 概览', link: '/content/2.agentkit-cli/1.overview' },
            { text: '命令详解', link: '/content/2.agentkit-cli/2.commands' },
            { text: '配置文件说明', link: '/content/2.agentkit-cli/3.configurations' }
          ]
        },
        {
          text: '🔧 SDK',
          collapsed: true,
          items: [
            { text: 'SDK 概览', link: '/content/3.agentkit-sdk/1.overview' },
            { text: 'Anotation 使用指南', link: '/content/3.agentkit-sdk/2.annotation' }
          ]
        },
        {
          text: '🚀 Runtime',
          collapsed: true,
          items: [
            { text: 'Runtime 概览', link: '/content/4.runtime/1.overview' }
          ]
        },
        {
          text: '🛠️ Tools',
          collapsed: true,
          items: [
            { text: 'Tools 快速开始', link: '/content/5.tools/1.sandbox_quickstart' }
          ]
        },
        {
          text: '💾 Memory',
          collapsed: true,
          items: [
            { text: 'Memory 快速开始', link: '/content/6.memory/1.memory_quickstart' }
          ]
        },
        {
          text: '📚 Knowledge',
          collapsed: true,
          items: [
            { text: 'Knowledge 快速开始', link: '/content/7.knowledge/1.knowledge_quickstart' }
          ]
        },
        {
          text: '🔌 MCP',
          collapsed: false,
          items: [
            { text: 'MCP 概览', link: '/content/8.mcp/1.overview' },
            { text: 'MCP 快速开始', link: '/content/8.mcp/2.mcp_quickstart' }
          ]
        }
      ]
    },
    
    socialLinks: [
      { icon: 'github', link: 'https://github.com/volcengine/agentkit-sdk-python' }
    ],
    
    footer: {
      message: 'Released under the Apache-2.0 License.',
      copyright: 'Copyright © 2025 Volcengine'
    },
    
    search: {
      provider: 'local'
    },
    
    outline: {
      level: [2, 3],
      label: '目录'
    },
    
    docFooter: {
      prev: '上一页',
      next: '下一页'
    },
    
    lastUpdated: {
      text: '最后更新于',
      formatOptions: {
        dateStyle: 'short',
        timeStyle: 'medium'
      }
    }
  }
}
