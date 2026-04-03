import os


def load_script(script_name: str):
    dirname = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(dirname, script_name + ".js")
    if not os.path.exists(script_path):
        raise Exception(f"Script {script_path}.js not found")
    with open(script_path) as file:
        return file.read()
