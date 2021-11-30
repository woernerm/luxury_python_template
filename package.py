"""
The all-in-one python package management tool.

There are lots of tools available that you can use to monitor and improve the
quality of your package. However, you have to configure them, remember how they work,
think about the order in which to execute them, parse their output to get badges and
finally clean up after them. It's easy to forgo this tedious work in the beginning when
all you can think about is the bright idea behind your new python package. Will you do
that later on? Probably not, because then chances are high that you get hundreds of
complaints from these tools and fixing them all will likely set you back for weeks.
Its way more fun to focus on new features anyway.

Meet package.py: It provides short, easy to remember commands for building, testing,
styling, security checking, documentation generation and more. No configuration
required. It keeps your package always clean and tidy by removing intermediate build
artifacts as well as empty folders. It compiles the output into a single, beautiful
report and meaningful badges so you can monitor the most important metrics right from
the start of development.

Just call
```py
python package.py --help
```
for additional information. By the way: The name is no coincidence: It's chosen such that
you can just hit tab for autocompletion after the first "p" of "package.py". Makes for
faster typing. ;)
"""
import argparse
import glob
import importlib
import inspect
import json
import math
import multiprocessing
import os
import pkgutil
import re
import runpy
import shutil
import sys
from typing import Union, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import contextlib
import io
import platform


class Settings:
    """
    Class for storing all configuration options.

    You can change the default settings directly in this class.
    """

    # Base directory of the repository.
    BASE_DIR = Path(__file__).parents[0]

    # Directory where the package source code can be found.
    SRC_DIR = BASE_DIR / "src"

    # Directory for placing all reports.
    REPORT_DIR = BASE_DIR / "report"

    # Directory in which the report template can be found.
    REPORT_TEMPLATE_DIR = BASE_DIR / "data" / "report_template"

    # Path to the report template.
    REPORT_TEMPLATE_FILE = REPORT_TEMPLATE_DIR / "report.jinja"

    # Path to the main report file.
    REPORT_HTML = REPORT_DIR / "report.html"

    # Directory for placing additional files used by the report.
    REPORT_FILES_DIR = REPORT_DIR / "files"

    # Name of the report section about code style.
    REPORT_SECTION_NAME_STYLE = "Style"

    # Name of the report section about testing.
    REPORT_SECTION_NAME_TEST = "Test"

    # Name of the report section about vulnerabilities found in dependencies (safety).
    REPORT_SECTION_NAME_DEPENDENCIES = "Dependencies"

    # Name of the report section about security (bandit).
    REPORT_SECTION_NAME_SECURITY = "Security"

    # Name of the report section about documentation.
    REPORT_SECTION_NAME_DOCUMENTATION = "Documentation"

    # The report shows code snippets. These snippets typically have only a few lines
    # that are of interest to the user. However, additional lines before and after the
    # relevant ones are also shown to provide some context. The number of lines before
    # and after is specified here.
    REPORT_LINE_RANGE = 10

    # Root directory for documentation.
    DOCUMENTATION_ROOT_DIR = BASE_DIR / "docs"

    # The directory in which the generated html documentation is stored.
    DOCUMENTATION_HTML_DIR = DOCUMENTATION_ROOT_DIR / "html"

    # Directories in the html output that can be deleted, because they are irrelevant.
    DOCUMENTATION_HTML_DIR_EXCLUDE = [
        DOCUMENTATION_HTML_DIR / ".doctrees",
        DOCUMENTATION_HTML_DIR / "_sources",
        DOCUMENTATION_ROOT_DIR / "build",
        DOCUMENTATION_ROOT_DIR / "doctrees",
    ]

    # Temporary directory for storing generated documentation source files.
    DOCUMENTATION_SOURCE_DIR = DOCUMENTATION_ROOT_DIR / "source"

    # Directory in which documentation templates are stored.
    DOCUMENTATION_TEMPLATE_DIR = DOCUMENTATION_ROOT_DIR / "templates"

    # Directory in which build artifacts are placed.
    DISTRIBUTABLE_DIR = BASE_DIR / "dist"

    # The file that contains package configuration for setuptools.
    CONFIGFILE = BASE_DIR / "setup.cfg"

    # Directory in which badges are stored.
    BADGE_FOLDER = BASE_DIR / "data" / "badges"

    # **********************************************
    # *** This section specifies temporary files ***
    # **********************************************

    # Folder into which json for analyzing dependencies are placed.
    TMP_DIR = BASE_DIR / "tmp"

    # Folder in which mypy stores its cache.
    MYPY_CACHE = BASE_DIR / ".mypy_cache"

    # Temporary directory for build files.
    BUILD_DIR = BASE_DIR / "build"

    # The file in which test coverage information is stored (for the coverage package).
    TEST_COVERAGE_FILE = BASE_DIR / ".coverage"

    # The file in which test coverage information is stored (for parsing by package.py).
    TEST_COVERAGE_JSON = TMP_DIR / "coverage.json"

    # Search expression for pip's requirement files. Each file found will be evaluated
    # by safety to detect dependency vulnerabilities.
    SECURITY_REQUIREMENTS_GLOB = str(BASE_DIR / "req") + "*.txt"

    # The file in which bandit's results are stored (for parsing by package.py).
    SECURITY_BANDIT_JSON = TMP_DIR / "bandit.json"

    # The file in which security test information about the currently active environment
    # is stored (for parsing by package.py). Note that not only requirement files
    # will be evaluated by safety but also the currently active environment (the one
    # package.py was called from).
    SECURITY_ACTIVE_JSON = TMP_DIR / "environment.json"

    # The file in which style violations are documented.
    STYLE_REPORT_JSON = TMP_DIR / "style.json"

    # THe file in which type errors are documented.
    TYPE_REPORT_XML = TMP_DIR / "type.xml"

    # File for storing warnings about undefined or undocumented Python code.
    DOCUMENTATION_COVERAGE_FILE = TMP_DIR / "doccoverage.json"

    # ******************************************************
    # *** This section specifies colors for badges files ***
    # ******************************************************

    # Thresholds for the badge colors that indicate the test coverage. Each dictionary
    # key corresponds to the minimum coverage necessary for using the color given as
    # dictionary value. The badge will use the highest key value for which
    # coverage >= key.
    TEST_COVERAGE_THRESHOLDS = {
        99: "brightgreen",
        98: "green",
        96: "yellowgreen",
        94: "yellow",
        90: "orange",
    }

    # Thresholds for the badge colors that indicate the documentation coverage. Each
    # dictionary key corresponds to the minimum coverage necessary for using the color
    # given as  dictionary value. The badge will use the highest key value for which
    # coverage >= key.
    DOCUMENTATION_COVERAGE_THRESHOLDS = {
        99: "brightgreen",
        98: "green",
        96: "yellowgreen",
        94: "yellow",
        90: "orange",
    }

    # Thresholds for the badge colors that indicate the number of security issues. Each
    # dictionary key corresponds to the maximum issues necessary for using the color
    # given as  dictionary value. The badge will use the lowest key value for which
    # number of issues <= key.
    SECURITY_ISSUES_THRESHOLDS = {0: "brightgreen"}


def require(requirements: List[Tuple[str, Optional[str]]], install: bool = False):
    """
    Installs the given module, if it is not available.

    Args:
        requirements: List of tuples describing the required dependencies. Each tuple
            is defined as (modulename, packagename). The packagename only has to be
            given, if it differs from the modulename. Otherwise, you can write None
            instead of packagename.
        install: If True, missing modules will automatically be installed. In the same
            case, the function will return False and not install anything if the
            parameter is set to False.

    Returns:
        True, if the given module is installed. False, otherwise.
    """

    notinstalled = []
    for requirement in requirements:
        modulename = requirement[0]
        packagename = modulename if requirement[1] is None else requirement[1]

        try:
            importlib.import_module(modulename)
        except ModuleNotFoundError:
            if install:
                pyexecute(["pip", "install", packagename])
                # Make sure that the running script finds the new module.
                importlib.invalidate_caches()
            else:
                notinstalled.append(requirement)

    return notinstalled


def remove_if_exists(path: Union[Path, str]):
    """
    Deletes a given file or folder, if it exists.

    Args:
        path: The path to the file or folder to delete.
    """
    if os.path.isfile(str(path)):
        os.remove(str(path))
    if os.path.isdir(str(path)):
        shutil.rmtree(str(path))


def remove_if_empty(path: Union[Path,str]):
    """
    Deletes a given folder, if it is empty.

    Args:
        path: The path to the folder that shall be deleted, if it is empty.
    """
    if os.path.isdir(str(path)) and len(os.listdir(str(path))) == 0:
        shutil.rmtree(str(path))


def mkdirs_if_not_exists(path: Union[str, Path]):
    """
    Creates the given folder path, if it does not exist already.

    Args:
        path: The folder path that shall be created.
    """
    if not os.path.isdir(str(path)):
        os.makedirs(str(path))


def runner(cmd: list):
    """
    Runs a module in a separate process.

    Args:
        cmd: The command to run. First entry must be the module to execute, e.g.
            "pip" for pip for "sphinx.ext.apidoc" for the sphinx apidoc extension.
    """

    # Create the list of arguments to provide to the executed module. For this, obtain
    # the file path for the module and set it as first argument, then copy the remaining
    # arguments as they are to the argument list.
    path = Path(pkgutil.get_loader(cmd[0]).path) # type: ignore
    apppath = path.parents[0] / "__main__.py" if path.name == "__init__.py" else path
    arguments = list([str(apppath)])
    arguments += cmd[1:]

    # Provide arguments to the module and run the module.
    sys.argv = arguments

    # Run module and silence error messages as well as findings except for pip.
    out_err = sys.stderr if cmd[0] == "pip" else io.StringIO()

    with contextlib.redirect_stderr(out_err):
        try:
            runpy.run_module(cmd[0], run_name="__main__")
        except Exception as e:
            print(f"Running command {' '.join(cmd)} failed:\n{str(e)}")


