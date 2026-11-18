"""The automated checks, run against known-good and known-bad submissions.

Run: python3 -m unittest discover grader/tests
Needs a JDK (JAVA_HOME, or JAVA_HOME_<version>_X64 as set by actions/setup-java) and network access to clone
the starter projects; the container test also needs Docker. Tests skip themselves when these are missing.
Only trusted inputs are used here: the exercise starters and submissions written for these tests.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GRADER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRADER))
import checks  # noqa: E402
from checks import container_image, fizzbuzz  # noqa: E402
import grade  # noqa: E402
import lessons  # noqa: E402
import trial  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiers import slow  # noqa: E402

DATA = Path(__file__).resolve().parent / 'data'
STARTERS = {
    'rest_reference': 'https://github.com/AtulKumarSharma79/containerbaseimage.git',  # a finished REST API
    'upgrade_starter': 'https://github.com/AtulKumarSharma79/Frameworkupgrade.git',
    'library_starter': 'https://github.com/AtulKumarSharma79/ReplaceUnsupportedthirdpartylibrary.git',
}
SECURITY_CONFIG_6 = '''package com.example.onboarding.config;

import org.springframework.boot.autoconfigure.security.servlet.PathRequest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.csrf(c -> c.disable())
            .authorizeHttpRequests(a -> a.requestMatchers(PathRequest.toH2Console()).permitAll().anyRequest().authenticated())
            .httpBasic(Customizer.withDefaults())
            .headers(h -> h.frameOptions(f -> f.sameOrigin()));
        return http.build();
    }

    @Bean
    InMemoryUserDetailsManager users() {
        return new InMemoryUserDetailsManager(User.withUsername("admin").password("{noop}admin123").roles("ADMIN").build());
    }
}
'''
GOOD_DOCKERFILE = '''FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY . .
RUN chmod +x gradlew && ./gradlew --no-daemon bootJar -x test

FROM eclipse-temurin:21-jre
RUN useradd --system --uid 10001 app && mkdir /app && chown app /app
WORKDIR /app
COPY --from=build /src/build/libs/*-SNAPSHOT.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
'''


def reference_upgrade(project):
    """What a correct framework-upgrade submission does to the starter."""
    gradle = project / 'build.gradle'
    gradle.write_text(gradle.read_text().replace("version '2.7.18'", "version '3.5.7'")
                      .replace("version '1.0.15.RELEASE'", "version '1.1.7'").replace('commons-text:1.9', 'commons-text:1.12.0'))
    for f in (project / 'src').rglob('*.java'):
        f.write_text(re.sub(r'\bjavax\.(persistence|validation)', r'jakarta.\1', f.read_text()))
    props = project / 'src/main/resources/application.properties'
    props.write_text(props.read_text().replace('server.max-http-header-size=', 'server.max-http-request-header-size=')
                     .replace('spring.jpa.hibernate.use-new-id-generator-mappings=true\n', ''))
    (project / 'src/main/java/com/example/onboarding/config/SecurityConfig.java').write_text(SECURITY_CONFIG_6)


def reference_replacement(project, only=None):
    """What a correct library-replacement submission does to the starter: the solution's files (from its answer
    key repository, kept in data/ so these tests do not depend on that repository staying public)."""
    solution = DATA / 'library_replacement' / 'solution'
    for f in solution.rglob('*'):
        if f.is_file() and (only is None or f.name in only):
            shutil.copy(f, project / f.relative_to(solution))
    if only is None:
        (project / 'src/main/resources/log4j.properties').unlink()


def cannot_clone(what):
    """Offline on a laptop: skip. On GitHub Actions a failed clone must fail the run, not turn it green unchecked."""
    if os.environ.get('GITHUB_ACTIONS'):
        raise RuntimeError(f'cannot clone {what}: the check tests would not run')
    raise unittest.SkipTest(f'cannot clone {what} (offline?)')


class LocalFolder:
    """A source whose one "pull request" is a folder on this machine (a starter or a reference submission)."""

    def __init__(self, path):
        self.path = Path(path)

    def checkout(self, repo, number, dest):
        shutil.copytree(self.path, dest, dirs_exist_ok=True)


def run_check(check, folder, lesson_key=None):
    """Grade a folder exactly as grade.py grades a pull request: same workspace, sandbox and error handling."""
    lesson = lessons.Lesson(lesson_key or check, lesson_key or check, 'local/folder', check, lessons.FIXTURES / (lesson_key or check))
    passed, reasons = grade.grade_submission(lesson, LocalFolder(folder), grade.PullRequest(1, 'tester', 'local', ''))
    return passed, reasons


@slow
@unittest.skipUnless(checks.jdks(), 'needs a JDK')
class FizzBuzzCheckTests(unittest.TestCase):
    def test_meaningful_tests_pass(self):
        ok, reasons = run_check('fizzbuzz', DATA / 'fizzbuzz' / 'good')
        self.assertTrue(ok, reasons)

    def test_tests_in_a_package_pass(self):
        ok, reasons = run_check('fizzbuzz', DATA / 'fizzbuzz' / 'in_package')
        self.assertTrue(ok, reasons)

    def test_weak_tests_fail_and_name_the_bugs_they_miss(self):
        ok, reasons = run_check('fizzbuzz', DATA / 'fizzbuzz' / 'weak')
        self.assertFalse(ok)
        self.assertIn('never says FizzBuzz', reasons[0])

    def test_missing_test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, reasons = run_check('fizzbuzz', Path(tmp))
        self.assertFalse(ok)
        self.assertIn('no FizzBuzzTest.java', reasons[0])


@slow
@unittest.skipUnless(checks.jdks(), 'needs a JDK')
class GradleCheckTests(unittest.TestCase):
    """Builds real Spring Boot projects, so each test takes 15-60 seconds."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        for name, url in STARTERS.items():
            r = subprocess.run(['git', 'clone', '-q', '--depth', '1', url, str(cls.tmp / name)], capture_output=True)
            if r.returncode:
                cannot_clone(url)
        shutil.copytree(cls.tmp / 'upgrade_starter', cls.tmp / 'upgrade_done')
        reference_upgrade(cls.tmp / 'upgrade_done')
        shutil.copytree(cls.tmp / 'library_starter', cls.tmp / 'library_done')
        reference_replacement(cls.tmp / 'library_done')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def copy(self, name):
        dest = Path(tempfile.mkdtemp()) / name
        self.addCleanup(shutil.rmtree, dest.parent, True)
        shutil.copytree(self.tmp / name, dest)
        return dest

    def test_rest_api_reference_passes(self):
        ok, reasons = run_check('rest_api', self.copy('rest_reference'))
        self.assertTrue(ok, reasons)

    def test_rest_api_with_auth_on_every_endpoint_fails(self):
        ok, reasons = run_check('rest_api', self.copy('upgrade_done'))
        self.assertFalse(ok)
        self.assertTrue(any('401' in r for r in reasons), reasons)

    def test_framework_upgrade_starter_fails_with_every_reason(self):
        ok, reasons = run_check('framework_upgrade', self.copy('upgrade_starter'))
        self.assertFalse(ok)
        text = '\n'.join(reasons)
        for part in ('javax', 'server.max-http-header-size', 'use-new-id-generator-mappings', 'Spring Boot 3.5', 'commons-text-1.9'):
            self.assertIn(part, text)

    def test_framework_upgrade_reference_passes(self):
        ok, reasons = run_check('framework_upgrade', self.copy('upgrade_done'))
        self.assertTrue(ok, reasons)

    def test_framework_upgrade_ignores_edited_tests(self):
        project = self.copy('upgrade_done')
        test = project / 'src/test/java/com/example/onboarding/EmployeeApiTests.java'
        test.write_text(test.read_text().replace('isUnauthorized()', 'isOk()'))  # would fail if it were used
        ok, reasons = run_check('framework_upgrade', project)
        self.assertTrue(ok, reasons)

    def test_library_replacement_starter_fails_with_every_reason(self):
        ok, reasons = run_check('library_replacement', self.copy('library_starter'))
        self.assertFalse(ok)
        text = '\n'.join(reasons)
        for part in ('still uses Joda-Time (org.joda): change it to use java.time', 'still uses log4j 1.x', 'still uses opencsv 2.3',
                     'log4j.properties is still there', 'build.gradle still asks for Joda-Time (joda-time:joda-time)',
                     'build.gradle still asks for log4j 1.x', 'build.gradle still asks for opencsv 2.3'):
            self.assertIn(part, text)
        self.assertEqual(len(reasons), 7, reasons)  # each library said once, not again as a jar

    def test_library_replacement_solution_passes(self):
        ok, reasons = run_check('library_replacement', self.copy('library_done'))
        self.assertTrue(ok, reasons)

    def test_library_replacement_half_done_names_only_what_is_left(self):
        project = self.copy('library_starter')
        reference_replacement(project, only={'OnboardingStatusService.java'})  # Joda-Time replaced in source only
        ok, reasons = run_check('library_replacement', project)
        self.assertFalse(ok)
        text = '\n'.join(reasons)
        self.assertNotIn('still uses Joda-Time', text)
        self.assertIn('build.gradle still asks for Joda-Time', text)
        self.assertIn('log4j 1.x', text)
        self.assertIn('opencsv 2.3', text)

    def test_library_replacement_ignores_edited_tests(self):
        project = self.copy('library_done')
        test = project / 'src/test/java/com/example/onboarding/EmployeeApiTests.java'
        test.write_text(test.read_text().replace('@Test', '@Test @org.junit.jupiter.api.Disabled'))
        controller = project / 'src/main/java/com/example/onboarding/controller/EmployeeController.java'
        controller.write_text(controller.read_text().replace('Employee created: id=', 'Created employee '))  # our tests catch it
        ok, reasons = run_check('library_replacement', project)
        self.assertFalse(ok)
        self.assertIn('Gradle build failed', '\n'.join(reasons))

    def test_library_replacement_old_library_left_in_the_build_is_caught(self):
        project = self.copy('library_done')
        gradle = project / 'build.gradle'
        gradle.write_text(gradle.read_text().replace("implementation 'com.opencsv:opencsv:5.9'",
                                                     "implementation 'com.opencsv:opencsv:5.9'\n    testImplementation 'joda-time:joda-time:2.1'"))
        ok, reasons = run_check('library_replacement', project)
        self.assertFalse(ok)
        self.assertEqual(reasons, ['build.gradle still asks for Joda-Time (joda-time:joda-time): remove that line'])

    def test_library_replacement_comments_and_log4j_2_are_not_old_libraries(self):
        project = self.copy('library_done')
        service = project / 'src/main/java/com/example/onboarding/service/OnboardingStatusService.java'
        service.write_text('// Moved from org.joda.time.Days to java.time.\n' + service.read_text())
        gradle = project / 'build.gradle'
        gradle.write_text(gradle.read_text().replace("implementation 'com.opencsv:opencsv:5.9'",
                                                     "implementation 'com.opencsv:opencsv:5.9'\n    implementation 'org.apache.logging.log4j:log4j-api:2.24.3'"))
        ok, reasons = run_check('library_replacement', project)
        self.assertTrue(ok, reasons)

    def trial_of(self, check, test_files=None, tests_repo=''):
        """A lesson's trial, with each repository it fetches standing in for a folder here."""
        unsolved = self.copy('library_done')  # a "solution" with a bug its own tests catch
        controller = unsolved / 'src/main/java/com/example/onboarding/controller/EmployeeController.java'
        controller.write_text(controller.read_text().replace('Employee created: id=', 'Created employee '))
        folders = {'o/starter': self.copy('library_starter'), 'o/solution': self.copy('library_done'), 'o/unsolved': unsolved}

        fetched = self.fetched = []

        class Source:
            def starter(self, repo, dest, ref='HEAD'):
                fetched.append((repo, ref))
                shutil.copytree(folders[repo], dest, dirs_exist_ok=True)
        lesson = lessons.Lesson('trial', 'Trial', 'o/starter', check, test_files or lessons.FIXTURES / 'library_replacement',
                                tests_repo, '', lessons.CHECKING, 'f' * 40 if tests_repo else '')
        return trial.run(lesson, Source())

    def test_trial_pinned_tests_compiling_against_the_starter_pass(self):
        passed, reasons = self.trial_of('tests')
        self.assertTrue(passed, reasons)
        self.assertEqual(reasons, ['the pinned tests compile against the starter'])

    def test_trial_tests_that_do_not_compile_fail_and_say_so(self):
        broken = Path(tempfile.mkdtemp()) / 'broken'
        self.addCleanup(shutil.rmtree, broken.parent, True)
        shutil.copytree(lessons.FIXTURES / 'library_replacement', broken)
        test = next(broken.rglob('*.java'))
        test.write_text(test.read_text() + '\nclass Broken { NoSuchType x; }\n')
        passed, reasons = self.trial_of('tests', test_files=broken)
        self.assertFalse(passed)
        self.assertIn('the pinned tests do not compile against the starter', reasons[0])

    def test_trial_tests_from_a_solutions_repository_must_pass_on_it(self):
        passed, reasons = self.trial_of('tests', tests_repo='o/solution')
        self.assertTrue(passed, reasons)
        self.assertIn('the solution in o/solution passes them', reasons)
        self.assertEqual(self.fetched, [('o/starter', 'HEAD'), ('o/solution', 'f' * 40)], 'the solution at the commit its tests were pinned from')
        passed, reasons = self.trial_of('tests', tests_repo='o/unsolved')
        self.assertFalse(passed)
        self.assertIn('the solution in o/unsolved does not pass the pinned tests', reasons[0])

    def test_trial_build_needs_the_starter_to_build(self):
        self.assertEqual(self.trial_of('build'), (True, ['the starter builds']))

    def test_level_build(self):
        self.assertTrue(run_check('build', self.copy('rest_reference'))[0])
        with tempfile.TemporaryDirectory() as tmp:
            ok, reasons = run_check('build', Path(tmp))
        self.assertFalse(ok)
        self.assertIn('no Gradle project', reasons[0])

    def test_level_tests_uses_the_lessons_fixture_files(self):
        ok, reasons = run_check('tests', self.copy('upgrade_done'), 'framework_upgrade')
        self.assertTrue(ok, reasons)
        ok, reasons = run_check('tests', self.copy('rest_reference'), 'framework_upgrade')
        self.assertFalse(ok)  # no security there, so our auth tests cannot pass
        self.assertIn('Gradle build failed', reasons[0])

    def test_level_tests_without_fixture_files_says_so(self):
        ok, reasons = run_check('tests', self.copy('rest_reference'), 'no_such_lesson')
        self.assertFalse(ok)
        self.assertIn('grader/fixtures/no_such_lesson', reasons[0])

    def test_project_in_a_subfolder_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(self.tmp / 'rest_reference', Path(tmp) / 'onboarding-tracker')
            ok, reasons = run_check('rest_api', Path(tmp))
        self.assertTrue(ok, reasons)


