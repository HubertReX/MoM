import sys

sys.path.append("project")

from project.enums import TaskEnum  # noqa: E402
from project.main import init  # noqa: E402
# try:
# except ImportError as e:
#     print(e)
#     with open("debug.log", "w") as f:
#         f.write(repr(e))

if __name__ == "__main__":
    # print("test")
    init()