def pyexecute(cmd: list):
    """
    Runs shell commands in a more secure way.

    Shell commands are executed using the absolute python path with which the script
    was started.

    Args:
        cmd: Command to execute as a list of arguments.

    Returns:
        The exit code of the process that ran the module.
    """
    if type(cmd) is not list:
        raise Exception(
            "Expected type list for parameter cmd. "
            + f"Instead got {type(cmd).__name__}."
        )

    p = multiprocessing.Process(
        target=runner,
        args=(cmd,),
    )
    p.start()
    p.join()
    return p.exitcode


class Report:
    """
    Generates an HTML report.

    The report is structured in sections, each intended for one aspect of code analysis.
    For example, one section may show dependency vulnerabilities, and another may show
    undocumented code. The main methods are report() to populate the sections and
    render() to output the HTML files. There are several subclasses which model different
    ways of presenting information like List and Table. In addition, the File subclass
    is used for showing code snippets. For example, on the main page the user may click
    on an issue and gets to another page highlighting the troublesome piece of code.
    """

    SUMMARY_NAME = "name"
    SUMMARY_VALUE = "value"
    SUMMARY_UNIT = "unit"
    SUMMARY_PASSED = "passed"

    class List:
        """
        Models a list of elements in the final report, e.g. a list of security issues.

        Each list element can be expanded to show details.
        """

        SUMMARY = "summary"
        DETAILS = "details"

        def __init__(self, name: str = "") -> None:
            """
            Initializes the list with a name (typically used as heading).

            Args:
                name: The name (typically heading) of the list.
            """
            self.heading = name
            self.type = "list"
            self.entries = []
            self.summary = None # type: ignore

        def add(self, summary, details) -> None:
            """
            Adds a row to the list.

            Args:
                summary: Brief one-line summary.
                details: In-depth description that is shown when the user expands the
                    row.
            """
            self.entries.append({self.SUMMARY: summary, self.DETAILS: details})

        def __iter__(self):
            """
            Allows the class to be used as an iterable.
            """
            self.index = 0
            return self

        def __next__(self):
            """
            Allows the class to be used as an iterable.
            """
            if self.index < len(self.entries):
                self.index += 1
                return self.entries[self.index - 1]
            else:
                raise StopIteration

        @property
        def count(self):
            """
            Returns the number of entries in the list.

            Returns:
                Number of entries in the list, i.e. the number of rows.
            """
            return len(self.entries)

    class Table:
        """
        Models a table in the final report, e.g. test coverage per file.
        """

        def __init__(self, name: str = "", columns: list = list()) -> None:
            """
            Initializes the table with a name and column headings.

            Args:
                name: The name (typically heading) of the table.
                columns: The heading for each column.
            """
            self.heading = name
            self.columns = columns
            self.type = "table"
            self.entries = []
            self.summary = None # type: ignore

        def add(self, *columndata: str) -> None:
            """
            Adds a row to the list.

            The number of arguments (excluding self) has to match the number of defined
            columns in the table.

            Args:
                columndata: Positional arguments, one for each defined column.
            """
            if len(columndata) != len(self.columns):
                raise ValueError(
                    f"Given number of columns ({len(columndata)}) "
                    + f"does not match table ({len(self.columns)})."
                )
            self.entries.append({self.columns[i]: d for i, d in enumerate(columndata)})

        def __iter__(self):
            """
            Allows the class to be used as an iterable.
            """
            self.index = 0
            return self

        def __next__(self):
            """
            Allows the class to be used as an iterable.
            """
            if self.index < len(self.entries):
                self.index += 1
                return self.entries[self.index - 1]
            else:
                raise StopIteration

        @property
        def count(self):
            """
            Returns the number of entries in the table.

            Returns:
                Number of rows in the table.
            """
            return len(self.entries)

        @property
        def headings(self):
            """
            Returns the headings for each column defined for the table.
            """
            return self.columns

    class File:
        """
        Models a file in the final report.

        This is typically used to provide actual code snippets with the issues being
        highlighted. The colors used for highlighting are defined in the report's HTML
        template. In this class, highlighting will just be categorized in terms of good,
        bad, neutral and no highlighting. The report template will then decide which
        colors to use to highlight good, bad and neutral code sections. A legend is
        also provided in the report to show what each color means. A label can be
        assigned to each category using the set_mark_name method.
        """

        CONTENT = "content"
        COLOR = "color"

        COLOR_GOOD = "good"
        COLOR_BAD = "bad"
        COLOR_NEUTRAL = "neutral"
        COLOR_NONE = "none"

        def __init__(self, filepath: str) -> None:
            """
            Initializes the object with the path to the file that shall be shown.

            Args:
                filepath: Path to the file that shall be shown.
            """
            self.type = "file"
            self.summary = None # type: ignore
            self.filepath = filepath
            self.outputpath = ""
            self.colorname = {}
            self.lines = []
            self.range = None

            with open(filepath, "r") as f:
                self.lines = [
                    {self.CONTENT: line, self.COLOR: self.COLOR_NONE} for line in f if line
                ]
                if not self.lines:
                    self.lines = [{self.CONTENT: "", self.COLOR: self.COLOR_NONE}]
                self.range = (0, len(self.lines))

        @property
        def heading(self):
            """
            The heading used for the report. Derived from the file path.
            """
            absolute = Path(self.filepath).absolute()
            return str(absolute.relative_to(Path().cwd()))

        def set_mark_name(self, marking: str, label: str):
            """
            Sets a label for a marking category.

            The colors used for highlighting are defined in the report's HTML
            template. In this class, highlighting will just be categorized in terms of
            good, bad, neutral and no highlighting. The report template will then decide
            which colors to use to highlight good, bad and neutral code sections. A
            legend is also provided in the report to show what each color means. A label
            can be assigned to each category using this method. For example, calling
            ```
            myreport.set_mark_name(myreport.COLOR_BAD, "Finding")
            ```
            will label the color used for "bad" code sections with the word "Finding".

            Args:
                marking: The marking to assign a name to. Must be Report.COLOR_GOOD,
                    Report.COLOR_BAD or Report.COLOR_NEUTRAL.
                label: The label associated with the color category. It is shown in the
                    legend that the report provides.

            """
            if marking not in [
                self.COLOR_GOOD,
                self.COLOR_BAD,
                self.COLOR_NEUTRAL,
                self.COLOR_NONE,
            ]:
                raise ValueError("Invalid marking type.")
            self.colorname[marking] = label

        def mark(self, lines: Union[list, int], marking):
            """
            Highlights the given lines with the given color category.

            The colors used for highlighting are defined in the report's HTML template.
            In this class, highlighting will just be categorized in terms of good, bad,
            neutral and no highlighting. The report template will then decide which
            colors to use to highlight good, bad and neutral code sections. For example,
            calling
            ```
            myreport.mark([5, 6, 7], myreport.COLOR_BAD)
            ```
            will mark lines 5 to 7 as "bad code" and the report will highlight these
            lines in a suitable color (e.g. red).

            Args:
                lines: The lines to highlight.
                marking: The color category to mark the lines with.
            """
            inlines = [lines] if type(lines) is int else lines

            if not inlines:
                return

            if marking not in [
                self.COLOR_GOOD,
                self.COLOR_BAD,
                self.COLOR_NEUTRAL,
                self.COLOR_NONE,
            ]:
                raise ValueError("Invalid marking type.")

            for linenumber in inlines:
                if linenumber > len(self.lines) or linenumber < 1:
                    raise ValueError(
                        "Invalid line number for "
                        + self.filepath
                        + ": "
                        + str(linenumber)
                        + ". Line number must be within 1 to "
                        + str(len(self.lines) + 1)
                        + "."
                    )

                # First line starts with 1 and not 0.
                self.lines[linenumber - 1][self.COLOR] = marking

        def identifier(self):
            """
            Provides a unique identifier for the file.

            Oftentimes, multiple issues reference the same code section in the same
            original file and highlight the section in the same way. This identifier is
            used to detect that and avoid duplicate files in the final report that
            waste storage.

            Returns:
                Hash representing the file's configuration including original filepath,
                highlighted lines and used color categories.
            """
            filepath = str(Path(self.filepath).absolute())
            range = f"{self.range[0]:08d}{self.range[1]:08d}" if self.range else "None"
            color = [f"{i:08d}" + line[self.COLOR] for i, line in enumerate(self.lines)]
            color = "".join(color)
            return hash(filepath + range + color)

    def __init__(self, settings: Settings, appname: str, version: str) -> None:
        """
        Initializes the report.

        Args:
            settings: The settings instance to use.
            appname: The name of the application / python package.
            version: The version of the application / python package.
        """
        import jinja2
        import dateutil.tz
        self._sections = {}
        self._files = {}
        self._appname = appname
        self._version = version
        self._settings = settings
        self._timestamp = datetime.now(dateutil.tz.gettz())
        self._environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self._settings.REPORT_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._maintemplate = self._environment.get_template("main.jinja")
        self._filetemplate = self._environment.get_template("file.jinja")
        

    def render(self):
        """
        Exports the report as HTML files.

        The HTML files will be stored in the directory given by REPORT_FILES_DIR.
        """
        outputdir = Path(self._settings.REPORT_HTML).parent
        
        # Create output directories.
        mkdirs_if_not_exists(outputdir)
        mkdirs_if_not_exists(self._settings.REPORT_FILES_DIR)

        # Copy style sheets to output directory.
        for f in glob.glob(str(self._settings.REPORT_TEMPLATE_DIR / "*.css")):
            shutil.copy(f, self._settings.REPORT_FILES_DIR)

        styledir = self._settings.REPORT_FILES_DIR.absolute()

        filelist = [str(self._settings.REPORT_HTML.absolute())]
        # Write main report file.
        with open(self._settings.REPORT_HTML, "wb") as f:
            output = self._maintemplate.render(
                appname=self._appname,
                version=self._version,
                timestamp=self._timestamp,
                report=self._sections,
                summary={heading: self.summary(heading) for heading in self._sections},
                style_dir=os.path.relpath(styledir, outputdir.absolute()),
            )
            f.write(output.encode("utf-8"))

        # Write files containing code snippets.
        for file in self._files.values():
            filename = (outputdir / Path(file.outputpath)).absolute()
            filedir = filename.parent
            filelist.append(str(filename.absolute()))
            with open(filename, "wb") as f:
                output = self._filetemplate.render(
                    appname=self._appname,
                    version=self._version,
                    timestamp=self._timestamp,
                    file=file,
                    style_dir=os.path.relpath(styledir, filedir.absolute()),
                )
                f.write(output.encode("utf-8"))
                f.close()

        # Remove report files that are not needed anymore.
        # Although one could just remove the entire report folder, it is easier to
        # delete superfluous files only, because it allows to regenerate the report with
        # the report opened in a browser. The user then just needs to refresh the page.
        # Deleting the folder is not allowed when the report has been opened in a
        # browser, because the file is then denoted as "in use by another process".
        for existing in glob.glob(str(self._settings.REPORT_FILES_DIR / "*.html")):
            if str(Path(existing).absolute()) not in filelist:
                remove_if_exists(existing)

    def add(self, section: str, data: Union[File, Table, List]):
        """
        Adds a section with the given name to the report.

        A section is described by one of the subclasses. For example, Report.List or
        Report.Table. Multiple instances may be added to the same section.

        Args:
            section: The name of the section to place the data in.
            data: The data representing the section, e.g. an instance of Report.List.
        """
        if isinstance(data, self.File):
            index = len(self._files)
            ident = data.identifier()

            # Avoid multiple files with the same content.
            if ident in self._files:
                data.outputpath = self._files[ident].outputpath
                return

            reportdir = self._settings.REPORT_HTML.parent
            filesdir = self._settings.REPORT_FILES_DIR
            reldir = filesdir.relative_to(reportdir)
            data.outputpath = str(reldir / (str(index) + ".html"))
            self._files[ident] = data
            return

        if section not in self._sections:
            self._sections[section] = [data]
        else:
            self._sections[section].append(data)

    def summary(self, section: str) -> dict:
        """
        Provides a summary metric / total value for the section with the given name.

        An example for a summary may be the total test coverage in percent. The summary
        is typically shown next to the section headline for quick reference.

        Args:
            section: Name of the section to return the summary for.

        Returns:
            A dictionary with three keys (Report.SUMMARY_NAME, Report.SUMMARY_VALUE and
            report.SUMMARY_UNIT) containing the name of the metric used to summarize
            the section, the value of that metric and the unit of that metric,
            respectively.
        """
        if (
            len(self._sections[section]) == 1
            and self._sections[section][0].summary
            and type(self._sections[section][0].summary) is tuple
        ):
            return {
                self.SUMMARY_NAME: self._sections[section][0].summary[0],
                self.SUMMARY_VALUE: self._sections[section][0].summary[1],
                self.SUMMARY_UNIT: self._sections[section][0].summary[2],
            }
        return {
            self.SUMMARY_NAME: "Issues",
            self.SUMMARY_VALUE: sum([entry.count for entry in self._sections[section]]),
            self.SUMMARY_UNIT: "",
        }

    def get_total(self, section: str):
        """
        Returns the value of the summary metric (see also Report.summary method).

        Args:
            section: The name of the section to get the summary metric for.

        Returns:
            Value of the summary metric.
        """
        return self.summary(section)[self.SUMMARY_VALUE]

    def remove(self):
        """
        Removes the report.
        """
        self.clean()
        remove_if_exists(self._settings.REPORT_HTML.parent)
        remove_if_exists(self._settings.REPORT_FILES_DIR)

    def clean(self):
        """
        Removes temporary files used for the report.
        """
        remove_if_exists(self._settings.TMP_DIR)


