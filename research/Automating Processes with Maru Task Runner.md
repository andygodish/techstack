---
tags: [maru, uds, kubernetes, task-runner, automation, deployment, bundles, yaml, configuration, ci-cd]
---

# Automating Processes with Maru Task Runner

## Overview

Maru is a task runner developed by Defense Unicorns and integrated within the UDS CLI tool. It provides a structured way to automate deployment and operational processes for Kubernetes environments through declarative YAML configuration files.

## Key Features

- **Declarative Configuration**: Define tasks and workflows in YAML format
- **Task Composition**: Organize tasks hierarchically with includes and dependencies  
- **Variable Substitution**: Pass parameters to tasks using environment variables
- **Remote Task Inclusion**: Reference tasks from remote repositories with authentication
- **Local Execution**: Run tasks on your local development environment similar to Make/Makefile

## Basic Structure

### Core Components

Maru requires a `tasks.yaml` file located in the root directory of your project. This file serves as the entry point for all task definitions and can include:

- **Includes**: References to other task files (local or remote)
- **Tasks**: Individual task definitions with actions and parameters
- **Authentication**: Configuration for accessing remote task repositories

### CLI Integration

Within the UDS CLI, Maru is aliased as `uds run`, allowing you to execute tasks using:

```bash
uds run [TASK-NAME]
uds run [TASK-NAME] --set VARIABLE=value
```

## Configuration Examples

### Root Tasks File Structure

```yaml
# Copyright [YEAR] [COMPANY]
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-[COMPANY]-Commercial

includes:
  - bundles: ./tasks/bundles.yaml
  - packages: ./tasks/packages.yaml
  # Remote task inclusion with authentication
  - lint: https://[DOMAIN]/api/v4/projects/[PROJECT-ID]/repository/files/tasks%2Flint.yaml/raw?ref=main

tasks:
  - name: environment-dev
    actions:
      - task: bundles:[BUNDLE-NAME]-dev-create
      - task: bundles:[BUNDLE-NAME]-dev-deploy

  - name: environment-test
    actions:
      - task: bundles:[BUNDLE-NAME]-test-create
      - task: bundles:[BUNDLE-NAME]-test-deploy

  - name: environment-prod
    actions:
      - task: bundles:[BUNDLE-NAME]-prod-create
      - task: bundles:[BUNDLE-NAME]-prod-deploy
```

### Parameterized Tasks

```yaml
- name: specific-packages-dev
  description: |
    Deploys specific packages from the bundle
    example: uds run specific-packages-dev --set PACKAGES='package1,package2,package3'
  actions:
    - task: bundles:[BUNDLE-NAME]-dev-deploy-specific-packages
      with:
        packages: ${PACKAGES}
```

### Task Organization Patterns

#### Local Task Includes
```yaml
includes:
  - bundles: ./tasks/bundles.yaml      # Bundle management tasks
  - packages: ./tasks/packages.yaml    # Individual package tasks
  - utilities: ./tasks/utils.yaml      # Common utility functions
```

#### Remote Task Authentication
For accessing tasks from remote repositories, configure authentication:

```bash
export MARU_AUTH='{"[GITLAB-DOMAIN]": "$[TOKEN-VARIABLE]"}'
```

## Implementation Strategies

### Environment-Specific Deployments

Structure your tasks to support multiple environments:

```yaml
tasks:
  - name: deploy-dev
    description: "Deploy to development environment"
    actions:
      - task: bundles:create-dev-bundle
      - task: bundles:deploy-dev-bundle
      - task: packages:configure-dev-settings

  - name: deploy-staging  
    description: "Deploy to staging environment"
    actions:
      - task: bundles:create-staging-bundle
      - task: bundles:deploy-staging-bundle
      - task: packages:configure-staging-settings

  - name: deploy-production
    description: "Deploy to production environment" 
    actions:
      - task: bundles:create-prod-bundle
      - task: bundles:deploy-prod-bundle
      - task: packages:configure-prod-settings
```

### Selective Package Deployment

Enable flexibility by allowing users to specify which packages to deploy:

```yaml
- name: deploy-selective
  description: |
    Deploy only specified packages
    Usage: uds run deploy-selective --set PACKAGES='app1,app2,database'
    Usage: uds run deploy-selective --set ENVIRONMENT=dev --set PACKAGES='monitoring'
  actions:
    - task: bundles:validate-packages
      with:
        packages: ${PACKAGES}
        environment: ${ENVIRONMENT:-dev}
    - task: bundles:deploy-specific-packages
      with:
        packages: ${PACKAGES}
        environment: ${ENVIRONMENT:-dev}
```

## Best Practices

### File Organization

- **Root Level**: Keep the main `tasks.yaml` simple with includes and high-level workflows
- **Tasks Directory**: Organize related tasks into separate files (`./tasks/bundles.yaml`, `./tasks/packages.yaml`)
- **Naming Conventions**: Use descriptive, hierarchical naming for tasks (e.g., `bundles:app-dev-deploy`)

### Task Design

