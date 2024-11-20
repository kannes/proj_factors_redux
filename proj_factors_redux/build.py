import glob

from qgis_plugin_tools.infrastructure.plugin_maker import PluginMaker


profile = 'default'
py_files = [fil for fil in glob.glob("**/*.py", recursive=True) if "test/" not in fil]
ui_files = list(glob.glob("**/*.ui", recursive=True))
extra_dirs = ["resources"]
compiled_resources = []

PluginMaker(py_files=py_files, ui_files=ui_files, extra_dirs=extra_dirs,compiled_resources=compiled_resources,profile=profile)