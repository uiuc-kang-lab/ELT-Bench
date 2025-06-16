from __future__ import annotations
import os
import re
import json
import shutil
from pathlib import Path
from tenacity import RetryError
from dataclasses import dataclass
from sweagent.agent.models import (
    APIStats,
    get_model,
    ModelArguments,
    CostLimitExceededError,
    ContextWindowExceededError,
)
from sweagent.utils.log import get_logger
from sweagent.agent.models import APIStats
from sweagent.environment.swe_env import SWEEnv
from simple_parsing.helpers.fields import field
from sweagent.agent.commands import Command, ParseCommand
from sweagent.utils.config import convert_paths_to_abspath
from simple_parsing.helpers.flatten import FlattenedAccess
from sweagent.agent.parsing import FormatError, ParseFunction
from sweagent.agent.history_processors import HistoryProcessor
from typing import Any, TypedDict, Optional, List, Dict, Literal
from simple_parsing.helpers.serialization.serializable import FrozenSerializable


@dataclass(frozen=True)
class Subroutine(FrozenSerializable):
    name: str
    agent_file: str
    return_type: str = None
    init_observation: str | None = None
    end_name: str | None = None
    signature: str | None = None
    docstring: str | None = None
    model: ModelArguments | None = None
    agent_args: Any | None = None

class AgentHook:
    def on_init(self): ...

    def on_run_start(
        self,
    ): ...

    def on_step_start(self): ...

    def on_actions_generated(self, *, thought: str, action: str, output: str): ...

    def on_sub_action_started(self, *, sub_action: str): ...

    def on_sub_action_executed(self, *, obs: str, done: bool): ...

    def on_step_done(self, *, trajectory_step: TrajectoryStep, model_stats: APIStats): ...

    def on_run_done(self): ...

    def on_model_query(self, *, query: str, agent: str):
        """Actually query the model with the complete history."""

    def on_query_message_added(
        self,
        *,
        role: str,
        content: str,
        agent: str,
        is_demo: bool = False,
        thought: str = "",
        action: str = "",
    ): ...

@dataclass(frozen=True)
class DARSPrompts:
    edit_expansion_prompt_template: str | None = None
    insert_expansion_prompt_template: str | None = None
    append_expansion_prompt_template: str | None = None
    submit_expansion_prompt_template: str | None = None
    create_expansion_prompt_template: str | None = None
    critic_expansion_prompt_template: str | None = None
    summarization_prompt_template: str | None = None

@dataclass(frozen=True)
class DARSConfig:
    num_iterations: int = 200
    num_expansions: int = 2
    max_branch_depth: int = 100
    resume_path: str | None = None
    search_dir_ft: int = 25
    search_file_ft: int = 25
    one_expansion_type_per_branch: bool = True
    num_expansions_per_branch: dict[str, int] = field(default_factory=dict)
    action_expansion_limit: dict | None = None
    allowed_action_in_expansion: dict | None = None
    expansion_temperature: float = 0.8
    num_expansion_sampling: int = 2
    n_lookahead: int = 5
    summarize_expansion_context: bool = False
    auto_submit: bool = False


class TrajectoryStep(TypedDict):
    action: str
    observation: str
    response: str
    state: str | None
    thought: str

@dataclass(frozen=True)
class AgentConfig(FrozenSerializable):
    system_template: str
    instance_template: str
    next_step_template: str | None = None  # defaults to instance_template
    next_step_no_output_template: str | None = None  # defaults to next_step_template
    strategy_template: str | None = None
    next_step_codegraph_template: str | None = None
    demonstration_template: str | None = None
    # Paths to demonstrations. If path is not absolute, it is assumed to be
    # relative to the SWE_AGENT_CONFIG_ROOT (if set) or the SWE-agent repository root
    demonstrations: list[str | Path] = field(default_factory=list)
    put_demos_in_history: bool = False  # if True, add demonstration to history instead of as a single message
    # defaults to format_error_template in ParseFunction
    format_error_template: str = None  # type: ignore
    # Paths to command files. If path is not absolute, it is assumed to be
    # relative to the SWE_AGENT_CONFIG_ROOT (if set) or the SWE-agent repository root
    command_files: list[str | Path] = field(default_factory=list)
    env_variables: dict[str, str] = field(default_factory=dict)
    codegraph_cache_dir: str = None
    util_functions: list[str] = field(default_factory=list)
    submit_command: str = "submit"
    parse_function: str = "ThoughtActionParser"
    parse_command: str = "ParseCommandBash"
    history_processor: str = "DefaultHistoryProcessor"
    history_processor_args: dict[str, Any] = field(default_factory=dict)
    command_docs: str = None  # type: ignore
    use_demonstrations: bool = True
    blocklist_error_template: str = "Interactive operation '{name}' is not supported by this environment"
    blocklist: tuple[str, ...] = (
        "vim",
        "vi",
        "emacs",
        "nano",
        "nohup",
        "git",
    )
    blocklist_standalone: tuple[str, ...] = (
        "python",
        "python3",
        "ipython",
        "bash",
        "sh",
        "exit",
        "/bin/bash",
        "/bin/sh",
        "nohup",
        "vi",
        "vim",
        "emacs",
        "nano",
    )
    # Should extract environment state in a json readable form
    state_command: Command = Command(
        name="state",
        code="""state() {
            echo '{"working_dir": "'$(realpath --relative-to=$ROOT/.. $PWD)'"}';
        };""",
    )
    _commands: list[Command] = field(default_factory=list)
    _subroutines: dict[str, Subroutine] = field(default_factory=dict)
    subroutine_types: list[Subroutine] = field(default_factory=list)
    agent_type: Literal["dars", "SWE-agent"] = "dars"
    DARS: DARSConfig = field(default_factory=DARSConfig)
    DARS_prompts: DARSPrompts = field(default_factory=DARSPrompts)
    swe_agent_checkpoint_path: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "command_files", convert_paths_to_abspath(self.command_files))
        object.__setattr__(self, "demonstrations", convert_paths_to_abspath(self.demonstrations))

        if self.next_step_template is None:
            object.__setattr__(self, "next_step_template", self.instance_template)
        if self.next_step_no_output_template is None:
            object.__setattr__(self, "next_step_no_output_template", self.next_step_template)

        object.__setattr__(self, "parse_command", ParseCommand.get(self.parse_command))
        for file in self.command_files:
            commands = self.parse_command.parse_command_file(file)

            util_functions = [command for command in commands if command.name.startswith("_")]
            commands = [command for command in commands if not command.name.startswith("_")]

            object.__setattr__(self, "util_functions", self.util_functions + util_functions)
            object.__setattr__(self, "_commands", self._commands + commands)

        for subroutine in self.subroutine_types:
            if subroutine.name == "submit":
                msg = "Cannot use 'submit' as a subroutine name"
                raise ValueError(msg)
            agent_args = AgentArguments(
                model=subroutine.model,
                config_file=subroutine.agent_file,
            )
            object.__setattr__(subroutine, "agent_args", agent_args)
            object.__setattr__(self, "_subroutines", {**self._subroutines, subroutine.name: subroutine})

        multi_line_command_endings = {
            command.name: command.end_name
            for command in [*self._commands, *self._subroutines.values()]
            if command.end_name is not None
        }
        object.__setattr__(self, "multi_line_command_endings", multi_line_command_endings)
        object.__setattr__(
            self,
            "command_docs",
            self.parse_command.generate_command_docs(
                self._commands,
                self.subroutine_types,
                **self.env_variables,
            ),
        )
        object.__setattr__(self, "parse_function", ParseFunction.get(self.parse_function))
        if self.format_error_template is None:
            object.__setattr__(
                self,
                "format_error_template",
                self.parse_function.format_error_template,
            )
        object.__setattr__(
            self,
            "format_error_template",
            self.format_error_template.format(**self.__dict__),
        )
        for command in self._commands:
            if command.name == self.submit_command:
                object.__setattr__(self, "submit_command_end_name", command.end_name)
                break
        object.__setattr__(
            self,
            "history_processor",
            HistoryProcessor.get(self.history_processor, **self.history_processor_args),
        )


