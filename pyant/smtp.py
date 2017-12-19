import email.header
import email.mime.multipart
import email.mime.text
import os
import smtplib

__all__ = ('sendmail',)

def sendmail(subject, to_addrs, cc_addrs = None, message = None, attaches = None, html = True):
    if not os.environ.get('SENDMAIL'):
        return True

    from_addr = 'admin@zte.com.cn'

    msg = email.mime.multipart.MIMEMultipart()
    msg['Subject'] = email.header.Header(subject, 'utf-8')
    msg['From'] = from_addr

    if isinstance(to_addrs, str):
        to_addrs = [to_addrs, ]

    msg['To'] = ','.join(to_addrs)

    if cc_addrs:
        if isinstance(cc_addrs, str):
            cc_addrs = (cc_addrs, )

            for cc in cc_addrs:
                if cc not in to_addrs:
                    to_addrs.append(cc)

        msg['Cc'] = ','.join(cc_addrs)

    if message:
        if html:
            msg.attach(email.mime.text.MIMEText(message, 'html', 'utf-8'))
        else:
            msg.attach(email.mime.text.MIMEText(message, 'plain', 'utf-8'))

    if attaches:
        for name, file in attaches.items():
            try:
                with open(file, 'rb') as f:
                    attach = email.mime.text.MIMEText(f.read(), 'base64', 'utf-8')
                    attach['Content-Type'] = 'application/octet-stream'
                    attach['Content-Disposition'] = 'attachment; filename = %s' % name

                    msg.attach(attach)
            except Exception as e:
                print(e)

                return False

    try:
        with smtplib.SMTP('10.30.18.230', 25) as smtp:
            smtp.login('ZhouYanQing181524', 'smtp@2013')
            smtp.sendmail(from_addr, to_addrs, msg.as_string())

        print('send mail to %s' % str(tuple(to_addrs)))

        return True
    except Exception as e:
        print(e)

        return False
