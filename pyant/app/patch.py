import collections
import datetime
import glob
import os
import os.path
import random
import re
import shutil

from lxml import etree

from pyant import command, daemon, password, smtp, string
from pyant.app import const
from pyant.builtin import os as builtin_os

__all__ = ('auto', 'patch', 'installation')

def auto():
    status = True

    if os.path.isdir(const.PATCH_XML_HOME):
        with builtin_os.chdir(const.PATCH_XML_HOME) as chdir:
            print('===== 拷贝补丁申请单 =====')

            for dir in glob.iglob('*', recursive = True):
                if not os.path.isdir(dir):
                    try:
                        os.remove(dir)
                    except:
                        pass

                    continue

                m = re.search(r'^(umebn|bn)_.*\((\d{8}.*)\)$', dir)

                if not m:
                    shutil.rmtree(dir, ignore_errors = True)

                    continue

                module = m.group(1)
                name = m.group(2)

                if module in ('bn',):
                    deploy_homes = [
                        os.path.join(const.PATCH_TEMPLATE_HOME, module, 'linux', name),
                        os.path.join(const.PATCH_TEMPLATE_HOME, module, 'windows', name),
                        os.path.join(const.PATCH_TEMPLATE_HOME, module, 'windows_x86', name)
                    ]
                else:
                    deploy_homes = [os.path.join(const.PATCH_TEMPLATE_HOME, module, 'none', name)]

                with builtin_os.chdir(dir) as _chdir:
                    for file in glob.iglob('**/*.xml', recursive = True):
                        try:
                            for deploy_home in deploy_homes:
                                os.makedirs(deploy_home, exist_ok = True)
                                shutil.copyfile(file, os.path.join(deploy_home, os.path.basename(file)))

                                if module in ('bn'):
                                    zipname = '%s.zip' % os.path.splitext(file)[0]

                                    if os.path.isfile(zipname):
                                        shutil.copyfile(zipname, os.path.join(deploy_home, os.path.basename(zipname)))
                        except Exception as e:
                            print(e)

                            status = False
                            continue

                shutil.rmtree(dir, ignore_errors = True)

    auto_info = []

    if os.path.isdir(const.PATCH_TEMPLATE_HOME):
        with builtin_os.chdir(const.PATCH_TEMPLATE_HOME) as chdir:
            print('===== 分发补丁申请单 =====')

            for dir in glob.iglob('*/*', recursive = True):
                if dir in const.PATCH_NODE_INFO:
                    ip, home = const.PATCH_NODE_INFO[dir]
                    proxy = daemon.PyroFileProxy(ip)

                    try:
                        proxy.proxy._pyroBind()
                    except:
                        continue

                    with builtin_os.chdir(dir) as _chdir:
                        for name in glob.iglob('*', recursive = True):
                            try:
                                if proxy.isdir(builtin_os.join(home, 'patch/build', 'dev', name)):
                                    build_home = builtin_os.join(home, 'patch/build', 'dev', name)
                                elif proxy.isdir(builtin_os.join(home, 'patch/build', 'release', name)):
                                    build_home = builtin_os.join(home, 'patch/build', 'release', name)
                                else:
                                    build_home = None

                                if build_home:
                                    for file in glob.iglob(os.path.join(name, '**/*.xml'), recursive = True):
                                        print('  %s' % os.path.normpath(os.path.abspath(file)))

                                        zipname = '%s.zip' % os.path.splitext(file)[0]

                                        try:
                                            tree = etree.parse(file)

                                            if not proxy.write(
                                                builtin_os.join(build_home, 'xml', os.path.basename(file)),
                                                etree.tostring(tree, encoding='utf-8', pretty_print=True, xml_declaration='utf-8')
                                            ):
                                                continue

                                            if os.path.isfile(zipname):
                                                if not proxy.copy_file(
                                                    zipname,
                                                    builtin_os.join(build_home, 'xml', os.path.basename(zipname))
                                                ):
                                                    continue

                                                os.remove(zipname)

                                            os.remove(file)
                                        except Exception as e:
                                            print(e)

                                            status = False
                                            continue

                                        if (dir, name) not in auto_info:
                                            auto_info.append((dir, name))

                                    if len(glob.glob(os.path.join(name, '**/*.xml'), recursive = True)) == 0:
                                        shutil.rmtree(name, ignore_errors = True)
                                else:
                                    shutil.rmtree(name, ignore_errors = True)
                            except Exception as e:
                                print(e)

                                status = False
                                continue

                    if len(glob.glob(os.path.join(dir, '**/*.xml'), recursive = True)) == 0:
                        shutil.rmtree(dir, ignore_errors = True)
                else:
                    shutil.rmtree(dir, ignore_errors = True)

            for dir in glob.iglob('*', recursive = True):
                if len(glob.glob(os.path.join(dir, '**/*.xml'), recursive = True)) == 0:
                    shutil.rmtree(dir, ignore_errors = True)

    if auto_info:
        print('===== 启动补丁制作 =====')

        for dir, name in auto_info:
            dir_paths = dir.split('/')

            if dir_paths[0] in ('bn',):
                jobname = '%s/patch/%s_patch_%s_%s' % (dir_paths[0], dir_paths[0], name, dir_paths[1])
            else:
                jobname = '%s/patch/%s_patch_%s' % (dir_paths[0], dir_paths[0], name)

            cmdline = 'java -jar "%s" -s %s build --username %s --password %s "%s"' % (
                const.JENKINS_CLI, const.JENKINS_URL, const.JENKINS_USERNAME, const.JENKINS_PASSWORD,
                jobname
            )

            display_cmd = 'java -jar "%s" -s %s build --username %s --password %s "%s"' % (
                const.JENKINS_CLI, const.JENKINS_URL, password.password(const.JENKINS_USERNAME), password.password(const.JENKINS_PASSWORD),
                jobname
            )

            cmd = command.command()

            for line in cmd.command(cmdline, display_cmd = display_cmd):
                print(line)

    return status

