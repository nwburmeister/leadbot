#
# from email.mime.text import MIMEText
# from datetime import date
# import smtplib
#
# SMTP_SERVER = "smtp.gmail.com"
# SMTP_PORT = 587
# SMTP_USERNAME = "james@wallacemurry.com"
# SMTP_PASSWORD = "Hihihi56henry9!"
#
# EMAIL_TO = ["wittedhaddock@gmail.com", "help@communityphone.org"]
# EMAIL_FROM = "email@gmail.com"
# EMAIL_SUBJECT = "Demo Email : "
# EMAIL_SPACE = ", "
#
# DATE_FORMAT = "%d/%m/%Y"
#
# DATA='This is the content of the email.'
#
# def send_email():
#     msg = MIMEText(DATA)
#     msg['Subject'] = EMAIL_SUBJECT + " %s" % (date.today().strftime(DATE_FORMAT))
#     msg['To'] = EMAIL_SPACE.join(EMAIL_TO)
#     msg['From'] = EMAIL_FROM
#     mail = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
#     mail.starttls()
#     mail.login(SMTP_USERNAME, SMTP_PASSWORD)
#     mail.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
#     mail.quit()
#
# if __name__=='__main__':
#     send_email()
