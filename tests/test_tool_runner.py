from ubix.tool_runner import ToolRunner
import unittest

class TestToolMethods(unittest.TestCase):
    def test_switch_mode(self):
        runner = ToolRunner(True)
        command = "Switch to scribe mode" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "change_mode")
        self.assertEqual(result.args['mode'], "scribe")


    def test_open_document_file(self):
        runner = ToolRunner(True)
        command = "open my math textbook" 
        print(f'executing command: {command}')
        runner.execute(command)

    def test_lock_insert(self):
        runner = ToolRunner(True)
        runner.change_mode("scribe")
        command = "lock insert" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "toggle_insert")
        command = "hello claude this is a command for muxtalk" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "write")

    def test_connect_bluetooth(self):
        runner = ToolRunner()
        command = "disconnect bluetooth headphones" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "edit_bt_connection")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.args['connect_or_disconnect'], 'disconnect')
        command = "Connect to bluetooth headphones" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "edit_bt_connection")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.args['connect_or_disconnect'], 'connect')

    def string_commands_together(self):
        runner = ToolRunner()
        command = "disconnect bluetooth headphones" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "edit_bt_connection")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.args['connect_or_disconnect'], 'disconnect')
        command = "Connect to bluetooth headphones, then resume my music" 
        print(f'executing command: {command}')
        result = runner.execute(command)
        self.assertEqual(result.tool, "edit_bt_connection")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.args['connect_or_disconnect'], 'connect')


if __name__ == '__main__':
    unittest.main()