class Meta:
    """
    Class for reading package meta information from setup.cfg.

    This is useful for third-party tools like sphinx to perform
    automatic configuration.
    """

    def __init__(self, configfile: Union[Path, str]):
        """
        Initializes the build with the package name from config file.

        Args:
            configfile: The name of the config file to pull the package
                name from.
        """
        self.configfile = str(configfile)

    def get(self, keyword: str):
        """
        Returns the value for the given key.

        Args:
            keyword: The name of the variable to be retrieved.

        Returns:
            The value in the config file stored under the given key.
        """

        with open(self.configfile, "r", encoding="utf8") as f:
            regex = r"[ ]*=[ ]*([^\n]+)?((\n[ \t]+([^\n]+))*)"
            buf = f.read()
            match = re.search(keyword + regex, buf)

            if match is None:
                raise LookupError(f'Could not determine "{keyword}".')

            matchstr = (match.group(1) or "") + (match.group(2) or "")
            lines = matchstr.split("\n")
            out = [entry.strip() for entry in lines if entry.strip()]
            return out if len(out) > 1 else out[0]

    def getCopyright(self):
        """
        Generate a copyright string for documentation.

        Returns:
            String with copyright notice.
        """
        import dateutil.tz
        date = datetime.now(dateutil.tz.UTC)
        return str(date.year) + ", " + self.get("author")


class Badge:
    """
    Class for generating badges that can be displayed in readme files or elsewhere.

    The badges are generated using the badge package. It will generate static SVG
    files that you may include in your readme, website or somewhere else. Using static
    files in the repository makes you independent from third-party services. This is
    useful if you work on confidential projects or if you want the badges to work on
    a device that is disconnected from the internet.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the class with settings.

        Args:
            settings: The settings instance to use.
        """
        self._settings = settings

    def _write(self, badgename: str, data: str):
        """
        Write the given SVG data to a file in the repository as given by the settings.

        Args:
            badgename: The filename of the badge.
            data: The SVG data to be written to a file in the repository.
        """
        badgefolder = os.path.normpath(self._settings.BADGE_FOLDER)
        badgefile = f"{badgefolder}\\{badgename}.svg"

        mkdirs_if_not_exists(self._settings.BADGE_FOLDER)
        with open(badgefile, "w") as f:
            f.write(data)

    def _getThresholdColorGTE(self, thresholddict: dict, value: float) -> str:
        """
        Returns the applicable color for a badge based on a threshold.

        Badges that indicate coverage are typically colored according to the indicated
        coverage. This method determines the right color by selecting the best match
        from the settings. The best match is the highest matching threshold.

        Args:
            thresholddict: Dictionary with keys as thresholds and values as color
                string for the badge package.
            value: The value to find the color for.

        Returns:
            Color string for the badge packages the matches the given value.
        """
        applicable = [k for k in thresholddict.keys() if value >= k]
        return str(thresholddict[max(applicable)]) if applicable else "red"

    def _getThresholdColorLTE(self, thresholddict: dict, value: float) -> str:
        """
        Returns the applicable color for a badge based on a threshold.

        Badges that indicate coverage are typically colored according to the indicated
        coverage. This method determines the right color by selecting the best match
        from the settings. The best match is the lowest matching threshold.

        Args:
            thresholddict: Dictionary with keys as thresholds and values as color
                string for the badge package.
            value: The value to find the color for.

        Returns:
            Color string for the badge packages the matches the given value.
        """
        applicable = [k for k in thresholddict.keys() if value <= k]
        return str(thresholddict[min(applicable)]) if applicable else "red"

    def coverage_badge(self, title: str, value: float, thresholds: dict):
        """
        Generates a badge for coverage.

        Args:
            title: The title of the badge to display.
            value: The coverage value in percent.
            thresholds: The threshold dictionary to use for assigning colors.
        """
        import pybadges
        coverage = math.floor(value)
        color = self._getThresholdColorGTE(thresholds, coverage)
        data = pybadges.badge(
            left_text=title, right_text=f"{coverage}%", right_color=color
        )
        self._write(title.replace(" ", "_"), data)

    def issue_badge(self, title: str, value: Optional[int], thresholds: dict):
        """
        Generates a badge for the number of issues found.

        Args:
            title: The title of the badge to display.
            value: The number of issues found.
            thresholds: The threshold dictionary to use for assigning colors.
        """
        import pybadges
        nissues = str(value)
        color = "red"

        if value is not None:
            color = self._getThresholdColorLTE(thresholds, value)
        else:
            nissues = "Unknown"

        data = pybadges.badge(
            left_text=title, right_text=f"{nissues}", right_color=color)
        self._write(title.replace(" ", "_"), data)

    def passfail_badge(self, name: str, passing: bool):
        """
        Generates a badge that indicates that something has passed or failed.

        The generated SVG file is directly written to one of the repository's folders
        as given in the settings.

        Args:
            name: The name displayed on the badge.
            passing: True, if the badge shall indicate passage. False, otherwise.
        """
        import pybadges
        text = "passing" if passing else "failing"
        color = "brightgreen" if passing else "red"
        data = pybadges.badge(left_text=name, right_text=text, right_color=color)
        self._write(name.replace(" ", "_"), data)


