import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def send_email(subject, recipient, text_body):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = os.environ.get('EMAIL_SENDER')
    msg['To'] = recipient
    
    msg.attach(MIMEText(text_body, 'plain'))
    
    try:
        smtp = smtplib.SMTP(os.environ.get('SMTP_SERVER'), int(os.environ.get('SMTP_PORT')))
        smtp.starttls()
        smtp.login(os.environ.get('EMAIL_SENDER'), os.environ.get('EMAIL_PASSWORD'))
        smtp.send_message(msg)
        smtp.quit()
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send email: {str(e)}')
        return False
