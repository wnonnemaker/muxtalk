#!/usr/bin/env python3
from ubix.tool_runner import ToolRunner
import importlib.resources

runner = ToolRunner()
command = "open my math textbook" 
print(f'executing command: {command}')
runner.execute(command)