class CalVersion:
    """
    Class for increasing the version number using calendar versioning.

    Calendar versioning is one of the simplest versioning schemes and can be easily
    automated. This is especially suitable for small projects that do not maintain
    multiple versions (e.g. providing fixes to older, long term stable releases) and do
    not require a strict scheme to highlight backward compatibility. More detailed
    information is given at https://calver.org/ . The scheme adopted here is
    YY.MM.Micro, meaning:
    * YY - Short year (1, 2, 3, ..., 21, 22, 23)
    * MM - Short month (1, 2, ..., 12)
    * Micro - Patch. Automatically incremented for each build.
    """

    VER_YEAR = 0
    VER_MONTH = 1
    VER_PATCH = 2

    def __init__(self, settings: Settings):
        """
        Initializes the instance with settings and determines the new version.

        The current version is determined from the setup.cfg file. If the version does
        not comply with the versioning scheme, the version is overwritten with
        micro / patch number zero.

        Args:
            settings: The settings instance to use.
        """
        meta = Meta(settings.CONFIGFILE)
        oldver = meta.get("version").split(".")

        if (
            type(oldver) is not list
            or not all([e.isdigit() for e in oldver])
            or len(oldver) > self.VER_PATCH + 1
            or int(oldver[self.VER_MONTH]) > 12
            or int(oldver[self.VER_YEAR]) > 99
        ):
            self.__resetVersion()
        else:
            self.__bumpVersion(oldver)

    def __versionstr(self, year: int, month: int, patch: int):
        """
        Returns the version string in standardized format.

        Args:
            year: The current year.
            month: The current month.
            patch: The automatically incremented patch number.
        """
        return f"{str(year)[-2:]}.{month}.{patch}"

    def __resetVersion(self):
        """
        Initializes a new version.

        This is done for cases in which there is no correct old version
        available to increment.
        """
        import dateutil
        date = datetime.now(dateutil.tz.UTC)
        self.version = self.__versionstr(date.year, date.month, 0)

    def __bumpVersion(self, oldversion: list):
        """
        Increase the old version number

        This is done for cases in which the old version complies with
        the versioning scheme.

        Args:
            oldversion: The old version as a list of strings. One
                element for each part of the version.
        """
        import dateutil
        date = datetime.now(dateutil.tz.UTC)
        oldmonth = int(oldversion[self.VER_MONTH])
        oldpatch = int(oldversion[self.VER_PATCH])
        newmonth = date.month
        patch = oldpatch + 1 if oldmonth == newmonth else 0
        self.version = self.__versionstr(date.year, date.month, patch)

    def bump(self, filename: str, regex: str):
        """
        Replaces all regex matches with the current version.

        The given regular expression must denote the version part as
        a group, because the first group in the match will be replaced
        with the new version string.

        Args:
            filename: File containing a version string.
            regex: The regular that matches the version given in the
                file. The version must be denoted as the first group
                in the regular expression.
        """
        with open(filename, "r") as f:
            buf = str(f.read())
            buf = re.sub(regex, r"\1 " + self.version, buf)
        with open(filename, "w") as f:
            f.write(buf)

    def __str__(self) -> str:
        return str(self.version)


class Documentation:
    """
    Class for managing documentation artifacts.

    The class allows to generate documentation, remove old documentation and clean up
    intermediate artifacts. It uses sphinx (https://www.sphinx-doc.org/en/master/) for
    generating the documentation. The package's API is automatically documented and
    missing documentation is reported.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings.

        Args:
            settings: Settings instance to get settings from.
        """
        self._settings = settings
        self._passed = False

    def remove(self) -> None:
        """
        Removes all documentation artifacts.
        """
        self.clean()
        remove_if_exists(self._settings.DOCUMENTATION_HTML_DIR)
        remove_if_empty(self._settings.REPORT_DIR)

    def clean(self) -> None:
        """
        Removes intermediate build artifacts.
        """
        remove_if_exists(self._settings.DOCUMENTATION_SOURCE_DIR)
        remove_if_exists(self._settings.DOCUMENTATION_COVERAGE_FILE)
        remove_if_empty(self._settings.TMP_DIR)

        for folder in self._settings.DOCUMENTATION_HTML_DIR_EXCLUDE:
            remove_if_exists(folder)

    def ispassed(self) -> bool:
        """
        Returns, whether the last run() call was successful and did not return issues.

        Returns:
            True, if the last call of run() was successful. False, otherwise.
        """
        return self._passed

    def run(self) -> bool:
        """
        Generates the documentation.

        Returns:
            True, if generation was successful. False, otherwise.
        """
        self.remove()

        # Generate new documentation
        step1result = not bool(
            pyexecute(
                [
                    "sphinx.ext.apidoc",
                    "-e",
                    "-q",
                    "-M",
                    "-f",
                    "-t",
                    str(self._settings.DOCUMENTATION_TEMPLATE_DIR),
                    "-o",
                    str(self._settings.DOCUMENTATION_SOURCE_DIR),
                    str(self._settings.SRC_DIR),
                ]
            )
        )

        step2result = not bool(
            pyexecute(
                [
                    "sphinx",
                    "-q",
                    "-b",
                    "html",
                    str(self._settings.DOCUMENTATION_ROOT_DIR),
                    str(self._settings.DOCUMENTATION_HTML_DIR),
                ]
            )
        )
        self._passed = step1result and step2result
        return self._passed