- **Atomic Operations**: Design tasks to be small, focused, and reusable
- **Error Handling**: Include validation steps before destructive operations
- **Documentation**: Provide clear descriptions and usage examples for complex tasks
- **Environment Variables**: Use sensible defaults and validate required parameters

### Security Considerations

- **Credential Management**: Never hardcode credentials in task files
- **Remote Includes**: Use authentication tokens for accessing private repositories
- **Variable Validation**: Validate input parameters before executing dangerous operations

## Common Use Cases

### CI/CD Integration
```yaml
- name: ci-pipeline
  description: "Complete CI pipeline execution"
  actions:
    - task: lint:validate-yaml
    - task: packages:build-images  
    - task: bundles:create-test-bundle
    - task: bundles:deploy-test-environment
    - task: packages:run-integration-tests
```

### Development Workflow
```yaml
- name: dev-setup
  description: "Set up local development environment"
  actions:
    - task: packages:install-dependencies
    - task: bundles:create-dev-bundle
    - task: bundles:deploy-local-cluster
    - task: packages:configure-dev-tools
```

### Maintenance Operations
```yaml
- name: cleanup-environment
  description: "Clean up specified environment resources"
  actions:
    - task: bundles:remove-deployment
      with:
        environment: ${ENVIRONMENT}
    - task: packages:cleanup-volumes
    - task: utilities:cleanup-temp-files
```

## Advanced Features

### Conditional Execution
Tasks can include conditional logic based on environment variables or system state.

### Parallel Execution
Some task runners support parallel execution of independent tasks to improve performance.

### Task Dependencies
Define explicit dependencies between tasks to ensure proper execution order.

## Troubleshooting

### Common Issues

1. **Task Not Found**: Verify the task name and include paths
2. **Authentication Errors**: Check that authentication tokens are properly configured
3. **Variable Substitution**: Ensure required environment variables are set
4. **File Not Found**: Confirm that referenced task files exist and are accessible

### Debugging Tips

- Use descriptive task names and include documentation
- Test tasks individually before composing complex workflows  
- Validate environment variables before task execution
- Include logging and status output in task actions

## Conclusion

Maru provides a powerful framework for automating Kubernetes deployment and operational processes. By following structured patterns and best practices, teams can create maintainable, reusable automation that scales across different environments and use cases.

The key to successful Maru implementation is starting with simple, well-defined tasks and gradually building more complex workflows through composition and parameterization.

## tasks.yaml Schema

https://raw.githubusercontent.com/defenseunicorns/uds-cli/main/tasks.schema.json