class FizzBuzzSetupTests(unittest.TestCase):
    def test_every_planted_bug_still_applies_to_the_reference_fizzbuzz(self):
        reference = (lessons.FIXTURES / 'fizzbuzz' / 'FizzBuzz.java').read_text()
        for label, old, _new in fizzbuzz.MUTANTS:
            self.assertEqual(reference.count(old), 1, f'planted bug "{label}": "{old}" must appear once in FizzBuzz.java')


class DockerfileRuleTests(unittest.TestCase):
    def problems(self, dockerfile, dockerignore=True):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'Dockerfile').write_text(dockerfile)
            if dockerignore:
                Path(tmp, '.dockerignore').write_text('.git\nbuild\n')
            return container_image.dockerfile_problems(Path(tmp))

    def test_compliant_dockerfile(self):
        self.assertEqual(self.problems(GOOD_DOCKERFILE), [])

    def test_starter_dockerfile_breaks_every_rule(self):
        text = '\n'.join(self.problems('FROM openjdk:17-jdk-slim\nCOPY app.jar app.jar\nENTRYPOINT ["java","-jar","app.jar"]\n', False))
        for part in ('multi-stage', 'openjdk:17-jdk-slim is not on the approved list', 'JRE image', 'non-root', '.dockerignore'):
            self.assertIn(part, text)

    def test_root_user_latest_tag_and_jdk_runtime_are_caught(self):
        text = '\n'.join(self.problems('FROM eclipse-temurin:21-jdk AS b\nFROM eclipse-temurin\nUSER root\n'))
        self.assertIn('eclipse-temurin:latest is not on the approved list', text)
        self.assertIn('non-root', text)
        text = '\n'.join(self.problems('FROM eclipse-temurin:21-jdk AS b\nFROM eclipse-temurin:21-jdk\nUSER app\n'))
        self.assertIn('JRE image', text)

    def test_digest_platform_and_registry_prefix_are_understood(self):
        df = GOOD_DOCKERFILE.replace('FROM eclipse-temurin:21-jre',
                                     'FROM --platform=linux/amd64 docker.io/library/eclipse-temurin:21.0.5_11-jre-noble@sha256:abc')
        self.assertEqual(self.problems(df), [])

    def test_unsupported_java_version_is_rejected(self):
        self.assertTrue(self.problems(GOOD_DOCKERFILE.replace('21-jre', '17-jre')))


