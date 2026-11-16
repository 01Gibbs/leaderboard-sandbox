"""library_replacement: Joda-Time, log4j 1.x and opencsv 2.3 are replaced by supported libraries. No source uses
them, log4j.properties is gone, none of them is in the built app (directly or through another library), and our copy
of the starter's tests passes, so the API, the CSV export and the log message behave exactly as before."""
import re
import zipfile
from pathlib import Path

from .toolkit import CheckFailed, boot_jar, gradle, gradle_project, overlay

# (what to call it, its packages in source, its jar in the built app)
OLD = [
    ('Joda-Time', r'org\.joda\.time', r'joda-time-.*\.jar'),
    ('log4j 1.x', r'org\.apache\.log4j', r'log4j-1\..*\.jar'),  # not Spring Boot's log4j-api-2 or log4j-to-slf4j-2
    ('opencsv 2.3', r'au\.com\.bytecode\.opencsv', r'opencsv-[0-2]\..*\.jar'),  # net.sf.opencsv; com.opencsv 5 is fine
]


def check(ws, lesson):
    project = gradle_project(ws.path)
    main = project / 'src' / 'main'
    problems = []
    sources = sorted(main.rglob('*.java')) if main.exists() else []
    for name, package, _ in OLD:
        users = [f.relative_to(project).as_posix() for f in sources if re.search(rf'\b{package}\b', f.read_text(errors='replace'))]
        if users:
            problems.append(f'{", ".join(users)} still use{"s" if len(users) == 1 else ""} {name} ({package.replace(chr(92), "")})')
    for props in sorted(main.rglob('log4j.properties')) if main.exists() else []:
        problems.append(f'{props.relative_to(project).as_posix()} is still there: move the logging settings to '
                        'application.properties and delete it')

    overlay(lesson.test_files, project)  # our copy of the tests: they must pass unchanged
    try:
        gradle(ws, project, ['test', 'bootJar'])
    except CheckFailed as e:
        raise CheckFailed('\n'.join(problems + [str(e)])) from None
    libs = [Path(n).name for n in zipfile.ZipFile(boot_jar(project)).namelist() if n.startswith('BOOT-INF/lib/')]
    for name, _, jar in OLD:
        found = [lib for lib in libs if re.fullmatch(jar, lib)]
        if found:
            problems.append(f'the built app still contains {name} ({", ".join(found)}): remove it from build.gradle, '
                            'or exclude it from the library that brings it in')
    return not problems, problems or ['old libraries gone, tests pass unchanged: same API, CSV and log message']
