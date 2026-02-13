import{_ as a,c as n,o as i,ag as p}from"./chunks/framework.CA4hJK0u.js";const d=JSON.parse('{"title":"AgentKit MCP Quick Start","description":"","frontmatter":{},"headers":[],"relativePath":"en/content/8.mcp/2.mcp_quickstart.md","filePath":"en/content/8.mcp/2.mcp_quickstart.md","lastUpdated":1770735100000}'),e={name:"en/content/8.mcp/2.mcp_quickstart.md"};function t(l,s,h,k,r,o){return i(),n("div",null,[...s[0]||(s[0]=[p(`<h1 id="agentkit-mcp-quick-start" tabindex="-1">AgentKit MCP Quick Start <a class="header-anchor" href="#agentkit-mcp-quick-start" aria-label="Permalink to &quot;AgentKit MCP Quick Start&quot;">​</a></h1><h2 id="prerequisites" tabindex="-1">Prerequisites <a class="header-anchor" href="#prerequisites" aria-label="Permalink to &quot;Prerequisites&quot;">​</a></h2><p>Before you begin, you need to prepare:</p><ol><li><p><strong>AccessKey &amp; SecretKey</strong> from a Volcengine account with AgentKit enabled</p><blockquote><p><strong>Tip:</strong> Make sure the AccessKey has <code>AgentKitFullAccess</code> permission.</p></blockquote></li><li><p><strong>MCP Service</strong> (can be deployed on VeFaaS or publicly accessible locations)</p><ul><li>Existing backend services that support MCP</li><li>Existing HTTP services with Swagger API definition JSON. See <a href="https://swagger.io/" target="_blank" rel="noreferrer">Swagger</a> for details.</li></ul></li><li><p><strong>Python 3.10+</strong> installed</p></li><li><p><strong>Ark API Key</strong></p></li></ol><h2 id="step-1-configure-local-environment" tabindex="-1">Step 1: Configure Local Environment <a class="header-anchor" href="#step-1-configure-local-environment" aria-label="Permalink to &quot;Step 1: Configure Local Environment&quot;">​</a></h2><blockquote><p>You can use <code>uv</code> or <code>python3 -m venv</code> for virtual environment management. Below we&#39;ll use <code>uv</code> as an example.</p><p><code>uv</code> installation reference: <a href="https://docs.astral.sh/uv/getting-started/installation/" target="_blank" rel="noreferrer">uv install</a></p></blockquote><p><strong>Virtual Environment Setup</strong></p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">mkdir</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> agentkit-mcp-quickstart</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">cd</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> agentkit-mcp-quickstart</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">uv</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> venv</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> --python</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> 3.12.0</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">source</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> .venv/bin/activate</span></span></code></pre></div><p><strong>Install Dependencies</strong></p><blockquote><p>You can specify a mirror source with <code>--index</code> to speed up installation.</p></blockquote><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">uv</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> pip</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> install</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> veadk-python</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">uv</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> pip</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> install</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> google-adk</span></span>
<span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">pip</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> install</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> agentkit-sdk-python</span></span></code></pre></div><h2 id="step-2-create-agentkit-mcp" tabindex="-1">Step 2: Create AgentKit MCP <a class="header-anchor" href="#step-2-create-agentkit-mcp" aria-label="Permalink to &quot;Step 2: Create AgentKit MCP&quot;">​</a></h2><ol><li><p>Log in to the <a href="https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/gateway/mcpservice" target="_blank" rel="noreferrer">AgentKit Console</a> on Volcengine.</p></li><li><p><a href="https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/gateway/mcpservice/create" target="_blank" rel="noreferrer">Create an MCP Service</a> for your prepared backend.</p></li><li><p>Obtain the MCP Service Endpoint and ApiKey after creation. You will see output similar to:</p><blockquote><p><code>httpUrl</code> is the MCP Service Endpoint, <code>Authorization</code> is the ApiKey.</p></blockquote></li></ol><div class="language-json vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">json</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  &quot;mcpServers&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">    &quot;create-http-334df4&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;httpUrl&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;https://sd4fc6lpoh486npgcaav0.apigateway-cn-beijing.volceapi.com/mcp/create-http-334df4&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">,</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">      &quot;headers&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: {</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">        &quot;Authorization&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">: </span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;Bearer P66l-rpaLbxxxxxxxxxxxxxxo2PQ&quot;</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">      }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">  }</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">}</span></span></code></pre></div><h2 id="step-3-set-environment-variables-and-run-agent" tabindex="-1">Step 3: Set Environment Variables and Run Agent <a class="header-anchor" href="#step-3-set-environment-variables-and-run-agent" aria-label="Permalink to &quot;Step 3: Set Environment Variables and Run Agent&quot;">​</a></h2><p><strong>Environment Variable Configuration</strong></p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">export</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> MCP_ENDPOINT</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{{Endpoint obtained in Step 2}}</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">export</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> MCP_AUTH_KEY</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{{ApiKey obtained in Step 2}}</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">export</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> API_KEY</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">{{Ark API Key}}</span></span></code></pre></div><p><strong>Code Example</strong></p><blockquote><p>In the code example below, we use the VeADK framework to create a simple agent for calling MCP services.</p></blockquote><div class="language-python vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">python</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">import</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;"> logging</span></span>
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
<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;">    # Run agent, automatically handling tool calls</span></span>
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
<span class="line"><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">    &quot;&quot;&quot;Health check endpoint&quot;&quot;&quot;</span></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">    return</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;pong!&quot;</span></span>
<span class="line"></span>
<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">if</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> __name__</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;"> ==</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &quot;__main__&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">:</span></span>
<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;">    # Start local development server</span></span>
<span class="line"><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">    app.run(</span><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">host</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;">&quot;0.0.0.0&quot;</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">, </span><span style="--shiki-light:#E36209;--shiki-dark:#FFAB70;">port</span><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">=</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">8000</span><span style="--shiki-light:#24292E;--shiki-dark:#E1E4E8;">)</span></span></code></pre></div><p><strong>Execute Request</strong></p><div class="language-bash vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span style="--shiki-light:#6F42C1;--shiki-dark:#B392F0;">curl</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> --location</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;http://localhost:8000/invoke&#39;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  --header</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;Content-Type: application/json&#39;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  --header</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;user_id: veadk-test&#39;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  --header</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;session_id: local_session&#39;</span><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;"> \\</span></span>
<span class="line"><span style="--shiki-light:#005CC5;--shiki-dark:#79B8FF;">  --data</span><span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &#39;{&quot;prompt&quot;: &quot;Analyze my ECS instances&quot;}&#39;</span></span></code></pre></div><p><strong>Execution Result</strong></p><div class="language-text vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">text</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>2025-10-24 20:17:33 | INFO | ark_veauth.py:25 - Fetching ARK token...</span></span>
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
<span class="line"><span>2025-10-24 20:19:14 | DEBUG | runner.py:288 - Event output: Here are your ECS instance details:</span></span>
<span class="line"><span>1. **Instance 1**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye7irm2sqobw80cqxd40</span></span>
<span class="line"><span>    - **Creation Time**: 2025-10-23T21:36:31+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>2. **Instance 2**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye7ipm0dtsqc6imh310d</span></span>
<span class="line"><span>    - **Creation Time**: 2025-10-23T21:05:44+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Debian 12 64 bit</span></span>
<span class="line"><span>    - **Image ID**: image-ydzwsvy72n46nmxzvafi</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>3. **Instance 3**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye7ilsbbpcbw80ca2ymj</span></span>
<span class="line"><span>    - **Creation Time**: 2025-10-23T20:06:54+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>4. **Instance 4**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye7fg1hgqoxjd1utrfy3</span></span>
<span class="line"><span>    - **Creation Time**: 2025-10-22T14:57:49+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>5. **Instance 5**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye5ejwoow0cva4fqydfc</span></span>
<span class="line"><span>    - **Creation Time**: 2025-09-24T14:25:37+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>6. **Instance 6**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye5ejub08wbw80bpd7hr</span></span>
<span class="line"><span>    - **Creation Time**: 2025-09-24T14:24:35+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>7. **Instance 7**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye5e5jyq68bw80c889i5</span></span>
<span class="line"><span>    - **Creation Time**: 2025-09-24T10:44:54+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>8. **Instance 8**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye5c4jbx8gqc6ily6b30</span></span>
<span class="line"><span>    - **Creation Time**: 2025-09-23T16:02:05+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Windows Server 2022 Datacenter Edition 64-bit Chinese</span></span>
<span class="line"><span>    - **Image ID**: image-ye5907jc6ikhx1exow93</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>9. **Instance 9**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye5c4end34xjd1umbfns</span></span>
<span class="line"><span>    - **Creation Time**: 2025-09-23T16:00:05+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Debian 12 64 bit</span></span>
<span class="line"><span>    - **Image ID**: image-ydzwsvfxhokhx11pdmlv</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span>10. **Instance 10**:</span></span>
<span class="line"><span>    - **Instance ID**: i-ye5blj0xdsxjd1tk1vfh</span></span>
<span class="line"><span>    - **Creation Time**: 2025-09-23T11:09:46+08:00</span></span>
<span class="line"><span>    - **Billing Method**: PostPaid (Pay-as-you-go)</span></span>
<span class="line"><span>    - **Instance Type**: ecs.e-c1m2.xlarge</span></span>
<span class="line"><span>    - **CPU**: 4 cores (2 cores, 2 threads per core)</span></span>
<span class="line"><span>    - **Memory**: 8192MB</span></span>
<span class="line"><span>    - **OS**: Debian 12 64 bit</span></span>
<span class="line"><span>    - **Image ID**: image-ydzwsvfxhokhx11pdmlv</span></span>
<span class="line"><span>    - **Status**: RUNNING</span></span>
<span class="line"><span>    - **Availability Zone**: cn-beijing-a</span></span>
<span class="line"><span></span></span>
<span class="line"><span>All 10 instances are pay-as-you-go with type ecs.e-c1m2.xlarge. Most use Windows Server 2022 Datacenter Edition 64-bit Chinese, with a few using Debian 12 64-bit. All are currently running in availability zone cn-beijing-a. If you need further analysis or have other operation requirements, feel free to ask.</span></span></code></pre></div>`,24)])])}const g=a(e,[["render",t]]);export{d as __pageData,g as default};