# ******************************************************** #
#                          PATCH                           #
# ******************************************************** #

# 目录结构
#   patch
#       build
#           dev
#           release
#               20171203
#                   build
#                   xml
#       patch
#           dev
#           release
#               20171203
#                   installation
#                   patch
class patch():
    def __init__(self, path):
        self.path = builtin_os.abspath(path)

        m = re.search(r'\/build\/(dev|release)\/', self.path)

        if m:
            self.output = builtin_os.join(m.string[:m.start()], 'patch', m.group(1), m.string[m.end():])
        else:
            self.output = self.path

        self.name = 'none'
        self.type = 'none'
        self.notification = '<PATCH 通知>'
        self.modules = {}

    def init(self, branch = None):
        os.makedirs(self.path, exist_ok = True)
        os.makedirs(self.output, exist_ok = True)

        with builtin_os.chdir(self.path) as chdir:
            os.makedirs('build', exist_ok = True)
            os.makedirs('xml', exist_ok = True)

        with builtin_os.chdir(self.output) as chdir:
            os.makedirs('installation', exist_ok = True)
            os.makedirs('patch', exist_ok = True)

        return True

    def build(self):
        status = True

        message = []

        if os.path.isdir(self.path):
            with builtin_os.chdir(self.path) as chdir:
                for file in glob.iglob('xml/*.xml', recursive = True):
                    if not os.path.isfile(file):
                        continue

                    infoes = self.load_xml(file)

                    if infoes is None:
                        to_addrs, cc_addrs = self.get_addrs_from_file(file)

                        message.append((os.path.basename(file), '解析XML文件失败', False))
                        self.sendmail('%s 解析XML文件失败, 请尽快处理' % self.notification, to_addrs, cc_addrs, None, file)

                        clean_env(file);

                        status = False
                        continue

                    if len(infoes) == 0:
                        message.append((os.path.basename(file), '未找到补丁信息', True))

                        clean_env(file);

                        continue

                    tmpdir = os.path.join(builtin_os.gettempdir(),
                        '%s%04d' % (datetime.datetime.now().strftime('%Y%m%d%H%M%S'), int(random.random() * 1000)))

                    index = -1
                    current = []

                    to_addrs, cc_addrs = self.get_addrs(infoes[0])

                    for info in infoes:
                        index += 1

                        if not self.build_permit(info):
                            continue

                        current.append([os.path.basename(file), index, False])

                        if not self.build_delete(info):
                            status = False

                            continue

                        if not self.build_source(info):
                            status = False

                            continue

                        if not self.build_compile(info):
                            status = False

                            continue

                        if not self.build_deploy(info, os.path.join(tmpdir, str(index))):
                            status = False

                            continue

                        if not self.build_check(os.path.join(tmpdir, str(index))):
                            status = False

                            continue

                        current[-1][-1] = True

                    status_all = True

                    for filename, index, _status in current:
                        if not _status:
                            status_all = False

                            break

                    if status_all:
                        for filename, index, _status in current:
                            id = self.get_id()

                            output = os.path.join(self.output, 'patch', id)
                            cur_status = True

                            with builtin_os.chdir(os.path.join(tmpdir, str(index)), True) as _chdir:
                                for name in glob.iglob('**/*', recursive = True):
                                    if os.path.isfile(name):
                                        try:
                                            dest_file = os.path.join(output, 'patch', name)
                                            os.makedirs(os.path.dirname(dest_file), exist_ok = True)

                                            shutil.copyfile(name, dest_file)
                                        except Exception as e:
                                            print(e)

                                            shutil.rmtree(output)

                                            status = False
                                            cur_status = False

                                            break

                            if cur_status:
                                if len(glob.glob(os.path.join(output, '*'), recursive = True)) == 0:
                                    message.append(('%s(%s)' % (filename, index), '补丁制作成功, 但没有输出文件(补丁号: %s)' % id, True))
                                    self.sendmail('%s 补丁制作成功, 但没有输出文件(补丁号: %s)'  % (self.notification, id), to_addrs, cc_addrs, None, file)
                                else:
                                    message.append(('%s(%s)' % (filename, index), '补丁制作成功(补丁号: %s)' % id, True))
                                    self.sendmail('%s 补丁制作成功, 请验证(补丁号: %s)' % (self.notification, id), to_addrs, cc_addrs, None, file)

                                self.to_xml(infoes[index], os.path.join(output, self.get_xml_filename(infoes[index])))
                            else:
                                message.append(('%s(%s)' % (filename, index), '补丁制作成功, 但输出补丁失败', True))
                                self.sendmail('%s 补丁制作成功, 但输出补丁失败' % self.notification, to_addrs, cc_addrs, None, file)
                    else:
                        for filename, index, _status in current:
                            if _status:
                                message.append(('%s(%s)' % (filename, index), '补丁制作成功, 但关联补丁制作失败', True))
                                self.sendmail('%s 补丁制作成功, 但关联补丁制作失败, 请尽快处理' % self.notification, to_addrs, cc_addrs, None, file)
                            else:
                                message.append(('%s(%s)' % (filename, index), '补丁制作失败', False))
                                self.sendmail('%s 补丁制作失败, 请尽快处理' % self.notification, to_addrs, cc_addrs, None, file)

                    clean_env(file, tmpdir);

        return status

    # ------------------------------------------------------

    def build_permit(self, info):
        return True

    def build_delete(self, info):
        return True

    def build_source(self, info):
        return True

    def build_compile(self, info):
        return True

    def build_deploy(self, info, path):
        return True

    def build_check(self, path):
        with builtin_os.chdir(path) as chdir:
            for file in glob.iglob('**/*.xml', recursive = True):
                try:
                    etree.parse(file)
                except Exception as e:
                    print(e)

                return False

        return True

    # info:
    #   name            : ''
    #   source          : []
    #   info            : {}
    def load_xml(self, file):
        try:
            tree = etree.parse(file)
        except Exception as e:
            print(e)

            return None

        if tree.getroot().get('version', '').strip() != '2.0':
            print('补丁申请单格式错误, 请使用新补丁申请单模板(版本号2.0)')

            return None

        infoes = []

        status = True
        index = -1

        for e in tree.findall('patch'):
            index += 1

            name = e.get('name', '').strip()

            if name:
                if name not in self.modules:
                    print('patch[%s]: patch节点的name属性不是合法的模块名称 - %s' % (index, name))

                    status = False
            else:
                print('patch[%s]: patch节点的name属性不能为空' % index)

                status = False

            info = {
                'name'      : name,
                'source'    : [],
                'info'      : collections.OrderedDict({
                    '提交人员'  : None,
                    '变更版本'  : None,
                    '变更类型'  : None,
                    '变更描述'  : None,
                    '关联故障'  : None,
                    '影响分析'  : None,
                    '依赖变更'  : None,
                    '走查人员'  : None,
                    '走查结果'  : None,
                    '自测结果'  : None,
                    '变更来源'  : None,
                    '开发经理'  : None,
                    '抄送人员'  : None
                })
            }

            for e_source in e.findall('source/attr'):
                name = builtin_os.normpath(e_source.get('name', '').strip())

                if name:
                    if name not in info['source']:
                        info['source'].append(name)
                else:
                    print('patch[%s]/source/attr: source下attr节点的name属性不能为空' % index)

                    status = False

            for e_info in e.findall('info/attr'):
                name = e_info.get('name', '').strip()

                if e_info.text:
                    value = e_info.text.strip()
                else:
                    value = ''

                if name:
                    if name in ('提交人员', '走查人员', '开发经理', '抄送人员'):
                        value = value.replace('\\', '/')

                    info['info'][name] = value
                else:
                    print('patch[%s]/info/attr: info下attr节点的name属性不能为空' % index)

                    status = False

            for x in info['info']:
                if info['info'][x] is None:
                    print('patch[%s]/info: info节点缺少(%s)' % (index, x))

                    status = False
                    continue

                if x in ('变更类型'):
                    if info['info'][x] not in ('需求', '优化', '故障'):
                        print('patch[%s]/info: info节点的(%s)必须是需求, 优化 或 故障' % (index, x))

                        status = False

                    continue

                if x in ('变更描述'):
                    if len(info['info'][x]) < 10:
                        print('patch[%s]/info: info节点的(%s)必须最少10个字符, 当前字符数: %s' % (index, x, len(info['info'][x])))

                        status = False

                    continue

                if x in ('关联故障'):
                    if not re.search(r'^[\d,\s]+$', info['info'][x]):
                        print('patch[%s]/info: info节点的(%s)必须是数字' % (index, x))

                        status = False

                    continue

                if x in ('变更来源'):
                    if not info['info'][x]:
                        print('patch[%s]/info: info节点的(%s)不能为空' % (index, x))

                        status = False

                    continue

                if x in ('走查人员', '抄送人员'):
                    info['info'][x] = string.split(info['info'][x])

                    continue

            if not self.__load_xml__(info, e, file):
                status = False
                continue

            infoes.append(info)

        if status:
            return infoes
        else:
            return None

    def to_xml(self, info, file):
        tree = etree.ElementTree(etree.XML("<patches version='2.0'/>"))

        element = etree.Element('patch')
        element.set('name', info['name'])

        tree.getroot().append(element)

        if not self.__to_xml__(info, element):
            return False

        info_element = etree.Element('info')
        element.append(info_element)

        for x in info['info']:
            e = etree.Element('attr')
            e.set('name', x)

            if isinstance(info['info'][x], str):
                e.text = info['info'][x]
            else:
                e.text = ', '.join(info['info'][x])

            info_element.append(e)

        os.makedirs(os.path.dirname(file), exist_ok = True)

        try:
            tree.write(file, encoding='utf-8', pretty_print=True, xml_declaration=True)

            return True
        except Exception as e:
            print(e)

            return False

    def clean_env(self, file, tmpdir = None):
        try:
            if os.path.isfile(file):
                os.remove(file)

            for name in glob.iglob('%s.%s' % (os.path.splitext(file)[0], '*')):
                if os.path.isfile(name):
                    os.remove(name)

            if tmpdir:
                shutil.rmtree(tmpdir)
        except:
            pass

    def get_addrs(self, info):
        to_addrs = '%s@zte.com.cn' % info['info']['提交人员'].replace('\\', '/').split('/', 1)[-1]

        cc_addrs = ['%s@zte.com.cn' % x.replace('\\', '/').split('/', 1)[-1] for x in info['info']['走查人员'] + info['info']['抄送人员']]
        cc_addrs.append('%s@zte.com.cn' % info['info']['开发经理'].replace('\\', '/').split('/', 1)[-1])

        return (to_addrs, cc_addrs)

    def get_addrs_from_file(self, file):
        to_addrs = None
        cc_addrs = []

        for encoding in ('utf-8', 'cp936'):
            try:
                with open(file, encoding = encoding) as f:
                    for line in f.readlines():
                        line = line.strip()

                    m = re.search(r'^<\s*attr\s+name\s*=.*提交人员.*>(.*)<\s*/\s*attr\s*>$', line)

                    if m:
                        to_addrs = '%s@zte.com.cn' % m.group(1).replace('\\', '/').split('/', 1)[-1]

                        continue

                    m = re.search(r'^<\s*attr\s+name\s*=.*走查人员.*>(.*)<\s*/\s*attr\s*>$', line)

                    if m:
                        cc_addrs += ['%s@zte.com.cn' % x.strip().replace('\\', '/').split('/', 1)[-1] for x in m.group(1).split(',')]

                        continue

                    m = re.search(r'^<\s*attr\s+name\s*=.*开发经理.*>(.*)<\s*/\s*attr\s*>$', line)

                    if m:
                        cc_addrs.append('%s@zte.com.cn' % m.group(1).replace('\\', '/').split('/', 1)[-1])

                        continue

                    break
            except:
                pass

        return (to_addrs, cc_addrs)

    def get_id(self):
        prefix = datetime.datetime.now().strftime('%Y%m%d')
        id = 0

        if os.path.isdir(os.path.join(self.output, 'patch')):
            with builtin_os.chdir(os.path.join(self.output, 'patch')) as chdir:
                for x in glob.iglob('%s_*' % prefix):
                    m = re.search(r'^\d{8}_(\d{4})$', x)

                    if m:
                        if id < int(m.group(1)):
                            id = int(m.group(1))

        return '%s_%04d' % (prefix, id + 1)

    def get_xml_filename(self, info):
        name, id = info['info']['提交人员'].replace('\\', '/').split('/', 1)

        return '%s_%s_%s.xml' % (datetime.datetime.now().strftime('%Y%m%d'), id, name)

    def sendmail(self, notification, to_addrs, cc_addrs = None, lines = None, file = None):
        if lines is None:
            lines = []

        if os.environ.get('BUILD_URL'):
            console_url = builtin_os.join(os.environ['BUILD_URL'], 'console')

            lines.append('')
            lines.append('详细信息: <a href="%s">%s</a>' % (console_url, console_url))
            lines.append('')

        smtp.sendmail(notification, to_addrs, cc_addrs, '<br>\n'.join(lines))

    def __load_xml__(self, info, element, file):
        return True

    def __to_xml__(self, info, element):
        return True

