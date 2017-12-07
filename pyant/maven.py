import collections
import glob
import os
import re
import xml.etree.ElementTree

from pyant import command, git
from pyant.builtin import os as builtin_os

__all__ = ['maven']

class maven:
    def __init__(self):
        self.path = os.getcwd()
        self.errors = None
        self.lines = []

        self.module_name = None
        self.module_home = os.getcwd()

        self.summary = False

    def clean(self):
        self.errors = None
        self.lines = []

        status = None

        cmd = command.command()

        for line in cmd.command('mvn clean -fn -U -T 5'):
            status = self.validate(status, line)

            if not self.ignore(line):
                print(line)

        if not cmd.result():
            status = False

        return status

    def compile(self, cmdline = None, retry_cmd = None, lang = None):
        if not cmdline:
            cmdline = 'mvn install -fn -U'

        self.errors = None
        self.lines = []

        status = None

        cmd = command.command()

        for line in cmd.command(cmdline):
            self.lines.append(line)

            status = self.validate(status, line)

            if not self.ignore(line):
                print(line)

        if not cmd.result():
            status = False

        if status:
            self.lines = []

            return True
        else:
            if retry_cmd:
                modules = self.retry_modules()

                if modules:
                    with builtin_os.tmpdir('tmp') as tmpdir:
                        self.retry_pom(modules, '../pom.xml')

                        return retry_compile(retry_cmd)
                else:
                    return retry_compile(retry_cmd)
            else:
                self.set_errors(lang)
                self.puts_errors()

                return False

    # ----------------------------------------------------------

    def ignore(self, line):
        line = line.strip()

        if re.search(r'^\$\s+', line):
            return False

        if re.search(r'^\(.*\)$', line):
            return False

        if re.search(r'^\[INFO\]\s+Reactor\s+Summary:$', line):
            self.summary = True

        if self.summary:
            if re.search(r'^\[INFO\]\s+Final\s+Memory:', line):
                self.summary = False

            return False
        else:
            if re.search(r'^\[INFO\]\s+-+$', line):
                return False
            elif re.search(r'^\[INFO\]\s+Building\s+', line):
                if re.search(r'^\[INFO\]\s+Building\s+(jar|war|zip)\s*:', line):
                    return True
                else:
                    return False
            elif re.search(r'^\[INFO\]\s+BUILD\s+(SUCCESS|FAILURE)$', line):
                return False
            elif re.search(r'\[(ERROR|EXCEPTION)\]', line):
                return False
            elif re.search(r'http:\/\/', line):
                return True
            elif re.search(r'\[exec\].*\s+(error|errors)\s+', line):
                return False
            elif re.search(r'\:.*\s+(error|errors)\s+', line):
                if 'following dependencies:' in line:
                    return True
                else:
                    return False
            else:
                return True

    def validate(self, status, line):
        m = re.search(r'^\[INFO\]\s+BUILD\s+(SUCCESS|FAILURE)$', line.strip())

        if m:
            if m.group(1) == 'SUCCESS':
                if status is None:
                    return True
                else:
                    return status
            else:
                return False
        else:
            return status

    def set_errors(self, lang = None):
        self.errors = None

        self.module_name = None
        self.module_home = os.getcwd()

        start = None
        logs = {}

        for index, line in enumerate(self.lines):
            line = line.strip()

            m = re.search(r'^\[INFO\]\s+Building\s+', line)

            if m:
                start = True

                if self.module_name:
                    if index > 1:
                        logs[self.module_name][-1] = index - 2
                    else:
                        logs[self.module_name][-1] = index

                self.module_name = m.string[m.end():].split()[0]

                if index > 0:
                    logs[self.module_name] = [index - 1, -1]
                else:
                    logs[self.module_name] = [index, -1]

                continue

            m = re.search(r'^\[INFO\]\s+BUILD\s+(SUCCESS|FAILURE)$', line)

            if m:
                start = False

                if self.module_name:
                    if logs[self.module_name][-1] == -1:
                        if index > 0:
                            logs[self.module_name][-1] = index - 1
                        else:
                            logs[self.module_name][-1] = index

                    self.module_name = None

                continue

            if start:
                if lang == 'cpp':
                    self.set_errors_cpp(line, index)
                else:
                    self.set_errors_java(line, index)
            else:
                if start:
                    m = re.search(r'^\[ERROR\]\s+.*\s+on\s+project\s+(.*?)\s*:', line)

                    if m:
                        self.module_name = m.group(1)

                        found = False

                        if self.errors:
                            for file, info in self.errors.items():
                                if info['module'] == self.module_name:
                                    found = True

                                    break

                        if not found:
                            file = None
                            lineno = None
                            message = [line]

                            for i in range(500):
                                tmpindex = index + i + 1

                                if tmpindex >= len(self.lines):
                                    break
                                end

                                tmpline = self.lines[tmpindex]

                                if tmpline is None:
                                    continue

                                tmpline = tmpline.strip()

                                if re.search(r'^\[ERROR\]\s+->\s+\[Help\s+.*\]$', tmpline):
                                    break

                                m = re.search(r'^\[ERROR\]\s+.*\s+in\s+(.*?)\/target\/', tmpline)

                                if m:
                                    file = os.path.abspath(m.group(1))

                                if re.search(r'^\[INFO\]\s+Building\s+', tmpline):
                                    break

                                message.append(tmpline)

                            if not self.errors:
                                self.errors = collections.OrderedDict()

                            if file not in self.errors:
                                self.errors[file] = {
                                    'module'  : self.module_name,
                                    'logs'    : None,
                                    'message' : {}
                                }

                            self.errors[file]['message'][lineno] = message

                        self.module_name = None

                        continue

        if self.errors:
            for file in self.errors:
                if file:
                    artifact_id = self.artifactid(file)

                    if artifact_id:
                        logs_info = logs.get(artifact_id)

                        if logs_info:
                            self.errors[file]['logs'] = self.lines[logs_info[0]:logs_info[-1]]

                    author, email, date, url = self.scm_info(file)

                    self.errors[file]['author'] = author
                    self.errors[file]['email'] = email
                    self.errors[file]['date'] = date
                    self.errors[file]['url'] = url

        return self.errors

    def set_errors_java(self, line, index):
        m = re.search(r'\s+Compiling\s+\d+\s+source\s+(file|files)\s+to\s+(.*)\/target\/', line)

        if m:
            self.module_home = m.group(2)

            return True

        m = re.search(r'^\[ERROR\]\s+(.+):\[(\d+),\d+\]', line)

        if m:
            if self.module_home and os.path.isdir(self.module_home):
                with builtin_os.chdir(self.module_home) as chdir:
                    file = os.path.abspath(m.group(1))
                    lineno = int(m.group(2))
                    message = [line]

                    for i in range(10):
                        tmpindex = index + i + 1

                        if tmpindex >= len(self.lines):
                            break

                        tmpline = self.lines[tmpindex]

                        if tmpline is None:
                            continue

                        tmpline = tmpline.strip()

                        if re.search(r'^\[INFO\]\s+\d+(error|errors)$', tmpline):
                            break

                        if re.search(r'^\[INFO\]', tmpline):
                            continue

                        message.append(tmpline)

                    if not self.errors:
                        self.errors = collections.OrderedDict()

                    if file not in self.errors:
                        self.errors[file] = {
                            'module'  : self.module_name,
                            'logs'    : None,
                            'message' : {}
                        }

                    self.errors[file]['message'][lineno] = message

                return True
            else:
                return False

        m = re.search(r'^Tests\s+run\s*:\s*(\d+)\s*,\s*Failures\s*:\s*(\d+)\s*,\s*Errors\s*:\s*(\d+)\s*,\s*Skipped\s*:\s*(\d+)\s*,\s*.*FAILURE.*\s*-\s*in\s+', line)

        if m:
            if self.module_home and os.path.isdir(self.module_home):
                with builtin_os.chdir(self.module_home) as chdir:
                    if int(m.group(2)) > 0 or int(m.group(3)):
                        filename = '%s.java' % m.string[m.end():].replace('.', '/')
                        file = None

                        if os.path.isfile(os.path.join('src/test/java', filename)):
                            file = os.path.abspath(os.path.join('src/test/java', filename))
                        else:
                            for name in glob.iglob(os.path.join('**', filename), recursive = True):
                                file = os.path.abspath(name)

                                if name.startswith('src/'):
                                    break

                        if file:
                            lineno = None
                            message = [line]

                            for i in range(10):
                                tmpindex = index + i + 1

                                if tmpindex >= len(self.lines):
                                    break

                                tmpline = self.lines[tmpindex]

                                if tmpline is None:
                                    continue

                                tmpline = tmpline.strip()

                                m = re.search(r'^at\s+.*\(#{File.basename(filename)}\s*:\s*(\d+)\)$', tmpline)

                                if m:
                                    lineno = int(m.group(1))
                                    message.append(tmpline)

                                    break

                                message.append(tmpline)

                            if not self.errors:
                                self.errors = collections.OrderedDict()

                            if file not in self.errors:
                                self.errors[file] = {
                                    'module'  : self.module_name,
                                    'logs'    : None,
                                    'message' : {}
                                }

                            self.errors[file]['message'][lineno] = message

                return True
            else:
                return False

        return None

    def set_errors_cpp(self, line, index):
        m = re.search(r'\s+\/bin\/sh\s+-c\s+cd\s+(.*?)\s+&&\s+', line)

        if m:
            self.module_home = m.group(1)

            return True

        m = re.search(r'\s+\/Fo(.*?)\\target\\objs\\.*\.obj\s+-c\s+', line)

        if m:
            self.module_home = m.group(1)

            return True

        # compile
        #   linux   : r':\s*(\d+)\s*:\s*(\d+)\s*:\s*\w*\s*(error|错误)\s*\w*\d*(:|：)'
        #   solaris : r',\s*第\s*(\d+)\s*行:\s*(error|错误)\s*,/'
        #   windows : r'\((\d+)\)\s*:\s*\w*\s*(error|错误)\s*\w*\d*(:|：)', r':\s*(\d+)\s*:\s*\w*\s*(error|错误)\s*\w*\d*(:|：)'
        m = (re.search(r':\s*(\d+)\s*:\s*(\d+)\s*:\s*\w*\s*(error|错误)\s*\w*\d*(:|：)', line) or
            re.search(r',\s*第\s*(\d+)\s*行:\s*(error|错误)\s*,', line) or
            re.search(r'\((\d+)\)\s*:\s*\w*\s*(error|错误)\s*\w*\d*(:|：)', line) or
            re.search(r':\s*(\d+)\s*:\s*\w*\s*(error|错误)\s*\w*\d*(:|：)', line))

        if m:
            if self.module_home and os.path.isdir(self.module_home):
                with builtin_os.chdir(self.module_home) as chdir:
                    file = m.string[:m.start()].strip()
                    lineno = int(m.group(1))
                    message = [line]

                    m = re.search(r'^"(.*)"$', file)

                    if m:
                        file = m.group(1).strip()

                    if file:
                        file = os.path.abspath(file)

                        if not self.errors:
                            self.errors = collections.OrderedDict()

                        if file not in self.errors:
                            self.errors[file] = {
                                'module'  : self.module_name,
                                'logs'    : None,
                                'message' : {}
                            }

                        self.errors[file]['message'][lineno] = message

                return True
            else:
                return False

        # link
        #   linux   : r'collect2\s*:\s*ld\s+', r':\s*(\d+)\s*:\s*undefined\s+reference\s+to\s+'
        #   solaris : r'ld\s*:\s*.*:\s*symbol\s+referencing\s+errors\.', r'\s+target\/objs\/(.*?)\.o$'
        #   windows : r'\s*:\s*fatal\s+error\s+LNK\d+\s*:', r':\s*error\s+LNK\d+\s*:\s*unresolved\s+external\s+symbol\s+'
        m = (re.search(r'collect2\s*:\s*ld\s+', line) or
            re.search(r'ld\s*:\s*.*:\s*symbol\s+referencing\s+errors\.', line) or
            re.search(r'\s*:\s*fatal\s+error\s+LNK\d+\s*:', line))

        if m:
            if re.search(r'collect2\s*:\s*ld\s+', line):
                osname = 'linux'
            elif re.search(r'ld\s*:\s*.*:\s*symbol\s+referencing\s+errors\.', line):
                osname = 'solaris'
            elif re.search(r'\s*:\s*fatal\s+error\s+LNK\d+\s*:', line):
                osname = 'windows'
            else:
                osname = None

            if self.module_home and os.path.isdir(self.module_home):
                with builtin_os.chdir(self.module_home) as chdir:
                    file = os.getcwd()
                    lineno = None
                    message = []

                    for i in range(500):
                        tmpindex = index - i - 1

                        if tmpindex < 0:
                            break

                        tmpline = self.lines[tmpindex]

                        if tmpline is None:
                            continue

                        tmpline = tmpline.strip()

                        if re.search(r':\s*link\s+\(default-link\)\s+@', tmpline):
                            break

                        if ((osname == 'linux' and re.search(r':\s*(\d+)\s*:\s*undefined\s+reference\s+to\s+', tmpline)) or
                            (osname == 'solaris' and re.search(r'\s+target\/objs\/(.*?)\.o$', tmpline)) or
                            (osname == 'windows' and re.search(r':\s*error\s+LNK\d+\s*:\s*unresolved\s+external\s+symbol\s+', tmpline))):
                            message.append(tmpline)

                    if not self.errors:
                        self.errors = collections.OrderedDict()

                    if file not in self.errors:
                        self.errors[file] = {
                            'module'  : self.module_name,
                            'logs'    : None,
                            'message' : {}
                        }

                    message.reverse()

                    self.errors[file]['message'][lineno] = message

                return True
            else:
                return False

        return None

    def puts_errors(self):
        if self.errors:
            errors = {}

            for file in self.errors:
                if file:
                    author = self.errors[file]['author']

                    if author not in errors:
                        errors[author] = {}

                    errors[author][file] = self.errors[file]['date']

            if errors:
                print()
                print('*' * 60)

                for author in sorted(list(errors.keys())):
                    print('%s:' % author)
                    print('=' * 30)

                    for file in sorted(list(errors[author].keys())):
                        print('  %s, %s' % (file, errors[author][file]))

                    print()

    def artifactid(self, path):
        if os.path.isfile(path):
            return self.artifactid(os.path.dirname(path))
        elif os.path.isdir(path):
            if os.path.isfile(os.path.join(path, 'pom.xml')):
                try:
                    xmlns = 'http://maven.apache.org/POM/4.0.0'
                    xml.etree.ElementTree.register_namespace('', xmlns)

                    namespace = {
                        'ns': xmlns
                    }

                    tree = xml.etree.ElementTree.parse(os.path.join(path, 'pom.xml'))
                    e = tree.find('ns:artifactId', namespace)

                    if e is not None:
                        text = e.text

                        if text.startswith('${prefix}'):
                            if sys.platform == 'win32':
                                text = text.replace('${prefix}', '')
                            else:
                                text = text.replace('${prefix}', 'lib')

                        return text
                    else:
                        return None
                except:
                    return None
            else:
                if os.path.dirname(path) == path:
                    return None
                else:
                    return self.artifactid(os.path.dirname(path))
        else:
            return None

    def artifactid_paths(self, dirname):
        if not dirname:
            dirname = '.'

        map = {}

        if os.path.isfile(os.path.join(dirname, 'pom.xml')):
            with builtin_os.chdir(dirname) as chdir:
                try:
                    xmlns = 'http://maven.apache.org/POM/4.0.0'
                    xml.etree.ElementTree.register_namespace('', xmlns)

                    namespace = {
                        'ns': xmlns
                    }

                    tree = xml.etree.ElementTree.parse('pom.xml')
                    e = tree.find('ns:artifactId', namespace)

                    if e is not None:
                        map[e.text.strip()] = os.getcwd()

                    for e in tree.findall('.//ns:modules/ns:module', namespace):
                        module_path = e.text.strip()

                        if module_path:
                            for k, v in self.artifactid_paths(module_path).items():
                                map[k] = v
                except:
                    pass

        return map

    def retry_compile(self, cmd):
        if os.path.isfile('pom.xml'):
            self.errors = None
            self.lines = []

            status = None

            for line in cmd.command(cmd):
                self.lines.append(line)

                status = self.validate(status, line)

                print(line)

            if not cmd.result():
                return False

            if status:
                self.lines = []

                return True
            else:
                self.set_errors(lang)
                self.puts_errors()

                return False
        else:
            return False

    def retry_modules(self):
        modules = {}

        start = False

        for line in self.lines:
            line = line.strip()

            if re.search(r'^\[INFO\]\s+Reactor\s+Summary:$', line):
                start = True

            if re.search(r'^\[INFO\]\s+BUILD\s+(SUCCESS|FAILURE)$', line):
                start = False

            if start:
                m = re.search(r'^\[INFO\]\s+(.*?)\s+\.+\s*(FAILURE|SKIPPED)', line)

                if m:
                    modules[m.group(1)] = None

        if modules:
            paths = self.artifactid_paths(self.path)

            for module_name in list(modules.keys()):
                path = paths.get(module_name)

                if path:
                    modules[module_name] = os.path.relpath(path, os.getcwd())
                else:
                    del modules[module_name]

        return modules

    def retry_pom(self, modules, template):
        try:
            xmlns = 'http://maven.apache.org/POM/4.0.0'
            xml.etree.ElementTree.register_namespace('', xmlns)

            namespace = {
                'ns': xmlns
            }

            tree = xml.etree.ElementTree.parse(template)

            for e in tree.findall('ns:artifactId', namespace):
                e.text = '%s-tmp' % e.text.strip()

            for e in tree.findall('.//ns:modules', namespace):
                for element in e.findall('ns:module', namespace):
                    e.remove(element)

            for e in tree.findall('ns:build', namespace):
                tree.getroot().remove(e)

            e = tree.find('ns:modules', namespace)

            for module, path in modules.items():
                element = xml.etree.ElementTree.Element('{%s}module' % namespace['ns'])
                element.text = '/'.join(('..', path))
                e.append(element)

            tree.write('pom.xml', encoding = 'utf-8', xml_declaration= True)
        except:
            pass

    def scm_info(self, file):
        author = None
        email = None
        date = None
        url = None

        if file:
            info = git.info(file)

            if info:
                author = info['author']
                email = info['email']
                date = info['date']
                url = info['url']

        return (author, email, date, url)
