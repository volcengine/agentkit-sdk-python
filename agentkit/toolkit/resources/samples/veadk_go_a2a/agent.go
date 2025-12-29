// Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	veagent "github.com/volcengine/veadk-go/agent/llmagent"
	"google.golang.org/adk/agent"
	"google.golang.org/adk/agent/llmagent"
)

func buildSampleAgent() (agent.Agent, error) {
	agentName := "{{ agent_name | default('VeADK-Go-Agent') }}"
	var description string
	{% if description %}description = `{{ description }}`{% else %}description = ""{% endif %}

	var instruction string
	{% if system_prompt %}instruction = `{{ system_prompt }}`{% else %}instruction = ""{% endif %}

	cfg := &veagent.Config{
		Config: llmagent.Config{
			Name:        agentName,
			Description: description,
			Instruction: instruction,
		},
		ModelExtraConfig: map[string]any{
			"extra_body": map[string]any{
				"thinking": map[string]string{
					"type": "disabled",
				},
			},
		},
	}
	return veagent.New(cfg)
}
