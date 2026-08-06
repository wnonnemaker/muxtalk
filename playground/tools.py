#!/usr/bin/env python3
import ubix
import importlib.resources
import logging
from ubix.tool_runner import ToolRunner

runner = ToolRunner()
command = "i want to see my latin textbook" 
print(f'executing command: {command}')
runner.execute(command)