@dataclass(frozen=True)
class AgentArguments(FlattenedAccess, FrozenSerializable):
    """Configure the agent's behaviour (templates, parse functions, blocklists, ...)."""

    model: ModelArguments = None

    # Policy can only be set via config yaml file from command line
    config_file: Path | None = None
    config: AgentConfig | None = field(default=None, cmd=False)

    def __post_init__(self):
        if self.config is None and self.config_file is not None:
            # If unassigned, we load the config from the file to store its contents with the overall arguments
            config = AgentConfig.load_yaml(self.config_file)
            object.__setattr__(self, "config", config)
        assert self.config is not None  # mypy
        for subroutine in getattr(self.config, "subroutines", {}).values():
            model_args = subroutine.model
            object.__setattr__(
                model_args,
                "per_instance_cost_limit",
                self.model.per_instance_cost_limit,
            )
            object.__setattr__(model_args, "total_cost_limit", self.model.total_cost_limit)

class DARSNode:
    def __init__(
            self, role: str, content: str, agent: str, 
            thought: Optional[str] = None, action: Optional[str] = None, 
            parent: Optional[DARSNode] = None, is_demo: bool = False, 
            is_terminal: bool = False, _depth: Optional[int] = None
        ):
        self.role = role
        self.content = content
        self.thought = thought
        self.action = action
        self.agent = agent
        self.parent = parent
        self.is_demo = is_demo
        self.children: List[DARSNode] = []
        self.is_terminal = is_terminal
        self._depth = 0 if parent is None else parent._depth + 1
        self._action_expansion_limit = None
        self.expansion_history = []
        if _depth is not None:
            self._depth = _depth
        self.node_id = None
        self.codegraph_keyword = None
        self.codegraph_context = None
        self.expansion_candidates = None
        self.critic_prompt = None
        self.critic_response = None
        self.expansion_prompt = None

    @property
    def depth(self) -> int:
        return self._depth

    def add_child(self, child: 'DARSNode'):
        child.parent = self
        child._depth = self._depth + 1
        child.expansion_history = self.expansion_history.copy()
        child._action_expansion_limit = self._action_expansion_limit.copy()
        self.children.append(child)

    def get_allowed_actions_in_expansion(self, dars_config: DARSConfig):
        if not self.expansion_history:
            return (list(dars_config.action_expansion_limit.keys()) 
                    if dars_config.action_expansion_limit is not None 
                    else [])

        first_action = self.expansion_history[0]
        if first_action not in dars_config.allowed_action_in_expansion:
            return []
        
        allowed_actions = set(dars_config.allowed_action_in_expansion[first_action])
        
        for action in self.expansion_history[1:]:
            if action not in dars_config.allowed_action_in_expansion:
                return []
            allowed_actions.intersection_update(dars_config.allowed_action_in_expansion[action])
            if not allowed_actions:
                return []
        if dars_config.action_expansion_limit is not None:
            allowed_actions.intersection_update(dars_config.action_expansion_limit.keys())

        return list(allowed_actions)

    def should_expand(self, dars_config: DARSConfig):
        allowed_actions = self.get_allowed_actions_in_expansion(dars_config)
        action = self.action.split()[0]
        if not allowed_actions or action not in allowed_actions:
            return False
        
        if self._action_expansion_limit is not None:
            return self._action_expansion_limit[action] > 0
        return False