class StyleCheck:
    """
    Class for performing automatic code styling and static code analysis.

    The class uses black (https://github.com/psf/black) and flake8
    (https://github.com/PyCQA/flake8). The settings for flake8 are chosen such that
    they comply with black's way of styling code. A report is generated to document
    any issues found.
    """

    KEY_CODE = "code"
    KEY_LINE = "line_number"
    KEY_COLUMN = "column_number"
    KEY_DESCRIPTION = "text"
    KEY_FILENAME = "filename"

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings.

        Args:
            settings: Settings instance to get settings from.
        """
        self._settings = settings
        self._passed = False

    def remove(self) -> None:
        """
        Removes the old issue report.
        """
        self.clean()
        remove_if_exists(self._settings.REPORT_HTML)
        remove_if_empty(self._settings.REPORT_DIR)

    def clean(self) -> None:
        """
        Removes intermediate artifacts.
        """
        remove_if_exists(self._settings.STYLE_REPORT_JSON)
        remove_if_empty(self._settings.TMP_DIR)
        remove_if_empty(self._settings.REPORT_DIR)

    def ispassed(self) -> bool:
        """
        Returns, whether the last run() call was successful and did not return issues.

        Returns:
            True, if the last call of run() was successful. False, otherwise.
        """
        return self._passed

    def run(self) -> bool:
        """
        Performs automatic styling with black and checks with flake8.

        Returns:
            True, if styling was successful and there were no remaining errors.
            False, otherwise.
        """
        self.clean()
        self.flakefile = str(self._settings.STYLE_REPORT_JSON)

        pyexecute(["isort", "--quiet", str(self._settings.SRC_DIR)])
        pyexecute(["black", "--quiet", str(self._settings.SRC_DIR)])

        mkdirs_if_not_exists(self._settings.REPORT_DIR)
        # Flake8 configuration is done as recommended by the black documentation as
        # found here:
        # https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html
        self._passed = not bool(
            pyexecute(
                [
                    "flake8",
                    "--format=json",
                    "--max-line-length",
                    "88",
                    "--select",
                    "C,E,F,W,B,B950",
                    "--extend-ignore",
                    "E203,E501",
                    "--output-file",
                    self.flakefile,
                    str(self._settings.SRC_DIR),
                ]
            )
        )
        return self._passed

    def report(self, report: Report):
        """
        Exports the results to the given report.

        Args:
            report: The report to export the results to.
        """
        with open(self.flakefile, "r") as f:
            data = json.load(f)
            for filename, issues in data.items():
                name = Path(filename).absolute().relative_to(Path().cwd())
                List = Report.List(str(name))
                for issue in issues:
                    file = report.File(filename)
                    file.mark([issue[self.KEY_LINE]], file.COLOR_BAD)
                    file.set_mark_name(file.COLOR_BAD, "Finding")
                    file.range = (
                        issue[self.KEY_LINE] - self._settings.REPORT_LINE_RANGE,
                        issue[self.KEY_LINE] + self._settings.REPORT_LINE_RANGE,
                    )
                    report.add(filename, file)

                    summary = issue[self.KEY_DESCRIPTION]
                    details = (
                        "<b>Code</b>: "
                        + str(issue[self.KEY_CODE])
                        + "<br />"
                        + "<b>Line</b>: "
                        + str(issue[self.KEY_LINE])
                        + "<br />"
                        + "<b>Column</b>: "
                        + str(issue[self.KEY_COLUMN])
                        + "<br />"
                        + "<b>File</b>: "
                        + f"<a href=\"{file.outputpath}#{issue[self.KEY_LINE]}\">"
                        + str(name)
                        + "</a>"
                    )

                    List.add(summary, details)

                report.add(self._settings.REPORT_SECTION_NAME_STYLE, List)

class TypeCheck:
    """
    Class for static type analysis.

    The class uses mypy (https://github.com/python/mypy).
    """

    REGEX_MSG = re.compile(r"([^:]+)[ ]*:[ ]*(\d+)[ ]*:[ ]*([^:]+)[ ]*:[ ]*([^\n]+?)\[([^\]]+)\][ ]*(\n|$)")
    GROUP_FILENAME = 1
    GROUP_LINE = 2
    GROUP_TYPE = 3
    GROUP_MSG = 4
    GROUP_CODE = 5

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings.

        Args:
            settings: Settings instance to get settings from.
        """
        self._settings = settings
        self._passed = False

    def remove(self) -> None:
        """
        Removes the old issue report.
        """
        self.clean()
        remove_if_exists(self._settings.REPORT_HTML)
        remove_if_empty(self._settings.REPORT_DIR)

    def clean(self) -> None:
        """
        Removes intermediate artifacts.
        """
        remove_if_exists(self._settings.TYPE_REPORT_XML)
        remove_if_exists(self._settings.MYPY_CACHE)
        remove_if_empty(self._settings.TMP_DIR)
        remove_if_empty(self._settings.REPORT_DIR)

    def ispassed(self) -> bool:
        """
        Returns, whether the last run() call was successful and did not return issues.

        Returns:
            True, if the last call of run() was successful. False, otherwise.
        """
        return self._passed

    def run(self) -> bool:
        """
        Performs static type analysis using mypy.

        Returns:
            True, if no type errors were found.
            False, otherwise.
        """
        self.clean()

        mkdirs_if_not_exists(self._settings.REPORT_DIR)
        
        self._passed = not bool(
            pyexecute(
                [
                    "mypy",
                    "--install-types",
                    "--show-error-codes",
                    "--non-interactive",
                    "--show-absolute-path",
                    "--warn-unreachable",
                    "--warn-return-any",
                    "--warn-redundant-casts",
                    "--no-implicit-optional",
                    "--follow-imports=silent",
                    "--ignore-missing-imports",
                    "--disable-error-code", "attr-defined",
                    "--disable-error-code", "var-annotated", 
                    "--disable-error-code", "union-attr", 
                    "--junit-xml",
                    str(self._settings.TYPE_REPORT_XML),
                    "--cache-dir",
                    str(self._settings.MYPY_CACHE),
                    str(self._settings.SRC_DIR),
                ]
            )
        )
        return self._passed

    def report(self, report: Report):
        """
        Exports the results to the given report.

        Args:
            report: The report to export the results to.
        """
        import defusedxml.ElementTree as et
        tree = et.parse(self._settings.TYPE_REPORT_XML)
        failurenode = tree.getroot().find(".//failure")
        messages = str(failurenode.text) if failurenode is not None else ""
        sections = {}
        files = {}
        lines = {}
        
        # Parse all messages
        for match in self.REGEX_MSG.finditer(messages):
            filename = match.group(self.GROUP_FILENAME).strip()
            filename = str(Path(filename).absolute().relative_to(Path().cwd()))
            line = int(match.group(self.GROUP_LINE).strip())
            msgtype = match.group(self.GROUP_TYPE).strip().capitalize()
            msg = match.group(self.GROUP_MSG).strip()
            code = match.group(self.GROUP_CODE).strip()

            if filename not in sections:
                file = report.File(filename)
                files[filename] = file
                lines[filename] = [] 
                report.add(str(Path(filename).absolute()), file)
                sections[filename] = Report.List(filename)
            
            files[filename].mark(line, file.COLOR_BAD)
            files[filename].set_mark_name(file.COLOR_BAD, "Finding")
            lines[filename].append(line)
            summary = f"<b>{code}</b>: {msg}"
            details = f"<b>Line</b>: {line}<br />" + f"<b>Type</b>: {msgtype} <br />" + f"<b>Code</b>: {code} <br />" + f"<b>File</b>: <a href=\"{files[filename].outputpath}#{line}\">{filename}</a>"
            sections[filename].add(summary, details)
        
        for filename, section in sections.items():
            files[filename].range = (min(lines[filename]) - self._settings.REPORT_LINE_RANGE, max(lines[filename]) + self._settings.REPORT_LINE_RANGE)
            report.add("Types", section) 

        if not sections:
            report.add("Types", Report.List())


class SecurityCheck:
    """
    Class for detecting security issues with the package.

    The class uses bandit (https://github.com/PyCQA/bandit) for the task. A report is
    generated to document any issues found.
    """

    KEY_BANDIT_RESULTS = "results"
    KEY_BANDIT_TESTNAME = "test_name"
    KEY_BANDIT_DESCRIPTION = "issue_text"
    KEY_BANDIT_FILENAME = "filename"
    KEY_BANDIT_CONFIDENCE = "issue_confidence"
    KEY_BANDIT_SEVERITY = "issue_severity"
    KEY_BANDIT_TESTID = "test_id"
    KEY_BANDIT_INFO = "more_info"
    KEY_BANDIT_LINES = "line_range"
    KEY_SAFETY_ID = 4
    KEY_SAFETY_NAME = 0
    KEY_SAFETY_AFFECTED = 1
    KEY_SAFETY_INSTALLED = 2
    KEY_SAFETY_DETAILS = 3

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings.

        Args:
            settings: Settings instance to get settings from.
        """
        self._settings = settings
        self.safetyfilenames = {}
        self.banditfilename = ""
        self._passed = False

    def remove(self) -> None:
        """
        Remove old reports.
        """
        self.clean()

        remove_if_exists(self._settings.REPORT_HTML)

    def clean(self) -> None:
        """
        Removes intermediate artifacts.
        """

        for filename in self.safetyfilenames.values():
            remove_if_exists(filename)
        remove_if_exists(self.banditfilename)
        remove_if_empty(self._settings.TMP_DIR)

    def ispassed(self) -> bool:
        """
        Returns, whether the last run() call was successful and did not return issues.

        Returns:
            True, if the last call of run() was successful. False, otherwise.
        """
        return self._passed

    def _safety(self) -> bool:
        """
        Runs the tool "safety" to examine, whether dependencies contain vulnerabilities.

        Returns:
            True, if the run was successful and no issues were found. False, otherwise.
        """

        mkdirs_if_not_exists(self._settings.TMP_DIR)

        activefile = str(self._settings.SECURITY_ACTIVE_JSON)
        setupfile = str(self._settings.TMP_DIR / "setup.cfg.json")

        # Check the currently activated environment for dependecy vulnerabilities.
        result = [
            not bool(
                pyexecute(
                    [
                        "safety",
                        "check",
                        "--full-report",
                        "--json",
                        "--output",
                        activefile,
                    ]
                )
            )
        ]

        # Check the config file of the package
        result += [
            not bool(
                pyexecute(
                    [
                        "safety",
                        "check",
                        "--file",
                        str(self._settings.CONFIGFILE),
                        "--full-report",
                        "--json",
                        "--output",
                        setupfile,
                    ]
                )
            )
        ]

        self.safetyfilenames["Active Environment"] = activefile
        self.safetyfilenames[self._settings.CONFIGFILE.name] = setupfile

        # Check all available requirements files for dependency vulnerabilities.
        for f in glob.glob(self._settings.SECURITY_REQUIREMENTS_GLOB):
            filepath = Path(f)
            filename = Path(f).name

            result += [
                not bool(
                    pyexecute(
                        [
                            "safety",
                            "check",
                            "-r",
                            str(filepath.resolve()),
                            "--full-report",
                            "--json",
                            "--output",
                            str(self._settings.TMP_DIR / filename) + ".json",
                        ]
                    )
                )
            ]
            self.safetyfilenames[Path(f).name] = f

        self._passed = all(result)
        return self._passed

    def _bandit(self) -> bool:
        """
        Runs the tool "bandit" to find common security issues.

        Returns:
            True, if the run was successful and no issues were found. False, otherwise.
        """
        # Bandit does not seem to be able to create a directory, if it does not exist
        # already. Therefore, create one if necessary.
        mkdirs_if_not_exists(self._settings.TMP_DIR)

        # *****************************
        # ** CHECK FOR INSECURE CODE **
        # *****************************

        # Create json for parsing by package.py.
        self.banditfilename = str(self._settings.SECURITY_BANDIT_JSON)

        return not bool(
            pyexecute(
                [
                    "bandit",
                    "--quiet",
                    "-r",
                    str(self._settings.SRC_DIR),
                    "-f",
                    "json",
                    "-o",
                    self.banditfilename,
                ]
            )
        )

    def run(self) -> bool:
        """
        Checks the package for security issues.

        Returns:
            True, if the run was successful and no security issues were found.
            False, otherwise.
        """
        self.clean()
        self.safetyfilenames = {}
        self.banditfilename = ""

        bresult = self._bandit()
        sresult = self._safety()
        return bresult and sresult

    def report(self, report: Report):
        """
        Exports the results to the given report.

        Args:
            report: The report to export the results to.
        """
        # Generate dependency report.
        for name, filename in self.safetyfilenames.items():
            if not os.path.isfile(str(filename)):
                List = Report.List(name)
                List.add(f"Analysis failed.", "")
                report.add("Dependencies", List)
                continue

            with open(filename, "r") as f:
                List = Report.List(name)
                try:
                    data = json.load(f)
                    for d in data:
                        summary = (
                            "<b>"
                            + d[self.KEY_SAFETY_NAME]
                            + "</b> "
                            + d[self.KEY_SAFETY_AFFECTED]
                        )
                        details = (
                            "<b>ID</b>: "
                            + d[self.KEY_SAFETY_ID]
                            + "<br />"
                            + "<b>Installed</b>: "
                            + d[self.KEY_SAFETY_INSTALLED]
                            + "<br />"
                            + d[self.KEY_SAFETY_DETAILS]
                        )
                        List.add(summary, details)
                    report.add("Dependencies", List)
                except json.decoder.JSONDecodeError:
                    pass

        # Check whether report fole exists.
        if not os.path.isfile(str(self.banditfilename)):
                List = Report.List()
                List.add(f"Analysis failed.", "")
                report.add(self._settings.REPORT_SECTION_NAME_SECURITY, List)
                return

        # Generate security report.
        with open(self.banditfilename, "r") as f:
            data = json.load(f)
            security = Report.List()

            if self.KEY_BANDIT_RESULTS not in data:
                data[self.KEY_BANDIT_RESULTS] = list()

            for entry in data[self.KEY_BANDIT_RESULTS]:
                filename = str(entry[self.KEY_BANDIT_FILENAME])
                relfilename = str(Path(filename).absolute().relative_to(Path().cwd()))
                file = report.File(relfilename)
                minline = min(entry[self.KEY_BANDIT_LINES])
                maxline = max(entry[self.KEY_BANDIT_LINES])
                file.mark(entry[self.KEY_BANDIT_LINES], file.COLOR_BAD)
                file.set_mark_name(file.COLOR_BAD, "Finding")
                file.range = (
                    minline - self._settings.REPORT_LINE_RANGE,
                    maxline + self._settings.REPORT_LINE_RANGE,
                )
                report.add(filename, file)

                summary = (
                    "<b>"
                    + entry[self.KEY_BANDIT_TESTNAME]
                    + "</b>: "
                    + entry[self.KEY_BANDIT_DESCRIPTION]
                )
                detail = (
                    "<b>Test ID</b>: "
                    + str(entry[self.KEY_BANDIT_TESTID])
                    + "<br />"
                    + "<b>Severity</b>: "
                    + str(entry[self.KEY_BANDIT_SEVERITY])
                    + "<br />"
                    + "<b>Confidence</b>: "
                    + str(entry[self.KEY_BANDIT_CONFIDENCE])
                    + "<br />"
                    + "<b>File</b>: "
                    + f"<a href=\"{file.outputpath}#{minline}\">"
                    + relfilename
                    + "</a>"
                    + "<br />"
                    + "<b>Line(s)</b>: "
                    + ", ".join([str(e) for e in entry[self.KEY_BANDIT_LINES]])
                    + "<br />"
                    + '<b>More Information</b>: <a href="'
                    + str(entry[self.KEY_BANDIT_INFO])
                    + '">'
                    + str(entry[self.KEY_BANDIT_INFO])
                    + "</a>"
                )

                security.add(summary, detail)

            report.add(self._settings.REPORT_SECTION_NAME_SECURITY, security)


class Test:
    """
    Class for running unit tests and generating a test coverage report.

    The class uses coverage (https://github.com/nedbat/coveragepy) for the task.
    """

    KEY_FILES = "files"
    KEY_SUMMARY = "summary"
    KEY_NUM_STATEMENTS = "num_statements"
    KEY_NUM_MISSING = "missing_lines"
    KEY_NUM_EXCLUDED = "excluded_lines"
    KEY_COVERAGE = "percent_covered"
    KEY_TOTALS = "totals"
    KEY_EXECUTED = "executed_lines"
    KEY_MISSING = "missing_lines"
    KEY_EXCLUDED = "excluded_lines"

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings.

        Args:
            settings: Settings instance to get settings from.
        """
        self._settings = settings
        self._passed = False

    def remove(self) -> None:
        """
        Removes old reports and intermediate artifacts like coverage files.
        """
        remove_if_exists(self._settings.TEST_COVERAGE_FILE)

    def clean(self) -> None:
        """
        Removes intermediate artifacts like coverage files.
        """
        remove_if_exists(self._settings.TEST_COVERAGE_FILE)
        remove_if_exists(self._settings.TEST_COVERAGE_JSON)

    def ispassed(self) -> bool:
        """
        Returns, whether the last run() call was successful and did not return issues.

        Returns:
            True, if the last call of run() was successful and did not return issues.
            False, otherwise.
        """
        return self._passed

    def run(self) -> bool:
        """
        Runs all unit tests and generates a coverage report.

        Returns:
            True, if all tests were successful. False, otherwise.
        """
        self.clean()

        self.coveragefile = str(self._settings.TEST_COVERAGE_JSON)
        mkdirs_if_not_exists(self._settings.TMP_DIR)
        cwd = Path().cwd()        
        srcdir_abs = self._settings.SRC_DIR.absolute()
        srcdir = srcdir_abs.relative_to(cwd)

        self._passed = not bool(
            pyexecute(
                [
                    "coverage",
                    "run",
                    "-m",
                    f"--source={srcdir}",
                    "unittest",
                    "-q",
                ]
            )
        )
        pyexecute(["coverage", "json", "--pretty-print", "-o", self.coveragefile])
        return self._passed

    def report(self, report: Report):
        """
        Exports the results to the given report.

        Args:
            report: The report to export the results to.
        """
        with open(self.coveragefile, "r") as f:
            data = json.load(f)
            filelist = data[self.KEY_FILES]
            table = Report.Table(
                "", ["Module", "Statements", "Missing", "Excluded", "Coverage"]
            )
            for filename, content in filelist.items():
                file = report.File(filename)
                file.mark(content[self.KEY_EXECUTED], file.COLOR_GOOD)
                file.mark(content[self.KEY_MISSING], file.COLOR_BAD)
                file.mark(content[self.KEY_EXCLUDED], file.COLOR_NEUTRAL)
                file.set_mark_name(file.COLOR_GOOD, "Run")
                file.set_mark_name(file.COLOR_BAD, "Missing")
                file.set_mark_name(file.COLOR_NEUTRAL, "Excluded")
                report.add(filename, file)

                nstatements = content[self.KEY_SUMMARY][self.KEY_NUM_STATEMENTS]
                nmissing = content[self.KEY_SUMMARY][self.KEY_NUM_MISSING]
                nexcluded = content[self.KEY_SUMMARY][self.KEY_NUM_EXCLUDED]
                coverage = str(content[self.KEY_SUMMARY][self.KEY_COVERAGE]) + "\u202F%"
                table.add(
                    f"<a href=\"{file.outputpath}\">{filename}</a>",
                    nstatements,
                    nmissing,
                    nexcluded,
                    coverage,
                )
                table.summary = ( # type: ignore
                    "Coverage",
                    math.floor(data[self.KEY_TOTALS][self.KEY_COVERAGE]),
                    "%",
                ) 
            report.add(self._settings.REPORT_SECTION_NAME_TEST, table)


class Build:
    """
    Class for building distributable files (e.g. wheel and source distributions).

    The class has the following purposes:
        - Removes the old build files.
        - Build the package.
        - Remove the temporary build artifacts.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings and the package name by reading setup.cfg.

        Args:
            settings: Settings instance to get settings from.
        """

        self._settings = settings
        self._passed = False

        with open(self._settings.CONFIGFILE, "r") as f:
            buf = str(f.read())
            match = re.search(r"name[ ]*=[ ]*([^\n ]+)", buf)

            if match is None:
                raise LookupError("Could not determine package name.")

            self.packagename = match.group(1).strip()

    def remove(self) -> None:
        """
        Remove old build files.
        """
        distfiles = self.packagename.replace("-", "_")
        distdir = self._settings.DISTRIBUTABLE_DIR
        self.clean()

        for f in glob.glob(str(distdir / distfiles) + "*.*"):
            remove_if_exists(f)

        for f in glob.glob(str(distdir / self.packagename) + "*.*"):
            remove_if_exists(f)

        remove_if_empty(distdir)

    def clean(self) -> None:
        """
        Remove intermediate artifacts and folders.
        """
        for f in glob.glob(str(self._settings.SRC_DIR / "*.egg-info")):
            remove_if_exists(f)

        remove_if_exists(self._settings.BUILD_DIR)

    def ispassed(self) -> bool:
        """
        Returns, whether the last run() call was successful and did not return issues.

        Returns:
            True, if the last call of run() was successful and did not return issues.
            False, otherwise.
        """
        return self._passed

    def run(self) -> bool:
        """
        Create a new source and binary (wheel) distribution.

        Returns:
            True, if operation was successful. False, otherwise.
        """
        self.remove()

        builddir = str(self._settings.DISTRIBUTABLE_DIR)
        self._passed = not bool(pyexecute(["build", "-s", "-w", "-o", builddir]))
        return self._passed


class DocInspector:
    """
    Class for inspecting doc strings that have already been parsed by sphinx.

    This class is useful for finding documented and undocumented code as well as
    computing the documentation coverage. This way, you always know whether there is
    documentation missing.
    """

    REGEX_PARAMETERS = re.compile(r":param[ ]*([^:]+):")
    REGEX_FIELD = re.compile(r":[^:]+:")
    REGEX_DOC = re.compile(
        r"(\"\"\".*?\"\"\"|#[^\n]*|\".*?\"|\'.*?\')", re.MULTILINE | re.DOTALL
    )
    REGEX_RETURN_NONE = re.compile(r"return([ ]*None|[ ]*[$\n])")
    REGEX_RETURN = re.compile(r"return[ ]+(\w|\d|[\[{\(])")
    REGEX_DOCRETURN = re.compile(r":return(s)?:[ ]*(\w|\d)+")
    REGEX_NESTED = re.compile(
        r"([ \t]+)(def|class)[ ]+[^:]+:\n(\1[ \t]+[^ ][^\n]+\n|[ ]*\n|\1[ \t]+[^ ])+"
    )

    UNUSED = "Unused"
    DOCUMENTED = "Documented"
    UNDOCUMENTED = "Undocumented"

    KEY_TYPE = "type"
    KEY_ISSUE = "issue"
    KEY_WHAT = "what"
    KEY_OBJNAME = "object_name"
    KEY_FILE = "file"
    KEY_LINES = "line_range"
    KEY_TEXT = "text"

    SECTION_ISSUES = "undocumented_elements"
    SECTION_DOCUMENTED = "documented_elements"

    ISSUE_UNDOC_PARAM = "undocumented parameter"
    ISSUE_UNDOC_RETURN = "undocumented return value"
    ISSUE_UNDOC_DESCRIPTION = "missing description"
    ISSUE_UNUSED_PARAM = "documented but unused parameter"

    JSON_INDENT = 4

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the class with settings.

        Args:
            settings: Instance of a settings class to get settings from.
        """
        self._settings = settings
        self.undocumented = list()
        self.missing = list()
        self.log = list()
        self.documented = {}  # Number of documented elements in each file.
        self.files = set()

    def _getcleandoc(self, doc: List[str]):
        """
        Applies Python's strip() function to each documentation line.

        Applying strip() avoids errors during parsing.

        Args:
            doc: The documentation string to apply strip() to.
        """
        return [line.strip() for line in doc if len(line.strip()) > 0]

    def _fromsignature(self, subject: object, type: str) -> list:
        """
        Returns all parameters that have been defined for the given subject object.

        This method is used to obtain the list of parameters the given subject
        was defined with. The list can then be used for comparing the documentation to.
        Note that this does only work for functions and methods.

        Args:
            subject: The object for which a list of parameters shall be obtained.
            type: The type of object as given by sphinx.
        """
        if not callable(subject):
            raise TypeError("Given subject is not callable.")

        signature = list(inspect.signature(subject).parameters.keys())

        # Filter the "self" - parameter.
        if type == "method" and signature[0].lower() == "self":
            signature.pop(0)

        return signature

    def _fromdocstring(self, lines: list) -> list:
        """
        Returns all parameters that have been documented in the given docstring.

        Args:
            lines: The docstring as a list of strings as given by sphinx.

        Returns:
            A list of strings with all parameter names that have been mentioned
            in the docstring by :param ... : .
        """
        params = list()
        doc = self._getcleandoc(lines)
        for line in doc:
            params += self.REGEX_PARAMETERS.findall(line)
        return params

    def save(self):
        """
        Saves information about documentation coverage to a file.

        The file is given in the settings as DOCUMENTATION_COVERAGE_FILE. A file is
        always created, even if there is no data to write. If the file already exists,
        it is overwritten.
        """

        mkdirs_if_not_exists(Path(self._settings.TMP_DIR))

        with open(self._settings.DOCUMENTATION_COVERAGE_FILE, "w") as f:
            data = {
                self.SECTION_DOCUMENTED: self.documented,
                self.SECTION_ISSUES: self.log,
            }
            json.dump(data, f, indent=self.JSON_INDENT)

    def load(self):
        """
        Loads information about documentation coverage from a file.

        The file is given in the settings as DOCUMENTATION_COVERAGE_FILE.
        """
        covfile = self._settings.DOCUMENTATION_COVERAGE_FILE

        if not os.path.isfile(covfile):
            raise Exception(f"Documentation coverage file {covfile} does not exist.")

        with open(self._settings.DOCUMENTATION_COVERAGE_FILE, "r") as f:
            data = json.load(f)
            self.documented = data[self.SECTION_DOCUMENTED]
            self.log = data[self.SECTION_ISSUES]

    def _getParameter(
        self, subject: object, lines: list, type: str, check: str
    ) -> list:
        """
        Returns a list of parameters that match a given check.

        One can obtain a list of parameter names that match a given check. For example,
        calling this method with check = DocInspector.UNDOCUMENTED returns a list of
        undocumented parameter names. Note that this method only works for functions
        and methods.

        Args:
            subject: The object to get the matching parameter list for.
            lines: The docstring as given by sphinx.
            type: The type of the subject as given by sphinx.
            check: The type of match to perform. Allowed values are
                UNDEFINED - Parameters that have been documented but are not part of the
                actual signature.
                DOCUMENTED - Parameters that have been documented.
                UNDOCUMENTED - Parameters that have not been documented.

        Returns:
            A list of parameter names that match the given type of check.
        """
        # These types are callable but do not have parameters.
        if type in ["exception", "class"] or not callable(subject):
            return list()

        signature = self._fromsignature(subject, type)
        documented = self._fromdocstring(lines)

        if check == self.UNDOCUMENTED:
            return [p for p in signature if p not in documented]
        elif check == self.DOCUMENTED:
            return [p for p in signature if p in documented]
        elif check == self.UNUSED:
            return [p for p in documented if p not in signature]
        else:
            raise Exception("Unknown check type.")

    def _getDescription(self, lines: list):
        """
        Returns the first descriptive line of the docstring, if present.

        Typically, the first descriptive line is the brief. This method is used to
        determine if there is any description present at all excluding parameter
        documentation and other fields documented using :fieldname ... : .

        Args:
            lines: The docstring as given by sphinx.

        Returns:
            The first descriptive line of the docstring. Typically, the brief.
        """
        doc = self._getcleandoc(lines)
        if not doc:
            return None
        # A brief typically does not contain fieldnames.
        if self.REGEX_FIELD.match(doc[0]) is not None:
            return None
        if len(doc[0]) == 0:
            return None
        return doc[0]

    def _missingReturn(self, subject: object, lines: list, what: str, name):
        """
        Determines, whether a return value documentation is missing.

        If there is a non-None return value, it should be documented. Functions and
        methods that return None can still document return values, e.g. to explicitly
        state None or document why None is returned. That is deemed optional.
        """

        if what not in ["method", "function"]:
            return None

        source = inspect.getsource(subject).strip() # type: ignore

        # Find returns that are not None.
        # First, remove docstrings, comments and strings.
        cleaned = self.REGEX_DOC.sub("", source)
        # Second, remove "return None" or return statements without value.
        cleaned = self.REGEX_RETURN_NONE.sub("", cleaned)
        # Third, remove nested functions and classes.
        cleaned = self.REGEX_NESTED.sub("", cleaned)

        # Find remaining return statements which mention a value or variable.
        notNone = self.REGEX_RETURN.search(cleaned)
        # Detect, whether return values are part of the docstring.
        docret = self.REGEX_DOCRETURN.search("\n".join(lines))

        return notNone is not None and docret is None

    def process(self, app, what, name, obj, options, lines) -> None:
        """
        Determines code that has not been properly documented.

        This method is meant to be connected to the "autodoc-process-docstring" event of
        sphinx. It parsed already parsed docstrings and compares the documentation
        with the actual definition of the given object. Since the docstring has already
        been parsed by sphinx, it does not matter which style was used for
        documentation. The results are stored in files as given in the settings from
        which the documentation coverage can be computed.

        Args:
            app: The Sphinx application object.
            what: The type of the object which the docstring belongs to.
            name: The fully qualified name of the object.
            obj: The object itself.
            options: The options given by sphinx.
            lines: Docstring as given by sphinx.
        """

        try:
            file = inspect.getsourcefile(obj)
            with open(file) as f: content = f.read().strip()
        except Exception:
            # Only evaluate objects for which a file can be determined.
            # For example, properties are not supported in Python 3.9.1.
            return

        # Check presence of description. If the file is empty, no issue is created,
        # because one does not need to document nothingness.
        if content and self._getDescription(lines) is None:
            self.add_issue(
                obj,
                what,
                name,
                self.ISSUE_UNDOC_DESCRIPTION,
                f"The {what} {name} has no description.",
            )
        else:
            self.add_documented(file)

        # Check presence of return value.
        if self._missingReturn(obj, lines, what, name):
            self.add_issue(
                obj,
                what,
                name,
                self.ISSUE_UNDOC_RETURN,
                f"The return value of {what} {name} is not documented. Note that "
                + "this message may also have been caused by incorrect indentation.",
            )
        else:
            self.add_documented(file)

        # Check presence of parameters.
        undocParameters = self._getParameter(obj, lines, what, self.UNDOCUMENTED)
        for param in undocParameters:
            self.add_issue(
                obj,
                what,
                param,
                self.ISSUE_UNDOC_PARAM,
                f"Parameter {param} of {what} {name} is not documented.",
            )

        # Check for superfluous parameters.
        unusedParameters = self._getParameter(obj, lines, what, self.UNUSED)
        for param in unusedParameters:
            self.add_issue(
                obj,
                what,
                param,
                self.ISSUE_UNUSED_PARAM,
                f"Parameter {param} of {what} {name} has been documented although it "
                + f"is not part of the {what}'s signature. Note that this may also be "
                + "a false positive caused by incorrect indentation. This means "
                + "parameter documentation exceeding a single line needs to be "
                + "indented by a single tab.",
            )

        # Add documented parameters to the number of documented elements.
        docParameters = self._getParameter(obj, lines, what, self.DOCUMENTED)
        self.add_documented(file, len(docParameters))

    def add_issue(self, obj, what, name, issuetype, text):
        """
        Adds an issue to the internal log.

        Args:
            obj: The object itself.
            what: The type of the object which the docstring belongs to.
            name: The fully qualified name of the object.
            issuetype: The type of issue found regarding the given object.
            text: Description of the issue.
        """
        start = end = 1
        if what != 'module':
            lines = inspect.getsourcelines(obj)
            start = 1 if lines[1] == 0 else lines[1]
            end = lines[1] + len(lines[0])

        self.log += [
            {
                self.KEY_ISSUE: issuetype,
                self.KEY_WHAT: what,
                self.KEY_OBJNAME: name,
                self.KEY_FILE: inspect.getsourcefile(obj),
                self.KEY_LINES: (start, end),
                self.KEY_TEXT: text,
            }
        ]

    def add_documented(self, file, count=1):
        """
        Increments the counter for the number of documented elements.

        Args:
            file: The file to increment the counter for.
            count: The number of elements to add to the current count.
        """
        self.documented[file] = (
            self.documented[file] + count if file in self.documented else count
        )

    def finish(self, *args) -> None:
        """
        Method for handling the "build-finished" sphinx event.

        Args:
            args: Other arguments that sphinx might supply.
        """
        self.save()

    def get_coverage(self, file: Optional[str] = None) -> float:
        """
        Returns the documentation coverage in percent.

        To compute the documentation coverage, two files are needed. One containing
        information about all documented code and one containing all warnings about
        undocumented code. The coverage is computed as the ratio of the number of
        entries in each file. Therefore, the documentation coverage may vary depending
        on what is recognized as documented and undocumented code.

        Args:
            file: If given, the coverage is returned for that file.

        Returns:
            Documentation coverage in percent.
        """
        if self.log is None:
            raise Exception("No documentation coverage information available.")

        numdoc = 0
        numundoc = 0
        if file is None:
            numdoc = sum([v for v in self.documented.values()])
            numundoc = len(self.log)
        else:
            numdoc = self.documented[file]
            numundoc = len([e for e in self.log if e[self.KEY_FILE] == file])

        return math.floor(numdoc / (numdoc + numundoc) * 100)

    def report(self, report: Report) -> None:
        """
        Exports the results to the given report.

        Args:
            report: The report to export the results to.
        """
        issues = report.List()

        for entry in self.log:
            filename = entry[self.KEY_FILE]
            relfilename = Path(filename).absolute().relative_to(Path().cwd())
            minline = min(entry[self.KEY_LINES])
            maxline = max(entry[self.KEY_LINES])
            file = report.File(filename)
            file.mark(min(entry[self.KEY_LINES]), file.COLOR_BAD)
            file.set_mark_name(file.COLOR_BAD, "Finding")
            file.range = (
                minline - self._settings.REPORT_LINE_RANGE,
                maxline + self._settings.REPORT_LINE_RANGE,
            )
            report.add(str(relfilename), file)

            summary = (
                "<b>"
                + entry[self.KEY_ISSUE].capitalize()
                + "</b>: "
                + entry[self.KEY_OBJNAME]
            )
            detail = (
                "<b>Object</b>: "
                + entry[self.KEY_OBJNAME]
                + "<br />"
                + "<b>File</b>: "
                + f"<a href=\"{file.outputpath}#{minline}\">"
                + str(relfilename)
                + "</a>"
                + "<br />"
                + "<b>Line</b>: "
                + str(min(entry[self.KEY_LINES]))
                + "<br />"
                + entry[self.KEY_TEXT]
            )
            issues.add(summary, detail)
        issues.summary = ("Coverage", math.floor(self.get_coverage()), "%") # type: ignore
        report.add(self._settings.REPORT_SECTION_NAME_DOCUMENTATION, issues)


class Manager:
    """
    The Manager class provides a simplified command line interface.

    The command line interface offers convenient commands for automated building,
    styling, testing, documenting, and cleaning. Badges are automatically updated to
    show the most important metrics.
    """

    CMD_CHOICES = ["build", "report", "doc", "remove"]
    REQUIREMENTS = [
        ("jinja2", None),
        ("pybadges", None),
        ("dateutil", "python-dateutil"),
        ("sphinx", None),
        ("pydata_sphinx_theme", None),
        ("myst_parser", "myst_parser[linkify]"),
        ("black", None),
        ("isort", None),
        ("flake8", None),
        ("flake8_json_reporter", "flake8-json"),
        ("safety", None),
        ("bandit", None),
        ("coverage", None),
        ("build", None),
        ("mypy", None),
        ("defusedxml", None),
    ]

    def __init__(self, settings: Settings) -> None:
        """
        Initializes the instance with settings.

        Args:
            settings: The settings instance to use.
        """
        self._settings = settings
        
        self.parser = argparse.ArgumentParser(
            description= 
            "This tool wraps some of the best open-source tools available for "
            + "improving\ncode quality. It provides simple, easy to remember commands "
            + "for running them.\n"
            + "The results are compiled into a single, beautiful report as well as "
            + "meaningful\nbadges that you can proudly show. No configuration and "
            + "no clutter.",
            formatter_class=argparse.RawTextHelpFormatter,
        )

        self.parser.add_argument(
            "cmd",
            type=str,
            help="The command to execute:\n"
            + "build:\tThe whole enchilada: Styling, testing,\n"
            + "\tdocumentation generation, security checking\n\tand building.\n"
            + "report:\tAnalyze your code from all angles.\n"
            + "doc:\tGenerates documentation.\n"
            + "remove:\tRemoves everything that can be generated.\n",
            choices=self.CMD_CHOICES,
        )

        self.parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            help="install all missing dependencies without asking.",
        )

        self.parser.add_argument(
            "-q", "--quiet", action="store_true", help="minimal output."
        )

        args = self.parser.parse_args()

        if args.cmd not in self.CMD_CHOICES:
            raise Exception(f"Command {args.cmd} does not exist.")

        self._setup(args.yes)

        self._meta = Meta(settings.CONFIGFILE)
        self._badge = Badge(settings)
        self._report = Report(
            self._settings, self._meta.get("name"), self._meta.get("version")
        )

        self._style = StyleCheck(self._settings)
        self._type = TypeCheck(self._settings)
        self._security = SecurityCheck(self._settings)
        self._test = Test(self._settings)
        self._doc = Documentation(self._settings)
        self._docinspector = DocInspector(self._settings)
        self._build = Build(self._settings)
        self._version = CalVersion(self._settings)

        getattr(self, args.cmd)(args.quiet)

    def _setup(self, yesmode: bool):
        """
        Installs missing dependencies.

        When running package.py required dependencies can be either installed
        automatically using the --yes option or, if this option was omitted, the user
        is asked what to do. This method handles the user interaction and the
        installation of missing dependencies.

        Args:
            yesmode: Set to True if the user shall not be asked whether to install any
                missing dependencies.
        """
        requirements = self.REQUIREMENTS

        # Sometimes, there can be issues with missing certificates when using the 
        # safety package on Windows systems. This can be solved by installing
        # python-certify-win32. However, this package may sometimes also fail to install
        # if there is no matching version available. Therefore, only try to install 
        # it once if safety is also not yet installed. If it fails, do not try to
        # install it again to avoid repetitive questions although everything is
        # working. 
        if platform.system() == "Windows" and require([("safety", None)], False):
            requirements += [("python-certify-win32", None)]

        notinstalled = require(requirements, False)

        if not notinstalled:
            return

        if yesmode:
            require(notinstalled, True)
            return

        print(
            "The following dependencies are required but not installed: "
            + ", ".join([e[0] for e in notinstalled])
        )
        while True:
            answer = input("Do you want to install them now (yes/no)? ")

            if answer.lower() in ["yes", "y"]:
                require(notinstalled, True)
                break
            elif answer.lower() in ["no", "n"]:
                exit()
            else:
                print("Invalid input. You need to answer with yes or no.\n")

    def report(self, quiet: bool):
        """
        Exports the results to the given report.

        Args:
            quiet: Set to True for minimal output.

        Returns:
            True, if all tool runs were successful and did not find any issues.
            False, otherwise.
        """

        self._report = Report(
            self._settings, self._meta.get("name"), self._meta.get("version")
        )

        if not quiet:
            print("Checking dependencies...")
        secresult = self._security.run()
        if not quiet:
            print("Styling code...")
        styleresult = self._style.run()
        if not quiet:
            print("Checking types...")
        typeresult = self._type.run()
        if not quiet:
            print("Running tests...")
        testresult = self._test.run()
        if not quiet:
            print("Generating documentation...")
        docresult = self._doc.run()

        self._docinspector.load()
        self._test.report(self._report)
        self._docinspector.report(self._report)
        self._security.report(self._report)
        self._style.report(self._report)
        self._type.report(self._report)

        self._report.render()

        self._test.clean()
        self._security.clean()
        self._style.clean()
        self._doc.clean()
        self._report.clean()
        self._type.clean()

        return secresult and styleresult and testresult and docresult and typeresult

    def build(self, quiet: bool) -> None:
        """
        Performs an automated build of the package.

        The build artifacts (e.g. wheel files) are stored in a folder as given in the
        settings. However, this is only done if the code passes all tests and style
        checks first. Otherwise, the process is aborted. Badges are updated in the
        process.

        Args:
            quiet: Set to True for minimal output.
        """
        print(f"Setting version to {self._version}.")
        configregex = r"(version[ ]*=)[ ]*[^\n]*"
        self._version.bump(str(self._settings.CONFIGFILE), configregex)

        self.remove(quiet)
        self.report(quiet)
        if not quiet:
            print("Building wheels...")
        self._build.run()

        self._badge.passfail_badge("build", True)
        self._badge.coverage_badge(
            "test coverage",
            self._report.get_total(self._settings.REPORT_SECTION_NAME_TEST),
            self._settings.TEST_COVERAGE_THRESHOLDS,
        )
        self._badge.coverage_badge(
            "doc coverage",
            self._report.get_total(self._settings.REPORT_SECTION_NAME_DOCUMENTATION),
            self._settings.DOCUMENTATION_COVERAGE_THRESHOLDS,
        )
        self._badge.issue_badge(
            "vulnerabilities",
            self._report.get_total(self._settings.REPORT_SECTION_NAME_SECURITY)
            + self._report.get_total(self._settings.REPORT_SECTION_NAME_DEPENDENCIES),
            self._settings.SECURITY_ISSUES_THRESHOLDS,
        )
        self._badge.passfail_badge("test", self._test.ispassed())
        self._badge.passfail_badge("build", self._build.ispassed())

        if not quiet:
            print("Update documentation...")
        self._doc.run()  # Generate documentation again to include recent badges.
        self._clean(quiet)

    def doc(self, quiet: bool) -> None:
        """
        Performs automatic documentation generation.

        Generates documentation using sphinx and updates the documentation related
        badges accordingly.

        Args:
            quiet: Set to True for minimal output.
        """
        # First run is only for determining documentation coverage.
        if not quiet:
            print("Generating documentation...")
        self._doc.run()
        self._doc.clean()

    def remove(self, quiet: bool) -> None:
        """
        Removes all files that have been generated for maximum cleanliness of the
        repository. Everything removed can be generated using the manager commands. For
        example, using:
        ```
        python package.py build
        ```

        Args:
            quiet: Set to True for minimal output.
        """
        if not quiet:
            print("Removing build artifacts...")
        self._build.remove()
        if not quiet:
            print("Removing reports...")
        self._report.remove()
        if not quiet:
            print("Removing temporary files...")
        self._style.remove()
        self._test.remove()
        self._doc.remove()
        self._security.remove()
        self._type.remove()

    def _clean(self, quiet: bool) -> None:
        """
        Remove all intermediate artifacts that might exist in the package.
        """
        if not quiet:
            print("Removing temporary files...")
        self._report.clean()
        self._build.clean()
        self._style.clean()
        self._test.clean()
        self._doc.clean()
        self._security.clean()
        self._type.clean()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    Manager(Settings())
