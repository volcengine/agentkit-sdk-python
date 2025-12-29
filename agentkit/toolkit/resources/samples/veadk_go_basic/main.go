// Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//	http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/volcengine/veadk-go/apps"
	"github.com/volcengine/veadk-go/apps/simple_app"
	"google.golang.org/adk/agent"
)

func main() {
	ctx := context.Background()

	a, err := buildSampleAgent()
	if err != nil {
		log.Printf("buildSampleAgent failed: %v", err)
		return
	}

	app := simple_app.NewAgentkitSimpleApp(apps.ApiConfig{
		Port:         8000,
		WriteTimeout: 120 * time.Second,
		ReadTimeout:  120 * time.Second,
		IdleTimeout:  600 * time.Second,
	})

	err = app.Run(ctx, &apps.RunConfig{
		AgentLoader: agent.NewSingleLoader(a),
	})
	if err != nil {
		fmt.Printf("Run failed: %v", err)
	}
}