# ******************************************************** #
#                    PATCH INSTALLATION                    #
# ******************************************************** #

class installation():
    def __init__(self, path):
        self.path = builtin_os.abspath(path)

        m = re.search(r'\/build\/(dev|release)\/', self.path)

        if m:
            self.output = builtin_os.join(m.string[:m.start()], 'patch', m.group(1), m.string[m.end():])
        else:
            self.output = self.path

        self.name = 'none'
        self.type = 'none'

    def build(self, version, display_version = None, sp_next = False, type = None):
        if not os.path.isdir(self.output):
            print('no such directory: %s' % os.path.normpath(self.output))

            return False

        if display_version is None:
            display_version = version

        if type is None:
            type = self.type

        with builtin_os.chdir(self.output) as chdir:
            id_info = {}

            for dir in glob.iglob('patch/*', recursive = True):
                id = os.path.basename(dir)

                if not re.search(r'^\d{8}_\d{4}$', id):
                    continue

                path = os.path.join(dir, 'patch', type)

                if not os.path.isdir(path):
                    for _dir in glob.iglob(os.path.join(dir, 'patch/*', type), recursive = True):
                        path = _dir

                if os.path.isdir(path):
                    id_info[id] = os.path.abspath(path)

            info = {}

            for id in sorted(id_info.keys()):
                with builtin_os.chdir(id_info[id]) as _chdir:
                    for file in glob.iglob('**/*', recursive = True):
                        if os.path.isfile(file):
                            info[file] = os.path.abspath(file)

            with builtin_os.tmpdir(builtin_os.tmpfilename()) as _tmpdir:
                for file in info:
                    filename = self.expand_filename(file)

                    if filename:
                        os.makedirs(os.path.dirname(filename), exist_ok = True)

                        try:
                            shutil.copyfile(info[file], filename)
                        except Exception as e:
                            print(e)

                            return False

                if not self.process(version, display_version, id_info, sp_next, type):
                    return False

        return True

    # ------------------------------------------------------

    def process(self, version, display_version, id_info, sp_next, type):
        return True

    def installation(self, version, type):
        return os.path.join(self.output, 'installation', version, 'installation')

    def expand_filename(self, filename):
        return filename
