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

from typing import Literal, get_args, get_origin

from InquirerPy import resolver
from pydantic import BaseModel


def prompt_base_model(model: type[BaseModel]) -> dict:
    """Generate interactive prompts for a Pydantic BaseModel.
    
    Args:
        model: A Pydantic BaseModel class
        
    Returns:
        Dictionary of user responses mapped to field names
    """
    prompts = []

    for field_name, model_field in model.model_fields.items():
        if get_origin(model_field.annotation) == Literal:
            prompts.append(
                {
                    "type": "list",
                    "name": field_name,
                    "default": model_field.default if model_field.default else "",
                    "message": model_field.description
                    if model_field.description
                    else field_name,
                    "choices": list(get_args(model_field.annotation)),
                }
            )
        elif model_field.annotation is bool:
            prompts.append(
                {
                    "type": "confirm",
                    "name": field_name,
                    "default": model_field.default if model_field.default else False,
                    "message": model_field.description
                    if model_field.description
                    else field_name,
                }
            )
        else:
            prompts.append(
                {
                    "type": "input",
                    "name": field_name,
                    "default": str(model_field.default) if model_field.default else "",
                    "message": model_field.description
                    if model_field.description
                    else field_name,
                }
            )

    responses = resolver.prompt(prompts)
    return responses
