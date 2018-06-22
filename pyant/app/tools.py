import glob
import os
import os.path
import re
import shutil
import tempfile
import zipfile

from lxml import etree

from pyant.builtin import os as builtin_os

__all__ = ('bn_cut_upgrade_installation', )

def bn_cut_upgrade_installation(installation_home):
    if os.path.isdir(installation_home):
        installation_upgrade = os.path.abspath('installation_upgrade')

        with builtin_os.chdir(installation_home) as chdir:
            for file in glob.iglob('**/*', recursive = True):
                if os.path.isfile(file):
                    dst = os.path.join(installation_upgrade, file)

                    if not os.path.isdir(os.path.dirname(dst)):
                        os.makedirs(os.path.dirname(dst), exist_ok = True)

                    shutil.copyfile(file, dst)

        with builtin_os.chdir(installation_upgrade) as chdir:
            zipfiles = []

            zipfiles += glob.glob('uca*.zip')
            zipfiles += glob.glob('usf*.zip')
            zipfiles += glob.glob('patch/uca*.zip')
            zipfiles += glob.glob('patch/usf*.zip')

            zipfiles += glob.glob('install*.zip')
            zipfiles += glob.glob('patch/install*.zip')

            uep_deletes = [
              'ums-client/procs/ppus/uca.ppu/uca-backup.pmu/uca-wsf-backup.par/conf/uca-wsf-backup-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-bo-report.pmu/uca-wsf-bo-report.par/conf/bo-report-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-ertwrapper.pmu/uca-wsf-ertwrapper.par/conf/ertwrapper-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-css-srm.pmu/uca-wsf-css-srm.par/conf/uca-wsf-srm-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-css-ssm.pmu/uca-wsf-css-ssm.par/conf/uca-wsf-ssm-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-fm.pmu/uca-wsf-fm.par/conf/uca-fm-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-inner.pmu/uca-wsf-inner.par/conf/uca-wsf-inner-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-license.pmu/uca-wsf-license.par/conf/uca-wsf-license-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-log.pmu/uca-wsf-log.par/conf/uca-wsf-log-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-mml.pmu/uca-wsf-mml-clis.par/conf/uca-wsf-mml-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-monitor.pmu/uca-wsf-monitor.par/conf/uca-wsf-monitor-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-pm.pmu/uca-wsf-pm.par/conf/uca-wsf-pm-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-poll.pmu/uca-wsf-poll.par/conf/uca-wsf-poll-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-role.pmu/uca-wsf-role.par/conf/uca-wsf-role-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-task.pmu/uca-wsf-task.par/conf/uca-wsf-task-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-unitsm.pmu/uca-wsf-unitsm.par/conf/uca-wsf-unitsm-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-user.pmu/uca-wsf-user.par/conf/uca-wsf-user-menutool.xml',
              'ums-client/procs/ppus/uca.ppu/uca-user.pmu/uca-wsf-user.par/conf/uca-wsf-user-sys-menutool.xml',

              'ums-client/procs/ppus/uca.ppu/uca-fm.pmu/uca-wsf-fm.par/conf/uca-fm-extensionimpl.xml',
              'ums-client/procs/ppus/uca.ppu/uca-pm.pmu/uca-wsf-pm.par/conf/uca-wsf-pm-extensionimpl.xml',
              'ums-client/procs/ppus/bnplatform.ppu/platform-api.pmu/bn-searcher-wsf.par/conf/bn-searcher-wsf-menutool.xml'
            ]

            for file in zipfiles:
                with builtin_os.tmpdir(tempfile.mkdtemp()) as tmpdir:
                    try:
                        with zipfile.ZipFile(os.path.join(chdir.path, file), 'r') as zip:
                            zip.extractall(tmpdir.path)
                    except Exception as e:
                        print(e)

                        return False

                    if re.search(r'^install.*\.zip$', os.path.basename(file)):
                        if os.path.isfile('conf/internalconfig.xml'):
                            try:
                                xml_parser = etree.XMLParser(strip_cdata=False)

                                tree = etree.parse('conf/internalconfig.xml', xml_parser)

                                for e in tree.findall('config'):
                                    key = e.get('key')

                                    if key == 'usf.components.ftpserver.session.max':
                                        for element in e.findall('processes/process/network'):
                                            if element.get('scale') == 'uep1':
                                                element.text = '110'
                                    elif key == 'usf.components.ftpserver.dataport':
                                        for element in e.findall('processes/process/network'):
                                            if element.get('scale') == 'uep1':
                                                element.text = '20870-20979'
                                    else:
                                        pass

                                tree.write('conf/internalconfig.xml', encoding='utf-8', pretty_print=True, xml_declaration=True)
                            except Exception as e:
                                print(e)

                                pass
                    else:
                        delete_files = []

                        for filename in glob.iglob('**/*', recursive = True):
                            if re.search(r'^ums-server\/works\/.*\/deploy-.*(fm|pm|hmf|e2e).*\.xml$', filename):
                                delete_files.append(filename)
                            elif os.path.basename(filename) in ('deploy-uep-main-main.xml', 'deploy-uep-mmlndf-mmlndf.xml', 'deploy-uep-umdproc-umdproc.xml', 'deploy-uep-web-web.xml'):
                                delete_files.append(filename)
                            elif filename.replace('\\', '/') in uep_deletes:
                                delete_files.append(filename)
                            else:
                                pass

                        if delete_files:
                            for filename in delete_files:
                                if os.path.isfile(filename):
                                    os.remove(filename)

                    try:
                        with zipfile.ZipFile(os.path.join(chdir.path, file), 'w') as zip:
                            for filename in glob.iglob('**/*', recursive = True):
                                zip.write(filename)

                            for filename in glob.iglob('**/.*', recursive = True):
                                zip.write(filename)
                    except Exception as e:
                        print(e)

                        return False

            delete_zipfiles = []
            delete_zipfiles += glob.glob('itmp*.zip')
            delete_zipfiles += glob.glob('patch/itmp*.zip')
            delete_zipfiles += glob.glob('pmservice*.zip')
            delete_zipfiles += glob.glob('patch/pmservice*.zip')

            for filename in delete_zipfiles:
                if os.path.isfile(filename):
                    os.remove(filename)

    return True