# Real Agent Workflow Example

This example demonstrates using **real agents** (Claude Code via ACF) in a multi-agent workflow. Unlike the mock-based examples, each agent here:

- Has its own **workspace directory** for file I/O
- Has an **AGENT.md** defining its role and constraints
- Has a **skills/** directory with skill documentation
- Uses **real Claude Code** via tmux for execution

## Structure

```
real_agents/
├── README.md                           # This file
├── real_agent_workflow.py              # Main workflow script
│
├── product_manager/
│   ├── AGENT.md                        # Role definition
│   ├── skills/
│   │   └── write-prd.md               # Skill documentation
│   └── workspace/                      # File output directory
│       └── (prd files created here)
│
├── developer/
│   ├── AGENT.md
│   ├── skills/
│   │   └── write-code.md
│   └── workspace/
│       └── (source code created here)
│
└── code_reviewer/
    ├── AGENT.md
    ├── skills/
    │   └── review-code.md
    └── workspace/
        └── (review reports created here)
```

## Prerequisites

1. **tmux** installed
2. **Claude CLI** installed and authenticated
3. **ACF v2** installed:
   ```bash
   cd /path/to/acf-v2
   pip install -e ".[dev]"
   ```

## How It Works

### Agent Configuration (AGENT.md)

Each agent has a configuration file defining:
- **Identity**: What role the agent plays
- **Responsibilities**: What tasks it handles
- **Output format**: Expected deliverables
- **Constraints**: What it should/shouldn't do

Example from `product_manager/AGENT.md`:
```markdown
## Identity
产品经理 (PM)

## Responsibilities
- 分析用户需求，提炼核心功能点
- 撰写清晰的产品需求文档 (PRD)
...
```

### Skills

Skills are documented capabilities that guide the agent's behavior:

```markdown
# Skill: Write PRD

## Description
撰写产品需求文档

## Input
- 用户原始需求描述
...

## Output Format
...
```

### System Prompt Construction

The main script (`real_agent_workflow.py`) dynamically constructs system prompts by combining:
1. AGENT.md content
2. All skill files
3. Workspace location
4. Execution instructions

### Workflow Flow

1. **Product Manager**
   - Receives: Feature request
   - Uses: write-prd skill
   - Creates: PRD document in workspace/

2. **Developer**
   - Receives: PRD content from previous step
   - Uses: write-code skill
   - Creates: Implementation in workspace/

3. **Code Reviewer**
   - Receives: Code from developer
   - Uses: review-code skill
   - Creates: Review report in workspace/

## Usage

```bash
cd /path/to/acf-v2/examples/real_agents

# Optional: Set API key for Claude
export ANTHROPIC_API_KEY=your_key

# Run the workflow
python real_agent_workflow.py
```

## Customization

### Adding a New Agent

1. Create agent directory:
   ```bash
   mkdir -p new_agent/{workspace,skills}
   ```

2. Write AGENT.md:
   ```markdown
   # New Agent Name
   
   ## Identity
   ...
   ```

3. Add skills in `skills/*.md`

4. Update `real_agent_workflow.py`:
   ```python
   new_adapter = create_claude_adapter(
       name="new_agent",
       workspace_dir=str(get_workspace_dir("new_agent")),
       ...
   )
   ```

### Modifying Skills

Edit the markdown files in `skills/` directories. The agent will read these at runtime and incorporate them into its system prompt.

## Notes

- **Execution Time**: Real agent workflows take significantly longer than mock examples (minutes vs seconds)
- **Cost**: Each node execution invokes Claude API (check your usage)
- **tmux Sessions**: The script automatically manages tmux sessions; manual cleanup shouldn't be needed
- **Checkpoints**: Workflow state is saved after each node for recovery

## Troubleshooting

### tmux not found
```bash
# Ubuntu/Debian
sudo apt-get install tmux

# macOS
brew install tmux
```

### Claude CLI not authenticated
```bash
claude login
```

### Permission denied in root environment
Claude Code requires interactive confirmation in root environments. The adapter handles this by sending "2" automatically after a delay.

## See Also

- [ACF v2 README](../../README.md)
- [Design Documentation](../../DESIGN.md)
- [Claude Adapter Source](../../src/acf/adapter/claude.py)