Copied on 8/26/25: 

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/defenseunicorns/maru-runner/src/types/tasks-file",
  "$ref": "#/$defs/TasksFile",
  "$defs": {
    "Action": {
      "properties": {
        "description": {
          "type": "string",
          "description": "Description of the action to be displayed during package execution instead of the command"
        },
        "cmd": {
          "type": "string",
          "description": "The command to run. Must specify either cmd or wait for the action to do anything."
        },
        "wait": {
          "$ref": "#/$defs/ActionWait",
          "description": "Wait for a condition to be met before continuing. Must specify either cmd or wait for the action."
        },
        "env": {
          "items": {
            "type": "string"
          },
          "type": "array",
          "description": "Additional environment variables to set for the command"
        },
        "mute": {
          "type": "boolean",
          "description": "Hide the output of the command during package deployment (default false)"
        },
        "maxTotalSeconds": {
          "type": "integer",
          "description": "Timeout in seconds for the command (default to 0"
        },
        "maxRetries": {
          "type": "integer",
          "description": "Retry the command if it fails up to given number of times (default 0)"
        },
        "dir": {
          "type": "string",
          "description": "The working directory to run the command in (default is CWD)"
        },
        "shell": {
          "$ref": "#/$defs/ShellPreference",
          "description": "(cmd only) Indicates a preference for a shell for the provided cmd to be executed in on supported operating systems"
        },
        "setVariables": {
          "items": {
            "$ref": "#/$defs/Variable"
          },
          "type": "array",
          "description": "(onDeploy/cmd only) An array of variables to update with the output of the command. These variables will be available to all remaining actions and components in the package."
        },
        "task": {
          "type": "string",
          "description": "The task to run"
        },
        "with": {
          "additionalProperties": {
            "type": "string"
          },
          "type": "object",
          "description": "Input parameters to pass to the task"
        },
        "if": {
          "type": "string",
          "description": "Conditional to determine if the action should run"
        }
      },
      "additionalProperties": false,
      "type": "object",
      "patternProperties": {
        "^x-": {}
      }
    },
    "ActionWait": {
      "properties": {
        "cluster": {
          "$ref": "#/$defs/ActionWaitCluster",
          "description": "Wait for a condition to be met in the cluster before continuing. Only one of cluster or network can be specified."
        },
        "network": {
          "$ref": "#/$defs/ActionWaitNetwork",
          "description": "Wait for a condition to be met on the network before continuing. Only one of cluster or network can be specified."
        }
      },
      "additionalProperties": false,
      "type": "object",
      "patternProperties": {
        "^x-": {}
      }
    },
    "ActionWaitCluster": {
      "properties": {
        "kind": {
          "type": "string",
          "description": "The kind of resource to wait for",
          "examples": [
            "Pod",
            "Deployment)"
          ]
        },
        "name": {
          "type": "string",
          "description": "The name of the resource or selector to wait for",
          "examples": [
            "podinfo",
            "app&#61;podinfo"
          ]
        },
        "namespace": {
          "type": "string",
          "description": "The namespace of the resource to wait for"
        },
        "condition": {
          "type": "string",
          "description": "The condition or jsonpath state to wait for; defaults to exist",
          "examples": [
            "Ready",
            "Available"
          ]
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "kind",
        "name"
      ],
      "patternProperties": {
        "^x-": {}
      }
    },
    "ActionWaitNetwork": {
      "properties": {
        "protocol": {
          "type": "string",
          "enum": [
            "tcp",
            "http",
            "https"
          ],
          "description": "The protocol to wait for"
        },
        "address": {
          "type": "string",
          "description": "The address to wait for",
          "examples": [
            "localhost:8080",
            "1.1.1.1"
          ]
        },
        "code": {
          "type": "integer",
          "description": "The HTTP status code to wait for if using http or https",
          "examples": [
            200,
            404
          ]
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "protocol",
        "address"
      ],
      "patternProperties": {
        "^x-": {}
      }
    },
    "InputParameter": {
      "properties": {
        "description": {
          "type": "string",
          "description": "Description of the parameter"
        },
        "deprecatedMessage": {
          "type": "string",
          "description": "Message to display when the parameter is deprecated"
        },
        "required": {
          "type": "boolean",
          "description": "Whether the parameter is required",
          "default": true
        },
        "default": {
          "type": "string",
          "description": "Default value for the parameter"
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "description"
      ],
      "patternProperties": {
        "^x-": {}
      }
    },
    "InteractiveVariable": {
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[A-Z0-9_]+$",
          "description": "The name to be used for the variable"
        },
        "pattern": {
          "type": "string",
          "description": "An optional regex pattern that a variable value must match before a package deployment can continue."
        },
        "description": {
          "type": "string",
          "description": "A description of the variable to be used when prompting the user a value"
        },
        "default": {
          "type": "string",
          "description": "The default value to use for the variable"
        },
        "prompt": {
          "type": "boolean",
          "description": "Whether to prompt the user for input for this variable"
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "name"
      ],
      "patternProperties": {
        "^x-": {}
      }
    },
    "ShellPreference": {
      "properties": {
        "windows": {
          "type": "string",
          "description": "(default 'powershell') Indicates a preference for the shell to use on Windows systems (note that choosing 'cmd' will turn off migrations like touch -> New-Item)",
          "examples": [
            "powershell",
            "cmd",
            "pwsh",
            "sh",
            "bash",
            "gsh"
          ]
        },
        "linux": {
          "type": "string",
          "description": "(default 'sh') Indicates a preference for the shell to use on Linux systems",
          "examples": [
            "sh",
            "bash",
            "fish",
            "zsh",
            "pwsh"
          ]
        },
        "darwin": {
          "type": "string",
          "description": "(default 'sh') Indicates a preference for the shell to use on macOS systems",
          "examples": [
            "sh",
            "bash",
            "fish",
            "zsh",
            "pwsh"
          ]
        }
      },
      "additionalProperties": false,
      "type": "object",
      "patternProperties": {
        "^x-": {}
      }
    },
    "Task": {
      "properties": {
        "name": {
          "type": "string",
          "description": "Name of the task"
        },
        "description": {
          "type": "string",
          "description": "Description of the task"
        },
        "actions": {
          "items": {
            "$ref": "#/$defs/Action"
          },
          "type": "array",
          "description": "Actions to take when running the task"
        },
        "inputs": {
          "additionalProperties": {
            "$ref": "#/$defs/InputParameter"
          },
          "type": "object",
          "description": "Input parameters for the task"
        },
        "envPath": {
          "type": "string",
          "description": "Path to file containing environment variables"
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "name"
      ],
      "patternProperties": {
        "^x-": {}
      }
    },
    "TasksFile": {
      "properties": {
        "includes": {
          "items": {
            "additionalProperties": {
              "type": "string"
            },
            "type": "object"
          },
          "type": "array",
          "description": "List of local task files to include"
        },
        "variables": {
          "items": {
            "$ref": "#/$defs/InteractiveVariable"
          },
          "type": "array",
          "description": "Definitions and default values for variables used in run.yaml"
        },
        "tasks": {
          "items": {
            "$ref": "#/$defs/Task"
          },
          "type": "array",
          "description": "The list of tasks that can be run"
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "tasks"
      ],
      "patternProperties": {
        "^x-": {}
      }
    },
    "Variable": {
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[A-Z0-9_]+$",
          "description": "The name to be used for the variable"
        },
        "pattern": {
          "type": "string",
          "description": "An optional regex pattern that a variable value must match before a package deployment can continue."
        }
      },
      "additionalProperties": false,
      "type": "object",
      "required": [
        "name"
      ],
      "patternProperties": {
        "^x-": {}
      }
    }
  }
}
```