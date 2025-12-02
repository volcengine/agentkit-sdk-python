import{_ as a,c as n,o as i,ag as p}from"./chunks/framework.CQuhCYrb.js";const E=JSON.parse('{"title":"AgentKit MCP Quick Start","description":"","frontmatter":{},"headers":[],"relativePath":"content/8.mcp/2.mcp_quickstart.md","filePath":"content/8.mcp/2.mcp_quickstart.md","lastUpdated":1764687855000}'),e={name:"content/8.mcp/2.mcp_quickstart.md"};function l(t,s,h,k,r,c){return i(),n("div",null,[...s[0]||(s[0]=[p(`<h1 id="agentkit-mcp-quick-start" tabindex="-1">AgentKit MCP Quick Start <a class="header-anchor" href="#agentkit-mcp-quick-start" aria-label="Permalink to &quot;AgentKit MCP Quick Start&quot;">​</a></h1><h2 id="环境要求" tabindex="-1">环境要求 <a class="header-anchor" href="#环境要求" aria-label="Permalink to &quot;环境要求&quot;">​</a></h2><p>开始前你需要准备：</p><ol><li><p>一个开通了 AgentKit 的火山账号的 AccessKey &amp; SecretKey</p><blockquote><p>Tips： 需要确保 AccessKey 有 AgentKitFullAccess 权限。</p></blockquote></li><li><p>MCP 服务（可以部署在 VeFaas 或公网可访问的位置）</p><ul><li>现存支持 MCP 的服务后端</li><li>现存的 HTTP 服务和服务的 Swagger 接口定义Json，具体可以参考<a href="https://swagger.io/" target="_blank" rel="noreferrer">Swagger</a></li></ul></li><li><p>Python 3.10+ installed</p></li><li><p>方舟APIKEY</p></li></ol><h2 id="第一步-配置本地环境" tabindex="-1">第一步：配置本地环境 <a class="header-anchor" href="#第一步-配置本地环境" aria-label="Permalink to &quot;第一步：配置本地环境&quot;">​</a></h2><blockquote><p>可以使用 <code>uv</code> 或者 <code>python3 -m venv</code> 进行虚拟环境管理，下文将以 <code>uv</code>做为示例</p><p><code>uv</code> 安装参考：<a href="https://docs.astral.sh/uv/getting-started/installation/" target="_blank" rel="noreferrer">uv install</a></p></blockquote><p>虚拟环境配置</p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">mkdir</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> agentkit-mcp-quickstart</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">cd</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> agentkit-mcp-quickstart</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">uv</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> venv</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> --python</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> 3.12.0</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">source</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> .venv/bin/activate</span></span></code></pre></div><p>安装依赖</p><blockquote><p>可以通过 <code>--index</code> 指定源，加快安装速度</p></blockquote><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">uv</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> pip</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> install</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> veadk-python</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">uv</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> pip</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> install</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> google-adk</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">pip</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> install</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> agentkit-sdk-python</span></span></code></pre></div><h2 id="第二步-创建-agentkit-mcp" tabindex="-1">第二步：创建 AgentKit MCP <a class="header-anchor" href="#第二步-创建-agentkit-mcp" aria-label="Permalink to &quot;第二步：创建 AgentKit MCP&quot;">​</a></h2><ol><li><p>登录火山引擎 <a href="https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/gateway/mcpservice" target="_blank" rel="noreferrer">AgentKit 控制台</a>。</p></li><li><p>为准备好的后端 <a href="https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/gateway/mcpservice/create" target="_blank" rel="noreferrer">创建 MCP 服务</a>。</p></li><li><p>获取到创建后的 MCP 服务 Endpoint 和 ApiKey。会看到以下类似的输出：</p></li></ol><blockquote><p><code>httpUrl</code>即为 MCP 服务的 Endpoint，<code>Authorization</code> 即为 ApiKey。</p></blockquote><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;mcpServers&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;create-http-334df4&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;httpUrl&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;https://sd4fc6lpoh486npgcaav0.apigateway-cn-beijing.volceapi.com/mcp/create-http-334df4&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;headers&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">        &quot;Authorization&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Bearer P66l-rpaLbxxxxxxxxxxxxxxo2PQ&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">      }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><h2 id="第三步-设置环境环境变量-运行-agent" tabindex="-1">第三步：设置环境环境变量，运行 Agent <a class="header-anchor" href="#第三步-设置环境环境变量-运行-agent" aria-label="Permalink to &quot;第三步：设置环境环境变量，运行 Agent&quot;">​</a></h2><p>环境变量配置</p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">export</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> MCP_ENDPOINT</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{{第三步中获取的Endpoint}}</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">export</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> MCP_AUTH_KEY</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{{第三步中获取的ApiKey}}</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">export</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> API_KEY</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{{方舟的APIKEY}}</span></span></code></pre></div><p>代码示例</p><blockquote><p>代码示例中，我们使用 VeADK 框架，创建了一个简单的智能体，用于调用 MCP 服务。</p></blockquote><div class="language-python vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">python</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">import</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> logging</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">from</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> veadk </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">import</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> Agent, Runner</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">from</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> veadk.config </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">import</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> getenv</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">from</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> agentkit.apps </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">import</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> AgentkitSimpleApp</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">from</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> google.adk.tools.mcp_tool.mcp_toolset </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">import</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> MCPToolset, StreamableHTTPConnectionParams</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">logger </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> logging.getLogger(</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">__name__</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">url </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> getenv(</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;MCP_ENDPOINT&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">mcp_auth_key </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> getenv(</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;MCP_AUTH_KEY&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">apikey </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> getenv(</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;API_KEY&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">mcp_ecs_toolset </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> MCPToolset(</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">        connection_params</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">StreamableHTTPConnectionParams(</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">        url</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">url,</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">        headers</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Authorization&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">f</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Bearer </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">{</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">mcp_auth_key</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">}</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    ),</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">app </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> AgentkitSimpleApp()</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">root_agent </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> Agent(</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">    name</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;ecs_helper&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">    model_name</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;doubao-1-5-pro-256k-250115&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">    instruction</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&#39;&#39;&#39;</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">        Help user find ECS instances and their details.</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">    &#39;&#39;&#39;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">    description</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;ECS Helper Agent&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">    tools</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">[mcp_ecs_toolset]</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">runner </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> Runner(</span><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">agent</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">root_agent)</span></span>
<span class="line"></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">@app.entrypoint</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">async</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;"> def</span><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;"> run</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">(payload: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">dict</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">, headers: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">dict</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">) -&gt; </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">str</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">:</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    prompt </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> payload[</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;prompt&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">]</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    user_id </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> headers[</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;user_id&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">]</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    session_id </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> headers[</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;session_id&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">]</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    logger.info(</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">        f</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Running agent with prompt: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">{</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">prompt</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">}</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">, user_id: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">{</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">user_id</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">}</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">, session_id: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">{</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">session_id</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">}</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    )</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    </span></span>
<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;">    # 运行智能体，自动处理工具调用</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    response </span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;"> await</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> runner.run(</span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">        messages</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">prompt, </span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">        user_id</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">user_id, </span></span>
<span class="line"><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">        session_id</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">session_id</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    )</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    logger.info(</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">f</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Run response: </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">{</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">response</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">}</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">    return</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> response</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">@app.ping</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">def</span><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;"> ping</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">() -&gt; </span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">str</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">:</span></span>
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">    &quot;&quot;&quot;健康检查接口&quot;&quot;&quot;</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">    return</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;pong!&quot;</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">if</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> __name__</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;"> ==</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;__main__&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">:</span></span>
<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;">    # 启动本地开发服务器</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    app.run(</span><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">host</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;0.0.0.0&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">, </span><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">port</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">8000</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span></code></pre></div><p>执行请求</p><div class="language-curl vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">curl</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>curl --location &#39;http://localhost:8000/invoke&#39; \\</span></span>
<span class="line"><span>  --header &#39;Content-Type: application/json&#39; \\</span></span>
<span class="line"><span>  --header &#39;user_id: veadk-test&#39; \\</span></span>
<span class="line"><span>  --header &#39;session_id: local_session&#39; \\</span></span>
<span class="line"><span>  --data &#39;{&quot;prompt&quot;: &quot;分析下我的ecs实例&quot;}&#39;</span></span></code></pre></div><p>运行结果</p><div class="language-text vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">text</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>2025-10-24 20:17:33 | INFO | ark_veauth.py:25 - Fetching ARK token...</span></span>
<span class="line"><span>2025-10-24 20:17:33 | INFO | agent.py:118 - Model extra config: {&#39;extra_headers&#39;: {&#39;x-is-encrypted&#39;: &#39;true&#39;, &#39;veadk-source&#39;: &#39;veadk&#39;, &#39;veadk-version&#39;: &#39;0.2.13&#39;, &#39;User-Agent&#39;: &#39;VeADK/0.2.13&#39;, &#39;X-Client-Request-Id&#39;: &#39;veadk/0.2.13&#39;}, &#39;extra_body&#39;: {&#39;caching&#39;: {&#39;type&#39;: &#39;enabled&#39;}, &#39;expire_at&#39;: 1761311852}}</span></span>
<span class="line"><span>2025-10-24 20:17:33 | DEBUG | agent.py:127 - LiteLLM client created with config: {&#39;extra_headers&#39;: {&#39;x-is-encrypted&#39;: &#39;true&#39;, &#39;veadk-source&#39;: &#39;veadk&#39;, &#39;veadk-version&#39;: &#39;0.2.13&#39;, &#39;User-Agent&#39;: &#39;VeADK/0.2.13&#39;, &#39;X-Client-Request-Id&#39;: &#39;veadk/0.2.13&#39;}, &#39;extra_body&#39;: {&#39;caching&#39;: {&#39;type&#39;: &#39;enabled&#39;}, &#39;expire_at&#39;: 1761311852}}</span></span>
<span class="line"><span>2025-10-24 20:17:33 | INFO | agent.py:153 - VeADK version: 0.2.13</span></span>
<span class="line"><span>2025-10-24 20:17:33 | INFO | agent.py:155 - Agent \`ecs_helper\` init done.</span></span>
<span class="line"><span>2025-10-24 20:17:33 | DEBUG | agent.py:156 - Agent: {&#39;name&#39;: &#39;ecs_helper&#39;, &#39;tools&#39;: [&lt;google.adk.tools.mcp_tool.mcp_toolset.MCPToolset object at 0x7f8b4f24b9b0&gt;], &#39;model_name&#39;: &#39;doubao-1-5-pro-256k-250115&#39;, &#39;model_api_base&#39;: &#39;https://ark.cn-beijing.volces.com/api/v3/&#39;}</span></span>
<span class="line"><span>2025-10-24 20:17:33 | WARNING | runner.py:198 - No short term memory or session service provided, use an in-memory one instead.</span></span>
<span class="line"><span>2025-10-24 20:17:33 | INFO | runner.py:217 - No long term memory provided.</span></span>
<span class="line"><span>INFO:     Started server process [1330124]</span></span>
<span class="line"><span>INFO:     Waiting for application startup.</span></span>
<span class="line"><span>INFO:     Application startup complete.</span></span>
<span class="line"><span>INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)</span></span>
<span class="line"><span>2025-10-24 20:18:35 | INFO | runner.py:250 - Run config: speech_config=None response_modalities=None save_input_blobs_as_artifacts=False support_cfc=False streaming_mode=&lt;StreamingMode.NONE: None&gt; output_audio_transcription=AudioTranscriptionConfig() input_audio_transcription=AudioTranscriptionConfig() realtime_input_config=None enable_affective_dialog=None proactivity=None session_resumption=None context_window_compression=None save_live_audio=False max_llm_calls=100</span></span>
<span class="line"><span>2025-10-24 20:18:35 | DEBUG | runner.py:265 - Auto create session: local_session, user_id: veadk-test, app_name: veadk_default_app</span></span>
<span class="line"><span>2025-10-24 20:18:38 | DEBUG | runner.py:280 - Function call: id=&#39;call_xbyfcvc86wc26mbxz39vst12&#39; args={&#39;region&#39;: &#39;cn-beijing&#39;, &#39;needNum&#39;: 10} name=&#39;describe_instances&#39;</span></span>
<span class="line"><span>2025-10-24 20:19:14 | DEBUG | runner.py:288 - Event output: 以下是您的ECS实例详情：</span></span>
<span class="line"><span>1. **实例1**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye7irm2sqobw80cqxd40</span></span>
<span class="line"><span>    - **创建时间**：2025-10-23T21:36:31+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>2. **实例2**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye7ipm0dtsqc6imh310d</span></span>
<span class="line"><span>    - **创建时间**：2025-10-23T21:05:44+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Debian 12 64 bit</span></span>
<span class="line"><span>    - **镜像ID**：image-ydzwsvy72n46nmxzvafi</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>3. **实例3**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye7ilsbbpcbw80ca2ymj</span></span>
<span class="line"><span>    - **创建时间**：2025-10-23T20:06:54+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>4. **实例4**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye7fg1hgqoxjd1utrfy3</span></span>
<span class="line"><span>    - **创建时间**：2025-10-22T14:57:49+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>5. **实例5**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye5ejwoow0cva4fqydfc</span></span>
<span class="line"><span>    - **创建时间**：2025-09-24T14:25:37+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>6. **实例6**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye5ejub08wbw80bpd7hr</span></span>
<span class="line"><span>    - **创建时间**：2025-09-24T14:24:35+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>7. **实例7**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye5e5jyq68bw80c889i5</span></span>
<span class="line"><span>    - **创建时间**：2025-09-24T10:44:54+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>8. **实例8**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye5c4jbx8gqc6ily6b30</span></span>
<span class="line"><span>    - **创建时间**：2025-09-23T16:02:05+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Windows Server 2022 Datacenter Edition 64 - bit Chinese</span></span>
<span class="line"><span>    - **镜像ID**：image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>9. **实例9**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye5c4end34xjd1umbfns</span></span>
<span class="line"><span>    - **创建时间**：2025-09-23T16:00:05+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Debian 12 64 bit</span></span>
<span class="line"><span>    - **镜像ID**：image-ydzwsvfxhokhx11pdmlv</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span>10. **实例10**：</span></span>
<span class="line"><span>    - **实例ID**：i-ye5blj0xdsxjd1tk1vfh</span></span>
<span class="line"><span>    - **创建时间**：2025-09-23T11:09:46+08:00</span></span>
<span class="line"><span>    - **计费方式**：PostPaid（按量计费）</span></span>
<span class="line"><span>    - **实例规格**：ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**：4核（核心数2，每核心线程数2）</span></span>
<span class="line"><span>    - **内存**：8192MB</span></span>
<span class="line"><span>    - **操作系统**：Debian 12 64 bit</span></span>
<span class="line"><span>    - **镜像ID**：image-ydzwsvfxhokhx11pdmlv</span></span>
<span class="line"><span>    - **状态**：RUNNING（运行中）</span></span>
<span class="line"><span>    - **所属可用区**：cn - beijing - a</span></span>
<span class="line"><span></span></span>
<span class="line"><span>以上10个实例均为按量计费，规格为ecs.e-c1m2.xlarge ，且大部分使用Windows Server 2022 Datacenter Edition 64 - bit Chinese操作系统，少数使用Debian 12 64 bit操作系统，目前状态均为运行中，所属可用区为cn - beijing - a 。若您还需要进一步分析或有其他操作需求，可继续向我提问。</span></span></code></pre></div>`,25)])])}const o=a(e,[["render",l]]);export{E as __pageData,o as default};
