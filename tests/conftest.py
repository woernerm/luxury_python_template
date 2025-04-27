import re
import importlib
from pathlib import Path
from collections import defaultdict

RE_WORD_BOUNDARY = re.compile(r"([^_])(_)(.)")
GROUP_WORD_BOUNDARY = 2

def to_sentence(snake_str: str) -> str:
    """Convert snake_case string to a sentence."""
    # Replace underscores with spaces and capitalize the first letter
    return re.sub(RE_WORD_BOUNDARY, r"\1 \3", snake_str).capitalize()

def get_requirement(item):
    """ Convert a test item to a requirement. """
    return to_sentence(item.name) or item.instance.__doc__
     
def pytest_collection_modifyitems(session, config, items):
    packagemod = importlib.import_module("package", "..")
    meta = packagemod.Meta("pyproject.toml")
    settings = packagemod.Settings()

    project = meta.get("name")
    copyright = meta.getCopyright()
    author = ", ".join(meta.getAuthors())
    release = meta.get("version")

    mod_prefix = str(settings.TEST_DIR.relative_to(Path.cwd()))

    # Write requirements to json file
    with open(settings.REQUIREMENTS_FILE, "w") as f:
        f.write(f"# {project}\n")
        f.write(f"**Author(s)**: {author}\n\n")
        f.write(f"**Copyright**: {copyright}\n\n")
        f.write(f"**Release(s)**: {release}\n\n")
        f.write(f"## Requirements\n")

        requirements = defaultdict(list)
        for item in items:
            modname = item.module.__name__
            requirements[modname].append(item)

        for modname, content in requirements.items():
            modname = (
                str(modname).removeprefix(f"{mod_prefix}.")
                .replace("test_", "").replace(".", " ").capitalize()
            )
            f.write(f"### {modname}\n")
            for id_, item in enumerate(content):
                text = get_requirement(item)            
                f.write(f"#### ID: {id_+1}\n\n")
                f.write(f"{text}\n\n")         