class DARSAgent:

    def __init__(self, name: str, args: AgentArguments):
        self.name = name
        self.model = get_model(args.model, args.config._commands + args.config.subroutine_types)
        self.config = args.config
        assert self.config is not None  # mypy
        self.system_args = {
            "command_docs": self.config.command_docs,
            **self.config.env_variables,
        }
        self.instance_args = None
        self._parse_command_patterns()
        self.root_node: Optional[DARSNode] = None
        self.last_container_id = None
        self.hooks = []
        self.logger = get_logger("agent")
        self.node_count = None

    def add_node_id(self, node: DARSNode):
        node.node_id = self.node_count
        self.node_count += 1

    def add_hook(self, hook: AgentHook):
        """Add hook to agent"""
        hook.on_init()
        self.hooks.append(hook)

    def _append_history(self, item: dict, parent_node: Optional[DARSNode] = None) -> DARSNode:
        for hook in self.hooks:
            hook.on_query_message_added(**item)

        new_node = DARSNode(
            role=item.get('role'),
            content=item.get('content'),
            agent=item.get('agent'),
            thought=item.get('thought'),
            action=item.get('action'),
            parent=None,
            is_demo=item.get('is_demo', False),
            is_terminal=item.get('is_terminal', False),
        )
        new_node.codegraph_keyword = item.get('codegraph_keyword')
        new_node.codegraph_context = item.get('codegraph_context')
        new_node.expansion_candidates = item.get('expansion_candidates')
        new_node.critic_prompt = item.get('critic_prompt')
        new_node.critic_response = item.get('critic_response')
        new_node.expansion_prompt = item.get('expansion_prompt')

        if self.root_node is None:
            if parent_node is not None:
                raise ValueError("Cannot specify parent_node when root_node is None")
            self.root_node = new_node
            self.root_node._action_expansion_limit = self.config.DARS.action_expansion_limit
        else:
            if parent_node is None:
                raise ValueError("Must specify parent_node when root_node is not None")
            
            if parent_node.is_terminal:
                new_node.is_terminal = True

            parent_node.add_child(new_node)

        return new_node

    def setup(self, instance_args, init_model_stats=None) -> None:
        """Setup the agent for a new instance. This includes
        formatting the system message and adding demonstrations to the history.

        Args:
            instance_args: Arguments for the instance
        """
        assert self.config is not None  # mypy
        self.model.reset_stats(init_model_stats)
        self.instance_args = instance_args

        system_msg = self.config.system_template.format(**self.system_args)
        self.logger.info(f"SYSTEM ({self.name})\n{system_msg}")

        self.root_node = None
        starting_node = self._append_history({"role": "system", "content": system_msg, "agent": self.name}, parent_node=None)
        if not self.config.use_demonstrations:
            return 

        if "history_to_messages" in dir(self.model):
            for demonstration_path in self.config.demonstrations:
                if self.config.demonstration_template is None and not self.config.put_demos_in_history:
                    msg = "Cannot use demonstrations without a demonstration template or put_demos_in_history=True"
                    raise ValueError(msg)

                # Load history
                self.logger.info(f"DEMONSTRATION: {demonstration_path}")
                demo_history = json.loads(Path(demonstration_path).read_text())["history"]
                demo_history = [
                    entry
                    for entry in demo_history
                    if ("agent" not in entry) or ("agent" in entry and entry["agent"] == self.name)
                ]

                if self.config.put_demos_in_history:
                    if self.config.demonstration_template is not None:
                        self.logger.warning("Demonstration template is ignored for put_demos_in_history=True")
                    for entry in demo_history:
                        if entry["role"] != "system":
                            entry["is_demo"] = True
                            self._append_history(entry)
                else:
                    demo_message = self.model.history_to_messages(
                        demo_history,
                        is_demonstration=True,
                    )
                    demonstration = self.config.demonstration_template.format(demonstration=demo_message)
                    starting_node = self._append_history(
                        {
                            "agent": self.name,
                            "content": demonstration,
                            "is_demo": True,
                            "role": "user",
                        },
                        parent_node=starting_node
                    )
        return starting_node

    @property
    def state_command(self) -> str:
        """Return the bash command that will be used to extract the environment state."""
        return self.config.state_command.name

    def local_history(self, node: DARSNode) -> list[dict[str, str]]:
        history = []
        self._backtrack_history(node, history)
        history = [entry for entry in history if entry["agent"] == self.name]
        return self.config.history_processor(history)

    def _backtrack_history(self, node: DARSNode, history: List[Dict[str, Any]]):
        if node is None:
            return

        self._backtrack_history(node.parent, history)

        if node.is_demo:
            history.append({
                "agent": node.agent,
                "content": node.content,
                "is_demo": True,
                "role": node.role,
            })
        elif node.thought is not None and node.action is not None:
            history.append({
                "role": node.role,
                "content": node.content,
                "thought": node.thought,
                "action": node.action,
                "agent": node.agent
            })
        else:
            history.append({
                "role": node.role,
                "content": node.content,
                "agent": node.agent
            })

    def _get_first_match(self, action: str, pattern_type: str) -> re.Match | None:
        """Return the first match of a command pattern in the action string."""
        assert self.config is not None  # mypy
        if pattern_type == "subroutine":
            patterns = {k: v for k, v in self.subroutine_patterns.items()}
        elif pattern_type == "multi_line":
            patterns = {
                k: v
                for k, v in self.command_patterns.items()
                if k in self.config.multi_line_command_endings or k == self.config.submit_command
            }
            patterns += {
                k: v for k, v in self.subroutine_patterns.items() if k in self.config.multi_line_command_endings
            }
        elif pattern_type == "multi_line_no_subroutines":
            patterns = {k: v for k, v in self.command_patterns.items() if k in self.config.multi_line_command_endings}
        else:
            msg = f"Unknown pattern type: {pattern_type}"
            raise ValueError(msg)
        matches = list()
        for _, pat in patterns.items():
            match = pat.search(action)
            if match:
                matches.append(match)
        if len(matches) == 0:
            return None
        matches = sorted(matches, key=lambda x: x.start())
        return matches[0]

    def _guard_multiline_input(self, action: str) -> str:
        """Split action by multiline commands, then append the first line in each multiline command with "<< '{end_name}'".
        Multiline commands (which are specified by an end_name) are commands that span multiple lines and are terminated by a specific end_name.

        Their multi-line argument is sent using a heredoc, which is a way to send a multi-line string to a command in bash.
        """
        parsed_action = list()
        rem_action = action
        while rem_action.strip():
            first_match = self._get_first_match(rem_action, "multi_line_no_subroutines")
            if first_match:
                pre_action = rem_action[: first_match.start()]
                match_action = rem_action[first_match.start() : first_match.end()]
                rem_action = rem_action[first_match.end() :]
                if pre_action.strip():
                    parsed_action.append(pre_action)
                if match_action.strip():
                    eof = first_match.group(3).strip()
                    if not match_action.split("\n")[0].strip().endswith(f"<< '{eof}'"):
                        guarded_command = match_action[first_match.start() :]
                        first_line = guarded_command.split("\n")[0]
                        guarded_command = guarded_command.replace(first_line, first_line + f" << '{eof}'", 1)
                        parsed_action.append(guarded_command)
                    else:
                        parsed_action.append(match_action)
            else:
                parsed_action.append(rem_action)
                rem_action = ""
        return "\n".join(parsed_action)

    def split_actions(self, action: str, pattern_type="subroutine") -> list[dict[str, Any]]:
        """Split an action into a list of actions in a greedy manner, each of which is a subroutine call or a single command."""
        parsed_action = list()
        rem_action = action
        while rem_action.strip():
            first_match = self._get_first_match(rem_action, pattern_type)
            if first_match:
                pre_action = rem_action[: first_match.start()]
                match_action = rem_action[first_match.start() : first_match.end()]
                rem_action = rem_action[first_match.end() :]
                if pre_action.strip():
                    parsed_action.append({"agent": self.name, "action": pre_action, "cmd_name": None})
                if match_action.strip():
                    if match_action.split()[0] == self.config.submit_command:
                        parsed_action.append(
                            {
                                "agent": self.name,
                                "action": match_action,
                                "cmd_name": first_match.group(1),
                            },
                        )  # submit command is not a subroutine
                    else:
                        parsed_action.append(
                            {
                                "agent": first_match.group(1),
                                "args": first_match.group(2),
                                "action": match_action,
                                "cmd_name": first_match.group(1),
                            },
                        )
            else:
                parsed_action.append({"agent": self.name, "action": rem_action, "cmd_name": None})
                rem_action = ""
        return parsed_action

    def _parse_command_patterns(self) -> None:
        assert self.config is not None  # mypy
        self.command_patterns = dict()
        for command in self.config._commands:
            if command.end_name is not None:
                pat = re.compile(
                    rf"^\s*({command.name})\s*(.*?)^({command.end_name})\s*$",
                    re.DOTALL | re.MULTILINE,
                )
                self.command_patterns[command.name] = pat
            else:
                pat = re.compile(rf"^\s*({command.name})\s*(.*?)$", re.MULTILINE)
                self.command_patterns[command.name] = pat
        self.subroutine_patterns = dict()
        for _, subroutine in self.config._subroutines.items():
            if subroutine.end_name is None:
                pat = re.compile(rf"^\s*({subroutine.name})\s*(.*?)$", re.MULTILINE)
                self.subroutine_patterns[subroutine.name,] = pat
            else:
                pat = re.compile(
                    rf"^\s*({subroutine.name})\s*(.*?)^({subroutine.end_name})\s*$",
                    re.DOTALL | re.MULTILINE,
                )
                self.subroutine_patterns[subroutine.name] = pat
        if hasattr(self.config, "submit_command_end_name"):
            submit_pat = re.compile(
                rf"^\s*({self.config.submit_command})\s*(.*?)^({self.config.submit_command_end_name})\s*$",
                re.DOTALL | re.MULTILINE,
            )
        else:
            submit_pat = re.compile(rf"^\s*({self.config.submit_command})(\s*)$", re.MULTILINE)  # group 2 is nothing
        self.subroutine_patterns[self.config.submit_command] = submit_pat
        self.command_patterns[self.config.submit_command] = submit_pat

    def forward(self, last_node: DARSNode, available_actions: list[str], temperature: Optional[float] = None, expansion_context: str = None, query_model: str = None) -> DARSNode:

        thought, action, output = self.forward_with_error_check(last_node, temperature, expansion_context, query_model=query_model)
        current_node = self._append_history(
            {
                "role": "assistant",
                "content": output,
                "thought": thought,
                "action": action,
                "agent": self.name,
            },
            parent_node=last_node
        )
        self.logger.info(f"💭 THOUGHT ({self.name})\n{thought}")
        self.logger.info(f"🎬 ACTION ({self.name})\n{action}")
        return current_node

    def local_history_with_action(self, last_node: DARSNode, expansion_context: str) -> List[Dict[str, str]]:
        base_history = self.local_history(last_node)
        info = ""
        if expansion_context:
            info = expansion_context
            last_message = base_history[-1]
            if last_message['role'] == 'user':
                last_message['content'] += f"\n\n{info}"
            else:
                base_history.append({"role": "user", "content": info})
        return base_history

    def forward_model(self, last_node: DARSNode, temperature: Optional[float] = None, expansion_context: str = None, query_model: str = None) -> str:

        if expansion_context:
            query = self.local_history_with_action(last_node, expansion_context)
        else:
            query = self.local_history(last_node)

        last_message = query[-1]
        self.logger.info(f"🤖 MODEL INPUT\n{last_message['content']}") 

        for hook in self.hooks:
            hook.on_model_query(query=query, agent=self.name)
        if query_model:
            return self.model.query(query, temperature=temperature, model_type=query_model)
        return self.model.query(query, temperature=temperature)

    def retry_after_format_fail(self, output: str, last_node: DARSNode) -> str:
        """Ask the model to correct (without committing to persistent history) after a malformatted model output"""
        format_error_template = self.config.format_error_template

        self.logger.warning(f"MALFORMED OUTPUT\n{output}")
        self.logger.warning(f"FORMAT ERROR\n{format_error_template}")

        temp_history = self.local_history(last_node) + [
            {"role": "assistant", "content": output, "agent": self.name},
            {"role": "user", "content": format_error_template, "agent": self.name},
        ]
        return self.model.query(temp_history, temperature=0.0)

    def retry_after_blocklist_fail(self, output: str, action: str, last_node: DARSNode) -> str:
        """Ask the model to correct (without committing to persistent history) after a disallowed command"""
        name = action.strip().split()[0]
        blocklist_error_message = self.config.blocklist_error_template.format(name=name)

        self.logger.warning(f"BLOCKLISTED OUTPUT\n{output}")
        self.logger.warning(f"BLOCKLIST ERROR\n{blocklist_error_message}")

        temp_history = self.local_history(last_node) + [
            {"role": "assistant", "content": output, "agent": self.name},
            {"role": "user", "content": blocklist_error_message, "agent": self.name},
        ]
        return self.model.query(temp_history)

    def should_block_action(self, action: str) -> bool:
        """Check if the command should be blocked."""
        names = action.strip().split()
        if len(names) == 0:
            return False
        name = names[0]
        if name in self.config.blocklist:
            return True
        if name in self.config.blocklist_standalone and name == action.strip():
            return True
        return False

    def check_format_and_requery(
        self,
        output: str,
        last_node: DARSNode,
    ) -> tuple[str, str, str]:

        # Condition for handling outputs with no thought (just action)
        if self.model.args.model_name == "human":
            return "", output, output
        elif self.model.args.model_name == "human_thought":
            thought, action = ParseFunction.get("ThoughtActionParser")(
                output,
                self.config._commands + self.config.subroutine_types,
                strict=False,
            )
            return thought, action, output

        format_fails = blocklist_fails = 0

        while format_fails + blocklist_fails <= 2:
            try:
                thought, action = self.config.parse_function(
                    output,
                    self.config._commands + self.config.subroutine_types,
                    strict=False,
                )
            except KeyboardInterrupt:
                raise
            except FormatError:
                format_fails += 1
                output = self.retry_after_format_fail(output, last_node)
                continue
            if self.should_block_action(action):
                blocklist_fails += 1
                output = self.retry_after_blocklist_fail(output, action, last_node)
            else:
                return thought, action, output
        self.logger.warning(f"Malformat limit reached: \n{output}")
        return "Exit due to format error", "exit_format", output

    def forward_with_error_check(self, last_node: DARSNode, temperature: Optional[float] = None, expansion_context: str = None, query_model: str = None) -> tuple[str, str, str]:

        try:
            output = self.forward_model(last_node, temperature, expansion_context, query_model=query_model)
        except KeyboardInterrupt:
            raise
        except RuntimeError as e:
            self.logger.warning(f"Runtime error: {e}")
            return (
                f"Exit due to runtime error: {e}",
                "exit_error",
                f"exit due to runtime error: {e}",
            )
        except ContextWindowExceededError:
            self.logger.warning("Context window exceeded")
            return "Exit due to context window", "exit_context", "Exit due to context window"
        except CostLimitExceededError:
            self.logger.warning("Cost limit exceeded")
            return "Exit due to cost limit", "exit_cost", "Exit due to cost limit"
        except RetryError as e:
            self.logger.warning(f"Retry error: {e}")
            return (
                f"Exit due to retry error: {e}",
                "exit_api",
                f"exit due to retry error: {e}",
            )
        return self.check_format_and_requery(output, last_node)

    def init_environment_vars(self, env: SWEEnv):
        self.set_environment_vars(env, self.config.env_variables)

    def set_environment_vars(self, env: SWEEnv, env_variables: dict[str, Any]) -> None:
        assert self.config is not None  # mypy
        commands_to_execute = (
            [self.config.state_command.code]
            +
            # [code for code in self.config.util_functions] +
            # [command.code for command in self.config._commands] +
            [f"{k}={v}" for k, v in env_variables.items()]
        )
        commands = "\n".join(commands_to_execute)
        try:
            output = env.communicate(commands)
            if env.returncode != 0:
                msg = f"Nonzero return code: {env.returncode}\nOutput: {output}"
                raise RuntimeError(msg)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.logger.warning("Failed to set environment variables")
            raise e
        command_files = list()
        for file in self.config.command_files:
            datum = dict()
            with open(file) as f:
                contents = f.read()
            datum["contents"] = contents
            filename = Path(file).name
            if not contents.strip().startswith("#!"):
                if filename.endswith(".sh"):
                    # files are sourced, so they are not executable
                    datum["name"] = Path(file).name
                    datum["type"] = "source_file"
                elif filename.startswith("_"):
                    # files are sourced, so they are not executable
                    datum["name"] = Path(file).name
                    datum["type"] = "utility"
                else:
                    msg = (
                        f"Non-shell script file {file} does not start with shebang.\n"
                        "Either add a shebang (#!) or change the file extension to .sh if you want to source it.\n"
                        "You can override this behavior by adding an underscore to the file name (e.g. _utils.py)."
                    )
                    raise ValueError(msg)
            else:
                # scripts are made executable
                datum["name"] = Path(file).name.rsplit(".", 1)[0].lstrip('_')
                datum["type"] = "script"
            command_files.append(datum)
        env.add_commands(command_files)

    def get_environment_vars(self, env: SWEEnv) -> dict[str, Any]:
        """Get environment variables"""
        assert self.config is not None  # mypy
        env_vars = dict()
        for var in self.config.env_variables:
            env_vars[var] = env.communicate(f"echo ${var}").strip()
        return env_vars

    def call_subroutine(self, agent_name: str, sub_action, env: SWEEnv, last_node: DARSNode):
        assert self.config is not None  # mypy
        env_vars = self.get_environment_vars(env)
        cwd = env.communicate("pwd -P").strip()
        init_observation = self.config._subroutines[agent_name].init_observation
        if init_observation is not None:
            obs, _, _, _ = env.step(init_observation.format(args=sub_action["args"]))
        else:
            obs = None
        if env.returncode != 0:
            self._append_history({"role": "user", "content": obs, "agent": agent_name})
            msg = f"Nonzero return code: {env.returncode} for init_observation in {agent_name}.\n{obs}"
            raise RuntimeError(msg)
        return_type = self.config._subroutines[agent_name].return_type
        sub_agent = DARSAgent(agent_name, self.config._subroutines[agent_name].agent_args)
        sub_agent_output = sub_agent.run(
            {"issue": sub_action["args"]},
            env,
            observation=obs,
            return_type=return_type,
            init_model_stats=self.model.stats,
        )
        self._merge_sub_agent_history(sub_agent, last_node)
        self.set_environment_vars(env, env_vars)
        env.communicate(f"cd {cwd}")
        self.model.stats.replace(sub_agent.model.stats)
        return sub_agent_output
    
    def get_codegraph_path(self, env: SWEEnv) -> str:
        base_path = "/root/persistent_data" if env.args.persistent_volume else ""
        code_graph_path = f"{base_path}/{env.record['instance_id']}"
        return code_graph_path

    def _merge_sub_agent_history(self, sub_agent: DARSAgent, last_node: DARSNode):
        sub_root = sub_agent.root_node
        if sub_root:
            last_node.add_child(sub_root)

    def _observation_state_to_node(self, last_node: DARSNode, observation: str, state: str) -> DARSNode:
        state_vars = json.loads(state)
        templates: list[str] = []

        if last_node.role == "system" or getattr(last_node, 'is_demo', False):
            templates = [self.config.instance_template]
            if self.config.strategy_template is not None:
                templates.append(self.config.strategy_template)
        elif observation is None or observation.strip() == "":
            templates = [self.config.next_step_no_output_template]
        elif last_node.codegraph_context and last_node.codegraph_keyword:  # Just check the immediate node
            templates = [self.config.next_step_codegraph_template]
        else:
            templates = [self.config.next_step_template]

        messages = []
        for template in templates:
            messages.append(
                template.format(
                    **self.instance_args,
                    **self.system_args,
                    **state_vars,
                    observation=(observation if observation is not None else ""),
                    codegraph_context=(last_node.codegraph_context if last_node.codegraph_context is not None else ""),
                    search_term=(last_node.codegraph_keyword if last_node.codegraph_keyword is not None else "")
                ),
            )
        message = "\n".join(messages)

        return self._append_history({
            "role": "user", 
            "content": message, 
            "agent": self.name,
            "codegraph_context": last_node.codegraph_context,
            "codegraph_keyword": last_node.codegraph_keyword
        }, parent_node=last_node)

    def reset_env_to_node(self, env: SWEEnv, node: DARSNode) -> None:
        env.reset(index=self.index)

        if env.container_obj.id != self.last_container_id:
            self.logger.info(f"Initializing agent settings for container {env.container_obj.id}")
            self.init_environment_vars(env)
            self.last_container_id = env.container_obj.id

        actions = []
        current = node
        while current.parent:
            if current.action:
                actions.append(current.action)
            current = current.parent
        actions.reverse()
        
        for action in actions:
            run_action = self._guard_multiline_input(action)
            for sub_action in self.split_actions(run_action):
                if sub_action["agent"] == self.name or sub_action["cmd_name"] == self.config.submit_command:
                    env.step(sub_action["action"])
                else:
                    agent_name = sub_action["agent"]
                    self.call_subroutine(agent_name, sub_action, env, node)
        
    def get_expansion_prompt(self, node: DARSNode) -> str:
        _command_handlers = {
            'edit': self.config.DARS_prompts.edit_expansion_prompt_template,
            'insert': self.config.DARS_prompts.insert_expansion_prompt_template,
            'append': self.config.DARS_prompts.append_expansion_prompt_template,
            'submit': self.config.DARS_prompts.submit_expansion_prompt_template,
            'create': self.config.DARS_prompts.create_expansion_prompt_template,
        }

        action = node.parent.action.split()[0]
        prompt_template = _command_handlers.get(action, '')
        if action != 'create' and action != 'submit':
            lookahead = self.config.DARS.n_lookahead
            context = ""
            patch = ""
            tmp = node.parent
            while lookahead:
                if tmp.action.split()[0] == "submit":
                    patch = tmp.children[0].content
                    if self.config.DARS.summarize_expansion_context:
                        break
                context += "ACTION: " + tmp.action + "\n"
                context += "OBERSERVATION: " + tmp.children[0].content[-10000:] + "\n\n"
                if not tmp.children or not tmp.children[0].children:
                    break
                tmp = tmp.children[0].children[0]
                lookahead -= 1
            if self.config.DARS.summarize_expansion_context:
                context = self.summarize_content(context, patch)
            return prompt_template.format(action=node.parent.action, prev_traj=context)
        return prompt_template

    def summarize_content(self, content: str, patch: str) -> str:

        summarization_prompt = self.config.DARS_prompts.summarization_prompt_template.format(next_steps=content, issue=self.instance_args['issue'])
        out = self.model.query([{"role": "user", "content": summarization_prompt, "agent": self.name}])
        if patch != '': 
            out += "\n" + "Finally the model submitted the following changes:\n" + patch
        return out

    def extract_best_action_index(self, response):
        pattern = r'<best_action_index>(\d+)</best_action_index>'
        match = re.search(pattern, response)
        if match:
            return int(match.group(1))
        raise ValueError("No best action index found in response")

    def select_expansion(self, node: DARSNode, actions: str) -> DARSNode:
        actions_context = ""
        for i, action in enumerate(actions):
            actions_context += f"Action {i}:\n{action}\n"
        critic_prompt = self.config.DARS_prompts.critic_expansion_prompt_template.replace("{actions}", f'\n{"".join(actions)}').replace("{previous_action}", node.children[0].action)
        response = self.forward_model(node, expansion_context=critic_prompt)
        try:
            action_index = self.extract_best_action_index(response)
        except Exception as e:
            self.logger.warning(f"Error in selecting expansion: {e}")
            action_index = 0
        return action_index, critic_prompt, response

    def get_expansion_action(self, node: DARSNode) -> DARSNode:
        actions = []
        thought_outs = []
        num_expansion_sampling = self.config.DARS.num_expansion_sampling
        expansion_context = self.get_expansion_prompt(node.children[0].children[0])
        for _ in range(num_expansion_sampling):
            thought, action, output = self.forward_with_error_check(node, temperature=self.config.DARS.expansion_temperature, expansion_context=expansion_context)
            actions.append(action)
            thought_outs.append((thought, action, output))
        index, critic_prompt, critic_response = self.select_expansion(node, actions)
        try:
            thought, action, output = thought_outs[index]
        except Exception as e:
            self.logger.error(f"Error in selecting expansion: {e}")
            index = 0
            thought, action, output = thought_outs[0]
        new_node = self._append_history(
            {
                "role": "assistant",
                "content": output,
                "thought": thought,
                "action": action,
                "agent": self.name,
                "critic_prompt": critic_prompt,
                "critic_response": critic_response,
                "expansion_prompt": expansion_context,
                "expansion_candidates": thought_outs
            },
            parent_node=node
        )
        self.logger.info(f"💭 THOUGHT ({self.name})\n{thought}")
        self.logger.info(f"🎬 ACTION ({self.name})\n{action}")
        return new_node

    def expand(self, node: DARSNode, env: SWEEnv, traj_dir: str = None) -> DARSNode:
        assert node.role == "user"
        self.logger.info(f"Parent Node depth: {node._depth} in expand function")
        num_expansions = self.config.DARS.num_expansions
        expansion_id = len(node.children) + 1
        if expansion_id > 1:
            self.reset_env_to_node(env, node)
        self.logger.info(f"Expansion Number: {expansion_id}")
        
        # Generate assistant node
        if expansion_id == 1:
            assistant_node = self.forward(node, env.get_available_actions())
        else:
            assistant_node = self.get_expansion_action(node)
            first_child_action_type = node.children[0].action.split()[0]
            assistant_node.expansion_history.append(first_child_action_type)
            
        action = assistant_node.action
        observations = []
        run_action = self._guard_multiline_input(action)
        done = False

        # Execute actions
        for sub_action in self.split_actions(run_action):
            if sub_action["agent"] == self.name or sub_action["cmd_name"] == self.config.submit_command:
                try:
                    if 'search_repo' in sub_action["action"]:
                        action = sub_action['action'].strip()
                        search_term = action.split(' ', 1)[1] if len(action.split(' ', 1)) > 1 else ""
                        codegraph_path = self.get_codegraph_path(env)
                        self.logger.info(f'Calling Retrieve Graph with search term: {search_term} and codegraph path {codegraph_path}')   
                        obs = env.communicate(f'python /root/retrieve_graph.py --search_term {search_term} --codegraph_dir {codegraph_path}')
                        self.logger.info('current codegraph keyword:\n' + search_term)
                        self.logger.info('current codegraph context:\n' + obs)
                        observations.append(obs)
                        # Set codegraph info in the assistant node
                        assistant_node.codegraph_keyword = search_term
                        assistant_node.codegraph_context = obs
                    else:
                        obs, _, done, info = env.step(sub_action["action"])
                        observations.append(obs)
                except Exception as e:
                    self.logger.error(f"Error in expansion: {e}")
                    done=False
                    obs = f'There was an error: {e} in executing the COMMAND\nTry Again.'
                    observations.append(obs)
                    info = {'model_stats': {'total_cost': 0.0, 'instance_cost': 0.0, 'tokens_sent': 0, 'tokens_received': 0, 'api_calls': 0}}

                if sub_action["cmd_name"] == self.config.submit_command:
                    done = True
                if "submit" in sub_action["action"]:  
                    assistant_node.is_terminal = True
                    done = True
                if done:
                    assistant_node.is_terminal = True
                    break
            else:
                agent_name = sub_action["agent"]
                sub_agent_output = self.call_subroutine(agent_name, sub_action, env, assistant_node)
                observations.append(sub_agent_output)

        observation = "\n".join([obs for obs in observations if obs is not None])
        state = env.communicate(self.state_command) if self.state_command else None
        if expansion_id == 1:
            if_expand = assistant_node.should_expand(self.config.DARS)
            if if_expand:
                assistant_node._action_expansion_limit[assistant_node.action.split()[0]] -= 1
                for _ in range(num_expansions-1):
                    self.node_stack.append(assistant_node.parent)
                self.node_stack.sort(key=lambda x: x._depth)
        user_node = self._observation_state_to_node(assistant_node, observation, state)
        self.add_node_id(user_node)
        return user_node

    def create_DARS_node_from_json(self, json_data, parent=None):
        role = json_data.get('role', '')
        content = json_data.get('content', '')
        agent = json_data.get('agent', '')
        thought = json_data.get('thought')
        action = json_data.get('action')
        is_demo = json_data.get('is_demo', False)
        is_terminal = json_data.get('is_terminal', False)
        _depth = json_data.get('_depth', None)
        node_id = json_data.get('node_id', None)
        expansion_history = json_data.get('expansion_history', [])
        _action_expansion_limit = json_data.get('_action_expansion_limit', {})
        codegraph_keyword = json_data.get('codegraph_keyword')
        codegraph_context = json_data.get('codegraph_context')

        node = DARSNode(
            role=role,
            content=content,
            agent=agent,
            thought=thought,
            action=action,
            parent=parent,
            is_demo=is_demo,
            is_terminal=is_terminal,
            _depth=_depth
        )
        node._depth = _depth
        node.node_id = node_id
        node.expansion_history = expansion_history
        node._action_expansion_limit = _action_expansion_limit
        node.codegraph_keyword=codegraph_keyword
        node.codegraph_context=codegraph_context
        node.expansion_prompt = json_data.get('expansion_prompt', '')
        node.critic_prompt = json_data.get('critic_prompt', '')
        node.critic_response = json_data.get('critic_response', '')
        node.expansion_candidates = json_data.get('expansion_candidates', [])

        children = json_data.get('children', [])
        for child_data in children:
            child_node = self.create_DARS_node_from_json(child_data, parent=node)
            child_node.parent = node
            node.children.append(child_node)
        return node

    def node_to_dict(self, node: DARSNode) -> Dict[str, Any]:
        return {
            "role": node.role,
            "content": node.content,
            "thought": node.thought,
            "action": node.action,
            "agent": node.agent,
            "is_demo": node.is_demo,
            "is_terminal": node.is_terminal,
            "children": [self.node_to_dict(child) for child in node.children],
            "_depth": node._depth,
            "node_id": node.node_id,
            "expansion_history": node.expansion_history,
            "_action_expansion_limit": node._action_expansion_limit,
            "codegraph_keyword": node.codegraph_keyword,
            "codegraph_context": node.codegraph_context,
            "expansion_prompt": node.expansion_prompt,
            "critic_prompt": node.critic_prompt,
            "critic_response": node.critic_response,
            "expansion_candidates": node.expansion_candidates
        }

    def node_id_to_node(self, node: DARSNode, node_id_to_node: Dict = {}) -> Dict[int, DARSNode]:
        if node.node_id:
            node_id_to_node[node.node_id] = node

        for child in node.children:
            self.node_id_to_node(child, node_id_to_node)

        return node_id_to_node

    def save_trajectory(
        self, trajectory: list[dict[str, Any]], log_path: Path, env_name: str, info: dict[str, Any], last_node: DARSNode
    ) -> None:
        """Save the trajectory"""
        log_dict = {
            "environment": env_name,
            "trajectory": trajectory,
            "history": self.local_history(last_node),
            "info": info,
        }
        log_path.write_text(json.dumps(log_dict, indent=2))

    def auto_submit(self, node: DARSNode, env: SWEEnv) -> DARSNode:
        if node.children is None or len(node.children) == 0:
            if node.role == "user" and not node.parent.action.startswith("submit"):
                current_node = self._append_history(
                    {
                        "role": "assistant",
                        "content": "Auto-submitting\n```submit\n```",
                        "thought": "Auto-submitting",
                        "action": "submit\n",
                        "agent": self.name,
                    },
                    parent_node=node
                )
                self.logger.info(f"💭 THOUGHT ({self.name})\nAuto-submitting")
                self.logger.info(f"🎬 ACTION ({self.name})\nsubmit")
                self.reset_env_to_node(env, node)
                obs, _, done, info = env.step('submit\n')
                observation = obs
                state = env.communicate(self.state_command) if self.state_command else None
                user_node = self._observation_state_to_node(current_node, observation, state)
                self.add_node_id(user_node)
                return
        for child in node.children:
            self.auto_submit(child, env)    

    def run(
        self,
        setup_args: dict[str, Any],
        env: SWEEnv,
        observation: str | None = None,
        traj_dir: Path | None = None,
        return_type: str | None = "info_trajectory",
        init_model_stats: APIStats | None = None,
        index: int | None = None,
    ):
        self.node_stack = []
        self.setup_args = setup_args
        self.index = index
        self.init_model_stats = init_model_stats

        if env.container_obj.id != self.last_container_id:
            self.logger.info(f"Initializing agent settings for container {env.container_obj.id}")
            self.init_environment_vars(env)
            self.last_container_id = env.container_obj.id
        starting_node = self.setup(setup_args, init_model_stats)

        for hook in self.hooks:
            hook.on_run_start()

        traj_log_path = traj_dir / (env.record["instance_id"] + ".traj")
        self.logger.info("Trajectory will be saved to %s", traj_log_path)

        state = env.communicate(self.state_command) if self.state_command else None
        current_node = self._observation_state_to_node(starting_node, observation, state)
        current_node._depth = 0
        self.node_count = 0
        self.add_node_id(current_node)

        if self.config.DARS.resume_path:
            assert os.path.exists(self.config.DARS.resume_path), f"Path {self.config.DARS.resume_path} does not exist"

            self.logger.info(f"Resuming from path: {self.config.DARS.resume_path}")

            # load the root node from the resume path
            with open(self.config.DARS.resume_path, "r") as f:
                checkpoint = json.load(f)
                root_data = checkpoint["root"]
                iterations = checkpoint["iterations"]
                self.node_count = checkpoint["node_count"]
                current_node_id = checkpoint["current_node_id"]
                node_id_stack = checkpoint["node_id_stack"]   

            self.root_node = self.create_DARS_node_from_json(root_data)
            node_id_to_node = self.node_id_to_node(self.root_node)
            self.node_stack = [node_id_to_node[node_id] for node_id in node_id_stack]
            if self.config.DARS.auto_submit:
                to_submit_node = node_id_to_node[1].parent.parent
                iterations = 0
                self.auto_submit(to_submit_node, env)
            current_node = node_id_to_node[current_node_id]

        for hook in self.hooks:
            hook.on_step_start()

        num_iterations = self.config.DARS.num_iterations if not self.config.DARS.resume_path else iterations
        while num_iterations:
            self.logger.info("Iteration Remaining: %s", num_iterations)
            if current_node is None or current_node._depth >= self.config.DARS.max_branch_depth or current_node.is_terminal:
                # we should start exploring a new branch
                if self.node_stack:
                    current_node = self.node_stack.pop(0)
                else:
                    break

            current_node = self.expand(current_node, env, traj_dir)

            if traj_dir:
                try:
                    root_dict = self.node_to_dict(self.root_node)
                    instance_id = env.record["instance_id"]

                    root_log_path_cur = traj_dir / f"{instance_id}.cur.root"
                    root_log_path_prev = traj_dir / f"{instance_id}.prev.root"

                    checkpoint = {
                        "root": root_dict,
                        "iterations": num_iterations,
                        "node_count": self.node_count,
                        "current_node_id": current_node.node_id,
                        "node_id_stack": [node.node_id for node in self.node_stack]
                    }

                    checkpoint_json = json.dumps(checkpoint, indent=2)

                    tmp_cur = traj_dir / f"{instance_id}.cur.tmp"
                    with open(tmp_cur, "w") as f:
                        f.write(checkpoint_json)
                    os.replace(tmp_cur, root_log_path_cur)

                    if root_log_path_cur.exists():
                        shutil.copy2(root_log_path_cur, root_log_path_prev)

                except Exception as e:
                    self.logger.error("Failed to save checkpoint: %s", e)
                    continue
                
            num_iterations -= 1

        trajectory = []
        info = {}

        # Get first path nodes (leftmost path from root)
        current = self.root_node
        path_nodes = []
        while current and current.children:
            if current.action:  # Skip nodes without actions (like initial system/user nodes)
                path_nodes.append(current)
            current = current.children[0]  # Always take first child
        if current and current.action:  # Add last node if it has an action
            path_nodes.append(current)

        # Construct trajectory directly from stored information
        for node in path_nodes:
            trajectory_step = TrajectoryStep(
                {
                    "action": node.action,
                    "observation": node.children[0].content if node.children else "",
                    "response": node.content,
                    "state": None,  # State isn't critical for most use cases
                    "thought": node.thought,
                },
            )
            trajectory.append(trajectory_step)

        # Finalize model stats and save trajectory
        model_stats: APIStats = self.model.stats
        info["model_stats"] = model_stats.to_dict()
        if traj_dir:
            self.save_trajectory(trajectory, traj_log_path, env_name=env.name, info=info, last_node=path_nodes[-1])
            # Save final root node state
            root_dict = self.node_to_dict(self.root_node)
            root_log_path = traj_dir / (env.record["instance_id"] + ".root")
            checkpoint = {
                "root": root_dict,
                "iterations": num_iterations,
                "node_count": self.node_count,
                "current_node_id": current_node.node_id,
                "node_id_stack": [node.node_id for node in self.node_stack]
            }
            with open(root_log_path, "w") as f:
                json.dump(checkpoint, f, indent=2)

        for hook in self.hooks:
            hook.on_run_done()

        self.logger.info("Trajectory saved to %s", traj_log_path)

        if return_type == "info":
            return info
        if return_type == "info_trajectory":
            return info, trajectory
        return trajectory[-1][return_type]