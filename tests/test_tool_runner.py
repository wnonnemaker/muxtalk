from ubix.tool_runner import ToolRunner

def test_switch_mode():
    runner = ToolRunner()
    with open(mode_path) as f:
        data = f.read()
    print(f'mode from file is: {data}')
    command = "Switch to scribe mode" 
    print(f'executing command: {command}')
    runner.execute(command)
    with open(mode_path) as f:
        data = f.read()
    print(f'mode from file is: {data}')
    command = "set active pane to ubix 2 0" 
    print(f'executing command: {command}')
    runner.execute(command)
    command = "I remember it being a sunny day in philly" 
    print(f'executing command: {command}')
    runner.execute(command)