class EveryCheckIsTestedTests(unittest.TestCase):
    """A custom check counts only once it is proven here, against a known-good and a known-bad submission."""

    def test_each_check_module_is_run_by_a_test_in_this_file(self):
        names = {f.stem for f in (GRADER / 'checks').glob('*.py')} - {'__init__', 'toolkit'}
        source = Path(__file__).read_text()
        untested = sorted(n for n in names if not re.search(rf"run_check\('{n}'", source))
        self.assertEqual(untested, [], 'add tests with run_check for these checks (see the add-lesson skill, step 5)')


def docker_running():
    return bool(shutil.which('docker')) and subprocess.run(['docker', 'info'], capture_output=True).returncode == 0


@slow
@unittest.skipUnless(checks.jdks() and docker_running(), 'needs a JDK and a running Docker')
class ContainerCheckTests(unittest.TestCase):
    def test_compliant_image_builds_runs_and_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            r = subprocess.run(['git', 'clone', '-q', '--depth', '1', STARTERS['rest_reference'], str(repo)], capture_output=True)
            if r.returncode:
                cannot_clone(STARTERS['rest_reference'])
            (repo / 'Dockerfile').write_text(GOOD_DOCKERFILE)
            (repo / '.dockerignore').write_text('.git\n.gradle\nbuild\n')
            ok, reasons = run_check('container_image', repo)
        self.assertTrue(ok, reasons)


if __name__ == '__main__':
    unittest.main()
