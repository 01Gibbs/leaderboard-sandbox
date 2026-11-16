"""library_replacement: Joda-Time, log4j 1.x and opencsv 2.3 are replaced by supported libraries. No source uses
them, build.gradle no longer asks for them, log4j.properties is gone, none of them is in the built app (directly or
through another library), and our copy of the starter's tests passes, so the API, the CSV export and the log message
behave exactly as before. Our copy of the tests is the starter's, as of its commit 29b8abd."""
import re
import zipfile
from pathlib import Path
from typing import NamedTuple

from .toolkit import CheckFailed, boot_jar, gradle, gradle_project, overlay


class Old(NamedTuple):
    name: str  # what the brief calls it
    package: str  # its packages in source
    coordinate: str  # group:artifact in build.gradle
    jar: str  # its jar in the built app, as a pattern
    instead: str  # the brief's approved replacement


OLD = [
    Old('Joda-Time', 'org.joda', 'joda-time:joda-time', r'joda-time-.*\.jar', 'java.time'),
    Old('log4j 1.x', 'org.apache.log4j', 'log4j:log4j', r'log4j-1\..*\.jar', 'SLF4J (org.slf4j.Logger)'),
    Old('opencsv 2.3', 'au.com.bytecode.opencsv', 'net.sf.opencsv:opencsv', r'opencsv-[0-2]\..*\.jar', 'opencsv 5 (com.opencsv) or Apache Commons CSV'),
]


def code(text):
    """Java source without its comments, so a note such as "moved off org.joda.time" is not counted as a use."""
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def check(ws, lesson):
    project = gradle_project(ws.path)
    main = project / 'src' / 'main'
    problems = []
    sources = {f: code(f.read_text(errors='replace')) for f in sorted(main.rglob('*.java'))} if main.exists() else {}
    for old in OLD:
        users = [f.relative_to(project).as_posix() for f, text in sources.items() if re.search(rf'\b{re.escape(old.package)}\.', text)]
        if users:
            problems.append(f'{", ".join(users)} still use{"s" if len(users) == 1 else ""} {old.name} ({old.package}): '
                            f'change it to use {old.instead}')
    build_files = [f for f in (project / 'build.gradle', project / 'build.gradle.kts') if f.exists()]
    declared = {old.name for old in OLD for f in build_files  # any configuration; not log4j 2's org.apache.logging.log4j:log4j-api
                if re.search(rf'(?<![\w.-]){re.escape(old.coordinate)}(?![\w-])', f.read_text(errors='replace'))}
    for old in OLD:
        if old.name in declared:
            problems.append(f'build.gradle still asks for {old.name} ({old.coordinate}): remove that line')
    for props in sorted(main.rglob('log4j.properties')) if main.exists() else []:
        problems.append(f'{props.relative_to(project).as_posix()} is still there: move the logging settings to '
                        'application.properties and delete it')

    overlay(lesson.test_files, project)  # our copy of the tests: they must pass unchanged
    try:
        gradle(ws, project, ['test', 'bootJar'])
    except CheckFailed as e:
        raise CheckFailed('\n'.join(problems + [str(e)])) from None
    with zipfile.ZipFile(boot_jar(project)) as jar:
        libs = [Path(n).name for n in jar.namelist() if n.startswith('BOOT-INF/lib/')]
    for old in OLD:
        found = [lib for lib in libs if re.fullmatch(old.jar, lib)]
        if found and old.name not in declared:  # declared: already said; otherwise another library brings it in
            problems.append(f'the built app still contains {old.name} ({", ".join(found)}), brought in by another '
                            'library: exclude it from that library in build.gradle')
    return not problems, problems or ['old libraries gone, tests pass unchanged: same API, CSV and log message']
