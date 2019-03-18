import datetime
import time
import smtplib
import traceback
from app import logger
from app.models import Messages, db
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# TODO: MOVE SOMEWHERE ELSE


class RedditReader:

    def __init__(self, reddit, users_emails=[]):
        self.imap_ssl_host = 'imap.gmail.com'
        self.imap_ssl_port = 993
        self.SMTP_SERVER = "smtp.gmail.com"
        self.SMTP_PORT = 587
        self.username = 'router@wallacemurry.com'
        self.password = 'assaultedQuails'
        self.writer_emails = users_emails
        self.reddit = reddit

    def reply_checker(self):
        """
        METHOD THAT CONSTANTLY CHECKS FOR NEW MESSAGES IN REDDIT INBOX

        :return:
        """
        logger.info("ENTERED REDDIT INBOX SCRAPER")
        while True:
            try:
                # TODO: CHANGE TO STREAM FOR PROD
                # PULL REDDIT INBOX STREAM
                new_reddit_messages = self.reddit.reddit_conn.inbox.unread()
                # LOOP THROUGH REDDIT MESSAGES
                for message in new_reddit_messages:
                    # GET REDDIT USERNAME / ID OF NEW MESSAGE
                    reddit_username_of_new_message = message.author.name
                    message_id = message.id
                    # CHECK TO SEE IF MESSAGE IS ALREADY IN MESSAGE QUEUE
                    message_exists = Messages.query.filter_by(
                        recipient=reddit_username_of_new_message).filter_by(
                        ca_user_id_assoc=message_id).first()
                    if not message_exists:
                        # FIND PARENT COMMENT, SO WE CAN IDENTIFY WHO REACHED OUT
                        parent_message = Messages.query.filter_by(
                            recipient=reddit_username_of_new_message).filter_by(
                            ca_user_id_assoc='parent').first()
                        if parent_message:
                            # GET THE SENDERS EMAIL
                            sender = parent_message.sender
                            # GET THE BODY TEXT OF THE NEW MESSAGE
                            body = message.body
                            parent_message_subect = parent_message.subject
                            # THE IDEA IS TO CODE THE REDDIT-EMAIL LINK IN JSON:
                            reddit_user_email_id = "\"username\": \"{reddit_username_of_new_message}\", " \
                                                   "\"message_id\": \"{message_id}\", " \
                                                   "\"subject\": \"{subject}\"".format(
                                reddit_username_of_new_message=reddit_username_of_new_message,
                                message_id=message_id,
                                subject=message.subject)

                            subject = "{" + reddit_user_email_id + "}"
                            # STORE MESSAGE IN DATABASE
                            ca_message = Messages(sender=reddit_username_of_new_message,
                                               recipient=sender,
                                               body=body,
                                               subject=subject,
                                               date_sent=datetime.datetime.now(),
                                               has_been_sent_for_processing=0,
                                               ca_user_id_assoc=message.parent_id)

                            # WE HAVE ADDED NEW MESSAGE TO DB, TIME TO EMAIL THE COMPLAINING ABOUT USER WHO STARTED CONVO
                            # We want to notify the user that they received a response
                            Messages.add_record(ca_message)
                            # TODO: UPDATE FOR PROD
                            self.send_email(sender,
                                            "router@communityphone.org",
                                            body,
                                            subject)
                            ca_message.has_been_sent_for_processing = 1
                            self.reddit.reddit_conn.inbox.mark_read([message])
                            db.session.commit()
                        else:
                            # IF PARENT MESSAGE DOESNT EXIST, MARK AS READ
                            self.reddit.reddit_conn.inbox.mark_read([message])

            except Exception as e:
                logger.info("EXCEPTION IN REDDIT READER")
                traceback.print_exc()

            # logger.info("NOTHING NEW IN INBOX STREAM--SLEEPING")
            time.sleep(100)

    def send_email(self, to_email, from_email, body, subject):
        """
        METHOD FOR SENDING A NOTIFICATION EMAIL TO A CA USER THAT A NEW ITEM IS IN OUR REDDIT INBOX
        :param to_email:
        :param from_email:
        :param body:
        :param subject:
        :return:
        """
        # TODO: FIX SUBJECT TO INCLUDE REDDIT MESSAGE ID AND USERNAME
        # DATE_FORMAT = "%d/%m/%Y"
        EMAIL_TO = to_email
        EMAIL_FROM = from_email
        EMAIL_SUBJECT = subject
        EMAIL_SPACE = ", "
        MSG = MIMEMultipart()
        MSG['Subject'] = EMAIL_SUBJECT # + " %s" % (date.today().strftime(DATE_FORMAT))
        MSG['To'] = EMAIL_SPACE.join(EMAIL_TO)
        MSG['From'] = EMAIL_FROM
        MSG.attach(MIMEText(body, 'plain'))
        try:
            mail = smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT)
            mail.starttls()
            mail.login(self.username, self.password)
            mail.sendmail(EMAIL_FROM, EMAIL_TO, MSG.as_string())
            mail.quit()
        except Exception:
            logger.critical("FAILED TO SEND EMAIL IN REDDIT READER. EXITING")
            exit(1)