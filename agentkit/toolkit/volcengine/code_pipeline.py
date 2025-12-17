# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests

import logging

from agentkit.utils.ve_sign import ve_request
from agentkit.platform import (
    VolcConfiguration,
)

logger = logging.getLogger(__name__)


class VeCodePipeline:
    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
    ) -> None:
        # Use provided region or None to trigger auto-detection in VolcConfiguration
        config = VolcConfiguration(
            access_key=access_key or None,
            secret_key=secret_key or None,
            region=region or None,
        )

        # If credentials not fully provided, resolve them
        if not any([access_key, secret_key]):
            creds = config.get_service_credentials("cp")
            self.volcengine_access_key = creds.access_key
            self.volcengine_secret_key = creds.secret_key
        elif not all([access_key, secret_key]):
            raise ValueError(
                "Error create cp instance: missing access key or secret key",
            )
        else:
            self.volcengine_access_key = access_key
            self.volcengine_secret_key = secret_key

        endpoint = config.get_service_endpoint("cp")

        self.region = endpoint.region
        self.service = endpoint.service
        self.version = endpoint.api_version
        self.host = endpoint.host
        self.content_type = "application/json"

    def _get_default_workspace(self) -> str:
        logger.info("Getting default workspace...")

        res = ve_request(
            request_body={},
            action="GetDefaultWorkspaceInner",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            logger.info(
                f"Default workspace retrieved successfully, workspace id {res['Result']['Id']}, res: {res}",
            )
            return res["Result"]["Id"]
        except KeyError:
            raise Exception(f"Get default workspace failed: {res}")

    def create_workspace(
        self,
        name: str,
        visibility: str,
        description: str = "",
        visible_users: list[dict[str, int]] | None = None,
    ) -> str:
        """
        Create a new workspace.

        Args:
            name: The name of the workspace (required)
            visibility: Visibility setting - "Account" (visible to all users) or "Specified" (visible to specified users only)
            description: Description of the workspace (optional)
            visible_users: List of users who can see the workspace (optional, each user dict contains AccountId and UserId)

        Returns:
            The workspace ID

        Raises:
            Exception: If workspace creation fails

        Example:
            # Create a workspace visible to all users
            workspace_id = cp.create_workspace(
                name="my-workspace",
                visibility="Account"
            )

            # Create a workspace visible to specific users
            workspace_id = cp.create_workspace(
                name="my-workspace",
                visibility="Specified",
                description="My demo workspace",
                visible_users=[{"AccountId": 24506499, "UserId": 0}]
            )
        """
        logger.info(f"Creating workspace: {name}...")

        request_body = {
            "Name": name,
            "Visibility": visibility,
        }

        if description:
            request_body["Description"] = description

        if visible_users:
            request_body["VisibleUsers"] = visible_users

        res = ve_request(
            request_body=request_body,
            action="CreateWorkspace",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            workspace_id = res["Result"]["Id"]
            logger.info(f"Workspace created successfully, workspace ID: {workspace_id}")
            return workspace_id
        except KeyError:
            raise Exception(f"Create workspace failed: {res}")

    def list_workspaces(
        self,
        page_number: int = 1,
        page_size: int = 10,
        name_filter: str = "",
        workspace_ids: list[str] | None = None,
    ) -> dict:
        """
        List workspaces with filtering options.

        Args:
            page_number: Page number for pagination (starts from 1)
            page_size: Number of items per page
            name_filter: Filter workspaces by name (fuzzy search, optional)
            workspace_ids: Filter by specific workspace IDs (optional)

        Returns:
            The response containing workspace items and pagination info:
            {
                "Items": [...],     # List of workspace objects
                "PageSize": 10,     # Current page size
                "PageNumber": 1,    # Current page number
                "TotalCount": 1     # Total number of workspaces
            }

        Raises:
            Exception: If the request fails

        Example:
            # List all workspaces
            result = cp.list_workspaces()

            # List workspaces with name filter
            result = cp.list_workspaces(name_filter="work")

            # List specific workspaces by IDs
            result = cp.list_workspaces(workspace_ids=["2c7a85e4ac034eb790b096705694****"])
        """
        logger.info("Listing workspaces...")

        request_body = {
            "PageNumber": page_number,
            "PageSize": page_size,
        }

        # Add filter if name_filter or workspace_ids are provided
        if name_filter or workspace_ids:
            request_body["Filter"] = {}
            if name_filter:
                request_body["Filter"]["Name"] = name_filter
            if workspace_ids:
                request_body["Filter"]["Ids"] = workspace_ids

        res = ve_request(
            request_body=request_body,
            action="ListWorkspaces",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            result = res["Result"]
            total_count = result.get("TotalCount", 0)
            items_count = len(result.get("Items", []))
            logger.info(
                f"Successfully listed workspaces, found {total_count} total, {items_count} in current page"
            )
            return result
        except KeyError:
            raise Exception(f"List workspaces failed: {res}")

    def get_workspaces_by_name(
        self,
        name: str,
        page_number: int = 1,
        page_size: int = 10,
    ) -> dict:
        """
        Get workspaces filtered by name.

        This is a convenience method that wraps list_workspaces with a name filter.

        Args:
            name: The name to filter workspaces by (fuzzy search)
            page_number: Page number for pagination (starts from 1)
            page_size: Number of items per page

        Returns:
            The response containing workspace items and pagination info:
            {
                "Items": [...],     # List of workspace objects matching the name
                "PageSize": 10,     # Current page size
                "PageNumber": 1,    # Current page number
                "TotalCount": 1     # Total number of matching workspaces
            }

        Raises:
            Exception: If the request fails

        Example:
            # Get workspaces with name containing "work"
            result = cp.get_workspaces_by_name(name="work")
            for workspace in result["Items"]:
                print(f"Workspace: {workspace['Name']} (ID: {workspace['Id']})")
        """
        logger.info(f"Getting workspaces by name: {name}...")
        return self.list_workspaces(
            page_number=page_number,
            page_size=page_size,
            name_filter=name,
        )

    def workspace_exists_by_name(self, name: str) -> bool:
        """
        Check if a workspace exists by name.

        Args:
            name: The workspace name to check

        Returns:
            True if at least one workspace with the given name exists, False otherwise

        Example:
            # Check if workspace exists
            if cp.workspace_exists_by_name("my-workspace"):
                print("Workspace exists")
            else:
                print("Workspace does not exist")
        """
        logger.info(f"Checking if workspace exists by name: {name}...")
        result = self.get_workspaces_by_name(name=name, page_size=1)
        exists = result.get("TotalCount", 0) > 0
        logger.info(f"Workspace '{name}' exists: {exists}")
        return exists

    def _create_pipeline(
        self,
        workspace_id: str,
        pipeline_name: str,
        spec: str,
        parameters: list[dict[str, str]] | None = None,
    ) -> str:
        logger.info("Creating pipeline...")
        res = ve_request(
            request_body={
                "WorkspaceId": workspace_id,
                "Name": pipeline_name,
                "Spec": spec,
                "Parameters": parameters or [],
            },
            action="CreatePipeline",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            logger.info(
                f"Pipeline created successfully, pipeline id {res['Result']['Id']}",
            )
            return res["Result"]["Id"]
        except KeyError:
            raise Exception(f"Create pipeline failed: {res}")

    def run_pipeline(
        self,
        workspace_id: str,
        pipeline_id: str,
        description: str = "",
        parameters: list[dict[str, str]] | None = None,
        resources: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Run a pipeline with the given parameters.

        Args:
            workspace_id: The workspace ID
            pipeline_id: The pipeline ID to run
            description: Description of this pipeline run
            parameters: List of parameters with key-value pairs
            resources: List of resources with ResourceId and Reference

        Returns:
            The pipeline run ID

        Raises:
            Exception: If the pipeline run fails
        """
        logger.info(f"Running pipeline {pipeline_id} in workspace {workspace_id}...")

        request_body = {
            "WorkspaceId": workspace_id,
            "Id": pipeline_id,
        }

        if description:
            request_body["Description"] = description

        if parameters:
            request_body["Parameters"] = parameters

        if resources:
            request_body["Resources"] = resources

        res = ve_request(
            request_body=request_body,
            action="RunPipeline",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            run_id = res["Result"]["Id"]
            logger.info(f"Pipeline run started successfully, run ID: {run_id}")
            return run_id
        except KeyError:
            raise Exception(f"Run pipeline failed: {res}")

    def run_pipeline_with_defaults(
        self,
        pipeline_id: str,
        description: str = "",
        parameters: list[dict[str, str]] | None = None,
        resources: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Run a pipeline using the default workspace.

        Args:
            pipeline_id: The pipeline ID to run
            description: Description of this pipeline run
            parameters: List of parameters with key-value pairs
            resources: List of resources with ResourceId and Reference

        Returns:
            The pipeline run ID

        Raises:
            Exception: If the pipeline run fails
        """
        workspace_id = self._get_default_workspace()
        return self.run_pipeline(
            workspace_id=workspace_id,
            pipeline_id=pipeline_id,
            description=description,
            parameters=parameters,
            resources=resources,
        )

    def list_pipeline_runs(
        self,
        workspace_id: str,
        pipeline_id: str,
        next_token: str = "",
        max_results: int = 10,
        statuses: list[str] | None = None,
        run_ids: list[str] | None = None,
    ) -> dict:
        """
        List pipeline runs with filtering options.

        Args:
            workspace_id: The workspace ID
            pipeline_id: The pipeline ID to query
            next_token: Pagination token for next page
            max_results: Maximum number of results to return
            statuses: Filter by run statuses (e.g., ["InProgress", "Succeeded", "Failed"])
            run_ids: Filter by specific run IDs

        Returns:
            The response containing pipeline runs and next token

        Raises:
            Exception: If the request fails
        """

        request_body = {
            "WorkspaceId": workspace_id,
            "PipelineId": pipeline_id,
            "MaxResults": max_results,
        }

        if next_token:
            request_body["NextToken"] = next_token

        if statuses or run_ids:
            request_body["Filter"] = {}
            if statuses:
                request_body["Filter"]["Statuses"] = statuses
            if run_ids:
                request_body["Filter"]["Ids"] = run_ids

        res = ve_request(
            request_body=request_body,
            action="ListPipelineRuns",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            result = res["Result"]
            return result
        except KeyError:
            raise Exception(f"List pipeline runs failed: {res}")

    def get_pipeline_run_status(
        self,
        workspace_id: str,
        pipeline_id: str,
        run_id: str,
    ) -> str:
        """
        Get the status of a specific pipeline run.

        Args:
            workspace_id: The workspace ID
            pipeline_id: The pipeline ID
            run_id: The pipeline run ID to query

        Returns:
            The status of the pipeline run

        Raises:
            Exception: If the request fails or run not found
        """

        # List pipeline runs with specific run ID filter
        result = self.list_pipeline_runs(
            workspace_id=workspace_id,
            pipeline_id=pipeline_id,
            run_ids=[run_id],
            max_results=1,
        )

        items = result.get("Items", [])
        if not items:
            raise Exception(f"Pipeline run {run_id} not found")

        status = items[0].get("Status", "Unknown")
        return status

    def list_pipelines(
        self,
        workspace_id: str,
        page_number: int = 1,
        page_size: int = 10,
        name_filter: str = "",
        pipeline_ids: list[str] | None = None,
    ) -> dict:
        """
        List pipelines in a workspace with filtering options.

        Args:
            workspace_id: The workspace ID to query pipelines from
            page_number: Page number for pagination (starts from 1)
            page_size: Number of items per page (max 100)
            name_filter: Filter pipelines by name (fuzzy search, optional)
            pipeline_ids: Filter by specific pipeline IDs (optional)

        Returns:
            The response containing pipeline items and pagination info:
            {
                "Items": [...],  # List of pipeline objects
                "PageSize": 10,   # Current page size
                "PageNumber": 1,  # Current page number
                "TotalCount": 1   # Total number of pipelines
            }

        Raises:
            Exception: If the request fails

        Example:
            # List all pipelines in workspace
            result = cp.list_pipelines(workspace_id="ws-123")

            # List pipelines with name filter
            result = cp.list_pipelines(workspace_id="ws-123", name_filter="test")

            # List specific pipelines by IDs
            result = cp.list_pipelines(workspace_id="ws-123", pipeline_ids=["pipe-1", "pipe-2"])
        """
        logger.info(f"Listing pipelines in workspace {workspace_id}...")

        request_body = {
            "WorkspaceId": workspace_id,
            "PageNumber": page_number,
            "PageSize": page_size,
        }

        # Add filter if name_filter or pipeline_ids are provided
        if name_filter or pipeline_ids:
            request_body["Filter"] = {}
            if name_filter:
                request_body["Filter"]["Name"] = name_filter
            if pipeline_ids:
                request_body["Filter"]["Ids"] = pipeline_ids

        res = ve_request(
            request_body=request_body,
            action="ListPipelines",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            result = res["Result"]
            total_count = result.get("TotalCount", 0)
            items_count = len(result.get("Items", []))
            logger.info(
                f"Successfully listed pipelines, found {total_count} total, {items_count} in current page"
            )
            return result
        except KeyError:
            raise Exception(f"List pipelines failed: {res}")

    def list_pipelines_with_defaults(
        self,
        page_number: int = 1,
        page_size: int = 10,
        name_filter: str = "",
        pipeline_ids: list[str] | None = None,
    ) -> dict:
        """
        List pipelines using the default workspace.

        Args:
            page_number: Page number for pagination (starts from 1)
            page_size: Number of items per page (max 100)
            name_filter: Filter pipelines by name (fuzzy search, optional)
            pipeline_ids: Filter by specific pipeline IDs (optional)

        Returns:
            The response containing pipeline items and pagination info

        Raises:
            Exception: If the request fails

        Example:
            # List all pipelines in default workspace
            result = cp.list_pipelines_with_defaults()

            # Search for pipelines containing "test" in name
            result = cp.list_pipelines_with_defaults(name_filter="test")
        """
        workspace_id = self._get_default_workspace()
        return self.list_pipelines(
            workspace_id=workspace_id,
            page_number=page_number,
            page_size=page_size,
            name_filter=name_filter,
            pipeline_ids=pipeline_ids,
        )

    def list_pipeline_run_stages_inner(
        self,
        workspace_id: str,
        pipeline_id: str,
        pipeline_run_id: str,
    ) -> dict:
        """
        List all stages of a pipeline run with detailed task and step information.

        Args:
            workspace_id: The workspace ID
            pipeline_id: The pipeline ID
            pipeline_run_id: The pipeline run ID to query stages from

        Returns:
            The response containing stage items and context:
            {
                "Items": [
                    {
                        "Id": "...",
                        "Name": "...",
                        "DisplayName": "...",
                        "Status": "...",
                        "Tasks": [...]
                    }
                ],
                "context": {...}
            }

        Raises:
            Exception: If the request fails

        Example:
            # List pipeline run stages
            result = cp.list_pipeline_run_stages_inner(
                workspace_id="x",
                pipeline_id="x",
                pipeline_run_id="x"
            )

            # Access stage information
            for stage in result["Items"]:
                print(f"Stage: {stage['DisplayName']} - Status: {stage['Status']}")
                for task in stage["Tasks"]:
                    print(f"  Task: {task['DisplayName']} - Status: {task['Status']}")
        """
        logger.info(f"Listing pipeline run stages for run {pipeline_run_id}...")

        request_body = {
            "WorkspaceId": workspace_id,
            "PipelineId": pipeline_id,
            "PipelineRunId": pipeline_run_id,
        }

        res = ve_request(
            request_body=request_body,
            action="ListPipelineRunStagesInner",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            result = res["Result"]
            items_count = len(result.get("Items", []))
            logger.info(
                f"Successfully listed pipeline run stages, found {items_count} stages"
            )
            return result
        except KeyError:
            raise Exception(f"List pipeline run stages failed: {res}")

    def get_task_run_log_download_uri(
        self,
        workspace_id: str,
        pipeline_id: str,
        pipeline_run_id: str,
        task_run_id: str,
        task_id: str,
        step_name: str,
    ) -> str:
        """
        Get the download URI for task run logs.

        Args:
            workspace_id: The workspace ID
            pipeline_id: The pipeline ID
            pipeline_run_id: The pipeline run ID
            task_run_id: The task run ID
            task_id: The task ID
            step_name: The step name to get logs from

        Returns:
            The download URL for the task run logs

        Raises:
            Exception: If the request fails

        Example:
            # Get task run log download URI
            log_url = cp.get_task_run_log_download_uri(
                workspace_id="****",
                pipeline_id="****",
                pipeline_run_id="****",
                task_run_id="****",
                task_id="****",
                step_name="step-name"
            )
            print(f"Log URL: {log_url}")
        """
        logger.info(
            f"Getting task run log download URI for task run {task_run_id}, step {step_name}..."
        )

        request_body = {
            "WorkspaceId": workspace_id,
            "PipelineId": pipeline_id,
            "PipelineRunId": pipeline_run_id,
            "TaskRunId": task_run_id,
            "TaskId": task_id,
            "StepName": step_name,
        }

        res = ve_request(
            request_body=request_body,
            action="GetTaskRunLogDownloadURI",
            ak=self.volcengine_access_key,
            sk=self.volcengine_secret_key,
            service=self.service,
            version=self.version,
            region=self.region,
            host=self.host,
            content_type=self.content_type,
        )

        try:
            url = res["Result"]["Url"]
            logger.info("Successfully retrieved task run log download URI")
            return url
        except KeyError:
            raise Exception(f"Get task run log download URI failed: {res}")

    def download_and_merge_pipeline_logs(
        self,
        workspace_id: str,
        pipeline_id: str,
        pipeline_run_id: str,
        output_file: str = "pipeline_run.log",
    ) -> str:
        """
        Download and merge all step logs from a pipeline run into a single file.

        This function retrieves all stages, tasks, and steps from a pipeline run,
        downloads the log for each step, and merges them in chronological order.
        If a step log fails to download, it records the failure instead of raising an error.

        Args:
            workspace_id: The workspace ID
            pipeline_id: The pipeline ID
            pipeline_run_id: The pipeline run ID to download logs from
            output_file: The output file path for merged logs (default: "pipeline_run.log")

        Returns:
            The path to the merged log file

        Raises:
            Exception: If unable to retrieve pipeline run stages

        Example:
            # Download and merge all logs
            log_file = cp.download_and_merge_pipeline_logs(
                workspace_id="******",
                pipeline_id="******",
                pipeline_run_id="******",
                output_file="build_logs.log"
            )

            # Read and display first 100 lines
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[:100]:
                    print(line.rstrip())
        """
        logger.info(
            f"Downloading and merging logs for pipeline run {pipeline_run_id}..."
        )

        # Get all stages information
        try:
            stages_data = self.list_pipeline_run_stages_inner(
                workspace_id=workspace_id,
                pipeline_id=pipeline_id,
                pipeline_run_id=pipeline_run_id,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve pipeline run stages: {e}")
            raise

        # Open output file for writing
        with open(output_file, "w", encoding="utf-8") as out_file:
            # Write header information
            out_file.write("=" * 80 + "\n")
            out_file.write("PIPELINE RUN LOG\n")
            out_file.write("=" * 80 + "\n")
            out_file.write(f"Workspace ID:     {workspace_id}\n")
            out_file.write(f"Pipeline ID:      {pipeline_id}\n")
            out_file.write(f"Pipeline Run ID:  {pipeline_run_id}\n")
            out_file.write("=" * 80 + "\n\n")

            # Process each stage
            stages = stages_data.get("Items", [])
            total_steps = 0
            successful_downloads = 0
            failed_downloads = 0

            for stage_idx, stage in enumerate(stages, 1):
                stage_id = stage.get("Id", "unknown")
                stage_name = stage.get("Name", "unknown")
                stage_display_name = stage.get("DisplayName", "unknown")
                stage_status = stage.get("Status", "unknown")

                out_file.write("\n" + "=" * 80 + "\n")
                out_file.write(
                    f"STAGE {stage_idx}: {stage_display_name} ({stage_name})\n"
                )
                out_file.write(f"Stage ID: {stage_id}\n")
                out_file.write(f"Status: {stage_status}\n")
                out_file.write("=" * 80 + "\n\n")

                # Process each task in the stage
                tasks = stage.get("Tasks", [])
                for task_idx, task in enumerate(tasks, 1):
                    task_id = task.get("Id", "unknown")
                    task_run_id = task.get("TaskRunID", "unknown")
                    task_name = task.get("Name", "unknown")
                    task_display_name = task.get("DisplayName", "unknown")
                    task_status = task.get("Status", "unknown")
                    task_start_time = task.get("StartTime", "unknown")
                    task_finish_time = task.get("FinishTime", "unknown")

                    out_file.write("\n" + "-" * 80 + "\n")
                    out_file.write(
                        f"TASK {task_idx}: {task_display_name} ({task_name})\n"
                    )
                    out_file.write(f"Task ID: {task_id}\n")
                    out_file.write(f"Task Run ID: {task_run_id}\n")
                    out_file.write(f"Status: {task_status}\n")
                    out_file.write(f"Start Time: {task_start_time}\n")
                    out_file.write(f"Finish Time: {task_finish_time}\n")
                    out_file.write("-" * 80 + "\n\n")

                    # Process each step in the task
                    steps = task.get("Steps", [])
                    for step_idx, step in enumerate(steps, 1):
                        step_name = step.get("Name", "unknown")
                        step_status = step.get("Status", "unknown")
                        step_start_time = step.get("StartTime", "unknown")
                        step_finish_time = step.get("FinishTime", "unknown")

                        total_steps += 1

                        out_file.write(f"\n{'*' * 60}\n")
                        out_file.write(f"STEP {step_idx}: {step_name}\n")
                        out_file.write(f"Status: {step_status}\n")
                        out_file.write(f"Start Time: {step_start_time}\n")
                        out_file.write(f"Finish Time: {step_finish_time}\n")
                        out_file.write(f"{'*' * 60}\n\n")

                        # Try to download the step log
                        try:
                            # Get log download URI
                            log_url = self.get_task_run_log_download_uri(
                                workspace_id=workspace_id,
                                pipeline_id=pipeline_id,
                                pipeline_run_id=pipeline_run_id,
                                task_run_id=task_run_id,
                                task_id=task_id,
                                step_name=step_name,
                            )

                            # Download the log content
                            response = requests.get(log_url, timeout=30)
                            response.raise_for_status()

                            log_content = response.text
                            out_file.write(log_content)

                            if not log_content.endswith("\n"):
                                out_file.write("\n")

                            successful_downloads += 1
                            logger.info(
                                f"Successfully downloaded log for step: {step_name}"
                            )

                        except Exception as e:
                            failed_downloads += 1
                            error_msg = f"[ERROR] Failed to download log for step '{step_name}': {str(e)}\n"
                            out_file.write(error_msg)
                            logger.warning(
                                f"Failed to download log for step {step_name}: {e}"
                            )

                        out_file.write("\n")

            # Write summary at the end
            out_file.write("\n" + "=" * 80 + "\n")
            out_file.write("LOG DOWNLOAD SUMMARY\n")
            out_file.write("=" * 80 + "\n")
            out_file.write(f"Total Steps: {total_steps}\n")
            out_file.write(f"Successful Downloads: {successful_downloads}\n")
            out_file.write(f"Failed Downloads: {failed_downloads}\n")
            out_file.write("=" * 80 + "\n")

        logger.info(
            f"Log file created: {output_file} ({successful_downloads}/{total_steps} steps downloaded)"
        )
        return output_file
